# Technical Description: Embedded git‑filter‑repo with Custom Filters

## A Detailed Explanation of Modifications and Subclassing for Item‑Level History Rewriting

---

## Preface

This document describes how the standard `git-filter-repo` tool has been embedded as a Python module and extended with custom filters to enable **item‑level erasure** of UUID‑identified records from Git history. The modifications allow the tool to be called programmatically from within an application, rather than as a standalone command‑line script. Custom filter classes override specific methods to scan commit messages for UUIDs and to strip those UUIDs from blob contents.

The description is factual. No claims of novelty or superiority are made. The code is open and can be inspected. The purpose is to document what has been built, not to compare it with other approaches.

---

## 1. The Original `git-filter-repo`

`git-filter-repo` is a powerful tool for rewriting Git history. It is designed to be run from the command line, typically for one‑time cleanup operations such as removing sensitive files or renaming authors. The tool works by:

1. Running `git fast-export` to stream repository data.
2. Applying filters (path, message, blob, etc.) in a Python callback architecture.
3. Feeding the filtered stream into `git fast-import` to create a new history.

The original script is not designed to be imported as a module. It has no `if __name__ == '__main__'` guard, so importing it would execute the main function immediately.

---

## 2. Modifications to Enable Import as a Module

The following change was made to `git_filter_repo.py`:

```python
if __name__ == '__main__':
    main()
else:
    # Allow importing as a module
    pass
```

**Effect:** When the file is imported (rather than executed directly), nothing runs. This allows the file to be loaded as a Python module using `importlib.util.spec_from_file_location`. The classes (`RepoFilter`, `FilteringOptions`, etc.) become available for subclassing and direct use.

---

## 3. Dynamic Loading in the Application

The application loads `git-filter-repo` dynamically from the repository root:

```python
filter_repo_path = os.path.join(os.path.dirname(__file__), "git_filter_repo.py")
if os.path.exists(filter_repo_path):
    try:
        spec = importlib.util.spec_from_file_location("git_filter_repo", filter_repo_path)
        git_filter_repo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(git_filter_repo)
        FILTER_REPO_AVAILABLE = True
    except Exception as e:
        FILTER_REPO_AVAILABLE = False
```

**Properties:**

- No external installation is required. The tool is shipped with the application.
- The tool is imported as a module, not executed as a subprocess.
- If the file is missing, erasure features are disabled gracefully.

---

## 4. Custom Filter: `UUIDEraseFilter`

The `UUIDEraseFilter` class inherits from `git_filter_repo.RepoFilter`. Its purpose is to **remove all traces of a specific UUID** from the Git history.

### 4.1 Initialisation

```python
class UUIDEraseFilter(git_filter_repo.RepoFilter):
    def __init__(self, args, uuid_to_erase):
        super().__init__(args)
        self.uuid = uuid_to_erase.encode() if isinstance(uuid_to_erase, str) else uuid_to_erase
        self.commits_removed = 0
        self.blobs_removed = 0
```

The UUID to erase is stored as a byte string for comparison with commit messages and blob contents.

### 4.2 Overriding `_tweak_commit`

This method is called for every commit during the filtering process.

```python
def _tweak_commit(self, commit, aux_info):
    if commit.message and self.uuid in commit.message:
        # Skip ERASED commits (preserve tombstones)
        if b"ERASED" not in commit.message:
            commit.skip()
            self.commits_removed += 1
            return
    super()._tweak_commit(commit, aux_info)
```

**Logic:**

1. Check if the commit message contains the target UUID.
2. If it does, and the message does **not** already contain `ERASED` (preserving tombstone commits), skip the commit entirely.
3. Otherwise, call the parent method for normal processing.

**Why this works:** Commit messages contain UUIDs in the `Metadata: uuid:...` line. By removing any commit that mentions the UUID, the item is erased from history.

### 4.3 Overriding `_tweak_blob`

This method is called for every blob (file content) during filtering.

```python
def _tweak_blob(self, blob):
    if blob.data and self.uuid in blob.data:
        blob.data = blob.data.replace(self.uuid, b'')
        self.blobs_removed += 1
    super()._tweak_blob(blob)
```

**Logic:**

1. Check if the blob data contains the UUID as a substring.
2. If so, replace the UUID with an empty byte string (effectively removing it).
3. Call the parent method.

**Why this is necessary:** The UUID may appear inside JSON files (`notes.json`, `structure.json`) as a key or value. Stripping it from the blob data ensures that even after the commit is removed, no residual copy remains in other commits.

### 4.4 Running the Filter

The filter is instantiated and executed:

```python
args = git_filter_repo.FilteringOptions.parse_args(["--force", "--uuid-erase", uuid], error_on_empty=False)
filter = UUIDEraseFilter(args, uuid)
filter.run()
```

---

## 5. Custom Filter: `NotebookEraseFilter`

This filter removes **all commits belonging to an entire notebook hierarchy**.

### 5.1 Initialisation

```python
class NotebookEraseFilter(git_filter_repo.RepoFilter):
    def __init__(self, args, notebook_uuid, all_uuids):
        super().__init__(args)
        self.notebook_uuid = notebook_uuid.encode()
        self.all_uuids = [u.encode() for u in all_uuids]
        self.commits_removed = 0
```

### 5.2 Overriding `_tweak_commit`

```python
def _tweak_commit(self, commit, aux_info):
    full_message = commit.message or b''

    # Check for root UUID pattern
    root_pattern = b'root:' + self.notebook_uuid
    if root_pattern in full_message:
        commit.skip()
        self.commits_removed += 1
        return

    # Check for any UUID from this notebook
    for uuid in self.all_uuids:
        uuid_pattern = b'uuid:' + uuid
        if uuid_pattern in full_message:
            commit.skip()
            self.commits_removed += 1
            return

    super()._tweak_commit(commit, aux_info)
```

**Logic:**

- Any commit whose message contains `root:<notebook_uuid>` is removed (the entire notebook hierarchy).
- Any commit whose message contains `uuid:<any_descendant_uuid>` is also removed.
- Other commits pass through unchanged.

This ensures that the entire notebook – all notes, files, subnotebooks, and their history – is erased in one pass.

---

## 6. Safety Features

| Feature | Implementation |
|---------|----------------|
| **Path validation** | The filter never runs on the project root. |
| **Availability check** | `FILTER_REPO_AVAILABLE` flag disables erasure if the module is not found. |
| **Confirmation prompt** | User must type `erase` before proceeding. |
| **Tombstone commit** | After erasure, a commit with `type: ERASED` is added to mark the deletion. |
| **Rollback** | During restoration, backups are created before merging; if anything fails, backups are restored. |

---

## 7. Integration with the Application

The erasure process is triggered from the application's user interface. The user does not need to know about `git-filter-repo`, Git commands, or history rewriting. They simply select an item, choose "erase", and type `erase` to confirm.

The filter runs as a library call, not as an external process. The application can track progress, handle errors, and update the UI accordingly.

---

## 8. Why This Works (Technical Summary)

| Requirement | How It Is Satisfied |
|-------------|---------------------|
| **Item‑level erasure** | UUIDs are embedded in commit messages. `UUIDEraseFilter` removes commits containing the UUID. |
| **Blob cleaning** | `_tweak_blob` removes UUIDs from file contents. |
| **Notebook‑level erasure** | `NotebookEraseFilter` scans for `root:` and `uuid:` patterns. |
| **Safety** | The filter skips commits containing `ERASED` (preserving tombstone markers). |
| **Embedding** | The tool is imported as a module, not executed as a subprocess. |
| **No external dependency** | The tool is shipped with the application. |

---

## 9. Limitations and Trade‑offs

- **Irreversible.** Once erased, data cannot be recovered (by design).
- **Collaborator impact.** If the repository is shared, erasure rewrites history, affecting clones.
- **Performance.** Rewriting history for large repositories may take time.
- **Commit signatures.** GPG signatures are invalidated by history rewriting.

These trade‑offs are acceptable for the application's threat model: a single user who needs GDPR‑compliant erasure and is willing to accept the consequences.

---

## 10. Conclusion

The embedded `git-filter-repo` module, extended with custom `UUIDEraseFilter` and `NotebookEraseFilter` classes, enables **surgical, item‑level erasure** of UUID‑identified records from Git history. The tool is no longer a dangerous command‑line script; it is a controlled, integrated feature of the application.

The modifications are minimal: an `if __name__ == '__main__'` guard to allow importing, and two custom filter classes that override `_tweak_commit` and `_tweak_blob`. The result is a powerful, user‑friendly erasure mechanism that complies with the "right to be forgotten" requirements of data protection regulations.

The code is open. The behaviour is observable. The reader may inspect the source for verification.

---
