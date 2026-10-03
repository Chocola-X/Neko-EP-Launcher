"""领域异常定义。

core 层抛出领域异常，services 层捕获 I/O/进程异常并转换，ui 层在信号槽内
捕获所有异常并转为用户可见消息。禁止裸 ``except``。
"""


class EnergyPlusLauncherError(Exception):
    """所有领域异常的基类。"""


class IDFParseError(EnergyPlusLauncherError):
    """IDF 解析错误。

    Args:
        line: 出错行号（1-based）。
        message: 错误描述。
        context: 出错上下文文本片段。
    """

    def __init__(self, line: int, message: str, context: str = "") -> None:
        self.line = line
        self.context = context
        super().__init__(f"[行 {line}] {message}" + (f": {context}" if context else ""))


class IDDFormatError(EnergyPlusLauncherError):
    """IDD 文件格式错误。

    Args:
        line: 出错行号（1-based）。
        message: 错误描述。
    """

    def __init__(self, line: int, message: str) -> None:
        self.line = line
        super().__init__(f"[IDD 行 {line}] {message}")


class ConfigError(EnergyPlusLauncherError):
    """配置读写错误。"""


class RunError(EnergyPlusLauncherError):
    """运行编排错误。"""


class ResultParseError(EnergyPlusLauncherError):
    """结果文件解析错误。"""
