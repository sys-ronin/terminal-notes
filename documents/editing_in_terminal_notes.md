# Editing in Terminal Notes

## A Document on the Act of Writing

---

## Preface

This document describes how editing works in Terminal Notes. The system does not assume a single way to write. It adapts to the user's tools, protects their work from loss, and preserves the syntax of their files.

More importantly, the editing interface is not static. It reveals commands only when they are relevant. The user never sees a button they cannot press. The interface teaches itself through use.

The description is factual. No claim of superiority is made. The reader may evaluate the design for themselves.

---

## The Two Editing Modes

The user can write in two ways, chosen per note at creation time. The choice is permanent for that note, because the system remembers which editor the user preferred for that type of writing.

### Internal Editor

The internal editor is built into the terminal. It is a simple line‑based input. The user writes lines, and presses `Ctrl+D` on an empty line to finish.

**When to use it:** Quick notes, drafts, or when an external editor is not available.

**What it provides:**
- No external dependencies
- Immediate, no launching delay
- Works over SSH or in minimal environments
- No syntax highlighting
- Plain text only

### External Editor

The external editor is the user's preferred editor (micro, nvim, vim, helix, emacs, nano, etc.). The system launches it on a temporary file, waits for the editor to close, and captures the content.

**When to use it:** Any serious writing, code, configuration files, or long‑form notes.

**What it provides:**
- Full syntax highlighting
- Keybindings the user already knows
- Autosave (injected by the system)
- Recovery from crashes

---

## Editor Configuration

The user's editor preferences are stored in `config.json`. There are two settings:

```json
{
    "edit": "micro",
    "view": "micro"
}
```

- `edit` – editor used for writing and modifying notes
- `view` – editor used for read‑only viewing (opens in read‑only mode)

If the configuration file does not exist, it is created automatically with sensible defaults. The user may edit it manually. There is no settings UI because the user sets this once and never thinks about it again.

**Editor auto‑detection:** The system tests each editor in a predefined order and uses the first one found. The user's preference overrides the order.

---

## Syntax Highlighting for File Notes

File notes (created with `[C]reate` → `2` → choose extension) retain their file extension. When opened in an external editor, the editor applies syntax highlighting based on that extension.

Supported extensions include:

| Category | Examples |
|----------|----------|
| Web | `.html`, `.js`, `.css`, `.ts`, `.vue`, `.jsx`, `.svelte` |
| Backend | `.py`, `.php`, `.rb`, `.java`, `.c`, `.cpp`, `.go`, `.rs` |
| DevOps | `.sh`, `.yml`, `.yaml`, `.toml`, `.ini`, `.cfg`, `.tf`, `Dockerfile` |
| Data | `.json`, `.xml`, `.sql`, `.proto` |
| Documentation | `.md`, `.txt`, `.tex`, `.bib`, `.org`, `.adoc`, `.rst`, `.typ` |
| Config | `.bashrc`, `.zshrc`, `.vimrc`, `.gitconfig`, `.gitignore`, `.editorconfig` |

The extension is stored in `structure.json` as `file_extension`. The content is stored in `files.json`. When viewing, the system launches the appropriate editor with the correct file extension, enabling full syntax highlighting.

---

## The Editing Interface: Contextual Buttons

The note view screen shows different buttons depending on the type of note and the state of the system. This is not minimalism. It is relevance.

### Note View (Regular Note)

```
[1]notebook/

Note Title: Meeting Notes
Created: May 20  Updated: May 21 14:30

Content lines...

                                 Page 1 of 3    >>

[E]dit  [V]iew  [T]imeline  [R]ename  [B]ack  [N]ext  [Q]uit
```

**Buttons shown:**
- `[E]dit` – modify the note
- `[V]iew` – read‑only view (opens external editor in read‑only mode)
- `[T]imeline` – see all historical versions
- `[R]ename` – change the title
- `[B]ack` – return to notebook view
- `[N]ext` – next page (if content spans multiple pages)
- `[P]rev` – previous page (shown only when not on first page)
- `[Q]uit` – exit the application

**`[X]port` is NOT shown** because this is not a file note.

### Note View (File Note)

```
[1]notebook/

File Name: script.py [.py file]
Created: May 20  Updated: May 21 14:30

Content lines...

                                 Page 1 of 3    >>

[E]dit  [V]iew  [X]port  [T]imeline  [R]ename  [B]ack  [N]ext  [Q]uit
```

**Buttons shown:**
- `[E]dit` – modify the file
- `[V]iew` – read‑only view (with syntax highlighting)
- `[X]port` – export the file to the filesystem (only appears for file notes)
- `[T]imeline` – see all historical versions
- `[R]ename` – change the filename (extension preserved)
- `[B]ack` – return to notebook view
- `[N]ext` / `[P]rev` – pagination
- `[Q]uit` – exit

**`[X]port` appears only when the note is a file note. The user does not see it otherwise.**

### Timeline View (Any Note)

```
Timeline: script.py (8 versions)

[1] 2026-05-21 14:30 [UPDATED] fix: added error handling (+15/-3)
[2] 2026-05-20 09:15 [CREATED] initial script (+247)

                                 Page 1 of 1

[V]iew  [B]ack  [Q]uit
```

**Buttons shown:**
- `[V]iew` – view the selected version (read‑only)
- `[B]ack` – return to note view
- `[Q]uit` – exit

**`[E]dit` is NOT shown** because you cannot edit history. **`[X]port` is NOT shown** because the version is a historical reconstruction, not the live file.

### Pagination Buttons (When Content Exceeds Screen Height)

The `[N]ext` and `[P]rev` buttons appear dynamically based on content length.

| Content Height | Buttons Shown |
|----------------|---------------|
| Fits on one page | No pagination buttons |
| Spans multiple pages, on first page | `[N]ext` only |
| Spans multiple pages, on last page | `[P]rev` only |
| Spans multiple pages, on middle page | `[N]ext` and `[P]rev` |

**The user never sees a pagination button that does nothing.**

---

## Why Contextual Buttons Matter

| Principle | Implementation |
|-----------|----------------|
| **Recognition over recall** | The user does not need to remember that file notes can be exported. The `[X]port` button appears when viewing a file note. |
| **Affordance** | The button's presence invites the action. The user discovers features by seeing them, not by reading a manual. |
| **Cognitive load reduction** | The user is not distracted by irrelevant commands. The interface shows only what is possible now. |
| **Forgiveness** | The user cannot accidentally press a button that is not shown. There is no "grayed out" ambiguity. |

**The interface teaches itself. Each new screen reveals new possibilities. The user learns by doing, not by studying.**

---

## Exporting File Notes

File notes can be exported to the filesystem. From the note view, press `[X]port`. The system prompts for a directory, then writes the file with its original name and extension.

**Export behaviour:**
- The file is saved as plain text (decrypted)
- The original filename is preserved
- The export directory can be any path (local, USB, network share)
- The system remembers the last few export directories for convenience

**`[X]port` appears ONLY for file notes. Regular notes cannot be exported because they have no file extension. The user never sees an option that does not apply.**

---

## Safety: Autosave and Recovery

When editing with an external editor, the system launches a background thread that saves recovery copies every 30 seconds.

**Recovery file location:** `.recovery/` in the application directory.

**Recovery file naming:** `{note_title}_{note_uuid[-6:]}.{ext}` (for file notes) or `{note_title}_{note_uuid[-6:]}` (for regular notes).

**Recovery process:**
1. When a notebook is opened, the system scans for recovery files belonging to notes in that notebook.
2. For each recovery file, it compares the timestamp with the note's `updated` timestamp.
3. If the recovery file is newer, the system restores the content, commits the change, and deletes the recovery file.

**Result:** Work is never lost, even if the editor crashes, the system crashes, or the power fails.

---

## Safety: Atomic Writes

When the system saves a note, it does not write directly to the file. It writes to a temporary file (`.tmp`), calls `fsync()` to force the write to disk, then renames the temporary file to the target name.

**Why this matters:**
- If the system crashes during write, the original file remains intact
- If the write fails, the temporary file is discarded
- No partial writes, no corruption

This applies to all JSON files (`structure.json`, `notes.json`, `files.json`) and to the recovery files themselves.

---

## The Complete Editing Experience

### Creating a Note

1. Press `[C]reate` from a notebook view
2. Enter a title
3. Choose editor: `1` for internal, `2` for external
4. Write
5. Save and exit (for external editor) or `Ctrl+D` (for internal)
6. The note appears in the list

### Editing a Note

1. From the note view, press `[E]dit`
2. The same editor choice is remembered per note (the one used at creation)
3. The system launches the editor with the current content
4. The user modifies the content
5. The system captures the new content, saves it, and commits the change to Git

### Viewing (Read‑Only)

1. From the note view, press `[V]iew`
2. The system launches the `view` editor in read‑only mode
3. The user can read, but cannot modify
4. No autosave, no recovery thread

### Renaming a Note

1. From the note view, press `[R]ename`
2. Enter the new title (or new filename with extension for file notes)
3. The system updates `structure.json` and commits the change
4. The UUID remains unchanged

### Timeline (Version History)

1. From the note view, press `[T]imeline`
2. The system shows a paginated list of every version of the note
3. Select a version, press `[V]iew` to see the note as it existed at that commit
4. The view is read‑only; cannot edit historical versions

### Exporting a File Note

1. From the file note view, press `[X]port`
2. Enter a directory path
3. The file is written to the filesystem with its original name and extension
4. The note remains in the notebook

---

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| **User's tools, not system's tools** | The system adapts to the user's preferred editor, not the other way around. |
| **Work is never lost** | Autosave, recovery, atomic writes. The system assumes failure and protects against it. |
| **Syntax matters** | File notes retain extensions for syntax highlighting. The system does not force plain text. |
| **Export is a copy, not a move** | Exporting does not remove the note. The user can share without losing the original. |
| **History is accessible** | Timeline view allows the user to revisit any past state. No version is hidden. |
| **No lock‑in** | Exported files are plain text. The user can leave any time. |
| **Buttons are contextual** | Commands appear only when relevant. The user never sees an option that does nothing. |
| **Interface teaches itself** | Each screen reveals new possibilities. Learning happens through use, not study. |

---

## What the User Experiences

A user writes a Python script as a file note. They press `[C]reate`, choose `2` (external editor), name it `script.py`. The system opens `micro` with syntax highlighting. They write code. Every 30 seconds, the system saves a recovery copy. They finish, save, exit. The note appears in the list.

Later, they edit the script. They press `[E]dit`. The system opens the same editor, with the same syntax highlighting. They modify. They save. The system commits the change.

They want to share the script. They press `[X]port` (which appears only because this is a file note), choose a directory, and the file appears on their filesystem.

They accidentally delete a critical function. They press `[T]imeline`, find yesterday's version, press `[V]iew`, see the old code, and manually restore it.

They view a regular note. The `[X]port` button is absent. They do not wonder why. They do not miss it. It was never relevant.

**The system never interrupts. It never asks "are you sure?" unless the action is destructive. It never hides the user's work. It never loses it. It never shows an option that cannot be used.**

---

## Conclusion

Editing in Terminal Notes is not a feature. It is the core activity. The system provides two modes (internal and external) to adapt to the user's context. It preserves syntax highlighting for file notes. It protects work with autosave, recovery, and atomic writes. It allows export without lock‑in. It provides timeline access to every past version.

The interface reveals commands only when they are relevant. The user never sees a button they cannot press. The `[X]port` button appears only for file notes. Pagination buttons appear only when content spans multiple pages. The `[N]ext` and `[P]rev` buttons appear only when there is a next or previous page.

**The user writes. The system remembers. The interface disappears. The buttons appear only when needed. Nothing more. Nothing less.**

**End of Document**
---
