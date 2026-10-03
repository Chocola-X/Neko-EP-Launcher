"""IDD 业务服务。

解析 ``Energy+.idd`` 并按版本号缓存到 ``resources/idd_cache.json``，启动优先
加载缓存。实例由 ``app.py`` 构造注入。依据 R-10。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.idd.models import FieldDef, IDDDocument, ObjectDef
from src.core.idd.parser import IDDParser

logger = logging.getLogger(__name__)


class IDDService:
    """IDD 业务服务。"""

    def __init__(self, cache_path: str | Path | None = None) -> None:
        """初始化 IDD 服务。

        Args:
            cache_path: 缓存文件路径，None 表示不缓存。
        """
        self._parser = IDDParser()
        self._cache_path = Path(cache_path) if cache_path else None
        self._doc: IDDDocument | None = None

    @property
    def document(self) -> IDDDocument | None:
        """返回当前 IDD 文档。"""
        return self._doc

    def is_loaded(self) -> bool:
        """是否已加载。"""
        return self._doc is not None

    def load(self, idd_path: str | Path) -> IDDDocument:
        """加载 IDD，优先用缓存。

        Raises:
            IDDFormatError: 解析失败。
        """
        idd_path = Path(idd_path)
        cache_key = idd_path.name
        if self._cache_path and self._try_load_cache(cache_key):
            logger.info("从缓存加载 IDD: %s", self._cache_path)
            return self._doc  # type: ignore[return-value]

        logger.info("解析 IDD 文件: %s", idd_path)
        self._doc = self._parser.parse_file(idd_path)
        if self._cache_path:
            self._save_cache(cache_key)
        return self._doc

    def get_object_def(self, type_name: str) -> ObjectDef | None:
        """查询对象定义。"""
        if self._doc is None:
            return None
        return self._doc.get(type_name)

    def get_reference_names(self, object_list_name: str) -> list[str]:
        """查询某 object-list 引用的所有对象名称（用于可搜索下拉）。

        Args:
            object_list_name: \\object-list 名称。

        Returns:
            提供该 reference 的对象实例名称列表（需结合 IDF 文档）。
        """
        if self._doc is None:
            return []
        names: list[str] = []
        for obj_def in self._doc.objects:
            for f in obj_def.fields:
                if object_list_name in f.references:
                    names.append(obj_def.name)
                    break
        return names

    def _try_load_cache(self, cache_key: str) -> bool:
        """尝试从缓存加载。"""
        if not self._cache_path or not self._cache_path.exists():
            return False
        try:
            data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False
        entry = data.get(cache_key)
        if not isinstance(entry, dict):
            return False
        try:
            self._doc = self._dict_to_doc(entry)
            return True
        except Exception as e:
            logger.warning("缓存解析失败: %s", e)
            return False

    def _save_cache(self, cache_key: str) -> None:
        """保存到缓存。"""
        if not self._cache_path or self._doc is None:
            return
        data: dict[str, object] = {}
        if self._cache_path.exists():
            try:
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                data = {}
        data[cache_key] = self._doc_to_dict(self._doc)
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as e:
            logger.warning("缓存写入失败: %s", e)

    @staticmethod
    def _doc_to_dict(doc: IDDDocument) -> dict[str, object]:
        return {
            "version": doc.version,
            "objects": [
                {
                    "name": o.name,
                    "group": o.group,
                    "memo": o.memo,
                    "min_fields": o.min_fields,
                    "unique_object": o.unique_object,
                    "extensible_size": o.extensible_size,
                    "fields": [
                        {
                            "name": f.name,
                            "type": f.type,
                            "units": f.units,
                            "default": f.default,
                            "required": f.required,
                            "key_choices": f.key_choices,
                            "object_lists": f.object_lists,
                            "references": f.references,
                            "minimum": f.minimum,
                            "minimum_greater": f.minimum_greater,
                            "maximum": f.maximum,
                            "maximum_less": f.maximum_less,
                            "note": f.note,
                            "begin_extensible": f.begin_extensible,
                        }
                        for f in o.fields
                    ],
                }
                for o in doc.objects
            ],
        }

    @staticmethod
    def _dict_to_doc(data: dict[str, object]) -> IDDDocument:
        doc = IDDDocument(version=str(data.get("version", "")))
        objects = data.get("objects", [])
        if not isinstance(objects, list):
            return doc
        for od in objects:
            if not isinstance(od, dict):
                continue
            obj = ObjectDef(
                name=str(od["name"]),
                group=str(od.get("group", "")),
                memo=str(od.get("memo", "")),
                min_fields=int(od.get("min_fields", 0)),
                unique_object=bool(od.get("unique_object", False)),
                extensible_size=int(od.get("extensible_size", 0)),
            )
            fields = od.get("fields", [])
            if isinstance(fields, list):
                for fd in fields:
                    if not isinstance(fd, dict):
                        continue
                    obj.fields.append(
                        FieldDef(
                            name=str(fd.get("name", "")),
                            type=str(fd.get("type", "alpha")),
                            units=str(fd.get("units", "")),
                            default=str(fd.get("default", "")),
                            required=bool(fd.get("required", False)),
                            key_choices=list(fd.get("key_choices", [])),
                            object_lists=list(fd.get("object_lists", [])),
                            references=list(fd.get("references", [])),
                            minimum=fd.get("minimum"),
                            minimum_greater=fd.get("minimum_greater"),
                            maximum=fd.get("maximum"),
                            maximum_less=fd.get("maximum_less"),
                            note=str(fd.get("note", "")),
                            begin_extensible=bool(fd.get("begin_extensible", False)),
                        )
                    )
            doc.add(obj)
        return doc
