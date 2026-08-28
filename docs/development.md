# 开发规范

本文档描述项目的代码风格、架构约束、测试规范与提交规范。

## 目录

- [项目结构](#项目结构)
- [架构约束](#架构约束)
- [代码风格](#代码风格)
- [测试规范](#测试规范)
- [提交规范](#提交规范)
- [打包构建](#打包构建)
- [发布流程](#发布流程)

---

## 项目结构

```
密码识别并自动解压缩/
├── run.py                          # 启动入口
├── config.json                     # 默认配置（Git 追踪）
├── config.local.json                # 用户配置（Git 忽略）
├── requirements.txt                 # 依赖
├── .gitignore
├── LICENSE
├── README.md
├── docs/                            # 开发文档
│   ├── architecture.md
│   ├── modules.md
│   ├── algorithms.md
│   ├── api.md
│   ├── development.md
│   └── faq.md
├── src/
│   └── archive_extractor/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py                   # QApplication 入口
│       ├── config.py                # 配置模型与持久化
│       ├── constants.py             # 全局常量
│       ├── core/                    # 核心层（无 Qt 依赖）
│       │   ├── scanner.py
│       │   ├── archive_info.py
│       │   ├── extractor.py
│       │   ├── verifier.py
│       │   ├── pipeline.py
│       │   ├── password_manager.py
│       │   ├── vault_git.py
│       │   └── worker.py            # QThread（唯一含 Qt 的 core 文件）
│       ├── models/                  # 数据模型（dataclass）
│       │   ├── archive_info.py
│       │   ├── result.py
│       │   └── vault_entry.py
│       ├── ui/                      # UI 层（PyQt6）
│       │   ├── main_window.py
│       │   ├── theme.py
│       │   ├── qt_compat.py          # 跨版本兼容层
│       │   └── widgets/
│       │       ├── folder_picker.py
│       │       ├── progress_panel.py
│       │       ├── settings_dialog.py
│       │       ├── status_panel.py
│       │       └── vault_dialog.py
│       └── utils/                    # 工具层
│           ├── fs.py
│           ├── logger.py
│           └── seven_zip.py
└── tests/                            # 测试
    ├── conftest.py
    ├── test_archive_info.py
    ├── test_password_manager.py
    ├── test_pipeline.py
    ├── test_scanner.py
    └── test_verifier.py
```

## 架构约束

### 分层依赖规则

```
config / constants / utils
        ▲
   models (dataclass)
        ▲
   core (scanner / archive_info / extractor / verifier / pipeline / password_manager)
        ▲
   worker (QThread) —— 唯一连接 core 与 ui 的桥梁
        ▲
   ui (theme / main_window / widgets)
```

**关键约束**：

1. **核心层无 Qt 依赖**：`src/archive_extractor/core/` 下除 `worker.py` 外均**不导入** `PyQt6`。这保证核心逻辑可用 pytest 直接测试，无需 GUI 环境。
2. **数据模型无副作用**：`models/` 仅为 dataclass，不含 I/O 或业务逻辑。
3. **单向依赖**：上层可依赖下层，下层不可反向依赖上层。`core` 不依赖 `ui`。
4. **`worker.py` 桥梁**：唯一同时引用 `core` 与 `PyQt6` 的文件，通过 `PipelineCallbacks` 协议解耦。

### 线程模型

- **主线程（GUI 线程）**：渲染界面、响应交互、弹出对话框。**从不直接触碰工作线程状态**。
- **工作线程（`ExtractionWorker(QThread)`）**：执行完整批次，通过 `pyqtSignal` 上报状态，**从不操作控件**。
- **删除确认桥接**：工作线程发射 `confirmation_requested` 信号 → 主线程弹 `QMessageBox.question` → 调用 `worker.set_delete_decision()` → 工作线程轮询返回。避免死锁。
- **取消**：`requestInterruption()` 在压缩包之间检查；单个 7z 子进程会运行完毕（不中途 kill，避免半解压状态）。

### 7z 调用约束

所有 7z 调用**必须**经过 `utils.seven_zip.run_7z()`，该函数：
- 永远传 `-p`（空或值）和 `-y`，避免挂起等待输入
- 设置 `stdin=DEVNULL`
- Windows 上设置 `creationflags=CREATE_NO_WINDOW` 隐藏控制台窗口
- 返回 `SevenZipResult`，提供 `ok` / `wrong_password` / `corrupt` 属性（后两者互斥）

### 配置持久化约束

- `config.json`：Git 追踪，**仅含默认值**，不含用户机器路径或敏感信息
- `config.local.json`：Git 忽略，存放运行时用户选择（输出目录、窗口几何等）
- 密码库 `~/.archive_password_vault/passwords.json`：独立 Git 仓库，与项目仓库完全隔离

---

## 代码风格

### Python 风格

- 遵循 [PEP 8](https://peps.python.org/pep-0008/)
- 使用 `from __future__ import annotations` 启用延迟注解求值
- 类型注解：所有公开函数与方法**必须**有类型注解
- 行长度上限：100 字符
- 使用 `pathlib.Path` 而非 `os.path` 字符串拼接
- 使用 dataclass 定义数据模型

### 命名规范

| 类型 | 风格 | 示例 |
|---|---|---|
| 模块/文件 | `snake_case` | `password_manager.py` |
| 类 | `PascalCase` | `ArchivePipeline` |
| 函数/方法 | `snake_case` | `iter_passwords_for` |
| 常量 | `UPPER_SNAKE` | `SEVEN_ZIP_DEFAULT` |
| 私有 | 前缀 `_` | `_parse_slt` |

### 文档字符串

- 公开类与函数使用三引号 docstring
- 复杂逻辑（如 SLT 解析、CRC 校验）在 docstring 或注释中说明算法

### 异常处理

- 核心层管线（`pipeline.process`）捕获所有异常，转为 `STATUS_FAILED` 结果，**不上抛**
- 密码库 Git 失败仅记日志告警，**不阻塞**写入流程
- 容忍缺失/多余的配置键（`Settings.from_dict` 过滤未知键）

### 安全实践

- 删除操作使用两步令牌（`prepare_delete` → `delete_password`），令牌仅内存存储
- 令牌比较使用 `secrets.compare_digest`（恒定时间比较，防时序攻击）
- 密码库读写通过 `threading.Lock` 串行化
- 文件写入使用原子操作（`tmp` + `os.replace`）

---

## 测试规范

### 测试框架

使用 [pytest](https://docs.pytest.org/)。测试文件位于 `tests/`，命名 `test_*.py`。

### 测试夹具

`tests/conftest.py` 提供共享夹具：
- `seven_zip`：指向系统 7z.exe
- `tmp_archives`：临时创建的测试压缩包（含加密/未加密）

### 运行测试

```bash
# 运行全部测试
pytest

# 静默模式
pytest -q

# 显示详细输出
pytest -v

# 运行单个测试文件
pytest tests/test_pipeline.py
```

### 测试要求

- 核心层模块**必须**有对应测试
- 新功能需附带测试用例
- 测试不依赖 GUI 环境（核心层无 Qt 依赖）
- 测试不依赖外部网络

---

## 提交规范

### 约定式提交

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

```
<type>: <subject>

<body>
```

**常用 type**：

| type | 说明 | 示例 |
|---|---|---|
| `feat` | 新功能 | `feat: add bulk password import` |
| `fix` | 修复 | `fix: resolve PyQt6 enum compatibility on Python 3.14` |
| `docs` | 文档 | `docs: add API reference` |
| `refactor` | 重构 | `refactor: extract common 7z wrapper` |
| `test` | 测试 | `test: add two-step delete token tests` |
| `chore` | 构建/工具 | `chore: update dependencies` |

### 分支策略

- `main`：稳定分支，通过测试的可发布代码
- `feature/*`：功能开发分支
- `fix/*`：修复分支

### Pull Request 流程

1. Fork 仓库并创建功能分支
2. 确保通过全部测试：`pytest -q`
3. 提交遵循约定式提交规范
4. PR 描述说明变更内容与动机
5. 代码审查通过后合并

---

## 打包构建

### 使用 PyInstaller 打包 EXE

```bash
# 安装打包工具
pip install pyinstaller

# 打包（单文件模式，含 7z.exe）
pyinstaller --noconfirm --onefile --windowed ^
  --name "ArchiveAutoExtractor" ^
  --add-data "src/archive_extractor;archive_extractor" ^
  --paths src ^
  --hidden-import PyQt6 ^
  run.py
```

打包产物位于 `dist/ArchiveAutoExtractor.exe`。

### 构建注意事项

- 使用 `--windowed` 隐藏控制台窗口
- 7z.exe 需用户自行安装（或打包时附加）
- PyQt6 插件（平台、图像格式）需正确包含
- 首次打包建议在干净的虚拟环境中进行

---

## 发布流程

1. **更新版本号**：修改 `constants.py` 中的 `APP_VERSION`
2. **运行测试**：`pytest -q` 确保全部通过
3. **打包 EXE**：按上述 PyInstaller 流程打包
4. **测试 EXE**：在干净环境验证启动与核心功能
5. **创建 Git 标签**：`git tag v1.0.0`
6. **创建 GitHub Release**：上传 EXE 与 Release Notes
7. **更新文档**：如有新功能，更新 README 与 docs
