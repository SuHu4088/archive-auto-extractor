# 密码识别并自动解压缩 (Archive Auto-Extractor)

一个带深色模式 GUI 的桌面应用：选择文件夹后递归扫描压缩包（ZIP / RAR / 7Z），自动解压并做 CRC 完整性校验；受密码保护的压缩包默认跳过，待用户启用密码库后再尝试解密；密码库独立存放于项目外部并自动 Git 追踪变更。

> 完整文档见 [`docs/`](docs/)。

## 功能特性

- 📁 **递归扫描**：选择文件夹后自动遍历所有子目录，识别 ZIP / RAR / 7Z 压缩包
- 🔓 **密码识别**：自动检测受密码保护的压缩包，默认跳过，避免无谓尝试
- 🔑 **密码库**：启用后从密码库逐一尝试解密；全部失败时将压缩包移入 `password_protected_unsolved/` 并提示「已尝试所有密码仍无法打开」
- ✅ **CRC 校验**：解压后比对存储 CRC 与解压文件 CRC（`7z l -slt` + `zlib.crc32` + `7z t` 三重校验），确保完整性
- 🗑️ **安全删除**：仅在 CRC 校验通过后才允许删除原压缩包，提供确认对话框 + 设置开关
- 📂 **同名子文件夹**：解压内容放入与原压缩包同名的子文件夹，避免文件混淆
- 🎨 **深色主题**：高对比度深色界面，状态/进度实时可见
- 📜 **状态实时提醒**：当前文件路径、操作阶段（扫描/解压/校验）、进度、成功/失败全程可见
- 🔐 **密码库 Git 追踪**：密码库存放于项目外，每次增删改查自动 Git 提交，变更可追溯可回滚

## 环境要求

- **Windows 10/11**（在其他平台需调整 7z 路径）
- **Python 3.10+**（开发使用 3.12.8）
- **7-Zip** 命令行工具（`7z.exe`）。默认路径 `D:\hardware\7-Zip\7z.exe`，可在设置中修改
- **Git**（用于项目初始化与密码库变更追踪）

## 安装

```bash
# 克隆 / 进入项目目录
cd "d:\Open_source_project\密码识别并自动解压缩"

# (推荐) 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

> PyQt6 在本机已预装。如需在新环境安装：`pip install PyQt6`。

## 使用说明

```bash
python run.py
```

启动后：

1. **选择源文件夹**：点击「选择文件夹」按钮，选定待处理的文件夹
2. **配置解压路径**：在「设置」中指定解压输出目录（默认与源文件夹相同）
3. **（可选）启用密码库**：在「设置」中开启密码模块，并通过「密码库」对话框添加密码
4. **开始**：点击「开始」按钮，程序递归扫描并自动处理压缩包
5. **观察状态**：底部状态面板与进度条实时显示处理过程
6. **删除确认**：若开启「成功后删除原文件」，CRC 校验通过后会弹出确认对话框

## 配置项说明

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `seven_zip_path` | `D:\hardware\7-Zip\7z.exe` | 7z.exe 路径 |
| `extraction_output_root` | `""` (空=源文件夹) | 解压输出根目录 |
| `create_same_name_subfolder` | `true` | 为每个压缩包创建同名子文件夹 |
| `delete_original_after_success` | `false` | CRC 校验通过后是否删除原文件 |
| `confirm_before_delete` | `true` | 删除前是否弹出确认对话框 |
| `password_module_enabled` | `false` | 是否启用密码库尝试解密 |
| `move_unsolved_to_subfolder` | `true` | 全部密码失败后移入 unsolved 子文件夹 |
| `unsolved_subfolder_name` | `password_protected_unsolved` | 未解决压缩包子文件夹名 |

## 常见问题

详见 [docs/faq.md](docs/faq.md)。

## 开发文档

- [架构设计](docs/architecture.md)
- [模块说明](docs/modules.md)
- [核心算法](docs/algorithms.md)
- [常见问题](docs/faq.md)

## 许可

本项目仅供学习与内部使用。
