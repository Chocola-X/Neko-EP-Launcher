# AGENTS.md — Neko-EP-Launcher 开发规范与行为准则

> 本文件是**所有参与本项目的 AI Agent 与人类开发者必须遵守的强制规范**。
> 优先级：本文件 > 全局 AGENTS.md > 通用约定。当本文件与其它规则冲突时，以本文件为准。
> 语言：所有提交信息、文档、注释、对话一律使用**简体中文**。
> **开发阶段说明**：当前处于**快速开发迭代阶段**，允许为了架构优化与功能演进进行破坏性更改而**无需考虑兼容层**。实现新功能与修复**直接在 `master` 分支中进行迭代**，不需要独立开分支。

---

## 0. 项目定位与最终目标

本项目是一个 **Linux 桌面端 EnergyPlus 图形化启动工具（Neko-EP-Launcher）**，基于 PySide6（Qt for Python）开发，目标用户为建筑节能 / 遮阳方向的研究与工程人员。代码仓库位于 https://github.com/Chocola-X/Neko-EP-Launcher 。

最终目标（按重要性排序）：

1. **方便地设置与编辑 EnergyPlus 计算输入数据**（IDF/epJSON，字段感知、有校验、有 IDD 元数据）。
2. **一键运行 EnergyPlus 模拟**，实时查看日志，运行结束自动归档。
3. **快速查看计算结果**：解析 `.err`/`.sql`/`.eso`/`eplustbl.*` 等输出文件，结构化呈现。
4. **结果可视化**：引入绘图库（matplotlib，嵌入 Qt），对时序数据、能耗汇总、负荷曲线等绘图。
5. **可对比、可复现**：支持运行历史浏览与多运行结果对比。

> 任何功能决策都必须能追溯到上述目标之一，否则不予实现。**禁止想当然决定功能**——涉及 EnergyPlus 行为时，必须查阅「参考资料」中列出的官方文档并注明出处。

---

## 1. 技术栈与版本约束

| 项 | 约束 | 说明 |
|----|------|------|
| Python | >= 3.10 | 使用 `match`、`dataclass(slots=True)` 等特性 |
| GUI | PySide6 >= 6.4 | Qt for Python，**禁止**混用 PyQt |
| 绘图 | matplotlib >= 3.7 | 通过 `matplotlib.backends.backend_qtagg` 嵌入 Qt |
| 数据 | pandas >= 2.0 | 仅用于结果数据解析，**不得**引入 numpy 之外的重型科学计算栈 |
| SQLite | 标准库 `sqlite3` | 读取 `eplusout.sql`，**禁止**引入 SQLAlchemy |
| 测试 | pytest >= 7.4, pytest-qt, pytest-cov | 见 §9 |
| Lint | ruff | 替代 flake8/black/isort，统一配置 |
| 类型 | mypy（严格） | CI 强制通过 |
| 打包 | pyproject.toml（PEP 621） | **禁止** setup.py |
| EnergyPlus | 9.4.0（当前安装版） | 代码须兼容 9.x，不硬编码小版本 |

**依赖新增原则**：每新增一个第三方依赖，必须在 PR 描述中说明「为何不能用标准库或已有依赖替代」。绘图与数据解析相关依赖集中在 `requirements.txt`，开发依赖在 `requirements-dev.txt`。

---

## 2. 分层架构与目录结构（高内聚、低耦合）

代码必须按下列分层组织，**层间只能自上而下依赖**，禁止逆向依赖与跨层调用。

```
Neko-EP-Launcher/
├── main.py                         # 仅负责构造 QApplication 与启动，<30 行
├── pyproject.toml                  # 项目元数据与构建配置
├── requirements.txt                # 运行依赖
├── requirements-dev.txt            # 开发依赖（pytest/ruff/mypy）
├── ruff.toml / mypy.ini            # 静态检查配置
├── config.json                     # 用户配置（运行时生成，不入库）
├── data/                           # 运行数据（.gitignore 忽略）
│   └── runs/<run_id>/              # 每次运行的独立目录
├── resources/                      # 静态资源（图标、qss、IDD 缓存）
├── tests/                          # 测试镜像 src/ 结构
│   ├── unit/
│   ├── integration/
│   └── fixtures/                   # 真实 IDF/输出文件样本
└── src/
    ├── core/                       # 纯逻辑层，零 GUI 依赖，零 I/O 副作用（可纯单测）
    │   ├── idf/                    # IDF 解析、序列化、文档模型
    │   │   ├── models.py           # IDFObject/IDFDocument 数据类
    │   │   ├── parser.py           # IDFParser
    │   │   └── serializer.py       # 保真序列化
    │   ├── idd/                    # IDD 解析与字段元数据
    │   │   ├── models.py           # FieldDef/ObjectDef/FieldMeta
    │   │   └── parser.py           # IDDParser（解析 Energy+.idd）
    │   ├── results/                # 输出文件解析（纯逻辑）
    │   │   ├── err_parser.py       # .err → ErrorRecord 列表
    │   │   ├── sql_reader.py       # .sql → 时序/汇总数据
    │   │   ├── eso_parser.py       # .eso 解析（如需）
    │   │   ├── table_parser.py     # eplustbl.xml/csv → 结构化表格
    │   │   └── rdd_parser.py       # .rdd/.mdd → 可用输出变量列表
    │   └── entities/               # 跨层共享的值对象与枚举
    ├── services/                   # 业务服务层，编排 core，含 I/O 与进程
    │   ├── config_service.py       # 配置读写（注入路径，非全局单例）
    │   ├── ep_runner.py            # EnergyPlus 进程管理（QProcess 封装）
    │   ├── run_manager.py          # 运行编排：准备目录、调用 runner、归档
    │   ├── idf_service.py          # IDF 打开/保存/校验编排
    │   └── history_service.py      # 运行历史索引与检索
    ├── persistence/                # 持久化层，仅做读写，不含业务规则
    │   ├── config_store.py         # JSON 配置读写
    │   └── run_repository.py       # runs 目录的读写与索引
    ├── ui/                         # 表现层，仅 PySide6，不写业务逻辑
    │   ├── main_window.py
    │   ├── editor/                 # IDF 文本编辑器、语法高亮
    │   ├── tree/                   # 对象树、字段编辑面板
    │   ├── run/                    # 运行面板、日志视图
    │   ├── results/                # 结果浏览、可视化视图
    │   ├── settings/               # 设置对话框
    │   ├── dialogs/                # 通用对话框
    │   └── theme.py                # 主题/调色板
    └── app.py                      # 应用装配（依赖注入容器）
```

### 2.1 层职责与依赖规则

| 层 | 职责 | 允许依赖 |
|----|------|----------|
| `core/` | 纯数据结构与算法，无 Qt、无文件系统副作用 | 仅标准库 + `core/` 内部 |
| `services/` | 编排 core，处理进程与 I/O，发信号 | `core/`、`persistence/` |
| `persistence/` | 纯读写，无业务判断 | `core/`（仅用其模型） |
| `ui/` | 渲染与用户交互，把信号转命令 | `services/`、`core/`（只读模型） |
| `app.py` | 构造各层实例并注入依赖 | 全部 |

**强制规则**：
- `core/` 内**禁止** `import PySide6`，**禁止** `import` 任何 `services/`/`ui/`/`persistence/` 模块。
- `ui/` 内**禁止**直接读写文件系统、**禁止**直接 `subprocess`/`QProcess` 启动 EnergyPlus；这些必须调用 `services/`。
- `persistence/` **禁止** import `PySide6`。
- **禁止模块级单例**（如现有 `config = Config()`、`parser = IDFParser()`）。实例由 `app.py` 构造并注入。
- **禁止跨层访问私有成员**（如 `run_panel._start_run()`）。层间通信只用：构造注入的方法、Qt 信号、明确公开的接口。

### 2.2 依赖注入

`app.py` 是唯一的"组装根"。示例：

```python
# src/app.py
class Application:
    def __init__(self, config_path: Path):
        self.config_store = ConfigStore(config_path)
        self.config_service = ConfigService(self.config_store)
        self.runner = EPRunner()
        self.run_manager = RunManager(self.runner, self.config_service, RUNS_DIR)
        self.idf_service = IDFService(IDFParser(), IDFSerializer())
        self.main_window = MainWindow(
            run_manager=self.run_manager,
            idf_service=self.idf_service,
            config_service=self.config_service,
        )
```

UI 组件通过构造函数接收所需服务，**不得**在 UI 内部 `from ..services.config_service import config_service`。

---

## 3. 命名与代码风格

- **包/模块**：`snake_case`，包名复数仅用于真正容纳多类的工具包（如 `entities`）。
- **类**：`PascalCase`；Qt 子类以 Qt 基类名后缀（`RunPanel(QWidget)`）。
- **函数/方法/变量**：`snake_case`；私有以单下划线前缀；**禁止**双下划线名称改写。
- **常量**：`UPPER_SNAKE`，定义在模块顶部或 `entities/constants.py`。
- **信号**：`camelCase`（Qt 惯例），如 `lineOutput = Signal(str)`。
- **文件编码**：UTF-8，无 BOM；换行 LF。
- **缩进**：4 空格，**禁止** Tab。
- **行宽**：100 字符，ruff 强制。
- **import 顺序**：标准库 → 第三方 → 本项目，每组内字母序，ruff `isort` 自动整理。
- **禁止**：通配 import（`from x import *`）、相对 import 跨层（同层可用相对）。

---

## 4. 类型注解与数据建模

- **所有**函数签名、方法签名、模块级变量必须有类型注解。
- 使用 `dataclass(slots=True, frozen=True)` 定义值对象（不可变）；可变文档模型用 `dataclass(slots=True)`。
- 优先用 `Path` 而非 `str` 表示路径。
- 集合类型写全泛型：`list[IDFObject]`、`dict[str, FieldDef]`，**禁止**裸 `list`/`dict`。
- 可空用 `X | None`（Python 3.10+ 联合类型），**禁止** `Optional`/`Union` 旧式写法。
- 禁止用 `Any`，确需时加 `# type: ignore[reason]` 并在 PR 说明。

```python
@dataclass(slots=True, frozen=True)
class ErrorRecord:
    severity: str  # "Warning" | "Severe" | "Fatal" | "Info"
    message: str
    line_in_idf: int | None
    object_name: str | None
```

---

## 5. 异常处理与日志

### 5.1 异常分层
- `core/` 抛出**领域异常**（如 `IDFParseError`、`IDDFormatError`），不捕获不吞。
- `services/` 捕获 I/O/进程异常，转换为业务结果或向上抛领域异常。
- `ui/` 在信号槽内**必须**捕获所有异常，转成用户可见消息（状态栏/对话框），**禁止**异常逃逸到 Qt 事件循环。

### 5.2 禁止
- `except:` 裸捕获、`except Exception:` 后 `pass`、`except Exception as e: print(e)`。
- 捕获后必须：记录日志 + 决策（恢复/上抛/通知用户）三者之一。

### 5.3 日志
- 使用标准库 `logging`，**禁止** `print`（除 `main.py` 启动早期）。
- 每个模块顶部 `logger = logging.getLogger(__name__)`。
- UI 用户可见信息走状态栏/通知，**不**走 logging 弹窗。
- 日志配置在 `app.py` 统一初始化，支持 DEBUG/INFO 到文件 + 控制台。

---

## 6. PySide6 使用规范

### 6.1 信号与槽
- 跨组件通信**优先用 Qt 信号**，而非直接调方法。信号名 `camelCase`。
- 信号参数必须是简单类型或不可变值对象，**禁止**把可变文档模型直接当信号载荷传递可变引用后由接收方修改（会导致双向耦合）；如需修改，发送方持有引用，接收方通过调用服务方法修改并由服务发信号通知。

### 6.2 线程与进程
- EnergyPlus 运行用 `QProcess`（非阻塞），通过信号通知完成。**禁止** `waitForFinished` 阻塞主线程。
- 耗时解析（如大 `.eso`、IDD 解析）放 `QThread` 或 `QThreadPool` + `QRunnable`，用信号回主线程更新 UI。
- **禁止**在工作线程直接操作 widget；只能发信号。

### 6.3 资源管理
- `QProcess`、`QFile`、`QThread` 必须设置父对象或显式 `deleteLater`，避免泄漏。
- 文件句柄用 `with open(...)`。

### 6.4 UI 与逻辑分离
- 每个 widget/窗口类只做：构建 UI、连接信号、把用户操作转成对 service 的调用、把 service 信号转成 UI 更新。
- **禁止**在 widget 内写解析/序列化/进程/持久化逻辑。

---

## 7. IDF / IDD 处理规范（核心域规则）

> 权威依据：EnergyPlus **Input Output Reference**（见「参考资料」R-2）。任何关于字段含义、单位、默认值、选择项的判断都必须查此文档，不得凭记忆。

### 7.1 IDF 解析
- 解析器必须正确处理：单/双引号字符串、`$` 宏变量、行尾 `!-` 字段名注释、嵌套括号（`()` 深度）、`!` 行注释、逗号/分号终止符。
- 解析必须记录每个对象的 `line_start`/`line_end`（1-based），用于错误定位与跳转。
- 解析失败必须抛 `IDFParseError(line, message, context)`，不得返回半成品文档。

### 7.2 序列化保真
- 序列化必须**尽量保留原文格式**：缩进、字段对齐、注释、空行。
- 当字段值被修改时，**优先原地替换该行**，而非整体重排（避免光标跳变、diff 噪声）。
- 序列化结果必须可被同一解析器重新解析且对象集合不变（往返一致性，单测覆盖）。

### 7.3 IDD 元数据（必须实现）
- 启动时解析 `Energy+.idd`（路径来自配置），构建 `dict[str, ObjectDef]`。
- 每个 `ObjectDef` 含：`name`、`group`、`fields: list[FieldDef]`，每个 `FieldDef` 含：`name`、`type`（real/integer/alpha/choice/object-list 等）、`units`、`default`、`required`（field choice）、`key_choices`、`reference`。
- 字段编辑面板必须利用 IDD 元数据：
  - `choice` 类型用下拉框；
  - `object-list` 类型用可搜索下拉（列出被引用对象名）；
  - `real/integer` 做范围与类型校验，非法值即时标红提示；
  - 显示单位与默认值；
  - 必填字段标记。
- IDD 解析结果缓存到 `resources/idd_cache.json`（按 EnergyPlus 版本号命名），下次启动直接加载。

### 7.4 epJSON
- EnergyPlus 支持 epJSON 输入（`Energy+.schema.epJSON`）。`-c` 可互转。
- 中期目标支持 epJSON 读写，但 IDF 优先。

---

## 8. EnergyPlus 运行规范

> 权威依据：命令行 `energyplus --help`（已记录于 ROADMAP）与 **Auxiliary Programs** 文档（R-3）。

### 8.1 命令行参数（完整且固定）
```
-a --annual            强制全年模拟
-c --convert           IDF↔epJSON 互转
-D --design-day        仅设计日模拟
-d --output-directory  输出目录
-i --idd               IDD 路径
-m --epmacro           先跑 EPMacro
-p --output-prefix     输出文件前缀（默认 eplus）
-r --readvars          模拟后跑 ReadVarsESO（生成 csv）
-s --output-suffix     输出命名风格 L/C/D
-w --weather           天气文件
-x --expandobjects    先跑 ExpandObjects
   --convert-only      仅转换不模拟
```
- 运行器必须把这些参数建模为枚举/数据类，**禁止**拼接字符串。
- UI 暴露常用项（天气、readvars、annual/design-day、expandobjects、output-prefix），高级项走"附加参数"文本框但需校验。

### 8.2 运行目录与归档
- 每次运行独立目录 `data/runs/<run_id>/`，`run_id` 默认时间戳 `YYYYMMDD_HHMMSS`，可自定义。
- 运行前**复制** IDF 与 EPW 到运行目录，保证可复现。
- 运行结束写入 `run.json` 元数据：run_id、开始/结束时间、耗时、退出码、命令行、IDF/EPW 哈希、输出文件清单与大小。
- **禁止**用 `shutil.rmtree` 删除已存在运行目录（会丢历史）；同名时追加 `_1`/`_2` 后缀。

### 8.3 输出文件契约（必须遵守，用于结果解析）

> 权威依据：**Output Details and Examples**（R-4），尤其「Output File List」。

| 文件 | 用途 | 解析方式 |
|------|------|----------|
| `eplusout.err` | 错误/警告 | 文本解析为 `ErrorRecord` 列表，定位到 IDF 对象 |
| `eplusout.end` | 一行成功/失败 | 判断运行状态 |
| `eplusout.sql` | 时序+汇总（SQLite） | **首选可视化数据源**，标准库 `sqlite3` 读取 |
| `eplusout.eso` | 标准输出（二进制） | 需 ReadVarsESO 转 csv；优先用 sql |
| `eplusout.mtr` | 计量输出 | 同 eso |
| `eplustbl.xml` | 表格汇总报告（XML） | 解析为结构化表格，展示能耗汇总 |
| `eplustbl.csv` | 表格汇总（CSV） | 备选 |
| `eplusout.eio` | 一次性汇总（CSV） | 解析建筑/区域摘要 |
| `eplusout.rdd` | 可用输出变量 | 解析为列表，供用户勾选添加 `Output:Variable` |
| `eplusout.mdd` | 可用计量变量 | 同 rdd |
| `eplusout.bnd` | 节点连接 | 文本查看 |
| `eplusout.audit`/`.shd`/`.dxf` | 审计/阴影/几何 | 文本/外部查看 |

- 结果解析器对每个文件类型独立实现，返回统一 `ResultData` 抽象。
- 大文件（>5MB）默认不全文加载，提供"用外部程序打开"。

---

## 9. 测试规范

> 框架：pytest + pytest-qt（Qt fixture）+ pytest-cov。覆盖率门槛见 §11。

### 9.1 测试分层
- **unit/**：测 `core/` 全部，纯函数，无 Qt，无文件系统（用 `tmp_path` fixture 例外）。覆盖率目标 ≥ 90%。
- **integration/**：测 `services/` + `persistence/`，可用 `tmp_path`、真实 IDF 样本、mock `QProcess`。覆盖率目标 ≥ 70%。
- **ui/**：关键交互用 pytest-qt 的 `qtbot` 做烟测（构建窗口、点击按钮、断言信号），不追求像素级。

### 9.2 强制要求
- 每个 `core/` 公开函数/类必须有对应测试文件 `test_<module>.py`。
- IDF 解析器必须有**往返测试**：`parse(serialize(parse(text))) == parse(text)`，覆盖 fixtures 下至少 10 个真实 IDF（取自 EnergyPlus ExampleFiles）。
- IDD 解析器必须对 `Energy+.idd` 做冒烟解析并断言关键对象（`Material`、`Zone`、`Building`）存在。
- 运行器测试用 mock `QProcess`，**禁止**在 CI 真跑 EnergyPlus（慢且依赖安装）；真跑放在可选的 `tests/e2e/`，本地手动执行。
- fixtures 用真实文件放 `tests/fixtures/`，包含至少：一个最小 IDF、一个含错误的 IDF、一个真实运行输出目录（取自现有 `data/runs/test_run_001/`）。

### 9.3 命令
```bash
pytest -m "not e2e"          # 默认跑除端到端外全部
pytest tests/unit -q --cov=src/core --cov-fail-under=90
ruff check .                 # lint
mypy src                     # 类型检查
```

---

## 10. 文档与注释

- **公开类/函数**必须有 docstring（Google 风格，中文），说明用途、参数、返回、可能的异常。
- **非公开**逻辑复杂处加注释解释"为什么"，不解释"是什么"。
- **禁止**用注释复述代码。**禁止**保留注释掉的死代码（用 git 管理历史）。
- README.md 面向用户；AGENTS.md 面向开发者/AI；ROADMAP.md 面向排期。三者保持一致，矛盾时以 AGENTS.md 为准并同步修正。
- 涉及 EnergyPlus 行为的注释/文档必须标注参考资料编号（如「依据 R-4 Output File List」）。

---

## 11. 验收标准（每个 PR / 每个阶段都必须满足）

### 11.1 代码质量门禁（CI 必须全绿）
1. `ruff check .` 无告警。
2. `mypy src` 无错误。
3. `pytest -m "not e2e"` 全通过。
4. `src/core` 覆盖率 ≥ 90%，`src/services` ≥ 70%。
5. 无新增模块级单例、无 `from x import *`、无裸 `except`。

### 11.2 架构门禁（人工/脚本检查）
6. `src/core` 下任意 `.py` 文件 `grep -r "PySide6"` 为空。
7. `src/ui` 下任意 `.py` 文件不出现 `subprocess`/`QProcess`/`open(` 写文件。
8. 无跨层访问私有成员（`._` 跨类调用）。
9. 新增依赖已在 PR 说明理由并写入对应 requirements。

### 11.3 功能验收（按阶段，见 ROADMAP）
10. 对应阶段的所有任务完成且测试通过。
11. 用户可感知功能在 README「使用说明」中有对应步骤。
12. 涉及 EnergyPlus 的功能在文档中标注参考资料编号。

### 11.4 分支与提交规范
- **分支策略**：当前处于快速开发迭代期，新功能与修复**直接在 `master` 分支**进行迭代开发与提交，不需要独立开分支；允许直接进行破坏性变更而不保留兼容层。
- 提交信息：`<类型>: <简述>`，类型 ∈ {feat, fix, refactor, test, docs, chore, perf}。正文说明动机与影响。
- 一个 commit 一个主题；禁止混合无关改动。
- **禁止**自动提交（`git commit -m "update"` 之类无意义信息）。
- 未经用户明确同意，**禁止** `git push` 与 `git commit`。

---

## 12. 禁止事项清单（硬性）

1. 禁止 `print` 调试残留入库。
2. 禁止硬编码绝对路径（如现有 `DEFAULT_EP_PATH`）；路径来自配置或运行参数。
3. 禁止在 `core/` 引入 Qt 或任何 GUI 依赖。
4. 禁止模块级实例化单例（`config = Config()`、`parser = IDFParser()`）。
5. 禁止 UI 直接操作文件系统或启动子进程。
6. 禁止 `time.sleep` 阻塞主线程等待结果。
7. 禁止 `shutil.rmtree` 删除历史运行目录。
8. 禁止凭记忆决定 EnergyPlus 字段/输出含义，必须查文档并标注。
9. 禁止引入未在 §1 列出的重型依赖（如 numpy 之外的科学栈、SQLAlchemy）。
10. 禁止在未读 AGENTS.md 与 ROADMAP.md 的情况下开始编码。
11. 禁止跳过测试直接交付；新增/修改公共 API 必须同步测试。
12. 禁止用 `# type: ignore` 无理由、无 PR 说明。

---

## 13. 参考资料（权威来源，决策时必须查阅）

> EnergyPlus 文档由 Big Ladder Software 托管：https://bigladdersoftware.com/epx/docs/
> 本项目对应 **Version 9.4**，文档根路径：`https://bigladdersoftware.com/epx/docs/9-4/`

| 编号 | 名称 | URL | 用途 |
|------|------|-----|------|
| R-1 | 文档总入口 | https://bigladdersoftware.com/epx/docs/ | 查找各版本入口 |
| R-2 | Input Output Reference | https://bigladdersoftware.com/epx/docs/9-4/input-output-reference/ | **所有 IDF 对象/字段定义的权威来源**；字段名、类型、单位、默认、选择、必填、引用关系 |
| R-3 | Auxiliary Programs | https://bigladdersoftware.com/epx/docs/9-4/auxiliary-programs/ | EPMacro、ExpandObjects、ReadVarsESO、convertESOMTR、CSVProc 等辅助程序行为 |
| R-4 | Output Details and Examples | https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/ | **所有输出文件格式**；尤其「Output File List」页 |
| R-4a | Output File List | https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/output-file-list.html | 输出文件总表（名称、描述、EP-Launch 命名） |
| R-4b | eplusout.sql | https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplusout-sql.html | SQLite 表结构（ReportData、ReportDataDictionary 等），**可视化首选数据源** |
| R-4c | eplusout.err | https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplusout-err.html | 错误文件格式，用于错误诊断与定位 |
| R-4d | eplustbl 汇总报告 | https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplustbl-lt-ext-gt.html | 表格汇总报告（Annual Building Utility Performance Summary 等） |
| R-4e | eplusout.rdd/mdd | https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplusout-rdd.html | 可用输出/计量变量列表，用于输出变量管理 |
| R-5 | Getting Started | https://bigladdersoftware.com/epx/docs/9-4/getting-started/ | 入门、EP-Launch 介绍、IDF Editor 介绍、文件扩展名、教程 |
| R-5a | IDF Editor 简介 | https://bigladdersoftware.com/epx/docs/9-4/getting-started/idf-editor-brief-introduction.html | 官方 IDF Editor 交互参考 |
| R-5b | EnergyPlus File Extensions | https://bigladdersoftware.com/epx/docs/9-4/getting-started/energyplus-file-extensions.html | 输入/输出文件扩展名总表 |
| R-6 | Engineering Reference | https://bigladdersoftware.com/epx/docs/9-4/engineering-reference/ | 计算原理（理解输出物理含义时查阅） |
| R-7 | EnergyPlus Essentials | https://bigladdersoftware.com/epx/docs/9-4/essentials/ | 概念入门 |
| R-8 | Tips and Tricks | https://bigladdersoftware.com/epx/docs/9-4/tips-and-tricks/ | 常见问题与最佳实践 |
| R-9 | 本地 EnergyPlus 安装 | `<energyplus_path>/Documentation/` | 随安装包附带的离线文档 |
| R-10 | 本地 IDD | `<energyplus_path>/Energy+.idd` | 字段元数据原始来源（解析对象） |
| R-11 | 本地 epJSON Schema | `<energyplus_path>/Energy+.schema.epJSON` | epJSON 输入格式 schema |
| R-12 | 官方 EP-Launch 源码 | https://github.com/NREL/EP-Launch | 官方跨平台启动器，参考其 workflow/utilities 分层与测试组织 |

### 查阅规则
- 任何关于"某字段是什么/有什么单位/可选值"的问题 → 查 R-2，必要时对照 R-10。
- 任何关于"某输出文件什么格式/怎么解析"的问题 → 查 R-4 对应子页。
- 任何关于"命令行参数行为"的问题 → 查 `energyplus --help` 与 R-3。
- 查阅后，在代码注释或 PR 描述中标注引用编号（如 `# 依据 R-4b: eplusout.sql 含 ReportData 表`）。

---

## 14. 开发流程（每个阶段执行步骤）

1. **读文档**：先读本 AGENTS.md 与 ROADMAP.md 当前阶段，再读相关 R-x 资料。
2. **设计**：在 ROADMAP.md 对应任务下写一行设计要点（改哪些模块、新哪些类），无需长篇。
3. **实现**：按分层写代码，同步写测试。
4. **自检**：跑 `ruff check . && mypy src && pytest -m "not e2e"`，全绿。
5. **对照验收**：逐条核对 §11。
6. **更新文档**：若改了用户可感知行为，同步 README；若改了架构/规范，同步 AGENTS.md。
7. **提交**：按 §11.4 规范提交，等待用户确认后再 push。

---

## 15. 当前代码已知问题（重构起点，详见 ROADMAP Phase 0）

- `src/config.py` 硬编码 `DEFAULT_EP_PATH` 绝对路径；模块级 `config = Config()` 单例。
- `src/idf_parser.py` 模块级 `parser = IDFParser()` 单例；序列化不保真（丢注释、重排对齐）。
- `src/idf_editor.py` 的 `_is_object_line()` 恒返回 `False`，对象类型名高亮实际失效。
- `src/main_window.py` 调用 `self._run_panel._start_run()`（跨层访问私有方法）。
- `src/run_panel.py` 直接 `from .config import config`（UI 直接依赖全局单例）。
- 无 IDD 解析，字段编辑无元数据（盲编辑）。
- 无结果解析与可视化（结果仅文本查看）。
- 无任何测试（`test/` 被 .gitignore 忽略）。
- 无 pyproject.toml，无 lint/类型检查配置。

> 这些是 Phase 0/1 必须解决的问题，新代码不得延续上述反模式。
