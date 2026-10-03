"""EnergyPlus 进程管理（QProcess 封装）。

非阻塞运行，通过信号通知输出与完成。禁止 ``waitForFinished`` 阻塞主线程。
运行目录准备与归档由 ``RunManager`` 负责，本类只管启动进程与收集输出。
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunResult:
    """运行结果。

    Attributes:
        run_id: 运行标识。
        run_dir: 运行目录。
        idf_path: 运行目录内的 IDF 路径。
        weather_path: 天气文件路径。
        start_time: 开始时间字符串。
        end_time: 结束时间字符串。
        elapsed: 耗时秒。
        exit_code: 退出码。
        success: 是否成功。
        error_message: 错误信息。
        output_files: 输出文件名列表。
        log_text: 完整日志文本。
        command: 完整命令行。
    """

    run_id: str
    run_dir: str
    idf_path: str
    weather_path: str = ""
    start_time: str = ""
    end_time: str = ""
    elapsed: float = 0.0
    exit_code: int = -1
    success: bool = False
    error_message: str = ""
    output_files: list[str] = field(default_factory=list)
    log_text: str = ""
    command: str = ""


class EPRunner(QObject):
    """EnergyPlus 进程运行器。

    Signals:
        lineOutput(str): 每行输出。
        stateChanged(str): 状态变更。
        finished(object): 运行完成，载荷为 RunResult。
        error(str): 错误信息。
    """

    lineOutput = Signal(str)
    stateChanged = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    STATE_IDLE = "idle"
    STATE_RUNNING = "running"
    STATE_FINISHED = "finished"
    STATE_ERROR = "error"

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._state = self.STATE_IDLE
        self._start_ts = 0.0
        self._current_result: RunResult | None = None
        self._log_lines: list[str] = []

    @property
    def state(self) -> str:
        """返回当前状态。"""
        return self._state

    @property
    def is_running(self) -> bool:
        """是否正在运行。"""
        return self._state == self.STATE_RUNNING

    def run(
        self,
        ep_executable: str,
        run_dir: str | Path,
        idf_filename: str,
        weather_filename: str = "",
        extra_args: str = "",
    ) -> RunResult | None:
        """在指定目录启动 EnergyPlus。

        Args:
            ep_executable: energyplus 可执行文件路径。
            run_dir: 工作目录（须已存在且含 IDF）。
            idf_filename: 工作目录内 IDF 文件名。
            weather_filename: 工作目录内天气文件名（可空）。
            extra_args: 附加命令行参数（空格分隔）。

        Returns:
            RunResult 或 None（启动失败）。
        """
        if self.is_running:
            self.error.emit("已有运行任务在进行中")
            return None
        if not ep_executable or not Path(ep_executable).exists():
            self.error.emit(f"无效的 EnergyPlus 可执行文件: {ep_executable}")
            return None

        run_dir_path = Path(run_dir)
        args: list[str] = []
        if weather_filename:
            args.extend(["-w", weather_filename])
        if extra_args:
            args.extend(extra_args.split())
        args.append(idf_filename)
        command = f"{ep_executable} {' '.join(args)}"

        result = RunResult(
            run_id=run_dir_path.name,
            run_dir=str(run_dir_path),
            idf_path=str(run_dir_path / idf_filename),
            weather_path=str(run_dir_path / weather_filename) if weather_filename else "",
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            command=command,
        )
        self._current_result = result
        self._log_lines = []
        self._start_ts = time.time()

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(run_dir_path))
        self._process.setProcessChannelMode(QProcess.MergedChannels)  # type: ignore[attr-defined]
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._set_state(self.STATE_RUNNING)
        self._log("=== EnergyPlus 运行开始 ===")
        self._log(f"工作目录: {run_dir_path}")
        self._log(f"IDF: {idf_filename}")
        if weather_filename:
            self._log(f"天气文件: {weather_filename}")
        self._log(f"命令: {command}")
        self._log("")

        self._process.start(ep_executable, args)
        if not self._process.waitForStarted(5000):
            self.error.emit("无法启动 EnergyPlus 进程")
            self._set_state(self.STATE_ERROR)
            self._process = None
            return None
        return result

    def cancel(self) -> None:
        """取消当前运行。"""
        if self._process and self.is_running:
            self._log("\n[用户取消运行]")
            self._process.kill()

    def _read_output(self) -> None:
        if not self._process:
            return
        data = bytes(self._process.readAllStandardOutput().data())
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
        for line in text.splitlines():
            self._log(line)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        elapsed = time.time() - self._start_ts
        if self._current_result is None:
            return
        r = self._current_result
        r.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r.elapsed = elapsed
        r.exit_code = exit_code
        r.success = exit_code == 0

        run_dir = Path(r.run_dir)
        r.output_files = []
        if run_dir.exists():
            idf_name = Path(r.idf_path).name
            for entry in sorted(run_dir.iterdir()):
                if entry.is_file() and entry.name != idf_name:
                    r.output_files.append(entry.name)

        self._log("")
        self._log(f"=== 运行结束 (退出码: {exit_code}, 耗时: {elapsed:.2f}s) ===")
        if r.success:
            self._log(f"输出文件: {len(r.output_files)} 个")
        else:
            self._log("运行失败，请检查 .err 文件")

        r.log_text = "\n".join(self._log_lines)
        self._set_state(self.STATE_FINISHED if r.success else self.STATE_ERROR)
        self.finished.emit(r)
        if self._process is not None:
            self._process.deleteLater()
        self._process = None

    def _on_error(self, proc_error: QProcess.ProcessError) -> None:
        msg = f"进程错误: {proc_error}"
        self._log(msg)
        self.error.emit(msg)
        self._set_state(self.STATE_ERROR)

    def _log(self, line: str) -> None:
        self._log_lines.append(line)
        self.lineOutput.emit(line)

    def _set_state(self, state: str) -> None:
        self._state = state
        self.stateChanged.emit(state)
