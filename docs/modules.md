# 模块说明

## 入口

### `run.py`
启动入口。将 `src/` 加入 `sys.path` 后调用 `archive_extractor.app.main()`。

### `archive_extractor/app.py`
创建 `QApplication`，应用深色调色板与 QSS 样式表，实例化并显示 `MainWindow`。

## 配置与常量

### `constants.py`
集中存放常量：`APP_NAME`、`SEVEN_ZIP_DEFAULT`、`VAULT_DIRNAME`、`UNSOLVED_SUBFOLDER`、`SUPPORTED_EXT`、7z 返回码常量、状态/阶段字符串。

### `config.py`
- `Settings` / `UISettings` dataclass：与 `config.json` schema 一一对应。
- `load()`：读取 `config.json`，叠加 `config.local.json` 覆盖，缺失键回退默认值。
- `save(settings, local=False)`：原子写入（`tmp` + `os.replace`）。
- `validate(settings)`：返回人类可读的校验问题列表。
- 路径助手：`seven_zip` / `output_root` / `vault_dir` 属性自动展开 `~` 与环境变量。

## 工具层 `utils/`

### `seven_zip.py`
- `run_7z(seven_zip, archive, args, password=None, timeout=None) -> SevenZipResult`：唯一 7z 调用入口。**永远**传 `-p`(空或值)、`-y`、`stdin=DEVNULL`、`creationflags=CREATE_NO_WINDOW`，防止 7z 挂起等待输入。
- `SevenZipResult`：封装返回码与输出流；提供 `ok` / `wrong_password` / `corrupt` 属性，其中 `wrong_password` 与 `corrupt` 互斥。
- `SevenZipError`：7z 失败时抛出。

### `fs.py`
- `ensure_dir`、`same_name_subfolder`（`output_root / archive.stem`）、`safe_move`（命名冲突追加数字后缀）、`safe_delete`（优先送回收站 `send2trash`，回退 `unlink`）、`is_hidden`。

### `logger.py`
配置 root logger：控制台 + `logs/app.log` 滚动文件（5×1MB）。`add_handler` 供 GUI 状态面板订阅日志。

## 数据模型 `models/`

### `archive_info.py`
- `ManifestEntry`：压缩包内单个文件（path, size, crc）。
- `ArchiveInfo`：检测结果（format, is_password_protected, header_encrypted, manifest）。

### `result.py`
- `ExtractionResult`：解压结果（ok, dest, extracted_files, error）。
- `VerifyResult`：校验结果（ok, file_count_match, missing, extra, size/crc mismatches, test_exit_code, detail）。
- `ArchiveResult`：单压缩包最终结果（path, status, message, extracted_count, password_used）。

### `vault_entry.py`
- `VaultEntry`：单条密码记录（id, value, label, enabled, use_count, created_at, last_used, notes）。
- `VaultEntry.new()` 工厂生成 uuid 与时间戳；`mark_used()` 更新使用计数。

## 核心层 `core/`

### `scanner.py`
`scan(root, output_root, extensions, skip_hidden)`：基于 `os.walk` 的生成器，剪枝 `output_root` 与 `password_protected_unsolved`，按目录排序保证确定性。

### `archive_info.py`
- `detect(seven_zip, archive, password=None) -> ArchiveInfo`：调用 `7z l -slt -p""`，解析输出判断格式/加密/manifest。
- `_parse_slt(stdout)`：解析 7z 技术列表输出。**用 `Type` 键区分头部块与文件条目**（7z 条目没有 `Folder` 字段，不能仅靠 `Folder` 判断）。
- `list_with_password(...)`：用已知密码重新列出头部加密压缩包的 manifest。

### `extractor.py`
`extract(seven_zip, archive, dest, password=None) -> ExtractionResult`：调用 `7z x -o<dest> -p<pw> -y`，拒绝覆盖非空 `dest`，返回解压出的文件列表。

### `verifier.py`
- `compute_extracted(dest)`：递归计算 `dest` 下所有文件的 `(size, crc32_hex)`。
- `_crc32_of_file(path)`：64KB 分块 `zlib.crc32`。
- `verify(seven_zip, archive, dest, password=None, info=None) -> VerifyResult`：三重校验——manifest CRC 比对、文件一致性（数量/路径/大小）、`7z t` 交叉校验。四项全过才算 `ok=True`。

### `password_manager.py` ⭐
`PasswordVault`：**密码库文件的唯一访问点**。
- `open()` / `close(stats)`：初始化仓库并提交 session 开闭标记（`--allow-empty`）。
- `list_entries(enabled_only)` / `iter_passwords_for(archive_name)`：读取返回副本，尝试顺序为 启用 → use_count 降序 → last_used 降序。
- 写操作 `add_password` / `update_password` / `set_enabled` / `record_success` / `record_failure_all`：原子写 JSON 后 `vault_git.commit`。
- **两步删除**：`prepare_delete(id)` 返回一次性令牌，`delete_password(id, token)` 验证令牌后才删除。错误令牌不消耗令牌，可重试。
- `threading.Lock` 串行化所有访问。

### `vault_git.py`
`VaultGit`：密码库本地 Git 自动化。
- `ensure_repo()`：首次 `git init` + 设置 local identity + 种子 `passwords.json`/`README.md` + 初始提交。
- `commit(message, allow_empty=False)`：`git add passwords.json README.md` 后提交。无变更返回 False。
- `log(limit)`：返回最近提交主题。

### `pipeline.py` ⭐
`ArchivePipeline.process(archive, callbacks) -> ArchiveResult`：**纯状态机，无 Qt 依赖**。
- 阶段：DETECT → DECIDE → EXTRACT → VERIFY → FINALIZE。
- 决策分支：
  - 非加密 → 解压+校验。
  - 加密 + 模块禁用 → SKIPPED（原位不动）。
  - 加密 + 模块启用 → 逐个 `7z t -p<guess>` 试密码；命中则解压+校验+`record_success`；全失败则 `record_failure_all` + 移入 unsolved。
- `confirm_delete` 回调交由调用方实现（工作线程用阻塞等待，GUI 弹对话框）。
- 任何异常都不上抛，转为 `STATUS_FAILED` 结果。

### `worker.py`
`ExtractionWorker(QThread)`：批次驱动 + 信号转发。
- 信号：`scan_started` / `archive_discovered` / `stage_changed` / `progress` / `password_try` / `archive_result` / `vault_committed` / `confirmation_requested` / `finished_all` / `fatal_error`。
- 压缩包之间检查 `isInterruptionRequested()`。
- `_WorkerCallbacks` 适配 `PipelineCallbacks` 协议到信号；`confirm_delete` 阻塞等待 GUI 回答。

## UI 层 `ui/`

### `theme.py`
- `Colors`：集中调色板（深色高对比：BG `#1e1f22`、Text `#e6e6e6`、Accent `#7c9cff`、Success `#46c46e`、Warn `#e0a832`、Error `#e5534b`）。
- `QSS`：覆盖所有控件的样式表字符串（唯一颜色集中处）。
- `apply_dark_palette(app)`：设置 QPalette 使原生对话框也匹配主题。

### `widgets/folder_picker.py`
`FolderPicker`：标签 + 只读 LineEdit + 浏览按钮，发射 `folder_changed(str)`。

### `widgets/status_panel.py`
- `StatusPanel`：`QListWidget` 彩色日志，`append_status` 按状态着色，`append_stage` 显示阶段。
- `StatusLogHandler`：`logging.Handler` 桥接日志记录到状态面板。

### `widgets/progress_panel.py`
`ProgressPanel`：当前文件标签 + `QProgressBar`，`set_progress(current, total)`。

### `widgets/settings_dialog.py`
`SettingsDialog(QDialog)`：编辑 7z 路径、输出目录、同名子文件夹、删除行为、密码模块开关、unsolved 配置、扫描扩展名。保存时校验。

### `widgets/vault_dialog.py`
`VaultDialog(QDialog)`：密码库表格 CRUD。密码默认掩码 `••••`，可切换明文。删除走两步确认。底部显示最近 Git 提交记录。

### `main_window.py`
`MainWindow(QMainWindow)`：组装所有控件、菜单栏、状态栏；连接 worker 信号到槽；处理删除确认对话框；持久化窗口几何（居中显示）。
