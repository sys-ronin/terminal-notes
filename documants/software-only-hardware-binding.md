# Prior Art Disclosure: Stateless Hardware-Anchored Key Derivation

## A Zero-Trust Architecture for Portable, Multi-Machine Encryption Without TPM

---

**Date of Disclosure:** April 2026  
**Author:** SYS_RONIN  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** github.com/sys-ronin/terminal-notes

---

## Summary

This document describes a key management architecture where encryption keys never exist as persistent data. Keys are derived at runtime from:

1. A timestamp stored in plain text
2. A system fingerprint derived from hardware characteristics
3. A user-provided recovery phrase (for initial setup and cross-machine recovery)

The derived key exists only during the decryption operation and is immediately discarded afterward. No key material is ever written to disk.

This architecture achieves hardware-bound security without requiring a TPM, Secure Enclave, HSM, or any specialized hardware. It works on any machine with standard components.

---

## 1. The Problem with Traditional Key Management

All existing encryption systems share a common assumption: **the key must exist as data somewhere.**

| Approach | Storage Location | Problem |
|----------|------------------|---------|
| TPM | Hardware chip | Not available on all machines |
| Secure Enclave | Apple-specific | Platform lock-in |
| HSM | External device | Cost, complexity |
| Key file | Disk | Can be copied |
| Password manager | Cloud | Trust third party |
| KMS | Cloud vendor | Vendor lock-in, cost |

**Every approach stores the key.** This creates a fundamental vulnerability: the key can be stolen, copied, or extracted.

---

## 2. The Alternative: Stateless Key Derivation

Instead of storing the key, derive it when needed from:

- **Something the machine is** (hardware fingerprint)
- **Something the user knows** (recovery phrase)
- **Something that changes** (timestamp)

The key exists only in RAM during decryption. After decryption, it is discarded. No key material persists on disk.

---

## 3. Core Components

### 3.1 System Fingerprint (Runtime Only)

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

**The fingerprint is never stored.** It is generated at runtime and discarded after use.

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

**No key is ever stored.** The same inputs always produce the same key, but the key never exists as a file.

### 3.4 Vault Entry Structure

Each notebook has multiple entries (one per trusted machine). Each entry contains:

| Field | Stored | Purpose |
|-------|--------|---------|
| timestamp | Plain text | Key derivation input |
| nonce | Plain text | AES-GCM nonce |
| encrypted_keys | Encrypted | Password_key + Phrase_key |
| active | Plain text | O(1) lookup for current machine |

**The fingerprint is never stored.** The vault does not know which machine owns which entry. The machine proves itself by successfully decrypting.

---

## 4. The Recovery Mechanism

When a machine has no entry (first time), the user enters the recovery phrase.

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
Verify with .tn_password (two-factor)
    ↓
Create new vault entry with:
    - New timestamp
    - Current system fingerprint
    - Encrypted keys (password_key + phrase_key)
    - active = True
    ↓
Notebook unlocked
```

**The phrase is required only once per machine.** After entry creation, only the password is required.

---

## 5. Multi-Machine Behavior

Each machine creates its own vault entry.

```
session.vault
├── entry_1 (machine A)
│   ├── timestamp_A (plain text)
│   ├── encrypted_keys (encrypted with SHA256(timestamp_A + fingerprint_A))
│   └── active: False
├── entry_2 (machine B)
│   ├── timestamp_B (plain text)
│   ├── encrypted_keys (encrypted with SHA256(timestamp_B + fingerprint_B))
│   └── active: True
```

**Properties:**

- Machine A cannot decrypt Machine B's entry (different fingerprint)
- Machine B cannot decrypt Machine A's entry
- Each machine finds its entry by trying all entries until one decrypts (or using active flag for O(1))
- No central coordination required
- Vault file can be copied between machines

---

## 6. Security Analysis

### 6.1 Attacker with Vault File Only

The attacker has `session.vault` but not the machine.

| What they see | What they cannot do |
|---------------|---------------------|
| Timestamps (plain text) | Derive key (need fingerprint) |
| Nonces (plain text) | Decrypt (need key) |
| Encrypted blobs | Decrypt (need key) |

**Result:** Vault file is useless without the correct machine fingerprint.

### 6.2 Attacker with Vault File + Machine

The attacker has the machine but not the user's password.

| What they have | What they cannot do |
|----------------|---------------------|
| System fingerprint | Cannot decrypt without password |
| Vault file | Keys are encrypted with password_key + phrase_key |
| .tn_recovery | Encrypted with phrase_key (user knows) |

**Result:** Cannot unlock without user's password or phrase.

### 6.3 Attacker Copies Vault to Another Machine

The attacker copies `session.vault` to a different machine.

| What happens | Result |
|--------------|--------|
| Different fingerprint | Key derivation produces different key |
| Decryption attempt | InvalidTag error (AES-GCM authentication fails) |
| Entry decryption | Fails |

**Result:** Vault cannot be decrypted on a different machine.

### 6.4 Attacker with Physical Disk Access

The attacker has the hard drive.

| What they find | What they cannot do |
|----------------|---------------------|
| Encrypted notebook files | Cannot decrypt without keys |
| session.vault | Cannot decrypt without original machine |
| .tn_recovery | Cannot decrypt without phrase |

**Result:** Data remains encrypted.

---

## 7. Comparison with Existing Approaches

| Feature | TPM | Secure Enclave | HSM | This Architecture |
|---------|-----|----------------|-----|-------------------|
| Hardware required | TPM chip | Apple hardware | External device | None |
| Key storage | In TPM | In Secure Enclave | In HSM | Nowhere (derived) |
| Portability | Low | Low | Low | High (vault file) |
| Multi-machine | No | No | No | Yes (entries stack) |
| Recovery | Complex | Complex | Complex | Phrase (once per machine) |
| Cost | Hardware cost | Apple tax | High | Free |
| Platform | Limited | Apple only | Enterprise | All |

---

## 8. Prior Art Assertion

This document establishes prior art for:

1. **Stateless key derivation** where keys are derived at runtime and never stored
2. **Hardware-anchored key derivation without TPM** using system fingerprints
3. **Multi-machine vault entries** where each machine has its own encrypted entry
4. **Timestamp as key material** for tamper-evident entries
5. **Active flag optimization** for O(1) lookup without trial decryption
6. **Phrase recovery creating new entries** without modifying existing ones

The concepts disclosed herein are now part of the public domain.

No party may obtain valid patent claims covering any concept described in this document.

---

## 9. Conclusion

This architecture demonstrates that hardware-bound encryption does not require specialized hardware. Keys can be derived at runtime from machine characteristics and stored timestamps, eliminating the need for persistent key storage.

The system is:

- **Portable** (vault file can be copied)
- **Multi-machine** (each machine has its own entry)
- **Recoverable** (phrase creates new entries)
- **Zero-trust** (vault contains no machine identifiers)
- **Tamper-evident** (any change breaks decryption)

This is not a theoretical proposal. It is implemented, tested, and used daily.

---

**SYS_RONIN**  
April 2026  
sys_ronin@protonmail.com
