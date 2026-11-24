"""校验实际运行配置并冻结 EnergyPlus 输入。依据 R-2、R-3、R-9、R-10。"""

from __future__ import annotations

import hashlib
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

from src.core.entities.run_options import RunOptions
from src.core.idf.models import IDFDocument
from src.services.idf_service import IDFService

logger = logging.getLogger(__name__)

# R-2/R-10。值为 IDF 字段位置、是否必填及省略时采用的引擎默认值。
FILE_FIELDS: dict[str, tuple[int, bool, str]] = {
    "schedule:file": (2, True, ""),
    "schedule:file:shading": (0, True, ""),
    "construction:windowdatafile": (1, False, "Window5DataFile.dat"),
    "table:independentvariable": (7, False, ""),
    "table:lookup": (7, False, ""),
}


@dataclass(slots=True, frozen=True)
class RunInput:
    """输入快照的来源及其在工作目录中的相对位置。"""

    kind: str
    source: Path
    destination: Path


@dataclass(slots=True)
class RunPreparation:
    """已经检查的运行参数、模型副本与待复制文件。"""

    executable: Path
    document: IDFDocument
    options: RunOptions
    model: RunInput
    files: tuple[RunInput, ...]


def validate_archive_name(name: str, label: str) -> None:
    """拒绝路径、特殊目录名及不可见控制字符。"""
    if (
        not name.strip()
        or name in {".", ".."}
        or name.startswith("-")
        or any(ch in "/\\:" or ord(ch) < 32 or ord(ch) == 127 for ch in name)
    ):
        raise ValueError(f"{label}必须是普通名称，不能包含路径或控制字符：{name!r}")


def _existing_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label}不存在或不是文件：{path}")
    return path.resolve()


def plan_run(
    ep_executable: str,
    idf_path: str,
    weather_path: str,
    options: RunOptions,
    *,
    analysis_outputs: bool,
) -> RunPreparation:
    """在创建归档前校验生效参数、读取模型并解析依赖。"""
    if options.extra_args:
        raise ValueError(f"不支持的运行参数：{' '.join(options.extra_args)}")
    if options.output_directory:
        raise ValueError("输出目录由启动器管理，不能使用 -d / --output-directory")
    if options.epmacro:
        raise ValueError("当前归档流程不支持 EPMacro，请先展开为普通 IDF")
    if options.annual and options.design_day:
        raise ValueError("全年模拟和仅设计日模拟不能同时启用")
    if options.output_prefix:
        validate_archive_name(options.output_prefix, "输出文件前缀")
    executable = _existing_file(Path(ep_executable), "EnergyPlus 可执行文件")
    # 相对依赖以用户打开的模型所在目录为准，包括模型本身是符号链接的场景。
    source = Path(idf_path).absolute()
    _existing_file(source, "IDF 文件")
    if source.suffix.casefold() != ".idf":
        raise ValueError("运行归档目前支持普通 IDF 文件")
    if options.readvars:
        for suffix in (".rvi", ".mvi"):
            control_file = source.with_suffix(suffix)
            if control_file.exists() or control_file.is_symlink():
                raise ValueError(f"暂不支持归档 ReadVarsESO 自定义控制文件：{control_file}")
    idf_service = IDFService()
    document = idf_service.open(source)
    if re.search(r"^\s*##", document.raw_text, re.MULTILINE):
        raise ValueError("模型包含 EPMacro 指令，请先展开为普通 IDF")
    model = RunInput("idf", source, Path(source.name))

    weather = options.weather_path or weather_path
    implicit_weather = source.parent / "in.epw"
    weather_file = None
    if weather:
        weather_file = _existing_file(Path(weather), "天气文件")
    elif implicit_weather.is_file():
        weather_file = implicit_weather.resolve()
    default_idd = executable.parent / "Energy+.idd"
    idd_file = _existing_file(
        Path(options.idd_path) if options.idd_path else default_idd, "IDD 文件"
    )
    files = [RunInput("idd", idd_file, Path("engine/Energy+.idd"))]
    if weather_file is not None:
        files.append(RunInput("weather", weather_file, Path("engine/in.epw")))
    dependencies: dict[Path, Path] = {}
    for obj in document.objects:
        name = obj.type_name.casefold()
        if name.startswith(("externalinterface", "pythonplugin:", "parametric:")):
            raise ValueError(f"暂不支持归档 {obj.type_name} 的外部运行依赖")
        if name not in FILE_FIELDS:
            continue
        index, required, default = FILE_FIELDS[name]
        raw_path = obj.get_field(index).strip().strip("\"'") or default
        if not raw_path:
            if required:
                raise ValueError(f"{obj.type_name} 第 {obj.line_start} 行缺少依赖文件路径")
            continue
        resource = _existing_file(
            source.parent / raw_path, f"{obj.type_name} 第 {obj.line_start} 行的依赖文件"
        )
        if resource not in dependencies:
            suffix = Path(raw_path).suffix
            if not re.fullmatch(r"\.[A-Za-z0-9]+", suffix):
                suffix = ""
            destination = Path("dependencies") / f"{len(dependencies) + 1}{suffix}"
            dependencies[resource] = destination
            files.append(RunInput("dependency", resource, destination))
        obj.set_field(index, dependencies[resource].as_posix())

    if analysis_outputs:
        idf_service.configure_outputs(document)
    resolved_options = replace(
        options,
        weather_path="engine/in.epw" if weather_file else "",
        idd_path="engine/Energy+.idd",
        output_directory="..",
    )
    return RunPreparation(executable, document, resolved_options, model, tuple(files))


def freeze_inputs(
    preparation: RunPreparation, work_dir: Path
) -> list[dict[str, str]]:
    """在独立工作目录写入最终模型与资源快照，并在启动前计算哈希。"""
    work_dir.mkdir()
    model = preparation.model
    IDFService().save(preparation.document, work_dir / model.destination)
    for file in preparation.files:
        dest = work_dir / file.destination
        dest.parent.mkdir(exist_ok=True)
        shutil.copy2(file.source, dest)
    return [
        {
            "kind": file.kind,
            "source": str(file.source),
            "path": (work_dir / file.destination).relative_to(work_dir.parent).as_posix(),
            "sha256": _file_sha256(work_dir / file.destination),
        }
        for file in (model, *preparation.files)
    ]


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def read_engine_version(executable: Path) -> str:
    """读取 EnergyPlus 自报版本。依据 9.4 的命令行帮助。"""
    try:
        process = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
            timeout=3,
        )
        version = next((line.strip() for line in process.stdout.splitlines() if line.strip()), "")
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError(f"无法读取 EnergyPlus 版本：{exc}") from exc
    if not version:
        raise ValueError("EnergyPlus 没有返回版本信息，请检查引擎安装")
    return version
