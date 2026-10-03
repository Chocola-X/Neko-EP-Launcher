"""JSON 配置读写（持久化层）。

仅做读写，不含业务判断。路径由调用方注入，禁止全局单例。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.entities.config import AppConfig
from src.core.exceptions import ConfigError

logger = logging.getLogger(__name__)


class ConfigStore:
    """配置文件读写。"""

    def __init__(self, config_path: str | Path) -> None:
        """初始化配置存储。

        Args:
            config_path: 配置文件路径。
        """
        self._path = Path(config_path)

    @property
    def path(self) -> Path:
        """返回配置文件路径。"""
        return self._path

    def load(self) -> AppConfig:
        """读取配置，文件不存在或损坏时返回默认配置。"""
        if not self._path.exists():
            logger.info("配置文件不存在，使用默认配置: %s", self._path)
            return AppConfig()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("配置文件损坏，使用默认配置: %s", e)
            return AppConfig()
        except OSError as e:
            raise ConfigError(f"无法读取配置文件: {e}") from e
        if not isinstance(data, dict):
            logger.warning("配置文件格式错误，使用默认配置")
            return AppConfig()
        return AppConfig.from_dict(data)

    def save(self, config: AppConfig) -> None:
        """写入配置。

        Args:
            config: 应用配置。

        Raises:
            ConfigError: 写入失败。
        """
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._path.write_text(
                json.dumps(config.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            raise ConfigError(f"无法写入配置文件: {e}") from e
