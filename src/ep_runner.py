"""EnergyPlus 运行器：管理子进程、实时输出、结果收集。"""
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtCore import QProcess, QObject, Signal, QTimer


@dataclass
class RunResult:
    """运行结果。"""
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
    output_files: list = field(default_factory=list)
    log_text: str = ""


class EPRunner(QObject):
    """EnergyPlus 运行器。"""

    lineOutput = Signal(str)
    stateChanged = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    STATE_IDLE = "idle"
    STATE_RUNNING = "running"
    STATE_FINISHED = "finished"
    STATE_ERROR = "error"

    def __init__(self, runs_dir: str, parent=None):
        super().__init__(parent)
        self._runs_dir = Path(runs_dir)
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._process: Optional[QProcess] = None
        self._state = self.STATE_IDLE
        self._start_ts = 0.0
        self._current_result: Optional[RunResult] = None
        self._log_lines = []

    @property
    def state(self):
        return self._state

    @property
    def is_running(self):
        return self._state == self.STATE_RUNNING

    def run(self, ep_executable: str, idf_path: str, weather_path: str = "",
            extra_args: str = "", run_id: str = "") -> Optional[RunResult]:
        if self.is_running:
            self.error.emit("已有运行任务在进行中")
            return None

        if not ep_executable or not Path(ep_executable).exists():
            self.error.emit(f"无效的 EnergyPlus 可执行文件: {ep_executable}")
            return None
        if not idf_path or not Path(idf_path).exists():
            self.error.emit(f"无效的 IDF 文件: {idf_path}")
            return None

        if not run_id:
            run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = self._runs_dir / run_id
        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True)

        idf_src = Path(idf_path)
        idf_dest = run_dir / idf_src.name
        shutil.copy2(idf_src, idf_dest)

        result = RunResult(
            run_id=run_id,
            run_dir=str(run_dir),
            idf_path=str(idf_dest),
            weather_path=weather_path,
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        self._current_result = result
        self._log_lines = []
        self._start_ts = time.time()

        args = []
        if weather_path and Path(weather_path).exists():
            wf_dest = run_dir / Path(weather_path).name
            shutil.copy2(weather_path, wf_dest)
            args.extend(["-w", wf_dest.name])
        if extra_args:
            args.extend(extra_args.split())
        args.append(idf_dest.name)

        self._process = QProcess(self)
        self._process.setWorkingDirectory(str(run_dir))
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read_output)
        self._process.finished.connect(self._on_finished)
        self._process.errorOccurred.connect(self._on_error)

        self._set_state(self.STATE_RUNNING)
        self._log(f"=== EnergyPlus 运行开始 ===")
        self._log(f"运行 ID: {run_id}")
        self._log(f"工作目录: {run_dir}")
        self._log(f"IDF: {idf_dest.name}")
        if weather_path:
            self._log(f"天气文件: {Path(weather_path).name}")
        self._log(f"命令: {ep_executable} {' '.join(args)}")
        self._log("")

        self._process.start(ep_executable, args)
        if not self._process.waitForStarted(5000):
            self.error.emit("无法启动 EnergyPlus 进程")
            self._set_state(self.STATE_ERROR)
            return None

        return result

    def cancel(self):
        if self._process and self.is_running:
            self._log("\n[用户取消运行]")
            self._process.kill()

    def _read_output(self):
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data()
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
        for line in text.splitlines():
            self._log(line)

    def _on_finished(self, exit_code, exit_status):
        elapsed = time.time() - self._start_ts
        if self._current_result is None:
            return
        r = self._current_result
        r.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        r.elapsed = elapsed
        r.exit_code = exit_code
        r.success = (exit_code == 0)
        r.log_text = "\n".join(self._log_lines)

        run_dir = Path(r.run_dir)
        r.output_files = []
        if run_dir.exists():
            for entry in sorted(run_dir.iterdir()):
                if entry.is_file() and entry.name != Path(r.idf_path).name:
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
        self._process = None

    def _on_error(self, proc_error):
        msg = f"进程错误: {proc_error}"
        self._log(msg)
        self.error.emit(msg)
        self._set_state(self.STATE_ERROR)

    def _log(self, line):
        self._log_lines.append(line)
        self.lineOutput.emit(line)

    def _set_state(self, state):
        self._state = state
        self.stateChanged.emit(state)
