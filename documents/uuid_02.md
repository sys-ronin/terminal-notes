# UUID-Based Routing for Data-at-Rest Visitation

## A Technical Pattern for Stateless, Coordinated Access to Distributed Artifacts

This document describes a pattern in which data artifacts (files, key entries, registry records) remain completely inert until an operation requires them. When an operation is triggered, a short, deterministic chain of UUID lookups resolves the locations of the required artifacts. The system “visits” each artifact (reading only the necessary portions), performs the operation, and then discards all transient state. The artifacts return to rest.

The pattern is not presented as an invention; it is described as an observed behavior in a working codebase. The purpose is to document a mechanism that may be useful in other domains where data is distributed across multiple storage media (local disks, USB drives, cloud buckets, network shares) and coordination must be achieved without a central server or persistent background services.

---

## 1. Core Concept: Data at Rest, Visited on Demand

In conventional applications, data is often “loaded” into a central database or a memory cache and then actively managed by a long‑running process. In the pattern described here, **no data is loaded permanently**. Instead:

- Every data artifact (a JSON file, a vault entry, a Git commit) stays on its storage medium (disk, USB, cloud bucket).
- The system knows the location of these artifacts through **registry files** that contain UUID‑based pointers.
- When a user action (e.g., reading a note, editing a file, erasing a notebook) is requested, the system follows a fixed sequence of UUID lookups to **visit** the necessary artifacts.
- Each visit reads only the required piece of information (a dictionary value, an encrypted blob, a file path).
- After the operation finishes, all read data is discarded. The artifacts remain untouched except for explicit write operations (which are also atomic and leave no cached state).

Artifacts are stored on any reachable medium: local disk, USB drive, NFS share, S3 bucket, WebDAV server, or public Git repository. The system does not distinguish between local and remote storage; it only requires a path or URL.

---

## 2. Identifiers and Registries

| Component | Format | Location | Content |
|-----------|--------|----------|---------|
| **System fingerprint** | 32‑byte hash (derived at runtime) | Not stored | Hardware identifiers (machine ID, product UUID, hostname, etc.) |
| **Master registry** | JSON dictionary | Local disk (or network share) | Maps system fingerprint → list of notebook UUIDs; maps notebook UUID → (vault name, entry UUID, folder path) |
| **Vault registry** | JSON dictionary | Local disk (or network share) | Maps vault name → absolute path or URL to the vault file |
| **Vault file** | JSON dictionary | Any reachable location | Maps entry UUID → (encrypted keys, nonce, timestamp) |
| **Notebook folder** | JSON files | Any reachable location | `structure.json` maps item UUID → metadata; `notes.json` maps item UUID → encrypted content |
| **Item UUID** | 128‑bit identifier (RFC 4122) | Embedded in `structure.json`, `notes.json`, Git commits | Permanent identifier for a note, file, or subnotebook |

All lookups are O(1) because they are direct dictionary key accesses or fixed‑size cryptographic operations.

---

## 3. The Visitation Chain (Deterministic O(1) Resolution)

For any operation that requires accessing a notebook’s content, the system executes the following chain. Each step reads one artifact, extracts a UUID or a path, and then discards the artifact (except for the final step where content is either displayed or written back).

```
runtime system fingerprint
    ↓ (read master registry)
notebook UUID list (user selects one)
    ↓ (read master registry)
(vault name, entry UUID, folder path)
    ↓ (read vault registry)
vault file URL (e.g., https://bucket.s3.amazonaws.com/vault.vault)
    ↓ (HTTP GET vault file, read entry by UUID)
encrypted keys + nonce
    ↓ (AES‑GCM decryption using fingerprint)
plaintext keys (stay in memory only for the operation)
    ↓ (read notebook folder / structure.json)
item metadata (if accessing a specific note)
    ↓ (read notebook folder / notes.json)
encrypted content
    ↓ (decrypt with plaintext keys)
plaintext content → presented to user
```

After the operation, the plaintext keys and content are discarded. The next operation repeats the chain from the beginning (keys may be cached briefly for performance, but the cache is validated before every use).

---

## 4. Example: Reading a Note from a Vault on S3

Assume the following configuration:

- **Master registry** – stored on local disk.
- **Vault file** – stored in an S3 bucket: `https://my-bucket.s3.us‑east‑1.amazonaws.com/notebooks/work.vault`
- **Notebook folder** – stored on a USB drive mounted at `/mnt/usb/notebooks/`

The operation “read note with UUID `'abc...'`” proceeds as:

1. Derive system fingerprint (runtime, not stored).
2. Read local master registry, get notebook UUID list.
3. User selects notebook. Master registry returns `(vault name='work', entry UUID='xyz...', folder path='/mnt/usb/notebooks/')`.
4. Read vault registry (local), map `'work'` → `'https://my-bucket.s3.us‑east‑1.amazonaws.com/notebooks/work.vault'`.
5. HTTP GET the vault file. It contains a dictionary: `{'xyz...': {'encrypted_keys': '...', 'nonce': '...'}}`.
6. Decrypt using system fingerprint → plaintext keys.
7. Read `structure.json` from `/mnt/usb/notebooks/` to locate note metadata.
8. Read `notes.json`, lookup `'abc...'` → encrypted content.
9. Decrypt using plaintext keys → display note.

All steps are O(1). The system never “loads the notebook”; it visits each artifact exactly once per operation.

---

## 5. Cross‑Domain Applicability

The same UUID‑based routing pattern can be used in any domain where data is distributed across independent storage locations and must be coordinated without a central server.

| Domain | How the Pattern Can Be Used |
|--------|-----------------------------|
| **Electronic health records (EHR)** | Patient records stored in different hospital systems; master registry maps patient ID → record UUID → location URL. Each hospital maintains its own vault for encryption keys. |
| **Supply chain provenance** | Each shipping event is a UUID‑addressed log entry; master registry maps product ID → event UUIDs → locations (on‑premise or cloud). |
| **Personal knowledge management** | As implemented in the reference code: notes, files, and subnotebooks stored in portable folders, keys in portable vaults, registry on local disk. |
| **Decentralised identity (DID)** | System fingerprint serves as a hardware‑bound identifier; registry maps fingerprint → DID documents stored on any cloud. |
| **Edge IoT data aggregation** | Edge devices produce UUID‑addressed data blobs; master registry (replicated) maps device ID → blob UUID → location (FTP, S3, MQTT). |
| **Multi‑cloud backup & recovery** | Backup archives are written as encrypted vaults; master registry (backed up separately) maps archive ID → vault URLs across different cloud providers. |

In every case, the pattern requires only:

- A way to generate and store UUIDs for data items.
- A registry that maps a well‑known identifier (e.g., patient ID, product ID, device ID) to a UUID and a storage location.
- A deterministic lookup chain that respects O(1) complexity.
- The ability to read from arbitrary URLs or file paths.

No central database, active coordination service, or persistent background process is required.

---

## 6. Operational Properties

- **Data at rest** – Artifacts are never “mounted” or “loaded” into a long‑lived cache. They are read on demand and then closed.
- **Stateless operation** – The system does not keep any persistent memory between operations. After a read, all decrypted keys and content are discarded.
- **Portable storage** – Artifacts can be moved across storage media without changing the resolution chain, as long as the registry paths are updated.
- **O(1) complexity** – The number of steps is fixed (about 7–10). The time to resolve a UUID does not grow with the number of stored items.
- **Network transparency** – The same chain works for local files, network shares, HTTP URLs, and Git remotes.
- **Component loss tolerance** – Loss of any single artifact (registry, vault, notebook folder) does not cause permanent data loss, because the recovery phrase can recreate the missing parts.

---

## 7. Contrast with Conventional Approaches

| Aspect | Conventional Approach | UUID‑Based Routing (This Pattern) |
|--------|----------------------|-----------------------------------|
| **Data loading** | Data is loaded into a database or memory cache. | Data remains at rest; system visits it on demand. |
| **Coordination** | Central coordinator (database server, backend service, transaction manager). | No coordinator; coordination emerges from UUID pointers in static files. |
| **State** | Persistent state in RAM (caches, session objects). | No persistent state; transient state discarded after each operation. |
| **Complexity** | Lookups may be O(log n) or O(n) if indexes are missing. | O(1) deterministic resolution. |
| **Cross‑cloud** | Requires federation, replication, or a multi‑cloud control plane. | Artifacts placed in different clouds; registry maps to their URLs. |

---

## 8. Implementation Notes (from Reference Code)

The reference implementation (Terminal Notes) provides a working example of this pattern. Key code modules:

- `vault_manager.py` – Reads and writes vault files; maps vault names to URLs or file paths.
- `secure_session.py` – Derives system fingerprint; encrypts/decrypts vault entries with AES‑GCM.
- `session_key_vault.py` – Caches decrypted keys per notebook, but validates the vault file existence before each use.
- `terminal_notes_core.py` – Contains the master registry and the sequential resolution chain for notebook access.

The system does not use a database, a message queue, or any background daemon. All operations are triggered by user input and execute synchronously.

---

## 9. Known Limitations

- **Network latency** – When artifacts are stored on remote clouds, each HTTP request adds latency. The O(1) complexity refers to the number of lookups, not to actual round‑trip time.
- **Cache staleness** – The optional in‑memory key cache may become stale if the vault file is externally modified. The implementation includes a validation step that checks the vault file’s existence before returning a cached key.
- **Registry consistency** – The master registry and vault registry are separate files; they must be kept in sync. The reference code does this atomically during write operations.

These limitations are not inherent to the pattern; they can be mitigated by using faster storage, shorter cache timeouts, or atomic updates.

---

## 10. Conclusion

The UUID‑based routing pattern allows data artifacts to remain completely at rest until an operation requires them. A short, deterministic chain of O(1) lookups resolves the locations of the artifacts (which may be on local disks, USB drives, or cloud buckets). The system visits each artifact, reads the necessary information, performs the operation, and discards all transient state.

The pattern does not require a central coordinator, a persistent background process, or a dedicated database. It is suitable for any domain where data is distributed across independent storage media and coordination must be achieved without a server.

The description is based on a working codebase. The reader is invited to inspect the source code and verify the observable behaviour independently.
```
