"""运行历史仓库。

索引 ``data/runs/`` 下所有 ``run.json``，提供列表/过滤/详情查询。
仅做读写，不含业务判断。禁止 import PySide6。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class RunRecord:
    """一次运行的历史记录（来自 ``run.json``）。

    Attributes:
        run_id: 运行标识。
        run_dir: 运行目录路径。
        start_time: 开始时间。
        end_time: 结束时间。
        elapsed: 耗时（秒）。
        exit_code: 退出码。
        success: 是否成功。
        command: 命令行。
        idf_path: IDF 文件名。
        weather_path: 天气文件名。
        idf_sha256: IDF 哈希。
        weather_sha256: 天气文件哈希。
        output_files: 输出文件列表。
    """

    run_id: str
    run_dir: str
    start_time: str = ""
    end_time: str = ""
    elapsed: float = 0.0
    exit_code: int = -1
    success: bool = False
    command: str = ""
    idf_path: str = ""
    weather_path: str = ""
    idf_sha256: str = ""
    weather_sha256: str = ""
    output_files: list[dict[str, object]] = field(default_factory=list)


class RunRepository:
    """运行历史仓库。"""

    def __init__(self, runs_dir: str | Path) -> None:
        """初始化仓库。

        Args:
            runs_dir: 运行归档根目录。
        """
        self._runs_dir = Path(runs_dir)

    def list_runs(self) -> list[RunRecord]:
        """列出所有历史运行，按开始时间降序。"""
        records: list[RunRecord] = []
        if not self._runs_dir.exists():
            return records
        for run_dir in self._runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            record = self.load_run(run_dir)
            if record is not None:
                records.append(record)
        records.sort(key=lambda r: r.start_time, reverse=True)
        return records

    def load_run(self, run_dir: str | Path) -> RunRecord | None:
        """加载单次运行记录。

        Args:
            run_dir: 运行目录路径。

        Returns:
            运行记录，无 ``run.json`` 时返回 None。
        """
        d = Path(run_dir)
        json_path = d / "run.json"
        if not json_path.exists():
            return None
        try:
            data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("读取 run.json 失败: %s", e)
            return None
        return RunRecord(
            run_id=str(data.get("run_id", d.name)),
            run_dir=str(d),
            start_time=str(data.get("start_time", "")),
            end_time=str(data.get("end_time", "")),
            elapsed=float(data.get("elapsed", 0.0)),
            exit_code=int(data.get("exit_code", -1)),
            success=bool(data.get("success", False)),
            command=str(data.get("command", "")),
            idf_path=str(data.get("idf_path", "")),
            weather_path=str(data.get("weather_path", "")),
            idf_sha256=str(data.get("idf_sha256", "")),
            weather_sha256=str(data.get("weather_sha256", "")),
            output_files=list(data.get("output_files", [])),
        )

    def get_run_by_id(self, run_id: str) -> RunRecord | None:
        """按 run_id 查找运行记录。"""
        run_dir = self._runs_dir / run_id
        if run_dir.exists():
            return self.load_run(run_dir)
        for d in self._runs_dir.iterdir():
            if d.is_dir() and d.name.startswith(run_id):
                record = self.load_run(d)
                if record is not None:
                    return record
        return None

    def filter_runs(
        self,
        success_only: bool = False,
        idf_name: str = "",
    ) -> list[RunRecord]:
        """过滤运行记录。

        Args:
            success_only: 仅返回成功的运行。
            idf_name: IDF 文件名过滤（子串匹配）。
        """
        records = self.list_runs()
        if success_only:
            records = [r for r in records if r.success]
        if idf_name:
            records = [r for r in records if idf_name in r.idf_path]
        return records
