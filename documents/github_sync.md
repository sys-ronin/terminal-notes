# PRIOR ART DISCLOSURE
## Conflict‑Free Git Sync for Local‑First Applications

**Date of publication:** May 2026
**Repository:** [https://github.com/sys-ronin/terminal-notes](https://github.com/sys-ronin/terminal-notes)
**Status:** Public, irrevocable, timestamped

This document establishes prior art for a specific method of synchronizing local‑first applications using Git as a transport, without exposing the user to merge conflicts, rebase complexity, or manual resolution.

**No party may patent these methods. No party may claim exclusive rights.**
This is not a request. This is a statement of fact.

---

## Table of Contents

1. The Problem: Sync Without User Intervention
2. The Core Innovation: State‑Aware Sync Decision Engine
3. Detection Mechanism: Counting Commits Ahead and Behind
4. The Divergence Resolution: Pull‑Then‑Push with Rebase
5. First‑Push Detection and Automatic Repository Creation
6. Tag Synchronization as Part of Sync
7. No Conflict Viewer, No Manual Merge
8. Integration with Hardware‑Bound Encryption
9. Integration with UUID‑Based Item Tracking
10. Adaptation to Other Platforms
11. Prior Art Assertion

---

## 1. The Problem: Sync Without User Intervention

Git is a powerful version control system, but it was designed for developers, not for end users. Its standard sync workflow exposes users to concepts that are barriers to non‑technical users:

- **Merge conflicts** – Git inserts conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) into files when two branches have diverged. Users must manually edit these markers and decide which changes to keep.
- **Rebase complexity** – `git rebase` can resolve conflicts more cleanly, but it requires understanding of commit history rewriting and force pushing.
- **Manual resolution** – Even with GUI tools, conflict resolution is a separate, interrupt‑driven workflow that breaks the user's flow.

Existing Git‑based note‑taking applications (e.g., Obsidian Git plugin, Foam, GitJournal) use Git in a linear, state‑agnostic manner:

```bash
git add .
git commit -m "update"
git pull
git push
```

This sequence fails when the local and remote branches have diverged. The user is then presented with a conflict and must intervene.

**No existing application provides a truly conflict‑free, one‑button sync that works for all states (no remote, local ahead, remote ahead, diverged) without user intervention.**

This disclosure describes such a method.

---

## 2. The Core Innovation: State‑Aware Sync Decision Engine

The sync operation is not a fixed sequence of Git commands. It is a **decision engine** that:

1. **Detects the current state** of the local repository relative to its remote.
2. **Selects the appropriate command sequence** based on that state.
3. **Executes the sequence** without further user input.
4. **Reports the outcome** with clear, non‑technical language.

### 2.1 The State Machine

| State | Condition | Action |
|-------|-----------|--------|
| **No remote** | Remote does not exist | Create repository (via API), then push all commits |
| **Remote exists, no commits** | Remote exists but has zero commits | Push all commits |
| **Local ahead** | `ahead > 0, behind = 0` | Push only |
| **Remote ahead** | `ahead = 0, behind > 0` | Pull only (`git pull --rebase`) |
| **Diverged** | `ahead > 0, behind > 0` | Pull (`git pull --rebase`), then push |
| **Already synced** | `ahead = 0, behind = 0` | Do nothing, report already synced |

The decision is made **before any write operation**. The user sees a description of what will happen and confirms with a single keystroke (`y` or `n`).

### 2.2 Why This Is Non‑Obvious

Conventional Git workflows treat `pull` and `push` as separate operations. The user is expected to know when to pull and when to push. The innovation here is:

- **The system decides**, not the user.
- **The decision is based on objective, queryable state** (commit counts), not heuristics.
- **The diverged case is handled automatically** by pulling first, then pushing – a sequence that many Git users do not know is the correct fix.
- **The user never sees a conflict** because the system never allows a state where a conflict could be presented.

This is not an automation of existing Git commands. It is a **reordering and conditional selection** of commands that eliminates the possibility of conflict presentation.

---

## 3. Detection Mechanism: Counting Commits Ahead and Behind

The state is detected using Git's built‑in revision range syntax. No external index or database is required.

### 3.1 Commands

After `git fetch origin` (which retrieves remote state without applying changes):

```bash
# Count commits in local that are not in remote (ahead)
git rev-list origin/master..master --count

# Count commits in remote that are not in local (behind)
git rev-list master..origin/master --count
```

These commands return integers. The system does not parse commit messages or examine file contents. The counts are sufficient to determine the state.

### 3.2 Why Revision Ranges Work

The two‑dot syntax (`A..B`) means: "commits reachable from B but not from A." This is Git's native method for comparing branches. It is:

- **Deterministic** – the same query returns the same result for the same repository state.
- **Fast** – Git uses its internal commit graph; no full history scan is required.
- **Language‑independent** – the same commands work on any platform where Git is installed.

### 3.3 Fallback Detection for Missing Remote

If the remote does not exist, `git remote get-url origin` fails. The system detects this before attempting revision range queries and enters the **no remote** state.

If the remote exists but has no commits, `git ls-remote origin HEAD` returns empty. The system detects this and enters the **first push** state.

---

## 4. The Divergence Resolution: Pull‑Then‑Push with Rebase

When both `ahead > 0` and `behind > 0`, the system executes:

```bash
git pull --rebase origin master
git push origin master
```

### 4.1 Why Rebase, Not Merge

`git pull` without `--rebase` creates a merge commit. If the diverged commits touch the same files, Git inserts conflict markers into the file. The user must manually resolve.

`git pull --rebase` replays local commits on top of the remote commits. If a conflict occurs during replay, Git stops and asks the user to resolve. However, in the context of a note‑taking application where:

- Each note has a unique UUID
- Notes are stored in JSON files keyed by UUID
- Different UUIDs are different keys in the JSON object

Conflicts are extremely rare. When they do occur, the user is still presented with a conflict. But the system's design (UUID separation) minimizes this risk.

### 4.2 Why Pull First, Then Push

If the system pushed first when diverged, the push would be rejected (non‑fast‑forward). The user would then have to pull. This is the standard Git error message, which is cryptic to non‑technical users.

By pulling first, the system ensures the push will be fast‑forward. The user never sees a rejected push error.

**The sequence (pull then push) is the innovation, not the individual commands.**

---

## 5. First‑Push Detection and Automatic Repository Creation

When the remote does not exist, the system:

1. **Checks if the remote repository exists on the hosting platform** (GitHub, GitLab, Bitbucket, etc.) via the platform's API.
2. If it does not exist, **creates it** using the platform's API with the user's stored credentials.
3. **Pushes all commits** to the newly created repository.
4. **Links the local notebook** to the remote repository.

This eliminates the separate "create repository" step that is required in standard Git workflows.

### 5.1 API Integration

The system uses the platform's REST API to check existence and create repositories. The API calls are:

- **Check existence:** `GET /repos/{owner}/{repo}`
- **Create:** `POST /user/repos` with `{"name": "...", "private": true/false}`

The user's credentials (personal access token) are stored in an encrypted vault, separate from the notebook encryption keys.

### 5.2 Why This Is Non‑Obvious

Standard Git workflows require the user to:
1. Create a repository on the web interface (or via CLI)
2. Copy the remote URL
3. Run `git remote add origin <url>`
4. Run `git push -u origin master`

The system collapses these four steps into one: press `[S]ync`, confirm, done. The user never leaves the application, never copies a URL, never runs a Git command.

---

## 6. Tag Synchronization as Part of Sync

Git tags (e.g., version tags like `v1.2.3`) are also synchronized during the sync operation. The system:

1. **Lists local tags** (`git tag -l`)
2. **Lists remote tags** (`git ls-remote --tags origin`)
3. **Computes differences**: tags to push (local not in remote), tags to delete (remote not in local)
4. **Offers the user options**:
   - Push new tags only
   - Full sync (push new + delete removed)
   - Skip tags, push commits only

If the user selects full sync, the system:

- **Deletes removed tags** from the remote (`git push origin :refs/tags/<tag>`)
- **Pushes new tags** (`git push origin <tag>`)

Tag synchronization is integrated into the same `[S]ync` button. The user does not need to run separate `git push --tags` commands.

---

## 7. No Conflict Viewer, No Manual Merge

The system **does not implement** a conflict viewer, a three‑way merge tool, or any manual resolution interface.

This is a deliberate design choice. The system prevents conflicts from being presented to the user by:

- Using UUID‑keyed JSON storage (changes to different UUIDs do not conflict)
- Applying `pull --rebase` before push when diverged
- Never allowing a state where conflict markers would be inserted

If a conflict does occur (e.g., the same note edited in two different clones), the system's behavior is:

- The `git pull --rebase` command will stop and report the conflict.
- The system does not attempt to resolve it automatically.
- The user is informed that manual intervention is required (rare).

However, in normal operation with UUID‑separated storage, conflicts are extremely rare. The system is designed for **conflict avoidance**, not conflict resolution.

---

## 8. Integration with Hardware‑Bound Encryption

The sync operation works seamlessly with encrypted notebooks. The encryption keys are stored in a vault file that can be located separately from the notebook data (see prior art disclosure on Ephemeral Coordination).

During sync:

- The remote repository contains encrypted JSON blobs (`.json` files encrypted with AES‑GCM).
- Git treats them as binary files; delta compression works on the encrypted blobs.
- The commit messages are **not encrypted**; they contain UUIDs and action types in plain text, enabling remote search without decryption.

This is a non‑obvious combination: **encrypted content, plain‑text queryable metadata, and Git‑based sync** all working together without a central server.

---

## 9. Integration with UUID‑Based Item Tracking

Every note, file, and subnotebook has a permanent UUID. Commit messages embed these UUIDs. The sync operation does not use UUIDs directly, but the UUIDs enable:

- **Timeline reconstruction** across sync boundaries – a note's history is preserved even after push/pull.
- **Activity aggregation** – the sync operation does not break the ability to see all changes across a notebook hierarchy.
- **Resurrection** – deleted items can be restored from history even after they have been synced to a remote.

The sync operation is **UUID‑agnostic** – it works on Git commits, which already contain the UUIDs. No additional coordination is required.

---

## 10. Adaptation to Other Platforms

The method described here is platform‑independent. The same state‑aware decision engine can be implemented on:

- **Web applications** – using the Git HTTP API or a local proxy
- **Desktop native applications** – using libgit2 or shelling out to Git
- **Mobile applications** – using a lightweight Git implementation or a remote sync service that emulates the same state detection

The core innovation is the **decision logic**, not the specific Git commands. Any implementation that:

- Detects whether a remote exists
- Counts commits ahead and behind using revision ranges
- Selects pull, push, or pull‑then‑push based on those counts
- Creates the remote repository automatically if missing

is practicing the method disclosed herein.

---

## 11. Prior Art Assertion

I, **sys‑ronin**, do hereby establish this document and the accompanying source code repository as prior art under **35 U.S.C. § 102(a)(1)** (United States) and **Articles 54 & 56 of the European Patent Convention (EPC)**.

- **Date of public disclosure:** May 2026
- **Mode of disclosure:** public GitHub repository
- **Status:** irrevocable and unwithdrawable

**The following concepts are disclosed as prior art:**

1. Using `git rev-list origin/master..master --count` and `git rev-list master..origin/master --count` to determine sync state.
2. The state machine that maps (ahead, behind, remote_exists, remote_has_commits) to actions (no remote, push only, pull only, pull‑then‑push, already synced).
3. Automatic repository creation via platform API when remote does not exist.
4. Tag synchronization integrated into the same sync operation, with options for push‑only, full sync, or skip.
5. The sequence `git pull --rebase` followed by `git push` for diverged branches, eliminating manual conflict resolution.
6. The absence of a conflict viewer or manual merge interface, relying on conflict avoidance instead.
7. Integration of encrypted blob storage with plain‑text, queryable commit messages.

**No party may:**

- Obtain valid patent claims covering these methods
- Enforce existing patents against implementations of these methods
- Assert trade secret protection over any implementation disclosed herein
- Claim exclusive rights to the state‑aware sync decision engine

The code is open. The methods are described. The reader may verify each claim by inspecting the source repository.

---

**End of Prior Art Disclosure**

*This document is a statement of fact, not a legal opinion. No legal advice is offered. No warranty is provided.*
