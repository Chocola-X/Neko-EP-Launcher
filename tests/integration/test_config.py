"""配置存储与服务集成测试。"""

from __future__ import annotations

from pathlib import Path

from src.core.entities.config import AppConfig
from src.persistence.config_store import ConfigStore
from src.services.config_service import ConfigService


def test_config_store_load_missing(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    cfg = store.load()
    assert cfg.energyplus_path == ""
    assert cfg.theme == "system"


def test_config_store_save_load(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    cfg = AppConfig(energyplus_path="/ep", theme="dark", run_options="-r -p")
    store.save(cfg)
    assert (tmp_path / "config.json").exists()
    loaded = store.load()
    assert loaded.energyplus_path == "/ep"
    assert loaded.theme == "dark"
    assert loaded.run_options == "-r -p"


def test_config_store_load_corrupt(tmp_path: Path) -> None:
    p = tmp_path / "config.json"
    p.write_text("{invalid json", encoding="utf-8")
    store = ConfigStore(p)
    cfg = store.load()
    assert cfg.energyplus_path == ""


def test_config_service_save_reload(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    svc = ConfigService(store)
    svc.config.energyplus_path = "/ep"
    svc.config.theme = "dark"
    svc.save()

    store2 = ConfigStore(tmp_path / "config.json")
    svc2 = ConfigService(store2)
    assert svc2.config.energyplus_path == "/ep"
    assert svc2.config.theme == "dark"


def test_config_service_add_recent(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    svc = ConfigService(store)
    svc.add_recent_file("/a.idf")
    svc.add_recent_file("/b.idf")
    assert svc.config.recent_files == ["/b.idf", "/a.idf"]
    assert (tmp_path / "config.json").exists()


def test_config_service_ep_paths(tmp_path: Path) -> None:
    ep_dir = tmp_path / "ep"
    ep_dir.mkdir()
    (ep_dir / "energyplus").write_text("#!/bin/sh\n")
    (ep_dir / "Energy+.idd").write_text("idd")
    (ep_dir / "WeatherData").mkdir()
    (ep_dir / "ExampleFiles").mkdir()

    store = ConfigStore(tmp_path / "config.json")
    svc = ConfigService(store)
    svc.config.energyplus_path = str(ep_dir)
    assert svc.get_ep_executable() != ""
    assert svc.get_idd_path() != ""
    assert svc.get_default_weather_dir() != ""
    assert svc.get_example_dir() != ""
    assert svc.is_ep_valid()


def test_config_service_invalid_ep(tmp_path: Path) -> None:
    store = ConfigStore(tmp_path / "config.json")
    svc = ConfigService(store)
    svc.config.energyplus_path = "/nonexistent"
    assert svc.get_ep_executable() == ""
    assert not svc.is_ep_valid()
