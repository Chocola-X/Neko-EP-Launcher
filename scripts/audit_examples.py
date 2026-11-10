"""批量审计官方示例；静态校验全部 IDF，可选运行 30 个设计日样本。

运行：python -m scripts.audit_examples --energyplus-home <安装目录> --output-dir <新目录>
追加 --simulate 执行真实模拟。依据 R-3 命令行与 R-4c 错误文件契约。
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import subprocess
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from time import monotonic

from src.core.results.err_parser import ErrParser
from src.services.idd_service import IDDService
from src.services.idf_service import IDFService

logger = logging.getLogger(__name__)

SAMPLES: tuple[str, ...] = (
    "ThermochromicWindow",
    "EMSThermochromicWindow",
    "1ZoneUncontrolled",
    "1ZoneUncontrolledUTF8",
    "1ZoneUncontrolledResLayers",
    "1ZoneUncontrolledFourAlgorithms",
    "1ZoneUncontrolledWithHysteresisPCM",
    "1ZoneEvapCooler",
    "1ZoneDataCenterCRAC_wPumpedDXCoolingCoil",
    "4ZoneWithShading_Simple_1",
    "4ZoneWithShading_Simple_2",
    "SolarShadingTest",
    "PurchAirWithDaylightingAndShadeControl",
    "DaylightingDeviceShelf",
    "DaylightingDeviceTubular",
    "CmplxGlz_InShadeGasMix",
    "AirflowWindowsAndBetweenGlassShades",
    "AirflowNetwork3zVent",
    "5Zone_IdealLoadsAirSystems_ReturnPlenum",
    "5ZoneWaterLoopHeatPump",
    "HeatPumpAirToAirWithRHcontrol",
    "HeatRecoveryPlantLoop",
    "PlantApplicationsGuide_Example1",
    "SolarCollectorFlatPlateWater",
    "EMSCustomOutputVariable",
    "EMSWindowShadeControl",
    "HVACTemplate-5ZoneFanCoil",
    "HVACTemplate-5ZoneUnitaryHeatPump",
    "HVACTemplate-5ZoneVAVWaterCooled",
    "WindowTests",
)


def simulate(
    source: Path, root: Path, output: Path, weather: Path, timeout: int
) -> dict[str, object]:
    """运行一个原始示例的副本，返回退出码、错误及耗时；超时也保留日志。"""
    run_dir = output / source.stem
    run_dir.mkdir()
    copied = run_dir / source.name
    shutil.copy2(source, copied)
    command = [
        str(root / "energyplus"),
        "-D",
        "-x",
        "-i",
        str(root / "Energy+.idd"),
        "-w",
        str(weather),
        "-d",
        str(run_dir),
        str(copied),
    ]
    started = monotonic()
    code: int | None = None
    error = ""
    try:
        with (run_dir / "console.log").open("w", encoding="utf-8") as log:
            code = subprocess.run(
                command,
                cwd=run_dir,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            ).returncode
    except subprocess.TimeoutExpired:
        error = f"超过 {timeout} 秒"
    except OSError as exc:
        error = str(exc)
    err_path = run_dir / "eplusout.err"
    records = ErrParser().parse_file(err_path) if err_path.exists() else []
    end_path = run_dir / "eplusout.end"
    status = ErrParser().parse_end_file(end_path) if end_path.exists() else None
    success = code == 0 and status is not None and status.success
    return {
        "file": source.name,
        "success": success,
        "exit_code": code,
        "seconds": round(monotonic() - started, 2),
        "error": error,
        "warnings": status.warnings if status else -1,
        "severes": status.severes if status else -1,
        "command": command,
        "records": [asdict(record) for record in records],
    }


def main() -> None:
    """校验全部示例、可选运行代表样本，并生成 JSON、CSV 和中文摘要。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--energyplus-home", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--simulate", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    root = args.energyplus_home.resolve()
    output = args.output_dir.resolve()
    # 每次新建目录，防止审计结果被覆盖。
    output.mkdir(parents=True, exist_ok=False)
    service = IDFService()
    idd = IDDService().load(root / "Energy+.idd")
    rows: list[dict[str, object]] = []
    examples = root / "ExampleFiles"
    for source in sorted(examples.rglob("*.idf")):
        try:
            doc = service.open(source)
            issues = service.validate(doc, idd)
            rows.append(
                {
                    "file": str(source.relative_to(examples)),
                    "objects": len(doc.objects),
                    "issues": [asdict(issue) for issue in issues],
                    "parse_error": "",
                }
            )
        except Exception as exc:
            logger.exception("示例校验失败：%s", source.name)
            rows.append(
                {
                    "file": str(source.relative_to(examples)),
                    "objects": 0,
                    "issues": [],
                    "parse_error": str(exc),
                }
            )
    (output / "static.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (output / "static.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["文件", "对象数", "校验问题数", "解析错误"])
        for row in rows:
            writer.writerow([row["file"], row["objects"], len(row["issues"]), row["parse_error"]])
    logger.info("静态校验完成：%d 个文件", len(rows))
    results: list[dict[str, object]] = []
    missing: list[str] = []
    if args.simulate:
        runs = output / "runs"
        runs.mkdir()
        weather = root / "WeatherData" / "USA_CO_Golden-NREL.724666_TMY3.epw"
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {}
            for name in SAMPLES:
                source = examples / f"{name}.idf"
                if source.exists():
                    pending[pool.submit(simulate, source, root, runs, weather, args.timeout)] = (
                        source
                    )
                else:
                    missing.append(name)
            for job in as_completed(pending):
                result = job.result()
                results.append(result)
                logger.info(
                    "模拟 %d/%d：%s，成功=%s",
                    len(results),
                    len(pending),
                    result["file"],
                    result["success"],
                )
                (output / "simulations.json").write_text(
                    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
                )
    with (output / "simulations.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        fields = ["file", "success", "exit_code", "seconds", "warnings", "severes", "error"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    counts = Counter(issue["object_type"] for row in rows for issue in row["issues"])
    summary = (
        f"静态校验文件：{len(rows)}\n"
        f"解析失败：{sum(bool(row['parse_error']) for row in rows)}\n"
        f"无校验问题：{sum(not row['issues'] and not row['parse_error'] for row in rows)}\n"
        f"问题对象类型统计：{dict(counts)}\n"
        f"真实设计日模拟：{len(results)}；成功：{sum(bool(row['success']) for row in results)}\n"
        f"选定样本不存在：{missing}\n"
        "所有模拟均使用 -D -x 和安装包 Golden 天气文件；原始示例不修改。\n"
        "设计日抽样不代表全年模拟通过；静态提示需与引擎日志核对。\n"
    )
    (output / "summary.txt").write_text(summary, encoding="utf-8")
    report = [
        "# EnergyPlus 示例批量测试",
        "",
        "```text",
        summary.rstrip(),
        "```",
        "",
        "## 真实设计日模拟",
        "",
        "| 示例 | 结果 | 引擎警告数 | 严重错误数 | 秒 |",
        "|---|---|---:|---:|---:|",
    ]
    for row in sorted(results, key=lambda row: str(row["file"])):
        report.append(
            f"| {row['file']} | {'通过' if row['success'] else '失败'} | {row['warnings']} | {row['severes']} | {row['seconds']} |"
        )
    report.extend(["", "## 解析失败", ""])
    for row in rows:
        if row["parse_error"]:
            report.append(f"- {row['file']}：{row['parse_error']}")
    report.extend(
        [
            "",
            "详细静态提示见 static.json / static.csv；真实引擎诊断见 simulations.json 和 runs/ 下各文件的 eplusout.err。",
            "静态提示可能涉及条件字段、预处理或外部数据，不能据此认定官方模型错误。",
        ]
    )
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    logger.info("%s\n审计目录：%s", summary, output)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logger.setLevel(logging.INFO)
    main()
