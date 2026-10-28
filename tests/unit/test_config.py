"""配置数据模型与异常单元测试。"""

from __future__ import annotations

from src.core.entities.config import AppConfig
from src.core.exceptions import (
    ConfigError,
    EnergyPlusLauncherError,
    IDDFormatError,
    IDFParseError,
    ResultParseError,
    RunError,
)


def test_app_config_defaults() -> None:
    cfg = AppConfig()
    assert cfg.energyplus_path == ""
    assert cfg.theme == "system"
    assert cfg.recent_files == []
    assert cfg.run_options == "-r"
    assert cfg.analysis_outputs


def test_add_recent_file_dedup_and_limit() -> None:
    cfg = AppConfig()
    for i in range(15):
        cfg.add_recent_file(f"/path/{i}.idf")
    assert len(cfg.recent_files) == 10
    assert cfg.recent_files[0] == "/path/14.idf"
    cfg.add_recent_file("/path/0.idf")
    assert cfg.recent_files[0] == "/path/0.idf"
    assert "/path/0.idf" not in cfg.recent_files[1:]


def test_app_config_roundtrip() -> None:
    cfg = AppConfig(
        energyplus_path="/ep",
        weather_dir="/wd",
        last_idf_dir="/idf",
        last_weather_file="/wf.epw",
        theme="dark",
        recent_files=["/a.idf", "/b.idf"],
        run_options="-r -p",
    )
    data = cfg.to_dict()
    cfg2 = AppConfig.from_dict(data)
    assert cfg2.energyplus_path == "/ep"
    assert cfg2.theme == "dark"
    assert cfg2.recent_files == ["/a.idf", "/b.idf"]
    assert cfg2.run_options == "-r -p"


def test_app_config_from_dict_missing_fields() -> None:
    cfg = AppConfig.from_dict({})
    assert cfg.energyplus_path == ""
    assert cfg.theme == "system"
    assert cfg.analysis_outputs


def test_analysis_outputs_can_be_disabled() -> None:
    cfg = AppConfig(analysis_outputs=False)
    assert not AppConfig.from_dict(cfg.to_dict()).analysis_outputs


def test_exceptions_hierarchy() -> None:
    assert issubclass(IDFParseError, EnergyPlusLauncherError)
    assert issubclass(IDDFormatError, EnergyPlusLauncherError)
    assert issubclass(ConfigError, EnergyPlusLauncherError)
    assert issubclass(RunError, EnergyPlusLauncherError)
    assert issubclass(ResultParseError, EnergyPlusLauncherError)


def test_idf_parse_error_message() -> None:
    e = IDFParseError(10, "bad token", "context here")
    assert e.line == 10
    assert e.context == "context here"
    assert "行 10" in str(e)


def test_idd_format_error_message() -> None:
    e = IDDFormatError(5, "missing field")
    assert e.line == 5
    assert "IDD 行 5" in str(e)
