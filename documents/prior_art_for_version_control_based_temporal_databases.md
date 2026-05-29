# Prior Art Disclosure: A Universal Architecture for Version‑Control‑Based Temporal Databases

## What This Document Describes

This document describes a class of systems that build an item‑level temporal database on top of any version control system (VCS). The architecture relies only on the core primitives that every VCS provides. The description is independent of any particular implementation, language, or tool. It is a logical specification.

The purpose of this disclosure is to place the described architecture in the public domain. No claim of invention is made. The architecture is described as a logical consequence of the properties of version control systems.

## 1. Core Primitives of Every Version Control System

Every version control system, regardless of its specific design, provides a small set of fundamental operations and data structures. These primitives are necessary and sufficient for the system to function as a version control tool. They are universal.

### 1.1 Immutable Snapshot

Every VCS records the state of a set of files at a point in time. This recorded state is immutable. Once created, it cannot be changed. In Git, this is called a *commit* and contains a complete snapshot of the project directory at that moment. In Subversion, it is a *revision*. In Mercurial, it is a *changeset*. The name varies, the property does not.

> “Commits are the core version‑control primitive … they represent an immutable snapshot of a filesystem and can be accessed with an ID.” 

### 1.2 Immutable Revision Identifier

Every snapshot has an identifier that is unique within the repository. The identifier is derived from the content of the snapshot, from a timestamp, from a sequential number, or from a combination of these. In Git, the identifier is a SHA‑1 hash of the commit object. In Subversion, it is a sequential revision number. In Mercurial, it is a changeset ID.

The identifier is stable. It does not change after the snapshot is created. It can be used to refer to that snapshot at any future time.

### 1.3 Parent Link

Every snapshot (except the first) has a reference to one or more preceding snapshots. This creates a directed acyclic graph (DAG) of history. The ability to navigate from a snapshot to its parent is a fundamental operation.

> “Parents are commits that are related to a commit, forming a directed acyclic graph.” 

In Git, the parent is accessed via the `^` suffix. In Mercurial, via revision numbers or the `parent()` revset. In Subversion, the parent is implicit in the sequential revision numbering. The operation exists in every VCS.

### 1.4 Metadata Attachment

Every snapshot can carry arbitrary metadata. At minimum, this includes the author, timestamp, and a log message. The log message is a free‑form text field. The ability to attach structured or unstructured data to a snapshot is universal.

### 1.5 Query by Metadata

Every VCS provides a mechanism to search or filter snapshots based on their metadata. In Git, `git log --grep` searches commit messages. In Mercurial, `hg log -k` searches commit messages. In Subversion, `svn log --search` performs a similar function.

> “We can use the --grep option to find specific strings in commit messages.” 

The ability to retrieve the set of snapshots whose metadata matches a pattern is a core operation.

## 2. Universal Data Model

A temporal database built on these primitives requires a persistent identifier for each logical item. This identifier must satisfy two properties:

1. **Global uniqueness** – no two items share the same identifier.
2. **Permanence** – the identifier does not change when the item is renamed, moved, or modified.

Universally Unique Identifiers (UUIDs) satisfy both properties. Any other identifier with the same properties (e.g., content hashes, deterministic random generators) is equally suitable.

The data model consists of three separate logical partitions:

| Partition | Contents |
|-----------|----------|
| **Structure** | Hierarchy and metadata of items (names, UUIDs, parent relationships) |
| **Content (text)** | Text content of regular items, keyed by UUID |
| **Content (binary)** | Binary content of file‑type items, keyed by UUID |

The separation of structure from content is not mandatory but follows from the principle of minimizing the scope of changes. A modification to an item's content does not require rewriting the structure partition.

## 3. Universal Operations

### 3.1 Recording a Change

When a change is made to any item, the system:

1. Updates the affected partition(s) (structure, text content, or binary content).
2. Creates a new immutable snapshot of the entire data set.
3. Attaches a structured message to the snapshot containing:
   - The action type (e.g., CREATED, UPDATED, DELETED, RENAMED, RESTORED, ERASED)
   - The content type (e.g., NOTE, FILE, NOTEBOOK, SUBNOTEBOOK)
   - The UUID of the affected item
   - The UUID of the parent container (if applicable)
   - The UUID of the root container (if applicable)
   - Change statistics (e.g., number of characters added or removed)

The snapshot becomes the new head of the history. The previous state remains accessible via the parent link.

### 3.2 Query by UUID

To find all snapshots that mention a specific UUID, the system executes a metadata query for the UUID string. The exact syntax varies by VCS, but the operation exists in all.

### 3.3 Query by Action Type

To find all snapshots that record a specific action (e.g., all DELETED operations), the system executes a metadata query for the action string anchored at the beginning of the message. The anchor ensures that incidental mentions of the word are not matched.

### 3.4 Reconstruction of an Item at a Snapshot

To reconstruct an item as it existed at a specific snapshot, the system:

1. Retrieves the structure partition from that snapshot.
2. Locates the item by its UUID.
3. Retrieves the appropriate content partition (text or binary) from the same snapshot.
4. Extracts the content using the UUID as the key.

The reconstruction does not modify the live data. It operates on historical snapshots only.

### 3.5 Restoration of a Deleted Item

To restore an item that was deleted, the system:

1. Locates the snapshot that recorded the deletion (by query for DELETED + UUID).
2. Retrieves the parent snapshot (the state immediately before deletion) using the parent link.
3. Reconstructs the item from the parent snapshot.
4. Merges the reconstructed item into the current structure and content partitions.
5. Creates a new snapshot recording the restoration.

The parent link is the critical operation. Without the ability to navigate to the previous state, restoration is not possible.

## 4. Necessary and Sufficient Conditions

The architecture described above requires exactly five capabilities from the underlying VCS:

| Capability | Universal VCS Operation |
|------------|------------------------|
| Immutable snapshot | `commit` (Git), `svn commit` (Subversion), `hg commit` (Mercurial) |
| Snapshot identifier | SHA‑1 hash (Git), revision number (Subversion), changeset ID (Mercurial) |
| Parent navigation | `^` suffix (Git), `parent()` revset (Mercurial), `svn log -r <N>` (Subversion) |
| Metadata attachment | commit message (all VCS) |
| Metadata query | `git log --grep`, `hg log -k`, `svn log --search` |

These five capabilities are present in every general‑purpose VCS. No additional features are required.

## 5. Universality Across VCS

The architecture does not depend on any VCS‑specific feature:

- **Not dependent on distributed model** – works equally with centralized VCS.
- **Not dependent on content addressing** – works with sequential revision numbers.
- **Not dependent on branching** – works with linear history.
- **Not dependent on staging area** – irrelevant to the core operations.
- **Not dependent on merging** – restoration uses only parent navigation, not merge.
- **Not dependent on shallow clones** – the repository is assumed complete.

Therefore, the architecture can be implemented on any VCS, past, present, or future, that provides the five primitive operations.

## 6. Prior Art Assertion

The concepts described in this document – including but not limited to the use of UUIDs as permanent item identifiers, the three‑partition data model, the structured commit message format with action and content types, the query by action type for deleted items, the reconstruction of an item from a parent snapshot, and the restoration via parent navigation – are disclosed in public, timestamped documents as of April 2026.

These disclosures constitute prior art under:

- **United States:** 35 U.S.C. § 102(a)(1) – A person is entitled to a patent unless the invention was described in a printed publication before the patent's effective filing date.
- **European Patent Convention:** Article 54(2) – The state of the art comprises everything made available to the public before the filing date.
- **EPO Enlarged Board of Appeal Decision G 1/23 (2 July 2025):** Public availability alone is sufficient for prior art; no requirement of reproducibility applies.

No party may obtain valid patent claims covering any concept disclosed herein in any jurisdiction.

## Conclusion

A temporal database that tracks items across their entire lifecycle – creation, modification, deletion, and restoration – can be built on top of any version control system that provides immutable snapshots, unique identifiers, parent navigation, metadata attachment, and metadata query. These five primitives are universal. The architecture described is therefore universal.

The purpose of this disclosure is to place this architecture in the public domain, not to claim ownership. The architecture is described as a logical consequence of the properties of version control systems. It belongs to no one.
