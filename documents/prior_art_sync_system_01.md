# Prior Art Disclosure: Distributed Synchronization for Encrypted, Item‑Level Git Repositories

## A Technical Description of Per‑UUID Conflict Resolution Using Timestamps Without Decryption

---

**Date of Disclosure:** June 2026  
**Author:** sys-ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** github.com/sys-ronin/terminal-notes  

---

## Summary

This document describes a synchronization method for distributed Git repositories where data is encrypted at rest and conflicts are resolved at the **item level** (per note, per file, per subnotebook) without ever decrypting the content. Each logical item is identified by a permanent UUID embedded in commit messages. Commits affecting the same UUID are grouped into a chain. When two repositories diverge, the system compares the timestamps of the last commit in each chain and keeps the chain whose last commit is newer. The result is a linear history with no merge commits, no manual conflict resolution, and no decryption during the conflict detection phase.

The method also handles **security commits** (password changes) separately: all security commits from both sides are preserved, deduplicated by content hash, and applied during reconstruction. This ensures that password changes propagate correctly without breaking the ability to decrypt the data.

The system is built on standard Git primitives (commit messages, timestamps, raw blob retrieval) and works with any remote Git server (GitHub, GitLab, Bitbucket, self‑hosted). No central coordination server is required.

---

## 1. Core Principles

### 1.1 UUID as Permanent Item Identifier

Every logical item – note, file, subnotebook – receives a UUID at creation. This UUID is embedded in every commit message that affects the item, using a structured format (e.g., `uuid:...`). The UUID never changes, even when the item is renamed, moved, or edited.

### 1.2 Commit as Immutable Snapshot

Each commit records the complete state of the encrypted JSON files (`notes.json`, `files.json`, `structure.json`) at that moment. The commit message also contains the UUID of the affected item and the action type (`CREATED`, `UPDATED`, `DELETED`, `RENAMED`, `RESTORED`, `ERASED`).

### 1.3 Timestamp as Conflict Resolution Authority

Each commit carries a Unix timestamp (seconds since the epoch). When two histories diverge, the timestamp of the last commit in a UUID chain determines which chain is kept. The system does not need to examine the encrypted content; it only compares timestamps.

### 1.4 No Decryption During Conflict Detection

The synchronization algorithm operates entirely on commit metadata (hashes, timestamps, UUIDs, raw encrypted blobs). It never decrypts `notes.json`, `files.json`, or `structure.json` to decide which version wins. Decryption is deferred until after the linear history is reconstructed.

---

## 2. Data Structures

### 2.1 Commit Metadata Extracted

For each commit, the system extracts:

| Field | Source | Purpose |
|-------|--------|---------|
| **Commit hash** | `git rev-list` | Unique identifier |
| **UUID** | Commit message (regex) | Groups commits by item |
| **Timestamp** | `%ct` format | Conflict resolution |
| **Author name/email** | `%an`, `%ae` | Preserve attribution |
| **Message** | `%B` | Full commit message |
| **Raw blobs** | `git show <hash>:<file>` | `notes_raw`, `files_raw`, `struct_raw` |

### 2.2 UUID Extraction Patterns

The system searches for UUIDs using three patterns, in order:

1. `uuid:<UUID>` (explicit metadata)
2. Standard RFC 4122 UUID (`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
3. Timestamp‑based ID (`\d{14}`) (legacy)

### 2.3 Security Commits Detection

A commit is classified as a **security commit** if its message contains `type: SECURITY:` or starts with `SECURITY:`. Security commits are handled separately from normal item commits.

---

## 3. Conflict Resolution Algorithm

### 3.1 Collect Commits from Both Sides

The system runs `git rev-list --no-merges <ref>` on both the local branch (`HEAD`) and the remote branch (`origin/master`). For each commit, it extracts the UUID, timestamp, raw blobs, and metadata.

### 3.2 Separate Normal and Security Commits

Security commits are separated from normal commits immediately after collection. They will be handled by a different logic path.

### 3.3 Group Normal Commits by UUID

Normal commits are grouped into dictionaries (`local_chains`, `remote_chains`) where the key is the UUID and the value is a list of commits affecting that UUID, sorted by timestamp.

### 3.4 Resolve Conflicts Per UUID

For each UUID that appears in either chain:

- If only one side has commits for that UUID, keep that side’s entire chain.
- If both sides have commits, compare the timestamps of the **last commit** in each chain (the most recent). Keep the chain whose last commit is newer. Discard the older chain entirely.

**This is the entire conflict resolution logic.** No JSON parsing. No decryption. No manual intervention.

### 3.5 Collect All Security Commits

All security commits from both sides are collected into a single list. Duplicates are removed by comparing the SHA‑256 hash of the raw `.tn_recovery` blob content. The newest security commit (by timestamp) is identified for later use.

### 3.6 Combine and Sort

The winning normal commits (from step 3.4) and the unique security commits (from step 3.5) are combined into a single list and sorted by timestamp (ascending). This list represents the linear history to be reconstructed.

---

## 4. Linear History Reconstruction

The reconstruction process creates a new, linear branch from scratch, replaying the winning commits in order.

### 4.1 Create Orphan Branch

The system creates an orphan branch (`temp-linear-reconstruction`) with no parent. This branch will hold the reconstructed history.

### 4.2 Apply Common Ancestor (if any)

If a common ancestor exists (found via `git merge-base`), the system retrieves the encrypted blobs from that ancestor and writes them to the working directory. This serves as the starting point.

### 4.3 Replay Winning Commits in Order

For each commit in the sorted winning list:

- Retrieve the raw encrypted blobs (`notes_raw`, `files_raw`, `struct_raw`) for that commit.
- Decrypt them (using the current crypto state) and merge into the working state.
- Write the updated encrypted blobs back to disk.
- Stage the changed files (`notes.json`, `files.json`, `structure.json`).
- If the commit is a security commit, also write the `.tn_*` files from that commit and stage them.
- Create a new commit with the original author, timestamp, and commit message.

**Important:** Decryption occurs only during replay, not during conflict resolution.

### 4.4 Restore Non‑Security TN Files

If no security commits were applied during reconstruction, the system restores the `.tn_*` files from backup copies made before the reconstruction began.

### 4.5 Replace Original Branch

The system switches back to the original branch, resets it to the reconstructed history, and deletes the temporary branch. A force push sends the linear history to the remote.

---

## 5. Security Commit Handling (Password Changes)

Password changes are represented by changes to the `.tn_recovery`, `.tn_test`, and `.tn_password` files. These files are not item‑specific and cannot be merged using the per‑UUID rule. The system handles them as follows:

1. **Separate early** – Security commits are separated from normal commits before any conflict resolution.
2. **Keep all** – All unique security commits from both sides are preserved (not just the newest chain).
3. **Deduplicate by content** – The system compares the raw `.tn_recovery` blob content using SHA‑256 to avoid keeping identical password changes from both sides.
4. **Apply during reconstruction** – When a security commit is encountered during replay, the system overwrites the `.tn_*` files in the working directory with the versions from that commit.
5. **Notify user** – After reconstruction, if the newest security commit came from the remote side, the system locks the notebook and informs the user that the password has changed. The user must use the new password to unlock.

This design ensures that a password change on one machine propagates to others, and that the system never ends up in a state where the notebook cannot be decrypted.

---

## 6. Handling Diverged Histories Without a Common Ancestor

When the local and remote repositories have no common ancestor (e.g., when a notebook is cloned from a backup or created from scratch), the system presents a simple decision interface to the user. It compares the timestamps and commit counts of both branches and offers one of three actions:

- **Update local** – if the remote is newer (or has more commits), reset local to remote.
- **Push local** – if local is newer (or has more commits), force push local to remote.
- **Reconstruct** – if both sides have unique commits, perform the per‑UUID reconstruction described above.

This decision is presented in clear, non‑technical language.

---

## 7. Implementation Notes

### 7.1 No JSON Parsing During Conflict Resolution

The synchronization algorithm never calls `json.loads()` on the encrypted blobs. It treats the blobs as opaque binary data. Parsing and decryption are deferred until after the winning commits are selected.

### 7.2 Atomic Operations

All writes to the working directory are performed directly. The reconstruction branch is built in isolation and only replaces the original branch after successful completion.

### 7.3 Git Commands Used

- `git rev-list --no-merges` – enumerate commits
- `git log -1 --format=%an|%ae|%ct|%B` – extract metadata
- `git show <hash>:<file>` – retrieve raw blobs
- `git merge-base` – find common ancestor
- `git checkout --orphan` – create new branch without history
- `git commit` with environment variables (preserve original author and timestamp)
- `git push --force` – update remote after reconstruction

### 7.4 Platform Support

The system is platform‑independent, using only standard Git commands and Python’s standard library. It works on Linux, macOS, and Windows, with any remote Git server (GitHub, GitLab, Bitbucket, Gitea, or self‑hosted).

---

## 8. Prior Art Assertion

This document establishes prior art for the following concepts, all of which are disclosed in public, timestamped materials as of June 2026:

1. **Per‑UUID conflict resolution** using commit timestamps, without decrypting content.
2. **Separation of normal and security commits** during synchronization.
3. **Deduplication of security commits** by content hash (`.tn_recovery`).
4. **Linear history reconstruction** on an orphan branch, preserving original timestamps and author information.
5. **Synchronization of encrypted Git repositories** without a central coordination server.
6. **Handling of diverged histories without a common ancestor** through a simple user‑facing decision interface.

The concepts disclosed herein are now part of the public domain. No party may obtain valid patent claims covering any concept described in this document.

---

## 9. Conclusion

This document describes a synchronization method for distributed, encrypted Git repositories where conflicts are resolved at the item level using only commit timestamps. The system never decrypts the content during conflict detection, works with any Git remote, and requires no central server.

The method handles both normal item updates and security‑critical password changes. It produces a linear history with no merge commits and no manual conflict resolution.

The description is factual. The code is open. The behavior is observable. This disclosure is made in the public interest.

---

**sys-ronin**  
June 2026  
sys_ronin@protonmail.com  
github.com/sys-ronin/terminal-notes
```
