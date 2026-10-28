# EnergyPlus Launcher

> Linux 桌面端 EnergyPlus 图形化启动工具，基于 PySide6（Qt for Python）开发。
> 面向建筑节能 / 遮阳方向的研究与工程人员，目标是「方便编辑输入、一键运行模拟、快速查看并可视化结果」。

当前版本对应 **EnergyPlus 9.4.0**。本项目持续完善中，路线图见 [ROADMAP.md](ROADMAP.md)。

---

## 功能特性

### 已实现
- **IDF 文本编辑器**：语法高亮、行号、当前行高亮、查找
- **IDF 对象树形视图**：按类型分组浏览，搜索过滤
- **IDD 元数据驱动字段编辑**：下拉框（choice/object-list）、单位显示、默认值、必填标记、数值校验标红（依据 R-2/R-10）
- **IDF 校验**：必填缺失、类型不匹配、引用对象不存在检查
- **EnergyPlus 运行**：QProcess 非阻塞运行，实时日志，结果文件归档
- **命令行参数完整建模**：annual/design-day/epmacro/expandobjects/readvars/output-prefix/output-suffix 等全部建模为枚举/数据类（依据 R-3）
- **结果结构化解析**：
  - `.err` 错误/警告表格视图，定位到对象（依据 R-4c）
  - `.sql` SQLite 时序数据读取（依据 R-4b）
  - `eplustbl.xml` 表格汇总报告（依据 R-4d）
  - `.rdd`/`.mdd` 可用输出变量列表（依据 R-4e）
- **结果可视化**（matplotlib 嵌入 Qt）：
  - 时序曲线绘图（多变量叠加、导出 PNG）
  - 能耗汇总柱状图/饼图
- **运行历史浏览**：浏览历史运行，过滤，双击打开结果
- **设置**：EnergyPlus 路径、天气文件目录、主题、附加运行参数
- **运行归档**：`run.json` 元数据（run_id/时间/退出码/命令行/文件哈希/输出清单）

---

## 环境要求

| 项 | 版本 |
|----|------|
| OS | Linux（KDE/GNOME 均可） |
| Python | >= 3.10 |
| EnergyPlus | 9.4.0（已安装于本机，路径在设置中配置） |

## 安装

```bash
git clone <repo-url> EnergyPlus-Laucher
cd EnergyPlus-Laucher
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # 运行依赖
pip install -r requirements-dev.txt    # 开发依赖（可选，含测试/lint）
```

## 运行

```bash
python main.py
```

首次启动后，进入 **工具 → 设置**，配置 EnergyPlus 安装目录（须含 `energyplus` 可执行文件与 `Energy+.idd`）。

---

## 使用说明

### 1. 编辑 IDF
- **文件 → 打开** 打开现有 IDF；**文件 → 打开示例** 从 EnergyPlus ExampleFiles 选择
- 左侧对象树按类型分组；打开文件后默认显示右侧 **属性编辑**，单击对象即可直接修改“值”栏
- 属性输入框始终可见；按 Enter 或切换到其他字段提交，Ctrl+S 保存时会提交当前输入。切换对象后继续编辑不会丢失选择
- 通过 **IDF 源码** 标签页或工具栏编辑完整文本；保留语法高亮、行号与自动同步。沿用底部原生水平滚动条，超出宽度的长行可左右拖动查看；行号栏固定在左侧，不覆盖正文和滚动条
- 文本停止输入 600ms 后自动同步对象树；语法未完成时暂停字段编辑，避免覆盖新文本
- 字段编辑保留原文注释、空行及缩进，支持 Ctrl+Z 撤销；同一行多个对象也可解析
- IDD 的 choice/object-list 字段提供可搜索下拉，未填写字段也能直接补充
- **编辑 → 校验 IDF** 检查必填、数值类型、取值范围及引用；结果窗口支持拖动调整大小和最大化，完整信息直接显示，可滚动查看或复制完整报告
- **编辑 → 配置可视化输出** 启用 `Output:SQLite, SimpleAndTabular`、汇总报告与 IDF 格式变量字典（R-2）；已有汇总请求保留。仍需请求具体的输出变量，保存并重新运行才会产生对应曲线

### 2. 运行模拟
- 底部运行面板确认 IDF 路径与天气文件（EPW）
- 可选设置运行 ID（留空则用时间戳 `YYYYMMDD_HHMMSS`）与附加参数
- 点击 **运行** 或按 **F5**；运行日志实时输出，运行结束弹窗提示
- 默认勾选 **生成分析数据**：在归档的运行副本中启用 SQLite（SimpleAndTabular）、汇总与变量字典，保留已有变量和汇总请求，不修改原始 IDF。需要严格按原文件运行时可取消，此选项会记忆（R-2）。曲线数据仍取决于模型中的 Output:Variable/Output:Meter 请求。
- 所有输入（IDF/EPW 副本）与输出归档到 `data/runs/<run_id>/`

### 3. 查看结果
- **文件 → 打开结果目录** 可直接在主工作区「结果分析」打开以前的输出，无需重新模拟
- 支持标准文件名和自定义输出前缀；同目录存在多个同类文件时提示选择单次运行目录
- 运行结束自动加载并切换主工作区「结果分析」；运行配置面板只保留配置与日志。历史记录也在主工作区打开。
- 缺少 XML 汇总时从 SQLite 恢复汇总表（需 `SimpleAndTabular`）；仅生成原始 HTML 的已有运行也可直接查看汇总与能耗图表（R-4d）。缺少 SQLite 时会显示原因和下次运行的设置提示。
- 主工作区「结果分析」提供 6 个子标签：
  - **错误**：`eplusout.err` 解析为表格，按级别/对象/描述展示
  - **汇总报告**：`eplustbl.xml` 解析为结构化表格，左侧选择表格名
  - **时序曲线**：从 `eplusout.sql` 读取变量列表，默认绘制首个可见变量，可搜索并多选变量，按环境周期与起止日期筛选，以真实日期绘图，不同单位分图；支持缩放、PNG 和完整 CSV 导出，表格预览前 1000 条。时序查询在线程池执行，暖机数据默认排除（R-4b）
  - **能耗图表**：选择汇总表及具体数值列绘制柱状图/饼图，可导出 PNG
  - **可用输出变量**：搜索 RDD/MDD，点击「添加选中变量到当前 IDF」插入每小时输出请求，保存并重新运行（R-4e）
  - **原始文件**：输出文件列表，单击预览（>5MB 提示外部打开）

### 4. 增强 HTML 报告

- EnergyPlus 的原始 `eplustbl.htm` 为表格汇总报告，具体格式由 `OutputControl:Table:Style` 控制（R-2）。本机 9.4 未配置此对象时默认 Comma；选择 HTML、XMLandHTML 或 All 才会包含 HTML。
- 在运行面板勾选 **运行结束后生成增强 HTML 报告**（设置会记忆），完成后在该次运行目录写入 `enhanced-report.html`。
- 已有结果可通过 **文件 → 打开结果目录 → 导出增强 HTML 报告** 生成。
- 报告包含状态、诊断、能耗柱状图、按环境周期分开的时序曲线及可筛选的全部汇总表；图表悬停可查看数值。
- HTML、样式、SVG 与筛选脚本全部内嵌，无需网络或额外服务即可打开和分享。原始 EnergyPlus 报告保留。
- 自动展示最多 6 个变量，优先每小时温度；未输出 SQL 或汇总数据时明确提示缺失内容。需要更多变量可在启动器的时序曲线中选择。

### 5. 运行历史
- **运行 → 运行历史** 打开历史面板
- 按 IDF 名称过滤、仅显示成功运行
- 双击历史记录在主工作区「结果分析」加载该次运行

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+N / O / S | 新建 / 打开 / 保存 |
| Ctrl+Shift+S | 另存为 |
| Ctrl+Z / Y | 撤销 / 重做 |
| Ctrl+F | 查找 |
| F5 | 运行 EnergyPlus |
| Ctrl+Q | 退出 |

---

## 项目结构

```
EnergyPlus-Laucher/
├── main.py                 # 入口（<30 行）
├── pyproject.toml          # 项目元数据与构建配置
├── src/
│   ├── core/               # 纯逻辑层（IDF/IDD/结果解析，零 GUI 依赖）
│   │   ├── idf/            # IDF 解析/序列化/校验
│   │   ├── idd/            # IDD 解析与字段元数据
│   │   ├── results/        # 输出文件解析（err/sql/rdd/table）
│   │   └── entities/       # 值对象与枚举（config/run_options）
│   ├── services/           # 业务服务层（运行编排/配置/结果/IDD/IDF）
│   ├── persistence/        # 持久化层（配置/运行仓库读写）
│   ├── ui/                 # 表现层（PySide6 窗口与组件）
│   │   ├── editor/         # IDF 文本编辑器
│   │   ├── tree/           # 对象树/字段面板
│   │   ├── run/            # 运行面板/历史视图
│   │   ├── results/        # 结果视图（错误/汇总/绘图/原始）
│   │   └── settings/       # 设置对话框
│   └── app.py              # 依赖注入组装根
├── tests/                  # unit / integration / fixtures
├── data/runs/              # 运行归档（.gitignore）
└── resources/              # IDD 缓存
```

详细分层规则与依赖方向见 [AGENTS.md §2](AGENTS.md)。

---

## 开发

开发规范、行为准则、验收标准统一见 [AGENTS.md](AGENTS.md)。实施路线与阶段任务见 [ROADMAP.md](ROADMAP.md)。

### 常用命令
```bash
ruff check .                  # lint
mypy src                      # 类型检查
pytest -m "not e2e"           # 单元 + 集成测试
pytest tests/unit -q --cov=src/core --cov-fail-under=90
```

本地完整运行链验收（需要安装 EnergyPlus；默认与自定义前缀各运行一次官方示例，检查主分析页、曲线与自动报告）：

```bash
ENERGYPLUS_HOME=/path/to/EnergyPlus QT_QPA_PLATFORM=offscreen pytest tests/e2e -m e2e -q
```

### 分支与提交
- 分支：`feature/<简述>` / `fix/<简述>` / `refactor/<简述>`，从 `master` 切出
- 提交信息：`<类型>: <简述>`，类型 ∈ {feat, fix, refactor, test, docs, chore, perf}
- 未经明确同意不提交、不推送

---

## EnergyPlus 输出文件说明

运行结束后 `data/runs/<run_id>/` 下产生的标准输出（依据 R-4a Output File List）：

| 文件 | 说明 |
|------|------|
| `eplusout.err` | 错误/警告，诊断首要文件 |
| `eplusout.end` | 一行成功/失败摘要 |
| `eplusout.sql` | SQLite 时序+汇总，**可视化首选数据源**（依据 R-4b） |
| `eplusout.eso` / `.mtr` | 标准输出 / 计量输出（二进制，可经 ReadVarsESO 转 csv） |
| `eplustbl.htm/csv/xml` | 表格汇总报告（Annual Building Utility Performance Summary 等） |
| `eplusout.eio` | 一次性汇总（CSV） |
| `eplusout.rdd` / `.mdd` | 可用输出变量 / 计量变量列表（IDF 格式） |
| `eplusout.bnd` / `.audit` / `.shd` / `.dxf` | 节点连接 / 审计 / 阴影 / 几何 |

完整字段与格式定义查阅 [EnergyPlus 9.4 Output Details](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/)。

---

## 参考资料

所有涉及 EnergyPlus 行为的决策均以下列官方文档为权威来源（完整索引见 [AGENTS.md §13](AGENTS.md)）：

- **Input Output Reference** — IDF 对象/字段定义：https://bigladdersoftware.com/epx/docs/9-4/input-output-reference/
- **Output Details and Examples** — 输出文件格式：https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/
- **Auxiliary Programs** — 辅助程序：https://bigladdersoftware.com/epx/docs/9-4/auxiliary-programs/
- **Getting Started** — 入门与 IDF Editor：https://bigladdersoftware.com/epx/docs/9-4/getting-started/
- 本地 IDD：`<energyplus_path>/Energy+.idd`；本地 epJSON Schema：`<energyplus_path>/Energy+.schema.epJSON`

---

## 参考实现

本项目参考了 NREL 官方 [EP-Launch](https://github.com/NREL/EP-Launch) 的 workflow/utilities 分层与测试组织思路。

## 本轮验证

使用本机 EnergyPlus 9.4 的 10 个官方 ExampleFiles（含两个遮阳模型）验证逐字符保真、修改后再解析；测试样本已纳入 `tests/fixtures/`，无需本地安装即可运行回归。另用 `1ZoneUncontrolled.idf` 真实执行设计日模拟，核验配置输出后的 SQLite、时序变量与汇总报告。大型时序图按步长抽样显示，CSV 保留全部查询数据；跨运行对比与 epJSON 编辑仍待实现。

## 界面与系统主题

- **工具 → 设置 → 通用 → 主题 → 跟随系统（原生外观）**：使用当前 Qt 平台提供的系统样式与颜色；不强制 Fusion，不加载全局自绘样式。深色/浅色仍可手动选择，点击“应用”立即生效。
- 属性编辑、IDF 源码、结果分析分为三个工作区；运行配置与日志默认收起，点击工具栏 **运行配置与日志** 展开。
- 常用工具栏使用原生图标和文字，提供打开、保存、另存为、属性、源码、校验、运行、结果与设置入口。
- 运行面板与 F5 共用保存和运行流程；关于窗口已移除开发者署名。
- 原生外观取决于桌面为 Qt 提供的主题插件；无图形界面的测试环境只能验证控件行为和调色板恢复，不能代替实际桌面的视觉验收。

## 许可证

本项目采用 **GNU Affero General Public License v3**，完整条款见 [LICENSE](LICENSE)。应用的“帮助 → 关于”中也提供许可证入口。

## 仓库文件管理

- 版本库保留源码、测试、官方示例测试样本、文档和许可证。
- `config.json` 是本机配置，不纳入版本控制；现有本地文件会保留。首次使用可通过设置窗口生成，或参考 `config.example.json`。
- `data/` 下的模拟历史、生成报告，`resources/idd_cache*.json`，日志、虚拟环境、测试缓存、覆盖率和构建产物均已忽略。
- 本地编辑器/智能体配置与外部 EnergyPlus、OpenStudio、EP-Launch 安装目录均已排除。`tests/fixtures/` 中的回归数据保留，不通过文件扩展名一律排除 IDF、天气或 SQL 文件。
