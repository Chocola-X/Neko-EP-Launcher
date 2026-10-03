"""``RunOptions`` 单元测试。"""

from __future__ import annotations

from src.core.entities.run_options import OutputSuffix, RunOptions


class TestRunOptions:
    """RunOptions 测试。"""

    def test_defaults(self) -> None:
        opts = RunOptions()
        assert opts.annual is False
        assert opts.design_day is False
        assert opts.readvars is False
        assert opts.weather_path == ""
        assert opts.extra_args == []

    def test_to_args_basic(self) -> None:
        opts = RunOptions(weather_path="weather.epw", readvars=True)
        args = opts.to_args("test.idf")
        assert "--readvars" in args
        assert "--weather" in args
        assert "weather.epw" in args
        assert args[-1] == "test.idf"

    def test_to_args_all(self) -> None:
        opts = RunOptions(
            annual=True,
            design_day=True,
            epmacro=True,
            readvars=True,
            expandobjects=True,
            output_prefix="myprefix",
            output_suffix=OutputSuffix.CAMELCASE,
            weather_path="w.epw",
        )
        args = opts.to_args("test.idf")
        assert "--annual" in args
        assert "--design-day" in args
        assert "--epmacro" in args
        assert "--readvars" in args
        assert "--expandobjects" in args
        assert "--output-prefix" in args
        assert "myprefix" in args
        assert "--output-suffix" in args
        assert "C" in args
        assert "--weather" in args
        assert "w.epw" in args

    def test_to_command_str(self) -> None:
        opts = RunOptions(readvars=True)
        cmd = opts.to_command_str("energyplus", "test.idf")
        assert cmd.startswith("energyplus ")
        assert "--readvars" in cmd
        assert "test.idf" in cmd

    def test_from_extra_args_empty(self) -> None:
        opts = RunOptions.from_extra_args("")
        assert opts.annual is False
        assert opts.readvars is False

    def test_from_extra_args_parse(self) -> None:
        opts = RunOptions.from_extra_args("-r -a -p myprefix")
        assert opts.readvars is True
        assert opts.annual is True
        assert opts.output_prefix == "myprefix"

    def test_from_extra_args_unknown(self) -> None:
        opts = RunOptions.from_extra_args("--unknown-flag value")
        assert "--unknown-flag" in opts.extra_args
        assert "value" in opts.extra_args

    def test_from_extra_args_suffix(self) -> None:
        opts = RunOptions.from_extra_args("-s C")
        assert opts.output_suffix == OutputSuffix.CAMELCASE

    def test_from_extra_args_invalid_suffix(self) -> None:
        opts = RunOptions.from_extra_args("-s X")
        assert opts.output_suffix is None

    def test_roundtrip(self) -> None:
        opts = RunOptions(annual=True, readvars=True, weather_path="w.epw")
        args = opts.to_args("test.idf")
        assert "test.idf" in args
        assert "--annual" in args
        assert "--readvars" in args

    def test_output_suffix_enum(self) -> None:
        assert OutputSuffix.LOWERCASE.value == "L"
        assert OutputSuffix.CAMELCASE.value == "C"
        assert OutputSuffix.DASH.value == "D"
