```mermaid
flowchart TD
    subgraph SOURCE["📄 Source Code Modules"]
        NM["NoteManager<br/>(terminal_notes_core.py)"]
        VM["VaultManager<br/>(vault_manager.py)"]
        CR["Crypto<br/>(crypto.py)"]
        NO["NotebookOperations<br/>(notebook_operations.py)"]
    end

    subgraph REGISTRIES["📋 Registries"]
        MR["Master Registry<br/>(notebooks_registry.json)<br/>maps notebook_id → system entries"]
        VR["Vault Registry<br/>(vaults_registry.json)<br/>maps vault_name → vault_path"]
    end

    subgraph VAULT["🔐 Vault File"]
        VF[".vault file<br/>(binary, AES‑GCM encrypted<br/>with system fingerprint)"]
    end

    subgraph NOTEBOOK["📁 Notebook Folder"]
        STRUCT["structure.json<br/>(hierarchy, metadata)"]
        NOTES["notes.json<br/>(regular note content)"]
        FILES["files.json<br/>(file note content)"]
        DOT_FILES[".tn_test / .tn_recovery / .tn_password<br/>(encryption markers, recovery)"]
        GIT[".git directory<br/>(full history)"]
    end

    %% Relationships
    NM -->|reads/writes| MR
    NM -->|reads/writes| VR
    NM -->|uses| VM
    NM -->|uses| CR
    NM -->|creates/locks/unlocks| NOTEBOOK

    VM -->|reads/writes| VR
    VM -->|reads/writes encrypted entries| VF

    CR -->|encrypts/decrypts| STRUCT
    CR -->|encrypts/decrypts| NOTES
    CR -->|encrypts/decrypts| FILES
    CR -->|creates/verifies| DOT_FILES

    NO -->|performs CRUD| STRUCT
    NO -->|performs CRUD| NOTES
    NO -->|performs CRUD| FILES

    NM -->|initiates commits| GIT
    NOTEBOOK -->|contains| GIT

    MR -->|stores vault name + entry UUID| VR
    VR -->|points to| VF
    VF -->|holds encrypted keys for| NOTEBOOK

    classDef src fill:#3498db,stroke:#2c3e50,color:white
    classDef reg fill:#2ecc71,stroke:#2c3e50,color:white
    classDef vault fill:#e74c3c,stroke:#2c3e50,color:white
    classDef nb fill:#f39c12,stroke:#2c3e50,color:white

    class NM,VM,CR,NO src
    class MR,VR reg
    class VF vault
    class STRUCT,NOTES,FILES,DOT_FILES,GIT nb
```

## Description

The diagram shows how source code modules interact with registries, the binary vault, and notebook folders:

- **NoteManager** (core orchestrator) reads/writes the **Master Registry** (maps notebook IDs to per‑system entries) and the **Vault Registry** (maps vault names to file paths). It also uses `VaultManager` and `Crypto` to manage encryption keys.
- **VaultManager** handles the binary `.vault` file – reading/writing entries encrypted with the system fingerprint. Each entry contains a notebook’s combined keys (`password_key + phrase_key`).
- **Crypto** performs the actual AES‑GCM encryption/decryption of the notebook’s JSON files (structure, notes, files) and manages the marker files (`.tn_test`, `.tn_recovery`, `.tn_password`).
- **NotebookOperations** executes CRUD operations directly on the JSON files inside the notebook folder.
- The **notebook folder** contains the encrypted/ext JSON files, marker files, and a `.git` directory for full history. The master registry references this folder via a relative or absolute path.
- The vault registry points to the `.vault` file, and the master registry stores for each system the vault name and the entry UUID inside that vault. This creates a complete chain: **notebook → master registry → vault registry → vault file → encrypted keys → notebook folder decryption**.
