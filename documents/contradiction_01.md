# Contradictions Observed in a Working System

## A Humble Reflection Based on Code, Not Theory

---

## Preface

This document describes a set of observable behaviors in a working software system. These behaviors contradict many assumptions that are taught in textbooks, discussed in academic papers, and used as the foundation of established design patterns.

I do not claim that the textbooks are wrong. I do not claim that my way is better. I only claim that the system works, and that it works differently from what I was taught to expect.

I have 25 years of system level experience and over 13 years of professional experience. However, I have no formal education in computer science, no prior coding or development experience, and I built this system under severe personal and financial constraints. I believe these circumstances shaped the architecture into its unusual form. The result is not what a textbook would prescribe, but it works. The code is open. The behavior described below can be verified.

---

## 1. State Does Not Live in the Application

**What I was taught to expect:** An application holds state in memory. If it needs to remember something between requests, it uses a database or a cache. A stateless service delegates state to a separate storage layer.

**What the code actually does:** The application has no long‑running memory. It starts, performs a single user operation (create, edit, delete, search, timeline, activity), and then clears all transient state. The only “state” that exists between operations is in static files: the master registry, the vault registry, the vault file, and the notebook JSONs. The application does not hold state. It visits state where it rests.

**Why this surprised me:** I did not plan this. I simply wanted an application that would not lose my data if it crashed. Putting everything in files that could be read and written atomically seemed natural. Only later did I realize that this went against the standard model of stateful applications.

---

## 2. No Central Coordinator

**What I was taught to expect:** When multiple independent operations need to be coordinated (for example, writing to a JSON file and committing to Git), a central coordinator (a transaction manager, a workflow engine, an orchestration layer) decides the order and ensures consistency.

**What the code actually does:** The system has no central coordinator. The order of operations is fixed in the code, but the coordination emerges from data dependencies. For example, editing a note calls a function that writes the note file and then calls another function that commits to Git. Neither function knows about the other. They simply execute in sequence. This works because each step’s output is the input to the next step.

**Why this surprised me:** I did not know about transaction managers or workflow engines. I just wrote the steps in the order that made sense. If the write failed, the commit would not happen. That was enough for my use case.

---

## 3. Hardware Binding Without Hardware

**What I was taught to expect:** Binding a key to a specific machine requires a Trusted Platform Module (TPM), a Secure Enclave, or a dedicated hardware token. Pure software cannot achieve hardware binding because software can be copied.

**What the code actually does:** The system binds decryption keys to the machine’s hardware without any specialized hardware. It derives a fingerprint at runtime from machine identifiers (machine ID, product UUID, hostname). This fingerprint is never stored on disk. The vault file contains entries encrypted with a key derived from that fingerprint. On a different machine, the fingerprint changes, and decryption fails. No TPM is used.

**Why this surprised me:** I did not have access to a TPM. I needed a way to ensure that the vault file would only work on the original machine. I thought: if I could generate a unique identifier from the hardware itself, and never store it, then copying the vault would be useless. It worked. Later I learned that this is not the standard approach.

---

## 4. No Key Iteration (Why PBKDF2/Argon2 Are Not Needed)

**What I was taught to expect:** Key derivation functions must use thousands or millions of iterations (PBKDF2, bcrypt, Argon2) to slow down brute‑force attacks. A single SHA256 pass is considered insecure for password‑based encryption.

**What the code actually does:** The system derives keys with a single SHA256 pass. No iterations. No memory‑hard function. Yet the system is secure because the password is **not** the encryption key. The actual encryption key (Ks) is derived from the **recovery phrase**, which has high entropy (132–264 bits). The password only unlocks a locally cached key. An attacker who brute‑forces the password gains nothing – they cannot derive Ks without the phrase. The password is a convenience factor, not a security boundary.

**Why this surprised me:** I did not know about PBKDF2. I just derived keys the simplest way I knew. Later I realized that the security industry assumes passwords are the weakest link. In my system, the password is **not** the link. The phrase is. And the phrase has enough entropy to make iterations unnecessary. The standard practice solves a problem my architecture does not have.

---

## 5. No Application Layer (Data as the Application Layer)

**What I was taught to expect:** An application has a clear separation: the user interface, the business logic, the data layer. The data layer is passive. The application layer is active. The application acts upon the data.

**What the code actually does:** The system has no distinct “application layer” in the traditional sense. The data **is** the application layer. The JSON files (registry, vault, notebook) contain not only data but also the pointers (UUIDs) that determine what the system does next. The application code is a small, stateless interpreter that reads these files and follows their pointers. There is no “business logic” separate from the data. The behavior emerges from the data itself.

**Why this surprised me:** I did not design a layered architecture. I just stored everything in files that referenced each other via UUIDs. The code reads them in a fixed order. Only later did I realize that the traditional distinction between “code” and “data” had blurred. The data directs the execution. The code is just a follower.

---

## 6. O(1) Resolution Across Network Storage

**What I was taught to expect:** Accessing data across a network introduces variable latency, and the complexity of locating data grows with the size of the system. Deterministic O(1) lookups are only possible with in‑memory hash tables or local disk indexes.

**What the code actually does:** The system resolves a notebook’s decryption keys and content using a fixed number of lookups (about 7 to 10) regardless of where the vault file is stored. The vault may be on a local USB drive, an S3 bucket, or a WebDAV server. The system reads the vault file (a simple HTTP GET) and then performs a dictionary lookup on the downloaded JSON object. The lookup is O(1) because the vault file is a hash map keyed by entry UUID.

**Why this surprised me:** I did not know about distributed hash tables or B‑trees. I just thought: put the keys in a dictionary, store the dictionary in a file, and fetch the file when needed. The network round trip is slower, but the number of steps does not grow.

---

## 7. Resurrection via Parent Commit

**What I was taught to expect:** When a file is deleted from a version control system, recovering it requires checking out an old revision, manually locating the file, and copying it. There is no “restore” button that works across renames and moves.

**What the code does:** The system treats deletion as reversible. Deleted items remain searchable. When the user presses a key to restore, the system finds the deletion commit, retrieves its parent commit (which contains the item before deletion), reconstructs the item from the parent commit’s JSON files, and merges it back into the live notebook. The restored item retains its original UUID.

**Why this surprised me:** I wanted to be able to recover notes I had deleted by accident. I knew Git had the history. I thought: if I store the UUID in the commit message, I can find all commits related to that item. The commit before deletion must contain the item. It worked on the first try.

---

## 8. Stateless Trust

**What I was taught to expect:** Once a user authenticates, the system establishes a session that remains valid for some period. Trust is cached.

**What the code does:** The system does not cache trust. Decryption keys are kept in a short‑term cache, but the cache is validated before every use (the system checks that the vault file still exists). The user can explicitly lock the notebook, which clears the cache immediately. No background timeout, no session expiry.

**Why this surprised me:** I did not want to implement session management. I thought: just check the vault file every time. If it is gone, discard the keys. The user can lock manually. It was simpler.

---

## 9. No Database

**What I was taught to expect:** Any application that needs to coordinate multiple data sources (a master registry, a vault registry, a vault file, notebook JSONs, Git commits) must use a database to maintain consistency and provide queries.

**What the code does:** The system uses no database. All coordination is achieved with JSON files and Git commits. The registries are JSON dictionaries. The vault file is a JSON dictionary. Consistency is maintained by atomic writes (write to a temporary file, then rename). Queries are simple key lookups.

**Why this surprised me:** I do not know how to set up a database. I know how to read and write JSON files. I used what I knew.

---

## 10. A Humble Realisation

I did not set out to contradict textbooks. I did not set out to invent new patterns. I set out to build a writing tool that would not frustrate me, that would not lose my data, that would work offline, that I could carry on a USB drive, and that I could trust with my private notes.

The constraints I worked under were severe. No funding, no team, no prior coding experience, no formal education, a tiny table, an old laptop, and 150+ days of 14‑16 hour work. I did not have the luxury of choosing the “correct” architecture. I chose what I could build with the knowledge I had and the tools that were available.

The result is unusual. It contradicts many established practices. But it works.

I share this not to argue, but to document. The code is open. The behaviour is observable. If you find value in it, you are welcome to use it, study it, or improve it. If you find it lacking, that is fair as well. I have done my best, and my best is what I have written here.

---

## 11. Conclusion

The system described in this document works. It uses no central database, no transaction manager, no TPM, no key iteration (because the password is not the encryption key), no background processes, and no long‑term caching of trust. The traditional “application layer” has dissolved into the data itself – the JSON files and UUID pointers determine the flow of execution. Yet it performs secure, portable, hardware‑bound encryption; resurrects deleted items from Git history; coordinates across multiple independent storage locations; and runs on any machine with Python and Git.

These properties contradict many widely taught assumptions. I do not claim that the textbooks are wrong. I claim only that my system works differently, and that this difference may be worth studying for those who are curious.

The code is the ultimate reference. The reader may verify each claim by inspecting the source.
