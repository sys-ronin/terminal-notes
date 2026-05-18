# Unified Prior Art Disclosure: Decentralised UUID Mesh Architecture

## A Comprehensive Technical Description of Stateless, O(1), Offline‑Capable Data Access, Authentication, and Management

---

**Date of Disclosure:** May 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** github.com/sys-ronin/terminal-notes  

---

## Summary

This document describes a **decentralised data architecture** built on UUID‑addressed resources, static registries, and deterministic resolution chains. It unifies three orthogonal concerns:

1. **Data access** – parallel, multi‑hop resolution across heterogeneous storage backends (file systems, object stores, databases) without central coordination.
2. **Authentication & authorisation** – per‑hop, offline‑capable security using self‑validating credentials (signed JWTs, pre‑signed URLs, client certificates).
3. **Management plane** – stateless, thread‑free administration (configuration updates, revocation, health checks, log collection) using the same one‑time request model.

All operations are O(1) per resolution step, require no background threads, no persistent connections, no always‑on daemons, and work fully offline. Partial implementations exist in the Terminal Notes system (UUID permanence, registry resolution, hardware‑bound keys, active cache validation). The full architecture described here is a logical extension of those patterns and is disclosed for prior art purposes.

---

## 1. Core Principles

### 1.1 UUID as Permanent Identifier
Every resource – data record, encryption key, policy document, configuration entry, audit log – receives a UUID at creation. The UUID never changes, even if the resource’s content or location changes. It serves as a stable, location‑independent foreign key.

### 1.2 Registry as Routing Table
A **registry** is a mapping from a UUID to either:
- A storage location (path, URL, database key), or
- Another UUID (a “hop” to be resolved next).

Registries are ordinary data artifacts (JSON files, database tables, key‑value stores). Multiple registries can coexist and be chained; there is no central registry.

### 1.3 Deterministic O(1) Resolution Chain
To access a resource:
1. Look up UUID `U` in a registry → obtain either a location `L` or another UUID `V`.
2. If `L` is a location, fetch the resource from `L`.
3. If `V` is a UUID, set `U = V` and repeat.

Each registry lookup is O(1) (hash table). The chain length is fixed per operation and does not grow with the total number of resources. The system never searches; it resolves.

### 1.4 Stateless, One‑Time Requests
All operations – data access, key retrieval, policy verification, administrative updates – are single, independent requests. No session, no persistent connection, no shared state. Each request carries all necessary authentication and authorisation evidence (signed JWT, pre‑signed URL, client certificate). The recipient verifies the credential locally and responds.

### 1.5 No Background Threads, No Always‑On Daemons
Components do not run background threads. They do not maintain heartbeats, keep‑alive connections, or background caches. A component can remain completely idle (not even running) until a request arrives. Activation is the request itself – O(1) resolution and fetch. OS‑level file notifications (e.g., `inotify`) can wake a process when a registry or configuration file changes, but no application‑level background thread is required.

---

## 2. Components

| Component | Role | Storage Examples |
|-----------|------|------------------|
| **Root registry** | Maps a top‑level identifier (user ID, system fingerprint, domain) to a root UUID. | JSON file, database table, Redis hash |
| **Node registry** | Maps a UUID to a storage location or to another UUID. | Key‑value store, file system path, object storage URL |
| **Data payload** | The actual content (document, row, blob). May contain UUIDs of other resources. | JSON, binary blob, SQL row |
| **Link record** | A separate record that holds a UUID and optional metadata (type, timestamp). | Inline within payload or separate entry |
| **Administrative registry** | Maps administrative UUIDs to configuration, revocation lists, audit log locations. | JSON file, append‑only file, database table |

All components are ordinary data artifacts. No component requires a long‑running service.

---

## 3. Resolution Algorithm (Single Chain)

Given a starting UUID `U`, the system resolves the associated data as follows:

1. **Look up `U` in the node registry** → obtain either a storage location `L` or another UUID `V`.
2. If `L` is a location, fetch the data payload from `L` (using the access method stored in the registry – file read, HTTP GET, database query).
3. If `V` is a UUID, set `U = V` and repeat from step 1.
4. Optionally, if the fetched data payload contains embedded UUIDs, the resolver may continue to follow those (branching, see Section 6).

Each registry lookup is O(1). The total number of steps is the depth of the chain, which is fixed per operation.

---

## 4. Layered Independence

The architecture separates concerns into independent layers, each with its own UUID space and resolution registry.

| Layer | Content | UUID Space | Registry |
|-------|---------|------------|----------|
| **Data layer** | Encrypted or plain content | Data UUIDs | Data registry (UUID → storage location) |
| **Metadata layer** | Attributes, relationships, lineage | Metadata UUIDs | Metadata registry (UUID → metadata record) |
| **Security policy layer** | Access control rules | Policy UUIDs | Policy registry (UUID → policy document) |
| **Key layer** | Encryption keys (DEKs, master keys) | Key UUIDs | Key registry (UUID → key storage location) |
| **Administrative layer** | Configuration, rotation schedules, audit rules | Admin UUIDs | Admin registry (UUID → admin record) |

Each layer can be:
- Stored independently (different physical locations, different storage systems).
- Managed by different authorities.
- Updated without affecting other layers.
- Resolved in O(1) time via its own registry.

### 4.1 Encryption as Independent Layer
- Data is stored encrypted using a data encryption key (DEK) identified by a UUID.
- The DEK UUID resolves to a location where the DEK is stored (key vault, HSM, encrypted file).
- The master key is another UUID, resolved through a separate registry.
- Each hop can be managed by a different authority with its own authentication.

Example (three hops):
1. Resolve data UUID → obtain encrypted blob location.
2. Resolve DEK UUID → obtain encrypted DEK location.
3. Resolve master key UUID → obtain master key.

All steps are O(1). The data cannot be decrypted without resolving all three hops.

### 4.2 Security Policy as Resolvable Resource
- Access control rules are stored as policy documents, each identified by a policy UUID.
- A user’s capability token contains policy UUIDs, not the rules themselves.
- The system resolves each policy UUID to fetch the rules (cached with TTL).
- Policies can be updated by writing a new policy document at the same UUID (or a new UUID with updated metadata).

Policy changes propagate without touching data or restarting services. The resolution mechanism is identical to data access.

---

## 5. Parallel Independent Chains

A single user request can initiate **multiple independent resolution chains concurrently**. Each chain starts from a different UUID and proceeds through its own sequence of lookups. The results are combined when all chains complete.

**Example: Composite resource fetch**
- Chain A: user UUID → registry → avatar location → fetch avatar
- Chain B: user UUID → registry → document list location → fetch list
- Chain C: user UUID → registry → configuration location → fetch config

All three chains run in parallel. The total latency is the maximum of the individual chain latencies, not the sum. No central coordinator orchestrates the chains; they are independent.

---

## 6. Multi‑Hop Chains with Branching (Fan‑Out)

When a data payload contains **multiple new UUIDs**, the system can follow all of them in parallel. This creates a fan‑out pattern.

**Example: Document with embedded images**
1. Resolve document UUID → fetch document text.
2. Parse the text to extract three image UUIDs (`img_1`, `img_2`, `img_3`).
3. Start parallel resolution chains for each image UUID:
   - Each image UUID → registry → image location → fetch image data.

The parallelism is data‑driven: the number of parallel tasks depends on the content, not on a predefined workflow. The resolver does not need to know the fan‑out in advance.

---

## 7. Cross‑Source Parallelism

Different UUIDs may resolve to different storage backends. The parallel resolution mechanism works seamlessly across heterogeneous systems because each lookup is independent and the registry stores the access method.

| UUID Prefix | Storage Backend | Access Method |
|-------------|----------------|----------------|
| `img_*` | S3 bucket | HTTP GET with pre‑signed URL |
| `doc_*` | PostgreSQL | SQL query with connection string |
| `cfg_*` | Local JSON file | File read |

The system does not need to know the backend type in advance. The registry entry contains the location and an optional access hint. Concurrency is natural because each backend access can be performed independently.

---

## 8. Multi‑Depth Registries (Registries of Registries)

A registry entry can point to another registry instead of directly to data. This allows:
- **Hierarchical registries** – a top‑level registry resolves to a second‑level registry, which resolves to actual data.
- **Sharding** – different parts of the UUID space can be managed by different registries (e.g., by UUID prefix).
- **Delegation** – a UUID can be resolved by a registry that is itself stored as a data payload.

In such a design, the resolution chain length equals the depth of registry nesting. Each step is still O(1). The system does not care whether a hop lands on a data file or on another registry; the algorithm is identical.

---

## 9. Data at Rest Until Visited

All components (registries, data payloads) remain **at rest** until an operation requires them. There are:
- No background indexing threads
- No periodic cache refreshes
- No pre‑loaded data
- No persistent connections

This property makes the pattern suitable for:
- **Cold storage** – data can be archived on slow media; only the necessary piece is retrieved on demand.
- **Ephemeral compute** – a container can spin up, resolve chains, fetch data, perform a task, and shut down without leaving state.
- **Air‑gapped environments** – all artifacts can be stored on removable media; resolution works offline.

---

## 10. Coordination‑Free Parallelism

Because there is no central coordinator, parallel resolution does not require:
- A transaction manager
- Locking or mutual exclusion
- A global index or scheduler

The system simply:
1. Starts all parallel lookups using the concurrency primitives of the runtime (threads, async tasks, goroutines).
2. Waits for all to complete (or for a timeout).
3. Combines the results (or reports partial failures).

If one chain fails (e.g., data not found), the operation can either fail entirely or return partial results, depending on the application’s requirements. No rollback is needed because there are no side effects.

---

## 11. Mesh Topology and UUID Routing

The combination of registries, multi‑hop chains, and parallel fan‑out creates a **data mesh** where:
- **Nodes** are UUIDs (identifying data records or registries).
- **Edges** are references stored inside payloads (UUID → UUID).
- **Routing tables** are the registries (UUID → location or next UUID).

This is analogous to a packet‑switched network:
- A **router** is a registry that points to another registry.
- A **switch** is a registry that points to multiple destinations (parallel fan‑out).
- A **link** is a UUID reference that the resolver follows.

The system can traverse arbitrary paths through the mesh. The topology is determined entirely by the content of the registries and the data payloads, not by a separate control plane.

---

## 12. Per‑Hop Authentication and Authorisation

Each resolution step (registry lookup, data fetch, chain traversal) can be independently secured using self‑validating credentials. No component needs to contact a central authority in real time.

### 12.1 Self‑Validating Credentials
Credentials are self‑contained and cryptographically verifiable. They typically include:
- Identity of the authorised subject.
- The resource(s) being accessed (e.g., a specific UUID).
- The permitted operation (read, write, delete).
- An expiration timestamp.
- A digital signature from the issuing authority.

The recipient verifies the signature using a pre‑shared public key. No network call is required.

### 12.2 Authentication Methods per Hop
| Hop | Authentication Method | Verification |
|-----|----------------------|--------------|
| Registry lookup (HTTP) | Bearer token (JWT) | Registry verifies signature locally |
| Registry lookup (file) | File permissions or signed request | OS or application verifies |
| Data fetch (S3) | Pre‑signed URL | Storage backend verifies URL signature |
| Database access | Pre‑signed SQL statement | Database verifies capability token |
| Component‑to‑component | Mutual TLS (client certificate) | Each side verifies certificate chain |

### 12.3 Delegation and Chain Traversal
When a payload contains a new UUID, the client may need to resolve it through another registry. That second registry may have its own authentication policy. The client can include a **delegated credential** signed by the previous hop’s owner.

**Example (distributed authority):**
- Registry A, when returning a pointer to Registry B, also returns a signed assertion that the client is permitted to access Registry B.
- Registry B trusts Registry A’s signature (direct trust or via a trust chain).

**Example (centralised authority):**
- A central issuer provides a JWT that contains permissions for all registries the client will encounter.
- Each registry verifies the same JWT; no delegation is needed.

### 12.4 Centralised vs. Distributed Authentication Management
| Aspect | Centralised | Distributed |
|--------|-------------|-------------|
| Authority | Single issuer (corporate IdP) | Each registry manages its own trust anchors |
| Token issuance | Admin panel or IdP signs all tokens | Tokens can be delegated hop by hop |
| Revocation | Short token lifetimes (offline) or central revocation list | Same, plus per‑registry revocation lists |
| Offline capability | Yes (self‑validating tokens) | Yes |
| Complexity | Lower | Higher (key distribution) |

### 12.5 Offline Operation
Because all credentials are self‑validating, the entire resolution and authentication process can be performed **offline**, provided the client has:
- The necessary registry files (cached or pre‑fetched).
- The necessary signed tokens (JWT) or pre‑signed URLs.
- The required public keys to verify signatures.

No real‑time callback to an authentication server is required.

---

## 13. Stateless, Decentralised Management Plane

All administrative actions are performed as one‑time, stateless requests – identical in nature to data access requests. No background threads, no persistent connections, no always‑on daemons.

### 13.1 Management Actions Without Background Threads
| Management Action | Implementation (proposed or partially implemented) |
|-------------------|-----------------------------------------------------|
| **Update a registry entry** | Admin panel sends a signed `PUT /registry/{uuid}` request. Registry writes the new mapping atomically (e.g., to a JSON file). |
| **Revoke a capability** | Admin panel appends a signed revocation entry to a shared revocation list (e.g., a JSON file). Components read the list on each request (or use OS file notifications). |
| **Rotate a data store key** | Admin panel sends a signed `POST /rotate-key` request. Data store generates a new key and responds. |
| **Check health** | Admin panel sends a one‑time `GET /health` request. Component responds with status. |
| **Collect logs** | Component writes logs to an append‑only file (e.g., JSON‑lines). Admin panel reads the file on demand. |
| **Distribute a public key** | Admin panel writes the key to a well‑known location (e.g., a registry entry). Components fetch the key when needed (cached with TTL). |

### 13.2 Real‑Time Effects Without Application Threads
Low‑latency effects (e.g., fast revocation) are achieved using OS‑level file notifications (`inotify`, `ReadDirectoryChangesW`). The operating system monitors file changes and wakes the application only when a change occurs. No application‑level background thread consumes CPU while waiting.

**Example: Fast revocation**
1. Admin panel appends a signed revocation entry to a file (`revocations.json`) on a shared volume.
2. The registry component uses `inotify` to watch that file.
3. When the file changes, the OS wakes the registry process. No background thread was running while the file was unchanged.
4. The registry re‑reads the file and updates its in‑memory revocation cache.
5. The next lookup request uses the updated list.

Propagation occurs within milliseconds, but no application‑level thread consumes CPU during the idle period.

### 13.3 Admin Panel as a Client of the Data Mesh
The admin panel is just another client of the UUID mesh. It follows the same rules: stateless requests, optional caching, no persistent connections. It can manage hops separately (direct requests to each component) or present combined views by resolving UUID chains. The same infrastructure serves both data and management – no separate control plane is required.

### 13.4 Cost and Operational Properties
| Property | Traditional Management | This Architecture |
|----------|------------------------|-------------------|
| Compute (idle) | Background threads consume CPU | Zero CPU when idle |
| Memory | Long‑lived connections, session state | No persistent state per client |
| Network | Constant heartbeats, keep‑alive messages | Only requests when work is needed |
| Storage for logs | Centralised log collector (always running) | Append‑only files, read on demand |
| Scaling | Limits on concurrent connections, thread pools | No per‑connection overhead; scales with request rate |
| Management complexity | Deploy and monitor daemons, handle split‑brain | No daemons; management is just another client |

---

## 14. Scalability Considerations

| Dimension | Characteristic |
|-----------|----------------|
| **Number of parallel chains** | Limited by runtime concurrency; typically hundreds to thousands. |
| **Registry size** | Each lookup is O(1) (hash table). Registries can be sharded by UUID prefix. |
| **Network overhead** | Each parallel fetch may open a separate connection; connection pooling can be used. |
| **Failure isolation** | A failing chain does not block others; results can be aggregated with partial failures. |
| **Registry updates** | Independent; changing a registry entry does not affect data payloads or other registries. |
| **Administrative operations** | Scale with request rate, not with number of components. No per‑component daemons. |

---

## 15. Example Use Cases (Technology‑Neutral)

### 15.1 Distributed Document Database
- Each document stored as a JSON file.
- Root registry maps user ID → collection index UUID.
- Collection index (JSON file) contains an array of document UUIDs.
- Node registry maps each document UUID to its storage location (local disk, S3, etc.).
- To list documents: read collection index (one hop). To read a document: resolve UUID (second hop).

### 15.2 Object Storage with Cross‑References
- Images stored in S3.
- Metadata records (JSON) stored in a separate key‑value store.
- UUID in metadata record points to image S3 key.
- To display an image: read metadata record → extract image UUID → resolve to S3 URL → fetch image.

### 15.3 Real‑Time Dashboard with Independent Widgets
- Dashboard configuration UUID → resolves to a list of widget UUIDs.
- For each widget UUID, start a parallel resolution chain (may involve multiple hops).
- All widgets fetched concurrently; dashboard updates when all complete.

### 15.4 Multi‑Tenant Data Mesh
- Each tenant has its own root registry.
- Root registry maps tenant UUID → tenant’s personal root UUID.
- Personal root resolves to user profile (database row) containing UUIDs of documents, settings, etc.
- Different tenants can store data in different physical locations (on‑prem, cloud, hybrid) without changing application logic.

### 15.5 Supply Chain Traceability
- Each shipment, batch, or transaction receives a UUID.
- Each event record references the previous event’s UUID, forming a verifiable chain of provenance.
- Registries can be hosted by each supply chain participant independently.
- No global consensus is required – any participant can verify a chain by following UUID references offline.

### 15.6 Offline Medical Record Access
- A patient carries a USB drive with encrypted medical records and a signed capability from their primary care provider.
- An emergency room doctor, without internet access, inserts the USB drive.
- The local application resolves UUIDs using a cached registry on the USB drive, verifies the capability signature, and displays the records.
- No real‑time authentication call is possible – and none is needed.

---

## 16. Operational Properties Summary

| Property | Description |
|----------|-------------|
| **No central coordinator** | Resolution is deterministic and local. |
| **No background processes** | Data and management components remain at rest until accessed. |
| **No database required** | Registries and data can be plain files (or any KV store). |
| **Transparent location changes** | Updating a registry entry is sufficient to move data. |
| **Resilience to partial loss** | Losing a data file does not corrupt the registry or other data. |
| **Parallelism without locking** | Independent chains run concurrently without coordination. |
| **Heterogeneous backends** | Different UUIDs can resolve to completely different storage systems. |
| **Offline capability** | All operations work without network, given pre‑fetched registries and credentials. |
| **Unified data and management** | Same stateless request mechanism serves both user and administrative operations. |

---

## 17. Prior Art Assertion

This document establishes prior art for the following concepts, all disclosed in public, timestamped materials as of May 2026 (partial implementations exist in the Terminal Notes system; the full architecture is a logical extension):

1. **UUID‑based permanent identifiers** for all resources (data, keys, policies, configurations, audit entries).
2. **Registries as routing tables** mapping UUIDs to storage locations or to other UUIDs.
3. **Deterministic O(1) resolution chains** – fixed‑length lookups using hash tables.
4. **Layered independence** – decoupling data, metadata, policy, keys, and administration into separate UUID‑addressable layers.
5. **Parallel independent resolution chains** – multiple chains running concurrently without coordination.
6. **Fan‑out (branching) resolution** – following multiple embedded UUIDs in parallel.
7. **Cross‑source parallelism** – resolving UUIDs to heterogeneous storage backends.
8. **Multi‑depth registries** – registries pointing to other registries (hierarchical, sharding, delegation).
9. **Data at rest until visited** – no background indexing, no pre‑loading, no persistent connections.
10. **Coordination‑free parallelism** – no transaction manager, locks, or global scheduler.
11. **Mesh topology for data routing** – UUIDs as nodes, references as edges, registries as routing tables.
12. **Per‑hop self‑validating authentication** – signed JWTs, pre‑signed URLs, client certificates, revocation lists.
13. **Offline‑capable security** – credentials verifiable without real‑time authority contact.
14. **Stateless, decentralised management plane** – administrative actions as one‑time, self‑validating requests.
15. **Management without background threads** – using OS‑level file notifications for low‑latency updates.
16. **Admin panel as a client of the data mesh** – unified data and control plane.
17. **Encryption as a resolvable layer** – keys identified by UUIDs, resolved through independent registries.
18. **Policy as a resolvable resource** – access rules stored as UUID‑addressable documents.
19. **Stateless administrative operations** – configuration, key rotation, and revocation as one‑time requests, same as data access.
20. **Cost reduction through stateless management** – elimination of idle resource consumption, connection overhead, and dedicated management daemons.

The concepts disclosed herein are now part of the public domain. No party may obtain valid patent claims covering any concept described in this document.

---

## 18. Conclusion

This document describes a **decentralised data architecture** that unifies data access, authentication, and management under a common set of principles: UUID‑addressed resources, static registries, deterministic O(1) resolution chains, parallel independent chains, per‑hop self‑validating credentials, and a stateless management plane without background threads or always‑on daemons.

The architecture works offline, scales with request rate, tolerates partial component loss, and eliminates central coordination. Partial implementations exist in the Terminal Notes system (UUID permanence, registry resolution, hardware‑bound keys, active cache validation). The full architecture described here is a logical extension of those patterns and is disclosed in the public interest. It may be cited in any patent examination, litigation, or prior art search.

---

**sys_ronin**  
May 2026  
sys-ronin@protonmail.com  
github.com/sys-ronin/terminal-notes
