# Git as Temporal Database

## Overview

Git is used in this system not as a version control tool, but as a temporal database. Every change to a notebook is recorded as a commit. Each commit carries structured metadata that enables querying by item identity, action type, and time. The repository becomes a complete, immutable history of every item, from creation through modification, deletion, and resurrection.

This document describes how Git is integrated, how commits are structured, and how the system queries history without external indexing.

---

## 1. Why Git

Git was chosen because it already provides:

- **Immutability.** Once written, a commit cannot be changed without rewriting history.
- **Cryptographic integrity.** Each commit is identified by a SHA‑1 hash that depends on its content and parent.
- **Efficient storage.** Git stores deltas, not full copies. Even with encryption, binary deltas remain efficient.
- **Queryability.** `git log` with `--grep` allows searching commit messages by pattern.
- **Portability.** Git is installed on most systems and can be bundled if not.
- **Decentralisation.** Every clone is a full copy. No central server required.

The system does not treat Git as a backup or sync tool. It treats Git as the primary storage layer. The JSON files in the working directory are a cache. The repository is the source of truth.

---

## 2. Repository Structure

Each root notebook has its own Git repository. The repository contains three JSON files:

- `structure.json` – the notebook hierarchy. Changes when items are created, moved, renamed, or deleted.
- `notes.json` – content of regular notes. Changes when a note is edited.
- `files.json` – content of file notes. Changes when a file is edited.

These files are written atomically (temporary file, flush, rename). Each write is followed by a Git commit. The commit captures the exact state of all three files at that moment.

The repository is located inside the notebook folder. There is no remote by default. Users can add a remote if they choose.

---

## 3. Commit Message Format

Every commit follows a structured format. The first line contains the action, content type, title, and context. Subsequent lines contain metadata and, for created or updated items, change statistics.

```
type: CREATED NOTE: Meeting Notes | in Work

Metadata: uuid:20260325120000 | parent:20260324120000 | root:20260323120000
```

Actions:
- `CREATED` – item created.
- `UPDATED` or `EDITED` – content changed.
- `DELETED` – item removed from current view.
- `RENAMED` – title or filename changed.
- `RESTORED` – item restored from history.
- `ERASED` – item permanently removed (tombstone).

Content types:
- `NOTE` – regular note.
- `FILE` – file note.
- `NOTEBOOK` – root notebook.
- `SUBNOTEBOOK` – subnotebook.

Metadata includes:
- `uuid` – the permanent identifier of the item.
- `parent` – the UUID of the notebook containing the item.
- `root` – the UUID of the root notebook (for multi‑notebook queries).

For created notes, the commit includes a change statistic: the number of characters added.

```
change: 247(+) totalc:247
```

For updated notes, it includes added and removed characters.

```
change: 12(+) 5(-) totalc:254
```

This format makes every commit queryable by action, by UUID, and by time.

---

## 4. Querying the Database

The system queries Git using standard commands. No external index is required.

### 4.1 By UUID

To find all commits that mention a specific UUID:

```
git log --all --grep "uuid:20260325120000"
```

This returns every commit where that UUID appears in the metadata. It includes creation, edits, renames, deletions, and restorations. The timeline engine uses this query to show the complete history of an item.

### 4.2 By Action

To find all deleted items:

```
git log --all --grep "^type: DELETED"
```

The resurrection engine uses this to locate items that were deleted. It then extracts the UUID and reconstructs the item from the commit before deletion.

### 4.3 By Action and UUID

To find all commits for a specific item that are deletions:

```
git log --all --grep "uuid:20260325120000" --grep "^type: DELETED"
```

This is used to locate the deletion commit for an item, so the timeline can show the version before deletion.

### 4.4 By Time

To find commits from the last seven days:

```
git log --all --since="7 days ago"
```

The activity view uses this to show recent changes across a notebook and its descendants.

### 4.5 By Text

To find commits whose messages contain a search term:

```
git log --all --grep "meeting"
```

The search engine uses this to find historical items that match a text query, combining it with action filters when specified.

---

## 5. Reading Historical Data

When a historical version is requested, the system reconstructs the item from the commit.

1. Retrieve `structure.json`, `notes.json`, and `files.json` from the commit using `git show`.
2. Parse the JSON. If the notebook is encrypted, decrypt using the same key (the key does not change over time).
3. Locate the item by UUID.
4. Create a minimal structure containing only that item and its content.
5. Display the result.

Reconstruction is on‑demand. The system does not pre‑load or cache historical versions.

---

## 6. Writing to the Database

Every modification to a notebook results in a commit.

- **Create a note.** Write to `notes.json` and `structure.json`. Commit with `type: CREATED NOTE`.
- **Edit a note.** Write to `notes.json`. Commit with `type: UPDATED NOTE` and change statistics.
- **Delete a note.** Remove from `structure.json` and `notes.json`. Commit with `type: DELETED NOTE`.
- **Rename a note.** Modify `structure.json`. Commit with `type: RENAMED NOTE` showing old and new names.
- **Restore a note.** Merge content into `notes.json` and add to `structure.json`. Commit with `type: RESTORED NOTE`.

Each commit is atomic. The JSON files are written atomically, then Git commits. If the commit fails, the JSON files remain unchanged. The system does not proceed if Git fails.

---

## 7. Encryption and Git

Notebooks are encrypted at rest. The JSON files are stored as encrypted blobs. Git treats them as binary files. Delta compression works on the encrypted blobs, not the plaintext.

When viewing history, the system uses the same key to decrypt the blobs. The key is derived from the folder name, which does not change. The same key works for every commit.

Encryption does not affect the queryability of commit messages. The messages themselves are not encrypted. They contain UUIDs, actions, and change statistics in plain text. This allows Git to search them without decryption.

---

## 8. Performance

- **Commits** happen on every modification. Each commit touches only the files that changed. For a note edit, only `notes.json` is written. The commit is fast.
- **Queries** use Git's internal index. `git log` with `--grep` is efficient. The system limits results to 50 to keep the interface responsive.
- **Reconstruction** happens only when the user views a historical version. No pre‑processing.
- **No background processes.** The system does not index, does not cache, does not pre‑load. It responds to user actions.

---

## 9. Why This Is Not Just Version Control

Version control is about tracking changes to files. This system treats Git as a database:

- Items have permanent UUIDs. They are tracked across renames, moves, deletions.
- Commit messages are structured and queryable.
- The system queries by UUID, by action, by time, by text.
- Historical versions are reconstructed on demand.
- Deleted items are not lost. They remain in the database until erased.
- Erasure removes them from the database, leaving a tombstone.

This is not a backup. It is not a sync tool. It is the primary storage. The working directory is a cache. The repository is the truth.

---

## 10. Design Principles

- **Immutability.** Once written, a commit is permanent. History is preserved.
- **Queryability.** Commit messages are structured for machine reading.
- **On‑demand reconstruction.** History is not pre‑computed. It is built when needed.
- **Separation of concerns.** Structure, notes, and files are separate. Changes to one do not affect the others.
- **Atomic operations.** JSON writes and Git commits are atomic. Partial failures do not corrupt state.
- **No external dependencies.** Git is the only external tool. No database, no indexer, no cache.

---

## 11. Limitations

- **Git must be installed.** The system works without Git, but history features are disabled.
- **Large repositories.** A notebook with tens of thousands of commits may slow `git log` queries. The 50‑result limit mitigates this.
- **Encrypted blobs.** Delta compression works on encrypted data, but plaintext diffs are not visible in Git.
- **No built‑in conflict resolution.** If the same notebook is modified in two clones, manual merge is required. The system does not attempt automatic merging.

---

## 12. Summary

Git is used as a temporal database. Each notebook is a repository. Each modification is a commit. Commit messages are structured with UUIDs, actions, and metadata. Queries by UUID, action, time, and text are performed with standard Git commands. Historical versions are reconstructed on demand. Deleted items remain accessible until erased. Erasure rewrites history and leaves a tombstone.

This is not a version control system used for backup. It is a database that happens to use Git as its storage engine. The working directory is a cache. The repository is the truth. Every change is recorded. Every item has a history. Nothing is lost unless it is erased.
