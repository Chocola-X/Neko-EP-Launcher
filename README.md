# EnergyPlus 图形化启动器

基于 PySide6 开发的 EnergyPlus 配置编辑与运行工具，适用于 KDE 桌面环境。

## 功能特性

- **IDF 文件编辑**：带语法高亮、行号显示的代码编辑器
- **对象树形结构**：按类型分组浏览所有 IDF 对象
- **字段表格编辑**：选中对象后通过表格编辑字段值
- **EnergyPlus 运行**：配置运行参数，一键启动模拟，实时显示日志
- **结果文件查看**：运行完成后查看所有输出文件（.csv、.err、.eso 等）
- **路径设置**：可配置 EnergyPlus 安装路径、天气文件目录
- **最近文件**：记录最近打开的 IDF 文件
- **主题切换**：支持 system/light/dark/fusion 主题

## 项目结构

```
EnergyPlus-Laucher/
├── main.py                    # 程序入口
├── requirements.txt           # 依赖
├── config.json                # 配置文件（自动生成）
├── data/                      # 数据目录
│   └── runs/                  # 每次运行的子目录（按运行ID命名）
├── src/
│   ├── config.py              # 配置管理
│   ├── idf_parser.py          # IDF 文件解析器
│   ├── idf_editor.py          # IDF 编辑器（语法高亮）
│   ├── idf_tree.py            # 对象树形视图 + 字段编辑面板
│   ├── settings_dialog.py     # 设置对话框
│   ├── ep_runner.py           # EnergyPlus 运行器
│   ├── run_panel.py           # 运行面板
│   └── main_window.py         # 主窗口
└── resources/
```

## 安装与运行

### 依赖

```bash
pip install -r requirements.txt
```

### 启动

```bash
python main.py
```

## 使用说明

### 1. 首次使用配置

1. 启动后点击 **工具 → 设置**
2. 在"运行"标签页确认 EnergyPlus 目录正确：
   `/run/media/chocola/DATA/Building_energy-saving_shading/EnergyPlus-9.4.0-998c4b761e-Linux-Ubuntu18.04-x86_64`
3. 在"路径"标签页设置天气文件目录（可点击"使用 EnergyPlus 默认天气目录"）
4. 点击"确定"保存设置

### 2. 编辑 IDF 文件

- **文件 → 打开**：打开现有 IDF 文件
- **文件 → 打开示例**：从 EnergyPlus 示例库打开
- 左侧对象树：按类型分组浏览，单击选中对象
- 字段编辑面板：选中对象后显示字段表格，可直接编辑值
- 中间编辑器：文本编辑，带语法高亮和行号
- **编辑 → 从文本同步到树**：将编辑器文本重新解析到对象树

### 3. 运行模拟

1. 在底部"运行面板"确认 IDF 文件路径
2. 选择天气文件（从下拉列表或浏览）
3. 可选：设置运行 ID 和附加参数
4. 点击"运行"按钮，或按 **F5**
5. 在"运行日志"标签页查看实时输出
6. 运行完成后在"结果文件"标签页查看输出

### 4. 结果保存

所有运行结果保存在 `data/runs/<运行ID>/` 目录下，包含：
- 输入的 IDF 和天气文件副本
- EnergyPlus 输出文件（eplusout.*、eplustbl.*）
- 完整的运行日志

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| Ctrl+N | 新建文件 |
| Ctrl+O | 打开文件 |
| Ctrl+S | 保存文件 |
| Ctrl+Shift+S | 另存为 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+F | 查找 |
| F5 | 运行 EnergyPlus |
| Ctrl+Q | 退出 |

## 技术栈

- Python 3.12
- PySide6 6.11 (Qt for Python)
- EnergyPlus 9.4.0

## 开发者

华为云码道(CodeArts)代码智能体
