# Prior Art Disclosure: A Lightweight, Encrypted Data Preservation System

**Date of Disclosure:** April 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  

---

## What This Document Describes

This document describes a method for preserving digital data that requires no institution, no complex software stack, and no ongoing maintenance. The method is built on four ordinary components: a text format (JSON), a version control system (Git), a symmetric encryption algorithm (AES‑256‑GCM), and a terminal.

The method is designed for a single user, a single folder, and a lifetime of writing. It is not a theoretical framework. It is a working implementation, timestamped and publicly available.

---

## The Preservation Problem

Digital data decays. Not because the media fails, but because the software required to read it becomes obsolete. Databases are replaced. File formats are abandoned. Encryption schemes are deprecated. Cloud services shut down.

Conventional solutions are institutional. They require dedicated servers, specialized staff, and ongoing funding. They are not designed for a person who simply wants their own notes to survive.

This system solves the problem differently: it uses only components that are already decades old and will remain usable for decades more.

---

## The Components

### JSON as the Storage Format

All persistent data is stored in JSON files. JSON is a text format defined by RFC 8259. It is not a database. It is not a binary blob. It is plain text.

Any text editor can open a JSON file. Any programming language can parse it. There is no vendor lock‑in. If the software that writes the JSON disappears, the data remains readable.

### Git as the Versioning Layer

Every change to the JSON files is recorded as a Git commit. Git stores commits as binary deltas. Changes are small, even when the underlying encrypted data changes.

Git provides:
- A complete, immutable history of every change.
- The ability to revert to any previous state.
- The ability to clone the entire dataset to another machine.

The user never needs to know Git. The system calls Git commands automatically. The repository is stored inside the same folder as the JSON files.

### Encryption Before Write

All JSON files are encrypted before they are written to disk. The encryption is AES‑256‑GCM, a symmetric cipher that is considered secure against known quantum attacks for the foreseeable future.

Encryption is applied **before** Git sees the data. Git stores the encrypted blobs. The plaintext never touches the disk.

Because encryption happens before write, there is no separate “encrypt then sync” step. The encrypted state is the only state.

### The Folder as the Unit of Preservation

A complete dataset is a single folder containing:
- Three JSON files (encrypted)
- A Git repository (storing the encrypted history)
- A small set of metadata files (`.tn_test`, `.tn_recovery`, `.tn_password`)

To preserve the data, copy the folder. To move it, copy the folder. To back it up, copy the folder. There is no separate database, no configuration file, no registry entry.

The folder is the archive. The archive is the folder.

---

## Why This System Is Quantum‑Safe

This system uses only AES-256-GCM for encryption, a symmetric algorithm. Unlike asymmetric cryptography (RSA, ECC), symmetric ciphers like AES are significantly less affected by known quantum algorithms. Grover’s algorithm would theoretically reduce the security of AES-256 to approximately 128 bits, which remains computationally infeasible to brute-force with current or anticipated quantum technology.

More importantly, the system never transmits encrypted data over any network. This makes the “harvest now, decrypt later” attack vector irrelevant, as there is no ciphertext available for collection. All encrypted data remains local to the user’s device. Any successful attack would require physical access to the storage medium plus the ability to break AES-256-GCM.

For the threat model of long-term local data preservation without network exposure, AES-256-GCM provides strong resistance against foreseeable quantum attacks.

---

## Why This System Is Lightweight

Conventional preservation systems require:
- Database servers
- Indexing engines
- Background processes
- Regular maintenance
- Institutional funding

This system requires none of those. It runs on any hardware that can execute a Python interpreter and call Git commands. Typical memory usage is under 100 MB. The executable is approximately 1 MB.

There are no background processes. No scheduled tasks. No automatic updates. The system does nothing unless the user explicitly runs a command.

This is not a compromise. It is a design choice: a preservation system should not require preservation itself.

---

## The Data Outlives the Software

If this software is never updated again, the data remains accessible.

- The JSON files can be read by any text editor.
- The Git repository can be inspected with any Git client.
- The encrypted blobs can be decrypted with any AES‑256‑GCM implementation.

A user who stops using the software still has a folder full of plain‑text JSON (if unencrypted) or standard encrypted blobs (if encrypted). The data is not trapped.

This is the opposite of vendor lock‑in. It is vendor liberation.

---

### Doomsday Recovery: Rebuilding the Application from Published Logic

The logic that governs the system is not hidden in the code. It is described in public, timestamped prior art documents. The three‑file architecture, the UUID permanence scheme, the commit message format, and the encryption key derivation are all documented.

In the future, if the original executable no longer runs, anyone can:

1. Read the prior art documents.
2. Implement the same logic in any programming language (Rust, Go, Java, C, JavaScript, etc.).
3. Parse the existing JSON files and Git history.
4. Recreate the same environment: view notes, search history, resurrect deleted items.

The application is not a black box. It is a **specification** with a reference implementation. The data is not tied to Python or to any specific binary. It is tied to open standards and documented patterns.

This is a doomsday feature: even if the software disappears, the data remains useful. The instructions for rebuilding the software are already public.


---

## Prior Art Assertion

The concepts described in this document – including but not limited to:

- The use of JSON as the sole persistent storage format for a digital preservation system
- The integration of Git as a versioning layer for encrypted blobs
- Encryption applied before write, with no separate sync step
- The folder as the self‑contained unit of preservation
- The system’s quantum‑safe properties derived from AES‑256 and offline storage

were made public in timestamped GitHub repositories and prior art disclosures starting in February 2026.

These concepts constitute prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) EPC. No party may obtain valid patent claims covering any of these concepts.

The system is released under the **Eternal License**, which explicitly prohibits patenting any disclosed concept.

---

## Conclusion

A digital preservation system does not need to be complex. It does not need a central authority. It does not need to be online.

It needs three things: a text format that will not become obsolete, a version control system that can track changes efficiently, and an encryption algorithm that will remain secure for decades.

JSON, Git, and AES‑256‑GCM provide these. A folder provides the container. A terminal provides the interface.

This is preservation for a single user. It is lightweight, fully encrypted, and designed to outlast its own implementation.
