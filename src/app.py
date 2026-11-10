"""应用装配（依赖注入组装根）。

构造各层实例并注入依赖。唯一允许访问全部层的模块。
"""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.ui.main_window import MainWindow

from src.core.idf.parser import IDFParser
from src.core.idf.serializer import IDFSerializer
from src.persistence.config_store import ConfigStore
from src.persistence.run_repository import RunRepository
from src.services.config_service import ConfigService
from src.services.ep_runner import EPRunner
from src.services.idd_service import IDDService
from src.services.idf_service import IDFService
from src.services.results_service import ResultsService
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
        self.results_service = ResultsService()
        self.ep_runner = EPRunner()
        self.run_manager = RunManager(self.ep_runner, runs_dir)
        self.run_repository = RunRepository(runs_dir)
        self._windows: list[MainWindow] = []

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

    def create_window(self, path: str | Path | None = None) -> MainWindow:
        """创建并显示一个主窗口，纳入应用窗口列表管理。"""
        from src.ui.main_window import MainWindow

        window = MainWindow(
            run_manager=self.run_manager,
            idf_service=self.idf_service,
            config_service=self.config_service,
            idd_service=self.idd_service,
            results_service=self.results_service,
            run_repository=self.run_repository,
        )
        self._windows.append(window)
        window.windowClosed.connect(self._unregister_window)
        window.destroyed.connect(lambda *_: self._unregister_window(window))
        window.newWindowRequested.connect(self._handle_new_window_requested)

        if path:
            window._open_file(str(path))
        window.show()
        return window

    def _unregister_window(self, window: MainWindow) -> None:
        """窗口销毁时从管理列表中注销。"""
        if window in self._windows:
            self._windows.remove(window)

    def _handle_new_window_requested(self, path: str) -> None:
        """响应窗口新建请求。"""
        self.create_window(path if path else None)

    @property
    def windows(self) -> list[MainWindow]:
        """返回当前所有活跃窗口列表（副本）。"""
        return list(self._windows)
