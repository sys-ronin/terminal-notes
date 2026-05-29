# Data Safety Architecture

## Overview

This document describes how the system ensures data is never lost, never corrupted, and always recoverable. It covers encryption in memory before writing, atomic file operations, separation of keys from data, portability of notebooks, the application itself, and the permanent erasure mechanism. The design prioritises safety over convenience, explicitness over automation, and verifiability over opacity.

The current version adds: **portable vault files** (keys can be stored anywhere), **active cache validation** (missing vault invalidates keys immediately), **missing vault recovery** (user‑guided resolution), **trusted devices management** (list and revoke machines), and **ephemeral hardware fingerprints** (Docker, cloud containers).

---

## 1. Encryption in Memory Before Write

### 1.1 When Encryption Happens

Encryption occurs only at the moment of writing to disk. Data is held in memory as plaintext while the user is working. This is necessary because the user needs to read and edit the content. The key is also held in memory while the notebook is unlocked.

When a note is edited:

1. The note content is in memory as plaintext.
2. The user saves. The content is written to a temporary file.
3. The temporary file is encrypted using the notebook's key (Ks).
4. The encrypted temporary file is renamed to the final file.

The key is cleared from memory when the notebook is locked (explicit), or when the `SessionKeyVault` cache is invalidated (vault missing), or when the application exits.

### 1.2 Why Not Encrypt in Memory

Encrypting in memory would require keeping the encrypted data alongside the plaintext or re‑encrypting on every access. It would add complexity without adding safety. The threat model assumes that if an attacker has access to memory, they also have access to the key. Keeping the key in memory is the necessary risk. The lock button is the explicit control to clear that risk when the notebook is not in use.

---

## 2. Atomic Writes

### 2.1 The Problem

Writing directly to a file risks partial writes. If the system crashes during the write, the file may be left half‑written, corrupted, or empty. This is unacceptable for data that must never be lost.

### 2.2 The Solution

Every JSON file is written using an atomic pattern:

1. Write to a temporary file in the same directory (`file.json.tmp`).
2. Call `os.fsync()` to force the data to disk.
3. Rename the temporary file to the final name (`file.json`).

On Unix systems, rename is atomic. If the system crashes during the write, the temporary file may be incomplete, but the original file remains untouched. If the system crashes during the rename, the file either has the old content or the new content. There is no intermediate state.

This pattern is used for `structure.json`, `notes.json`, `files.json`, the master registry, the vault registry, and the vault files themselves.

### 2.3 Recovery

After a crash, the system starts with the files as they were before the interrupted write. No recovery action is needed. The temporary files are left behind and are ignored.

---

## 3. Separation of Keys from Data

### 3.1 Where Keys Are Stored

Keys are **never stored in plain text**. They are stored in **vault files** (`.vault` or `session.vault`). Each vault file is a JSON dictionary mapping an entry UUID to an encrypted blob containing the combined password key (Kp) and phrase key (Ks), plus a nonce and timestamp.

The vault file can be stored **anywhere**: local disk, USB, network share, S3 bucket, WebDAV server. Its location is recorded in a small `vaults_registry.json` that maps a vault name to a path or URL.

The master registry (`notebooks_registry.json`) maps a system fingerprint → notebook UUID → (vault name, entry UUID, folder path).

### 3.2 Why Separate

- **If a notebook folder is copied to another machine, the vault does not travel with it.** The encrypted data is useless without the vault entry (and the hardware fingerprint to decrypt it).
- **If the vault file is stored on a separate USB, unplugging that USB instantly invalidates the in‑memory key cache.** The system will detect the missing vault and refuse further operations until it is restored or a recovery is performed.
- **If the vault file is stored on a network share or cloud object storage**, the security relies on the hardware fingerprint, not on the transport layer. Even if the vault is intercepted, it cannot be decrypted without the original machine’s fingerprint.

### 3.3 Portability of Notebooks

A notebook folder can be copied, moved, or synced to any location. It contains only encrypted data. The keys are **not** inside. The folder can be backed up, shared, or stored in the cloud without exposing the content.

To open the notebook on another machine, the user must either:

- Have a copy of the vault file **and** be on the original machine (fingerprint matches), or
- Enter the recovery phrase (which recreates the vault entry on the new machine).

The notebook travels. The keys do not travel unless explicitly carried (vault file on USB) or recreated (phrase).

---

## 4. Application Portability

### 4.1 No Installation

The application is distributed as a folder. It contains:

- The Python source or compiled executable.
- The `assets` folder with bundled cryptography and cffi.
- A `config.json` for user preferences.

The user copies the folder. It runs. No installation. No registry entries. No system dependencies beyond Python and Git (which are widely available).

### 4.2 Data and Vault Locations

All user data is stored inside the same folder by default, but can be relocated:

- `config/` – default session vault (`session.vault`), master registry, vault registry, Git accounts.
- `notebooks_root/` – notebooks and master registry.
- `.recovery/` – recovery files from unsaved edits.

**Custom vaults** can be created anywhere (USB, network share, cloud). The `vaults_registry.json` stores the location. The user can change a notebook’s vault at any time (the vault entry is migrated, keys are preserved).

The entire application folder can be backed up by copying it. It can be moved to another machine and run. The user’s notebooks, settings, and vault registries move with it. The only thing that does not move is the **hardware fingerprint** used to decrypt vault entries – but the recovery phrase can recreate them.

### 4.3 No External Dependencies

The application bundles its own cryptography and cffi. It does not require the user to install them. It does not require internet to install them. It does not require root or admin privileges. It runs from the folder. It is portable.

---

## 5. Active Cache Validation and Missing Vault Recovery

### 5.1 The SessionKeyVault

The `SessionKeyVault` is a transparent dict‑like cache that stores decrypted `Crypto` objects (keys) for unlocked notebooks. Unlike a conventional cache, it **validates the existence of the underlying vault file before every cache hit**:

```python
if notebook_id in self._cache:
    vault_path = self.manager._get_vault_path(notebook_id)
    if vault_path and os.path.exists(vault_path):
        return self._cache[notebook_id]
    else:
        del self._cache[notebook_id]   # immediate invalidation
```

If the vault file is missing (USB unplugged, network share unmounted, file deleted), the cached entry is deleted instantly. No subsequent operation can use stale keys.

### 5.2 Missing Vault Recovery

When the system needs to unlock a notebook and the vault file is missing (no cache, and vault not found), it presents a user dialog with options:

1. **Retry** – after re‑inserting the missing device or restoring network access.
2. **Locate vault file manually** – user provides a new path or URL; the registry is updated.
3. **Use recovery phrase** – recreates the vault entry (prompts for phrase, creates new entry in a chosen vault).
4. **Cancel** – aborts the operation.

The system can recover from loss of any single component (vault file, notebook folder, app instance) without data loss. Only the recovery phrase is irreplaceable.

---

## 6. Trusted Devices Management

### 6.1 Per‑Machine Vault Entries

Each machine that ever unlocks a notebook creates its own entry in the vault file. The vault may contain entries for many machines (e.g., home desktop, work laptop, USB‑carried instance). Each entry is encrypted with that machine’s hardware fingerprint.

The system provides a user interface (`_show_trusted_devices`) that:

- Lists all trusted devices (hostname, creation timestamp, active status)
- Marks the current machine
- Allows the user to **remove any entry**, including the current machine’s own entry

### 6.2 Revocation

Removing the current machine’s entry:

- Immediately locks the notebook
- Clears all cached keys from memory (`SessionKeyVault`)
- Removes the system’s entry from the vault
- The notebook can only be unlocked again using the recovery phrase

Removing another machine’s entry simply deletes that entry; that machine can no longer unlock the notebook (unless it has a separate copy of the vault with its own entry – the user must propagate the updated vault file to revoke across machines).

No central server is involved. This is a **decentralized, offline‑first device revocation mechanism**.

---

## 7. Permanent Erasure with git‑filter‑repo

### 7.1 Two‑Tier Deletion

- **Forget (soft delete).** The item is removed from the current view. The Git history remains. The item can be restored.
- **Erase (hard delete).** The item is removed from Git history. It cannot be restored. A tombstone commit remains to mark the erasure.

### 7.2 How Erasure Works

The system uses a customised version of `git-filter-repo`, imported as a module, not called as a subprocess.

For a single item:

1. The system finds all commits that mention the UUID.
2. It runs `UUIDEraseFilter`, which removes those commits and strips the UUID from file content.
3. It adds a tombstone commit with `type: ERASED`.

For an entire notebook:

1. The system collects all UUIDs in the notebook and its descendants.
2. It runs `NotebookEraseFilter`, which removes every commit that mentions any of those UUIDs.
3. It deletes the notebook folder.
4. It removes the notebook’s vault entries from **all** vault files listed in the master registry.

The erasure is irreversible. The user must confirm by typing “erase” before the operation proceeds.

### 7.3 Why git‑filter‑repo Is Embedded

The tool is embedded as a module so that it can be extended with custom filters and called programmatically. The system does not rely on the user having it installed. It does not spawn a subprocess. The erasure is integrated into the application, not a separate script.

---

## 8. Recovery from Crash

### 8.1 During Editing

When an external editor is open, a background thread saves the content every 30 seconds to a recovery file. The recovery file is named with the note’s UUID and title. It is stored in `.recovery/` inside the application folder.

If the editor crashes, the system closes, or the machine loses power, the recovery file remains.

### 8.2 On Next Open

When the notebook is opened, the system scans `.recovery/` for files matching the UUIDs of notes in the notebook. For each match:

- If the note exists, the recovery content is compared to the saved content. If newer, it is restored.
- If the note does not exist, the recovery content is used to create a new note.

The recovery file is deleted after restoration. The user does not need to know that recovery happened.

---

## 9. Integrity Checks

### 9.1 Master Registry

The master registry (`notebooks_registry.json`) is the source of truth for which notebooks exist and where they are located, as well as the mapping from system fingerprint to vault and entry UUID. It is encrypted for encrypted notebooks. The system checks on startup that the paths in the registry exist. If a path is missing, the notebook is marked as missing but not removed. The user can later re‑import it.

### 9.2 Vault Registry

The vault registry (`vaults_registry.json`) maps vault names to absolute paths or URLs. It is **not encrypted** (only contains metadata, no keys). The system validates that the path exists when resolving a vault name; if missing, it triggers the missing vault recovery flow.

### 9.3 Session Storage (Vault File)

Vault files are encrypted binary formats (version 5). On startup, the system reads the vault file (local or via HTTP). If it is corrupted or cannot be decrypted (wrong hardware fingerprint), the system treats it as missing – it will not use stale entries.

### 9.4 Notebook Structure

Each notebook’s `structure.json` is read on unlock. If it is corrupted (unreadable JSON or missing UUIDs), the notebook cannot be unlocked. The user must restore from backup or Git history.

---

## 10. Portability and Ephemeral Fingerprints

### 10.1 Running in Docker / Cloud

The hardware fingerprint is derived at runtime from the execution environment (machine ID, hostname, container ID, etc.). When the application runs inside a Docker container or a cloud VM, the fingerprint is **ephemeral** – it changes when the container is recreated.

If the user stores a vault entry for that container, the entry becomes undecryptable after the container is destroyed. This is intentional: it allows **stateless, ephemeral workloads** where keys die with the container.

### 10.2 Three‑Component Separation

The system can be split across three independent locations:

- **Application** (executable + registries) – can be on a USB drive.
- **Vault file** (keys) – can be on a separate USB, network share, or cloud bucket.
- **Notebook folder** (encrypted data) – can be on local disk, another USB, or public Git repository.

The system resolves the paths via the registries. Loss of any single component does not cause data loss (recovery phrase can recreate the missing parts).

---

## 11. Design Principles

- **Atomicity.** Every write is atomic. No partial writes. No corruption.
- **Separation.** Keys are separate from data. Vaults are separate from notebooks. The application is separate from both.
- **Explicitness.** The lock button is explicit. Erasure requires confirmation. Trusted device removal requires confirmation. Missing vault triggers user‑guided recovery.
- **Verifiability.** The master registry is the source of truth. The vault registry is the source for key store locations. Git is the history. The user can inspect all.
- **Portability.** The application runs from a folder. Notebooks run from a folder. Vaults can be anywhere. No installation. No system dependencies.
- **Active validation.** The key cache checks the vault’s existence before every use. Stale keys are impossible.

---

## 12. Limitations

- **No automatic backup.** The system does not back up data. The user must copy the folders.
- **No conflict resolution.** If the same notebook is modified in two locations, manual merge is required.
- **Vault entries are machine‑bound.** Moving a notebook to another machine requires the recovery phrase (or copying the vault file and having the same hardware fingerprint – rare).
- **Erasure is irreversible.** Once erased, data cannot be recovered. The user confirms.
- **Git required for history.** Without Git, resurrection, timeline, and activity are disabled. The core remains.
- **Recovery phrase is single point of failure.** If lost, the data cannot be recovered (by design).

---

## 13. Summary

Data is encrypted only when written to disk. Writes are atomic. Keys are stored in portable vault files that can be anywhere. The in‑memory key cache validates vault existence before every use; missing vault invalidates immediately. User‑guided recovery handles missing vaults. Trusted devices can be listed and revoked. Notebooks are portable; vaults are portable; the application is portable. Deleted items are soft‑deleted (restorable) or hard‑erased (with tombstone) using an embedded `git-filter-repo`. Recovery from crash is automatic. The system does not lose data unless the user explicitly erases it. It does not corrupt data. It does not require external tools. It is designed for safety, portability, and verifiability.

The addition of active cache validation, missing vault recovery, trusted devices management, and ephemeral container fingerprints makes the system **resilient to component loss** – no single piece (USB, network share, cloud bucket) is critical. Only the recovery phrase is irreplaceable.
```
