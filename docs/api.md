# API 文档

本文档描述核心层（`src/archive_extractor/core/`）的公开接口。核心层**不依赖 PyQt6**（`worker.py` 除外），可用 pytest 直接测试。

## 目录

- [配置 config](#配置-config)
- [常量 constants](#常量-constants)
- [7z 封装 utils.seven_zip](#7z-封装-utilsseven_zip)
- [文件系统工具 utils.fs](#文件系统工具-utilsfs)
- [扫描器 core.scanner](#扫描器-corescanner)
- [压缩包检测 core.archive_info](#压缩包检测-corearchive_info)
- [解压器 core.extractor](#解压器-coreextractor)
- [校验器 core.verifier](#校验器-coreverifier)
- [密码库 core.password_manager](#密码库-corepassword_manager)
- [密码库 Git core.vault_git](#密码库-git-corevault_git)
- [管线 core.pipeline](#管线-corepipeline)
- [数据模型 models](#数据模型-models)

---

## 配置 config

模块路径：`src/archive_extractor/config.py`

### `Settings`

与 `config.json` 一一对应的强类型 dataclass。

| 属性 | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `version` | `int` | `1` | 配置版本号 |
| `seven_zip_path` | `str` | `SEVEN_ZIP_DEFAULT` | 7z.exe 路径 |
| `extraction_output_root` | `str` | `""` | 解压输出根目录（空=源文件夹） |
| `scan_extensions` | `list[str]` | `SUPPORTED_EXT` | 扫描的扩展名 |
| `create_same_name_subfolder` | `bool` | `True` | 创建同名子文件夹 |
| `delete_original_after_success` | `bool` | `False` | 成功后删除原文件 |
| `confirm_before_delete` | `bool` | `True` | 删除前确认 |
| `password_module_enabled` | `bool` | `False` | 启用密码库 |
| `vault_path` | `str` | `"~/.archive_password_vault"` | 密码库目录 |
| `move_unsolved_to_subfolder` | `bool` | `True` | 移动未解决压缩包 |
| `unsolved_subfolder_name` | `str` | `"password_protected_unsolved"` | 未解决子文件夹名 |
| `unsolved_location` | `str` | `"output_root"` | 未解决位置（`output_root` / `beside_archive`） |
| `max_threads` | `int` | `1` | 最大线程数 |
| `theme` | `str` | `"dark"` | 主题 |
| `log_level` | `str` | `"INFO"` | 日志级别 |
| `ui` | `UISettings` | — | UI 状态（窗口几何） |

**路径属性（自动展开 `~` 与环境变量）：**

| 属性 | 返回类型 | 说明 |
|---|---|---|
| `settings.seven_zip` | `Path` | 7z.exe 解析后路径 |
| `settings.output_root` | `Path` | 输出根目录（空时返回空 Path） |
| `settings.vault_dir` | `Path` | 密码库目录 |

### `load() -> Settings`

读取 `config.json`，叠加 `config.local.json` 覆盖。缺失键回退默认值；文件不存在时写入默认值。

### `save(settings: Settings, local: bool = False) -> None`

原子写入（`tmp` + `os.replace`）。`local=True` 写入 `config.local.json`（git-ignored）。

### `validate(settings: Settings) -> list[str]`

返回人类可读的校验问题列表（空列表表示无问题）。

---

## 常量 constants

模块路径：`src/archive_extractor/constants.py`

| 常量 | 值 | 说明 |
|---|---|---|
| `APP_NAME` | `"Archive Auto-Extractor"` | 应用名称 |
| `APP_VERSION` | `"1.0.0"` | 应用版本 |
| `SEVEN_ZIP_DEFAULT` | `r"C:\Program Files\7-Zip\7z.exe"` | 7z 默认路径 |
| `VAULT_DIRNAME` | `".archive_password_vault"` | 密码库目录名 |
| `VAULT_FILENAME` | `"passwords.json"` | 密码库文件名 |
| `UNSOLVED_SUBFOLDER` | `"password_protected_unsolved"` | 未解决子文件夹名 |
| `SUPPORTED_EXT` | `(".zip", ".rar", ".7z")` | 支持的扩展名 |
| `EXIT_OK` | `0` | 7z 成功退出码 |
| `EXIT_WARNING` | `1` | 7z 警告退出码 |
| `EXIT_FATAL` | `2` | 7z 致命错误退出码 |
| `EXIT_CMDLINE_ERROR` | `7` | 7z 命令行错误退出码 |
| `EXIT_WRONG_PASSWORD` | `255` | 7z 密码错误退出码 |
| `STATUS_OK` | `"ok"` | 状态：成功 |
| `STATUS_SKIPPED` | `"skipped"` | 状态：跳过 |
| `STATUS_FAILED` | `"failed"` | 状态：失败 |
| `STATUS_UNSOLVED` | `"unsolved"` | 状态：未解决 |
| `STAGE_SCAN` | `"scan"` | 阶段：扫描 |
| `STAGE_DETECT` | `"detect"` | 阶段：检测 |
| `STAGE_EXTRACT` | `"extract"` | 阶段：解压 |
| `STAGE_VERIFY` | `"verify"` | 阶段：校验 |
| `STAGE_FINALIZE` | `"finalize"` | 阶段：收尾 |

---

## 7z 封装 utils.seven_zip

模块路径：`src/archive_extractor/utils/seven_zip.py`

### `run_7z(seven_zip, archive, args, password=None, timeout=None) -> SevenZipResult`

**唯一的 7z 调用入口**。永远传 `-p`（空或值）、`-y`、`stdin=DEVNULL`、`creationflags=CREATE_NO_WINDOW`，防止 7z 挂起等待输入。

| 参数 | 类型 | 说明 |
|---|---|---|
| `seven_zip` | `Path` | 7z.exe 路径 |
| `archive` | `Path` | 压缩包路径 |
| `args` | `list[str]` | 操作参数（不含密码/yes 标志），如 `["x", "-odest"]` |
| `password` | `str \| None` | 密码；`None` 表示无密码（仍传 `-p` 空值） |
| `timeout` | `int \| None` | 超时秒数 |

### `SevenZipResult`

| 属性 | 类型 | 说明 |
|---|---|---|
| `returncode` | `int` | 7z 退出码 |
| `stdout` | `str` | 标准输出 |
| `stderr` | `str` | 标准错误 |

| 属性 | 类型 | 说明 |
|---|---|---|
| `.ok` | `bool` | 退出码 == 0 |
| `.wrong_password` | `bool` | 密码错误（退出码 255 或 2 + stderr 含 `Wrong password`/`Cannot open encrypted`） |
| `.corrupt` | `bool` | 压缩包损坏（与 `wrong_password` **互斥**） |

### `SevenZipError(RuntimeError)`

7z 失败时抛出。属性：`returncode`、`stderr`、`command`。

---

## 文件系统工具 utils.fs

模块路径：`src/archive_extractor/utils/fs.py`

| 函数 | 签名 | 说明 |
|---|---|---|
| `ensure_dir` | `(path: Path) -> Path` | 确保目录存在 |
| `same_name_subfolder` | `(output_root: Path, archive: Path) -> Path` | 返回 `output_root / archive.stem` |
| `safe_move` | `(src: Path, dest_dir: Path) -> Path` | 移动文件，命名冲突追加数字后缀 |
| `safe_delete` | `(path: Path) -> bool` | 删除文件（优先送回收站，回退 `unlink`） |
| `is_hidden` | `(path: Path) -> bool` | 判断隐藏/系统文件 |

---

## 扫描器 core.scanner

模块路径：`src/archive_extractor/core/scanner.py`

### `scan(root, output_root=None, extensions=SUPPORTED_EXT, skip_hidden=True) -> Iterator[Path]`

基于 `os.walk` 的生成器，剪枝 `output_root` 与 `password_protected_unsolved`，按目录排序保证确定性。

| 参数 | 类型 | 说明 |
|---|---|---|
| `root` | `Path` | 扫描根目录 |
| `output_root` | `Path \| None` | 解压输出根（被剪枝，避免重扫） |
| `extensions` | `tuple[str, ...]` | 匹配的扩展名（大小写不敏感） |
| `skip_hidden` | `bool` | 跳过隐藏/系统文件 |

**返回**：按目录排序的压缩包路径迭代器。

---

## 压缩包检测 core.archive_info

模块路径：`src/archive_extractor/core/archive_info.py`

### `detect(seven_zip, archive, password=None) -> ArchiveInfo`

调用 `7z l -slt -p""`，解析输出判断格式 / 加密状态 / manifest。

### `list_with_password(seven_zip, archive, password) -> ArchiveInfo`

用已知密码重新列出头部加密压缩包的 manifest。

---

## 解压器 core.extractor

模块路径：`src/archive_extractor/core/extractor.py`

### `extract(seven_zip, archive, dest, password=None) -> ExtractionResult`

调用 `7z x -o<dest> -p<pw> -y`。拒绝覆盖非空 `dest`，返回解压出的文件列表。

---

## 校验器 core.verifier

模块路径：`src/archive_extractor/core/verifier.py`

### `verify(seven_zip, archive, dest, password=None, info=None) -> VerifyResult`

**三重校验**——manifest CRC 比对、文件一致性（数量/路径/大小）、`7z t` 交叉校验。四项全过才算 `ok=True`。

### `compute_extracted(dest) -> list[tuple[str, int, str]]`

递归计算 `dest` 下所有文件的 `(relative_path, size, crc32_hex)`。

---

## 密码库 core.password_manager

模块路径：`src/archive_extractor/core/password_manager.py`

### `PasswordVault`

**密码库文件的唯一访问点**。线程安全（`threading.Lock`），Git 追踪。

| 方法 | 签名 | 说明 |
|---|---|---|
| `open` | `() -> None` | 初始化仓库并提交 session 开启标记 |
| `close` | `(stats: dict \| None = None) -> None` | 提交 session 关闭标记（含使用统计） |
| `list_entries` | `(enabled_only=False) -> list[VaultEntry]` | 返回条目副本 |
| `iter_passwords_for` | `(archive_name) -> Iterator[tuple[VaultEntry, str]]` | 按优先级排序的密码迭代器 |
| `add_password` | `(value, label="", notes="") -> VaultEntry` | 添加密码 |
| `bulk_add_passwords` | `(passwords, label_prefix="", skip_duplicates=True) -> tuple[int, int]` | 批量添加（返回 added, skipped） |
| `update_password` | `(entry_id, value=None, label=None) -> VaultEntry \| None` | 更新密码 |
| `set_enabled` | `(entry_id, enabled) -> bool` | 启用/禁用 |
| `prepare_delete` | `(entry_id) -> str \| None` | 返回一次性删除令牌 |
| `delete_password` | `(entry_id, token) -> bool` | 验证令牌后删除 |
| `record_success` | `(entry_id, archive_name) -> None` | 记录成功（use_count+1，触发 Git 提交） |
| `record_failure_all` | `(archive_name) -> None` | 记录全部失败 |
| `commit_log` | `(limit=20) -> list[str]` | 返回最近 Git 提交主题 |

**密码排序**（`iter_passwords_for`）：
1. 仅启用条目（`enabled=True`）
2. `use_count` 降序（曾成功过的优先）
3. `last_used` 降序（最近成功的优先）
4. `label` 升序（确定性兜底）

**两步删除**：`prepare_delete` 返回临时令牌（仅内存），`delete_password` 用 `secrets.compare_digest` 验证。错误令牌不消耗令牌，可重试。

---

## 密码库 Git core.vault_git

模块路径：`src/archive_extractor/core/vault_git.py`

### `VaultGit`

| 方法 | 签名 | 说明 |
|---|---|---|
| `ensure_repo` | `() -> None` | 首次 `git init` + 设置 identity + 种子文件 + 初始提交 |
| `commit` | `(message, allow_empty=False) -> bool` | `git add` 后提交，无变更返回 False |
| `log` | `(limit=20) -> list[str]` | 返回最近提交主题 |

Git 失败仅记日志告警，**不阻塞**密码库写入与解压流程。

---

## 管线 core.pipeline

模块路径：`src/archive_extractor/core/pipeline.py`

### `PipelineCallbacks`（Protocol）

进度回调协议，由工作线程实现：

| 方法 | 签名 | 说明 |
|---|---|---|
| `on_stage` | `(archive, stage, detail) -> None` | 阶段变更通知 |
| `on_password_try` | `(archive, idx, total) -> None` | 密码尝试通知 |
| `on_result` | `(result: ArchiveResult) -> None` | 结果通知 |
| `confirm_delete` | `(archive) -> bool` | 删除确认（阻塞等待） |

### `ArchivePipeline`

| 方法 | 签名 | 说明 |
|---|---|---|
| `__init__` | `(settings, vault \| None)` | 构造管线 |
| `process` | `(archive, callbacks) -> ArchiveResult` | 处理单个压缩包（纯状态机） |

**状态机阶段**：DETECT → DECIDE → EXTRACT → VERIFY → FINALIZE

任何异常都不上抛，转为 `STATUS_FAILED` 结果。

### `PipelineStats`

批次统计计数器：`ok` / `failed` / `skipped` / `unsolved`。

---

## 数据模型 models

### `models.archive_info`

| 类 | 字段 | 说明 |
|---|---|---|
| `ManifestEntry` | `path, size, crc` | 压缩包内单个文件 |
| `ArchiveInfo` | `format, is_password_protected, header_encrypted, manifest` | 检测结果 |

### `models.result`

| 类 | 字段 | 说明 |
|---|---|---|
| `ExtractionResult` | `ok, dest, extracted_files, error` | 解压结果 |
| `VerifyResult` | `ok, file_count_match, missing, extra, size/crc mismatches, test_exit_code, detail` | 校验结果 |
| `ArchiveResult` | `path, status, message, extracted_count, password_used` | 单压缩包最终结果 |

### `models.vault_entry`

| 类 | 字段 | 说明 |
|---|---|---|
| `VaultEntry` | `id, value, label, enabled, use_count, created_at, last_used, notes` | 单条密码记录 |

| 方法 | 说明 |
|---|---|
| `VaultEntry.new(value, label, notes)` | 工厂：生成 uuid + 时间戳 |
| `VaultEntry.mark_used()` | 更新使用计数与最后使用时间 |
| `VaultEntry.from_dict(d)` | 从字典构造 |
| `VaultEntry.to_dict()` | 序列化为字典 |
