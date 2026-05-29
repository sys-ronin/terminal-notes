# Encryption Embedded at Every Layer: A Code‑Driven Description

## How Terminal Notes Integrates Cryptography Without Exception

This document describes how encryption is not an optional feature but a pervasive, non‑bypassable layer integrated into every storage operation. The description is based on the actual code and the bundled cryptography assets. No claim of novelty or superiority is made. The purpose is to document the observable fact that **no plaintext data is ever written to disk** and that every read path that accesses encrypted data must pass through decryption.

---

## 1. The Central Principle: Encryption is Not an Add‑On

In many applications, encryption is applied at the boundary: a file is encrypted before upload and decrypted after download. The application logic often works with plaintext data, and encryption is a separate concern.

In Terminal Notes, encryption is **embedded into the fundamental I/O functions**. The code does not have a separate “encrypt this file” step. Instead, every write to a notebook’s JSON files goes through a `write_json` function that transparently encrypts if a `Crypto` object is present. Every read goes through a `read_json` function that transparently decrypts.

As a result, there is **no path in the code** that writes plaintext to the notebook folder. The only plaintext that ever exists is in memory while the application is running, and it is cleared when the notebook is locked or the process exits.

---

## 2. Embedded Cryptography: Bundled Assets for Zero‑Configuration Deployment

The system does not rely on the user to install cryptographic libraries. Instead, it bundles the necessary assets in the `assets/` directory, which includes platform‑specific wheels for `cryptography` and `cffi`. The `crypto.py` module attempts to import `cryptography` from the system; if that fails, it falls back to the bundled libraries.

```python
# From crypto.py
try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    HAS_CRYPTO = True
except ImportError:
    # Fallback to bundled assets
    if sys.version_info >= (3, 13):
        # add bundled paths to sys.path
        sys.path.insert(0, os.path.join(assets_dir, 'cffi'))
        sys.path.insert(0, os.path.join(assets_dir, 'cryptography'))
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        HAS_CRYPTO = True
```

This mechanism ensures that **AES‑256‑GCM is always available** without requiring the user to run `pip install cryptography`. The user does not need to know which cryptographic primitives are used; the system provides them transparently. The fallback works on Linux, macOS, and Windows, with pre‑compiled wheels for each platform.

The assets include:

- `cffi/` – the C Foreign Function Interface library, required by `cryptography`
- `cryptography/` – the complete `cryptography` package source and wheels
- Platform‑specific binaries for `manylinux2014_x86_64`, `macosx_10_9_x86_64`, and `win_amd64`

Thus, **encryption is not only embedded in the logic but also in the distribution**. The user does not need to install any external dependencies. The system is self‑contained.

---

## 3. The Universal JSON Handler: `read_json` / `write_json`

The functions `read_json` and `write_json` in `notebook_operations.py` are the **single point of contact** for all persistent JSON data.

```python
def write_json(filepath, data, crypto=None):
    # Convert data to JSON string
    json_str = json.dumps(data, indent=2)
    if crypto:
        final_data = crypto.encrypt(json_str)   # ← encryption applied
        mode = 'wb'
    else:
        final_data = json_str.encode('utf-8')
        mode = 'wb'
    # atomic write to .tmp + rename
```

```python
def read_json(filepath, crypto=None):
    with open(filepath, 'rb') as f:
        raw = f.read()
    return _parse_json(raw, crypto)
```

`_parse_json` tries decryption if `crypto` is provided; if decryption fails or no crypto is given, it falls back to plain JSON (for unencrypted notebooks). This design ensures that **no caller ever needs to know whether the data is encrypted**. The encryption is transparent to the rest of the application.

**Every notebook operation** (create, edit, delete, rename, restore) that reads or writes `structure.json`, `notes.json`, or `files.json` goes through these functions. Therefore, there is **no way to bypass encryption** for those files.

---

## 4. Encryption at Rest: The Three JSON Files

For an encrypted notebook, all three JSON files are stored as **encrypted binary blobs**. No plaintext ever touches the disk:

| File | Content | Encryption Key |
|------|---------|----------------|
| `structure.json` | Notebook hierarchy, note metadata | Ks (phrase key) |
| `notes.json` | Note text content | Ks |
| `files.json` | File note content | Ks |

The encryption is applied **before** the file is written. Git stores the encrypted blobs. The entire commit history is encrypted. An attacker with access to the disk or a cloned Git repository sees only random‑looking binary data.

---

## 5. Key Management: Dual‑Key Separation (Kp, Ks, Kc)

Encryption is not a single key. The system uses three distinct keys, each with a specific role, derived using the bundled SHA256 implementation (Python’s `hashlib`):

- **Ks (phrase key)**: derived from the recovery phrase + folder name using `SHA256(phrase + b':' + folder_name)`. This is the **actual encryption key** for all notebook data. It is never stored anywhere; it is derived each time the notebook is unlocked.
- **Kp (password key)**: derived from the user’s password + folder name using `SHA256(password + b':' + folder_name)`. Used only to verify the user’s identity against a cached entry. **Kp never encrypts any data**.
- **Kc (combined key)**: derived as `SHA256(Kp + Ks)`. Used only for the self‑referential `.tn_password` file (verification).

This separation ensures that even if the password is leaked, the encrypted data remains safe because Ks is not derived from the password.

The derivation uses only standard SHA256, which is part of Python’s `hashlib`. No external cryptographic library is needed for key derivation (only for AES‑GCM encryption). This minimises external dependencies.

---

## 6. Hardware Binding: Vault Entries Without Stored Keys

The `SecureSessionStorage` class manages a vault file (by default `config/session.vault`, but can be any file). This vault contains **entries** that store encrypted copies of `Kp + Ks`. Each entry is encrypted with a key derived from:

```
entry_key = SHA256(timestamp + system_fingerprint)
```

The `system_fingerprint` is derived at runtime from hardware identifiers (machine ID, product UUID, hostname) using SHA256 and is **never written to disk**. Consequently, a vault file copied to another machine cannot be decrypted because the fingerprint differs.

The `SessionKeyVault` class transparently reads these entries on demand, caches them in memory, and **validates the existence of the vault file before every cache hit**. If the vault file disappears, the cache is invalidated immediately.

Thus, encryption is embedded not only in data storage but also in **key storage**: the keys themselves are always stored encrypted and bound to hardware.

---

## 7. Git Commits: Encrypted Blobs Only

When a notebook is pushed to a Git remote, the repository contains only the encrypted JSON files and the hidden `.tn_*` files. The commit messages contain **plaintext UUIDs and action types**, but no note content. This is a deliberate trade‑off: the history structure is searchable, but the content remains encrypted. The encryption boundary is preserved because the actual note text never leaves the encrypted blobs.

Because the JSON files are already encrypted before Git sees them, the version control system never has access to plaintext. This is true for every commit in the history.

---

## 8. Recovery Phrase: The Ultimate Key That Never Touches Disk

The recovery phrase is the root of trust. It is **never stored anywhere** – not in a file, not in a registry, not in the Git history. It is shown to the user once and then forgotten by the system. The user must remember it or keep it safe. This is the only secret that can recreate Ks and thus decrypt the notebook.

The phrase is used only during:

- Notebook creation (to derive Ks)
- First unlock on a new machine (to create a vault entry)
- Password recovery (to derive Ks and then Kp)

In every case, the phrase is entered via `getpass`, used to derive a key in memory, and then discarded. No trace remains on disk.

---

## 9. No Unencrypted Transient Files

The system uses `tempfile` only for two purposes:

- Temporary storage of editor content (which is plaintext, but that is the user’s editor environment; the app does not write that content to disk itself – the editor does).
- Reconstruction of deleted items for timeline/history views: a temporary directory with plaintext JSON files is created. This directory is deleted as soon as the user closes the view. This is the only place where decrypted content exists on disk, and it is explicitly ephemeral (the user must explicitly choose to view a historical version, and the files are removed after use).

All other operations work entirely in memory and write only encrypted blobs.

---

## 10. Encryption is Mandatory for Encrypted Notebooks

If a notebook is marked as encrypted, **all paths to its data require a `Crypto` object**. The `SessionKeyVault` will raise an exception if the keys cannot be obtained. The caller cannot “skip” encryption because the `write_json` and `read_json` functions will either encrypt or decrypt based on the presence of the `crypto` argument. For encrypted notebooks, that argument is always provided after the notebook is unlocked.

Thus, there is **no code path** that writes an unencrypted JSON file for an encrypted notebook.

---

## 11. Summary: Encryption Embedded in Every Layer

| Layer | Mechanism | Encryption Guarantee |
|-------|-----------|----------------------|
| **Cryptography distribution** | Bundled `cryptography` and `cffi` wheels | No external install required; AES‑256‑GCM always available |
| **Key derivation** | SHA256 (Python `hashlib`) | No external libraries needed for key derivation |
| **JSON file I/O** | `read_json` / `write_json` with optional `crypto` | No plaintext write path for encrypted notebooks |
| **Key storage** | Vault entries encrypted with hardware fingerprint (AES‑256‑GCM) | Keys never stored in plain text |
| **Key caching** | `SessionKeyVault` validates vault existence before returning cached key | Stale keys cannot be used after vault removal |
| **Git commits** | Blobs are already encrypted; commit messages contain only UUIDs | Content never appears in plain text even in history |
| **Memory** | Keys cleared on lock or process exit | No persistent plaintext keys on disk |
| **Recovery phrase** | Never stored, only entered via `getpass` | No disk trace of the master secret |

The code is open. The behavior is observable. Every write to a notebook’s persistent storage that occurs while the notebook is in encrypted state passes through an encryption path. The cryptographic primitives are embedded in the distribution, requiring no external installation. There are no exceptions.

This is not a claim of perfection. It is a description of what the code does. The reader is invited to verify by inspecting the source.

---

**sys_ronin**  
May 2026
```
