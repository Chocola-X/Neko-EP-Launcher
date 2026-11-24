"""EnergyPlus 进程管理（QProcess 封装）。

非阻塞运行，通过信号通知输出与完成。禁止 ``waitForFinished`` 阻塞主线程。
运行目录准备与归档由 ``RunManager`` 负责，本类只管启动进程与收集输出。
"""

from __future__ import annotations

import logging
import shlex
import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QObject, QProcess, Signal

from src.core.entities.run_options import RunOptions

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
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
        command: 便于阅读的命令行。
        task_id: 与用户可编辑的运行目录名独立的内部任务标识。
        command_args: 传给进程的完整参数数组，首项是可执行文件。
        working_directory: 引擎进程的工作目录。
        source_idf_path: 用户选择的原始模型路径。
        idd_path: 实际使用的 IDD 快照路径。
        cancelled: 是否由用户取消。
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
    output_files: tuple[str, ...] = ()
    log_text: str = ""
    command: str = ""
    task_id: str = field(default_factory=lambda: uuid4().hex)
    command_args: tuple[str, ...] = ()
    working_directory: str = ""
    source_idf_path: str = ""
    idd_path: str = ""
    cancelled: bool = False


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
        run_options: RunOptions | None = None,
        *,
        working_directory: Path | None = None,
        source_idf_path: str = "",
    ) -> RunResult | None:
        """在指定目录启动 EnergyPlus。

        Args:
            ep_executable: energyplus 可执行文件路径。
            run_dir: 工作目录（须已存在且含 IDF）。
            idf_filename: 工作目录内 IDF 文件名。
            weather_filename: 工作目录内天气文件名（可空）。
            extra_args: 附加命令行参数（空格分隔）。
            run_options: 结构化运行选项（优先于 extra_args）。
            working_directory: 输入快照目录，省略时使用运行目录。
            source_idf_path: 提交任务时的原始模型路径。

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
        work_dir = working_directory or run_dir_path
        if run_options is not None:
            if weather_filename and not run_options.weather_path:
                run_options = replace(run_options, weather_path=weather_filename)
            weather_filename = run_options.weather_path
            args = run_options.to_args(idf_filename)
        else:
            args = []
            if weather_filename:
                args.extend(["-w", weather_filename])
            if extra_args:
                args.extend(shlex.split(extra_args))
            args.append(idf_filename)
        command_args = (ep_executable, *args)
        command = shlex.join(command_args)

        result = RunResult(
            run_id=run_dir_path.name,
            run_dir=str(run_dir_path),
            idf_path=str(work_dir / idf_filename),
            weather_path=str(work_dir / weather_filename) if weather_filename else "",
            idd_path=str(work_dir / run_options.idd_path)
            if run_options and run_options.idd_path else "",
            source_idf_path=source_idf_path,
            working_directory=str(work_dir),
            command_args=command_args,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            command=command,
        )
        self._current_result = result
        self._log_lines = []
        self._start_ts = time.monotonic()

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(work_dir))
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._set_state(self.STATE_RUNNING)
        self._log("=== EnergyPlus 运行开始 ===")
        self._log(f"工作目录: {work_dir}")
        self._log(f"IDF: {idf_filename}")
        if weather_filename:
            self._log(f"天气文件: {weather_filename}")
        self._log(f"命令: {command}")
        self._log("")

        self._process.start(ep_executable, args)
        return result

    def cancel(self) -> None:
        """取消当前运行。"""
        if self._process and self._current_result and not self._current_result.cancelled:
            self._current_result = replace(self._current_result, cancelled=True)
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

    def _on_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._current_result is None:
            return
        self._read_output()
        result = self._current_result
        elapsed = time.monotonic() - self._start_ts
        success = (
            exit_code == 0
            and exit_status == QProcess.ExitStatus.NormalExit
            and not result.cancelled
        )
        try:
            output_files = tuple(
                entry.name
                for entry in sorted(Path(result.run_dir).iterdir())
                if entry.is_file() and entry != Path(result.idf_path)
            )
        except OSError as exc:
            logger.warning("无法列出运行输出：%s", exc)
            output_files = ()

        self._log("")
        self._log(f"=== 运行结束 (退出码: {exit_code}, 耗时: {elapsed:.2f}s) ===")
        if success:
            self._log(f"输出文件: {len(output_files)} 个")
        elif not result.cancelled:
            self._log("运行失败，请检查 .err 文件")

        completed = replace(
            result,
            end_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            elapsed=elapsed,
            exit_code=exit_code,
            success=success,
            output_files=output_files,
            log_text="\n".join(self._log_lines),
        )
        self._current_result = None
        if self._process is not None:
            self._process.deleteLater()
        self._process = None
        self._set_state(self.STATE_FINISHED if success else self.STATE_ERROR)
        self.finished.emit(completed)

    def _on_error(self, proc_error: QProcess.ProcessError) -> None:
        if self._current_result is None or self._process is None:
            return
        msg = f"进程错误: {self._process.errorString()}"
        self._current_result = replace(self._current_result, error_message=msg)
        self._log(msg)
        if not self._current_result.cancelled:
            self.error.emit(msg)
        if proc_error == QProcess.ProcessError.FailedToStart:
            self._on_finished(-1, QProcess.ExitStatus.CrashExit)

    def _log(self, line: str) -> None:
        self._log_lines.append(line)
        self.lineOutput.emit(line)

    def _set_state(self, state: str) -> None:
        self._state = state
        self.stateChanged.emit(state)
