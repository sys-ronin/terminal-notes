# Prior Art Disclosure: Terminal Notes Encryption System

## A Complete Technical Description of a Flexible, Dual-Key, Hardware-Bound, Portable Encryption Architecture with Zero-Configuration, Cross-Platform Deployment and Explicit Memory Management

---

**Date of Disclosure:** April 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** [github.com/sys-ronin/terminal_notes](https://github.com/sys-ronin/terminal_notes)

---

## Table of Contents

1. Introduction
2. Summary of Disclosed Concepts
3. Cryptographic Primitives and Bundled Distribution
4. Key Derivation
5. The Three Keys
6. Flexible Phrase System
7. File Structure
8. Hardware-Bound Key Storage
9. Dual-Key Authentication
10. The Lock Button: Visual Encryption Status and Explicit Memory Manager
11. Recovery Mechanism
12. Password Change Without Re-encryption
13. No Phrase Storage
14. Git as Encrypted Sync Layer
15. Portability and Zero-Configuration Deployment
16. Encryption Overhead
17. How the System Was Built: The Logic Chain
18. Prior Art Assertion
19. 35 U.S.C. § 102(a)(1) Compliance
20. Conclusion

---

## 1. Introduction

This document describes the encryption architecture implemented in Terminal Notes, a local-first, terminal-based note-taking system. The system is built on standard cryptographic primitives (AES-256-GCM, SHA256) but employs a novel key management architecture that:

- Separates authentication from encryption
- Uses a flexible phrase system (any length, any words, any text)
- Binds keys to hardware
- Enables recovery without cloud services
- Allows instant password changes
- Provides free encrypted sync via Git
- Bundles cross-platform cryptography libraries for zero-configuration deployment
- Uses a single lock symbol (🔒/🔐) as the complete encryption interface
- Implements the lock button as an **explicit memory manager** that unloads encryption keys and notebook structure from RAM

The purpose of this disclosure is to establish prior art under 35 U.S.C. § 102(a)(1). The concepts described herein are now part of the public domain. No party may obtain valid patent claims covering any concept disclosed.

---

## 2. Summary of Disclosed Concepts

| Concept | Description |
|---------|-------------|
| **Bundled Cross-Platform Cryptography** | Cryptography libraries (cryptography, cffi) bundled with platform-specific wheels for Linux, macOS, Windows. No external installation required. |
| **Flexible Phrase System** | 6, 8, 12, 24 random words OR any custom text (poems, stories, sentences) |
| **Dual-Key Separation** | Password key for daily authentication, phrase key for encryption |
| **Hardware-Bound Key Storage** | Keys encrypted with system fingerprint derived from machine identifiers |
| **Cross-Encrypted Key Files** | Three files: `.tn_test`, `.tn_recovery`, `.tn_password` |
| **Lock Button as Visual Status** | Single key (`l`) toggles between 🔒 (locked) and 🔐 (unlocked). The symbol is the complete interface. |
| **Lock Button as Explicit Memory Manager** | Locking removes encryption keys from memory AND unloads the entire notebook structure (notes, subnotebooks, content cache) from RAM. Unlocking loads keys from secure session and restores structure. |
| **Instant Password Change** | Password change without re-encrypting the notebook |
| **No Phrase Storage** | Recovery phrase shown once, never stored or hashed |
| **Git as Encrypted Sync** | Encrypted JSON blobs pushed to Git remotes (including public repos) |
| **Folder Name as Salt** | Folder name used in all key derivations to ensure uniqueness |
| **Portable Notebook Folder** | Self-contained encrypted folder, importable on any machine with phrase |
| **Zero-Configuration** | Single executable, bundled dependencies, runs on any system with no setup |

---

## 3. Cryptographic Primitives and Bundled Distribution

The system uses only standard, well-audited cryptographic primitives:

| Component | Algorithm | Source |
|-----------|-----------|--------|
| **Encryption** | AES-256-GCM | `cryptography` library |
| **Key Derivation** | SHA256 | Python `hashlib` |
| **Randomness** | `os.urandom` | Operating system CSPRNG |
| **Key Storage** | AES-256-GCM | Encrypted with system fingerprint |

### Bundled Cross-Platform Distribution

The cryptography libraries are bundled with the application to achieve zero-configuration deployment:

```
assets/
├── cffi/
│   ├── _cffi_backend.cp313-win_amd64.pyd     # Windows
│   ├── _cffi_backend.cpython-313-darwin.so   # macOS
│   └── _cffi_backend.cpython-313-x86_64-linux-gnu.so  # Linux
├── cryptography/
│   └── [complete cryptography library source]
└── cryptography-46.0.3-cp38-abi3-manylinux2014_x86_64.whl
```

**Properties:**
- No `pip install` required
- No system dependencies (OpenSSL, libffi)
- Works on any system with Python 3.6+ (3.13 for my bundled-setup)
- Cross-platform support: Linux, macOS, Windows
- Single executable output (via PyInstaller, experimental builder provided) includes all dependencies

---

## 4. Key Derivation

All keys are derived using SHA256 with a secret and a salt:

```python
def derive_key(secret, salt):
    combined = secret + b':' + salt
    return hashlib.sha256(combined).digest()
```

- **Secret:** User password or recovery phrase (any length, any text)
- **Salt:** Notebook folder name (e.g., `"my-notes-20260401123456"`)

**Properties:**
- Same secret on different notebooks yields different keys
- SHA256 output is always 256 bits, regardless of secret length
- No secret is ever used directly
- The salt is public (folder name) but ensures uniqueness

---

## 5. The Three Keys

The system maintains three keys per notebook:

| Key | Derivation | Purpose | Storage |
|-----|------------|---------|---------|
| **Password Key (Kp)** | SHA256(password + folder) | Daily authentication | Encrypted in `.tn_recovery` with Ks |
| **Phrase Key (Ks)** | SHA256(phrase + folder) | Actual encryption key | Never stored (derived on demand) |
| **Combined Key (Kc)** | SHA256(Kp + Ks) | Verification | Self-referential in `.tn_password` |

**Notebook data is encrypted with Ks.** The password key is never used for encryption.

---

## 6. Flexible Phrase System

This is a core innovation. The system accepts any phrase as the ultimate key:

### Auto-Generated Phrases (BIP-39 Style)

| Length | Entropy | Security Level |
|--------|---------|----------------|
| 6 words | 66 bits | 2,000 years to crack |
| 8 words | 88 bits | Stronger than most corporate passwords |
| 12 words | 132 bits | Bitcoin standard, unbreakable |
| 24 words | 264 bits | Beyond any known computational limit |

### Custom Phrases (User-Provided)

The user can enter any text as their recovery phrase:

- A sentence: *"The old oak tree behind my grandmother's house"*
- A poem: *"I wandered lonely as a cloud that floats on high o'er vales and hills"*
- A story: *"When I was seven, I found a key under the big rock by the creek"*
- Any combination: *"My first car was a 1998 Honda Civic, license plate ABC-123"*

**Properties of Custom Phrases:**
- Any length (minimum 1 character, no maximum)
- Any content (letters, numbers, spaces, punctuation)
- Case-sensitive
- No word list restrictions
- Entropy depends on user's creativity (can exceed 264 bits)

### Why This Matters

The phrase system is flexible because:

1. **Users can choose their security level** — 6 words for quick recovery, 24 words for maximum security
2. **Users can create memorable phrases** — a personal story is harder to forget than random words
3. **Users can create unguessable phrases** — no one knows the story of your childhood
4. **The system does not restrict creativity** — any text works

**The key remains 256 bits regardless of phrase length.** The phrase selects one of 2^256 possible keys. The entropy of the phrase determines how hard it is to guess which key is used.

---

## 7. File Structure

Each encrypted notebook folder contains:

```
notebook_folder/
├── structure.json      # Notebook structure, encrypted with Ks
├── notes.json          # Note content, encrypted with Ks
├── files.json          # File content, encrypted with Ks
├── .tn_test            # "VERIFICATION" encrypted with Ks
├── .tn_recovery        # Kp encrypted with Ks
└── .tn_password        # Kc encrypted with Kc (self-referential)
```

**No file contains unencrypted secrets.** All are raw encrypted binary blobs.

---

## 8. Hardware-Bound Key Storage

Keys are cached in a secure session file, encrypted with a system fingerprint:

```python
fingerprint = SHA256(
    machine_id + product_uuid + platform_info + hostname + user_id
)
```

**Machine Identifiers Used:**

| Platform | Identifiers |
|----------|-------------|
| Linux | `/etc/machine-id`, product UUID, CPU info |
| macOS | IOPlatformUUID, hardware serial number |
| Windows | MachineGUID, ComputerName, user SID |

**Properties:**
- Keys cannot be decrypted on a different machine
- Copying the notebook folder to another machine requires the recovery phrase
- The same notebook can be used on multiple machines by importing with the phrase on each

---

## 9. Dual-Key Authentication

The system separates authentication from encryption:

### Daily Use (Trusted Machine)

1. User enters password
2. System derives Kp from password + folder
3. System retrieves Ks from secure session cache
4. System derives Kc and verifies `.tn_password`
5. Notebook decrypts with Ks

**The phrase is never entered during daily use.**

### First Use on New Machine

1. User copies notebook folder to new machine
2. User enters phrase (once)
3. System derives Ks
4. System decrypts `.tn_recovery` to retrieve Kp
5. System derives Kc and verifies `.tn_password`
6. System caches Kp and Ks in new machine's secure session
7. Future unlocks require only password

**The phrase is only needed once per machine.**

---

## 10. The Lock Button: Visual Encryption Status and Explicit Memory Manager

The lock button serves two critical functions: visual encryption status and explicit memory management.

### 10.1 Visual Representation

| State | Symbol | Meaning |
|-------|--------|---------|
| **Locked** | 🔒 | Notebook encrypted, keys not in memory, structure unloaded, cannot access |
| **Unlocked** | 🔐 | Notebook decrypted, keys in memory, structure loaded, full access |
| **Unencrypted** | (no symbol) | Notebook not encrypted |

### 10.2 User Interaction

Single key press (`l`) toggles the lock state:

- **Press `l` on a locked notebook** → prompts for password, verifies, loads keys, loads structure, symbol changes to 🔐
- **Press `l` on an unlocked notebook** → clears keys from memory, unloads structure, symbol changes to 🔒

### 10.3 The Lock Button as Explicit Memory Manager

When the user presses `l` on an unlocked notebook, the system performs explicit memory cleanup:

```python
# Lock operation
notebook.custom_path = None                    # Remove path reference
del self.manager.session_keys[notebook.id]     # Delete encryption keys from memory
notebook.locked = True                          # Set lock state
if hasattr(notebook, '_crypto'):               # Remove crypto object
    delattr(notebook, '_crypto')
```

Additionally, the notebook structure is unloaded:

```python
# Unload notebook content
notebook.notes = []                 # Clear all notes from memory
notebook.subnotebooks = []          # Clear all subnotebooks from memory
notebook._notes_loaded = False      # Mark as unloaded
```

**What is removed from memory:**
- Encryption keys (Kp, Ks, Kc)
- Crypto object
- All note content
- All subnotebook structures
- File content cache
- Path references

**What remains:**
- Registry entry (notebook metadata, encrypted)
- Notebook folder on disk
- Secure session file (keys encrypted with system fingerprint)

### 10.4 Why This Matters

The lock button is not just a security feature. It is an **explicit memory manager**:

- **User-controlled memory** — the user decides when to unload a notebook, not the system
- **No background processes** — the system does not pre-load or cache notebooks
- **Explicit unloading** — locking is the only way to free notebook memory
- **Working memory alignment** — matches how human attention works: when you stop thinking about something, you clear it from working memory

### 10.5 Cognitive Alignment

The lock button externalizes the human cognitive process of clearing working memory:

| Human Cognition | System Implementation |
|-----------------|----------------------|
| Focus on one task | Notebook unlocked, loaded in memory |
| Switch tasks | Lock notebook, unload from memory |
| Return to task | Unlock notebook, reload from disk |

**The user controls what stays in memory. The system does not guess.**

### 10.6 Security Implications

- **Memory dump protection** — keys are not kept in memory longer than necessary
- **Screensaver/lock-screen protection** — user can lock notebooks before stepping away
- **Multi-user machines** — users can lock notebooks when switching accounts
- **No automatic unlocking** — the system never re-loads keys without user action

---

## 11. Recovery Mechanism

If the password is forgotten:

1. User enters phrase on any machine
2. System derives Ks
3. System decrypts `.tn_recovery` to retrieve Kp
4. System has both keys, can decrypt notebook
5. User sets new password (updates `.tn_recovery`, `.tn_password`, secure session)

**Recovery works on any machine, requires no cloud, no email, no central authority.**

---

## 12. Password Change Without Re-encryption

Changing password does not re-encrypt the notebook:

1. User enters old password (verifies Kp)
2. User enters new password
3. System derives new Kp'
4. System updates `.tn_recovery` with new Kp' (still encrypted with Ks)
5. System updates `.tn_password` with new Kc'
6. System updates secure session with new Kp'

**The notebook remains encrypted with Ks (unchanged).** Password change is instant regardless of notebook size.

---

## 13. No Phrase Storage

The recovery phrase is:

- Generated once (if auto-generated)
- Shown once
- Never written to disk
- Never hashed
- Never saved in any form

**The user alone owns the phrase. The system cannot recover it. The system cannot lose it.**

---

## 14. Git as Encrypted Sync Layer

Because all files are encrypted binary blobs:

- Any Git remote works (GitHub, GitLab, self-hosted)
- Public repositories are safe (JSON is encrypted)
- No separate sync service needed
- No subscription required

**Git becomes a free, encrypted sync infrastructure.**

---

## 15. Portability and Zero-Configuration Deployment

The application is distributed as:

- **Source code** — Python files with bundled assets
- **Linux executable** — Single file, no dependencies
- **Windows executable** — Single file, bundled editors (micro, nvim)
- **Docker container** — Multi-user, SSH-enabled, three deployment modes
- **USB drive** — Copy folder, run anywhere

**Properties:**
- No installation required
- No system dependencies
- No configuration files
- No environment variables
- No admin privileges needed
- Works on any machine with Python or the bundled executable

---

## 16. Encryption Overhead

Each encrypted file uses:

- 12 bytes nonce (random per encryption)
- 16 bytes GCM authentication tag
- Total overhead: **28 bytes per file**

No base64 encoding. No JSON wrappers. No metadata headers.

Example: A 1KB plaintext note becomes approximately 1,028 bytes encrypted.

---

## 17. How the System Was Built: The Logic Chain

This system was not designed from theory. It emerged from answering questions:

### Question 1: What do I need?
Privacy. Only I can read my notes.

### Question 2: What do I have?
A laptop. A folder. A user who will type something daily.

### Question 3: What is the problem with passwords?
Weak. Reused. Forgotten.

### Question 4: What if the password isn't the key?
Let password unlock the real key. The real key should be something stronger.

### Question 5: What is a strong key?
A recovery phrase. Like Bitcoin. 12 random words. Unbreakable.

### Question 6: But I can't type 12 words every day.
So use password daily. Phrase only for recovery and import.

### Question 7: What about the folder name?
Use it as salt. Same phrase on different notebooks = different keys.

### Question 8: What if I don't want random words?
Let users write anything. A poem. A story. A memory.

### Question 9: How do I bind keys to the machine?
System fingerprint. Hardware identifiers. Keys can't be copied.

### Question 10: How do I make encryption visible?
One symbol. Locked/unlocked. One key to toggle.

### Question 11: How do I manage memory?
Lock button unloads everything. Keys. Structure. Content. User controls RAM.

### Question 12: Why explicit memory management?
User knows when they're done. System shouldn't guess. Clear working memory when switching tasks.

### Question 13: How do I distribute without dependencies?
Bundle cryptography wheels for all platforms. Single executable.

### Question 14: What if I forget the password?
Recover with phrase. No cloud. No email. No support.

### Question 15: What if I change the password?
Password isn't the key. Just update the file that holds it. Instant.

### Question 16: How do I sync?
Git. Encrypted blobs. Public repos are safe. Free sync forever.

**Each step followed from the previous. The system is a chain of logic, not a collection of features.**

---

## 18. Prior Art Assertion

This document establishes prior art for the following concepts:

1. **Bundled cross-platform cryptography** — Cryptography libraries bundled with platform-specific wheels; zero-configuration deployment; single executable with all dependencies
2. **Flexible phrase system** — 6, 8, 12, 24 random words OR any custom text (poems, stories, sentences) as the ultimate encryption key
3. **Lock button as visual status** — Single key (`l`) toggles between 🔒 (locked) and 🔐 (unlocked); the symbol is the complete encryption interface
4. **Lock button as explicit memory manager** — Locking removes encryption keys from memory AND unloads the entire notebook structure (notes, subnotebooks, content cache) from RAM; unlocking loads keys from secure session and restores structure
5. **Cognitive alignment with working memory** — User controls what stays in memory; system does not pre-load or cache; matches human attention model
6. **Dual-key separation** — password for daily authentication, phrase for encryption
7. **Hardware-bound key storage** — keys encrypted with system fingerprint derived from machine identifiers
8. **Cross-encrypted key files** — three files serving distinct purposes: `.tn_test`, `.tn_recovery`, `.tn_password`
9. **Instant password change** — password change without re-encrypting the encrypted data
10. **No phrase storage** — recovery phrase shown once, never stored or hashed
11. **Git as encrypted sync** — encrypted blobs in Git repositories, including public
12. **Folder name as salt** — folder name used in all key derivations
13. **Portable encrypted folder** — self-contained, importable on any machine with phrase
14. **Zero-configuration deployment** — no installation, no dependencies, single executable

These concepts are described in public, timestamped documents as of April 2026. They constitute prior art under 35 U.S.C. § 102(a)(1).

---

## 19. 35 U.S.C. § 102(a)(1) Compliance

Under 35 U.S.C. § 102(a)(1), a person is entitled to a patent unless the claimed invention was patented, described in a printed publication, or in public use, on sale, or otherwise available to the public before the effective filing date of the claimed invention.

This document, and the accompanying source code repository, were made public in April 2026. All concepts disclosed herein are therefore part of the public domain as of that date. Any patent application filed after that date claiming these concepts is invalidated by this prior art.

---

## 20. Conclusion

Terminal Notes implements a dual-key encryption system where:

- Cryptography is bundled for all platforms (no installation required)
- The phrase can be 6, 8, 12, 24 random words OR any custom text (poems, stories, sentences)
- The phrase is the ultimate key (256-bit SHA256 output)
- The password is a convenience factor for daily use
- Keys are bound to hardware (system fingerprint)
- The lock button (🔒/🔐) is the complete encryption interface
- **The lock button is also an explicit memory manager** — it unloads keys, structure, and content from RAM
- Users control memory explicitly, matching human cognitive patterns
- Recovery works on any machine with the phrase
- Password changes are instant
- No phrase is ever stored
- Git provides free, encrypted sync
- The notebook folder is fully portable
- The application runs anywhere with zero configuration

The code is open. The design is documented. The user owns their data.

This disclosure is made in the public interest. It may be cited in any patent examination, litigation, or prior art search. No legal advice is offered. No warranty is provided. This document is a statement of fact.

---

**sys_ronin**  
April 2026  
sys_ronin@protonmail.com  
github.com/sys-ronin/terminal_notes
