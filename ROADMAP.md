# ROADMAP.md — EnergyPlus Launcher 实施路线图

> 本文件给出从当前初版到最终目标的分阶段实施计划。
> 每个阶段都是**可独立交付、可验收**的增量。阶段内任务顺序可调整，但不得跳过验收门禁。
> 执行前必读 [AGENTS.md](AGENTS.md)。所有 EnergyPlus 行为以「参考资料」为准，禁止凭记忆。

参考资料编号（R-x）对应 AGENTS.md §13。命令行选项来自 `energyplus --help`（9.4.0）：
```
-a --annual  -c --convert  -D --design-day  -d --output-directory  -i --idd
-m --epmacro  -p --output-prefix  -r --readvars  -s --output-suffix
-w --weather  -x --expandobjects  --convert-only
```

---

## 本轮增强：Linux 桌面 EP-Launch 工作流

目标：完善现有桌面框架，优先交付可靠的 IDF 编辑与可交互的结果分析。

- 设计（P1）：解析器记录字符区间，序列化按区间替换以保留全文注释；主窗口自动同步、保留撤销栈；字段面板接入 IDD 下拉与引用，改进字段校验（对象增删复制留待后续）。
- 设计（P2）：输出变量列表可搜索并插入 IDF；一键配置 SQLite/汇总输出；可直接打开已有结果目录，识别自定义输出前缀，缺失 XML 时从 SQL 汇总恢复。
- 设计（P3）：时序按环境周期、日期筛选，变量标签标明频率，使用真实时间轴、单位分轴、表格预览与 CSV 导出；汇总图按指定数值列绘图；耗时读取在工作线程完成。
- 验证：新增损坏输入、单行多对象、注释保真、编辑撤销、实际 SQL/XML、输出配置和图表交互回归测试；运行 lint、类型检查、完整测试及覆盖率检查。
- 依据：R-2/R-4b/R-4d/R-4e/R-10；本轮已查阅本地 9.4 官方 InputOutputReference.pdf、OutputDetailsAndExamples.pdf 与 Energy+.idd（R-9）。

## 现状评估（重构起点）

### 已有
- PySide6 GUI：主窗口、IDF 编辑器（语法高亮+行号）、对象树+字段表格、设置对话框、QProcess 运行器、运行面板（日志+结果文件文本查看）
- IDF 逐字符解析器（处理引号/括号/注释/字段名注释）
- 运行归档到 `data/runs/<run_id>/`，复制 IDF/EPW
- 一个真实运行样本 `data/runs/test_run_001/`（含 err/eso/sql/rdd/mdd/eplustbl 等全套输出）

### 缺失 / 缺陷（按优先级）
| # | 问题 | 影响 | 阶段 |
|---|------|------|------|
| 1 | 无测试（`test/` 被 .gitignore） | 不可回归、不可重构 | P0 |
| 2 | 无 pyproject.toml / lint / 类型检查 | 无质量门禁 | P0 |
| 3 | 模块级单例（`config`、`parser`）、UI 依赖全局单例 | 耦合、不可测 | P0 |
| 4 | 硬编码 `DEFAULT_EP_PATH` 绝对路径 | 不可移植 | P0 |
| 5 | `main_window` 调 `run_panel._start_run()`（跨层私有） | 架构违规 | P0 |
| 6 | 无 IDD 解析，字段编辑无元数据（盲编辑） | 核心体验缺失 | P1 |
| 7 | `idf_editor._is_object_line()` 恒 False，高亮失效 | 体验缺陷 | P1 |
| 8 | 序列化不保真（丢注释、重排对齐） | 编辑丢信息 | P1 |
| 9 | 无结果解析（err/sql/eplustbl/rdd） | 无法"快速查看结果" | P2 |
| 10 | 无可视化（matplotlib） | 无法直观呈现 | P3 |
| 11 | 无输出变量管理（rdd/mdd → 添加 Output:Variable） | 配置不便 | P2 |
| 12 | 无运行历史索引/对比 | 不可复现对比 | P4 |
| 13 | 无 epJSON 读写 | 格式覆盖不全 | P5 |
| 14 | 无国际化、无打包 | 发布受限 | P5 |

---

## Phase 0 — 工程基础设施与架构整改（必须先做）

**目标**：建立质量门禁，消除架构反模式，为后续功能开发提供可测试的骨架。本阶段不新增用户功能。

### 任务
- [ ] **0.1 项目元数据**：新增 `pyproject.toml`（PEP 621）、`requirements-dev.txt`、`ruff.toml`、`mypy.ini`；`.gitignore` 移除 `test/`，改为忽略 `.venv/`、`data/`、`config.json`、`resources/idd_cache.json`。
- [ ] **0.2 分层骨架**：按 AGENTS.md §2 创建 `src/core/`、`src/services/`、`src/persistence/`、`src/ui/`、`src/app.py` 目录与 `__init__.py`。
- [ ] **0.3 消除单例与硬编码**：
  - `config.py` → 拆为 `persistence/config_store.py`（读写）+ `services/config_service.py`（业务）+ `core/entities/config.py`（数据类）；删除 `DEFAULT_EP_PATH` 与模块级 `config`。
  - `idf_parser.py` → 迁移到 `core/idf/`（`models.py`/`parser.py`/`serializer.py`），删除模块级 `parser`。
  - `main.py` 改为构造 `Application`（`app.py`）并注入依赖，<30 行。
- [ ] **0.4 修复跨层违规**：`main_window` 不再调 `run_panel._start_run()`，改为发信号或调 `run_manager` 公开方法；`run_panel` 不再 `from .config import config`，改构造注入。
- [ ] **0.5 异常与日志**：引入 `core/exceptions.py`（`IDFParseError` 等）；各模块加 `logger = logging.getLogger(__name__)`；`app.py` 统一配置 logging；清除裸 `except`/`print`。
- [ ] **0.6 类型注解**：为迁移后的全部公开 API 补类型注解（`X | None`、泛型集合、`Path`）。
- [ ] **0.7 测试骨架**：建立 `tests/unit/`、`tests/integration/`、`tests/fixtures/`；把 `data/runs/test_run_001/` 的输出样本复制到 `tests/fixtures/`；为 `IDFParser` 写往返测试（至少 3 个 fixture IDF，含 `1ZoneUncontrolled.idf`）。
- [ ] **0.8 CI 脚本**：根目录加 `Makefile` 或文档记录 `ruff check . && mypy src && pytest -m "not e2e"`。

### 验收（阶段门禁）
- `ruff check .` 与 `mypy src` 全绿。
- `pytest -m "not e2e"` 通过，`src/core` 覆盖率 ≥ 90%。
- `grep -r "PySide6" src/core` 为空；`grep -rn "= Config()\|= IDFParser()" src` 为空；无 `._` 跨层调用。
- 应用可正常启动、打开 IDF、运行模拟（功能不退步）。

---

## Phase 1 — IDF/IDD 元数据驱动编辑

**目标**：字段编辑从"盲编辑"升级为"元数据驱动"，对标官方 IDF Editor（依据 R-5a）。这是目标 #1 的核心。

### 任务
- [ ] **1.1 IDD 模型与解析**（`core/idd/`）：
  - `models.py`：`FieldDef`（name/type/units/default/required/key_choices/reference/field_choice）、`ObjectDef`（name/group/fields）、`IDDDocument`。
  - `parser.py`：`IDDParser`，解析 `Energy+.idd`（IDD 格式：`\group`、`\obj`、`\field`、`\type`、`\units`、`\default`、`\key`、`\reference`、`\object-list`、`\required-field`、`\begin-extensible`）。依据 R-10。
  - 解析结果按 EnergyPlus 版本号缓存到 `resources/idd_cache.json`，启动优先加载缓存。
- [ ] **1.2 字段编辑面板升级**（`ui/tree/field_panel.py`）：
  - 依据 `ObjectDef` 渲染字段：`choice`→下拉、`object-list`→可搜索下拉（列出被引用对象名）、`real/integer`→带校验的输入框、显示单位/默认/必填标记。
  - 非法值即时标红提示；可扩展字段（`\begin-extensible`）支持"添加/删除字段"。
- [ ] **1.3 修复语法高亮**：`idf_editor._is_object_line()` 改为基于解析结果或行首 token 判断，使对象类型名高亮生效。
- [ ] **1.4 序列化保真**：`serializer.py` 改为**尽量保留原文**（缩进、对齐、注释、空行）；字段修改优先原地替换该行。往返测试扩展到 ≥10 个 fixture IDF（取自 EnergyPlus ExampleFiles）。
- [ ] **1.5 IDF 校验**：`services/idf_service.py` 提供 `validate(doc, idd) -> list[ValidationIssue]`，检查必填缺失、类型不匹配、引用对象不存在等；UI 在对象树/字段面板标红。
- [ ] **1.6 测试**：IDD 解析对 `Energy+.idd` 冒烟，断言 `Material`/`Zone`/`Building`/`Construction` 存在且字段数合理；字段编辑面板用 pytest-qt 烟测。

### 验收
- 打开任意 ExampleFiles IDF，对象树字段名、单位、下拉选项与官方 IDF Editor 一致（抽查 5 类对象对照 R-2）。
- 修改字段后保存，再次打开格式与字段值均正确（往返一致）。
- IDD 解析 + 缓存加载测试通过；`src/core` 覆盖率 ≥ 90%。

---

## Phase 2 — 结果结构化解析与错误诊断

**目标**：运行结束后"快速查看计算结果"——结构化而非纯文本。这是目标 #3 的核心。依据 R-4。

### 任务
- [ ] **2.1 错误解析**（`core/results/err_parser.py`）：`eplusout.err` → `list[ErrorRecord]`（severity/message/line_in_idf/object_name）。依据 R-4c。UI 用表格/列表呈现，双击跳转到 IDF 对象行。
- [ ] **2.2 SQLite 读取**（`core/results/sql_reader.py`）：用标准库 `sqlite3` 读 `eplusout.sql`，封装查询：列出可用变量（`ReportDataDictionary`）、按变量+时间范围取时序（`ReportData`）。依据 R-4b。**禁止** SQLAlchemy。
- [ ] **2.3 表格汇总解析**（`core/results/table_parser.py`）：解析 `eplustbl.xml`（优先，结构化）为 `list[ReportTable]`；备选 `eplustbl.csv`。依据 R-4d。UI 用表格视图呈现 Annual Building Utility Performance Summary 等报告。
- [ ] **2.4 输出变量管理**（`core/results/rdd_parser.py` + UI）：解析 `eplusout.rdd`/`.mdd`（IDF 格式）为可用变量列表；UI 提供勾选界面，一键生成并插入 `Output:Variable`/`Output:Meter` 对象到 IDF。依据 R-4e。
- [ ] **2.5 结果视图整合**（`ui/results/`）：运行面板「结果文件」升级为多标签：错误、汇总报告、时序数据、原始文件。大文件（>5MB）提供"外部打开"。
- [ ] **2.6 RunManager 归档增强**：运行结束写 `run.json`（run_id/起止时间/耗时/退出码/命令行/IDF 与 EPW 哈希/输出文件清单+大小）；禁止 `shutil.rmtree` 删历史目录，同名追加 `_1`/`_2`。
- [ ] **2.7 测试**：用 `tests/fixtures/test_run_001/` 真实输出做解析器测试；mock `QProcess` 测 RunManager 归档。

### 验收
- 运行 `1ZoneUncontrolled.idf`，结束后错误视图、汇总报告表、可用变量列表均正确呈现（与 `eplustbl.htm` 人工对照）。
- 双击错误条目跳转到 IDF 对应行。
- 勾选 rdd 变量可正确插入 IDF 并保存。
- 解析器单测覆盖 ≥ 90%。

---

## Phase 3 — 结果可视化

**目标**：对时序与汇总数据绘图，嵌入 Qt。这是目标 #4。引入 matplotlib + pandas。

### 任务
- [ ] **3.1 依赖与嵌入**：`requirements.txt` 加 `matplotlib>=3.7`、`pandas>=2.0`；用 `matplotlib.backends.backend_qtagg.FigureCanvasQTAgg` 嵌入 Qt。在 PR 说明为何需要（绘图与表格数据处理）。
- [ ] **3.2 时序曲线视图**（`ui/results/timeseries_view.py`）：从 `sql_reader` 取变量时序，绘制折线图；支持多变量叠加、时间范围选择（日/周/月/全年）、单位标注。
- [ ] **3.3 能耗汇总图**：基于 `table_parser` 结果绘制柱状图/饼图（如各终端能耗占比、月度能耗）。
- [ ] **3.4 负荷曲线**：从 sql 取 Zone/Sys 负荷，绘制负荷曲线（可选：散点、面积）。
- [ ] **3.5 图表交互**：图例切换、缩放、导出 PNG；绘图在主线程做（数据已加载），大数据集先聚合。
- [ ] **3.6 测试**：解析层（sql_reader/table_parser）单测；UI 图表用 pytest-qt 烟测（构建视图、喂数据、断言 canvas 存在）。

### 验收
- 运行后可对任意 `ReportDataDictionary` 变量绘时序曲线；能耗汇总有柱状图。
- 导出 PNG 成功；切换变量/时间范围图表更新。
- 无主线程卡顿（大数据集聚合后再绘）。

---

## Phase 4 — 运行历史与对比

**目标**：可复现、可对比。这是目标 #5。

### 任务
- [ ] **4.1 运行仓库**（`persistence/run_repository.py`）：索引 `data/runs/` 下所有 `run.json`，提供列表/过滤/详情查询。
- [ ] **4.2 历史浏览 UI**（`ui/run/history_view.py`）：列出历史运行（时间/IDF/退出码/耗时），双击打开结果视图。
- [ ] **4.3 多运行对比**：选择 2~N 次运行，对比同一变量时序（叠加曲线）或同一汇总项（并排柱状图）。
- [ ] **4.4 复现**：从历史运行一键重新打开其 IDF/EPW，或基于相同输入新建运行。
- [ ] **4.5 测试**：用 tmp_path 构造多个 run 目录测 repository；对比视图烟测。

### 验收
- 历史列表正确反映 `data/runs/`；对比两次运行的同一变量曲线叠加正确。
- 从历史运行可复现输入。

---

## Phase 5 — 完善与发布

**目标**：覆盖剩余格式、国际化、打包发布。

### 任务
- [ ] **5.1 epJSON 读写**（依据 R-11）：支持打开/保存 `.epJSON`（对照 `Energy+.schema.epJSON`）；提供 IDF↔epJSON 转换（命令行 `-c`/`--convert-only`）。
- [ ] **5.2 命令行参数完整建模**：`-a/-D/-m/-x/-p/-s` 等全部建模为枚举/数据类，UI 暴露常用项，高级项走校验过的附加参数框。依据 `energyplus --help`。
- [ ] **5.3 国际化**：UI 文案抽到 `.ts/.qm` 或简单字典，支持中/英切换。
- [ ] **5.4 打包**：`pyproject.toml` 配置构建，产出可执行入口（如 `python -m energyplus_launcher`）；可选 PyInstaller 单文件。
- [ ] **5.5 文档定稿**：README 使用说明与截图同步最终功能；AGENTS.md 与代码现状一致。

### 验收
- 可打开/保存 epJSON，IDF↔epJSON 转换结果与 `energyplus -c` 一致。
- 全部命令行参数可配置且校验生效。
- `pip install .` 后命令行可启动应用。

---

## 全局验收标准（每阶段都必须满足）

详见 [AGENTS.md §11](AGENTS.md)。核心：
1. `ruff check . && mypy src && pytest -m "not e2e"` 全绿。
2. `src/core` 覆盖率 ≥ 90%，`src/services` ≥ 70%。
3. 架构门禁：core 无 PySide6、无模块级单例、无跨层私有访问、UI 不直接 I/O/进程。
4. 涉及 EnergyPlus 的功能在代码注释/PR 标注参考资料编号。
5. 用户可感知功能在 README 有对应使用说明。

---

## 阶段依赖与建议顺序

```
P0 (基础设施) → P1 (IDD 编辑) → P2 (结果解析) → P3 (可视化) → P4 (历史对比) → P5 (完善发布)
```

- P0 是所有后续阶段的前置，**必须先完成**。
- P1 与 P2 在 P0 后可并行（分别属编辑侧与结果侧），但 P3 依赖 P2 的解析层。
- P4 依赖 P2 的 run.json 归档。
- 每个阶段交付前对照「验收」逐条核对，未达标不得进入下一阶段。

本轮结果：已完成上述保真编辑、自动同步、输出请求管理与时序/汇总分析增强；对象增删复制、跨运行对比和 epJSON 继续保留为后续任务。

### 增强 HTML 报告（本轮追加）

- 已实现：持久化的运行后自动生成开关；结果页面手动导出；单文件离线 HTML（内嵌 SVG/CSS/JS），包含能耗概览、环境周期时序、错误诊断与可搜索汇总表。
- 数据来自现有 ResultsService，报告构建在 core/results/html_report.py，后台任务避免阻塞界面；模型文本统一 HTML 转义。
- 依据 R-2 OutputControl:Table:Style、R-4b SQLite、R-4d 汇总表；缺少数据明确说明，保留 EnergyPlus 原始报告。

### 本轮 UI 易用性修复

- 设计：移除全局自绘样式与强制 Fusion，记录 Qt 原生样式/调色板并支持切回“跟随系统”；编辑器高亮随系统明暗变化。
- 设计：对象树置于左侧，属性编辑作为默认主工作区，IDF 源码与结果单独分页；运行面板默认收起，工具栏使用原生图标与文字。
- 设计：字段改用常驻输入框，Enter/离开输入框提交；保留对象选择，避免每次修改销毁输入控件或误清空属性面板；保存前提交当前编辑。
- 验证：Qt 键盘输入、切换字段、保存重开、源码同步、撤销与主题恢复回归；删除关于窗口开发者署名。

本轮 UI 验证：174 项测试通过，ruff/mypy 通过；core 覆盖率 96.2%，services 覆盖率 84.4%。已用官方示例与本机 IDD 检查属性工作区，并验证高亮不会误触发修改、连续输入保持焦点、保存提交、对象切换及主题恢复。

### IDF 源码滚动与行号栏修复

- 设计：源码编辑器保留不换行模式与原生按需水平滚动条，不额外添加滚动条；行号栏仅占正文视口高度，字体、行号位数与视口变化时同步更新几何，避免遮挡正文或滚动条。
- 验证：长行左右滚动、回到行首、滚动条与行号栏互不覆盖、行数/字体/窗口尺寸变化后的布局回归。

### 校验结果窗口易用性

- 设计：使用独立 ValidationDialog 替代 QMessageBox 的折叠详情区，默认较大尺寸、可拖动缩放与最大化，完整问题文本直接显示并支持复制；通过、未加载 IDD 与语法错误也使用该窗口。
- 验证：大量长消息下的缩放与滚动、只读文本、复制内容及校验入口回归。

### 提交前仓库整理

- 取消跟踪本机 config.json，保留文件并添加 config.example.json；完善日志、缓存、构建、外部安装目录与本地工具配置的忽略规则。
- 纳入用户提供的 GNU AGPL v3 LICENSE，项目元数据引用实际许可证；关于窗口提供许可证说明与完整条款入口。
- 官方 IDF 与真实结果样本作为回归资产保留；提交前重新执行 lint、类型检查和完整测试。
