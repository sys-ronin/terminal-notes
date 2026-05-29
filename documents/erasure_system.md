# Permanent Erasure System

## Overview

The erasure system provides two distinct deletion modes: *forget* (soft delete) and *erase* (hard delete).  
- **Forget** removes an item from the current view but leaves its history intact. The item can be restored later.  
- **Erase** permanently removes all traces of an item from the Git history. After erasure, only a tombstone commit remains to mark that something existed.

The hard erase capability is built on a modified version of `git-filter-repo`, embedded directly into the application and extended with custom filters. This section describes the erasure process, the integration with `git-filter-repo`, and the tombstone commit that finalises the operation.

---

## 1. Deletion Modes

The `Eraser` class in `eraser.py` implements both modes. The entry point is `delete_item(uuid, delete_type, item_title)`.

**Forget (soft delete) – `_soft_delete`**  
- Removes the item from its parent’s list (e.g., `notebook.notes.remove(note)`).  
- Saves the notebook data via `NoteManager.save_data()`.  
- Commits the deletion using the appropriate `GitManager` method (`commit_note_deletion`, `commit_subnotebook_deletion`).  
- The commit message follows the standard format with `type: DELETED`.  
- The item remains in Git history and can be restored via the resurrection system.

**Erase (hard delete) – `_hard_delete`**  
- Preserves all current crypto keys before starting (saved in `saved_session_keys`).  
- Temporarily disables auto‑unlock (`self.manager._skip_auto_unlock = True`).  
- Locates the root notebook and its repository path.  
- Calls `_purge_from_git(uuid, item_type, context)` to rewrite history.  
- Removes the item from the current view (same as forget).  
- Creates a tombstone commit with `type: ERASED`.  
- Restores the saved crypto keys and re‑enables auto‑unlock.

---

## 2. Git History Purge with `git-filter-repo`

The application embeds `git_filter_repo.py`, a full copy of the standard `git-filter-repo` tool, extended with two custom filter classes: `UUIDEraseFilter` and `NotebookEraseFilter`. The embedded version is imported as a module, not invoked via subprocess.

### 2.1. `UUIDEraseFilter`

This filter removes every commit that contains a given UUID in its message, and also strips the UUID from blob content.

**Implementation:**  
- Inherits from `RepoFilter`.  
- Overrides `_tweak_commit(commit, aux_info)`:  
  - If the commit message contains the UUID **and** the message does not already contain the word `ERASED` (to preserve tombstone commits), the commit is skipped (removed).  
- Overrides `_tweak_blob(blob)`:  
  - If the blob data contains the UUID, it replaces the UUID with an empty byte string, effectively removing it from the file content.

The filter is instantiated and run directly from Python:

```python
filter = UUIDEraseFilter(args, uuid_to_erase)
filter.run()
```

### 2.2. `NotebookEraseFilter`

This filter removes all commits belonging to an entire notebook hierarchy. It takes the root notebook UUID and a list of all UUIDs in that notebook (notes, subnotebooks, files).

**Implementation:**  
- Overrides `_tweak_commit(commit, aux_info)`:  
  - If the commit message contains `root:<notebook_uuid>` or any of the individual UUIDs with `uuid:...`, the commit is skipped.  
- All other commits pass through unchanged.

The filter is used when the user chooses to erase an entire notebook.

### 2.3. Safety Checks

Before running any filter, `_purge_from_git()` performs several checks:

- The repository path must not be the project root (preventing accidental erasure of the application code).  
- `git-filter-repo` must be available (the module must have loaded successfully).  
- The path must exist and contain a `.git` directory.  

These checks are enforced by the `FILTER_REPO_AVAILABLE` flag and explicit path comparisons.

---

## 3. The Purge Process

`_purge_from_git()` is responsible for invoking `git-filter-repo` with the correct arguments.

1. **Determine the repository path** via the root notebook’s `custom_path`.  
2. **Build the command arguments** for `git-filter-repo`:  
   - `--force` (overwrite the existing repository).  
   - `--uuid-erase <uuid>` (for single‑item erasure).  
   - `--prune-empty=always` (remove empty commits).  
   - `--path structure.json`, `--path notes.json`, `--path files.json` (restrict rewriting to these three files).  
3. **Parse the arguments** using `git_filter_repo.FilteringOptions.parse_args()`.  
4. **Instantiate the appropriate filter** (`UUIDEraseFilter` or `NotebookEraseFilter`).  
5. **Call `filter.run()`** to execute the rewrite.  
6. **Run `git gc --aggressive --prune=now`** to clean up the repository after rewriting.

All output is suppressed (stderr and stdout are captured or redirected) to avoid cluttering the UI.

---

## 4. Tombstone Commit

After the Git history has been purged, a tombstone commit is created to mark that the item was erased. This commit is **not** removed by the filter (the filter explicitly preserves commits containing `ERASED`).  

The tombstone message is generated in `_hard_delete`:

```
type: ERASED NOTE: Title | in NotebookName

Metadata: uuid:xxxx-xxxx | parent:xxxx-xxxx | root:xxxx-xxxx
This item was permanently erased from history.
```

The commit is written using `GitManager.commit_silently()`, with the appropriate files (e.g., `structure.json` alone for a note, plus the relevant content file).  

Because the tombstone contains `type: ERASED` and the UUID, it will be found by `erased*` searches and appear in the activity view, but attempts to view its content will show a tombstone message (no content).

---

## 5. Erasing an Entire Notebook

The `secure_erase_notebook(notebook)` method follows a similar but more extensive process:

1. **Collect all UUIDs** belonging to the notebook (including notes, subnotebooks, and the notebook itself).  
2. **Create a temporary file** containing replacement patterns for each UUID (`literal:uuid==>`) for `git-filter-repo`.  
3. **Run `NotebookEraseFilter`** with the notebook UUID and the list of all UUIDs.  
4. **After the filter completes**, delete the notebook folder with `shutil.rmtree()`.  
5. **Unregister the notebook** from the registry and remove its session key.

This process completely removes the notebook from both history and the current filesystem.

---

## 6. Integration with Encryption

During erasure, the system must handle encrypted notebooks correctly:

- Before starting, all current crypto keys are saved (`saved_session_keys = dict(self.manager.session_keys)`).  
- Auto‑unlock is disabled to prevent the manager from trying to re‑acquire keys during the purge.  
- After the purge and tombstone commit, the saved keys are restored.  

This ensures that other encrypted notebooks remain accessible after the erasure operation.

---

## 7. Recovery and Failure Handling

If the `git-filter-repo` step fails for any reason, the operation stops before the tombstone commit is made. The item remains in the current view (it has not yet been removed). The user is informed of the failure, and no permanent change occurs.

If the tombstone commit fails after a successful purge, the Git history is already rewritten, but the item may still appear in the current view (since the removal step occurs after the tombstone). In practice, this scenario is rare; the commit operation is simple and rarely fails.

---

## 8. Constraints and Trade‑offs

- **Irreversible.** The `erase` operation rewrites history and cannot be undone. The tombstone commit is a marker, not a recovery point.  
- **Requires `git-filter-repo`.** The filter module must be present and loadable. The application checks `FILTER_REPO_AVAILABLE` and fails gracefully if it is not.  
- **Slow for large histories.** Rewriting history with `git-filter-repo` processes all commits. For very large repositories, this may take noticeable time. The operation is run in the foreground with minimal output.  
- **Encryption key preservation.** During erasure, all other notebook keys are temporarily stored in memory. If the system crashes during this window, keys may be lost, but the user can re‑enter passwords on restart.  

---

## 9. Summary

The erasure system provides two levels of deletion: forget (soft) and erase (hard). Hard erase uses an embedded, extended version of `git-filter-repo` to rewrite Git history, removing all traces of a UUID. A tombstone commit with `type: ERASED` is added to preserve a marker of the erased item. The process respects encryption by saving and restoring keys, and includes safety checks to prevent accidental erasure of the project repository.

This design allows the application to offer true permanent deletion while maintaining the ability to indicate that an item once existed, all within the constraints of a terminal‑based, Git‑backed note system.
