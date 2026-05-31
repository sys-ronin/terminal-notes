# Prior Art Disclosure: A Version‑Controlled, Deterministic, Offline‑First Data Management System with Item‑Level Encryption and Pluggable Merge Semantics

## A Technical Description of a General‑Purpose Data Structure for Distributed Synchronisation, Cryptographic Separation, and Systematic Erasure

---

**Date of Disclosure:** May 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable 
**Repository:** github.com/sys-ronin/terminal-notes  

---

## Summary

This document describes a **version‑controlled data management system** for distributed, offline‑first synchronisation of item‑level data. The system is built on an **append‑only version store** where each version record contains a complete snapshot of an item identified by a permanent UUID. Snapshots may be encrypted; the system never needs to decrypt them for synchronisation or erasure. An index maps UUIDs to the list of versions where that item appears.

Synchronisation between replicas is **deterministic**: for each UUID, a pluggable comparison rule selects the winning chain of versions, and the merged history is linearised (sorted by timestamp). The resulting history contains **no merge commits** – it is a single, linear sequence.

The system supports **permanent erasure** of items: all versions containing a UUID can be removed from the version store, optionally replaced by a tombstone record. Erasure is systematic, auditable, and does not require decryption.

The system is **storage‑agnostic**. It can be implemented on any storage backend that supports atomic append, read by position, atomic replacement of the entire store, and optional encryption of snapshot blobs. Example backends include file systems, embedded databases (SQLite, LMDB), key‑value stores, and version control systems (Git).

The purpose of this disclosure is to establish prior art for the concepts described herein. No claim of invention is made. The reader may evaluate the system for their own requirements.

---

## 1. Core Concepts

### 1.1 Item UUID

Every logical item (record, document, configuration entry, sensor reading, financial transaction, etc.) receives a **permanent, globally unique identifier** (UUID) at creation. The UUID never changes throughout the item’s lifetime.

### 1.2 Snapshot with Optional Encryption

A **snapshot** is the complete state of an item at a point in time. It is stored as an opaque byte array. The snapshot may be:

- **Plaintext** – readable by any system.
- **Compressed** – using any compression algorithm (e.g., zlib, LZ4).
- **Encrypted** – using any symmetric or asymmetric encryption scheme.

The data management system **never inspects, decrypts, or modifies** the snapshot content. Encryption is applied **before** the snapshot is passed to the system. This allows the system to operate on encrypted data without ever having access to the encryption keys.

### 1.3 Version Record

A **version record** is an immutable tuple containing:

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | 16 bytes | The permanent identifier of the item. |
| `timestamp` | 64‑bit integer | Author time (seconds since epoch). |
| `metadata` | variable | Optional application‑defined data (e.g., author priority, access control list, signature). |
| `snapshot` | variable | The complete state of the item (opaque bytes, may be encrypted). |

Version records are stored in **append‑only** order, typically by increasing timestamp.

### 1.4 Version Store

A **version store** is an append‑only sequence of version records. The position of a record in the store is its **sequence number** (starting from 0). The store may be implemented as a file, a table, or any other linear storage.

### 1.5 Index

An **index** is a mapping from UUID to the list of sequence numbers (or timestamps) where that UUID appears in the version store. The index can be rebuilt by scanning the store or maintained incrementally.

---

## 2. Operations

All operations are **deterministic** and require **no central coordinator**.

### 2.1 Create a New Version (Append)

**Input:** A snapshot (opaque bytes, may be encrypted), its UUID, a timestamp, and optional metadata.  
**Effect:**

1. Create a new version record with the given UUID, timestamp, metadata, and snapshot.
2. Append the record to the end of the local version store.
3. Update the local index: add the new sequence number to the UUID’s list.

The operation is **local**. No communication with other replicas occurs. The snapshot is stored exactly as provided; encryption happens before this operation.

### 2.2 Read Latest Version

**Input:** A UUID.  
**Effect:**

1. Look up the UUID in the index. Obtain the list of sequence numbers (sorted by timestamp).
2. Take the last sequence number in the list.
3. Retrieve the version record from the store at that position.
4. Return the snapshot (still encrypted, if encryption was applied).

Complexity: O(1) for index lookup + O(1) for store read.

### 2.3 Read Version at a Specific Time

**Input:** A UUID and a timestamp `T`.  
**Effect:**

1. Look up the UUID in the index. Obtain the list of sequence numbers with associated timestamps.
2. Binary‑search the list to find the last version record with timestamp ≤ `T`.
3. Retrieve the version record from the store at that position.
4. Return the snapshot (still encrypted, if encryption was applied).

Complexity: O(log N) where N is the number of versions for that UUID.

### 2.4 Synchronise (Merge Two Version Stores)

**Input:** A remote version store (fetched from another replica).  
**Effect:**

1. Fetch the remote store (all version records, or only records newer than a known version).
2. Group all version records (local and remote) by UUID.
3. For each UUID:
   - Let `chain_local` be the list of version records for that UUID from the local store, sorted by timestamp.
   - Let `chain_remote` be the list from the remote store, sorted by timestamp.
   - Apply a **deterministic comparison function** to decide which chain to keep.
   - The comparison function is pluggable (see Section 3).
4. Collect all winning version records (from all UUIDs).
5. Sort the winning records by timestamp (ascending).
6. Construct a **new version store** containing the sorted records.
7. Replace the local version store with the new store.
8. Rebuild the index from the new store.

The result is a **single, linear version history** with no branches and no merge commits. The operation is deterministic: given the same local and remote stores and the same comparison function, any replica will produce the same merged store.

**Crucially, the system never decrypts the snapshots.** The merge operates only on UUIDs, timestamps, and metadata – not on the encrypted content.

### 2.5 Erase an Item (Permanent Deletion)

**Input:** A UUID.  
**Effect:**

1. Create a new version store containing all version records from the current store except those whose UUID equals the input UUID.
2. Optionally, append a **tombstone record** with:
   - UUID = the erased UUID
   - Timestamp = current time
   - Metadata = `{"action": "ERASED", "original_timestamp": <timestamp of erased version>}`
   - Snapshot = empty (or a marker)
3. Replace the local version store with the new store.
4. Rebuild the index.

Erased data cannot be recovered from the version store. The tombstone record preserves an audit trail of the erasure. Because snapshots may be encrypted, the system does not need to decrypt them during erasure; it simply removes the entire record.

---

## 3. Pluggable Comparison Function for Merge

The comparison function decides which chain (local or remote) is kept for a given UUID. It must be:

- **Deterministic** – same inputs always produce the same output.
- **Total** – always produces a winner (no ties).
- **Available to all replicas** – does not require a central oracle.

Examples of comparison rules:

| Rule | Inputs | Winner |
|------|--------|--------|
| **Newer timestamp** | Last version timestamp of each chain | Chain with the larger timestamp |
| **Higher priority** | Priority of the author (stored in metadata) | Chain whose author has higher priority |
| **Access control** | ACL of the item (stored in metadata) | Chain whose author is permitted |
| **Voting** | Signed votes from other replicas | Chain with more votes |
| **Merkle consensus** | Hash of the chain + proof from other replicas | Chain that is part of the longest proof chain |

The rule is **pluggable**. The data management system does not depend on the specific rule; it only requires that the rule is deterministic.

---

## 4. Encryption Integration

The system is designed to work with encrypted data without ever decrypting it.

| Operation | Does the system decrypt? | Explanation |
|-----------|--------------------------|-------------|
| **Create version** | No | Encryption happens before the snapshot is passed to the system. |
| **Read latest version** | No | Returns the encrypted snapshot as stored. Decryption is the caller’s responsibility. |
| **Read version at time** | No | Same as above. |
| **Synchronise (merge)** | No | The merge operates only on UUIDs, timestamps, and metadata. Encrypted snapshots are treated as opaque blobs. |
| **Erase item** | No | The system removes entire version records without inspecting the snapshot. |

**Security properties:**

- The system never possesses encryption keys.
- The system never decrypts user data.
- The system can be deployed in untrusted environments (e.g., public cloud) without exposing plaintext.
- The encryption scheme is pluggable; the system imposes no constraints on algorithm, key length, or key management.

---

## 5. Storage‑Agnostic Implementation

The system can be implemented on any storage backend that provides the following primitives:

| Primitive | Description | Example Implementations |
|-----------|-------------|--------------------------|
| **Atomic append** | Add a version record to the end of the store without corrupting existing data. | File append (with `fsync`); SQLite `INSERT`; LMDB put with sequential key. |
| **Read by position** | Retrieve a version record given its sequence number. | File `seek` + `read`; SQLite `SELECT WHERE id = N`; LMDB get. |
| **Read all records** | Iterate over all version records in order. | File sequential read; SQLite `SELECT ORDER BY id`; LMDB forward cursor. |
| **Atomic store replacement** | Replace the entire version store with a new store (for sync and erasure). | File rename; SQLite transaction + replace table; LMDB `mdb_copy` + swap. |
| **Index** | Mapping from UUID to sequence numbers. | In‑memory dictionary (rebuilt on restart); persistent key‑value store (e.g., LMDB). |

**No single storage backend is mandatory.** The system can be adapted to file systems, embedded databases, key‑value stores, or version control systems (like Git). The encrypted snapshots are stored as opaque blobs; the backend does not need to understand their format.

---

## 6. Properties of the System

| Property | Why It Holds |
|----------|--------------|
| **Deterministic convergence** | Given the same version stores and the same comparison function, every replica computes the same merged store. |
| **No central coordinator** | The merge is computed locally; only the version stores themselves are exchanged. |
| **Offline‑first** | Replicas can operate independently and synchronise when a connection is available. |
| **Linear history (no merge commits)** | The merged store is a single, linear sequence of version records ordered by timestamp. |
| **Per‑item granularity** | Conflicts are resolved per UUID, not per file or per batch of records. |
| **Policy‑agnostic** | Any deterministic comparison rule (timestamp, priority, ACL, voting, etc.) can be used. |
| **Encryption‑agnostic** | The system never decrypts snapshots; it treats them as opaque blobs. |
| **Erasure‑capable** | Items can be permanently removed from the version store, with optional tombstone auditing. |
| **No background processes** | Synchronisation is triggered on demand (user command or external event). No continuous polling. |
| **Scalable** | The cost of a sync operation is O(N) where N is the number of version records that differ. Per‑UUID operations are O(1) with an index. |
| **Storage‑agnostic** | The system can be implemented on files, databases, key‑value stores, or version control systems. |

---

## 7. Comparison with Existing Systems

| System | Granularity | Merge Semantics | Central Coordinator? | Offline‑First? | Erasure? | Encryption Aware? | Storage Agnostic? |
|--------|-------------|-----------------|----------------------|----------------|----------|-------------------|-------------------|
| Relational DB (primary‑replica) | Row | Last‑write‑wins (often) | Yes (primary) | No | Yes | No (DB may see plaintext) | No |
| Distributed KV (Dynamo, Cassandra) | Key | Last‑write‑wins or custom | No (gossip) | No (needs quorum) | Yes (tombstones) | No (KV sees plaintext) | No |
| CRDT library | Operation | Deterministic (CRDT merge) | No | Yes | No | No | No |
| Blockchain | Transaction | Consensus (PoW, PoS) | No (but global broadcast) | No | No | No | No |
| Event sourcing | Event | Replay events in order | Yes (event store) | No | No | No | No |
| Git | File | Three‑way merge (manual) | No | Yes | No | No (Git sees plaintext) | No |
| **This system** | **Item (UUID)** | **Deterministic, pluggable** | **No** | **Yes** | **Yes (with tombstone)** | **Yes (encrypted blobs)** | **Yes** |

---

## 8. Extensions and Optimisations

### 8.1 Separation of Metadata and Snapshot Storage

The version store can store only **references** to snapshots (e.g., content hashes or keys in a content‑addressed store). This allows:

- Lazy loading – metadata without snapshot content.
- Selective sync – sync only metadata, or only snapshots.
- Storage optimisation – different backends for metadata and large blobs.
- Encryption at different levels – metadata may be plaintext, snapshots encrypted.

### 8.2 Delta Compression

Instead of storing full snapshots for every version, the system can store **deltas** (compressed differences) against the previous snapshot of the same UUID. On read, the full snapshot is reconstructed by applying the deltas. This reduces storage size for frequently changed items. Deltas can be encrypted individually or together with the snapshot.

### 8.3 Partitioning

The version store can be partitioned by UUID prefix or by time range. This allows parallel reads and writes and improves scalability for high‑volume deployments. Each partition is an independent version store; cross‑partition references are not required because items are identified by UUID and each UUID resides in exactly one partition.

### 8.4 Incremental Sync

Instead of transferring the entire version store, replicas can exchange only version records added since a known version (e.g., sequence number or timestamp). This reduces network bandwidth. The receiving replica appends the new records and updates its index.

### 8.5 Pluggable Merge Policies

The comparison function can be implemented as a dynamically loaded module, allowing different policies for different item types or different deployment environments.

---

## 9. Example Use Cases

| Domain | How the System Applies |
|--------|------------------------|
| **Personal data synchronisation** (notes, files, settings) | UUID per note/file. Sync across devices using timestamp‑based rule (last write wins). Erasure for GDPR compliance. Snapshots encrypted with user’s key. |
| **Medical records** | UUID per patient record. Merge rule: priority (doctor > nurse). Erasure for patient‑requested deletion. Snapshots encrypted with patient’s or hospital’s key. |
| **Supply chain tracking** | UUID per shipment. Merge rule: priority (shipper > carrier). Erasure after retention period. Shipment data may be encrypted per partner. |
| **Financial ledgers (private)** | UUID per transaction. Merge rule: timestamp (later transaction wins) or consensus (signed votes). Transactions encrypted with private key. |
| **Collaborative editing** | UUID per paragraph or per element. Merge rule: priority (owner > contributor). Content may be encrypted with group key. |
| **Sensor networks** | UUID per sensor. Merge rule: timestamp (latest reading). Erasure for data retention compliance. Sensor readings may be encrypted per device. |
| **Configuration management** | UUID per configuration entry. Merge rule: priority (security policy > developer). Erasure for secret removal. Secrets encrypted before storage. |
| **Legal contracts** | UUID per clause or per signature event. Merge rule: priority (signatory > reviewer). Erasure by court order. Contract text encrypted with legal team’s key. |
| **Scientific research data** | UUID per dataset. Merge rule: timestamp or priority (PI > postdoc). Erasure for retracted data. Raw data encrypted with lab key. |

---

## 10. Prior Art Assertion

This document establishes prior art for the following concepts, all disclosed in public, timestamped materials as of May 2026:

1. **Version‑controlled data management system** with append‑only version store.
2. **UUID as permanent item identifier** embedded in each version record.
3. **Per‑item change chains** grouped by UUID.
4. **Deterministic, pluggable comparison function** for selecting winning chains.
5. **Linear history reconstruction** (merge‑free, sorted by timestamp).
6. **Encryption‑agnostic design** – system never decrypts snapshots.
7. **Storage‑agnostic design** – no dependency on a specific storage backend.
8. **Systematic erasure** (removal of all versions for a UUID) with optional tombstone.
9. **Separation of metadata and snapshot storage** for lazy loading and selective sync.
10. **Delta compression** for snapshot storage.
11. **Partitioning** for scalability.
12. **Incremental sync** via version numbers or timestamps.

The concepts disclosed herein are now part of the public domain. No party may obtain valid patent claims covering any concept described in this document.

---

## 11. Conclusion

This document describes a **version‑controlled data management system** for distributed, offline‑first synchronisation of item‑level data. The core is an append‑only version store of UUID‑addressed records, each containing a complete snapshot of an item. Snapshots may be encrypted; the system never needs to decrypt them. Synchronisation is deterministic, pluggable, and produces a linear (merge‑free) history. Items can be permanently erased with optional audit trails.

The system is **storage‑agnostic**; it can be implemented on files, databases, key‑value stores, or version control systems. It is **encryption‑agnostic**; it works with any encryption scheme without accessing keys. It is suitable for a wide range of domains: personal data, medical records, supply chains, financial ledgers, collaborative editing, sensor networks, configuration management, legal contracts, and scientific research.

The disclosure is made in the public interest. It may be cited in any patent examination, litigation, or prior art search.

---

**sys_ronin**  
May 2026  
sys_ronin@protonmail.com  
github.com/sys-ronin/terminal-notes
```
