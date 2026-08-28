# 架构设计

## 概述

「密码识别并自动解压缩」是一个桌面应用，递归扫描文件夹中的压缩包（ZIP/RAR/7Z），自动解压并做 CRC 完整性校验，受密码保护的压缩包默认跳过，待启用密码库后再尝试解密。整体采用**分层架构**，核心逻辑不依赖 GUI 框架，便于单元测试与复用。

## 分层

```
┌─────────────────────────────────────────────┐
│  UI 层 (PyQt6)                              │
│  theme / main_window / widgets / dialogs   │
└───────────────┬─────────────────────────────┘
                │ 信号 / 槽（Qt）
┌───────────────▼─────────────────────────────┐
│  并发层  ExtractionWorker (QThread)         │
│  扫描驱动 + 信号转发 + 删除确认桥接         │
└───────────────┬─────────────────────────────┘
                │ PipelineCallbacks 协议
┌───────────────▼─────────────────────────────┐
│  核心层 (无 Qt)                             │
│  scanner → archive_info → extractor        │
│  → verifier → pipeline                     │
│  password_manager / vault_git              │
└───────────────┬─────────────────────────────┘
                │ subprocess / 文件 I/O
┌───────────────▼─────────────────────────────┐
│  外部依赖                                   │
│  7z.exe (C:\Program Files\7-Zip)  ·  Git  │
│  ~/.archive_password_vault (独立 Git 仓库) │
└─────────────────────────────────────────────┘
```

## 模块依赖

```
config / constants / utils
        ▲
        │
   models (dataclass)
        ▲
        │
   core: scanner, archive_info, extractor, verifier
   core: password_manager ──▶ vault_git ──▶ git
   core: pipeline ──▶ password_manager + 上述 core
   core: worker (QThread) ──▶ pipeline + scanner + password_manager
        ▲
        │
   ui: theme, main_window, widgets ──▶ worker + config
```

**关键约束**：`core/` 下除 `worker.py` 外均不导入 `PyQt6`，因此可用 pytest 直接测试。

## 线程模型

- **主线程（GUI 线程）**：渲染界面、响应交互、弹出确认对话框。
- **工作线程（`ExtractionWorker(QThread)`）**：执行扫描→解压→校验→收尾的完整批次，通过 `pyqtSignal` 上报状态，**从不直接触碰控件**。
- **删除确认桥接**：工作线程遇到需要确认删除时，发射 `confirmation_requested` 信号；主线程槽弹出 `QMessageBox.question`，用户回答后调用 `worker.set_delete_decision()`，工作线程在 `_WorkerCallbacks.confirm_delete` 中轮询该标志返回结果。这样既避免在工作线程中操作控件，又不会死锁。
- **取消**：`requestInterruption()` 在压缩包之间检查；单个 7z 子进程会运行完毕（不中途 kill，避免半解压状态）。

## 数据流（单压缩包）

```
scanner.scan ─▶ archive_path
                   │
            archive_info.detect (7z l -slt -p"")
                   │
            ┌──────┴─────── Encrypted? ───────┐
            │No                                │Yes
            ▼                                  ▼
     extractor.extract            password_module_enabled?
     (7z x -p"")                       ┌──────┴───────┐
            │                          │No             │Yes
            ▼                          ▼               ▼
     verifier.verify              SKIPPED     try each password:
     (7z l CRC + zlib.crc32                 7z t -p<guess>
      + 7z t 交叉校验)                       ├─ ok → extract + verify
            │                                └─ all fail → UNSOLVED
       ┌────┴────┐                              + move to unsolved dir
       │ok       │fail
       ▼         ▼
   (可选删除)   FAILED（保留原文件）
   确认对话框
```

## 配置与持久化

- `config.json`：跟踪于项目 Git，仅含默认值（不含用户机器路径）。
- `config.local.json`：git-ignored，存放运行时用户选择（输出目录、窗口几何等）。
- `~/.archive_password_vault/passwords.json`：独立 Git 仓库，密码库数据。

## 两个 Git 仓库

| 仓库 | 位置 | 用途 | 提交时机 |
|---|---|---|---|
| 项目仓库 | 项目根 `.git` | 版本管理代码与文档 | 手动开发提交；初始化时自动提交 |
| 密码库仓库 | `~/.archive_password_vault/.git` | 追踪密码库变更 | 每次增删改查、session 开闭自动提交 |

两者完全独立，不共享配置、提交或远程。
