# Prior Art Disclosure: A Logic‑Based, Language‑Independent Forever App

**Date of Disclosure:** April 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** [github.com/sys-ronin/terminal-notes](https://github.com/sys-ronin/terminal-notes)

---

## What This Document Is

This document describes a writing system built on three common, stable components: Python, JSON, and Git. The system runs in a terminal, requires no network, no installation, and no external dependencies beyond a Python interpreter (or a bundled executable). It is designed to last for decades, to be portable across any hardware, and to be completely independent of any single programming language.

This document is a **defensive publication**. It establishes prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) EPC. The concepts described here are now part of the public domain. No party may obtain valid patent claims covering any of these concepts.

The description is neutral. It does not compare this system to others. It does not argue that this system is better. It simply explains what it is and how it works.

---

## The Constraints That Directed the Design

The system was not built by adding features. It was built by respecting a small set of immutable, non‑negotiable constraints:

1. **Zero trust** – no reliance on external authorities or services.
2. **Every hardware faulty** – assume components fail.
3. **Electricity will go dark** – assume power loss at any moment.
4. **User knows nothing about technology** – assume no technical background.
5. **Must run on any system** – no platform lock‑in.
6. **Must be dependency‑free** – no external libraries (except bundled cryptography).
7. **Must run for centuries** – plan for long‑term survival without maintenance.
8. **Must be portable** – the data folder is the unit of movement.

From these constraints, every feature emerged logically. The system is not a collection of arbitrary features; it is a **necessary consequence** of the constraints.

---

## The Implementation: Python, JSON, Git

### Python

Python is a programming language available on almost every operating system. It is included by default on Linux and macOS, and can be installed on Windows in minutes. The system uses only the Python standard library – no third‑party packages are required. The bundled executable version requires no Python installation at all.

### JSON

All persistent data is stored in three JSON files:

- `structure.json` – hierarchy and metadata
- `notes.json` – note content
- `files.json` – file content

JSON is a text format (RFC 8259). It is human‑readable, machine‑parseable, and language‑agnostic. Any programming language that can read text can parse JSON. The data is not locked into any specific language or database.

### Git

Git is a version control system available on almost every operating system. The system uses Git to store every change as a commit. Commit messages contain structured metadata: UUID, action type (created, updated, deleted, renamed, restored, erased), and timestamps. This turns Git into an item‑level temporal database.

The user never needs to know Git. The system calls Git commands automatically. The Git repository lives inside the notebook folder; it is an internal detail.

---

## Why the System Is Language‑Independent

The core logic of the system is encoded in the **data structures**, not in the Python code. The three‑file architecture, UUID permanence, and Git commit format are patterns that can be re‑implemented in any language that supports JSON, text files, and calling a version control system.

- **UUID permanence** – identity is a property of the data, not the code.
- **Three‑file separation** – structure, content, and files are stored independently; this is a data model, not a language feature.
- **Git as a temporal database** – the commit message format is a plain text protocol; any language can write and read it.

Thus, the system’s implementation in Python is incidental. A developer could rewrite the same logic in Rust, Go, Java, C, or JavaScript without changing a single byte of the user’s data. The data outlives the code.

---

## The Forever Properties

| Property | How the System Achieves It |
| :--- | :--- |
| **Data outlives software** | The artifacts are JSON and text, readable by any tool. |
| **No vendor lock‑in** | The user owns the folder; no cloud, no account, no proprietary format. |
| **Language‑agnostic** | The core logic can be re‑implemented in any language. |
| **Dependency‑free** | No external libraries (except bundled crypto) and no required services. |
| **Offline‑first** | Works without internet; Git remotes are optional. |
| **Crash‑safe** | Atomic writes (`.tmp` → `rename`) and Git commits ensure no corruption. |
| **Century‑scale** | JSON, Git, and AES‑GCM will remain usable for decades. |

---

## Post‑Hoc Validation: Alignment with Long‑Lived Software Theories

The system was built from first principles, without reference to any academic theories. After its completion, it was observed that its architecture aligns with several concepts that have been independently proposed as requirements for software that can last for decades.

**Legacy‑First Design (LFD)** proposes that time be treated as a primary architectural constraint, distinguishing between permanent and transient system elements and framing prolonged absence of maintenance as a predictable phase rather than an exceptional failure. The system was built with time as the central constraint: JSON and Git were chosen because they are already decades old and will remain usable for decades more. The system expects no updates, no maintenance, and no ongoing support; it is designed to survive abandonment.

**DARPA’s BRASS programme** sought foundational advances in the design and implementation of long‑lived software systems that can dynamically adapt to changes in the resources they depend upon. The programme called for an “entirely new clean‑slate approach”. The system achieves longevity not through adaptive self‑modification but through radical simplicity, the use of mature technologies that do not change rapidly, and the elimination of all external dependencies. It is a working example of a software system that can remain functional without ongoing maintenance, providing a proof by existence for the BRASS vision.

**Zero‑dependency software** is recognised as a strategy for long‑term maintainability, because “zero dependency is a must” for software that “must be maintainable until my death or longer”. The system was built with zero dependencies beyond the standard library, directly embodying this principle.

**Alan Kay’s growable systems** and **Roy Fielding’s evolvable systems** both emphasise message‑passing as the key to long‑term viability. The system uses numbered commands as messages between the user and the data; its UUID‑based identity system allows items to be moved and renamed without breaking references; and its append‑only Git history supports growth and evolution without disruption.

These observations are offered not as claims of intentional design, but as post‑hoc validation that the system’s constraint‑driven architecture naturally satisfies principles that have been independently recognised as essential for software longevity.

---

## Prior Art Assertion

The concepts described in this document – including but not limited to:

- The three‑file atomic architecture (`structure.json`, `notes.json`, `files.json`)
- UUID permanence for item identity across renames, moves, and deletions
- Git as an item‑level temporal database with structured commit messages
- Key derivation from the folder name (salt stored exclusively as the filesystem path)
- Portable, hardware‑bound encryption without a TPM
- The “forever” design properties listed above

were made public in timestamped GitHub repositories and prior art disclosures starting in April 2026.

These concepts constitute prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) of the European Patent Convention, as clarified by Enlarged Board of Appeal decision G 1/23 (2 July 2025). No party may obtain valid patent claims covering any of these concepts in any jurisdiction.

The system is released under the **Eternal License**, which explicitly prohibits patenting any disclosed concept and asserts that the technology belongs to no one.

---

## Conclusion

This writing system is not “forever” because it claims immortality. It is “forever” because it is built on foundations that will outlast any single implementation: open standards (JSON), a mature version control system (Git), and a minimalist, dependency‑free architecture. The data is open, the logic is portable, and the design is free from external dependencies.

The system can be recreated in any language. The data will remain readable. The history will remain accessible. The user will never be locked in.

That is the only kind of “forever” that matters.
