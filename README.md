# 📓 Terminal Notes

> Encrypted terminal-based writing system with Git temporal history, powerful search, and zero-trust decoupled architecture.

---

## 📦 1. Requirements

- **Python 3.13** (any version for installed cffi and cryptography)
- **Git** (for history, timeline, restoration)
- **No pip install needed** (cryptography is bundled in `assets/`)
- **nvim / micro** (configurable via config.json)
- **Linux / Windows / Mac** (designed to run on any OS)

(tested only on Debian Linux 13)

---

## 🚀 2. Executables

`terminal_notes_ui.py` - Main notebook app — encrypted notes, search, Git timeline, restore


**Run from project folder:**

```bash
python3 terminal_notes_ui.py
```
or
```bash
git clone https://github.com/sys-ronin/terminal-notes.git
cd terminal-notes
chmod 700 terminal_notes_ui.py
./terminal_notes_ui.py
```
**single command**
```bash
git clone https://github.com/sys-ronin/terminal-notes.git && cd terminal-notes && python3 terminal_notes_ui.py
```
---

## 🔍 3. Search (from main app)

| Command | Description |
|---------|-------------|
| `s query` | Search current notebook |
| `s g* query` | Search **all** notebooks |
| `s created*` | Show all created notes |
| `s deleted*` | Show deleted notes (restorable) |
| `s in* notebookname` | Search inside a specific notebook |
| `s date* 15-05-2026` | Filter by exact date |
| `s today*` | Today’s changes |
| `s thisweek*` | This week’s activity |
| `s created* file* in* projects` | Created files inside the "projects" notebook |


**💡 Tips:**
- `j1`, `j2`, `jb` → jump between notebooks
- `l` → lock / unlock encrypted notebooks
- `b` → back
- `q` → quit
- `s` → search

*The entire GitHub repository with all its source code and documentation are explicitly part of the prior art (Public + timestamped + enabling)*

*A fact – my app itself has no name printed except on documents, like an app with no name. I could not find a place to put it and it is not needed inside the environment.*

*`The rest is explained in documentations`*
---
`email : sys_ronin@protonmail.com`


*Write without friction inside the best possible environment - The Terminal*

`sys-ronin`
