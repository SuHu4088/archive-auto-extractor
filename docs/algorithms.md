# 核心算法

## 1. 密码保护检测

### 问题
ZIP / RAR / 7Z 三种格式的加密方式不同，纯 Python 库无法统一处理：
- `zipfile` 不能识别 AES vs ZipCrypto，不能解 AES。
- `rarfile` 需要 `unrar` 二进制。
- `py7zr` 仅支持 7z。

### 方案：统一用 `7z l -slt -p""`

`7z l -slt` 输出每个条目的技术字段。一次调用即可判断三种加密状态：

| 状态 | `7z l` 返回码 | stderr | 条目 `Encrypted` | 可否列出 manifest |
|---|---|---|---|---|
| 未加密 | 0 | — | `-` | ✓ |
| 数据加密（文件名可见） | 0 | — | `+` | ✓ |
| 头部加密（文件名不可见） | 2 | `Wrong password` / `Cannot open encrypted` | — | ✗ |

### SLT 输出解析

`7z l -slt` 的输出结构：

```
Listing archive: <path>

--
Path = <archive>        ← 头部块（有 Type，无 Folder）
Type = zip
Physical Size = 131

----------
                          ← 空行分隔
Path = hello.txt         ← 文件条目（有 Path，无 Type）
Folder = -
Size = 13
CRC = EBE6C6E6
Encrypted = -
```

**区分头部块与文件条目的关键**：头部块同时有 `Path` 和 `Type`；文件条目有 `Path` 但**没有** `Type`。（7z 条目甚至没有 `Folder` 字段，所以不能仅靠 `Folder` 判断——这是实现中的一个关键 bug 修复点。）

解析逻辑（`archive_info._parse_slt`）：
1. 按 `\n\n` 分割块。
2. 每块解析 `Key = Value`。
3. 若块含 `Type` 且 `archive_format` 未知 → 记录格式。
4. 若块含 `Path` 但不含 `Type` → 文件条目；`Folder = +` 跳过目录，其余加入 manifest。

## 2. CRC 完整性校验

### 三重校验（全过才允许删除原文件）

#### 校验 1：存储 CRC 比对
- 从 `7z l -slt` 取每个条目的 `CRC` 字段（8 位十六进制 CRC32）。
- 对解压出的文件用 `zlib.crc32` 分 64KB 块计算 CRC32：`crc & 0xFFFFFFFF` 格式化为 8 位 hex。
- 按相对路径逐条比对。

#### 校验 2：文件一致性
- manifest 文件数 == 解压文件数。
- 无缺失（manifest 有但解压无）。
- 无多余（解压有但 manifest 无）。
- 每个文件大小匹配。

#### 校验 3：7z 自检交叉验证
- 运行 `7z t <archive> -p<pw> -y`。
- 退出码必须为 0。这是 7z 自己的解压后 CRC 测试，独立于我们的解析器，作为兜底。

### 降级策略
- 若某条目 `CRC` 字段为空（罕见，solid RAR4）→ 该条目降级为仅校验大小 + 依赖 `7z t`。
- 若无法读取 manifest（仍加密）→ 直接判 `ok=False`（fail safe）。

### 完整性保证
删除原文件需同时满足：CRC 全匹配 + 大小全匹配 + 文件数一致 + `7z t` 退出 0 + 用户确认。任一不满足则保留原文件。

## 3. 密码尝试策略

### 排序
`iter_passwords_for(archive)` 按以下优先级排序（用稳定的链式排序，最次要的键先排）：

1. 仅启用条目（`enabled=True`）。
2. `use_count` 降序（曾成功过的优先）。
3. `last_used` 降序（最近成功的优先）。
4. `label` 升序（确定性兜底）。

### 尝试
对每个候选密码运行 `7z t <archive> -p<guess> -y`：
- 退出 0 → 命中，重新列出 manifest（头部加密时）后解压+校验，`record_success`（use_count+1，触发 Git 提交）。
- `wrong_password=True`（退出码 2 + stderr 含 `Wrong password`/`Cannot open encrypted`）→ 试下一个。
- `corrupt=True`（退出码 2 + stderr 含 `CRC failed`/`data error`，且非密码错）→ 判损坏，停止尝试。
- 全部失败 → `record_failure_all` + 移入 `password_protected_unsolved/`，提示「已尝试所有密码仍无法打开」。

### `wrong_password` 与 `corrupt` 互斥
关键设计：`corrupt` 属性先检查 `wrong_password`，若为密码错则返回 False。否则 `Cannot open encrypted`（密码错的 stderr）会被 `Cannot open`（损坏的子串）误判为损坏。这避免了一次错误的密码尝试被误读为压缩包损坏。

## 4. 密码库 Git 自动化

### 仓库结构
```
~/.archive_password_vault/
├── .git/
├── passwords.json    ← 密码数据
└── README.md          ← 说明
```

### 提交时机与消息

| 操作 | 提交消息 | allow-empty |
|---|---|---|
| 首次初始化 | `Initialize password vault` | 否 |
| session 开启 | `Vault session opened` | 是 |
| 添加 | `Add password '<label>'` | 否 |
| 更新 | `Update password '<label>'` | 否 |
| 启用/禁用 | `Toggle password '<label>' -> enabled\|disabled` | 否 |
| 删除 | `Delete password '<label>'` | 否 |
| 命中成功 | `Record success for '<label>' on <archive>` | 否 |
| 全部失败 | `All passwords failed for <archive>` | 否 |
| session 关闭 | `Vault session closed (tried=<n> ok=<m>)` | 是 |

### 噪声控制
单个密码的 `7z t` 尝试**不**各自提交（否则 1000 个密码会产生 1000 次提交）。仅在 `record_success` / `record_failure_all` / session 开闭时提交。这满足「每次调用后提交」——「调用」指逻辑上的密码库操作（成功/失败结果），而非每次探测。

### 容错
Git 失败仅记日志告警，**不阻塞**密码库写入与解压流程。密码库文件完整性优先于 Git 快照。

## 5. 同名子文件夹解压

`extractor.extract` 的 `dest = output_root / archive.stem`。例如 `vacation.zip` 解压到 `<output_root>/vacation/`。避免多个压缩包内容混在同一目录。若 `dest` 非空则拒绝解压（防止覆盖）。

## 6. 扫描剪枝

`scanner.scan` 在 `os.walk` 中：
- 从下钻目录列表移除 `output_root`（不重扫已解压内容）。
- 移除名为 `password_protected_unsolved` 的目录（不重扫已移动的未解决压缩包）。
- 跳过隐藏/系统文件。

这避免了「移动未解决压缩包到解压目录后又被扫描」的循环。
