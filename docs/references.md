# EnergyPlus 官方参考资料与规范依据

> 本项目所有关于 EnergyPlus 计算引擎行为、字段定义、输出文件格式与辅助程序的逻辑，均严格依据官方文档，严禁凭空臆想。
> 本项目当前主要对应 **EnergyPlus Version 9.4**。

---

## 1. 核心参考文档索引

官方文档由 Big Ladder Software 托管，根地址：https://bigladdersoftware.com/epx/docs/9-4/

| 编号 | 文档名称 | 官方链接 | 在本项目中的用途 |
|------|----------|----------|------------------|
| **R-1** | 文档总索引 | [Documentation Index](https://bigladdersoftware.com/epx/docs/) | 检索各版本 EnergyPlus 技术手册入口 |
| **R-2** | Input Output Reference | [Input Output Reference](https://bigladdersoftware.com/epx/docs/9-4/input-output-reference/) | **所有 IDF 对象与字段定义的权威来源**。包括字段名、类型、单位、默认值、必填项与对象间引用关系 |
| **R-3** | Auxiliary Programs | [Auxiliary Programs](https://bigladdersoftware.com/epx/docs/9-4/auxiliary-programs/) | 辅助程序规范：EPMacro、ExpandObjects、ReadVarsESO、convertESOMTR 等行为与参数 |
| **R-4** | Output Details and Examples | [Output Details and Examples](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/) | **所有输出文件格式的规范标准** |
| **R-4a** | Output File List | [Output File List](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/output-file-list.html) | 输出文件总表（标准名称、用途说明与扩展名） |
| **R-4b** | eplusout.sql | [eplusout.sql](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplusout-sql.html) | SQLite 表结构（ReportData、ReportDataDictionary、TabularData 等），可视化首选数据源 |
| **R-4c** | eplusout.err | [eplusout.err](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplusout-err.html) | 错误/警告文件日志格式，用于诊断解析与对象定位 |
| **R-4d** | eplustbl 汇总报告 | [eplustbl<ext>](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplustbl-lt-ext-gt.html) | 表格汇总报告结构与内容定义 |
| **R-4e** | eplusout.rdd/mdd | [eplusout.rdd/mdd](https://bigladdersoftware.com/epx/docs/9-4/output-details-and-examples/eplusout-rdd.html) | 可用输出变量与可用仪表计量字典格式 |
| **R-5** | Getting Started | [Getting Started](https://bigladdersoftware.com/epx/docs/9-4/getting-started/) | 入门指引、文件扩展名列表与 IDF Editor 交互逻辑参考 |

---

## 2. 本地元数据资源

- **IDD 文件**：位于 `<energyplus_installation_dir>/Energy+.idd`。启动器启动时解析该文件，生成包含字段类型、开闭区间、引用关系及选项列表的元数据字典，并持久化缓存至 `resources/idd_cache.json`。
- **epJSON Schema**：位于 `<energyplus_installation_dir>/Energy+.schema.epJSON`。用于校验与模型转换标准。

---

## 3. 官方参考实现

- **EP-Launch 源码**：[https://github.com/NREL/EP-Launch](https://github.com/NREL/EP-Launch)
  本项目在工作流分层、输出管理与测试设计上参考了 NREL 官方启动器的组织思想。
