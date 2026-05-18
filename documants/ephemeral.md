# The Ephemeral Coordination Architecture

## A Technical Description of Stateless, Hardware-Bound, Artifact-Driven Systems

---

## Preface

This document describes an architectural pattern where application state is not held in memory or managed by a central coordinator, but is instead distributed across portable, self-describing artifacts. The system does not "contain" data. It "visits" data. Coordination is not mediated by a server or a protocol, but emerges deterministically from the relationships encoded in the artifacts themselves.

This is not a product pitch. This is a technical description of how such a system operates, how it achieves security through ephemeral binding, and how it can function across network-accessible storage while maintaining the security properties of an offline application.

---

## Part 1: The Inversion of Control

### 1.1 The Conventional Model

In conventional application architecture, the application is the center. It starts, connects to resources, loads state into memory, maintains sessions, and responds to inputs. The data lives inside the system's memory or its attached database. The system is the subject. The data is the object.

This model creates an unavoidable attack surface. While the system is running, the state exists in memory. While the database is attached, the data exists on a mounted volume. The attack window is the lifetime of the process plus the persistence of the storage.

### 1.2 The Inverted Model

In the architecture described here, the relationship is reversed. The data does not live in the system. The system visits the data.

The application is a stateless interpreter. It does not load state into memory and keep it there. It reads artifacts (files, registry entries, vaults) as needed, performs a deterministic operation, and then discards all derived state. The artifacts remain on disk. The system leaves no trace.

| Conventional | Inverted |
|--------------|----------|
| Application starts → loads state → holds state → responds → may persist changes | Application starts → reads artifact A → resolves to artifact B → reads B → performs operation → forgets everything |
| State is active (in memory) | State is static (on disk) |
| System contains data | System visits data |
| Attack window is process lifetime | Attack window is single operation |

### 1.3 Why This Matters for Security

Because the system does not hold state between operations, an attacker who compromises the machine after an operation has completed finds nothing. There is no session to hijack. No keys remain in memory. No open file handles. No network sockets listening.

The only way to intercept data is to be present during the exact millisecond of the operation. This is a dramatically smaller attack window than any stateful system.

---

## Part 2: Memory and Key Lifecycle

### 2.1 The Reality of Key Caching

For interactive use, some in-memory key caching is necessary. Decrypting every note from the vault file for every keystroke would be unusable. The system maintains a short-term cache of decrypted keys for notebooks that are currently open.

However, this cache is **validated before every use**. If the underlying vault file disappears (USB unplugged, network share unmounted), the cache is invalidated immediately. The system does not continue with stale keys.

### 2.2 Key Lifecycle

| Phase | Location of Keys | Duration |
|-------|------------------|----------|
| **Notebook locked** | Vault file only (encrypted) | Indefinite |
| **Unlock operation** | Decrypted in memory temporarily | Milliseconds |
| **Notebook unlocked, active** | In `SessionKeyVault` cache | Until lock or exit |
| **After lock button pressed** | Explicitly deleted from memory | Immediate |
| **After process exits** | Freed by OS | Immediate |

### 2.3 Explicit User Control

The lock button provides immediate, user-controlled key clearing. No background timeout, no ambiguous "session expiry." The user decides when to end the trust window.

### 2.4 No Persistent Key Storage

Decrypted keys are never written to disk. They exist only in RAM. After process exit or explicit lock, no trace remains.

---

## Part 3: Practical Ephemeral Binding

### 3.1 The Problem with Traditional Hardware Binding

Traditional hardware binding uses a Trusted Platform Module (TPM). The TPM stores keys in a dedicated chip and proves the machine's identity through cryptographic attestation. This is secure, but it has drawbacks:

- TPMs are not available on all machines.
- TPMs have known vulnerabilities (SPI bus sniffing, physical probing).
- TPM‑bound keys cannot be moved or backed up (they are tied to the hardware).
- Recovery from hardware failure is complex and often data‑destructive.

### 3.2 Ephemeral Binding Defined

Ephemeral binding means: the binding between a key and a machine exists only at the moment of decryption. It is not stored anywhere. It is derived from runtime evidence of the machine's identity.

The key used to decrypt the vault entry is derived as:

```
entry_key = SHA256(timestamp + system_fingerprint)
```

Where `system_fingerprint` is derived from hardware identifiers (machine ID, product UUID, hostname, CPU information, etc.) and is **never stored on disk**. It is generated at runtime and discarded after use.

### 3.3 How It Works Across Network Storage

The vault file can be stored on any reachable address: a USB drive, a network share, an S3 bucket, a WebDAV server, or any HTTP‑accessible endpoint. The vault file contains encrypted entries, each bound to a specific machine's hardware fingerprint.

When the system reads a vault entry from a network location:

1. The application downloads (or reads) the encrypted blob.
2. The application derives the current machine's fingerprint at runtime.
3. The application attempts decryption using `entry_key = SHA256(timestamp + fingerprint)`.
4. If the fingerprint matches the one used when the entry was created, decryption succeeds. Otherwise, it fails.

**The network is not trusted.** The vault file could be intercepted, modified, or replaced. Decryption will simply fail. The security does not rely on TLS or any network‑level protection. The cryptography is sufficient.

### 3.4 The Multiple O(1) Translations

The system uses a chain of deterministic resolutions, each a simple lookup or hash:

| Step | Input | Output | Complexity |
|------|-------|--------|------------|
| 1 | System fingerprint | Notebook UUID list (from master registry) | O(1) dict lookup |
| 2 | Notebook UUID | Vault name + entry UUID (from master registry) | O(1) dict lookup |
| 3 | Vault name | Vault file path (from vault registry) | O(1) dict lookup |
| 4 | Entry UUID | Encrypted keys (from vault file) | O(1) dict lookup |
| 5 | Encrypted keys + fingerprint | Decrypted keys | O(1) AES‑GCM decryption |
| 6 | Decrypted keys + notebook data | Decrypted content | O(1) AES‑GCM decryption |

Each translation is independent and deterministic. The system never searches. It resolves.

---

## Part 4: Complete Ephemeral Coordination

### 4.1 The Mist Architecture

The "Fortress" model of security builds a hardened perimeter around a central database or service. Everything inside is trusted. This is the conventional approach.

The "Mist" model of security distributes trust across ephemeral components. No single component is trusted. Trust is rebuilt for each operation from evidence. This is what your system implements.

| Fortress Model | Mist Model |
|----------------|------------|
| Central database | Distributed artifacts |
| Persistent connections | Ephemeral resolution |
| Trust is granted (login) | Trust is demonstrated (decryption) |
| Attack surface is the perimeter | Attack surface is the operation |
| Recovery requires backups | Recovery requires phrase |

### 4.2 How Ephemeral Coordination Works

Coordination is not mediated by a protocol. There is no "handshake," no "heartbeat," no "leader election." Components find each other because the deterministic resolution chain always leads to the right artifact.

Consider three components stored in three different locations:

- **App and master registry** – local disk (or container)
- **Vault file** – network share (or S3 bucket)
- **Notebook data** – public Git repository

The system does not "connect" these components. It reads them in sequence. The master registry tells it where to find the vault. The vault tells it where to find the keys. The notebook data is located separately. There is no coordination. There is only resolution.

If any component is missing, the resolution fails at that step. The system reports "vault missing" or "notebook not found." There is no timeout, no retry storm, no cascading failure. The failure is immediate and local.

### 4.3 The Role of UUIDs as Static Bridges

UUIDs are not just identifiers. In this architecture, they are **static bridges** – permanent pointers that connect artifacts without requiring active coordination.

- A notebook's UUID appears in the master registry, linking the system fingerprint to the notebook.
- The master registry entry contains the vault name and entry UUID, linking the notebook to its key entry.
- The vault file uses the entry UUID as a key, linking the entry to the encrypted keys.
- The notebook's `structure.json` and `notes.json` use UUIDs to link notes to content.

These bridges are static (they do not change) and deterministic (the resolution is always the same). There is no "routing." There is no "service discovery." There is only reading.

---

## Part 5: Portability Scenarios

### 5.1 Local‑Only Operation (Standard)

- App and master registry: `~/terminal-notes/`
- Vault file: `~/terminal-notes/config/session.vault`
- Notebook data: `~/terminal-notes/notebooks_root/`

All components on the same machine. Simplest deployment.

### 5.2 USB‑Based Portable Operation

- App and master registry: `/mnt/usb/terminal-notes/`
- Vault file: `/mnt/usb/terminal-notes/config/session.vault`
- Notebook data: `/mnt/usb/notebooks/`

Entire system on a USB drive. Unplug the USB, and nothing is accessible. Plug into any machine, run from the USB, and the system works (using that machine's hardware fingerprint to decrypt the vault). The first time on a new machine, the recovery phrase is required.

### 5.3 Split‑Component Portable Operation (High Security)

- App and master registry: `/mnt/usb1/terminal-notes/`
- Vault file: `/mnt/usb2/vault.vault` (different USB)
- Notebook data: `/mnt/usb3/notebooks/` (third USB)

Three USBs. An attacker who steals any one USB cannot access the data. The vault alone is useless without the correct hardware fingerprint. The notebook alone is useless without the keys from the vault. The app alone is useless without the vault and notebook.

### 5.4 Network‑Accessible Vault

- App and master registry: Local machine
- Vault file: `https://my-server.com/vault.vault` (network share, S3, WebDAV)
- Notebook data: Local machine or network share

The vault is fetched over HTTP. The system does not require TLS for security (though TLS is recommended for availability). The vault entries are encrypted with the hardware fingerprint. Even if an attacker intercepts the vault file, they cannot decrypt it without the original hardware.

### 5.5 Public Notebook with Private Vault

- App and master registry: Local machine
- Vault file: Local USB
- Notebook data: Public GitHub repository

The notebook data is publicly visible. It is encrypted with the recovery phrase. Without the phrase, it is useless. The vault (on the USB) contains the keys derived from the phrase. The attacker would need both the USB (to get the keys) and the phrase (to decrypt the keys) – but the keys are already decrypted by the hardware fingerprint, so the attacker would also need the original machine.

Layers of protection.

### 5.6 Containerized Deployment with Ephemeral Fingerprint

- App and master registry: Docker container (ephemeral)
- Vault file: Network share or cloud storage
- Notebook data: Network share or Git remote

The container starts, derives its hardware fingerprint (from container ID, hostname, network stack), reads the vault from the network, decrypts the keys, reads the notebook data, performs operations, and exits. The container is destroyed. The fingerprint is gone. The vault entry for that container is now useless.

This is true ephemeral computing. The cloud provider never sees the decrypted keys. The network share never sees the hardware fingerprint. The container leaves no trace.

---

## Part 6: Key Lifecycle and Memory Management

### 6.1 Keys in RAM During Unlocked State

When a notebook is unlocked, the decrypted keys are stored in the `SessionKeyVault` cache. This is necessary for responsive interactive use. Decrypting every note from the vault file for every keystroke would be unusable.

The keys remain in memory until:

- The user explicitly locks the notebook (clears the cache)
- The application process exits (memory freed by OS)
- The vault file is detected as missing (cache invalidated)

### 6.2 Cache Validation

Before every cache hit, the system validates that the underlying vault file still exists:

```python
if notebook_id in self._cache:
    vault_path = self.manager._get_vault_path(notebook_id)
    if vault_path and os.path.exists(vault_path):
        return self._cache[notebook_id]
    else:
        del self._cache[notebook_id]  # Invalidate stale cache
```

If the vault is missing (USB unplugged, network share unmounted), the cache is cleared immediately. The system does not continue with stale keys.

### 6.3 Explicit Lock Button

The lock button provides immediate, user-controlled key clearing:

```python
def unload_notebook(self, notebook_id):
    if notebook_id in self.session_keys:
        del self.session_keys[notebook_id]
    if hasattr(self.session_keys, 'clear_cache'):
        self.session_keys.clear_cache(notebook_id)
```

No background timeout, no ambiguous "session expiry." The user decides when to end the trust window.

### 6.4 Process Exit

When the application terminates, the Python process is destroyed. All memory (including the `SessionKeyVault` cache) is freed by the operating system. Decrypted keys are not persisted anywhere.

### 6.5 No Persistent Key Storage

Decrypted keys are never written to disk. The vault file contains only encrypted keys. The `.tn_recovery` file contains the password key encrypted with the phrase key. The `.tn_password` file contains the combined key encrypted with itself (self-referential verification).

Plaintext keys exist only in RAM, and only while the notebook is unlocked.

---

## Part 7: Security Properties

### 7.1 No Persistent State

After each operation, the system holds no decrypted keys, no session tokens, no authentication credentials. The only state that exists is the static artifacts on disk (or network). An attacker who compromises the machine when no operation is running finds nothing.

### 7.2 Hardware Binding Without TPM

The vault entries are bound to the machine's hardware fingerprint, derived at runtime. No TPM is required. No TPM vulnerability applies. The fingerprint is never stored, so it cannot be stolen from disk.

### 7.3 Network‑Transparent Security

The vault file can be stored on any reachable network address. The security does not depend on TLS or network isolation. The cryptography (AES‑256‑GCM) protects the content. The hardware fingerprint protects the keys.

### 7.4 Deterministic Resolution (No Search)

The system never searches. It resolves: system fingerprint → notebook UUIDs → vault name → entry UUID → keys → decrypted content. Each step is O(1). There is no linear scan, no fuzzy matching, no pattern recognition. The attack surface is minimal.

### 7.5 Immediate Cache Validation

The `SessionKeyVault` cache validates the existence of the underlying vault file before every use. If the vault is missing (USB unplugged, network share unmounted), the cache is invalidated immediately. The system does not continue with stale keys.

### 7.6 Lock Button as Explicit Clear

The lock button clears the in‑memory cache immediately. The user can explicitly end the trust window. No background process, no timeout, no ambiguity.

### 7.7 Recovery Phrase as Root of Trust

All keys are ultimately derived from the recovery phrase. If all components are lost, the phrase can recreate everything. The phrase is never stored anywhere. The user is the sole authority.

---

## Part 8: Architectural Summary

| Property | Implementation |
|----------|----------------|
| **State management** | Artifact‑driven, stateless interpreter |
| **Key storage (encrypted)** | Portable vault files, network‑accessible |
| **Key storage (decrypted)** | RAM only, never on disk |
| **Cache validation** | Before every use, checks vault existence |
| **Key clearing** | Explicit lock button, process exit |
| **Coordination** | Deterministic resolution, no protocol |
| **Hardware binding** | Runtime fingerprint, no TPM |
| **Recovery** | High‑entropy phrase, offline |
| **Attack surface** | Operation‑only, no persistent state |
| **Portability** | Components can be separated across any storage |

---

## Conclusion

The architecture described here is not theoretical. It is implemented, tested, and used. It demonstrates that a system can be:

- **Stateless** – no persistent memory between operations
- **Hardware‑bound** – without a TPM or secure enclave
- **Portable** – components can be separated across diverse storage media
- **Network‑transparent** – vaults can be stored on any reachable address
- **Recoverable** – from loss of any single component
- **Deterministic** – no search, no fuzzy logic, no AI
- **Explicit** – user controls key clearing, cache validation, lock state

Keys exist in RAM while a notebook is unlocked. This is necessary for interactive use. However, the system provides:

1. **Cache validation** – stale keys are cleared when the vault disappears
2. **Explicit clearing** – lock button immediately removes keys from memory
3. **No disk persistence** – decrypted keys are never written to storage
4. **Process isolation** – keys die with the process

The pattern is called **Ephemeral Coordination** because trust is not stored. It is rebuilt for each operation from runtime evidence and static artifacts. The system does not contain data. It visits data. It does not maintain trust. It demonstrates trust.

This is not a comparison. This is a description. The architecture exists. The code is open. The documents are public. The reader may judge for themselves.
