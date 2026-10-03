"""IDF 业务编排服务。

封装解析、序列化、保存等操作，供 UI 调用。实例由 ``app.py`` 构造注入。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.core.exceptions import IDFParseError
from src.core.idd.models import FieldDef, IDDDocument
from src.core.idf.models import IDFDocument, IDFObject, ValidationIssue
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

    def validate(self, doc: IDFDocument, idd: IDDDocument | None) -> list[ValidationIssue]:
        """校验 IDF 文档，返回问题列表。

        检查：必填缺失、类型不匹配、引用对象不存在。依据 R-2。

        Args:
            doc: IDF 文档。
            idd: IDD 文档（None 时仅做基础检查）。
        """
        issues: list[ValidationIssue] = []
        ref_index = self._build_reference_index(doc, idd)
        for obj in doc.objects:
            obj_def = idd.get(obj.type_name) if idd else None
            name = obj.name()
            for i, val in enumerate(obj.fields):
                fdef = obj_def.fields[i] if obj_def and i < len(obj_def.fields) else None
                fname = fdef.name if fdef else ""
                stripped = val.strip()
                if fdef and fdef.required and not stripped:
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            message=f"必填字段 '{fname}' 为空",
                            object_type=obj.type_name,
                            object_name=name,
                            field_index=i,
                            field_name=fname,
                        )
                    )
                if fdef and stripped:
                    self._check_type(issues, obj, name, i, fname, stripped, fdef)
                    self._check_reference(issues, obj, name, i, fname, stripped, fdef, ref_index)
        return issues

    def _check_type(
        self,
        issues: list[ValidationIssue],
        obj: IDFObject,
        name: str,
        i: int,
        fname: str,
        val: str,
        fdef: FieldDef,
    ) -> None:
        if fdef.type in ("real", "integer"):
            low = val.lower()
            if fdef.autosizable and low == "autosize":
                return
            if fdef.autocalculatable and low == "autocalculate":
                return
            try:
                num = float(val)
            except ValueError:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"字段 '{fname}' 期望数值，实际为 '{val}'",
                        object_type=obj.type_name,
                        object_name=name,
                        field_index=i,
                        field_name=fname,
                    )
                )
                return
            if fdef.minimum is not None and num < fdef.minimum:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"字段 '{fname}'={num} 小于最小值 {fdef.minimum}",
                        object_type=obj.type_name,
                        object_name=name,
                        field_index=i,
                        field_name=fname,
                    )
                )
            if fdef.maximum is not None and num > fdef.maximum:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"字段 '{fname}'={num} 大于最大值 {fdef.maximum}",
                        object_type=obj.type_name,
                        object_name=name,
                        field_index=i,
                        field_name=fname,
                    )
                )
        elif fdef.type == "choice" and fdef.key_choices:
            unquoted = val.strip("\"'")
            if unquoted not in fdef.key_choices:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"字段 '{fname}' 值 '{unquoted}' 不在选项中",
                        object_type=obj.type_name,
                        object_name=name,
                        field_index=i,
                        field_name=fname,
                    )
                )

    def _check_reference(
        self,
        issues: list[ValidationIssue],
        obj: IDFObject,
        name: str,
        i: int,
        fname: str,
        val: str,
        fdef: FieldDef,
        ref_index: dict[str, set[str]],
    ) -> None:
        if fdef.object_lists:
            unquoted = val.strip("\"'")
            if not unquoted:
                return
            found = False
            for lst in fdef.object_lists:
                if unquoted in ref_index.get(lst, set()):
                    found = True
                    break
            if not found:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"字段 '{fname}' 引用 '{unquoted}' 未找到对应对象",
                        object_type=obj.type_name,
                        object_name=name,
                        field_index=i,
                        field_name=fname,
                    )
                )

    @staticmethod
    def _build_reference_index(doc: IDFDocument, idd: IDDDocument | None) -> dict[str, set[str]]:
        """构建引用索引：object-list 名 → 提供该引用的对象名称集合。"""
        index: dict[str, set[str]] = {}
        if idd is None:
            return index
        for obj in doc.objects:
            obj_def = idd.get(obj.type_name)
            if obj_def is None:
                continue
            for i, val in enumerate(obj.fields):
                if not val.strip():
                    continue
                fdef = obj_def.fields[i] if i < len(obj_def.fields) else None
                if fdef is None:
                    continue
                unquoted = val.strip("\"'")
                for ref in fdef.references:
                    index.setdefault(ref, set()).add(unquoted)
        return index
