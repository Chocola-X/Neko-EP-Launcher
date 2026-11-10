"""生成自包含的可视化 HTML；不读取文件、不依赖 GUI。依据 R-4。"""

from __future__ import annotations

import math
from html import escape

from src.core.results.models import ErrorRecord, ReportTable


def line_chart(label: str, points: list[tuple[str, float]]) -> str:
    """生成含悬停数值的 SVG 曲线，限制绘图点数。"""
    values = [(t, v) for t, v in points if math.isfinite(v)]
    if not values:
        return ""
    sampled = values[:: max(1, math.ceil(len(values) / 600))]
    low, high = min(v for _, v in values), max(v for _, v in values)
    scale = high - low or 1
    positions = [
        (45 + i * 700 / max(1, len(sampled) - 1), 210 - (v - low) / scale * 170)
        for i, (_, v) in enumerate(sampled)
    ]
    coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in positions)
    dots = "".join(
        f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3"><title>{escape(t)}: {v:g}</title></circle>'
        for (x, y), (t, v) in zip(positions, sampled, strict=True)
    )
    return f'''<article><h3>{escape(label)}</h3><p>范围 {low:g} – {high:g} · {len(values)} 条记录 · 图中 {len(sampled)} 点</p>
<svg viewBox="0 0 800 260" role="img" aria-label="{escape(label, quote=True)}"><path d="M45 25V215H750" fill="none" stroke="#ccd5e0"/>
<polyline points="{coords}" fill="none" stroke="#178ba8" stroke-width="2"/><g fill="#178ba8">{dots}</g>
<text x="45" y="245">{escape(values[0][0])}</text><text x="750" y="245" text-anchor="end">{escape(values[-1][0])}</text></svg></article>'''


def bar_chart(table: ReportTable) -> str:
    """按固定数值列绘图，避免把不同列的数值混合。"""
    if not table.columns:
        return ""
    column = next(
        (
            i
            for i, name in enumerate(table.columns)
            if name.lower() in ("electricity", "totalenergy")
        ),
        0,
    )
    values: list[tuple[str, float, str]] = []
    for name, row in zip(table.rows, table.cells, strict=False):
        if column >= len(row):
            continue
        try:
            value = float(row[column].split("[")[0].strip())
        except ValueError:
            continue
        if math.isfinite(value):
            values.append((name, value, row[column]))
    if not values:
        return ""
    maximum = max(abs(v) for _, v, _ in values) or 1
    bars = "".join(
        f'<div class="bar-row"><span>{escape(name)}</span><meter min="0" max="{maximum}" value="{abs(value)}"></meter><b>{escape(raw)}</b></div>'
        for name, value, raw in values
    )
    return f"<article><h3>{escape(table.table_name)} · {escape(table.columns[column])}</h3>{bars}</article>"


def build_report(
    title: str,
    status: str,
    errors: list[ErrorRecord],
    tables: list[ReportTable],
    charts: list[str],
    notes: list[str],
) -> str:
    """构建完整 HTML，所有模型文本转义，资源全部内嵌。"""
    diagnostics = "".join(
        f"<li><b>{escape(e.severity)}</b> {escape(e.message)}</li>" for e in errors
    )
    summaries = "".join(
        bar_chart(t)
        for t in tables
        if t.table_name.lower()
        in ("enduses", "siteandsourceenergy", "end uses", "site and source energy")
    )
    reports = []
    for table in tables:
        heading = f"{table.report_name} / {table.table_name} ({table.report_for})"
        header = "<th>项目</th>" + "".join(f"<th>{escape(c)}</th>" for c in table.columns)
        rows = "".join(
            "<tr><th>"
            + escape(name)
            + "</th>"
            + "".join(f"<td>{escape(v)}</td>" for v in row)
            + "</tr>"
            for name, row in zip(table.rows, table.cells, strict=False)
        )
        reports.append(
            f'<details><summary>{escape(heading)}</summary><div class="scroll"><table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table></div></details>'
        )
    messages = "".join(f"<p>{escape(n)}</p>" for n in notes)
    return (
        """<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>EnergyPlus 增强报告</title><style>
:root{font-family:system-ui,sans-serif;color:#233349;background:#edf2f7}body{max-width:1200px;margin:auto;padding:32px}header{background:#143448;color:white;padding:30px;border-radius:16px}h1{margin:0 0 10px}h2{margin-top:32px}article,details,.notice{background:white;border:1px solid #dce5ee;border-radius:12px;padding:20px;margin:16px 0}p{line-height:1.6}summary{cursor:pointer;font-weight:600}svg{width:100%;max-height:320px}svg text{font-size:11px;fill:#53657b}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:16px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;margin-top:16px;font-size:13px}th,td{padding:10px;text-align:left;border-bottom:1px solid #e5ebf1}thead{background:#edf3f8}input{padding:12px;border:1px solid #becddb;border-radius:7px;width:90%}.bar-row{display:grid;grid-template-columns:1fr 1fr 120px;gap:10px;margin:12px 0;font-size:13px}meter{width:100%}footer{color:#62748b;margin-top:30px}@media print{body{padding:0}details{break-inside:avoid}input{display:none}}
</style><header><h1>EnergyPlus · 增强分析报告</h1>"""
        + f'<p>{escape(title)}</p><strong>{escape(status)}</strong></header><div class="notice">{messages}</div>'
        + f'<h2>能耗概览</h2><div class="grid">{summaries or "<p>没有可用的能耗汇总数据。</p>"}</div><h2>时序曲线</h2>{"".join(charts) or "<p>没有可用的时序数据。请请求输出变量并启用 SQLite 后重新模拟。</p>"}<h2>诊断记录（{len(errors)}）</h2><ul>{diagnostics or "<li>未发现诊断记录。</li>"}</ul><h2>汇总表（{len(tables)}）</h2>'
        + """<input id="search" placeholder="筛选报告或表名" aria-label="筛选汇总表">"""
        + "".join(reports)
        + """<footer>Neko-EP-Launcher · 单文件离线报告 · 数据来源：EnergyPlus SQL/XML/ERR 输出（R-4）。图表为抽样预览，完整时序可在启动器导出 CSV。</footer><script>document.getElementById('search').addEventListener('input',function(){const q=this.value.toLowerCase();document.querySelectorAll('details').forEach(e=>e.hidden=!e.querySelector('summary').textContent.toLowerCase().includes(q));});</script></html>"""
    )
