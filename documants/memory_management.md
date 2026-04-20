# Memory Efficiency Architecture

## 1. No Background Processes

The application performs no work unless the user initiates an action. There are no:

- Background indexing threads.
- Periodic cache refreshes.
- Auto‑save timers (the recovery system uses a thread only while an editor is open).
- Pre‑loading of notebooks or notes.

All operations—loading, decrypting, searching, committing—happen synchronously in response to user input.

This means memory usage at rest is exactly the memory required to hold the data structures the user has explicitly loaded.

---

## 2. Notebook Loading

Notebooks are loaded only when viewed.

- At startup, only the registry is read (`notebooks_registry.json`). This file contains metadata for every notebook: name, ID, encryption status, lock state, and path.
- The registry is small. For 100 notebooks, the registry is a few dozen kilobytes.
- The in‑memory notebook list stores only these metadata entries, not the notebook structure.

When the user selects a notebook to view:

- If the notebook is unlocked, its `structure.json` is loaded. This file contains the names and IDs of all notes, subnotebooks, and files, but **not their content**.
- The structure of a notebook with 1000 notes is still small (tens of kilobytes), because each note is represented by a small dictionary (`id`, `title`, `created`, `updated`, `file_extension`).

Locked notebooks are **not loaded**. Their `structure.json` is never read. Only their registry entry exists in memory.

---

## 3. Note Content Loading

Note content is stored in `notes.json` or `files.json`. These files are **not loaded** when the notebook is opened.

When the user views a note:

- The content file is opened and parsed.
- Only the specific note’s content is extracted (`content_map.get(note_id, "")`).
- The entire content file is read, but the JSON parser creates a dictionary of all notes. This is necessary because the file format is keyed by UUID. For a notebook with 10,000 notes, the dictionary will contain 10,000 entries. Each entry is a string (the note content). This is the largest memory consumer when viewing notes.

To mitigate this:

- The content file is read only when a note is viewed.
- After viewing, the dictionary is held in memory only if the notebook remains open. If the user returns to the notebook list, the content data is not retained.
- The recovery system writes autosave files, but those are on disk, not in memory.

---

## 4. Timeline: Paginated Loading

Timeline view does **not** load all versions of a note at once.

When the user requests a timeline:

- The system runs `git log --grep "uuid:..."` and receives a list of commit hashes with their dates and messages.
- Only the metadata (hash, date, first line of message) is stored in memory for each version.
- The list is then paginated: the UI displays only the items that fit on the current screen (typically 10–20 versions).
- The content of a version is **not loaded** until the user selects `[V]iew` on a specific entry.

If the note has 500 versions, the timeline will store 500 small records (each a few hundred bytes), which is manageable. But the full content of those versions is never loaded until explicitly requested.

This is critical: the system does not reconstruct historical versions just to display the list.

---

## 5. Activity View: Paginated Loading

Activity view follows the same principle.

- The Git log returns a list of commits (limited to 50).
- Each commit is represented by its hash, date, subject, and body.
- The UI displays these as a paginated list.
- The content of a commit (the actual state of an item) is **not loaded** until the user selects `[V]iew`.

Activity view does not reconstruct every commit in the list. It only loads the metadata needed for display.

---

## 6. Locked Notebooks

A locked notebook occupies:

- One registry entry (a few hundred bytes).
- No structure data.
- No content data.
- No crypto key.

When a notebook is locked, its `custom_path` is set to `None`, its `notes` list is cleared, and its `_crypto` attribute is deleted. The key is removed from `session_keys`.

**The lock button is an explicit memory manager.** It unloads the entire notebook structure, its content cache, and its encryption key from memory. This is not just a security feature; it is a user‑controlled mechanism to free resources when a notebook is no longer in active use.

Because the registry retains the notebook’s metadata, the notebook can be unlocked again later without data loss.

---

## 7. Git History and Temporary Files

History operations (activity, timeline, resurrection) run Git commands and parse their output.

- `git log` output is read as text and processed line by line. The entire log is not stored in memory; it is streamed.
- When reconstructing a historical item, a temporary directory is created (using `tempfile.mkdtemp`). This directory contains JSON files representing that single item. It is deleted when the view is closed or when the application exits.
- Only one such temporary directory exists per viewed historical item. There is no caching of multiple versions.

---

## 8. Search

Search results are limited to 50 items.

- Current items: the search walks the in‑memory notebook structure. This traversal is O(n) on the number of items in unlocked notebooks. For a typical user, this is negligible.
- Historical items: Git queries return a list of commits; the results are processed on the fly. The list is stored in memory only until the user selects an item or starts a new search.

Search does not pre‑index or cache results.

---

## 9. Encryption

Encryption keys are stored in `session_keys` only for unlocked notebooks. Each key is 32 bytes (256 bits).

- Unlocking a notebook adds one key to the dictionary.
- Locking a notebook removes it.
- The permanent storage (`config/.session_storage.enc`) is read at startup, but the keys are loaded into memory only if the corresponding notebook is unlocked later. Loading them does not keep them in memory permanently; they are stored in `session_keys` only after explicit unlock.

---

## 10. External Editor Autosave

When an external editor is launched, a background thread saves recovery files every 30 seconds.

- The thread reads the temporary file content into memory, writes it to a recovery file, and discards the string.
- The only persistent memory usage is the thread itself (negligible).
- After the editor closes, the thread stops and the recovery file is cleaned up (unless the editor crashed, in which case the file remains on disk for the next session).

---

## 11. UI Pagination

All list views (home, notebook, subnotebooks, search results, activity, timeline) use pagination.

- The number of items per page is calculated dynamically based on terminal height, typically 10–20 items.
- Only the items for the current page are rendered. The full list is stored in memory (the notebook structure or the result list), but the list itself is the in‑memory representation of the data, not a copy.
- For timeline and activity, the list is the result of a Git query; only the metadata for the displayed page is kept in a separate slice, but the original list remains in memory. This list is limited (50 items for activity, unlimited for timeline but rarely exceeds a few hundred).

---

## 12. Memory Footprint Estimates

| Component | Size |
|-----------|------|
| Locked notebook (registry entry) | ~200 bytes |
| Unlocked notebook structure (100 notes) | ~10 KB |
| Unlocked notebook structure (1000 notes) | ~100 KB |
| Note content (10,000 notes, 100 chars each) | ~1 MB (loaded only when viewed) |
| Encryption key per unlocked notebook | 32 bytes |
| Activity view commits (50 commits) | ~50 KB |
| Timeline metadata (500 versions) | ~100 KB |
| Timeline content (loaded only on view) | variable, per version |
| Search results (50 items) | ~10 KB |
| Git log streaming buffer | a few KB |

Typical working memory while viewing a notebook with 500 notes, after viewing a few notes, with timeline metadata loaded: **3–6 MB**.

When all notebooks are locked: memory is essentially the registry (a few KB) plus the running Python interpreter.

---

## 13. Why the Lock Button Is a Memory Manager

The lock button is often described only as a security feature: it clears the encryption key. But it also clears:

- `notebook.custom_path` – the reference to the on‑disk folder.
- `notebook.notes` – the list of note objects (each holding title, timestamps, etc.).
- `notebook.subnotebooks` – the entire subnotebook tree.
- `notebook._crypto` – the key.
- The entry in `session_keys`.

This means the notebook’s entire memory footprint is reclaimed. The only thing remaining is the registry entry.

Because the user decides when to lock, they control what stays in memory. This is not automatic; it is explicit. For long‑running sessions, locking notebooks that are not currently needed is the primary way to keep memory usage low.

---

## 14. Summary

Memory efficiency in this application is not achieved by aggressive caching or compression. It is achieved by:

- **Loading nothing unless needed.**
- **Pagination to limit displayed items.**
- **On‑demand reconstruction of historical data.**
- **Explicit user control via the lock button to unload entire notebooks.**

The result is a system where thousands of notebooks can exist, yet memory usage remains proportional to the small subset that is actively in use. Timeline and activity views do not pre‑load content; they only load metadata and wait for the user to request more. This matches the natural working pattern of a user: they focus on a few things at a time, and the system does not waste resources on the rest.
