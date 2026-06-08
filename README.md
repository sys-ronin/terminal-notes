# 📓 Terminal Notes

> Encrypted terminal-based writing system with Git temporal history, powerful search, and zero-trust decoupled architecture.

---
*text based screenshots*
```

                                 Root Notebooks                                 

No notebooks yet.

Create your first notebook to get started!

or

Press [M] to import existing from remote

[C]reate  [M]anage  [Q]uit

> 
```
```

                                 Root Notebooks                                 

[1] 🔒 aa
[2] 🔐 terminal-notes (10 notes, 8 files, 1 sub)

[C]reate  [V]iew  [S]earch  [D]elete  [L]ock  [M]anage  [Q]uit

>
```
```

     .../[1]depth05/[2]depth06/[3]depth07/[4]depth08/[5]depth09/[6]depth10/     

Notes & Files: (2 notes, 4 files)
[1] regular_internal_note                               [Updated: Jun 08 19:28]
[2] regular_external_note                               [Updated: Jun 08 19:28]
[3] index.html                                          [Updated: Jun 08 19:29]
[4] Dockerfile                                          [Updated: Jun 08 20:05]
[5] research.tex                                        [Updated: Jun 08 20:05]
[6] .bashrc                                             [Updated: Jun 08 20:06]

Sub-notebook: (1 sub)
[7] View Sub-notebook =>

[C]reate  [V]iew  [D]elete  [A]ctivity  [B]ack  [J]ump  [Q]uit

>
```
```

                                 Notebook: 🔐 aa                                 

Type: 🔐 Encrypted (unlocked)
Path: /home/user/terminal-notes/notebooks_root/aa-20262607180201

Account: user-name@github
Repository: aa-20262607180201
Visibility: 🔒 PRIVATE
Last modified: Jun 07, 2026 20:46

Vault: default

Notes: 4
Files: 0
Subnotebooks: 0

[V]isibility  [S]ync  [D]elete  [C]hange  [A]ctivity  [B]ack  [Q]uit

>
```
```

                               [1]terminal-notes/                               

File Name: new_post.md [.md file]
Created: Jun 04  Updated: Jun 06 11:42

Show HN: A terminal writing environment with git, e2ee sync and temporal
search

I am a 40 years old jobless sys-admin with no cs degree and no development
experience and 25 yeras of system knowledge. I built a fully encrypted
writing environment where I can write with focus forgetting about the
application. Here ai was my code translator while I strictly was the
architect and instructor. It all started when i asked myself that "why and
how i remember any past memory instantly without searching inside my head".
This became the design principle of my app. Thus I solved a fundamental git
problem of tracking a single note throughout the history by embedding uuid
in every commit.

                                  Page 1 of 7    >>                             

[E]dit  [V]iew  [X]port  [T]imeline  [R]ename  [B]ack  [N]ext  [Q]uit

> 
```
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
