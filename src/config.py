"""应用配置管理模块。"""
import json
import os
from pathlib import Path

DEFAULT_EP_PATH = "/run/media/chocola/DATA/Building_energy-saving_shading/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64"

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
RUNS_DIR = DATA_DIR / "runs"
CONFIG_FILE = APP_DIR / "config.json"


class Config:
    """全局配置单例。"""

    def __init__(self):
        self.energyplus_path = DEFAULT_EP_PATH
        self.weather_dir = ""
        self.last_idf_dir = ""
        self.last_weather_file = ""
        self.theme = "system"
        self.recent_files = []
        self.run_options = "-r"
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.energyplus_path = data.get("energyplus_path", DEFAULT_EP_PATH)
                self.weather_dir = data.get("weather_dir", "")
                self.last_idf_dir = data.get("last_idf_dir", "")
                self.last_weather_file = data.get("last_weather_file", "")
                self.theme = data.get("theme", "system")
                self.recent_files = data.get("recent_files", [])
                self.run_options = data.get("run_options", "-r")
            except (json.JSONDecodeError, OSError):
                pass

    def save(self):
        data = {
            "energyplus_path": self.energyplus_path,
            "weather_dir": self.weather_dir,
            "last_idf_dir": self.last_idf_dir,
            "last_weather_file": self.last_weather_file,
            "theme": self.theme,
            "recent_files": self.recent_files[:10],
            "run_options": self.run_options,
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError:
            pass

    def add_recent_file(self, path):
        path = os.path.normpath(path)
        if path in self.recent_files:
            self.recent_files.remove(path)
        self.recent_files.insert(0, path)
        self.recent_files = self.recent_files[:10]
        self.save()

    def get_ep_executable(self):
        ep_path = Path(self.energyplus_path)
        if not ep_path.exists():
            return ""
        for name in ("energyplus", "energyplus-9.4.0"):
            exe = ep_path / name
            if exe.exists() and os.access(exe, os.X_OK):
                return str(exe)
        return ""

    def get_idd_path(self):
        idd = Path(self.energyplus_path) / "Energy+.idd"
        return str(idd) if idd.exists() else ""

    def get_default_weather_dir(self):
        wd = Path(self.energyplus_path) / "WeatherData"
        return str(wd) if wd.exists() else ""

    def get_example_dir(self):
        ex = Path(self.energyplus_path) / "ExampleFiles"
        return str(ex) if ex.exists() else ""


config = Config()
