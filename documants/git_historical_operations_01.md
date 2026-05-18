# Prior Art Disclosure: Git Resurrection Engine

## What This Document Describes

This document describes a system for recovering deleted items from Git history. The system treats deletion as inhibition, not destruction. Deleted items remain searchable and restorable. The system also provides a timeline view that uses the same underlying engine to reconstruct any past version of an item.

The implementation uses Git commit messages as a queryable index. Each commit message contains the UUID of the affected item and the action performed (`CREATED`, `UPDATED`, `DELETED`, `RENAMED`, `RESTORED`, `ERASED`). This allows the system to find all commits related to a specific item and to distinguish between different types of changes.

No comparison with other systems is made. This document simply describes what exists.

---

## The Problem

When a user deletes a note, file, or subnotebook, most systems remove it permanently after a short retention period. The user cannot search for deleted items. The user cannot restore an item deleted weeks or months ago. Data loss is permanent and irreversible.

Git preserves history, but Git's native recovery mechanisms operate at the file level, not the item level. A user cannot search for "all deleted notes containing the word 'meeting'". A user cannot restore a single note from a file that contains many notes. Git's recovery commands require command-line expertise and knowledge of commit hashes.

The resurrection engine solves these problems by building a searchable, item-level history layer on top of Git.

---

## Core Mechanism: Commit Messages as a Queryable Index

Every commit message follows a strict format:

```
type: ACTION CONTENT_TYPE: title | context

Metadata: uuid:ITEM_UUID | parent:PARENT_UUID | root:ROOT_UUID
```

**Example:**
```
type: DELETED NOTE: meeting-notes | in work

Metadata: uuid:20260315120000 | parent:20260314120000 | root:20260313120000
```

This structure enables four key query patterns:

1. **Find all deletions** – `git log --grep "^type: DELETED"`
2. **Find all renames** – `git log --grep "^type: RENAMED"`
3. **Find all restorations** – `git log --grep "^type: RESTORED"`
4. **Find all commits for a specific UUID** – `git log --grep "uuid:20260315120000"`

The `^type:` anchor ensures that the search matches only the action line, not incidental mentions of the word "deleted" in the commit message body.

---

## The Resurrection Engine: Logical Steps

### Step 1: Find Deleted Items

**Input:** A text query (e.g., "meeting" or empty for all deleted items)

**Process:**

1. Run `git log --all --grep "^type: DELETED"` to retrieve every deletion commit in the repository.

2. For each deletion commit, extract:
   - The commit hash (to locate the commit)
   - The commit message (to extract the title, context, and UUID)
   - The parent commit hash (the commit immediately before the deletion)

3. Filter the results by the text query:
   - Search the commit message for the query text
   - If the query is empty, include all deletions

4. For each matching deletion commit, call the reconstruction mechanism (see Step 5) using the **parent commit hash** (the commit before deletion)

5. Return a list of reconstructed items, each containing the item's title, content, UUID, parent UUID, and a temporary directory with the reconstructed JSON files

**Why the parent commit?** The deletion commit itself does not contain the item (the item was removed). The parent commit contains the item in its pre-deletion state.

---

### Step 2: Find Renamed Items

**Input:** A text query

**Process:**

1. Run `git log --all --grep "^type: RENAMED"` to retrieve every rename commit

2. For each rename commit, extract:
   - The commit hash
   - The commit message (contains old name → new name)
   - The parent commit hash (the commit before the rename)

3. Filter by the text query (search the commit message)

4. For each matching rename commit, call the reconstruction mechanism using the **parent commit hash** (the commit before the rename, where the item still had its old name)

5. Return a list of reconstructed items, each including both the old name and the new name

---

### Step 3: Find Restored Items

**Input:** A text query

**Process:**

1. Run `git log --all --grep "^type: RESTORED"` to retrieve every restoration commit

2. For each restoration commit, extract:
   - The commit hash
   - The commit message
   - **The commit hash itself** (not the parent). The restoration commit contains the item (the item was added back)

3. Filter by the text query

4. For each matching restoration commit, call the reconstruction mechanism using the **commit hash itself**

5. Return a list of reconstructed items

---

### Step 4: Find Erased Items (Tombstones)

**Input:** A text query

**Process:**

1. Run `git log --all --grep "^type: ERASED"` to retrieve every erasure commit

2. For each erasure commit, extract:
   - The commit hash
   - The commit message (contains the title and UUID)
   - The parent UUID (from the metadata)

3. Filter by the text query

4. Return minimal metadata (title, UUID, parent UUID, erasure timestamp). **No content is returned** because the item has been permanently removed from Git history by `git-filter-repo`

5. The UI displays a tombstone message: "This item was permanently erased from history"

---

### Step 5: Reconstruct an Item from a Specific Commit

**Input:** An item UUID and a commit hash

**Process:**

1. **Retrieve the historical JSON files** from the specified commit:
   - `git show <commit-hash>:structure.json`
   - `git show <commit-hash>:notes.json`
   - `git show <commit-hash>:files.json`

2. **Parse the JSON**:
   - If the notebook is encrypted, decrypt the JSON using the notebook's key (derived from the folder name and the user's phrase or password)
   - The key does not change over time, so the same key works for all historical commits

3. **Locate the item by UUID** in the historical `structure.json`:
   - Walk the hierarchy recursively (notebooks → subnotebooks → notes)
   - If the UUID belongs to a note or file, extract its metadata (title, timestamps, file extension if any)
   - If the UUID belongs to a subnotebook, extract its name and the list of its child UUIDs

4. **Extract the item's content**:
   - If the item is a note, look up its UUID in the historical `notes.json`
   - If the item is a file, look up its UUID in the historical `files.json`
   - If the item is a subnotebook, collect **all** UUIDs in its hierarchy (recursively) and extract their content from `notes.json` and `files.json`

5. **Create a minimal temporary directory** containing only the reconstructed item:
   - Create a new `structure.json` that contains only the item and its ancestors (enough to display the item in context)
   - Create a new `notes.json` or `files.json` containing only the content for the reconstructed item (or all content for a subnotebook)
   - Write these files to a temporary directory (e.g., `/tmp/resurrected_<uuid>/`)

6. **Return a result dictionary** containing:
   - `temp_dir`: the path to the temporary directory
   - `title`: the item's title or name
   - `content`: the item's content (for notes and files)
   - `uuid`: the item's UUID
   - `parent_id`: the UUID of the parent notebook
   - `is_file_note`: boolean indicating whether the item is a file
   - `is_subnotebook`: boolean indicating whether the item is a subnotebook
   - `date`: the commit timestamp
   - `commit_message`: the commit message

---

### Step 6: Restore an Item

**Input:** A result dictionary from the reconstruction mechanism

**Process:**

1. **Extract the parent UUID** from the result dictionary. The parent UUID is stored in the commit metadata and indicates where the item originally lived

2. **Locate the target notebook** in the live registry by its UUID. The target notebook is the parent notebook where the item should be restored

3. **Create backups** of the live JSON files (`structure.json`, `notes.json`, `files.json`) before making any changes. Each backup is written to a separate file (e.g., `structure.json.restore_backup`)

4. **Merge the reconstructed content** into the live content files:
   - Read the reconstructed `notes.json` or `files.json` from the temporary directory
   - Read the live `notes.json` or `files.json`
   - For each UUID in the reconstructed file, add or update the entry in the live file (UUID is the key, so there is no conflict)
   - Write the updated content back to the live file atomically (write to `.tmp`, `fsync`, `rename`)

5. **Update the live structure**:
   - Read the live `structure.json`
   - Locate the parent notebook by UUID
   - Append the reconstructed item (note, file, or subnotebook) to the parent's `notes` or `subnotebooks` list
   - Write the updated structure back atomically

6. **Commit the restoration**:
   - Stage the changed files (`structure.json` and the appropriate content file)
   - Create a commit with message type `RESTORED`, including the UUID and parent information in the metadata
   - If the restoration is a subnotebook, include a summary of the restored content (number of notes, files, subnotebooks)

7. **Delete the temporary directory** and the backup files

8. **Refresh search results** (if the restoration was triggered from a search view) so that the restored item no longer appears as deleted

**Atomicity guarantee:** If any step fails (e.g., disk full, write error), the backup files are restored, and the live files remain unchanged. The restoration either succeeds completely or fails completely.

---

## The Timeline Engine: Logical Steps

**Input:** An item UUID and a notebook ID

**Process:**

1. **Find the root notebook** containing the item. All commits are stored in the root notebook's Git repository

2. **Run a Git log query** to find every commit mentioning the UUID:
   ```
   git log --all --grep "uuid:<UUID>"
   ```

3. **Parse the results**:
   - For each commit, extract the commit hash, timestamp, and commit message
   - Parse the commit message to determine the action (`CREATED`, `UPDATED`, `DELETED`, `RENAMED`, `RESTORED`, `ERASED`)
   - For `UPDATED` or `EDITED` actions, extract the change statistics (`+X/-Y`) from the commit message body

4. **Store the version metadata** in a list, sorted by timestamp (newest first). Each version contains:
   - `commit_hash`: the Git commit identifier
   - `date`: the commit timestamp
   - `action`: the action type
   - `message`: the commit message (first line)
   - `stats`: change statistics (for `UPDATED` or `EDITED` actions)

5. **Display the timeline** as a paginated list. The user can select any version to view

6. **When the user selects a version**, call the reconstruction mechanism (Step 5) using the selected commit hash. The reconstructed item is displayed in a read-only viewer

**Note:** The timeline engine does **not** pre-reconstruct every version. It only stores metadata. Reconstruction happens on-demand when the user views a specific version. This keeps memory usage low even for items with hundreds of historical versions.

---

## Recursive Subnotebook Restoration

When a subnotebook is restored, the process is recursive:

1. **Collect all UUIDs** in the subnotebook hierarchy:
   - Start with the subnotebook's own UUID
   - Recursively traverse its `notes` list and `subnotebooks` list
   - Add every note UUID and every child subnotebook UUID to the set

2. **Merge all content** for those UUIDs:
   - For each UUID in the set, if it exists in the reconstructed `notes.json`, add it to the live `notes.json`
   - If it exists in the reconstructed `files.json`, add it to the live `files.json`

3. **Merge the structure**:
   - Add the subnotebook (with its complete internal structure) to the parent notebook's `subnotebooks` list

4. **Commit the restoration** with a summary:
   - `type: RESTORED SUBNOTEBOOK: name | to parent (X notes, Y files, Z subs)`

The restoration is atomic: all content and structure changes are written in a single operation, with backups created before any changes.

---

## Why Git's Native Recovery Is Not Equivalent

Git's native recovery commands:

- Operate at the **file level**, not the item level
- Require the user to know the **file path** and the **commit hash**
- Cannot search for deleted **content** (e.g., "meeting")
- Cannot restore a **single item** from a file that contains many items
- Provide no **user-facing restore button**; the user must type Git commands

The resurrection engine:

- Operates at the **item level** (notes, files, subnotebooks)
- Searches by **UUID, action type, and text content**
- Restores a single item from a file containing many items
- Provides a simple `[R]estore` command in the UI
- Requires **no knowledge of Git**

The difference is not incremental. It is a difference in kind.

---

## The Cognitive Model

The resurrection engine implements a specific cognitive model of memory:

| Operation | Cognitive Analogue | Implementation |
|-----------|-------------------|----------------|
| **Soft delete (forget)** | Inhibition | Item removed from current view, but remains in Git history. Searchable via `deleted*` |
| **Hard erase (erase)** | Destruction | Item removed from Git history via `git-filter-repo`. Tombstone commit marks the erasure |
| **Restoration** | Disinhibition | Item merged back into live notebook from the commit before deletion |
| **Timeline** | Reconsolidation | User can revisit any past state of the item |

This model treats deletion as reversible (unless explicitly erased). The user does not lose data by accident. The user can explore history without fear. The system remembers what the user forgets.

---

## Implementation Summary

| Component | Logical Mechanism |
|-----------|-------------------|
| **UUID permanence** | Every item receives a permanent UUID at creation. The UUID appears in every commit message and in every JSON file that references the item |
| **Commit message format** | `type: ACTION CONTENT_TYPE: title \| context` with `Metadata: uuid:... \| parent:... \| root:...` |
| **Deletion search** | `git log --grep "^type: DELETED"` → extract UUID → reconstruct from parent commit |
| **Renamed search** | `git log --grep "^type: RENAMED"` → extract old/new names → reconstruct from parent commit |
| **Restoration search** | `git log --grep "^type: RESTORED"` → reconstruct from the commit itself |
| **Erasure search** | `git log --grep "^type: ERASED"` → return tombstone metadata (no content) |
| **Reconstruction** | Retrieve JSON files from specific commit → locate UUID → create temporary directory with minimal structure and content |
| **Restoration** | Merge reconstructed content into live files → update structure → commit as `RESTORED` |
| **Timeline** | `git log --grep uuid:<UUID> --all` → store metadata → reconstruct on-demand |
| **Recursive subnotebook restoration** | Collect all UUIDs in hierarchy → merge all content → update structure → commit summary |

---

## Prior Art Assertion

The concepts described in this document – including but not limited to item-level deletion search, item-level rename search, restoration from commit before deletion, recursive subnotebook restoration, timeline reconstruction on-demand, and the cognitive model of deletion as inhibition – were made public in timestamped GitHub repositories and prior art disclosures starting in February 2026.

These concepts constitute prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) EPC. No party may obtain valid patent claims covering any of these concepts.

The system is released under the **Eternal License**, which explicitly prohibits patenting any disclosed concept.

---

## Conclusion

The Git Resurrection Engine treats deletion as inhibition, not destruction. Deleted items remain searchable and restorable. The timeline engine uses the same underlying engine to reconstruct any past version of an item. The system operates at the item level, not the file level, and requires no knowledge of Git commands.

This is not a wrapper around Git. It is a new abstraction layer that transforms Git's file-centric history into an item-centric temporal database.
```
