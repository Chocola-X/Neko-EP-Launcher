"""运行编排服务。

每个窗口拥有独立实例。该实例为任务占用归档目录、冻结输入、启动引擎，
并在任务结束后记录实际命令及输出。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.core.entities.run_options import RunOptions
from src.services.ep_runner import EPRunner, RunResult
from src.services.run_preparation import (
    freeze_inputs,
    plan_run,
    read_engine_version,
    validate_archive_name,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunRequest:
    """运行请求参数。

    Attributes:
        idf_path: IDF 文件路径。
        weather_path: 天气文件路径（可空）。
        run_id: 归档目录名称（空则用时间戳）。
        extra_args: 附加命令行参数。
        options: 结构化运行选项（优先于 extra_args）。
        analysis_outputs: 在运行副本中启用 SQLite 与汇总输出。
    """

    idf_path: str
    weather_path: str = ""
    run_id: str = ""
    extra_args: str = ""
    options: RunOptions | None = None
    analysis_outputs: bool = False


class RunManager(QObject):
    """运行编排服务。

    Signals:
        runStarted(str): 运行开始，载荷为 run_id。
        runFinished(object): 运行完成，载荷为 RunResult。
        lineOutput(str): 运行输出行。
        stateChanged(str): 运行器状态变更。
        error(str): 错误信息。
    """

    runStarted = Signal(str)
    runFinished = Signal(object)
    lineOutput = Signal(str)
    stateChanged = Signal(str)
    error = Signal(str)

    def __init__(
        self, runner: EPRunner, runs_dir: str | Path, parent: QObject | None = None
    ) -> None:
        """初始化运行管理器。

        Args:
            runner: EnergyPlus 运行器。
            runs_dir: 运行归档根目录。
        """
        super().__init__(parent)
        self._runner = runner
        self._runs_dir = Path(runs_dir)
        self._inputs: list[dict[str, str]] = []
        self._engine_version = ""
        self._runner.lineOutput.connect(self.lineOutput)
        self._runner.stateChanged.connect(self.stateChanged)
        self._runner.finished.connect(self._on_finished)
        self._runner.error.connect(self.error)

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self._runner.is_running

    @property
    def state(self) -> str:
        """返回运行器状态。"""
        return self._runner.state

    def cancel(self) -> None:
        """取消当前运行。"""
        self._runner.cancel()

    def start(self, ep_executable: str, request: RunRequest) -> RunResult | None:
        """启动一次运行。

        Args:
            ep_executable: energyplus 可执行文件路径。
            request: 运行请求。

        Returns:
            RunResult 或 None（参数错误）。
        """
        if self.is_running:
            self.error.emit("此窗口已有运行任务")
            return None
        try:
            run_id = request.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
            validate_archive_name(run_id, "运行 ID")
            options = request.options or RunOptions.from_extra_args(request.extra_args)
            preparation = plan_run(
                ep_executable,
                request.idf_path,
                request.weather_path,
                options,
                analysis_outputs=request.analysis_outputs,
            )
            self._engine_version = read_engine_version(preparation.executable)
            run_dir = self._create_run_dir(run_id)
            work_dir = run_dir / "inputs"
            self._inputs = freeze_inputs(preparation, work_dir)
            result = self._runner.run(
                ep_executable=str(preparation.executable),
                run_dir=run_dir,
                idf_filename=f"./{preparation.model.destination.as_posix()}",
                run_options=preparation.options,
                working_directory=work_dir,
                source_idf_path=str(preparation.model.source),
            )
            if result is None:
                self._inputs = []
                return None
            if self.is_running:
                self.runStarted.emit(result.run_id)
            return result
        except Exception as exc:
            self._inputs = []
            logger.warning("运行准备失败：%s", exc)
            self.error.emit(f"运行准备失败：{exc}")
            return None

    def _create_run_dir(self, run_id: str) -> Path:
        """在实际归档根下原子占用目录名，跳过所有已存在条目。"""
        root = self._runs_dir.resolve()
        root.mkdir(parents=True, exist_ok=True)
        suffix = 0
        while True:
            candidate = root / (f"{run_id}_{suffix}" if suffix else run_id)
            try:
                candidate.mkdir()
            except FileExistsError:
                suffix += 1
            else:
                return candidate

    def _on_finished(self, result: RunResult) -> None:
        inputs, self._inputs = self._inputs, []
        self._write_run_json(result, inputs)
        self.runFinished.emit(result)

    def _write_run_json(self, result: RunResult, inputs: list[dict[str, str]]) -> None:
        """写入实际命令、启动前输入哈希与输出文件清单。"""
        run_dir = Path(result.run_dir)
        try:
            hashes = {item["kind"]: item["sha256"] for item in inputs if item["kind"] != "dependency"}
            meta = {
                "run_id": result.run_id,
                "task_id": result.task_id,
                "start_time": result.start_time,
                "end_time": result.end_time,
                "elapsed": result.elapsed,
                "exit_code": result.exit_code,
                "success": result.success,
                "cancelled": result.cancelled,
                "error_message": result.error_message,
                "command": result.command,
                "command_args": result.command_args,
                "engine_version": self._engine_version,
                "output_directory": str(run_dir),
                "working_directory": result.working_directory,
                "idf_path": result.idf_path,
                "weather_path": result.weather_path,
                "idd_path": result.idd_path,
                "idf_sha256": hashes.get("idf", ""),
                "weather_sha256": hashes.get("weather", ""),
                "idd_sha256": hashes.get("idd", ""),
                "inputs": inputs,
                "output_files": self._list_output_files(run_dir),
            }
            temp = run_dir / ".run.json.tmp"
            temp.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
            temp.replace(run_dir / "run.json")
        except OSError as exc:
            logger.warning("写入 run.json 失败: %s", exc)
            self.error.emit(f"运行结束，但归档元数据写入失败：{exc}")

    @staticmethod
    def _list_output_files(run_dir: Path) -> list[dict[str, object]]:
        """列出输出文件及大小。"""
        files: list[dict[str, object]] = []
        if not run_dir.exists():
            return files
        for entry in sorted(run_dir.iterdir()):
            if entry.is_file() and entry.name not in {"run.json", ".run.json.tmp"}:
                files.append({"name": entry.name, "size": entry.stat().st_size})
        return files
