# Poor Man's Hardware Encryption

## A Zero‑Trust, Portable, Multi‑Machine Key Derivation Architecture Without TPM

---

**Date of Disclosure:** May 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** github.com/sys-ronin/terminal-notes

---

## Summary

This document describes a **poor man's hardware encryption** system – a key management architecture where encryption keys never exist as persistent data. Keys are derived at runtime from:

1. A timestamp stored in plain text
2. A system fingerprint derived from hardware characteristics
3. A user‑provided recovery phrase (for initial setup and cross‑machine recovery)

The derived key exists only during the decryption operation and is immediately discarded. No key material is ever written to disk. No TPM, no Secure Enclave, no HSM, no specialised hardware of any kind.

**The poor man's approach:** Use what you have – standard hardware, standard cryptography, and a simple insight: *don't store the key; derive it when needed.*

---

## 1. The Problem with Traditional Key Management

All conventional encryption systems share a common assumption: **the key must exist as data somewhere.**

| Approach | Storage Location | Why the Poor Man Cannot Afford It |
|----------|------------------|----------------------------------|
| TPM | Hardware chip | Not available on all machines; requires proprietary firmware |
| Secure Enclave | Apple‑specific | Platform lock‑in; Apple tax |
| HSM | External device | Costs thousands of dollars |
| Key file | Disk | Can be copied; requires backup discipline |
| Password manager | Cloud | Trust a third party; subscription fees |
| KMS | Cloud vendor | Vendor lock‑in; ongoing costs |

**Every approach stores the key.** This creates a fundamental vulnerability: the key can be stolen, copied, or extracted. More importantly, it requires resources the poor man does not have.

The poor man's alternative: **derive the key when needed, store nothing persistent.**

---

## 2. The Alternative: Stateless Key Derivation

Instead of storing the key, derive it at runtime from:

- **Something the machine is** (hardware fingerprint, derived fresh each time)
- **Something the user knows** (recovery phrase, stored only in the user's memory)
- **Something that changes** (timestamp, stored in plain text)

The key exists only in RAM during decryption. After decryption, it is discarded. No key material persists on disk. No hardware to buy. No cloud subscription.

---

## 3. Core Components

### 3.1 System Fingerprint (Runtime Only, Never Stored)

The fingerprint is derived from hardware characteristics that are:

- Stable across reboots
- Unique to the machine
- Not reproducible on different hardware

**Linux:**
- `/etc/machine-id`
- DMI product UUID
- CPU information

**macOS:**
- IOPlatformUUID
- Hardware serial number

**Windows:**
- MachineGUID
- Computer name + SID

**All platforms:**
- Hostname
- Username
- OS release

**The fingerprint is never stored on disk.** It is generated at runtime from the live hardware and discarded after use.

### 3.2 Timestamp (Stored in Plain Text)

Each vault entry contains a timestamp. This timestamp is:

- Stored in plain text (not encrypted)
- Used as part of the key derivation
- Different for each machine that trusts the notebook

**The timestamp is public.** Knowing it does not help an attacker because the fingerprint is required.

### 3.3 Key Derivation

```
encryption_key = SHA256( timestamp + system_fingerprint )
```

**No key is ever stored.** The same inputs always produce the same key, but the key never exists as a file. No key generation, no key backup, no key rotation – just derivation.

### 3.4 Vault Entry Structure

Each notebook has multiple entries (one per trusted machine). Each entry contains:

| Field | Stored | Purpose |
|-------|--------|---------|
| timestamp | Plain text | Key derivation input |
| nonce | Plain text | AES‑GCM nonce |
| encrypted_keys | Encrypted | Password_key + Phrase_key |
| active | Plain text | O(1) lookup for current machine |

**The fingerprint is never stored.** The vault file does not know which machine owns which entry. The machine proves itself by successfully decrypting an entry.

---

## 4. The Recovery Mechanism (The Poor Man's Backup)

When a machine has no entry (first time, or after entry removal), the user enters the recovery phrase.

**Recovery flow:**

```
User enters phrase
    ↓
phrase_key = SHA256(phrase + folder_name)
    ↓
Decrypt .tn_test (verification)
    ↓
Decrypt .tn_recovery → get password_key
    ↓
Verify with .tn_password (two‑factor)
    ↓
Create new vault entry with:
    - New timestamp
    - Current system fingerprint
    - Encrypted keys (password_key + phrase_key)
    - active = True
    ↓
Notebook unlocked
```

**The phrase is required only once per machine (or after entry removal).** After entry creation, only the password is required for daily use.

No cloud backup. No subscription. No IT department. Just a phrase the user writes down.

---

## 5. Multi‑Machine Behaviour

Each machine creates its own vault entry. The vault file can be copied between machines; entries remain bound to their original hardware.

```
session.vault
├── entry_1 (machine A)
│   ├── timestamp_A (plain text)
│   ├── encrypted_keys (encrypted with SHA256(timestamp_A + fingerprint_A))
│   ├── active: False
│   └── system_name: "laptop-ubuntu"
├── entry_2 (machine B)
│   ├── timestamp_B (plain text)
│   ├── encrypted_keys (encrypted with SHA256(timestamp_B + fingerprint_B))
│   ├── active: True
│   └── system_name: "desktop-fedora"
```

**Properties:**

- Machine A cannot decrypt Machine B's entry (different fingerprint)
- Machine B cannot decrypt Machine A's entry
- Each machine finds its entry by trying all entries until one decrypts (or using active flag for O(1))
- No central coordination required
- Vault file can be copied between machines (but entries remain useless on different hardware)

---

## 6. Portable Vault Storage (The Poor Man's Hardware Key)

The vault file can be stored **anywhere**: local disk, USB drive, network share, S3 bucket, WebDAV server. Its location is recorded in a small `vaults_registry.json` file.

Because entries are encrypted with the hardware fingerprint, the vault file can be placed on **untrusted cloud storage** without revealing the keys.

**The poor man's hardware key:** A USB drive containing the vault file. Plug it in, use your notebook. Unplug it, the cache invalidates immediately. No expensive hardware token required.

---

## 7. Active Cache Validation (Missing Vault Detection)

The `SessionKeyVault` is a transparent dict‑like cache that stores decrypted keys for unlocked notebooks. Unlike a conventional cache, it **validates the existence of the underlying vault file before every cache hit**:

```python
if notebook_id in self._cache:
    vault_path = self.manager._get_vault_path(notebook_id)
    if vault_path and os.path.exists(vault_path):
        return self._cache[notebook_id]
    else:
        del self._cache[notebook_id]   # immediate invalidation
```

If the vault file is missing (USB unplugged, network share unmounted), the cached entry is deleted instantly. No stale keys, no silent failures.

---

## 8. Security Analysis (Why the Poor Man Is Not Less Secure)

### 8.1 Attacker with Vault File Only

The attacker has the vault file but not the original machine.

| What they see | What they cannot do |
|---------------|---------------------|
| Timestamps (plain text) | Derive key (need fingerprint) |
| Nonces (plain text) | Decrypt (need key) |
| Encrypted blobs | Decrypt (need key) |

**Result:** Vault file is useless without the correct machine fingerprint.

### 8.2 Attacker Copies Vault to Another Machine

The attacker copies the vault file to a different machine.

| What happens | Result |
|--------------|--------|
| Different fingerprint | Key derivation produces different key |
| Decryption attempt | InvalidTag error (AES‑GCM authentication fails) |

**Result:** Vault cannot be decrypted on a different machine. No TPM required.

### 8.3 Attacker Steals the USB Drive with the Vault

The vault file is on a USB drive. The drive is stolen.

| What the attacker has | What they cannot do |
|-----------------------|---------------------|
| Encrypted vault entries | Cannot decrypt without the original machine's fingerprint |
| (No notebook folder) | No data even if they could decrypt |

**Result:** The USB drive alone is useless. The notebook folder is elsewhere.

---

## 9. Comparison with "Rich Man's" Solutions

| Feature | TPM / HSM / Secure Enclave | Poor Man's Architecture |
|---------|---------------------------|------------------------|
| Hardware required | Specialised chip or device | **None** – standard hardware only |
| Key storage | In hardware (persistent) | **Nowhere** (derived at runtime) |
| Portability | Low (keys tied to specific chip) | **High** (vault file can be copied) |
| Multi‑machine | No | **Yes** (entries stack) |
| Recovery | Complex (IT intervention, backup keys) | **Simple** (phrase on any machine) |
| Cost | Expensive (chip cost, Apple tax, HSM) | **Free** |
| Platform lock‑in | Yes | **None** |
| TPM bus sniffing vulnerability | **Vulnerable** | **Immune** (no hardware bus) |

The poor man does not have less security. He has a different architecture – one that favours portability, user control, and software purity over proprietary hardware.

---

## 10. Prior Art Assertion

This document establishes prior art for the following concepts, all disclosed in public, timestamped materials as of May 2026:

1. **Stateless key derivation** – keys derived at runtime and never stored
2. **Hardware‑anchored key derivation without TPM** – using system fingerprints derived at runtime
3. **Multi‑machine vault entries** – each machine has its own encrypted entry
4. **Timestamp as key material** – for tamper‑evident entries
5. **Active flag optimisation** – O(1) lookup without trial decryption
6. **Phrase recovery creating new entries** – without modifying existing ones
7. **Portable vault files** – stored on any medium (USB, cloud, network)
8. **Active cache validation** – missing vault invalidates cache immediately
9. **Poor man's hardware binding** – software‑only, no TPM, no specialised hardware

The concepts disclosed herein are now part of the public domain. No party may obtain valid patent claims covering any concept described in this document.

---

## 11. Conclusion

This architecture demonstrates that hardware‑bound encryption does **not** require specialised hardware. Keys can be derived at runtime from machine characteristics and stored timestamps, eliminating the need for persistent key storage.

**The poor man's system is:**

- **Portable** – vault file can be stored anywhere (USB, cloud, network)
- **Multi‑machine** – each machine has its own encrypted entry
- **Recoverable** – phrase recreates entries, even after vault loss
- **Zero‑trust** – vault contains no machine identifiers
- **Tamper‑evident** – any change breaks decryption
- **Resilient** – missing vault triggers recovery, not data loss
- **Free** – no hardware to buy, no subscriptions

This is not a theoretical proposal. It is implemented, tested, and used daily. The poor man built it because he could not afford the rich man's hardware. It turns out the poor man's solution is more portable, more flexible, and in some ways more secure.

---

**sys_ronin**  
May 2026  
sys-ronin@protonmail.com
```
