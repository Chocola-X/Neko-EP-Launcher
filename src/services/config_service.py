"""配置业务服务。

编排 ``ConfigStore`` 读写，提供 EnergyPlus 路径解析等业务方法。实例由
``app.py`` 构造并注入，禁止模块级单例。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.entities.config import AppConfig
from src.persistence.config_store import ConfigStore

logger = logging.getLogger(__name__)

_EP_EXECUTABLE_NAMES = ("energyplus", "energyplus-9.4.0")


class ConfigService:
    """配置业务服务。"""

    def __init__(self, store: ConfigStore) -> None:
        """初始化配置服务。

        Args:
            store: 配置存储。
        """
        self._store = store
        self._config: AppConfig = store.load()

    @property
    def config(self) -> AppConfig:
        """返回当前配置（可变引用，调用方修改后需 save）。"""
        return self._config

    def save(self) -> None:
        """持久化当前配置。"""
        self._store.save(self._config)

    def reload(self) -> None:
        """从存储重新加载配置。"""
        self._config = self._store.load()

    def add_recent_file(self, path: str) -> None:
        """添加最近文件并保存。"""
        self._config.add_recent_file(path)
        self.save()

    def get_ep_executable(self) -> str:
        """返回 EnergyPlus 可执行文件路径，未找到返回空串。"""
        ep_path = Path(self._config.energyplus_path)
        if not ep_path.exists():
            return ""
        for name in _EP_EXECUTABLE_NAMES:
            exe = ep_path / name
            if exe.exists() and exe.is_file():
                return str(exe)
        return ""

    def get_idd_path(self) -> str:
        """返回 Energy+.idd 路径，不存在返回空串。"""
        idd = Path(self._config.energyplus_path) / "Energy+.idd"
        return str(idd) if idd.exists() else ""

    def get_default_weather_dir(self) -> str:
        """返回 EnergyPlus 自带天气目录，不存在返回空串。"""
        wd = Path(self._config.energyplus_path) / "WeatherData"
        return str(wd) if wd.exists() else ""

    def get_example_dir(self) -> str:
        """返回 ExampleFiles 目录，不存在返回空串。"""
        ex = Path(self._config.energyplus_path) / "ExampleFiles"
        return str(ex) if ex.exists() else ""

    def is_ep_valid(self) -> bool:
        """检查 EnergyPlus 路径是否有效（含可执行文件与 IDD）。"""
        return bool(self.get_ep_executable()) and bool(self.get_idd_path())
