# The Distributed Artifact Architecture

## A Technical Description of Separated State in Terminal Notes

---

## Preface

This document describes how the Terminal Notes application separates its operational state across multiple independent artifacts. The architecture does not rely on a centralized database, always-on service, or any single point of coordination. Instead, it distributes state across artifacts that can be stored, moved, and accessed independently.

The description is factual. No claims of superiority are made. The reader may assess the properties for themselves.

---

## Part 1: The Three Artifacts

The system maintains three distinct categories of artifacts. Each serves a separate function and can exist in a different location.

### 1.1 Master Registry (`notebooks_registry.json`)

**What it contains:**
- A mapping from notebook identifiers to system‑specific entries.
- For each system fingerprint, the path to the notebook folder, the name of the vault containing its keys, and the entry UUID within that vault.
- A lock state (whether the notebook is currently locked on that system).
- An autolock flag (whether the notebook should lock on application restart).

**What it does NOT contain:**
- Encryption keys (plaintext or encrypted).
- Notebook content (notes, files, structure).
- User passwords or recovery phrases.

**Location flexibility:** Can be stored on local disk, USB drive, network share, or within a container image.

### 1.2 Vault Registry (`vaults_registry.json`)

**What it contains:**
- A mapping from vault names (e.g., "default", "work_usb", "backup_cloud") to file system paths.
- A timestamp of when the mapping was last updated.

**What it does NOT contain:**
- Any encrypted keys.
- Any notebook data.
- Any user credentials.

**Location flexibility:** Lives next to the master registry by convention, but the path stored in the vault registry can point anywhere.

### 1.3 Vault File (`.vault` binary file)

**What it contains:**
- A set of encrypted entries, each identified by a UUID.
- Each entry contains a notebook identifier, a timestamp, a nonce, and the AES‑GCM encrypted combination of a password key and a phrase key.
- Each entry is encrypted with a system fingerprint (derived at runtime from hardware identifiers; never stored).

**What it does NOT contain:**
- Notebook content.
- Unencrypted keys.
- The system fingerprint (never stored anywhere).

**Location flexibility:** Can be stored on any readable medium: local disk, USB drive, network file share, S3 bucket, WebDAV server, or any HTTP‑accessible endpoint.

### 1.4 Notebook Folder

**What it contains:**
- `structure.json` – the hierarchy of notes and subnotebooks (encrypted with the phrase key).
- `notes.json` – the content of regular notes (encrypted with the phrase key).
- `files.json` – the content of file notes (encrypted with the phrase key).
- `.tn_test` – a verification marker (encrypted with the phrase key).
- `.tn_recovery` – the password hash and password key, encrypted with the phrase key.
- `.tn_password` – the combined key, self‑encrypted (used for verification).
- `.git` directory – full revision history (commit messages are plaintext; content remains encrypted).

**What it does NOT contain:**
- The phrase key.
- The password key (except in encrypted form inside `.tn_recovery`).
- Any information about where the vault or registry are located.

**Location flexibility:** Can be stored on local disk, USB drive, network share, or public Git repository.

---

## Part 2: How the Artifacts Relate

The artifacts reference each other, but **not bidirectionally**. The chain of resolution is one‑way:

1. **Master registry** contains:
   - For each system fingerprint: a vault name (`"default"`, `"work_usb"`, etc.)
   - For each system fingerprint: an entry UUID

2. **Vault registry** maps vault names to file paths.

3. **Vault file**, at the path from the vault registry, contains an entry indexed by the UUID from the master registry.

4. **Notebook folder** is referenced by the master registry (as a path). Its location is independent of the vault.

There is no reverse reference. The notebook folder does not know where its keys are stored. The vault file does not know which notebooks use its entries. Each artifact is blind to the others except through the explicit chain of resolution.

This means:
- You can move the notebook folder without updating the vault.
- You can move the vault without updating the notebook folder.
- You can change the registry to point to a different vault without touching the notebook data.
- You can have multiple registries pointing to the same vault (different systems sharing a vault file).

---

## Part 3: The Resolution Chain

When the application needs to access a notebook, it performs the following steps:

| Step | Operation | Input | Output | Artifact Accessed |
|------|-----------|-------|--------|-------------------|
| 1 | Generate system fingerprint | Hardware identifiers | 32‑byte key (runtime, not stored) | None (derived) |
| 2 | Look up fingerprint in master registry | Fingerprint hash | Notebook entry: vault name, entry UUID, notebook path | Master registry |
| 3 | Look up vault path in vault registry | Vault name | Absolute file path | Vault registry |
| 4 | Read encrypted entry from vault file | Entry UUID | Encrypted key blob (nonce + ciphertext) | Vault file |
| 5 | Decrypt key blob | Encrypted blob + fingerprint | Combined keys (password key + phrase key) | None (decryption) |
| 6 | Read notebook folder | Path from step 2 | Encrypted JSON files | Notebook folder |
| 7 | Decrypt notebook content | JSON files + phrase key | Plaintext structure and notes | None (decryption) |

Each step is deterministic. The system never searches. It resolves.

If any artifact is missing or inaccessible, the chain breaks at that step. The error is immediate and local: "vault not found," "notebook folder missing," "decryption failed." There is no timeout, no retry storm, no cascading failure.

---

## Part 4: Practical Use Cases

### 4.1 Default Operation (All Artifacts Local)

All three artifacts reside on the same machine. This is the simplest deployment. The user interacts with the application normally. The vault registry points to a local `.vault` file. The master registry points to local notebook folders.

### 4.2 Portable USB Drive

The user places the master registry, vault registry, and vault file on a USB drive. Notebook folders remain on the internal drive. When the USB is inserted, the application resolves the vault from the USB. When the USB is removed, resolution fails. The user controls access by physically removing the key material.

### 4.3 Split Artifacts Across Multiple USB Drives

The user places:
- Master registry on USB A
- Vault file on USB B
- Notebook folder on internal drive

To access the notebook, the user must insert **both** USB A and USB B. An attacker who steals any one USB gains nothing. The master registry without the vault cannot decrypt. The vault without the master registry does not know which entry belongs to which notebook. The notebook folder alone is encrypted.

### 4.4 Network‑Accessible Vault, Local Notebook

The user stores the vault file on a network file share or S3 bucket. The master registry (local) points to that URL (via a mounted path). The notebook folder remains local. The application can unlock the notebook without storing the vault locally. The network share never sees the decrypted keys. The local machine never retains the vault file.

### 4.5 Public Notebook Folder, Private Vault

The user pushes the notebook folder to a public Git repository. The notebook is encrypted with the phrase key. The vault remains on a private USB drive. Anyone can clone the notebook folder, but without the vault (which contains the phrase key encrypted with the user’s hardware fingerprint), they cannot decrypt it. The user can share the encrypted notebook publicly while retaining exclusive decryption capability.

### 4.6 Ephemeral Container with Network Vault

The user runs the application inside a Docker container that is destroyed after each use. The master registry is built into the container image. The vault file is fetched from a network share at runtime. The notebook folder is mounted from another network location. The container derives its fingerprint from its container ID and hostname. After the container exits, no trace remains on the compute node. The vault and notebook persist elsewhere, but the keys used to decrypt them are gone.

### 4.7 Disaster Recovery

The user’s laptop is stolen. The notebook folder and master registry were on the laptop. The vault was on a separate USB drive kept at home.

- The thief has the notebook folder (encrypted) and the master registry (which points to the missing vault). They cannot decrypt.
- The user buys a new laptop, installs the application, copies the notebook folder from a backup (or re‑clones from Git), inserts the USB vault, and enters the recovery phrase once to re‑authorize the new hardware.
- The notebook is recovered. The thief gains nothing.

### 4.8 Vault Migration

The user wants to move the vault from an old USB drive to a new one. They copy the vault file to the new drive, update the vault registry to point to the new path, and optionally delete the old vault. The notebook folder and master registry require no changes. The notebook continues to work.

### 4.9 Multi‑System Access with Single Vault

The user maintains the same vault file on a network share. They access the same notebook from multiple computers. On each computer, the first unlock requires the recovery phrase (to create a system‑specific vault entry). After that, each computer uses its own hardware fingerprint to decrypt its entry in the same shared vault file. The vault file contains separate entries for each system. No synchronization is required.

---

## Part 5: Unique Use Cases Introduced by This Architecture

### 5.1 Key Material as a Removable Peripheral

The vault file functions as a physical key. Removing it locks all notebooks that depend on it. No background timeouts, no session expiry – physical removal is immediate and absolute. This turns key management into a physical act.

### 5.2 No Central Coordination

The artifacts reference each other through simple path strings. There is no service discovery, no leader election, no heartbeat protocol. The system functions across any storage medium that can be addressed by a path. Coordination emerges from the one‑way resolution chain.

### 5.3 Selective Portability

Any artifact can be moved independently. The user can:
- Move the notebook folder without moving the vault.
- Move the vault without moving the notebook folder.
- Replace the master registry to change which notebooks are visible.
- Duplicate the master registry to have multiple views of the same vault and notebook.

### 5.4 Ephemeral Compute, Persistent Storage

The application can run in a temporary environment (container, cloud function, CI job) that derives a fingerprint, decrypts the vault, accesses the notebook, and then destroys itself. The vault and notebook remain on persistent storage. The compute node holds no long‑term state. This enables secure automation and batch processing.

### 5.5 Publicly Auditable, Privately Encrypted Notebooks

The notebook folder can be stored in a public Git repository. Anyone can see that changes occurred (commit history, timestamps, contributor names). The content remains encrypted. The phrase key is required to decrypt, and the phrase key is never stored. The public repository serves as a verifiable, immutable log of activity without exposing the content.

### 5.6 Hardware Migration Without Data Migration

When the user replaces their computer, they do not need to decrypt and re‑encrypt the notebook folder. They simply copy the master registry and notebook folder to the new machine, insert the vault (or point to it on a network share), and use the recovery phrase once. The notebook data never touches the old machine in plaintext after the migration. The new machine creates its own vault entry.

### 5.7 Offline Recovery from Any Single Component Loss

| Lost component | Recovery method |
|----------------|-----------------|
| Master registry | Recreate from backup or memory (paths can be re‑entered). The vault and notebook are unchanged. |
| Vault file | Restore from backup. The notebook folder remains encrypted but recoverable with the phrase (which recreates the keys). |
| Notebook folder | Restore from backup (or re‑clone from Git). The vault still contains the keys. |
| Hardware fingerprint (new machine) | Use the recovery phrase to create a new vault entry for the new machine. |

No single point of failure. The phrase is the ultimate root, but it is only needed when hardware changes.

---

## Part 6: Operational Properties

### 6.1 No Database Required

The system uses three JSON files (master registry, vault registry, and a binary vault file) plus a folder of JSON files for notebook data. No SQLite, no PostgreSQL, no in‑memory database. All artifacts are human‑readable (except the binary vault) and can be inspected, backed up, or moved with standard file tools.

### 6.2 No Always‑On Service

Coordination does not require a server. The artifacts are static. The application is stateless between operations. The system can function entirely offline, with network access used only to retrieve artifacts from remote storage.

### 6.3 Deterministic Resolution

Given the same artifacts and the same hardware, the resolution chain produces the same result every time. There is no randomness (except in cryptographic nonces, which do not affect the chain). This makes the system predictable and debuggable.

### 6.4 Failure Isolation

If the vault file is corrupted, the notebook folder remains readable (encrypted, but not destroyed). If the master registry is corrupted, the vault and notebook are untouched. Failures in one artifact do not cascade to others, except that resolution will stop at the failed step.

---

## Conclusion

The distributed artifact architecture separates operational state into three independent categories:

- **Master registry** – maps notebooks to systems (paths, vault names, entry UUIDs, lock states)
- **Vault registry** – maps vault names to file paths
- **Vault file** – stores encrypted key entries bound to hardware fingerprints
- **Notebook folder** – stores encrypted content and structure

Each artifact can be stored, moved, and accessed independently. The resolution chain is one‑way and deterministic. No central coordination is required. Failure in one artifact does not compromise others.

This architecture enables use cases that are difficult or impossible with monolithic storage: removable key material, portable vaults, publicly auditable encrypted notebooks, ephemeral compute with persistent storage, and recovery from loss of any single component.

The description is factual. The reader may evaluate the properties for their own requirements.
