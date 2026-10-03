"""IDF 业务编排服务。

封装解析、序列化、保存等操作，供 UI 调用。实例由 ``app.py`` 构造注入。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.exceptions import IDFParseError
from src.core.idf.models import IDFDocument, IDFObject
from src.core.idf.parser import IDFParser
from src.core.idf.serializer import IDFSerializer

logger = logging.getLogger(__name__)


class IDFService:
    """IDF 业务服务。"""

    def __init__(
        self, parser: IDFParser | None = None, serializer: IDFSerializer | None = None
    ) -> None:
        """初始化 IDF 服务。

        Args:
            parser: IDF 解析器（默认新建）。
            serializer: IDF 序列化器（默认新建）。
        """
        self._parser = parser or IDFParser()
        self._serializer = serializer or IDFSerializer()

    @property
    def parser(self) -> IDFParser:
        """返回解析器。"""
        return self._parser

    @property
    def serializer(self) -> IDFSerializer:
        """返回序列化器。"""
        return self._serializer

    def open(self, path: str | Path) -> IDFDocument:
        """打开并解析 IDF 文件。

        Raises:
            IDFParseError: 解析失败。
        """
        logger.info("打开 IDF: %s", path)
        return self._parser.parse_file(path)

    def parse(self, text: str, source_path: str = "") -> IDFDocument:
        """解析文本。

        Raises:
            IDFParseError: 解析失败。
        """
        return self._parser.parse_text(text, source_path)

    def serialize(self, doc: IDFDocument) -> str:
        """序列化文档为文本。"""
        return self._serializer.serialize(doc)

    def serialize_object(self, obj: IDFObject) -> str:
        """序列化单个对象。"""
        return self._serializer.serialize_object(obj)

    def save(self, doc: IDFDocument, path: str | Path) -> None:
        """序列化并保存到文件。

        Raises:
            IDFParseError: 写入失败。
        """
        text = self._serializer.serialize(doc)
        p = Path(path)
        try:
            p.write_text(text, encoding="utf-8")
        except OSError as e:
            raise IDFParseError(0, f"无法保存文件: {e}") from e
        logger.info("保存 IDF: %s", path)

    def save_text(self, text: str, path: str | Path) -> None:
        """直接保存文本到文件。

        Raises:
            IDFParseError: 写入失败。
        """
        p = Path(path)
        try:
            p.write_text(text, encoding="utf-8")
        except OSError as e:
            raise IDFParseError(0, f"无法保存文件: {e}") from e
