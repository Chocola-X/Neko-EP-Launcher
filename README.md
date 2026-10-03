# EnergyPlus Launcher

> Linux 桌面端 EnergyPlus 图形化启动工具，基于 PySide6（Qt for Python）开发。
> 面向建筑节能 / 遮阳方向的研究与工程人员，目标是「方便编辑输入、一键运行模拟、快速查看并可视化结果」。

当前版本对应 **EnergyPlus 9.4.0**。本项目处于早期重构阶段，路线图见 [ROADMAP.md](ROADMAP.md)。

---

## 功能特性

### 已实现（初版，待重构）
- IDF 文本编辑器：语法高亮、行号、当前行高亮、查找
- IDF 对象树形视图：按类型分组浏览，搜索过滤
- 字段表格编辑：选中对象后表格编辑字段值
- EnergyPlus 运行：QProcess 非阻塞运行，实时日志，结果文件列表
- 设置：EnergyPlus 路径、天气文件目录、主题、附加运行参数
- 最近文件、运行结果归档到 `data/runs/<run_id>/`

### 规划中（见 ROADMAP）
- **IDD 元数据驱动的字段编辑**：下拉框、单位、默认值、必填校验、引用对象选择（依据 R-2/R-10）
- **结果结构化解析**：`.err` 错误定位、`.sql` 时序数据、`eplustbl.xml` 能耗汇总、`.rdd` 输出变量管理（依据 R-4）
- **结果可视化**：matplotlib 嵌入 Qt，时序曲线、负荷曲线、能耗对比
- **运行历史与对比**：浏览历史运行，多运行结果对比
- **epJSON 读写支持**（依据 R-11）

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
- 左侧对象树按类型分组，单击选中对象，字段面板显示字段表格
- 中间为文本编辑器（语法高亮 + 行号），**编辑 → 从文本同步到树** 重新解析
- 字段编辑与文本双向联动；保存前可撤销/重做

### 2. 运行模拟
- 底部运行面板确认 IDF 路径与天气文件（EPW）
- 可选设置运行 ID（留空则用时间戳 `YYYYMMDD_HHMMSS`）与附加参数
- 点击 **运行** 或按 **F5**；运行日志实时输出，运行结束弹窗提示
- 所有输入（IDF/EPW 副本）与输出归档到 `data/runs/<run_id>/`

### 3. 查看结果
- 运行面板「结果文件」标签页列出输出文件，单击预览（>5MB 提示外部打开）
- 规划：结构化错误视图、时序曲线、能耗汇总表、可视化图表

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
├── main.py                 # 入口
├── src/
│   ├── core/               # 纯逻辑层（IDF/IDD/结果解析，零 GUI 依赖）
│   ├── services/           # 业务服务层（运行编排、配置、历史）
│   ├── persistence/        # 持久化层（配置/运行仓库读写）
│   ├── ui/                 # 表现层（PySide6 窗口与组件）
│   └── app.py              # 依赖注入组装根
├── tests/                  # unit / integration / fixtures
├── data/runs/              # 运行归档（.gitignore）
└── resources/              # 图标、qss、IDD 缓存
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

## 开发者

华为云码道（CodeArts）代码智能体。

本项目参考了 NREL 官方 [EP-Launch](https://github.com/NREL/EP-Launch) 的 workflow/utilities 分层与测试组织思路。
