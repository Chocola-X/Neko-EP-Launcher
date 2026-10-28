# 回归测试样本

本目录中的 IDF 文件来自本机官方 EnergyPlus 9.4 安装包的 `ExampleFiles/`，用于解析、注释保真和编辑往返测试。其中包含两个遮阳模型。

`test_run_001/` 是 `1ZoneUncontrolled.idf` 的真实运行样本，包含天气输入、SQLite、XML 汇总、变量字典和诊断输出，用于离线结果解析、绘图及增强报告测试。保留这组数据是为了让主要回归测试不需要启动 EnergyPlus。

`eplustbl-html-only.htm` 摘自官方 `1ZoneUncontrolled_DDChanges.idf` 的本地 9.4 运行报告，保留前两张完整数据表，用于缺少 SQL/XML 时的 HTML 汇总回退测试。

这些文件是有意纳入版本控制的测试资产；新的本地模拟和导出报告应放在已忽略的项目 `data/` 目录。第三方示例及输出数据保留其原有来源信息，项目 LICENSE 不改变第三方资产原有的许可。
