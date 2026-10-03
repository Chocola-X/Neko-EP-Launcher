"""应用装配（依赖注入组装根）。

构造各层实例并注入依赖。唯一允许访问全部层的模块。
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from src.core.idf.parser import IDFParser
from src.core.idf.serializer import IDFSerializer
from src.persistence.config_store import ConfigStore
from src.services.config_service import ConfigService
from src.services.ep_runner import EPRunner
from src.services.idd_service import IDDService
from src.services.idf_service import IDFService
from src.services.run_manager import RunManager

logger = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = APP_DIR / "data"
RUNS_DIR = DATA_DIR / "runs"
CONFIG_FILE = APP_DIR / "config.json"
RESOURCES_DIR = APP_DIR / "resources"
IDD_CACHE = RESOURCES_DIR / "idd_cache.json"


def setup_logging(level: int = logging.INFO) -> None:
    """统一配置日志：控制台 + 文件。"""
    APP_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(console)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            APP_DIR / "launcher.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        )
        root.addHandler(file_handler)
    except OSError:
        pass


class Application:
    """应用容器，构造并持有各层实例。"""

    def __init__(
        self, config_path: str | Path = CONFIG_FILE, runs_dir: str | Path = RUNS_DIR
    ) -> None:
        """初始化应用，装配依赖。

        Args:
            config_path: 配置文件路径。
            runs_dir: 运行归档目录。
        """
        self.config_store = ConfigStore(config_path)
        self.config_service = ConfigService(self.config_store)
        self.idf_service = IDFService(IDFParser(), IDFSerializer())
        self.idd_service = IDDService(IDD_CACHE)
        self.ep_runner = EPRunner()
        self.run_manager = RunManager(self.ep_runner, runs_dir)

    def load_idd(self) -> None:
        """根据配置加载 IDD（启动时调用）。"""
        idd_path = self.config_service.get_idd_path()
        if idd_path:
            try:
                self.idd_service.load(idd_path)
            except Exception as e:
                logger.warning("加载 IDD 失败: %s", e)

    def apply_theme(self) -> None:
        """根据配置应用主题。"""
        from src.ui.theme import apply_theme

        apply_theme(self.config_service.config.theme)
