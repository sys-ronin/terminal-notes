# The Three‑File Architecture

## 1. The Division

Every notebook repository contains exactly three JSON files:

- `structure.json` – the notebook hierarchy: names, UUIDs, parent relationships, and references to notes and subnotebooks.
- `notes.json` – content of regular notes, keyed by UUID.
- `files.json` – content of file notes (any file type), also keyed by UUID.

This separation is the foundation upon which every other feature is built.

---

## 2. Why Three Files, Not One

A single file containing everything (structure and all content) would create a single point of change for any modification. Every note edit would require rewriting the entire file. Git would store a full new version each time, regardless of delta compression, because the file would be completely different.

By separating structure from content:

- Renaming a notebook or moving a note changes only `structure.json`.
- Editing a note changes only `notes.json` (or `files.json`).
- Adding a file changes only `files.json` and `structure.json` (but structure is a small addition).

Each file evolves independently. Git stores deltas for each file separately, so a small change in `notes.json` results in a small delta. The repository size grows with the number of changes, not with the number of versions times the total size.

This is the primary mechanism that keeps the Git storage footprint low over years of use.

---

## 3. UUID as the Common Key

All three files use the same UUIDs to refer to notes and files.

- `structure.json` contains notes entries with `id` fields.
- `notes.json` has keys equal to those UUIDs.
- `files.json` also uses the same UUIDs as keys.

When a note is created, a UUID is generated. That UUID is stored in `structure.json` (as part of the note’s entry) and also becomes a key in `notes.json` (or `files.json`). The two are linked by the UUID.

This allows the system to:

- Load the structure without loading content.
- Load a note’s content by looking up its UUID in the appropriate content file.
- Load content for a list of notes without scanning the structure again.

Because the link is by UUID, the content files are simple dictionaries. No complex mapping is needed.

---

## 4. How This Enables Navigation

Navigation (home screen, notebook view, subnotebook view) requires only `structure.json`. The user sees a list of notes with titles, timestamps, and file indicators. None of that needs the actual content.

- When the user opens a notebook, `structure.json` is read. The notes list is built from the `notes` array. The content of the notes is **not loaded**.
- When the user scrolls through the list, only the `structure.json` data is used.
- The lock button can unload `structure.json` when locking a notebook, freeing memory. The content files are not even loaded, so no memory is wasted.

If structure and content were combined, unlocking a notebook would load all content automatically, increasing memory footprint and startup time.

---

## 5. How This Enables Git History

Git commits record changes to these files individually. Because they are separate:

- A commit that renames a note touches only `structure.json`. The content file remains unchanged.
- A commit that edits a note touches only `notes.json`. The structure file remains unchanged.
- A commit that deletes a note touches `structure.json` (to remove the entry) and the appropriate content file (to remove the mapping). The two changes are in separate files, but they are part of the same commit.

This separation means that when you view the history of a note, the `git log` command can be scoped to `notes.json`. It does not need to filter through commits that only changed structure. Conversely, activity view for a notebook (showing renames) can focus on `structure.json`.

The commit messages embed the UUID and the action. Git does not need to parse the file content to understand what changed; the metadata is in the message.

---

## 6. How This Enables Resurrection

Resurrection requires reconstructing an item from a past commit. Because structure and content are separate:

- The structure at a given commit is retrieved from `structure.json` at that commit.
- The content is retrieved from `notes.json` or `files.json` at the same commit.
- The UUID links the two.

If the files were combined, reconstructing a single note would require loading the entire monolithic file and extracting the relevant parts. With separation, only the necessary parts are loaded: the structure entry for the note and its content entry.

The timeline engine uses this to reconstruct only the requested item, not the whole notebook.

---

## 7. How This Enables Precise Deletion with `git-filter-repo`

When erasing a note, `git-filter-repo` is told to operate only on `structure.json`, `notes.json`, and `files.json`. Because the content is separate from the structure:

- Removing a note requires removing its entry from `structure.json` and its key from `notes.json` (or `files.json`). Both are in separate files.
- The `UUIDEraseFilter` can target these specific files, leaving other files untouched.

If the data were combined, erasing a note would require rewriting a single large file, potentially affecting other notes in the same file. Because of the separation, the operation is scoped and safe.

---

## 8. How This Enables Restoration

Restoration is the inverse of deletion. When a note is restored:

- The structure entry is added back to `structure.json`.
- The content entry is added back to `notes.json` (or `files.json`).
- The UUID is reused; no new ID is generated.

Because structure and content are separate, adding them back is a simple insertion. The restore process does not need to merge two different file formats; it just appends to the appropriate JSON dictionaries and writes the files.

---

## 9. How This Enables Memory Efficiency

When a notebook is unlocked:

- `structure.json` is read and parsed. This gives the entire note list (titles, timestamps, etc.) without loading any content.
- `notes.json` and `files.json` are **not read** until a note is viewed.

When a note is viewed:

- The appropriate content file is read and parsed.
- The entire dictionary is loaded, but only one note’s content is displayed.

When the user returns to the notebook list, the content dictionary can be discarded (in practice, it stays until the notebook is locked or the app exits, but it is not needed for the list). The structure remains in memory, but structure is small compared to content.

If structure and content were combined, unlocking a notebook would load all content automatically, consuming memory proportional to the total size of all notes.

---

## 10. How This Enables the Lock Button as Memory Manager

Locking a notebook discards:

- The parsed `structure.json` (the note list).
- The parsed `notes.json` and `files.json` (if they were loaded).
- The encryption key.

Because structure and content are separate, locking can be selective. The system does not need to keep structure in memory once the notebook is locked; it can be reloaded from disk when unlocked again.

If structure and content were combined, locking would either have to keep the combined structure in memory (wasting memory) or discard it entirely (requiring a full reload on unlock, which would reload all content as well). The separation allows fine‑grained control.

---

## 11. How This Enables Git Delta Efficiency

Git stores each file independently. Because structure and content are separate:

- `structure.json` changes frequently but remains small (a few kilobytes). Git stores deltas for it.
- `notes.json` and `files.json` grow over time but change only when their corresponding notes are edited. Each edit produces a small delta (the change in the encrypted blob, which Git compresses further).

If all data were in one file, every edit would change the entire file. Even with delta compression, the first edit after a large addition would create a large delta because the file would shift. Separation prevents this.

---

## 12. Why This Design Is the Foundation for Everything

Without this separation:

- Navigation would require loading content.
- Git history would be a single file’s history, making it impossible to separate structure changes from content changes.
- Resurrection would require reconstructing a monolithic file.
- Deletion with `git-filter-repo` would be imprecise and risk affecting unrelated data.
- Restoration would be a full‑file rewrite.
- Memory would be tied to total note count, not active use.
- The lock button could not unload structure independently of content.
- Git storage would grow much faster because each edit would rewrite the entire notebook state.

This separation is not an implementation detail. It is the central architectural decision that enables every other feature:

- **Navigation** – uses structure only.
- **Git history** – separate files mean separate history streams.
- **Resurrection** – reconstruct by UUID from two separate files.
- **Filter‑repo deletion** – target specific files, not the whole notebook.
- **Restoration** – append to two separate files.
- **Memory efficiency** – load structure without content, load content on demand.
- **Lock button** – discard structure, content, and key independently.
- **Storage efficiency** – small deltas for small changes.

Every feature you built rests on this single decision: keep the notebook’s blueprint separate from its contents, and link them by UUID. Without it, the system would be a conventional note‑taking app. With it, it becomes a versioned, memory‑efficient, resurrectable, and securely erasable knowledge base.

This is why the three‑file architecture is the most important part of the codebase. It is not merely a storage format; it is the enabling structure for everything that follows.
