```markdown
# Restoration Engine: Technical Description

## A Document on the Resurrection of Deleted Items in Terminal Notes

---

## Preface

This document describes the restoration mechanism implemented in Terminal Notes. The system treats deletion as *inhibition*, not destruction. A deleted item is not erased from history; it is removed from the current view but remains accessible in the Git commit log. Restoration brings the item back from the commit that existed *before* the deletion, re‑inserts it into the live notebook, and records the event with a `RESTORED` commit.

The description is factual, based on the source code (`git_resurrection.py`, `restore.py`, `notebook_operations.py`). No claims of novelty are made. The reader may verify each step by inspecting the cited files.

---

## 1. Core Concepts

### 1.1 Deletion as Inhibition

When a note, file, or subnotebook is deleted using the soft‑delete (`forget`) operation:

- The item is removed from the in‑memory `notebook.notes` list.
- It is removed from `structure.json` and the appropriate content file (`notes.json` or `files.json`).
- A Git commit is created with `type: DELETED` and the item’s UUID in the metadata.

**The item is not destroyed.** Its last known state (before deletion) is stored in the commit **parent** of the deletion commit.

### 1.2 The Key Insight: Parent Commit

The deletion commit itself does **not** contain the item. To recover the item, the system navigates to the commit **before** the deletion:

```bash
git rev-parse <deletion-commit>^
```

This parent commit holds the `structure.json`, `notes.json`, and `files.json` as they were before the deletion. The item’s UUID is still present there.

### 1.3 Restoration as Disinhibition

Restoration reverses the deletion:

1. Locate the deletion commit (via search, activity view, or timeline).
2. Get its parent commit (the state before deletion).
3. Extract the item’s metadata and content from the parent commit’s JSON files.
4. Merge that content back into the live notebook.
5. Commit the restoration with `type: RESTORED`.

The original UUID is preserved, ensuring continuity of history across deletion and resurrection.

---

## 2. Finding Deleted Items

The `GitHistoryMiner` class provides methods to locate deleted items across all notebooks.

### 2.1 `find_deleted_items(query)`

**Input:** A search query (e.g., `"meeting"` or empty for all deleted items).

**Process:**

1. For each root notebook (that has a Git repository), run:
   ```bash
   git log --all --grep "^type: DELETED"
   ```
2. Parse each commit line to extract:
   - Commit hash
   - Commit message (contains title, context, UUID)
3. For each commit that matches the query text (if any), obtain the **parent commit hash**.
4. Call `_create_temp_json_for_item(uuid, parent_commit)` to reconstruct the item as it existed before deletion.
5. Return a list of reconstructed item objects, each containing:
   - `title`, `content`, `uuid`, `parent_id`, `temp_dir`, `is_file_note`, `is_subnotebook`, etc.

**Note:** The reconstruction uses the **parent** commit, not the deletion commit itself. This is the core of the resurrection mechanism.

### 2.2 `find_renamed_items(query)`

Similar to `find_deleted_items`, but searches for `^type: RENAMED` commits. The parent commit contains the item with its old name; the commit message contains both old and new names.

### 2.3 `find_restored_items(query)`

Searches for `^type: RESTORED` commits. The commit itself contains the restored item (not the parent). Reconstruction uses the commit hash directly.

### 2.4 `find_erased_items(query)`

Searches for `^type: ERASED` commits. These are tombstone markers. Only metadata is returned; content is unavailable (permanently removed).

---

## 3. Reconstructing an Item from a Specific Commit

### 3.1 `_create_temp_json_for_item(uuid, commit_hash)`

**Input:** Item UUID and a commit hash (parent of deletion, or the commit itself for restored items).

**Steps:**

1. **Retrieve historical JSON files** from the commit:
   ```bash
   git show <commit-hash>:structure.json
   git show <commit-hash>:notes.json
   git show <commit-hash>:files.json
   ```
2. **Decrypt** if the notebook is encrypted (using the same key derived from the recovery phrase and folder name; the key does not change over time).
3. **Locate the item** by UUID in `structure.json` (recursively traverse the hierarchy).
4. **Extract content** from `notes.json` (if note) or `files.json` (if file). For a subnotebook, recursively collect all descendant UUIDs and extract all their content.
5. **Create a minimal temporary directory** containing:
   - `structure.json` – only the item and its ancestors (enough to display the item in context).
   - `notes.json` or `files.json` – only the content of the reconstructed item (or all content for a subnotebook).
6. **Return a result dictionary** with:
   - `temp_dir`, `title`, `content`, `uuid`, `parent_id`, `is_file_note`, `is_subnotebook`, `date`, `commit_message`, and a reference to the encryption key (`_crypto`).

**The temporary directory is used by the UI to display the resurrected item.** It is deleted after the user finishes viewing or after restoration.

---

## 4. Restoring an Item

### 4.1 `_restore_item(result_data, ui)` (in `GitHistoryMiner` or `Restore` class)

**Input:** A result dictionary from `_create_temp_json_for_item`.

**Steps:**

1. **Extract parent UUID** from the commit metadata (or from the item’s original parent information). This tells where the item originally lived.
2. **Locate the target notebook** in the live registry using the parent UUID.
3. **Create backups** of the live `structure.json`, `notes.json`, and `files.json` (e.g., `file.json.restore_backup`) to allow rollback in case of failure.
4. **Merge content**:
   - Read the reconstructed `notes.json` (or `files.json`) from the temporary directory.
   - Add or update each entry in the live `notes.json` (or `files.json`) using the UUID as the key.
   - Write the updated content back atomically (`.tmp` → `rename`).
5. **Update structure**:
   - Read the live `structure.json`.
   - Locate the parent notebook by UUID.
   - Append the reconstructed item (note, file, or subnotebook) to the parent’s `notes` or `subnotebooks` list.
   - Write the updated structure back atomically.
6. **Commit the restoration**:
   - Stage the changed files (`structure.json`, `notes.json`, and/or `files.json`).
   - Create a commit with message:
     ```
     type: RESTORED <TYPE>: title | to notebook (X notes, Y files, Z subs)

     Metadata: uuid:ITEM_UUID | parent:PARENT_UUID | root:ROOT_UUID
     ```
   - For subnotebooks, include a summary of restored content.
7. **Delete the temporary directory** and the backup files.
8. **Refresh search results** (if the restoration was triggered from a search view) so that the item no longer appears as deleted.

### 4.2 `restore_subnotebook(uuid, target_notebook, source_data)`

For a subnotebook, the restoration is **recursive**:

1. Collect all UUIDs in the subnotebook’s hierarchy (from its `structure.json` at the target commit).
2. Merge **all** content (notes and files) for those UUIDs into the live `notes.json` and `files.json`.
3. Add the complete subnotebook structure (with all its descendants) to the parent notebook’s `subnotebooks` list.
4. Commit with a summary message.

**Atomicity:** If any step fails, backups are restored, and the live files remain unchanged. The restoration either succeeds completely or fails completely.

---

## 5. Timeline Integration

The timeline engine (`timeline_engine.py`) reuses the same reconstruction mechanism. When a user views a historical version of an item:

1. `TimelineEngine.get_item_timeline(uuid, notebook_id)` returns a list of commits (metadata only).
2. When the user selects a specific version, `create_version_at_commit(uuid, commit_hash, crypto)` is called.
3. This method delegates to `_create_temp_json_for_item(uuid, commit_hash)` (the same function used for resurrection) and returns a version object.
4. The UI displays the reconstructed item using the same viewer as resurrected items.

**No pre‑loading or caching of all versions.** Reconstruction happens on demand, keeping memory usage low.

---

## 6. Error Handling and Safety

| Failure Scenario | Mitigation |
|------------------|------------|
| Parent commit does not exist (first commit) | Restoration fails gracefully; user is notified. |
| Item UUID not found in parent commit | The item may have been created in the deletion commit itself? (Impossible; deletion commit does not contain the item.) – Fallback: report not found. |
| Write conflict during merge | Atomic writes and backups prevent partial updates. |
| Git commit fails | The notebook files are already updated; the user can later commit manually (unlikely, but safe). |
| Temporary directory cannot be created | Retry with different name; if still fails, abort restoration. |

---

## 7. Summary

The restoration engine in Terminal Notes:

- **Finds deleted items** using `git log --grep "^type: DELETED"`.
- **Reconstructs items** from the commit **before** deletion using `git rev-parse <deletion-commit>^`.
- **Creates temporary directories** with minimal JSON files for display.
- **Merges content and structure** atomically with backups.
- **Commits the restoration** with `type: RESTORED` and preserves the original UUID.

This mechanism works for notes, files, and entire subnotebook hierarchies. It requires **no user knowledge of Git** and is fully integrated with the search and timeline features.

The code is open, and the behaviour is observable. This document is based on direct reading of the source (`git_resurrection.py`, `restore.py`, `notebook_operations.py`).

---

**sys_ronin**
May 2026
sys-ronin@protonmail.com
github.com/sys-ronin/terminal-notes
```
