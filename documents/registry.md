# Code, Artifacts, and Their Relationships in Terminal Notes

## A Technical Map of the System’s Data Flow

This document describes how the different code modules, registry files, vaults, notebook data, and Git components interact. It is based on direct observation of the source code and the artifacts it produces. The purpose is to provide a clear map of the relationships that make the system work.

No claim of novelty or superiority is made. This is a descriptive document, not a prescriptive one.

---

## 1. Overview of Components

| Component | Code Modules | Artifacts | Role |
|-----------|--------------|-----------|------|
| **Master Registry** | `NoteManager` (in `terminal_notes_core.py`) | `notebooks_registry.json` | Maps system fingerprint → notebook UUIDs; notebook UUID → (vault name, entry UUID, folder path). |
| **Vault Registry** | `VaultManager` | `vaults_registry.json` | Maps vault name → absolute path or URL to the vault file. |
| **Vault File** | `SecureSessionStorage`, `VaultManager` | `*.vault` or `session.vault` | Contains dictionary: entry UUID → (encrypted keys, nonce, timestamp). |
| **Notebook Data** | `Notebook`, `Note`, `NotebookOperations` | `structure.json`, `notes.json`, `files.json`, `.tn_test`, `.tn_recovery`, `.tn_password` | Stores encrypted hierarchy, content, and encryption verification files. |
| **Git Repository** | `GitManager` | `.git` directory inside notebook folder | Stores commit history; commit messages contain UUIDs and action types. |
| **Session Key Cache** | `SessionKeyVault` | In‑memory (no persistent artifact) | Caches decrypted `Crypto` objects for unlocked notebooks; validates vault existence before each use. |

---

## 2. Code Modules and Their Responsibilities

### 2.1 `terminal_notes_core.py`
- Defines `Note`, `Notebook`, `NoteManager`, `SimpleNav`.
- `NoteManager` owns the master registry (`load_registry`, `save_registry`), the `session_keys` cache (a `SessionKeyVault` instance), and the list of notebooks.
- `get_crypto()` orchestrates the resolution chain: fingerprint → master registry → vault name → vault file → entry UUID → keys.
- `_get_vault_path()` uses `VaultManager` to resolve a vault name to a file path or URL.

### 2.2 `vault_manager.py`
- Manages the vault registry (`vaults_registry.json`).
- Provides methods: `get_vault_path(vault_name)`, `create_vault(location)`, `add_entry_to_vault()`, `get_entry_from_vault()`, `remove_entry_from_vault()`.
- Reads and writes vault files (JSON dictionaries) atomically.

### 2.3 `secure_session.py`
- Implements `SecureSessionStorage`, which reads/writes the vault file (binary format) and handles encryption/decryption of entries using the hardware fingerprint.
- The fingerprint is derived at runtime from machine identifiers and never stored.
- Each entry is stored under an entry UUID; the entry contains the encrypted combination of password key (Kp) and phrase key (Ks).

### 2.4 `session_key_vault.py`
- Implements `SessionKeyVault`, a dict‑like object that acts as a transparent cache.
- On `__getitem__`, it checks the in‑memory cache; if present, it validates that the underlying vault file still exists (via `_get_vault_path`). If the vault is missing, the cache entry is deleted.
- If not cached, it calls `_get_crypto_from_vault` (from `NoteManager`) to load the keys from the vault, then caches the result.

### 2.5 `notebook_operations.py`
- Contains `NotebookOperations`, which handles low‑level file I/O for notebooks.
- `save_notebook()` writes `structure.json`, `notes.json`, `files.json` using `write_json()` (which encrypts if a crypto object is provided).
- `edit_note()`, `create_note()`, `delete_note()` call `save_notebook` and `_git_commit`.

### 2.6 `git_manager.py`
- `GitManager` manages Git operations inside a notebook folder.
- `commit_note_creation()`, `commit_note_edit()`, etc. generate structured commit messages containing UUIDs, action types, and change statistics.
- The repository is stored inside the notebook folder.

### 2.7 `crypto.py`
- Implements key derivation (SHA256), AES‑GCM encryption/decryption, and the creation of `.tn_test`, `.tn_recovery`, `.tn_password`.
- The `Crypto` object holds the three keys (Kp, Ks, Kc) and provides encryption methods.

---

## 3. Relationships Between Artifacts

### 3.1 Master Registry → Vault Name → Vault Registry → Vault File

```
master registry: notebook UUID → (vault name, entry UUID, folder path)
                                   ↓
vault registry: vault name → vault file path (local or URL)
                                   ↓
vault file: entry UUID → (encrypted keys, nonce, timestamp)
```

**This is the primary resolution chain for obtaining decryption keys.**

### 3.2 Master Registry → Notebook Folder

```
master registry: notebook UUID → folder path
                                   ↓
notebook folder: structure.json, notes.json, files.json
```

**The folder path can be relative to `notebooks_root` or absolute.**

### 3.3 Notebook Folder → Git Repository

```
notebook folder/
├── .git/          ← Git repository
├── structure.json
├── notes.json
├── files.json
└── .tn_*
```

**Git commits record changes to these files and embed UUIDs in commit messages.**

### 3.4 SessionKeyVault ↔ Vault File

```
SessionKeyVault (in‑memory cache)
        ↓ (on cache miss)
_get_crypto_from_vault() → reads vault file, decrypts entry → returns Crypto object
        ↓ (on cache hit before return)
checks that vault file still exists; if missing, invalidates cache.
```

**The vault file must be present for the cache to be valid. The cache is not a trust anchor; it is a convenience that is actively validated.**

### 3.5 .tn_ Files ↔ Crypto Object

| File | Encrypted with | Contains |
|------|----------------|----------|
| `.tn_test` | Ks | "VERIFICATION" (used to test phrase) |
| `.tn_recovery` | Ks | Kp (hex) |
| `.tn_password` | Kc (self‑referential) | Kc (hex) |

**These files are stored inside the notebook folder and are used for recovery and verification.**

---

## 4. Data Flow for a Typical Operation (e.g., Edit Note)

The following sequence shows how the components interact. Numbers correspond to steps.

1. **User action** → UI calls `NoteManager.edit_note()`.
2. `NoteManager` delegates to `NotebookOperations.edit_note()`, which updates the in‑memory `Note` object.
3. `NotebookOperations.save_notebook()` is called with `save_notes=True`.
   - It obtains the decryption keys via `self.manager.session_keys[notebook.id]` (which triggers `SessionKeyVault.__getitem__`).
   - `SessionKeyVault` checks its cache. If not present, it calls `NoteManager._get_crypto_from_vault()`.
   - `_get_crypto_from_vault()` uses the master registry and vault registry to resolve the vault file path and entry UUID, then reads the vault file (via `VaultManager`), decrypts the entry using the hardware fingerprint (via `SecureSessionStorage`), and returns a `Crypto` object.
   - The `Crypto` object is cached in `SessionKeyVault`.
4. `save_notebook` writes `notes.json` (and `structure.json`) using `write_json()`, which encrypts the JSON data with the `Crypto` object’s Ks.
5. `NotebookOperations._git_commit()` calls `GitManager.commit_note_edit()`, which stages the changed files and creates a commit with a message containing the note UUID, change statistics, and parent/root UUIDs.
6. The commit is recorded in the Git repository inside the notebook folder.

**All components work together without a central coordinator. The resolution chain is deterministic; the order is fixed by the code.**

---

## 5. Component Independence and Portability

| Artifact | Can Be Stored Independently | Resolution Mechanism |
|----------|----------------------------|----------------------|
| **Master registry** | Yes (local disk, network share) | Direct file read |
| **Vault registry** | Yes (local disk, network share) | Direct file read |
| **Vault file** | Yes (any reachable URL or path) | Lookup via vault registry, then HTTP GET or file read |
| **Notebook folder** | Yes (any reachable path) | Lookup via master registry |
| **Git remote** | Yes (any Git URL) | `git clone` or `git pull` |

Because each artifact is addressed by a path or URL, the system can be distributed across multiple storage locations without changing the code. The only requirement is that the registries (which are small) are accessible.

---

## 6. Summary of Key Relationships

| Relationship | Implemented In | Artifact(s) Involved |
|--------------|----------------|----------------------|
| Fingerprint → notebook list | Master registry | `notebooks_registry.json` |
| Notebook UUID → vault name, entry UUID, folder path | Master registry | `notebooks_registry.json` |
| Vault name → vault file path | Vault registry | `vaults_registry.json` |
| Entry UUID → encrypted keys | Vault file | `*.vault` or `session.vault` |
| Notebook folder → structure, notes, files | Filesystem | `structure.json`, `notes.json`, `files.json` |
| Notebook folder → Git history | Git repository | `.git/` |
| .tn\_* files → key verification | Notebook folder | `.tn_test`, `.tn_recovery`, `.tn_password` |
| In‑memory cache ↔ vault file | `SessionKeyVault` | `session_keys` cache and vault file |

All relationships are **static** (stored in files) and **deterministic** (the resolution steps are fixed). There is no dynamic service discovery, no central coordinator, and no background process.

---

## 7. Conclusion

The system is built on a small set of independent components that communicate through shared artifacts (JSON files, vault files, Git commits). The code modules each have a clear responsibility, and the overall behavior emerges from the deterministic order in which they are invoked. The relationships between artifacts are captured in registries and UUID pointers, making the entire system portable and resilient to component loss.

The code is open. The artifacts are self‑describing. The reader may verify each relationship by inspecting the source and the files it produces.

```
