# EnergyPlus 输出文件说明与解析规范

> 本文档依据 EnergyPlus 官方文档 **Output Details and Examples**（R-4），对模拟运行产物 `data/runs/<run_id>/` 下输出文件的用途、数据格式及启动器的解析策略进行规范记录。

---

## 1. 输出文件清单与契约

运行结束后，单次运行目录标准产生的文件及启动器解析策略如下：

| 文件名 | 用途描述 | 核心内容 / 格式 | 启动器解析方式与去向 | 规范依据 |
|--------|----------|-----------------|----------------------|----------|
| `eplusout.err` | 模拟诊断日志 | 文本格式，记录 Warnings、Severe、Fatal 报错及可能发生问题的 IDF 行号 | 解析为 `ErrorRecord` 列表，在主工作区「错误」标签以表格呈现，支持定位对象 | R-4c |
| `eplusout.end` | 运行状态标志 | 单行简短摘要（成功/失败、警告数、运行时间） | 用于判定进程是否正常收尾 | R-4 |
| `eplusout.sql` | 结构化数据库 | SQLite 数据库，包含时序变量字典、环境周期、报表及全部数值 | **可视化首选数据源**。标准库 `sqlite3` 读取，驱动时序曲线交互绘图与导出 | R-4b |
| `eplustbl.xml` | 表格汇总报告 | XML 结构化数据，包含建筑冷热负荷、年能耗汇总等表格 | 解析为 `ReportTable` 集合，在主工作区「汇总报告」呈现，供交互筛选与绘图 | R-4d |
| `eplustbl.htm` | HTML 格式报告 | 由 `OutputControl:Table:Style` 生成的原始 HTML | 当缺失 XML 汇总时，作为降级数据源解析表格 | R-4d |
| `eplustbl.csv` | CSV 格式报告 | 逗号分隔的汇总表格 | 备选查看文件 | R-4d |
| `eplusout.rdd` | 可用输出变量 | IDF 语法格式，列出当前模型支持的所有变量（Output:Variable） | 解析为结构化列表，在主工作区「可用输出变量」中供搜索与一键添加 | R-4e |
| `eplusout.mdd` | 可用计量变量 | IDF 语法格式，列出可用计量表（Output:Meter） | 同上 | R-4e |
| `eplusout.eso` | 标准输出流 | 包含全部输出变量的时序流数据（复杂文本） | 优先使用 `eplusout.sql`，当通过 ReadVarsESO 转换后可生成 CSV | R-4 |
| `eplusout.mtr` | 计量输出流 | 包含仪表计量数据的时序流数据 | 同上 | R-4 |
| `eplusout.eio` | 一次性环境汇总 | 逗号分隔格式，记录建筑尺寸、材质构造、区域几何一次性摘要 | 原始文本查看 | R-4 |
| `eplusout.bnd` | 暖通分支节点连接 | 文本文件，记录 HVAC 节点连通关系 | 原始文本查看 | R-4 |
| `enhanced-report.html` | 增强离线报告 | 启动器生成的自包含单文件综合报告（含图表、时序和可搜索汇总） | 运行后自动生成或手动导出，可脱机分享 | - |
| `run.json` | 运行元数据归档 | 记录任务标识、引擎版本、实际命令、退出码、输入快照哈希及输出清单 | 持久化层索引，用于运行历史检索与复盘 | - |

---

### 运行输入与归档

- 每次运行独占 `data/runs/<run_id>/`。运行 ID 为一个目录名，已有目录、文件或符号链接占用名称时自动追加编号。单次任务另有独立的 `task_id`，即使同名实验从不同窗口发起也可区分。
- 运行工作目录是归档下的 `inputs/`。启动器复制实际使用的 IDF、EPW 和 IDD，并在运行副本中重写已识别的资源路径。引擎输出仍写入运行目录根部（R-3、R-9）。
- 支持 `Schedule:File`、`Schedule:File:Shading`、`Construction:WindowDataFile`、`Table:IndependentVariable` 和 `Table:Lookup` 的文件依赖。相对路径从原模型所在目录解析。依赖按独立名称归档，两个目录中的同名文件可并存（R-2、R-10）。
- 高级参数 `-w` 优先于所选 EPW，`-i` 优先于安装目录的 IDD。未指定天气时，如原模型目录存在 `in.epw` 则归档使用该文件。显式文件缺失、输出目录覆盖（`-d`）、未知参数，以及 EPMacro、ExternalInterface、PythonPlugin 和参数化预处理工作流会在准备阶段给出错误。用 `-r` 时，模型旁的自定义 `.rvi` 或 `.mvi` 也会提示暂不支持（R-2、R-3）。[EnergyPlus 9.4 命令行实现](https://github.com/NREL/EnergyPlus/blob/v9.4.0/src/EnergyPlus/CommandLineInterface.cc)
- `run.json` 的 `command_args` 是实际启动参数数组，首项为引擎可执行文件。`working_directory` 和 `output_directory` 记录实际工作及输出位置。`inputs` 列出各文件的角色、来源、相对归档路径和启动前的 SHA256。取消与启动失败也会记录终态。
- 重跑时，把 `inputs/` 复制到新的运行目录，在该副本中执行 `command_args`，使用 `engine_version` 对应的引擎安装。归档包含模型输入，重跑仍依赖对应的 EnergyPlus 安装及其辅助程序。

---

## 2. 结果可视化首选数据源设计

1. **时序曲线首选 `eplusout.sql`**：
   - 相比大体积且格式专有的 `.eso`，SQLite 数据库提供了索引和标准 SQL 查询能力；
   - 启动器在运行前默认勾选「生成分析数据」，在运行副本中注入 `Output:SQLite, SimpleAndTabular`，保证模拟输出完整的 SQLite 库；
   - 时序变量查询在独立工作线程中执行，暖机数据（Warmup）默认过滤，大型时序支持抽样绘制与完整 CSV 导出。

2. **汇总报告多级容错解析**：
   - 优先解析 `eplustbl.xml` 获取精确命名的表格与单元格；
   - 若模型仅输出了 HTML 格式，启动器内置 HTML 表格解析器自动提取表格；
   - 若表格文件缺失，启动器可从 `eplusout.sql` 的 `TabularDataWithStrings` 表中重构还原汇总表。
   - 柱状图保留单位并拒绝混合量纲。终端用能饼图仅接受年度建筑性能汇总中已知资源的同单位可加分项。总计用于校验，子分类表、负值、零总量会给出提示（R-2、R-4d）。

---

## 3. 增强 HTML 报告生成机制

- 勾选运行面板中的「运行结束后生成增强 HTML 报告」后，系统会在模拟完成时提取状态摘要、诊断记录、能耗概览柱状图、代表性时序曲线（SVG）和全部可折叠筛选的汇总表；
- **全内嵌自包含**：样式（CSS）、矢量图表（SVG）和轻量筛选脚本全内联写入单文件 `enhanced-report.html`，无需外链 CDN、无需本地网络服务器，双击即可在任意现代浏览器中浏览与交付分享。
