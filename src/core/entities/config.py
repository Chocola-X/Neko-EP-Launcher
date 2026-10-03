"""应用配置数据模型（值对象）。

仅含数据结构与默认值，不含 I/O。读写由 ``persistence.config_store`` 负责，
业务由 ``services.config_service`` 负责。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class AppConfig:
    """应用配置（可变，因运行期会更新最近文件等）。

    Attributes:
        energyplus_path: EnergyPlus 安装目录。
        weather_dir: 天气文件目录。
        last_idf_dir: 最近打开的 IDF 目录。
        last_weather_file: 最近使用的天气文件。
        theme: 主题名（system/light/dark/fusion）。
        recent_files: 最近打开的文件列表（最多 10 条）。
        run_options: 附加运行参数。
    """

    energyplus_path: str = ""
    weather_dir: str = ""
    last_idf_dir: str = ""
    last_weather_file: str = ""
    theme: str = "system"
    recent_files: list[str] = field(default_factory=list)
    run_options: str = "-r"

    def add_recent_file(self, path: str) -> None:
        """添加最近文件到列表头部，去重，最多保留 10 条。"""
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        del self.recent_files[10:]

    def to_dict(self) -> dict[str, object]:
        """序列化为可 JSON 化的字典。"""
        return {
            "energyplus_path": self.energyplus_path,
            "weather_dir": self.weather_dir,
            "last_idf_dir": self.last_idf_dir,
            "last_weather_file": self.last_weather_file,
            "theme": self.theme,
            "recent_files": list(self.recent_files),
            "run_options": self.run_options,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> AppConfig:
        """从字典构造，缺失字段用默认值。"""
        recent_raw = data.get("recent_files", [])
        recent_files = [str(p) for p in recent_raw] if isinstance(recent_raw, list) else []
        return cls(
            energyplus_path=str(data.get("energyplus_path", "")),
            weather_dir=str(data.get("weather_dir", "")),
            last_idf_dir=str(data.get("last_idf_dir", "")),
            last_weather_file=str(data.get("last_weather_file", "")),
            theme=str(data.get("theme", "system")),
            recent_files=recent_files,
            run_options=str(data.get("run_options", "-r")),
        )
