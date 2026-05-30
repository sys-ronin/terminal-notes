# What Can Be Done: An Accidental Idea

## A General‑Purpose, Deterministic Conflict Resolution Engine for Distributed, Encrypted Data

---

## Preface

This document describes an idea that emerged from a specific implementation (a data management system). The author does not claim to have invented the concept of deterministic conflict resolution, nor does he claim that the idea is novel. He observed a pattern in his own work and is now describing it in general terms, independent of the original implementation.

The idea may be useful in other domains. It may not. The reader is invited to evaluate it for themselves.

The idea has two complementary parts:

1. **A synchronisation engine** that resolves conflicts deterministically, produces linear history, and requires no central coordinator.
2. **A systematic erasure engine** that permanently removes specific items from history while maintaining auditability.

Both operate on the same foundation: permanent item identifiers (UUIDs) embedded in every commit message, per‑item change chains, and deterministic rules.

The mechanisms work with encrypted data, require no background processes, and are triggered only when explicitly invoked – either by a user action or by an external event (e.g., a webhook from a remote repository). No background threads, no continuous polling.

The following sections describe these mechanisms in abstract terms.

---

## Part 1: The Core Mechanism (Synchronisation)

### 1.1 Per‑Item Identification

Every logical item in the system – a record, a document, a configuration entry, a sensor reading, a financial transaction – receives a permanent, globally unique identifier (UUID). This UUID never changes throughout the item’s lifetime.

Every change to an item produces a commit (or equivalent atomic version record) that contains:

- The UUID of the changed item.
- A timestamp (author time).
- A complete snapshot of the item’s data (or a reference to the complete snapshot).
- Any other metadata required by the application (e.g., author, priority, access control level).

The commit message (or equivalent metadata field) contains the UUID in plaintext. The item’s data may be encrypted, signed, or plaintext as required.

### 1.2 Per‑Item Change Chains

All commits across all repositories (or replicas) are grouped by UUID. Each UUID forms a **chain** of commits in chronological order. Because each commit changes exactly one UUID (by design constraint), the chains are disjoint.

### 1.3 Deterministic Conflict Resolution

When two replicas diverge (i.e., each has commits that the other does not), the system compares the chains for each UUID:

- If only one replica has commits for a UUID, that chain is kept.
- If both replicas have commits for the same UUID, a **deterministic comparison function** decides which chain wins.

The comparison function can be any rule that is:

- **Deterministic** (same inputs always produce the same output)
- **Total** (always produces a winner)
- **Available to all replicas** (no central oracle required)

Examples:

| Comparison Rule | Inputs | Winner |
|----------------|--------|--------|
| Newer timestamp | Last commit timestamp of each chain | Chain with the larger timestamp |
| Higher priority | Role/priority of the author (stored in commit metadata) | Chain whose author has higher priority |
| Access control list | ACL of the item (stored separately) | Chain whose author is permitted |
| Voting | Signed votes from other replicas | Chain with more votes |
| Merkle consensus | Hash of the chain + proof from other replicas | Chain that is part of the longest proof chain |

The rule is **pluggable**. The mechanism does not depend on the specific rule.

### 1.4 Merging Winning Chains

All winning commits (from all UUIDs) are collected into a single list and sorted by their original timestamp (ascending). This produces a **linear sequence of commits** that respects the original order of changes, independent of branch topology.

### 1.5 Linear History Reconstruction

A new branch (or equivalent isolated version line) is created. The system then replays each winning commit in order, writing the complete snapshot of each item (as stored in the commit) to the working tree, and committing with the original author, timestamp, and message.

Because each commit is a **complete snapshot**, no merging of file contents is needed. The replay is a simple binary copy.

After replay, the new branch replaces the old branch (e.g., via `git branch -f` and `git push --force` or equivalent). The result is a **linear, merge‑free history** that contains all winning commits from all replicas, ordered by their original timestamps.

### 1.6 Trigger Mechanism: No Background Processes

Synchronisation is **not** continuous. It is triggered explicitly by:

- A user command (e.g., `[S]ync` in a user interface).
- An external event (e.g., a webhook from a remote repository indicating that new commits have arrived).

The system does not run background threads, does not poll remote repositories, and does not maintain long‑running connections. When triggered, it performs a **single, atomic synchronisation operation**:

1. Fetch remote commits (if any).
2. Perform the conflict resolution and history reconstruction described above.
3. Push the result (if changed).

Between triggers, the system is completely idle. This design minimises resource consumption, avoids race conditions, and makes behaviour predictable.

### 1.7 Multi‑User and Branch‑Aware Triggering

The same trigger mechanism works for multi‑user scenarios:

- User A pushes commits to the shared remote repository.
- The remote repository can be configured to send a notification (webhook) to User B’s system.
- User B’s system, upon receiving the webhook, triggers a synchronisation operation.
- Alternatively, User B can trigger synchronisation manually.

The remote repository acts as a passive relay. It never initiates synchronisation; it only stores data and emits notifications when data changes. This is compatible with standard Git hosting platforms (GitHub, GitLab, Bitbucket, Gitea) and can be implemented with minimal infrastructure.

The synchronisation mechanism itself is **branch‑aware**. Different branches can be synchronised independently. Each branch maintains its own UUID chains and its own history. The same deterministic conflict resolution applies within each branch.

### 1.8 Handling No Common Ancestor

If the two replicas share no common ancestor (e.g., after a history‑rewriting operation), the system falls back to comparing global repository statistics: last commit timestamp or total commit count. The side with the newer timestamp (or, if equal, the side with more commits) wins. The losing side is either reset to the winning side or force‑pushed to the winning side.

---

## Part 2: Systematic Data Shredding (Permanent Erasure)

### 2.1 The Need for Permanent Erasure

Synchronisation preserves history. Soft deletion (removing an item from the current view) keeps the item in Git history. This is sufficient for reversible mistakes.

However, some data must be **permanently erased**:

- Personally identifiable information (PII) subject to GDPR right to be forgotten.
- Secrets accidentally committed (passwords, keys, tokens).
- Data that must be removed by legal order.
- Content that the user simply wants gone forever, with no possibility of recovery.

Standard Git cannot erase history without rewriting it. Rewriting history manually is error‑prone and dangerous. The mechanism described below automates it safely, systematically, and at the same item level as everything else.

### 2.2 The Mechanism: Custom Filtering

The system embeds a history‑rewriting tool as a library (e.g., `git-filter-repo` loaded as a Python module, not called as a subprocess). It extends the tool with custom filters designed for per‑item erasure.

#### UUID Erasure Filter

Input: a single UUID.
Process:

1. Iterate through every commit in the repository.
2. For each commit, remove the UUID from the commit message (if present).
3. For each blob (file) in each commit, if the blob is a JSON dictionary (e.g., `notes.json`), remove the key‑value pair whose key is the UUID.
4. If the blob is binary and not parseable as JSON, skip it (the UUID cannot appear in binary data unless explicitly placed there).
5. After processing, write the modified commit objects and blobs.
6. Track the number of commits and blobs modified.

Output: a repository history that contains no trace of the UUID. All commits that contained only that UUID (and no other changes) become empty and are pruned. The remaining commits are rewritten with the UUID removed.

#### Notebook Erasure Filter

Input: a root UUID and a list of all descendant UUIDs (collected recursively from the notebook’s structure).
Process: Apply the UUID erasure filter to every UUID in the list. Additionally, remove commits that contain the root UUID in the `root:` metadata field.
Output: a repository history that contains no trace of the notebook or any of its items.

### 2.3 The Erasure Workflow

1. User identifies item(s) to erase permanently.
2. System collects all affected UUIDs (one for a single note or file; a full tree for a notebook).
3. System runs the custom filter with the collected UUIDs.
4. Filter rewrites history, removing every occurrence of each UUID from commit messages and from JSON blobs.
5. System creates a **tombstone commit** with a special action type (`ERASED`) containing the UUID(s) and metadata about the erasure.
6. System force‑pushes the rewritten history to the remote repository.
7. All replicas that synchronise after this point receive the rewritten history. The erased items are gone from past and future.

### 2.4 Properties of the Erasure Mechanism

| Property | Description |
|----------|-------------|
| **Systematic** | The filter knows about UUIDs, JSON structure, and commit message format. It does not require manual grep or sed. |
| **Auditable** | The tombstone commit remains as a record that an erasure occurred. The content is gone; the fact of erasure is not. |
| **Compliant** | Meets GDPR “right to be forgotten” requirements. Data is removed from backups, replicas, and history. |
| **Safe** | Erasure requires explicit confirmation (e.g., typing `erase`). The filter does not run accidentally. |
| **Encrypted‑data safe** | The filter operates on raw blobs. If the blob is encrypted, the UUID will not appear in the ciphertext (assuming proper encryption). However, the UUID appears in the **plaintext commit message**. Removing it from the commit message is sufficient. The encrypted blob remains unchanged. |
| **No decryption required** | The filter never needs to decrypt. It operates on metadata (commit messages) and on JSON structure (which requires parsing, but the JSON values may be encrypted; the keys are plaintext). |

### 2.5 Relationship to Synchronisation

| Operation | Synchronisation | Erasure |
|-----------|----------------|---------|
| Works on | UUID chains | Individual UUIDs or trees |
| Preserves history | ✅ (linear, no merge) | ❌ (removes history) |
| Uses commit metadata | ✅ (UUIDs, timestamps) | ✅ (UUIDs, action types) |
| Never decrypts | ✅ | ✅ |
| Requires force push | ✅ (after reconstruction) | ✅ (after rewrite) |
| Trigger | User command or webhook | User command only (explicit) |

The two mechanisms are opposites, but they share the same foundation. Both rely on UUIDs embedded in commit messages. Both operate without decryption. Both require force push to update remotes. One builds history; the other subtracts from it.

---

## 3. Key Properties (Both Mechanisms)

| Property | Description |
|----------|-------------|
| **No central coordinator** | Each replica resolves conflicts independently using the same deterministic rule. The only communication is through the shared repository (passive relay). |
| **Deterministic convergence** | Given the same set of commits and the same comparison rule, all replicas will converge to the same final state. |
| **Linear history** | The final history contains no merge commits. It is a single straight line of commits ordered by timestamp. |
| **Encryption‑agnostic** | Both mechanisms work with encrypted data because they never need to decrypt. They operate on commit metadata (UUIDs, timestamps) and raw blobs. |
| **Storage‑efficient** | Because each commit contains a complete snapshot, replay is simple binary copy. No content merging is required. |
| **Policy‑agnostic** | Any deterministic comparison rule (timestamp, priority, ACL, voting, etc.) can be used. The mechanism does not depend on the rule. |
| **Offline‑first** | Each replica can operate independently and sync when the shared repository is reachable. |
| **No background processes** | Synchronisation is triggered only by explicit user action or external event (e.g., webhook). Erasure is triggered only by explicit user action. No background threads, no polling, no continuous connections. |
| **Triggerable from remote** | A remote repository can notify local replicas via webhook, enabling near‑real‑time synchronisation without background polling. |
| **Scalable** | The complexity of a sync operation is O(N) where N is the number of commits that differ between the two replicas (plus grouping overhead). Resolution per UUID is O(1). |
| **Large‑scale data** | The data is stored in blobs; the system only reads and writes complete snapshots. Delta compression is performed by the underlying storage layer (e.g., Git’s packfiles) and works efficiently if the encryption is stream‑cipher based. |

---

## 4. Potential Applications Beyond the Original Domain

The mechanisms described are not limited to any specific domain. They could be applied to any distributed, versioned, potentially encrypted data set where items are independent and conflicts can be resolved deterministically. The erasure mechanism is particularly relevant for domains subject to data retention regulations.

### 4.1 Medical Records

- **Item:** A patient’s record (identified by UUID).
- **Changes:** Updates from clinics, labs, pharmacies.
- **Conflict resolution:** Timestamp (most recent update wins) or priority (doctor > nurse > system).
- **Erasure:** Patient requests deletion of their record (GDPR). System erases all UUIDs associated with that patient. Tombstone commit records the erasure for audit purposes.
- **Advantages:** Linear audit trail, no merge conflicts, encrypted records can be stored in a public repository, offline access for remote clinics, verifiable compliance with right to be forgotten.

### 4.2 Supply Chain Tracking

- **Item:** A shipment or pallet (identified by UUID).
- **Changes:** Location updates, status changes, customs clearance.
- **Conflict resolution:** Priority (shipper > carrier > receiver) or timestamp.
- **Erasure:** Shipment data may need to be erased after retention period expires.
- **Advantages:** Each party has a local copy, syncs when online, full history preserved, no central server required, retention compliance automated.

### 4.3 Financial Ledgers (Private, Permissioned)

- **Item:** A transaction or account balance (identified by UUID).
- **Changes:** Debits, credits, reconciliation entries.
- **Conflict resolution:** Timestamp (later transaction wins) or a consensus rule (e.g., signed by multiple parties).
- **Erasure:** Regulatory requirement to delete data after a certain period (e.g., 7 years). Systematic erasure ensures compliance without manual intervention.
- **Advantages:** Not a blockchain (no proof‑of‑work, no global broadcast), but provides a linear, auditable, append‑only log with deterministic resolution. Suitable for private, permissioned environments.

### 4.4 Collaborative Code or Document Editing

- **Item:** A function, a paragraph, a configuration stanza (identified by UUID).
- **Changes:** Edits from multiple developers.
- **Conflict resolution:** Priority (lead > contributor), or manual approval via pull request (the comparison rule is “user chose this version”).
- **Erasure:** A secret accidentally committed. Erase the UUID containing the secret from history.
- **Advantages:** Linear history, no merge commits, works offline, syncs via Git (already supported), secure history rewriting for secrets management.

### 4.5 Sensor Networks (Edge Sync)

- **Item:** A sensor reading or a device configuration (identified by UUID).
- **Changes:** Readings, parameter updates.
- **Conflict resolution:** Timestamp (most recent reading wins) or source priority (primary sensor > secondary).
- **Erasure:** Old readings may need to be erased to comply with data retention policies.
- **Advantages:** Edge devices can operate offline, sync when connected, linear history preserved, no central coordinator needed, retention compliance automated.

### 4.6 Configuration Management (Infrastructure as Code)

- **Item:** A server configuration, a deployment manifest, a security policy (identified by UUID).
- **Changes:** Updates from engineers.
- **Conflict resolution:** Priority (security policy > configuration) or timestamp.
- **Erasure:** A secret (e.g., API key) committed to configuration. Erase the UUID containing the secret.
- **Advantages:** Complete audit trail, offline editing, deterministic sync, secure secret removal.

### 4.7 Legal Contracts (Smart Legal Contracts)

- **Item:** A contract clause or a signing event (identified by UUID).
- **Changes:** Amendments, reviews, approvals.
- **Conflict resolution:** Priority (signatory > reviewer) or timestamp.
- **Erasure:** Contract may need to be erased after legal retention period expires, or by court order.
- **Advantages:** Immutable audit trail, encrypted clauses can be stored privately, deterministic resolution avoids litigation over “which version is current”, verifiable erasure for compliance.

### 4.8 Scientific Research Data

- **Item:** A dataset, a figure, a result (identified by UUID).
- **Changes:** Corrections, annotations, peer reviews.
- **Conflict resolution:** Timestamp or author priority (PI > postdoc > student).
- **Erasure:** Data that was later found to be erroneous or that must be retracted.
- **Advantages:** Reproducible history, encrypted raw data can be shared publicly without revealing content, linear timeline of corrections, verifiable retraction.

---

## 5. Relationship to Existing Concepts

| Concept | Similarity | Difference |
|---------|------------|------------|
| **CRDTs (Conflict‑free Replicated Data Types)** | Both provide deterministic conflict resolution. | CRDTs require special data types and merge functions. This mechanism works with arbitrary blobs and resolves at the item level, not at the operation level. |
| **Git’s own merge** | Both operate on commit graphs. | Git’s merge uses a three‑way diff on file contents. This mechanism uses UUID chains and timestamp comparison; no diff is performed. |
| **Eventual consistency** | Both allow replicas to converge. | This mechanism provides a deterministic resolution rule and produces a linear history, not just eventual convergence. |
| **Blockchain / Distributed Ledger** | Both provide an append‑only log. | This mechanism does not require global broadcast, proof‑of‑work, or a consensus protocol. It relies on a shared repository (which may be untrusted) and deterministic local resolution. |
| **Operational Transformation (OT)** | Both support collaborative editing. | OT is typically real‑time and centralised. This mechanism is lazy (sync on demand), triggerable, and decentralised. |
| **Git filter‑repo (ad‑hoc usage)** | Both rewrite history. | This mechanism uses filter‑repo programmatically with custom filters designed for UUID‑based erasure. It is systematic, not ad‑hoc. |

---

## 6. Implementation Notes (Language‑ and Storage‑Agnostic)

To implement these mechanisms in a new domain, the following components are required:

### For Synchronisation

1. **Item identifier** – A permanent UUID assigned to each logical item at creation.
2. **Commit format** – A structured metadata field (e.g., commit message) that contains the UUID and the timestamp. The commit must reference a complete snapshot of the item’s data.
3. **Commit granularity constraint** – Each commit must change exactly one UUID. This may be enforced by the application.
4. **Grouping function** – A function that collects all commits, groups them by UUID, and builds chains in chronological order.
5. **Comparison function** – A deterministic rule that, given two chains for the same UUID, decides which chain wins.
6. **Replay function** – A function that takes a list of winning commits (sorted by timestamp), writes the complete snapshot of each item to the working tree, and creates a new commit with the original metadata.
7. **Branch replacement** – A function that replaces the old branch with the newly constructed linear branch.
8. **Fallback for no common ancestor** – A function that compares global repository statistics (last commit timestamp or total commit count) when the replicas share no common ancestor.
9. **Trigger interface** – A way to invoke synchronisation on demand (user command or webhook). No background processes.

### For Erasure

10. **History‑rewriting library** – A library capable of iterating through every commit and blob in a repository, modifying them, and writing new objects (e.g., `git-filter-repo`).
11. **UUID erasure filter** – A filter that, given a UUID, removes it from commit messages and from JSON blobs where it appears as a key.
12. **Notebook erasure filter** – A filter that applies the UUID erasure filter to a set of UUIDs and also removes commits containing a root UUID in metadata.
13. **Tombstone commit creator** – A function that creates a commit with a special action type (`ERASED`) containing the erased UUID(s) and metadata.
14. **Safety confirmation** – A requirement for explicit user confirmation (e.g., typing a confirmation phrase) before erasure.

These components can be implemented on top of any version control system that supports:

- Reading commit metadata (including a plaintext field).
- Reading and writing binary blobs.
- Creating branches and force‑pushing.
- Iterating through all commits (for erasure).

Git is a natural candidate, but the mechanism is not Git‑specific.

---

## 7. Limitations and Known Edge Cases

| Limitation | Description | Mitigation |
|------------|-------------|------------|
| **Discarding losing chains** | When a UUID has conflicting chains, the losing chain is discarded entirely. This loses the changes in that chain. | Suitable when the comparison rule correctly identifies the “correct” chain (e.g., newer timestamp for a single user, higher priority for a hierarchical organisation). Not suitable for use cases where both chains must be preserved. |
| **Timestamp trust** | The mechanism relies on commit timestamps. If clocks are tampered with, the comparison rule may produce incorrect winners. | Use monotonic clocks or rely on a different comparison rule (priority, ACL, voting). |
| **No common ancestor fallback** | When replicas share no common ancestor, the fallback (last commit timestamp or commit count) is heuristic. | Avoid this case by never rewriting history. If history rewrite is necessary (e.g., for erasure), accept that the fallback is a best‑effort heuristic. |
| **Erasure is irreversible** | Once history is rewritten, the erased data cannot be recovered. | Require explicit confirmation (typing a confirmation phrase). Provide clear warning. This is a feature, not a bug. |
| **Erasure requires force push** | After erasure, the remote history is rewritten. Other replicas must force‑pull or re‑clone. | This is unavoidable. Document the behaviour. Use tombstone commits to indicate that erasure occurred. |
| **Large binary items** | Storing complete snapshots of large binary items per commit may cause storage bloat. | Store large items in a content‑addressed store (CAS) and store only the reference in the commit. The mechanism works with references because they are also blobs. |
| **Replay of encrypted blobs** | The replay function writes raw encrypted blobs to the working tree. If the encryption key is not available, the blobs remain encrypted. | This is by design. The mechanism never requires decryption. If plaintext is needed, it must be decrypted separately. |
| **Erasure of encrypted blobs** | If the blob is encrypted and the UUID only appears in the commit message (not in the ciphertext), removing the UUID from the commit message is sufficient. The encrypted blob does not need to be modified. | This is a simplification. The filter only needs to parse JSON if the blob is known to be JSON. Otherwise, it skips blob modification. |

---

## 8. Conclusion

This document describes two complementary mechanisms that emerged from a specific implementation:

1. **A synchronisation engine** that resolves conflicts deterministically, produces linear history, requires no central coordinator, and is triggered only on demand (user command or webhook). No background processes.
2. **A systematic erasure engine** that permanently removes specific items from history, leaves audit trails (tombstone commits), and meets compliance requirements for data retention laws (GDPR, etc.).

Both mechanisms operate on the same foundation: permanent item identifiers (UUIDs) embedded in every commit message, per‑item change chains, and deterministic rules. Both work with encrypted data without requiring decryption. Both can be implemented on top of standard version control systems (e.g., Git) and can be triggered from remote repositories via webhooks.

Potential applications include medical records, supply chain tracking, financial ledgers, collaborative editing, sensor networks, configuration management, legal contracts, and scientific research data – any domain where data must be versioned, synchronised across replicas without central coordination, and, when required, permanently erased in a verifiable, auditable manner.

The idea is described here in abstract terms, independent of any specific implementation. The reader is invited to evaluate it for their own domain.

---

**End of Document**
```
