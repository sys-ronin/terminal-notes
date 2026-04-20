
# Secure Session Storage: A Zero‑Trust, Portable Key Cache

## What This Document Describes

This document describes the secure session storage system implemented in `secure_session.py`. The system caches cryptographic keys across application restarts without storing any long‑lived secrets. It is designed for a local‑first, offline‑first application where the user owns the data and controls the keys.

The session storage is a binary vault file (`session.vault`) that contains encrypted entries for each notebook. Each entry stores the derived password key (`Kp`) and phrase key (`Ks`) for a specific machine. The vault is portable, but each machine can only decrypt its own entries because the encryption key is derived from the machine's hardware fingerprint **at runtime** – the fingerprint is never stored.

This document describes the implementation as it exists in the code. No comparison with other systems is made.

---

## The Problem

An encrypted notebook requires two keys:

- **`Kp`** – derived from the user's password (`SHA256(password + b':' + folder_name)`). This key is used for daily authentication.
- **`Ks`** – derived from the user's recovery phrase (`SHA256(phrase + b':' + folder_name)`). This key never changes and is the actual encryption key for the notebook content.

Entering the recovery phrase on every application start is inconvenient. The user wants to unlock the notebook with only their password after the first unlock on a given machine.

However, the system cannot store `Ks` in plain text. It cannot store `Kp` in plain text. It cannot rely on a cloud service. The user may use the same notebook on multiple machines, and the session cache must be portable but also machine‑bound to prevent key extraction.

---

## The Solution: A Binary Vault with Per‑Machine Entries

The system stores a binary file named `session.vault` in the application's configuration directory. The file has the following structure (as implemented in `_read_vault()` and `_write_vault()`):

```
[4 bytes] version (4)
For each notebook (notebook_id as UTF‑8 string):
    [4 bytes] notebook_id_length
    [variable] notebook_id (UTF‑8, plain text – used as lookup key)
    [4 bytes] number_of_entries
    For each entry:
        [8 bytes] timestamp (Unix nanoseconds)
        [12 bytes] nonce
        [4 bytes] encrypted_keys_length
        [variable] encrypted_keys (AES‑256‑GCM ciphertext)
        [1 byte] active_flag (1 if active, 0 otherwise)
        [8 bytes] created_timestamp (Unix nanoseconds)
```

The file is a binary format, not JSON. There is no outer encryption. The security comes from the encryption of each individual entry, not from obscuring the file structure.

The `notebook_id` is stored as a plain text UTF‑8 string to allow direct lookup. This is not a secret; it is the identifier used to find the correct entry list.

---

## Entry Encryption

Each entry stores the encrypted concatenation of `Kp` (32 bytes) and `Ks` (32 bytes). The encryption key for the entry is derived as:

```python
encryption_key = SHA256(str(timestamp) + fingerprint)
```

Where:

- `timestamp` is a Unix nanosecond timestamp stored in the entry header.
- `fingerprint` is a 32‑byte value derived from hardware identifiers (machine‑id, product UUID, hostname, etc.) at runtime. The fingerprint is **never stored** anywhere.

The encryption uses AES‑256‑GCM:

- A random 12‑byte nonce is generated per entry.
- The ciphertext includes the encrypted `Kp` and `Ks` and a 16‑byte authentication tag.
- The nonce is stored in the entry header.

Decryption requires the correct `timestamp` and the current machine's fingerprint. If either is wrong, decryption fails with an `InvalidTag` exception.

```python
# From _derive_entry_key()
key_material = str(timestamp).encode() + fingerprint
return hashlib.sha256(key_material).digest()
```

---

## The Active Flag

Each entry has a single‑byte `active_flag` (1 for active, 0 for inactive). When the system unlocks a notebook on a machine, the `get_keys()` method:

1. Retrieves all entries for the given `notebook_id`.
2. First, tries to find an entry where `active_flag == 1`. If found, it attempts decryption.
3. If decryption succeeds, it returns the recovered `Kp` and `Ks`.
4. If decryption fails (e.g., because the fingerprint changed), it sets `active_flag = 0` for that entry, writes the vault back to disk, and falls back to trying all entries.

When a new entry is created (first unlock on a machine, or after a password change), it is added with `active_flag = 1`, and any previously active entry for that notebook is set to `active_flag = 0`.

This design allows O(1) lookup in the common case (active flag set and correct) while falling back to O(n) trial decryption when the fingerprint changes (e.g., after an OS reinstall or on a new machine).

---

## Adding a New Machine

When the user opens a notebook on a machine that has no active entry (or no entry at all), the system calls `get_keys_with_verification()`, which eventually calls `_recover_with_phrase()`:

1. Prompts the user for the **recovery phrase** (not the password).
2. Derives `Ks` from the phrase and the folder name.
3. Uses `Ks` to decrypt `.tn_recovery` and retrieve `Kp`.
4. Verifies both keys by decrypting `.tn_password` with `SHA256(Kp + Ks)`.
5. Calls `store_keys()` to create a new entry in `session.vault` with a fresh `timestamp`, a new `nonce`, and `encrypted_keys` set to AES‑GCM of `Kp` and `Ks` using `SHA256(timestamp + fingerprint)`.
6. The new entry is added with `active_flag = 1`. Any existing entry for this notebook is left unchanged (its `active_flag` remains whatever it was).

The recovery phrase is never stored. The new entry caches the derived keys for future unlocks.

---

## Normal Unlock (Machine Already Trusted)

When the user opens a notebook on a machine that already has an active entry, the system calls `get_keys_with_verification()`:

1. `get_keys()` finds the active entry and decrypts it to obtain `Kp` and `Ks`.
2. The system then prompts the user for their **password** (not the phrase).
3. It derives `Kp_entered` from the entered password and the folder name.
4. If `Kp_entered == Kp`, the password is correct.
5. It then verifies `.tn_password` using `SHA256(Kp + Ks)` as a two‑factor check.
6. If all checks pass, the notebook unlocks.

The phrase is never required after the first unlock on a given machine.

---

## Changing the Password

When the user changes the password on a trusted machine (via `_change_password_with_old()` or `_change_password_with_phrase()`), the system:

1. Locates the active entry for that notebook (via `get_keys()`, which returns `Kp_old` and `Ks`).
2. Verifies the old password (if using the old password method) or uses the phrase to decrypt `.tn_recovery`.
3. Derives `Kp_new` from the new password and the folder name.
4. Calls `store_keys()` which:
   - Reads the existing vault.
   - **Removes any existing active entry** (by filtering out entries with `active_flag == 1`).
   - Creates a **new entry** with a fresh `timestamp`, a new `nonce`, and `encrypted_keys` set to AES‑GCM of `Kp_new` and `Ks` using `SHA256(timestamp + fingerprint)`.
   - Sets `active_flag = 1` for the new entry.
   - Appends the new entry to the list (the old inactive entries remain).
5. Updates `.tn_recovery` and `.tn_password` on disk.

**Important:** The old entry for this machine becomes inactive but remains in the vault. Each machine has at most **one active entry** at any time. Other machines that have their own entries will continue to use their cached `Kp` (which is now stale). When they next unlock, they will detect the mismatch and prompt for the recovery phrase to create a new entry.

---

## Machine Fingerprint Derivation

The machine fingerprint is derived at runtime using available hardware identifiers (implemented in `_generate_system_fingerprint()`):

- **Linux**: `/etc/machine-id`, product UUID from `/sys/class/dmi/id/product_uuid`, CPU info.
- **macOS**: `IOPlatformUUID` from `ioreg`, hardware serial number.
- **Windows**: `MachineGUID` from the registry, ComputerName.

Additional components include:
- `platform.node()` (hostname)
- `platform.processor()`
- `os.getuid()` (user ID)
- `platform.system()` and `platform.release()`

The components are concatenated and hashed with SHA256. The fingerprint is **never stored on disk**. It is recomputed on every application start. If the hardware identifiers change (e.g., after a motherboard replacement), the fingerprint will change, and the existing vault entries will become undecryptable. The user must re‑enter the recovery phrase to create new entries.

This design ensures that the cached keys cannot be extracted from the vault file and used on a different machine.

---

## Security Properties

- **No long‑lived secrets are stored.** The vault stores only encrypted keys. The encryption key is derived at runtime from the machine fingerprint.
- **The recovery phrase is never stored.** It is used only to create the first entry on a new machine.
- **The vault is portable but machine‑bound.** Copying `session.vault` to another machine does not allow decryption because the fingerprint will be different.
- **Tamper‑evident.** Any change to an entry's `timestamp`, `nonce`, or `encrypted_keys` will cause decryption to fail with an `InvalidTag` error.
- **O(1) unlock in the common case.** The active flag allows direct lookup without trial decryption.
- **Password changes are instant and do not require re‑encryption.** Only the vault entry for the current machine is updated; other machines update lazily when they next unlock.

---

## Code References

| Method | Purpose |
|--------|---------|
| `_get_system_fingerprint()` | Derives the machine fingerprint from hardware identifiers at runtime. Never stores it. |
| `_derive_entry_key(timestamp, fingerprint)` | Derives the encryption key for a vault entry. |
| `_read_vault()` | Reads the binary `session.vault` file and returns a dictionary. |
| `_write_vault(vault)` | Writes the dictionary back to the binary file atomically. |
| `store_keys(notebook_id, password_key, phrase_key)` | Creates a new active entry (replaces the old one). |
| `get_keys(notebook_id)` | Retrieves the active entry's keys (if fingerprint matches). |
| `get_keys_with_verification(notebook_id, folder_path, folder_name)` | Handles the full unlock flow: normal unlock, first‑time setup, and password‑changed detection. |
| `_recover_with_phrase(notebook_id, folder_path, folder_name)` | Recovers `Kp` and `Ks` from the recovery phrase and creates a new vault entry. |

---

## Limitations

- **Machine fingerprint changes break the cache.** If the fingerprint changes (new hardware, OS reinstall), all entries become undecryptable. The user must re‑enter the recovery phrase to create new entries.
- **No remote sync.** The vault is a local file. Users who want to share the cache across machines must copy the file manually.
- **Binary format is not human‑readable.** The vault is not designed for manual inspection.

---

## Prior Art Assertion

The concepts described in this document – including but not limited to the binary vault format, per‑machine entries with timestamps, active flag for O(1) lookup, key derivation from runtime hardware fingerprint, and the separation of key storage from key derivation – were made public in timestamped GitHub repositories and prior art disclosures starting in February 2026.

These concepts constitute prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) EPC. No party may obtain valid patent claims covering any of these concepts.

The system is released under the **Eternal License**, which explicitly prohibits patenting any disclosed concept.

---

## Conclusion

The secure session storage system is a zero‑trust, portable, machine‑bound key cache. It stores encrypted entries for each notebook, one per trusted machine. The encryption key is derived at runtime from the machine's hardware fingerprint, which is never stored. The active flag enables O(1) lookup. The vault is portable but cannot be decrypted on a different machine.

This design balances security, portability, and convenience. It allows the user to unlock notebooks with only a password after the first unlock on a given machine, while ensuring that the recovery phrase is never stored and that keys cannot be extracted from the vault file.

```
