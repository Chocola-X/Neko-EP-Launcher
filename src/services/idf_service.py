"""IDF 业务编排服务。

封装解析、序列化、保存等操作，供 UI 调用。实例由 ``app.py`` 构造注入。
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import replace
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
        for object_index, obj in enumerate(doc.objects):
            issue_start = len(issues)
            obj_def = idd.get(obj.type_name) if idd else None
            name = obj.name()
            for i in range(max(len(obj.fields), len(obj_def.fields) if obj_def else 0)):
                val = obj.get_field(i)
                fdef = obj_def.get_field(i) if obj_def else None
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
            issues[issue_start:] = [
                replace(issue, object_index=object_index) for issue in issues[issue_start:]
            ]
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
            if not math.isfinite(num) or (fdef.type == "integer" and not num.is_integer()):
                issues.append(
                    ValidationIssue(
                        "error",
                        f"字段 '{fname}' 需要有限的{fdef.type}数值",
                        obj.type_name,
                        name,
                        i,
                        fname,
                    )
                )
                return
            if (fdef.minimum_greater is not None and num <= fdef.minimum_greater) or (
                fdef.maximum_less is not None and num >= fdef.maximum_less
            ):
                issues.append(
                    ValidationIssue(
                        "error", f"字段 '{fname}' 超出允许的开区间", obj.type_name, name, i, fname
                    )
                )
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
            if unquoted.casefold() not in {choice.casefold() for choice in fdef.key_choices}:
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
                if unquoted.casefold() in {v.casefold() for v in ref_index.get(lst, set())}:
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
                fdef = obj_def.get_field(i)
                if fdef is None:
                    continue
                unquoted = val.strip("\"'")
                for ref in fdef.references:
                    index.setdefault(ref, set()).add(unquoted)
        return index

    def configure_outputs(self, doc: IDFDocument) -> None:
        """启用 SQLite/汇总及 IDF 变量字典，保留已有汇总请求。依据 R-2。"""
        for name, fields in [
            ("Output:SQLite", ["SimpleAndTabular"]),
            ("Output:VariableDictionary", ["IDF", "Name"]),
            ("Output:Table:SummaryReports", ["AllSummary"]),
        ]:
            objects = doc.get_objects_by_type(name)
            if not objects:
                doc.objects.append(IDFObject(name, fields))
            elif name in ("Output:SQLite", "Output:VariableDictionary"):
                objects[0].set_field(0, fields[0])

    def add_output(
        self, doc: IDFDocument, name: str, is_meter: bool, frequency: str = "Hourly"
    ) -> bool:
        """添加输出请求并避免重复，返回是否新增。依据 R-2/R-4e。"""
        type_name = "Output:Meter" if is_meter else "Output:Variable"
        fields = [name, frequency] if is_meter else ["*", name, frequency]
        if any(
            [v.casefold() for v in obj.fields[: len(fields)]] == [v.casefold() for v in fields]
            for obj in doc.get_objects_by_type(type_name)
        ):
            return False
        doc.objects.append(IDFObject(type_name, fields))
        return True

    def update_field(
        self, doc: IDFDocument, object_index: int, field_index: int, value: str
    ) -> None:
        """更新指定字段，复杂文本自动加引号，避免破坏 IDF 分隔符。"""
        if field_index < 0:
            raise ValueError("字段索引不可为负")
        if any(c in value for c in ",;!\n") and not (value.startswith('"') and value.endswith('"')):
            if '"' in value:
                raise ValueError("含分隔符的字段请使用完整的引号字符串")
            value = f'"{value}"'
        doc.objects[object_index].set_field(field_index, value)

    def resize_fields(self, doc: IDFDocument, object_index: int, append: bool) -> None:
        """增减末尾字段，避免中间字段移位改变含义。"""
        obj = doc.objects[object_index]
        if append:
            obj.set_field(len(obj.fields), "")
        elif obj.fields:
            obj.fields.pop()
            obj.field_names = obj.field_names[: len(obj.fields)]
            obj.comments = obj.comments[: len(obj.fields)]

    def parse_objects(self, text: str) -> list[IDFObject]:
        """解析 IDF 或本应用的 JSON 对象剪贴板，损坏内容抛出解析或值错误。"""
        if not text.strip():
            return []
        if text.lstrip().startswith("{"):
            data = json.loads(text)
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("type"), str)
                or not isinstance(data.get("fields"), list)
                or not all(isinstance(value, str) for value in data["fields"])
            ):
                raise ValueError("对象 JSON 格式错误")
            # 重新解析序列化文本，确保 JSON 值不会注入额外对象。
            obj = IDFObject(data["type"], data["fields"])
            parsed = self.parse(self.serialize_object(obj)).objects
            if len(parsed) != 1 or parsed[0].fields != obj.fields:
                raise ValueError("JSON 含非法的 IDF 字段值")
            return parsed
        return self.parse(text).objects

    def add_object(self, doc: IDFDocument, obj: IDFObject) -> None:
        """向文档追加一个对象，重置源码区间以作为新增对象序列化。"""
        new_obj = IDFObject(
            type_name=obj.type_name,
            fields=list(obj.fields),
            field_names=list(obj.field_names),
            comments=list(obj.comments),
            source_start=-1,
            source_end=-1,
            field_spans=[],
        )
        doc.objects.append(new_obj)

    def remove_object(self, doc: IDFDocument, object_index: int) -> bool:
        """从文档中删除指定索引的对象。"""
        if 0 <= object_index < len(doc.objects):
            doc.objects.pop(object_index)
            return True
        return False

    def duplicate_object(self, doc: IDFDocument, object_index: int) -> IDFObject | None:
        """复制指定索引的对象并追加到文档。"""
        if 0 <= object_index < len(doc.objects):
            source = doc.objects[object_index]
            copy_name = f"{source.name()}_Copy" if source.name() else ""
            new_fields = list(source.fields)
            if new_fields and copy_name:
                new_fields[0] = copy_name
            new_obj = IDFObject(
                type_name=source.type_name,
                fields=new_fields,
                field_names=list(source.field_names),
                comments=list(source.comments),
            )
            doc.objects.append(new_obj)
            return new_obj
        return None

    def collect_objects(
        self, doc: IDFDocument, indices: tuple[int, ...], idd: IDDDocument | None = None
    ) -> list[IDFObject]:
        """按源文件顺序收集所选对象；提供 IDD 时递归包含引用依赖（R-2/R-10）。

        Args:
            doc: 来源文档。
            indices: 所选对象索引。
            idd: 字段引用元数据；None 表示仅复制选择。

        Raises:
            ValueError: 引用缺失或同一引用存在歧义。
        """
        selected = set(indices)
        if any(i < 0 or i >= len(doc.objects) for i in selected):
            raise ValueError("对象选择已失效，请重新选择")
        if idd is not None:
            providers: dict[tuple[str, str], set[int]] = {}
            for index, obj in enumerate(doc.objects):
                definition = idd.get(obj.type_name)
                if definition is None:
                    continue
                for field_index, value in enumerate(obj.fields):
                    field = definition.get_field(field_index)
                    if field and value.strip():
                        for reference in field.references:
                            key = (reference, value.strip().strip("\"'").casefold())
                            providers.setdefault(key, set()).add(index)
            pending = list(selected)
            while pending:
                obj = doc.objects[pending.pop()]
                definition = idd.get(obj.type_name)
                if definition is None:
                    raise ValueError(f"IDD 中没有 {obj.type_name}，无法确定引用依赖")
                for index, value in enumerate(obj.fields):
                    field = definition.get_field(index)
                    if not field or not field.object_lists or not value.strip():
                        continue
                    matches: set[int] = set()
                    for reference in field.object_lists:
                        matches.update(
                            providers.get((reference, value.strip().strip("\"'").casefold()), set())
                        )
                    if len(matches) != 1:
                        raise ValueError(
                            f"{obj.type_name} / {obj.name()} 的引用 {value} 缺失或不唯一"
                        )
                    for match in matches - selected:
                        selected.add(match)
                        pending.append(match)
        return [obj for index, obj in enumerate(doc.objects) if index in selected]

    def paste_objects(
        self, doc: IDFDocument, objects: list[IDFObject], idd: IDDDocument | None = None
    ) -> int:
        """原子追加对象；跳过相同定义，拒绝同名或唯一对象冲突，返回新增数。"""
        additions: list[IDFObject] = []
        for obj in objects:
            definition = idd.get(obj.type_name) if idd else None
            name_field = definition.get_field(0) if definition else None
            has_name = name_field is None or name_field.name.casefold() == "name"
            for existing in [*doc.objects, *additions]:
                same_type = existing.type_name.casefold() == obj.type_name.casefold()
                if same_type and existing.fields == obj.fields:
                    break
                existing_def = idd.get(existing.type_name) if idd else None
                existing_name = existing_def.get_field(0) if existing_def else None
                shared_reference = bool(
                    name_field
                    and existing_name
                    and set(name_field.references) & set(existing_name.references)
                )
                name_conflict = (
                    has_name
                    and (same_type or shared_reference)
                    and bool(obj.name())
                    and existing.name().strip("\"'").casefold()
                    == obj.name().strip("\"'").casefold()
                )
                if (same_type and definition and definition.unique_object) or name_conflict:
                    raise ValueError(
                        f"{obj.type_name} / {obj.name()} 与已有定义冲突，请先重命名或调整目标对象"
                    )
            else:
                additions.append(obj)
        for obj in additions:
            self.add_object(doc, obj)
        return len(additions)

    def update_fields(
        self, doc: IDFDocument, object_index: int, values: tuple[tuple[int, str], ...]
    ) -> None:
        """原子修改选定字段，保留未选择字段；非法值不产生部分修改。"""
        obj = doc.objects[object_index]
        draft = IDFDocument(objects=[IDFObject(obj.type_name, list(obj.fields))])
        for index, value in values:
            self.update_field(draft, 0, index, value)
        for index, _ in values:
            obj.set_field(index, draft.objects[0].get_field(index))

    def encode_fields(self, obj: IDFObject, indices: tuple[int, ...]) -> str:
        """编码带原字段位置的参数，支持引号、换行与空值。"""
        return json.dumps(
            {"type": obj.type_name, "fields": [[index, obj.get_field(index)] for index in indices]},
            ensure_ascii=False,
        )

    def decode_fields(self, text: str, type_name: str) -> tuple[tuple[int, str], ...]:
        """校验结构化字段剪贴板；拒绝类型不匹配或损坏数据。"""
        data = json.loads(text)
        if not isinstance(data, dict) or data.get("type", "").casefold() != type_name.casefold():
            raise ValueError("所选属性只能粘贴到同类型对象")
        fields = data.get("fields")
        if not isinstance(fields, list) or not fields:
            raise ValueError("剪贴板没有属性")
        result: list[tuple[int, str]] = []
        for pair in fields:
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or type(pair[0]) is not int
                or pair[0] < 0
                or not isinstance(pair[1], str)
            ):
                raise ValueError("属性剪贴板格式错误")
            result.append((pair[0], pair[1]))
        return tuple(result)
