# Logic‑as‑Code: A Permanent Architecture

## What This Document Is

This document describes a system where the core logic is not stored in executable source code but is encoded in data structures, file formats, and documented rules. The implementation in Python is incidental. Any language that can parse JSON, call Git commands, and implement AES‑GCM can recreate the same system.

The purpose is to separate the ephemeral (code) from the permanent (logic). The logic is the set of relationships between UUIDs, JSON files, Git commits, and folder names. These relationships are documented in public, timestamped prior art. They do not belong to any programming language.

This document does not compare itself to other systems. It does not advertise. It simply describes a mechanism.

---

## The Problem

Software rots. Dependencies are abandoned. APIs change. Languages fall out of favour. A program that works today may not compile or run in ten years.

Most systems tie their logic to a specific implementation. When the implementation becomes obsolete, the logic is lost. Users are forced to migrate or lose their data.

This system solves the problem by moving the logic out of the code and into the data. The data is the authority. The code is just a reader.

---

## The Mechanism

### Step 1: Store Everything in Standard Formats

All persistent data is stored in:

- **JSON** (RFC 8259) – for hierarchy, notes, and files.
- **Git commits** (plain text) – for history.
- **AES‑GCM** – for encryption.

These are not arbitrary choices. JSON is a text format that can be parsed by any language. Git commits are text files with a documented structure. AES‑GCM is a standard encryption algorithm with implementations everywhere.

### Step 2: Encode Logic in Data Structures, Not Functions

The logic is not in `if` statements or loops. It is in the relationships between data elements:

- **UUID permanence**: Every item has a UUID. That UUID appears in every commit message and in every JSON file that references the item. The logic is: "to find the history of an item, search the Git log for its UUID." This is a rule, not a function.
- **Three‑file separation**: Hierarchy is in `structure.json`. Content is in `notes.json` and `files.json`. The logic is: "to display a note, read its content from the appropriate file using its UUID as the key." This is a data mapping, not a procedure.
- **Git as a temporal database**: The commit message format is fixed: `type: ACTION CONTENT_TYPE: title | context`. The logic is: "to resurrect a deleted item, find the commit before its deletion and reconstruct from the JSON files at that commit." This is a query pattern, not an algorithm.

These rules can be expressed in any language. They do not depend on Python syntax or libraries.

### Step 3: Document the Rules as Prior Art

The rules are not hidden in source code comments. They are published as timestamped prior art documents. Anyone, anywhere, at any future date, can read these documents and understand how the system works.

The documents describe:

- The format of `structure.json`, `notes.json`, and `files.json`.
- The structure of Git commit messages.
- The key derivation (`SHA256(password + b':' + folder_name)`).
- The encryption scheme (AES‑GCM with a 12‑byte nonce and a 16‑byte authentication tag).

These documents are the source of truth. The code is just a reference implementation.

### Step 4: The Code Becomes Disposable

Because the logic is documented and the data is stored in standard formats, the Python implementation can be discarded at any time. A future programmer can:

1. Read the prior art documents.
2. Parse the JSON files and Git history.
3. Implement the same logic in any language (Rust, Go, Java, C, JavaScript, etc.).
4. Produce a new application that reads the same data and behaves identically.

The data does not need to be migrated. The history does not need to be rewritten. The encryption does not need to be broken. Only the implementation changes.

---

## Why This Works

### Language Independence

The system does not rely on any language‑specific feature. JSON is not Python. Git is not Python. AES‑GCM is not Python. The logic is expressed in terms of these standards, not in terms of Python objects or methods.

### Data Longevity

JSON is plain text. Git commits are plain text. Plain text is the only digital format that has survived every technological shift. If JSON and Git are still readable in fifty years, the data will be readable.

### No Vendor Lock‑in

There is no company behind this system. There is no cloud service. There is no subscription. The user owns the folder. The folder is the archive.

### No Dependency on the Original Author

The prior art documents are public. The logic is described. Anyone can rebuild the system. The original author does not need to be consulted. The code does not need to be maintained. The system lives on its own.

---

## The Role of the Implementation

The Python code serves one purpose: to demonstrate that the logic works. It is a proof of concept, not a prison. It is a convenience, not a requirement.

If the Python implementation becomes obsolete, it will be replaced. The data will remain. The logic will be re‑expressed. The system will continue.

This is not a claim of immortality. It is a consequence of architectural choices.

---

## Prior Art Assertion

The concept of separating logic from implementation – encoding the rules in data structures and documenting them as prior art – was made public in timestamped GitHub repositories and prior art disclosures starting in February 2026.

This document is part of that disclosure.

---

## Conclusion

The logic is not the code. The code is a transient expression of the logic. The logic lives in the data structures, the file formats, and the documented rules. It can be re‑implemented in any language, on any platform, at any time in the future.

The system is not tied to Python. It is not tied to any specific runtime. It is tied to JSON, Git, and AES‑GCM – standards that will outlive any single implementation.

The data is the artifact. The logic is the blueprint. The code is just a tool.
