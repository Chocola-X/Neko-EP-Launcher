"""运行编排服务。

负责准备运行目录（复制 IDF/EPW，同名追加后缀而非删除）、调用 ``EPRunner``、
运行结束归档写 ``run.json``。禁止 ``shutil.rmtree`` 删除历史目录。
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.core.entities.run_options import RunOptions
from src.services.ep_runner import EPRunner, RunResult
from src.services.idf_service import IDFService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunRequest:
    """运行请求参数。

    Attributes:
        idf_path: IDF 文件路径。
        weather_path: 天气文件路径（可空）。
        run_id: 运行标识（空则用时间戳）。
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
        self._runs_dir.mkdir(parents=True, exist_ok=True)
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
        idf_path = Path(request.idf_path)
        if not idf_path.exists():
            self.error.emit(f"无效的 IDF 文件: {request.idf_path}")
            return None

        run_id = request.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._make_unique_dir(run_id)
        run_dir.mkdir(parents=True)

        idf_dest = run_dir / idf_path.name
        shutil.copy2(idf_path, idf_dest)
        if request.analysis_outputs:
            try:
                service = IDFService()
                document = service.open(idf_dest)
                service.configure_outputs(document)
                service.save(document, idf_dest)
            except Exception as exc:
                logger.exception("配置运行副本分析输出失败")
                self.error.emit(f"配置分析输出失败: {exc}")
                return None

        weather_filename = ""
        if request.weather_path and Path(request.weather_path).exists():
            wf_dest = run_dir / Path(request.weather_path).name
            shutil.copy2(request.weather_path, wf_dest)
            weather_filename = wf_dest.name

        result = self._runner.run(
            ep_executable=ep_executable,
            run_dir=run_dir,
            idf_filename=idf_dest.name,
            weather_filename=weather_filename,
            extra_args=request.extra_args,
            run_options=request.options,
        )
        if result is None:
            return None
        self.runStarted.emit(result.run_id)
        return result

    def _make_unique_dir(self, run_id: str) -> Path:
        """生成唯一运行目录，同名时追加 _1/_2 后缀，禁止删除已有目录。"""
        base = self._runs_dir / run_id
        if not base.exists():
            return base
        n = 1
        while True:
            cand = self._runs_dir / f"{run_id}_{n}"
            if not cand.exists():
                return cand
            n += 1

    def _on_finished(self, result: RunResult) -> None:
        self._write_run_json(result)
        self.runFinished.emit(result)

    def _write_run_json(self, result: RunResult) -> None:
        """运行结束写 run.json 元数据。"""
        run_dir = Path(result.run_dir)
        meta = {
            "run_id": result.run_id,
            "start_time": result.start_time,
            "end_time": result.end_time,
            "elapsed": result.elapsed,
            "exit_code": result.exit_code,
            "success": result.success,
            "command": result.command,
            "idf_path": result.idf_path,
            "weather_path": result.weather_path,
            "idf_sha256": self._file_sha256(result.idf_path),
            "weather_sha256": self._file_sha256(result.weather_path) if result.weather_path else "",
            "output_files": self._list_output_files(run_dir),
        }
        try:
            (run_dir / "run.json").write_text(
                json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("写入 run.json 失败: %s", e)

    @staticmethod
    def _file_sha256(path: str) -> str:
        """计算文件 SHA256，失败返回空串。"""
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return ""

    @staticmethod
    def _list_output_files(run_dir: Path) -> list[dict[str, object]]:
        """列出输出文件及大小。"""
        files: list[dict[str, object]] = []
        if not run_dir.exists():
            return files
        for entry in sorted(run_dir.iterdir()):
            if entry.is_file() and entry.name not in ("run.json",):
                files.append({"name": entry.name, "size": entry.stat().st_size})
        return files
