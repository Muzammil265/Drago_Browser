# LeanBrowse 🌐⚡

A low-memory, privacy-first desktop web browser built with **Python 3**, **PySide6 (Qt for Python)**, and **Qt WebEngine (Chromium)**.

---

## Architecture Overview

LeanBrowse divides responsibilities between a custom Python browser application layer and the embedded Chromium rendering engine:

```
+-----------------------------------------------------------------+
|                         LeanBrowse UI                           |
|   Tabs · Address Bar · Navigation · Privacy Controls · Memory   |
+-----------------------------------------------------------------+
                                |
                                v
+-----------------------------------------------------------------+
|                   Browser Controller (Python)                   |
|          Tab Manager · Session Handling · Memory Policies       |
+-----------------------------------------------------------------+
          |                                       |
          v                                       v
+-----------------------+              +-----------------------+
|   Resource Monitor    |              |    Privacy Manager    |
| Process RSS · Inactive|              | Off-The-Record Profile|
|  Tab Hibernation Timer|              | Memory Cache · DDG    |
+-----------------------+              +-----------------------+
          |                                       |
          +-------------------+-------------------+
                              |
                              v
+-----------------------------------------------------------------+
|                     Qt WebEngine (Chromium)                     |
|           Page Rendering · JavaScript · Network Requests         |
+-----------------------------------------------------------------+
```

### Key Engineering Pillars

1. **Intelligent Tab Hibernation (Memory Conservation)**:
   - When a tab stays inactive in the background for a configured period (default: 3 minutes; configurable down to 30 seconds for quick testing), its `QWebEngineView` and Chromium renderer process are unloaded from memory.
   - A lightweight placeholder (`SleepingTabWidget`) retains page metadata.
   - When the user switches back or clicks "Wake", the view is recreated and reloaded automatically.
   - A manual **"💤 Sleep Background"** button and shortcut (`Ctrl+Shift+S`) allows instant hibernation.

2. **Full Process Tree Resource Monitoring**:
   - Live memory telemetry monitors both the parent Python application process and all spawned Chromium child engine processes (GPU, renderers, network service) using `psutil`.
   - Tooltip reveals exact memory breakdown and child process counts.

3. **Privacy-First Defaults**:
   - Runs on an **Off-The-Record `QWebEngineProfile`**: zero persistent cookies, zero disk cache, zero persistent SQLite history on your drive.
   - HTTP cache is restricted strictly to volatile RAM.
   - **DuckDuckGo** is configured as the default search engine.
   - Quick **"🛡️ Private"** shield menu allows reviewing active privacy policies or flushing in-memory cache and cookies on demand.

---

## Directory Structure

```
LeanBrowse/
├── main.py                     # Application entry point & CLI options
├── requirements.txt            # Dependency definitions (PySide6, psutil, pytest)
├── requirements-lock.txt       # Pinned reproducible dependency versions
├── .gitignore                  # Git ignore rules for venv, cache, bytecode
├── pytest.ini                  # Pytest path and execution configuration
├── browser/
│   ├── __init__.py             # Browser package metadata
│   ├── controller.py           # Window UI, tab containers, sleeping widget, shortcuts
│   ├── memory_manager.py       # Resource monitor (psutil) & tab idle manager
│   └── privacy.py              # Off-the-record profile, cookies, DDG search normalization
└── tests/
    ├── test_privacy.py         # URL parser, DDG search, and off-the-record tests
    └── test_memory_manager.py  # Process RSS, tab tracking, and hibernation tests
```

---

## Quick Start (PowerShell on Windows 10/11)

### 1. Activate Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Run LeanBrowse
```powershell
python main.py
```

### Optional Command-Line Arguments:
```powershell
# Launch with custom starting URL
python main.py --url https://www.wikipedia.org

# Set inactivity hibernation timeout to 30 seconds for quick testing
python main.py --idle-timeout 30
```

---

## Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| `Ctrl + T` | Open new tab |
| `Ctrl + W` | Close current tab |
| `Ctrl + R` / `F5` | Reload current page |
| `Alt + Left` | Back |
| `Alt + Right` | Forward |
| `Ctrl + L` / `Alt + D` | Select & focus address bar |
| `Ctrl + Tab` | Next tab |
| `Ctrl + Shift + Tab` | Previous tab |
| `Ctrl + Shift + S` | Hibernate all background tabs immediately |
| `Ctrl + Shift + Del` | Open Privacy dialog / Flush in-memory session |

---

## Running the Automated Test Suite

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

All unit tests for URL resolution, search fallback, privacy guarantees, process memory calculation, and idle state transitions run headlessly.

---

## Memory Benchmark Guide

To verify RAM conservation across browser states:

| Test Scenario | Measurement Instructions | LeanBrowse RSS | Baseline Browser (Chrome/Edge) |
| :--- | :--- | :---: | :---: |
| **Test A — Idle** | Start browser, wait 60 seconds with 1 blank/home tab | *Record from indicator* | *Record from Task Manager* |
| **Test B — Five Tabs** | Open 5 heavy tabs (e.g., Wikipedia, GitHub, BBC, Reddit, Docs) | *Record from indicator* | *Record from Task Manager* |
| **Test C — Inactive Tabs** | Leave tabs untouched or click `💤 Sleep Background` | *Record from indicator* | *Record from Task Manager* |
