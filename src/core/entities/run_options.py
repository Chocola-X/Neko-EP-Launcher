"""EnergyPlus 命令行参数建模。

依据 ``energyplus --help``（9.4.0）与 R-3 Auxiliary Programs。
全部参数建模为枚举/数据类，禁止拼接字符串。
"""

from __future__ import annotations

import contextlib
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
        """从附加参数字符串解析（简单空格分隔）。

        Args:
            extra: 附加参数字符串（如 ``"-r -p myprefix"``）。

        Returns:
            RunOptions 实例。
        """
        opts = cls()
        if not extra:
            return opts
        parts = extra.split()
        i = 0
        while i < len(parts):
            p = parts[i]
            if p in ("-a", "--annual"):
                opts.annual = True
            elif p in ("-D", "--design-day"):
                opts.design_day = True
            elif p in ("-m", "--epmacro"):
                opts.epmacro = True
            elif p in ("-r", "--readvars"):
                opts.readvars = True
            elif p in ("-x", "--expandobjects"):
                opts.expandobjects = True
            elif p in ("-c", "--convert"):
                opts.convert = True
            elif p == "--convert-only":
                opts.convert_only = True
            elif p in ("-p", "--output-prefix") and i + 1 < len(parts):
                opts.output_prefix = parts[i + 1]
                i += 1
            elif p in ("-d", "--output-directory") and i + 1 < len(parts):
                opts.output_directory = parts[i + 1]
                i += 1
            elif p in ("-i", "--idd") and i + 1 < len(parts):
                opts.idd_path = parts[i + 1]
                i += 1
            elif p in ("-w", "--weather") and i + 1 < len(parts):
                opts.weather_path = parts[i + 1]
                i += 1
            elif p in ("-s", "--output-suffix") and i + 1 < len(parts):
                with contextlib.suppress(ValueError):
                    opts.output_suffix = OutputSuffix(parts[i + 1])
                i += 1
            else:
                opts.extra_args.append(p)
            i += 1
        return opts
