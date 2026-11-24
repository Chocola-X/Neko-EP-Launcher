"""EnergyPlus 命令行参数建模。

依据 ``energyplus --help``（9.4.0）与 R-3 Auxiliary Programs。
全部参数建模为枚举/数据类，禁止拼接字符串。
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from enum import Enum


class OutputSuffix(Enum):
    """输出文件命名风格（``-s`` 参数）。"""

    LOWERCASE = "L"
    CAMELCASE = "C"
    DASH = "D"


@dataclass(slots=True)
class RunOptions:
    """EnergyPlus 运行选项。

    对应命令行参数：
    - ``-a``/``--annual``: annual
    - ``-D``/``--design-day``: design_day
    - ``-d``/``--output-directory``: output_directory
    - ``-i``/``--idd``: idd_path
    - ``-m``/``--epmacro``: epmacro
    - ``-p``/``--output-prefix``: output_prefix
    - ``-r``/``--readvars``: readvars
    - ``-s``/``--output-suffix``: output_suffix
    - ``-w``/``--weather``: weather_path
    - ``-x``/``--expandobjects``: expandobjects
    - ``-c``/``--convert``: convert
    - ``--convert-only``: convert_only

    Attributes:
        annual: 强制全年模拟。
        design_day: 仅设计日模拟。
        output_directory: 输出目录。
        idd_path: IDD 路径。
        epmacro: 先跑 EPMacro。
        output_prefix: 输出文件前缀。
        readvars: 模拟后跑 ReadVarsESO。
        output_suffix: 输出命名风格。
        weather_path: 天气文件路径。
        expandobjects: 先跑 ExpandObjects。
        convert: IDF↔epJSON 互转。
        convert_only: 仅转换不模拟。
        extra_args: 附加参数（校验后的）。
    """

    annual: bool = False
    design_day: bool = False
    output_directory: str = ""
    idd_path: str = ""
    epmacro: bool = False
    output_prefix: str = ""
    readvars: bool = False
    output_suffix: OutputSuffix | None = None
    weather_path: str = ""
    expandobjects: bool = False
    convert: bool = False
    convert_only: bool = False
    extra_args: list[str] = field(default_factory=list)

    def to_args(self, idf_filename: str = "") -> list[str]:
        """转换为命令行参数列表。

        Args:
            idf_filename: IDF 文件名（追加到末尾）。

        Returns:
            参数列表（不含可执行文件路径）。
        """
        args: list[str] = []

        if self.annual:
            args.append("--annual")
        if self.design_day:
            args.append("--design-day")
        if self.output_directory:
            args.extend(["--output-directory", self.output_directory])
        if self.idd_path:
            args.extend(["--idd", self.idd_path])
        if self.epmacro:
            args.append("--epmacro")
        if self.output_prefix:
            args.extend(["--output-prefix", self.output_prefix])
        if self.readvars:
            args.append("--readvars")
        if self.output_suffix is not None:
            args.extend(["--output-suffix", self.output_suffix.value])
        if self.weather_path:
            args.extend(["--weather", self.weather_path])
        if self.expandobjects:
            args.append("--expandobjects")
        if self.convert:
            args.append("--convert")
        if self.convert_only:
            args.append("--convert-only")

        args.extend(self.extra_args)

        if idf_filename:
            args.append(idf_filename)

        return args

    def to_command_str(self, ep_executable: str, idf_filename: str = "") -> str:
        """转换为完整命令行字符串。"""
        args = self.to_args(idf_filename)
        return f"{ep_executable} {' '.join(args)}"

    @classmethod
    def from_extra_args(cls, extra: str) -> RunOptions:
        """从附加参数字符串解析，支持带引号的路径。

        Args:
            extra: 附加参数字符串（如 ``"-r -p myprefix"``）。

        Returns:
            RunOptions 实例。
        """
        opts = cls()
        if not extra:
            return opts
        flags = {
            "-a": "annual", "--annual": "annual",
            "-D": "design_day", "--design-day": "design_day",
            "-m": "epmacro", "--epmacro": "epmacro",
            "-r": "readvars", "--readvars": "readvars",
            "-x": "expandobjects", "--expandobjects": "expandobjects",
            "-c": "convert", "--convert": "convert",
            "--convert-only": "convert_only",
        }
        arguments = {
            "-p": "output_prefix", "--output-prefix": "output_prefix",
            "-d": "output_directory", "--output-directory": "output_directory",
            "-i": "idd_path", "--idd": "idd_path",
            "-w": "weather_path", "--weather": "weather_path",
            "-s": "output_suffix", "--output-suffix": "output_suffix",
        }
        parts = iter(shlex.split(extra))
        for part in parts:
            flag, equals, value = part.partition("=")
            if flag in flags and not equals:
                setattr(opts, flags[flag], True)
            elif flag in arguments:
                if not equals:
                    value = next(parts, "")
                if not value or value.startswith("-"):
                    raise ValueError(f"参数 {flag} 缺少有效值")
                if arguments[flag] == "output_suffix":
                    try:
                        opts.output_suffix = OutputSuffix(value)
                    except ValueError:
                        raise ValueError("输出命名风格必须为 L、C 或 D") from None
                else:
                    setattr(opts, arguments[flag], value)
            else:
                opts.extra_args.append(part)
        return opts
