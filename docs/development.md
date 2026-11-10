# Neko-EP-Launcher 开发指南

> 本文档面向参与 **Neko-EP-Launcher** 研发与维护的开发者与 AI 助手，记录项目开发环境搭建、架构分层规则、质量门禁与调试工具等必要信息。
> 规范性准则统一以根目录 [AGENTS.md](../AGENTS.md) 为准。

---

## 1. 技术栈与环境搭建

| 类别 | 约束 / 版本 | 说明 |
|------|-------------|------|
| Python | >= 3.10 | 核心特性：模式匹配 `match`、`dataclass(slots=True)` 等 |
| GUI 框架 | PySide6 >= 6.4 | Qt for Python 原生桌面交互，**严禁混用 PyQt** |
| 绘图可视化 | matplotlib >= 3.7 | 嵌入 Qt 窗口控件（`backend_qtagg`） |
| 数据处理 | pandas >= 2.0 | 仅用于时序与表格解析，不得引入重量级复杂栈 |
| 模拟内核 | EnergyPlus 9.4.0 | 兼容 9.x，不在逻辑中硬编码绝对路径 |
| 代码检查 | ruff, mypy (严格) | 替代 flake8/black/isort，静态类型检查全通过 |
| 测试框架 | pytest, pytest-qt, pytest-cov | 单元测试、Qt 交互测试与覆盖率统计 |

### 环境初始化

```bash
git clone https://github.com/Chocola-X/Neko-EP-Launcher.git
cd Neko-EP-Launcher

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装运行与开发依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

---

## 2. 分层架构与依赖约束

代码必须严格遵守自上而下的分层单向依赖原则，**严禁逆向依赖与跨层调用**：

```
Neko-EP-Launcher/
├── main.py                         # 组装入口（QApplication 启动，<30 行）
├── pyproject.toml                  # 项目元数据与构建配置
├── requirements.txt                # 运行依赖
├── requirements-dev.txt            # 开发依赖（pytest/ruff/mypy）
├── config.example.json             # 初始配置模板
├── resources/                      # IDD 缓存与静态资源
├── tests/                          # 自动化测试镜像 src/ 结构
│   ├── unit/                       # core 纯逻辑单元测试（无 Qt 依赖）
│   ├── integration/                # 服务层与 UI 交互集成测试（pytest-qt）
│   └── fixtures/                   # 官方 IDF 样例与运行结果测试数据
└── src/
    ├── core/                       # 纯逻辑层：无 GUI 依赖、无 I/O 副作用
    │   ├── idf/                    # IDF 解析、保真序列化与文档模型
    │   ├── idd/                    # IDD 元数据驱动解析模型
    │   ├── results/                # 输出文件纯解析（err/sql/table/rdd）
    │   └── entities/               # 跨层共享数据类与枚举配置
    ├── services/                   # 业务服务层：编排 core，封装 QProcess 与 I/O
    │   ├── config_service.py       # 配置管理
    │   ├── idf_service.py          # IDF 解析/保存/对象增删编排
    │   ├── idd_service.py          # IDD 元数据缓存与检索
    │   ├── results_service.py      # 结果文件结构化解析编排
    │   ├── ep_runner.py            # EnergyPlus 进程管理（QProcess 非阻塞）
    │   └── run_manager.py          # 模拟运行准备、归档与元数据记录
    ├── persistence/                # 持久化层：读写磁盘配置与 runs 历史目录
    ├── ui/                         # 表现层：基于 PySide6，仅负责交互与渲染
    │   ├── main_window.py          # 主工作区与多窗口调度
    │   ├── editor/                 # IDF 源码高亮与滚动编辑
    │   ├── tree/                   # 对象树、右键菜单与属性表格编辑面板
    │   ├── results/                # 结果分析（错误、汇总、时序曲线、能耗图）
    │   ├── run/                    # 模拟运行配置、实时日志与历史记录
    │   └── theme.py                # 原生系统主题与调色板
    └── app.py                      # 依赖注入容器与多窗口生命周期管理根
```

### 依赖规则门禁
1. **`src/core/` 零 GUI 依赖**：严禁 `import PySide6`，严禁产生磁盘 I/O 或网络副作用。
2. **`src/ui/` 零 I/O 逻辑**：严禁在 UI 控件内直接调用 `subprocess`、`QProcess` 或 `open()` 写文件，必须统一由 `services/` 编排。
3. **禁止模块级单例**：应用组件均由 `app.py` 构造并注入。
4. **跨窗口通信基于系统剪贴板与事件信号**：对象与参数复制采用标准序列化字符串（IDF 代码与 JSON），实现各窗口松耦合交互。

---

## 3. 常用开发命令

### 代码检查与格式化
```bash
ruff check .           # 代码静态分析与 import 排序检查
mypy src               # 严格类型检查
```

### 运行自动化测试
```bash
# 运行全部单元与集成测试（推荐日常执行）
pytest -m "not e2e"

# 纯逻辑单元测试与覆盖率检查（要求 core >= 90%）
pytest tests/unit -q --cov=src/core --cov-fail-under=90

# 服务层集成测试与覆盖率检查（要求 services >= 70%）
pytest tests/integration -q --cov=src/services --cov-fail-under=70

# 本地完整模拟链端到端验证（需本地安装 EnergyPlus）
ENERGYPLUS_HOME=/path/to/EnergyPlus QT_QPA_PLATFORM=offscreen pytest tests/e2e -m e2e -q
```

---

## 4. 快速迭代与提交规范

> **阶段说明**：当前处于**快速开发迭代阶段**，允许为了架构优化与功能演进进行破坏性更改而**无需考虑兼容层**。

- **分支策略**：新功能与修复**直接在 `master` 分支**进行迭代开发与提交，不需要独立开分支。
- **提交信息格式**：`<类型>: <简述>`，类型必须属于 `{feat, fix, refactor, test, docs, chore, perf}` 之一。
  - 示例：`feat: 支持新建多程序窗口与跨窗口对象/参数相互复制`
  - 示例：`docs: 更新架构文档与使用说明`
- **提交纪律**：一个 commit 聚焦一个主题；严禁无意义的自动提交；未经明确授权不向远程仓库推送。

---

## 5. 调试与脚本工具

### 官方示例批量核查脚本
仓库提供了针对 EnergyPlus 官方 ExampleFiles 的静态与动态验证脚本：

```bash
# 静态校验全部官方 IDF
python -m scripts.audit_examples --energyplus-home /path/to/EnergyPlus --output-dir ./audit_results

# 静态校验并并行执行 30 个代表性模型的设计日模拟
python -m scripts.audit_examples --energyplus-home /path/to/EnergyPlus --output-dir ./audit_results --simulate --workers 4 --timeout 120
```

该脚本会生成逐文件的 JSON/CSV 校验记录、详细的中文审计报告及原始运行日志，便于回归分析与误报排查。
