# Prior Art Disclosure: Deterministic, Offline‑First, Item‑Addressable Append‑Only Log with Pluggable Merge Semantics

## A Technical Description of a General‑Purpose Data Structure for Distributed Synchronisation and Erasure

---

**Date of Disclosure:** May 2026
**Author:** sys_ronin
**Status:** Public, Timestamped, Irrevocable
**Repository:** github.com/sys-ronin/terminal-notes

---

## Summary

This document describes a **data structure** for distributed, offline‑first synchronisation of item‑level data. The structure is an **append‑only log** where each record is a complete snapshot of an item identified by a permanent UUID. Records are immutable and ordered by timestamp. An index maps UUIDs to the positions (or timestamps) of their records. Synchronisation between replicas is **deterministic**: for each UUID, a pluggable comparison rule selects the winning chain of records, and the merged log is linearised (sorted by timestamp). The resulting history contains **no merge commits** – it is a single, linear sequence.

The structure supports **permanent erasure** of items: all records containing a UUID can be removed from the log, optionally replaced by a tombstone record. Erasure is systematic, auditable, and does not require decryption of encrypted snapshots.

The data structure is **storage‑agnostic**. It can be implemented on any storage system that supports atomic append, read by position, and atomic replacement of the entire log (e.g., a file, a SQLite table, a key‑value store, or a version control system like Git). The description below is abstract; no specific storage is assumed.

The purpose of this disclosure is to establish prior art for the concepts described herein. No claim of invention is made. The reader may evaluate the structure for their own requirements.

---

## 1. Core Concepts

### 1.1 Item UUID

Every logical item (record, document, configuration entry, sensor reading, financial transaction, etc.) receives a **permanent, globally unique identifier** (UUID) at creation. The UUID never changes throughout the item’s lifetime.

### 1.2 Snapshot

A **snapshot** is the complete state of an item at a point in time. It is stored as an opaque byte array. The snapshot may be plaintext, compressed, or encrypted. The data structure does not inspect or modify the snapshot content.

### 1.3 Record

A **record** is an immutable tuple containing:

| Field | Type | Description |
|-------|------|-------------|
| `uuid` | 16 bytes | The permanent identifier of the item. |
| `timestamp` | 64‑bit integer | Author time (seconds since epoch). |
| `metadata` | variable | Optional application‑defined data (e.g., author priority, access control list, signature). |
| `snapshot` | variable | The complete state of the item (opaque bytes). |

Records are stored in **append‑only** order, typically by increasing timestamp.

### 1.4 Log

A **log** is an append‑only sequence of records. The position of a record in the log is its **sequence number** (starting from 0). The log may be stored as a file, a table, or any other linear storage.

### 1.5 Index

An **index** is a mapping from UUID to the list of positions (or timestamps) where that UUID appears in the log. The index can be rebuilt by scanning the log or maintained incrementally.

---

## 2. Operations

All operations are **deterministic** and require **no central coordinator**.

### 2.1 Append

**Input:** A snapshot (opaque bytes), its UUID, a timestamp, and optional metadata.
**Effect:**

1. Create a new record with the given UUID, timestamp, metadata, and snapshot.
2. Append the record to the end of the local log.
3. Update the local index: add the new position to the UUID’s list.

The operation is **local**. No communication with other replicas occurs.

### 2.2 Read Latest

**Input:** A UUID.
**Effect:**

1. Look up the UUID in the index. Obtain the list of positions (sorted by timestamp).
2. Take the last position in the list.
3. Retrieve the record from the log at that position.
4. Return the snapshot (and optional metadata).

Complexity: O(1) for index lookup + O(1) for log read.

### 2.3 Read at Time

**Input:** A UUID and a timestamp `T`.
**Effect:**

1. Look up the UUID in the index. Obtain the list of positions with associated timestamps.
2. Binary‑search the list to find the last record with timestamp ≤ `T`.
3. Retrieve the record from the log at that position.
4. Return the snapshot (and optional metadata).

Complexity: O(log N) where N is the number of records for that UUID.

### 2.4 Synchronise (Merge)

**Input:** A remote log (fetched from another replica).
**Effect:**

1. Fetch the remote log (all records, or only records newer than a known version).
2. Group all records (local and remote) by UUID.
3. For each UUID:
   - Let `chain_local` be the list of records for that UUID from the local log, sorted by timestamp.
   - Let `chain_remote` be the list from the remote log, sorted by timestamp.
   - Apply a **deterministic comparison function** to decide which chain to keep.
   - The comparison function is pluggable (see Section 3).
4. Collect all winning records (from all UUIDs).
5. Sort the winning records by timestamp (ascending).
6. Construct a **new log** containing the sorted records.
7. Replace the local log with the new log.
8. Rebuild the index from the new log.

The result is a **single, linear log** with no branches and no merge commits. The operation is deterministic: given the same local and remote logs and the same comparison function, any replica will produce the same merged log.

### 2.5 Erase (Permanent Deletion)

**Input:** A UUID.
**Effect:**

1. Create a new log containing all records from the current log except those whose UUID equals the input UUID.
2. Optionally, append a **tombstone record** with:
   - UUID = the erased UUID
   - Timestamp = current time
   - Metadata = `{"action": "ERASED", "original_timestamp": <timestamp of erased record>}`
   - Snapshot = empty (or a marker)
3. Replace the local log with the new log.
4. Rebuild the index.

Erased data cannot be recovered from the log. The tombstone record preserves an audit trail of the erasure.

---

## 3. Pluggable Comparison Function

The comparison function decides which chain (local or remote) is kept for a given UUID. It must be:

- **Deterministic** – same inputs always produce the same output.
- **Total** – always produces a winner (no ties).
- **Available to all replicas** – does not require a central oracle.

Examples of comparison rules:

| Rule | Inputs | Winner |
|------|--------|--------|
| **Newer timestamp** | Last record timestamp of each chain | Chain with the larger timestamp |
| **Higher priority** | Priority of the author (stored in metadata) | Chain whose author has higher priority |
| **Access control** | ACL of the item (stored in metadata) | Chain whose author is permitted |
| **Voting** | Signed votes from other replicas | Chain with more votes |
| **Merkle consensus** | Hash of the chain + proof from other replicas | Chain that is part of the longest proof chain |

The rule is **pluggable**. The data structure does not depend on the specific rule; it only requires that the rule is deterministic.

---

## 4. Storage‑Agnostic Implementation

The data structure can be implemented on any storage system that provides the following primitives:

| Primitive | Description | Example Implementations |
|-----------|-------------|--------------------------|
| **Atomic append** | Add a record to the end of the log without corrupting existing data. | File append (with `fsync`); SQLite `INSERT`; LMDB put with sequential key. |
| **Read by position** | Retrieve a record given its sequence number. | File `seek` + `read`; SQLite `SELECT WHERE id = N`; LMDB get. |
| **Read all records** | Iterate over all records in order. | File sequential read; SQLite `SELECT ORDER BY id`; LMDB forward cursor. |
| **Atomic log replacement** | Replace the entire log with a new log (for sync and erasure). | File rename; SQLite transaction + replace table; LMDB `mdb_copy` + swap. |
| **Index** | Mapping from UUID to positions. | In‑memory dictionary (rebuilt on restart); persistent key‑value store (e.g., LMDB). |

**No single storage system is mandatory.** The structure can be adapted to file systems, embedded databases, key‑value stores, or version control systems (like Git).

---

## 5. Properties

| Property | Why It Holds |
|----------|--------------|
| **Deterministic convergence** | Given the same logs and the same comparison function, every replica computes the same merged log. |
| **No central coordinator** | The merge is computed locally; only the logs themselves are exchanged. |
| **Offline‑first** | Replicas can operate independently and synchronise when a connection is available. |
| **Linear history** | The merged log is a single, linear sequence of records ordered by timestamp. No branches, no merge commits. |
| **Per‑item granularity** | Conflicts are resolved per UUID, not per file or per batch of records. |
| **Policy‑agnostic** | Any deterministic comparison rule (timestamp, priority, ACL, voting, etc.) can be used. |
| **Encryption‑agnostic** | Snapshots are opaque bytes; the data structure never decrypts them. |
| **Erasure‑capable** | Items can be permanently removed from the log, with optional tombstone auditing. |
| **No background processes** | Synchronisation is triggered on demand (user command or external event). No continuous polling. |
| **Scalable** | The cost of a sync operation is O(N) where N is the number of records that differ. Per‑UUID operations are O(1) with an index. |
| **Storage‑agnostic** | The structure can be implemented on files, databases, key‑value stores, or version control systems. |

---

## 6. Comparison with Existing Systems

| System | Granularity | Merge Semantics | Central Coordinator? | Offline‑First? | Erasure? | Storage Agnostic? |
|--------|-------------|-----------------|----------------------|----------------|----------|-------------------|
| Relational DB (primary‑replica) | Row | Last‑write‑wins (often) | Yes (primary) | No | Yes | No |
| Distributed KV (Dynamo, Cassandra) | Key | Last‑write‑wins or custom | No (gossip) | No (needs quorum) | Yes (tombstones) | No |
| CRDT library | Operation | Deterministic (CRDT merge) | No | Yes | No | No |
| Blockchain | Transaction | Consensus (PoW, PoS) | No (but global broadcast) | No | No | No |
| Event sourcing | Event | Replay events in order | Yes (event store) | No | No | No |
| Git | File | Three‑way merge (manual) | No | Yes | No | No |
| **This data structure** | **Item (UUID)** | **Deterministic, pluggable** | **No** | **Yes** | **Yes (with tombstone)** | **Yes** |

---

## 7. Extensions and Optimisations

### 7.1 Separation of Structure and Data

The log can store only **references** to snapshots (e.g., content hashes or keys in a content‑addressed store). This allows:

- Lazy loading – structure without content.
- Selective sync – sync only structure, or only content.
- Storage optimisation – different backends for metadata and large blobs.

### 7.2 Delta Compression

Instead of storing full snapshots for every record, the log can store **deltas** (compressed differences) against the previous snapshot of the same UUID. On read, the full snapshot is reconstructed by applying the deltas. This reduces storage size for frequently changed items.

### 7.3 Partitioning

The log can be partitioned by UUID prefix or by time range. This allows parallel reads and writes and improves scalability for high‑volume deployments.

### 7.4 Incremental Sync

Instead of transferring the entire log, replicas can exchange only records added since a known version (e.g., sequence number or timestamp). This reduces network bandwidth.

### 7.5 Pluggable Merge Policies

The comparison function can be implemented as a dynamically loaded module, allowing different policies for different item types or different deployment environments.

---

## 8. Example Use Cases

| Domain | How the Data Structure Applies |
|--------|-------------------------------|
| **Personal data synchronisation** (notes, files, settings) | UUID per note/file. Sync across devices using timestamp‑based rule (last write wins). Erasure for GDPR compliance. |
| **Medical records** | UUID per patient record. Merge rule: priority (doctor > nurse). Erasure for patient‑requested deletion. |
| **Supply chain tracking** | UUID per shipment. Merge rule: priority (shipper > carrier). Erasure after retention period. |
| **Financial ledgers (private)** | UUID per transaction. Merge rule: timestamp (later transaction wins) or consensus (signed votes). |
| **Collaborative editing** | UUID per paragraph or per element. Merge rule: priority (owner > contributor). |
| **Sensor networks** | UUID per sensor. Merge rule: timestamp (latest reading). Erasure for data retention compliance. |
| **Configuration management** | UUID per configuration entry. Merge rule: priority (security policy > developer). Erasure for secret removal. |
| **Legal contracts** | UUID per clause or per signature event. Merge rule: priority (signatory > reviewer). Erasure by court order. |
| **Scientific research data** | UUID per dataset. Merge rule: timestamp or priority (PI > postdoc). Erasure for retracted data. |

---

## 9. Prior Art Assertion

This document establishes prior art for the following concepts, all disclosed in public, timestamped materials as of May 2026:

1. **Append‑only log as the primary storage** for item‑addressed data.
2. **UUID as permanent item identifier** embedded in each record.
3. **Per‑item change chains** grouped by UUID.
4. **Deterministic, pluggable comparison function** for selecting winning chains.
5. **Linear history reconstruction** (merge‑free, sorted by timestamp).
6. **Storage‑agnostic design** – no dependency on a specific storage system.
7. **Systematic erasure** (removal of all records for a UUID) with optional tombstone.
8. **Separation of structure and data** for lazy loading and selective sync.
9. **Delta compression** for snapshot storage.
10. **Partitioning** for scalability.
11. **Incremental sync** via version numbers or timestamps.

The concepts disclosed herein are now part of the public domain. No party may obtain valid patent claims covering any concept described in this document.

---

## 10. Conclusion

This document describes a **data structure** for distributed, offline‑first synchronisation of item‑level data. The core is an append‑only log of UUID‑addressed records, each containing a complete snapshot of an item. Synchronisation is deterministic, pluggable, and produces a linear (merge‑free) history. Items can be permanently erased with optional audit trails.

The structure is **storage‑agnostic**; it can be implemented on files, databases, key‑value stores, or version control systems. It is suitable for a wide range of domains: personal data, medical records, supply chains, financial ledgers, collaborative editing, sensor networks, configuration management, legal contracts, and scientific research.

The disclosure is made in the public interest. It may be cited in any patent examination, litigation, or prior art search.

---

**sys_ronin**
May 2026
sys_ronin@protonmail.com
github.com/sys-ronin/terminal-notes
