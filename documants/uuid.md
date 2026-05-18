# UUID‑Based Architecture

## A Technical Description of Observable Behavior

This document describes the internal mechanics of a system that coordinates operations across multiple independent storage artifacts using deterministically resolved UUID chains. The description is based on the code as it exists and the behavior observed during execution. No claim of novelty or superiority is made. The purpose is to document what the system does, how it achieves O(1) resolution across local and network storage, and how complex operations (create note, edit note, search deleted items, secure erase notebook) are executed as a sequence of small, stateless steps.

The system uses three independent resolution chains that start from different identifiers, proceed in parallel, and converge only at the final write or display operation. Each chain is O(1) per step and does not require a central coordinator.

---

## 1. Core Design Principle

The system does not rely on a central coordinator, a persistent database, or a background service. Instead, every operation is performed by following **multiple deterministic UUID chains** that start from different origins:

- **Chain A:** Resolves the notebook folder path (from an in‑memory object).
- **Chain B:** Resolves the decryption keys (from the master registry, vault registry, and vault file).
- **Chain C:** Prepares the note data and Git commit metadata (from user input and the note object).

These chains execute independently but are orchestrated by the code order. Their outputs converge at the **write phase** (filesystem and Git) for create, edit, delete, rename, or at the **display phase** for search, timeline, and activity.

---

## 2. Artifacts and Identifiers

| Artifact | Format | Stored Where | Contains |
|----------|--------|--------------|----------|
| **Master registry** | `notebooks_registry.json` | Local disk (or network share) | Maps system fingerprint → list of notebook UUIDs; maps notebook UUID → (vault name, entry UUID, folder path) |
| **Vault registry** | `vaults_registry.json` | Local disk (or network share) | Maps vault name → absolute path or URL to the vault file |
| **Vault file** | `*.vault` or `session.vault` | Any reachable location (local, USB, S3, WebDAV) | Dictionary: entry UUID → (encrypted keys, nonce, timestamp) |
| **Notebook folder** | `structure.json`, `notes.json`, `files.json` | Any reachable location | Note metadata and encrypted content, keyed by item UUID |
| **Git repository** | Inside notebook folder | Local or remote (GitHub, GitLab) | Commit history; commit messages contain UUIDs and action types |
| **System fingerprint** | Derived at runtime | Never stored | Hash of machine identifiers (machine ID, product UUID, hostname, etc.) |

All UUIDs are used as **static pointers**. The system never searches; it always resolves by direct key lookup.

---

## 3. Example Operation: Create Note (`c`)

The user presses `c`, enters title and content, and chooses an editor. The system spawns three independent chains.

```mermaid
flowchart TD
    subgraph UserInitiated["User presses 'c'"]
        A1["User enters title and content"] --> A2["Capture content"]
    end

    subgraph Operation["Create Note Operation"]
        B1["Generate new UUID for note"] --> B2["Create Note object in memory"]
        B2 --> B3["Append note to notebook.notes list"]
    end

    subgraph ChainA["Chain A: Notebook Path (O1)"]
        C1["notebook.custom_path (from memory)"] --> C2["Resolve absolute folder path"]
    end

    subgraph ChainB["Chain B: Key Resolution (O1)"]
        D1["notebook ID"] --> D2["Lookup entry UUID + vault name from master registry"]
        D2 --> D3["vault registry → vault file path (local or URL)"]
        D3 --> D4["Read vault file → fetch encrypted keys by entry UUID"]
        D4 --> D5["Hardware fingerprint (runtime) → AES‑GCM decrypt keys"]
        D5 --> D6["Crypto object (keys ready)"]
    end

    subgraph ChainC["Chain C: Git Metadata (O1)"]
        E1["Note UUID (generated)"] --> E2["Collect notebook UUID, parent UUID, root UUID"]
        E2 --> E3["Assemble commit message: type: CREATED NOTE, title, context"]
    end

    subgraph Write["Convergence: Write & Commit"]
        F1["Write structure.json (notebook.to_dict()) – encrypted with keys"] --> F2["Write notes.json (add note content) – encrypted with keys"]
        F1 --> F3["Git add structure.json"]
        F2 --> F4["Git add notes.json"]
        F3 & F4 --> F5["Git commit (using message from Chain C)"]
    end

    UserInitiated --> Operation
    Operation --> ChainA
    Operation --> ChainB
    Operation --> ChainC
    ChainA --> Write
    ChainB --> Write
    ChainC --> Write
    Write --> Done["Note created, UI refreshes"]
```

---

## 4. Example Operation: Edit Note (`e`)

The user presses `e`, modifies content in an external editor, and saves. The system updates the note object and triggers the three chains.

```mermaid
flowchart TD
    subgraph UserInitiated["User presses 'e'"]
        A1["User modifies content in external editor"] --> A2["Capture new content"]
    end

    subgraph Operation["Edit Note Operation"]
        B1["Update note.content in memory"] --> B2["Update note.updated timestamp"]
    end

    subgraph ChainA["Chain A: Notebook Path (O1)"]
        C1["notebook.custom_path (cached)"] --> C2["Absolute folder path"]
    end

    subgraph ChainB["Chain B: Key Resolution (O1)"]
        D1["notebook ID"] --> D2["Lookup entry UUID + vault name from master registry"]
        D2 --> D3["vault registry → vault file path"]
        D3 --> D4["Read vault file → encrypted keys by entry UUID"]
        D4 --> D5["Hardware fingerprint → decrypt keys"]
        D5 --> D6["Crypto object (keys)"]
    end

    subgraph ChainC["Chain C: Git Metadata & Change Stats (O1)"]
        E1["Compare old content vs new content"] --> E2["Compute added/removed characters"]
        E2 --> E3["Collect note UUID, notebook UUID, parent, root"]
        E3 --> E4["Assemble commit message: type: UPDATED, stats"]
    end

    subgraph Write["Convergence: Write & Commit"]
        F1["Write notes.json (encrypted) overwriting old content"] --> F2["Git add notes.json"]
        F1 --> F3["Git add structure.json (timestamp update)"]
        F2 & F3 --> F4["Git commit (using message from Chain C)"]
    end

    UserInitiated --> Operation
    Operation --> ChainA
    Operation --> ChainB
    Operation --> ChainC
    ChainA --> Write
    ChainB --> Write
    ChainC --> Write
    Write --> Done["Note edited, UI refreshes"]
```

---

## 5. Example Operation: Search for Deleted Items (`s deleted*`)

The user enters a query with an action wildcard. The system parses the query, then runs two parallel searches: one over current in‑memory notes and one over Git history. The results are merged and displayed.

```mermaid
flowchart TD
    subgraph UserInitiated["User presses 's'"]
        A1["User enters query (e.g., 'deleted* meeting')"] --> A2["Query parser extracts: action=DELETED, type=note, text='meeting'"]
    end

    subgraph CurrentSearch["Search Current Notes (in‑memory)"]
        B1["Walk unlocked notebooks tree"] --> B2["Match titles/content against query text"]
        B2 --> B3["Collect matching note UUIDs"]
    end

    subgraph HistoricalSearch["Search Deleted Items (from Git)"]
        C1["git log --grep '^type: DELETED' --all"] --> C2["For each commit: extract UUID, title, parent commit hash"]
        C2 --> C3["Filter by text ('meeting')"]
        C3 --> C4["For each: reconstruct item from parent commit (git show)"]
        C4 --> C5["Create temporary directory with reconstructed JSON files"]
    end

    subgraph ChainB["Chain B: Key Resolution (for decryption)"]
        D1["notebook ID"] --> D2["Lookup entry UUID + vault name from master registry"]
        D2 --> D3["vault registry → vault file path"]
        D3 --> D4["Read vault file → encrypted keys by entry UUID"]
        D4 --> D5["Hardware fingerprint → decrypt keys"]
        D5 --> D6["Crypto object (keys)"]
    end

    subgraph Merge["Merge & Display"]
        E1["Decrypt current matches with keys"] --> E2["Decrypt historical matches with keys"]
        E1 & E2 --> E3["Combine results, add action prefix (deleted, updated, etc.)"]
        E3 --> E4["Display paginated results"]
    end

    UserInitiated --> CurrentSearch
    UserInitiated --> HistoricalSearch
    CurrentSearch --> Merge
    HistoricalSearch --> ChainB
    ChainB --> Merge
    Merge --> Done["Search results shown"]
```

---

## 6. Example Operation: Secure Erase Notebook

This operation removes all traces of a notebook: its folder, its Git history, all vault entries (for every trusted device), and its registry entry.

```mermaid
flowchart TD
    subgraph Step1["Step 1: Collect all trusted device entries"]
        A["notebook UUID"] --> B["master registry: get all (vault name, entry UUID) for this notebook"]
        B --> C["For each: resolve vault file path from vault registry"]
    end

    subgraph Step2["Step 2: Purge Git history"]
        D["notebook folder path"] --> E["Collect all descendant UUIDs from structure.json (recursive)"]
        E --> F["Run git-filter-repo with NotebookEraseFilter"]
        F --> G["Remove all commits containing any UUID"]
    end

    subgraph Step3["Step 3: Delete all vault entries"]
        H["For each (vault path, entry UUID)"] --> I["Open vault file (local or HTTP GET if remote)"]
        I --> J["Delete entry with matching entry UUID"]
        J --> K["Write vault file back atomically (.tmp → rename)"]
    end

    subgraph Step4["Step 4: Delete master registry entry"]
        L["notebook UUID"] --> M["Remove from master registry"]
        M --> N["Save registry atomically"]
    end

    subgraph Step5["Step 5: Delete notebook folder"]
        O["folder path"] --> P["shutil.rmtree()"]
    end

    subgraph Step6["Step 6: Clear memory"]
        Q["notebook ID"] --> R["Remove from SessionKeyVault cache"]
        R --> S["Remove from self.encrypted_notebooks set"]
        S --> T["Clear cached crypto object from notebook._crypto"]
    end

    Step1 --> Step2 --> Step3 --> Step4 --> Step5 --> Step6
    Step6 --> Done["Secure erase complete. Notebook no longer exists."]
```

---

## 7. Multi‑Cloud Operation Without Complexity

Because all artifacts are addressed by path or URL, the same O(1) resolution chains work across different cloud providers:

| Artifact | Possible Location | Resolution Step | O(1) Lookup |
|----------|-------------------|-----------------|--------------|
| Master registry | Local disk, USB, network share | Read JSON file | Yes |
| Vault registry | Local disk, USB, network share | Read JSON file | Yes |
| Vault file | S3 bucket, Backblaze B2, WebDAV server | HTTP GET at known URL | Yes (dictionary lookup in vault file) |
| Notebook folder | Local disk, NFS, Git remote | Path or Git clone | Yes (once resolved) |
| Git remote | GitHub, GitLab, self‑hosted | `git clone` or `git pull` | Yes (fixed URL) |

The system does **not** perform distributed consensus, two‑phase commit, or cross‑cloud locking. It simply reads files from their respective locations. If a location becomes unavailable, the operation fails cleanly (missing vault, missing notebook). Recovery is possible using the recovery phrase.

---

## 8. Theoretical Observations

The behavior observed in this system aligns with several theoretical concepts, although no prior work combines them in the same way.

- **Deterministic resolution** – UUIDs as static pointers resemble **content‑addressable identifiers** (IPFS, Git). Unlike those systems, this system uses dictionary lookups in registry files, not hash‑based addressing.
- **Stateless pipeline** – The sequential O(1) chains resemble a **pipe‑and‑filter** architecture (Shaw & Garlan, 1996) but without an explicit orchestrator. The pipeline is implicit in the data dependencies.
- **Ephemeral binding** – Deriving a decryption key from runtime hardware identifiers without storing it is analogous to **hardware‑rooted trust** (TPM, WebAuthn PRF) but implemented in software only.
- **Emergent convergence** – Multiple independent chains converge on a single operation without a central coordinator. This is an example of **coordinated action through shared data** (stigmergy).

These references are not claims of influence. They illustrate that the observed properties have been discussed in the literature, but the specific combination found in this codebase appears to be original.

---

## 9. Conclusion

The system executes operations as a set of independent, deterministic O(1) resolution chains that start from different identifiers (notebook path, decryption keys, Git metadata) and converge only at the final write or display phase. The chains are orchestrated by the code order, not by a central coordinator. The system works across local disks, USB drives, and cloud storage without changing its complexity.

The code is open. The behavior is observable. The description above is based on what the system does, not on what it claims to be. The reader is invited to inspect the source and verify the described properties independently.

---

## 10. Prior Art Notification

This document describes a working system publicly available in a timestamped source code repository (April 2026). The described architecture may constitute prior art under **35 U.S.C. § 102(a)(1)** (US) and **EPC Article 54(2)** (Europe). Under **EPO decision G 1/23 (2025)**, public availability alone is sufficient.

The system is released under the Eternal License, which prohibits patenting any disclosed concept. Readers considering patent applications in related fields are advised to review this document.

```
