# Secure Session Storage: Zero‑Trust, Portable Key Cache (Current Implementation)

## Scope

This document describes the secure session storage system as implemented in the provided codebase (files: `secure_session.py`, `vault_manager.py`, `terminal_notes_core.py`, `session_key_vault.py`, `change_notebook.py`). It focuses on how cryptographic keys are cached across application restarts, how per‑machine entries are stored, and how the live cache (`SessionKeyVault`) acts as a proxy to the binary vault.

No comparisons with other systems are made. The description is aligned with the actual code.

---

## Problem Restatement

An encrypted notebook uses two derived keys:

- **`Kp`** = `SHA256(password + b':' + folder_name)` – used for daily authentication.
- **`Ks`** = `SHA256(phrase + b':' + folder_name)` – used for actual content encryption.

The user wants to unlock the notebook with only their password after the first unlock on a given machine. The system must not store `Ks` or `Kp` in plain text, cannot rely on a cloud service, and must be portable yet machine‑bound.

---

## Architecture Overview

The system consists of three layers:

1. **Binary Vault File** (`.vault`) – stores encrypted entries, each containing `Kp` and `Ks` for a specific notebook and a specific machine. The vault file is managed by `VaultManager`.
2. **Master Registry** (`notebooks_registry.json`) – stores per‑system metadata: which vault file contains the entry, the entry UUID, and the lock state (`locked` flag).
3. **In‑Memory Proxy Cache** (`SessionKeyVault`) – a dictionary‑like object that holds **only unlocked** keys in RAM. It reads from the vault on demand and writes back when keys are updated.

This design separates the persistent encrypted storage (vault) from the live cache, and adds a master registry to support multiple vaults (e.g., default on internal drive, custom on USB).

---

## The Binary Vault File (Version 2)

The vault file (e.g., `session.vault`) uses a custom binary format implemented in `VaultManager.read_vault_file()` and `write_vault_file()`. The structure is:

```
[4 bytes] version = 2
[4 bytes] number_of_entries (N)
For each entry (1..N):
    [4 bytes] entry_uuid_length
    [variable] entry_uuid (UTF‑8 string, e.g., "550e8400‑e29b‑41d4‑a716‑446655440000")
    [4 bytes] notebook_id_length
    [variable] notebook_id (UTF‑8 string, plain text – not secret, used for lookup)
    [8 bytes] timestamp (Unix nanoseconds)
    [4 bytes] nonce_length (always 12)
    [12 bytes] nonce
    [4 bytes] encrypted_keys_length
    [variable] encrypted_keys (AES‑256‑GCM ciphertext of combined keys)
```

The file is **not** encrypted as a whole. Each entry is individually encrypted. The notebook_id is stored in plain text to allow fast locating of entries belonging to a notebook. The entry UUID is a unique identifier used by the master registry to reference this entry.

---

## Entry Encryption

Each entry stores the concatenation of `Kp` (32 bytes) and `Ks` (32 bytes), encrypted with AES‑256‑GCM. The encryption key is derived at runtime:

```python
encryption_key = SHA256(str(timestamp) + fingerprint)
```

Where:

- `timestamp` is the Unix nanosecond timestamp stored in the entry header.
- `fingerprint` is a 32‑byte value derived from hardware identifiers (machine‑id, product UUID, hostname, etc.) in `SecureSessionStorage._generate_system_fingerprint()`. The fingerprint is **never stored** on disk; it is recomputed on every application start.

The nonce is random (12 bytes) and stored in the entry header.

Decryption requires the correct `timestamp` and the current machine's fingerprint. If either is wrong, decryption fails (raises `InvalidTag`).

---

## Master Registry (`notebooks_registry.json`)

The master registry (managed by `NoteManager.load_registry()`) stores per‑notebook, per‑system entries. Its structure (simplified):

```json
{
  "version": 2,
  "system_index": { "fp_hash": "system_name" },
  "notebooks": {
    "notebook_id": {
      "name": "My Notebook",
      "systems": {
        "fp_hash": {
          "path": "relative/path/to/folder",
          "vault": "default",
          "entry": "550e8400-...",
          "locked": false,
          "system_name": "hostname"
        }
      }
    }
  }
}
```

- `fingerprint_hash` (`fp_hash`) is `SHA256(fingerprint + system_name)[:16]` – a short identifier for the current system.
- `vault` is the name of the vault file (e.g., `"default"` or `"vault_abc123"`).
- `entry` is the UUID of the entry inside that vault.
- `locked` indicates whether the notebook is locked on this system (`true` means the keys are not cached in RAM; the user must unlock).

When the user unlocks a notebook on a system, the master registry is updated with `locked: false` and the entry UUID is stored. When the user locks it, `locked: true` is set, but the vault entry remains.

---

## Live Proxy Cache: `SessionKeyVault`

`SessionKeyVault` (in `session_key_vault.py`) is a dictionary‑like object that serves as an in‑memory cache for **unlocked** crypto keys. Its behaviour:

- **`__getitem__(notebook_id)`** :  
  - First checks the internal `_cache` dict.  
  - If not cached, it calls `NoteManager._get_crypto_from_vault(notebook_id)`, which reads the master registry to locate the vault and entry UUID, decrypts the entry using the current fingerprint, and returns the `Crypto` object.  
  - The result is stored in `_cache` for future access.

- **`__setitem__(notebook_id, crypto)`** :  
  - Stores the `crypto` in `_cache`.  
  - Also writes the keys back to the vault (calls `NoteManager._write_crypto_to_vault()`). This updates the entry for the current system with the same UUID, preserving it for other systems.

- **`lock(notebook_id)`** :  
  - Removes the entry from `_cache` (RAM).  
  - Does **not** delete the vault entry; the keys remain in the vault for future unlocks.

- **`unlock(notebook_id, crypto)`** :  
  - Adds the `crypto` to `_cache` (does not write to vault again unless the keys changed).

Thus, `SessionKeyVault` acts as a **proxy** that lazily loads keys from the vault and caches them only while the notebook is unlocked.

---

## First‑Time Unlock on a New Machine

When a notebook is opened on a machine that has no entry in the master registry for that system, the user is prompted for the **recovery phrase** (implemented in `SecureSessionStorage._recover_with_phrase()`):

1. User enters the 12‑word recovery phrase.
2. `Ks` is derived from the phrase and folder name.
3. The system decrypts `.tn_recovery` (encrypted with `Ks`) to obtain `Kp`.
4. Both keys are verified using `.tn_password` (encrypted with `SHA256(Kp + Ks)`).
5. A new entry is created in the **default vault** (or a specified vault):
   - A new UUID is generated.
   - The current `timestamp` and a fresh nonce are used.
   - The combined `Kp + Ks` is encrypted with `SHA256(timestamp + fingerprint)`.
   - The entry is added to the vault file.
6. The master registry is updated with the new system entry (`locked: false`, `vault: "default"`, `entry: <uuid>`).
7. The `Crypto` object is stored in `SessionKeyVault._cache`.

Future unlocks on the same machine will use the normal password flow.

---

## Normal Unlock (Machine Already Trusted)

When a notebook is opened on a machine that already has a system entry in the master registry with `locked: false`, the process is:

1. `SessionKeyVault[notebook_id]` is accessed.
2. `NoteManager._get_crypto_from_vault()` reads the master registry to obtain the vault name and entry UUID.
3. The vault file is read, and the entry is decrypted using the current fingerprint (the `timestamp` is known from the entry header).
4. The decrypted `Kp` and `Ks` are used to create a `Crypto` object.
5. The user is prompted for their **password** (not the phrase). `Kp_entered` is derived and compared with the decrypted `Kp`.
6. `.tn_password` is verified as a two‑factor check.
7. If successful, the `Crypto` is placed in `SessionKeyVault._cache` and the notebook unlocks.

No recovery phrase is required.

---

## Password Change

When the user changes the password on a trusted machine (via `ChangeNotebookHandler._change_password_with_old()` or `_change_password_with_phrase()`):

1. The old `Kp` and `Ks` are obtained (using the normal unlock flow).
2. The new password is used to derive `Kp_new`.
3. The system calls `NoteManager._write_crypto_to_vault(notebook_id, new_crypto)`, which:
   - Looks up the existing entry UUID from the master registry.
   - Re‑encrypts the combined keys (`Kp_new + Ks`) with a **new timestamp** and a new nonce.
   - Overwrites the entry in the vault (the same UUID is used, but the ciphertext and nonce change).
4. The `.tn_recovery` and `.tn_password` files are updated on disk.
5. The notebook is then locked (the user must re‑unlock with the new password).

Other machines that have their own entries will still have the old `Kp` cached. When they next unlock, the password check will fail because `Kp_entered` will not match the decrypted `Kp`. The system will fall back to the recovery phrase flow, create a new entry for that machine, and update its master registry entry.

---

## Trusted Devices View

The `ChangeNotebookHandler._show_trusted_devices()` method lists all machines that have an entry for a given notebook. It does this by:

- Scanning the master registry for the notebook.
- For each system fingerprint hash, reading the corresponding vault and entry UUID.
- Decrypting the entry (requires the current machine's fingerprint – but the entry's metadata, such as `timestamp`, can be read without decryption). The system name is stored in the master registry, so it can be displayed even without decrypting the entry.

The user can remove a trusted device, which:
- Deletes the entry from the vault.
- Removes the system entry from the master registry.
- If the current machine is removed, the notebook is immediately locked.

---

## Code References (Current Implementation)

| Component | File | Key Methods |
|-----------|------|--------------|
| Binary vault I/O | `vault_manager.py` | `read_vault_file()`, `write_vault_file()`, `add_entry_to_vault()`, `get_entry_from_vault()`, `remove_entry_from_vault()` |
| Vault registry | `vault_manager.py` | `load_vault_registry()`, `get_vault_path()`, `set_vault_path()` |
| Master registry | `terminal_notes_core.py` | `load_registry()`, `save_registry()`, `_get_current_system_entry()`, `_update_system_entry()` |
| Live proxy cache | `session_key_vault.py` | `__getitem__`, `__setitem__`, `lock()`, `unlock()`, `clear_cache()` |
| Fingerprint derivation | `secure_session.py` | `_get_system_fingerprint()`, `_generate_system_fingerprint()` |
| Recovery phrase flow | `secure_session.py` | `_recover_with_phrase()`, `get_keys_with_verification()` |
| Unlock flow | `terminal_notes_core.py` | `get_crypto()`, `_get_crypto_from_vault()`, `_write_crypto_to_vault()` |
| Password change | `change_notebook.py` | `_change_password_with_old()`, `_change_password_with_phrase()` |
| Trusted devices | `change_notebook.py` | `_show_trusted_devices()` |

---

## Security Properties (Current)

- **No long‑lived secrets stored** – only encrypted keys in vault files. The encryption key is derived at runtime from hardware fingerprint.
- **Recovery phrase never stored** – used only to create the first entry on a new machine.
- **Portable but machine‑bound** – copying a vault file to another machine does not allow decryption because the fingerprint differs.
- **Tamper‑evident** – any change to an entry's ciphertext, nonce, or timestamp causes decryption to fail.
- **O(1) unlock** – the master registry stores the exact vault and entry UUID for the current system; no trial decryption needed.
- **Lazy cache invalidation** – `SessionKeyVault` caches only unlocked keys; locking removes from RAM but keeps vault entry.
- **Multi‑vault support** – different notebooks can use different vaults (e.g., default on internal drive, custom on USB). The master registry tracks which vault each system uses.

---

## Limitations (Current)

- **Hardware fingerprint changes break the cache** – after a motherboard replacement or OS reinstall, all entries become undecryptable. User must re‑enter recovery phrase to create new entries.
- **No remote sync** – vault files are local; users must copy them manually if they want to share the cache.
- **Binary format not human‑readable** – designed for machine use only.
- **Password change on one machine does not automatically update other machines** – they will detect a mismatch and fall back to recovery phrase.

---

## Prior Art Assertion

The concepts described in this document – including but not limited to: per‑machine binary vault entries referenced by UUID, master registry mapping system fingerprints to entry UUIDs, in‑memory proxy cache (`SessionKeyVault`) backed by vault files, key derivation from runtime hardware fingerprint, and the separation of key storage from key derivation – were made public in timestamped GitHub repositories and prior art disclosures starting in February 2026.

These concepts constitute prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) EPC. No party may obtain valid patent claims covering any of these concepts.

The system is released under the **Eternal License**, which explicitly prohibits patenting any disclosed concept.

---

## Conclusion

The current secure session storage system is a zero‑trust, portable, machine‑bound key cache that uses a binary vault for persistent storage, a master registry for metadata, and an in‑memory proxy cache for unlocked keys. It balances security, portability, and convenience, allowing password‑only unlocks on trusted machines after an initial recovery phrase setup.
