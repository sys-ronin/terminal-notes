# Terminal Notes Encryption System: A Technical Overview

---

## 1. Introduction

This document describes the encryption architecture implemented in Terminal Notes. It does not claim novelty. It does not assert superiority. It documents what exists.

The system is built on standard cryptographic primitives: AES-256-GCM for encryption, SHA256 for key derivation. The design choices—separating authentication from encryption, binding keys to hardware, using recovery phrases as key material—are documented here for transparency.

No secrets are stored. No keys are transmitted. The user owns their data completely.

---

## 2. Cryptographic Primitives

| Component | Algorithm | Purpose |
|-----------|-----------|---------|
| **Encryption** | AES-256-GCM | Authenticated encryption with 256-bit key |
| **Key Derivation** | SHA256 | One-way function to derive keys from secrets |
| **Randomness** | `os.urandom` | 12-byte nonce per encryption |
| **Key Storage** | AES-256-GCM | Keys encrypted with system fingerprint |

All primitives are from the `cryptography` library, a well-audited Python package.

---

## 3. Key Derivation

Every key in the system is derived using SHA256:

```python
def derive_key(secret, salt):
    combined = secret + b':' + salt
    return hashlib.sha256(combined).digest()
```

**No secret is ever used directly.** Passwords, phrases, and their derivatives all pass through SHA256 with a salt.

---

## 4. The Three Keys

The system maintains three keys per notebook:

| Key | Derivation | Purpose |
|-----|------------|---------|
| **Password Key (Kp)** | SHA256(password + folder) | Daily authentication |
| **Phrase Key (Ks)** | SHA256(phrase + folder) | Actual encryption key |
| **Combined Key (Kc)** | SHA256(Kp + Ks) | Verification (`.tn_password`) |

**Notebook data is encrypted with Ks.** The password key (Kp) is only used to verify user identity and to unlock access to Ks.

---

## 5. Security Level: 2²⁵⁶ Key Space

The actual encryption key (Ks) is a 256-bit SHA256 output. This provides:

- Key space: 2²⁵⁶ possibilities
- No known practical attack against AES-256-GCM
- Same key space as Bitcoin private keys

The phrase selects one of these 2²⁵⁶ possibilities. Phrase entropy determines how hard it is to guess which key is used.

---

## 6. Phrase Entropy

Users can choose any phrase. The system generates BIP-39 style phrases or accepts custom text:

| Phrase Type | Word Source | Entropy (bits) |
|-------------|-------------|----------------|
| 6 words | BIP-39 list (2048 words) | 66 |
| 8 words | BIP-39 list (2048 words) | 88 |
| 12 words | BIP-39 list (2048 words) | 132 |
| 24 words | BIP-39 list (2048 words) | 264 |
| Custom text | User-defined | Variable (user-dependent) |

**The key remains 256 bits regardless of phrase length.** The phrase is input to SHA256; the output is always 256 bits.

---

## 7. File Structure

Each encrypted notebook folder contains:

```
notebook_folder/
├── structure.json      # Encrypted with Ks
├── notes.json          # Encrypted with Ks
├── files.json          # Encrypted with Ks
├── .tn_test            # "VERIFICATION" encrypted with Ks
├── .tn_recovery        # Kp encrypted with Ks
└── .tn_password        # Kc encrypted with Kc (self-referential)
```

**No file contains unencrypted secrets.** All are encrypted binary blobs.

---

## 8. Encryption Overhead

Each encrypted file uses:

- 12 bytes nonce (random per encryption)
- 16 bytes GCM authentication tag
- Total overhead: **28 bytes per file**

No base64 encoding. No JSON wrappers. No metadata headers.

Example: A 1KB plaintext note becomes ~1,028 bytes encrypted.

---

## 9. Daily Use: Password Only

When the notebook is unlocked on a trusted machine:

1. User enters password
2. System derives Kp
3. System retrieves Ks from secure session (cached)
4. Kc is derived for verification
5. Notebook decrypts with Ks

**The phrase is never entered during daily use.** It is only required for import on new machines.

---

## 10. Import on New Machine: Phrase Only

When importing a notebook to a new machine:

1. User enters phrase
2. System derives Ks
3. System verifies `.tn_test` with Ks
4. System decrypts `.tn_recovery` with Ks to retrieve Kp
5. System derives Kc and verifies `.tn_password`
6. System caches Kp and Ks in secure session
7. Notebook becomes usable with password only

**The phrase is only needed once per machine.** After import, daily use requires only password.

---

## 11. Hardware Binding: System Fingerprint

Keys are cached in secure session, which is encrypted with a system-specific fingerprint:

```python
fingerprint = SHA256(
    machine_id + product_uuid + platform_info + hostname + user_id
)
```

- On Linux: `/etc/machine-id`, product UUID, CPU info
- On macOS: IOPlatformUUID, hardware serial
- On Windows: MachineGUID

**The same notebook folder copied to another machine cannot be unlocked without the phrase.** Keys are bound to the machine where they were cached.

---

## 12. Password Change: Instant

Changing password does not re-encrypt the notebook:

1. User enters old password → derive old Kp
2. User enters new password → derive new Kp
3. Update `.tn_recovery` with new Kp (still encrypted with Ks)
4. Update `.tn_password` with new Kc
5. Update secure session with new Kp

**The notebook remains encrypted with Ks (unchanged).** Password change is instant regardless of notebook size.

---

## 13. Recovery: Phrase Only

If the password is forgotten:

1. User enters phrase on any machine
2. System derives Ks
3. System decrypts `.tn_recovery` to retrieve Kp
4. System derives Kc and verifies `.tn_password`
5. Notebook decrypts with Ks
6. User sets new password

**Recovery works on any machine.** No cloud, no email, no central authority.

---

## 14. No Phrase Storage

The recovery phrase is:

- Generated once (if auto-generated)
- Shown once
- Never stored
- Never hashed
- Never saved

**The user alone owns the phrase.** The system cannot recover it. The system cannot lose it. The user is responsible for its safekeeping.

---

## 15. GitHub as Sync Layer

Because all files are encrypted binary blobs:

- Any Git remote works (GitHub, GitLab, self-hosted)
- Public repos are safe (JSON is encrypted)
- No separate sync service needed
- No subscription required

**The notebook can be pushed to a public GitHub repository without exposing content.**

---

## 16. Portability

The notebook folder is self-contained:

- All encrypted data inside
- No external dependencies
- Copy to USB, email, cloud storage
- Import on new machine with phrase

**The folder can be moved anywhere. The data remains encrypted.**

---

## 17. Security Properties Summary

| Property | Implementation |
|----------|----------------|
| **Encryption** | AES-256-GCM |
| **Key Space** | 2²⁵⁶ |
| **Key Derivation** | SHA256 with salt |
| **Phrase Entropy** | 66 to 264+ bits (user choice) |
| **Hardware Binding** | System fingerprint |
| **Recovery** | Phrase only, any machine |
| **Password Change** | Instant (no re-encryption) |
| **No Phrase Storage** | Yes (shown once, never stored) |
| **No Cloud Dependency** | Yes (Git optional) |

---

## 18. Limitations

- **No third-party audit** — code is open for review
- **No key derivation iteration** — SHA256 is fast, but entropy is the primary protection
- **User-dependent phrase strength** — custom phrases can be weak if chosen poorly
- **Hardware changes** may invalidate secure session (recovery phrase resolves this)

---

## 19. Conclusion

Terminal Notes implements a dual-key encryption system where:

- The phrase is the ultimate key (256-bit SHA256 output)
- The password is a convenience factor for daily use
- Keys are bound to hardware (system fingerprint)
- Recovery works on any machine with the phrase
- Password changes are instant
- No phrase is ever stored

This architecture is built on standard cryptographic primitives. 

The code is open. The design is documented. The user owns their data.

---

**sys_ronin**  
April 2026
