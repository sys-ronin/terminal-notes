# Prior Art Disclosure: Terminal Notes Integrated System

## Complete Technical Disclosure Including Deterministic UUID‑Level Synchronisation

---

**Date of Disclosure:** February 2026 (initial), May 2026 (updated)  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** github.com/sys-ronin/terminal-notes  

---

This document establishes prior art for the complete integrated system described herein. All concepts, implementations, combinations, and future adaptations disclosed are now part of the public domain.

**No party may patent these concepts. No party may claim exclusive rights.**  
This is not a request. This is a statement of fact.

---

## Table of Contents

1. UUID Permanence (Item Identity)
2. Infinite Nested Subnotebooks with Full Content
3. Notebook Registry & Portability
4. Notebook Manager with Git Account Integration
5. Three‑File Atomic Architecture
6. Custom Encryption Architecture (Zero‑Trust, Portable, Hardware‑Bound)
7. Zero‑Trust Binary Vault (Session Storage)
8. Universal JSON Handler with Automatic Crypto
9. Git as Item‑Level Temporal Database
10. Git Resurrection Engine
11. Timeline Engine
12. Custom Query Parser for Pinpoint Searching
13. Unified Search Engine
14. Relative Ancestor Navigation (Fish‑Eye)
15. Activity View (Temporal Aggregation)
16. Complete Hierarchy Resurrection
17. git‑filter‑repo as Embedded Module with Custom Filters
18. Permanent Erasure with git‑filter‑repo
19. Crash Recovery with UUID Keying
20. Configurable Editor System
21. Data‑as‑UI (Zero Learning Curve)
22. Terminal User Interface as Integral Component
23. Cross‑Platform Adaptations (Future Implementations)
24. Cognitive Alignment (Emergent Property)
25. Zero Background Processes (Cognitive Efficiency)
26. Portable Secure Session Vaults (Custom Locations)
27. Trusted Devices Management
28. Missing Vault Detection and Active Cache Validation
29. Docker / Cloud Ephemeral Fingerprinting
30. O(1) Deterministic UUID Chains and Multiple‑Origin Coordination
31. Deterministic UUID‑Level Synchronisation (Item‑Level Git Sync)
32. Eternal License
33. Prior Art Assertion
34. Integrated System

---

### 1. UUID Permanence (Item Identity)

Every item (note, notebook, file, subnotebook) receives a UUID at creation. The UUID never changes throughout the item’s lifetime. It survives:

- Rename operations
- Move operations between notebooks
- Deletion and resurrection from history
- Export and re‑import across machines
- Git commit history (every commit references the UUID)
- Platform migration (Linux, macOS, Windows)
- Hard erase (UUID persists in commit history until purged via `git‑filter‑repo`)

UUIDs enable:
- Item tracking across time
- Resurrection of deleted items
- Timeline reconstruction
- Activity aggregation
- Cross‑notebook reference integrity
- Recovery after crashes
- O(1) dictionary lookups in memory
- Deterministic navigation through parent‑child relationships
- **Per‑UUID commit grouping for synchronisation**

UUID format: timestamp‑based (`YYYYMMDDHHMMSS`) for simple items, RFC 4122 UUID4 for complex.
All operations use UUID as primary key, never name or path.

---

### 2. Infinite Nested Subnotebooks with Full Content

Notebooks can contain unlimited nested subnotebooks, forming arbitrary depth hierarchies. Each subnotebook is a full notebook object with its own UUID, name, parent ID reference, notes collection, and subnotebooks collection (recursive).

Content inheritance:
- Notes in subnotebooks are stored in the parent’s `notes.json` / `files.json`
- Full content of entire hierarchy is accessible from the root
- No depth limit – recursion handles any nesting level
- Search traverses the entire tree automatically
- Activity view aggregates changes across the whole hierarchy

The tree structure enables project organisation, hierarchical categorisation, unlimited depth without performance degradation, independent versioning, and selective restoration of branches.

---

### 3. Notebook Registry & Portability

A central registry (`notebooks_registry.json`) maps notebook UUID → filesystem path and, for encrypted notebooks, to vault and entry identifiers. Registry entries for encrypted notebooks are encrypted with the notebook’s own key.

Notebooks can live in any location:
- Default directory (`notebooks_root/`)
- Custom user‑specified paths
- External drives, network shares, Docker volumes, cloud‑synced folders
- USB drives (portable)

Path handling:
- Paths stored relative to `notebooks_root` when possible
- Absolute paths preserved for external locations
- Cross‑platform normalisation prevents duplicate detection failures
- Missing paths detected and flagged during load

Custom paths persist in `structure.json` within each notebook. Notebooks are self‑contained and can be moved manually. Re‑import detects existing paths and prevents duplicates.

---

### 4. Notebook Manager with Git Account Integration

A centralised manager for all notebooks provides Git account integration:

**Account system**
- Encrypted storage of Git credentials using a zero‑trust binary vault
- Supports GitHub, GitLab, Bitbucket, and self‑hosted Gitea
- Account ID generated from `username@host`
- Per‑notebook repository configuration
- Multiple entries per account (one per trusted machine)

**Repository management**
- Link a notebook to a Git repository
- Create repository on first push
- Push with authentication via stored token
- Pull updates for listed notebooks
- Change visibility (public/private)
- Delete remote repository
- Test connection with timeout and retry
- Change remote account and repository

**Parallel operations**
- Multi‑threaded repository scanning with connection pooling
- DNS caching for performance
- Timeout handling with retry logic
- Progress indicators for batch operations

**Notebook discovery**
- Scan accounts for Terminal Notes repositories
- Detect encryption status remotely
- Parse `structure.json` to extract metadata without cloning
- Show counts (notes, files, subs) remotely
- Link existing notebooks to accounts

This creates a complete notebook lifecycle management system integrated with Git hosting platforms.

---

### 5. Three‑File Atomic Architecture

Each notebook is a self‑contained directory with exactly three JSON files:

- **`structure.json`** – hierarchy only (UUIDs, names, parent‑child relationships, custom_path). Enables tree navigation without loading content. Small size allows fast loading even with thousands of notes.
- **`notes.json`** – UUID → content mapping for regular text notes. Human‑readable, Git‑diffable, searchable.
- **`files.json`** – UUID → content mapping for file notes (80+ extensions). Extensions stored in `structure.json` for syntax highlighting.

**Write operations are atomic:**
1. Write to `.tmp` file
2. `fsync()` to force disk flush
3. `rename()` atomic operation
4. Original file replaced only on success

**Crash recovery is inherent:** partial writes affect only `.tmp` files, which are ignored on next startup. No corruption possible.

This separation enables:
- Resurrection (reconstruct items from history)
- Timeline (version history per item)
- Activity view (aggregated changes across hierarchy)
- Git efficiency (small deltas, meaningful diffs)
- Memory efficiency (load structure without content)
- **Surgical per‑UUID conflict resolution during sync**

---

### 6. Custom Encryption Architecture (Zero‑Trust, Portable, Hardware‑Bound)

A novel encryption architecture that integrates seamlessly with all operations:

**Key derivation (one‑way, irreversible):**
```text
Kp = SHA256(password + b':' + folder_name)   # password key
Ks = SHA256(phrase + b':' + folder_name)     # phrase key (never changes)
Kc = SHA256(Kp + Ks)                         # combined key
```
The folder name is part of the key. Renaming the folder permanently locks the data, creating a physical binding between key and storage location.

**Three verification files per notebook:**
- `.tn_test` – `"VERIFICATION"` encrypted with Ks
- `.tn_recovery` – `Kp` encrypted with Ks
- `.tn_password` – `Kc` encrypted with Kc (self‑referential)

**Encryption format:**
- Magic header: `b"TN_ENC"` (6 bytes) prepended to all encrypted data
- Nonce: 12 random bytes per encryption
- Ciphertext: AES‑GCM encrypted data with authentication tag

**File structure:**
- `structure.json`, `notes.json`, `files.json` → fully encrypted (binary)
- `.tn_test` → encrypted verification marker

**Registry encryption:** Notebook entries in the master registry are encrypted with the notebook’s key, preventing metadata leakage about encrypted notebooks.

**Lock/Unlock as explicit memory manager:**
- **Locked:** `custom_path = None`, session key removed, keys cleared from RAM, shows 🔒
- **Unlocked:** `custom_path` restored, session key present, shows 🔐

**Autolock flag (per‑notebook):** stored in the registry entry as `autolock`. When enabled, the notebook is forced into locked state on every application startup, regardless of its previous lock state. Useful for shared computers or sensitive notebooks.

**Password change (instant, no re‑encryption):** only `.tn_recovery` and `.tn_password` are updated; Ks never changes; notebook content remains encrypted with Ks.

**Cross‑machine synchronisation:** each trusted machine adds its own entry in the session vault. The entry is encrypted with `SHA256(timestamp + machine fingerprint)`. The fingerprint is never stored – derived at runtime. A new machine requires the recovery phrase once, then only the password. Old entries remain for other machines.

---

### 7. Zero‑Trust Binary Vault (Session Storage)

Keys are stored in a portable, tamper‑evident binary vault (`session.vault`). The vault format (version 5 or later) stores:

- Version number (4 bytes)
- For each notebook: `id_length`, `notebook_id`, `num_entries`
- For each entry: `timestamp`, `nonce`, `encrypted_keys_length`, `encrypted_keys`, `active_flag`, `created_timestamp`, `system_name` (hostname)

**Key derivation for each entry:**
`encryption_key = SHA256(timestamp + current_fingerprint)`

The fingerprint is derived from hardware at runtime and **never stored**.

**Active flag** enables O(1) lookup without trial decryption; falls back to trial decryption if the flag is incorrect.

**System fingerprint generation (runtime only, never stored):**
- Linux: `/etc/machine-id`, product UUID, CPU info
- macOS: IOPlatformUUID, hardware UUID, serial number
- Windows: MachineGUID, ComputerName, SID
- Fallback: hostname, username, platform info, file paths

**Properties:** no outer encryption, no stored fingerprint, tamper‑evident, portable, multi‑machine, zero‑trust.

---

### 8. Universal JSON Handler with Automatic Crypto

Single unified handler for all JSON operations:

- `read_json(filepath, crypto)` – reads any JSON file, automatically decrypts if crypto provided, returns parsed dict or `None`
- `write_json(filepath, data, crypto)` – writes any JSON file with atomic pattern, encrypts automatically if crypto provided, guarantees no partial writes
- `read_bytes(raw_bytes, crypto)` – reads JSON from bytes (e.g., `git show` output), decrypts if crypto provided
- `_parse_json(raw, crypto)` – the single point where decryption happens; tries decryption first, falls back to plain text

All operations (load, save, merge, filter) use these handlers. Encryption is invisible – callers simply pass a `crypto` object when available. The entire application is encryption‑aware without being aware of the encryption details.

---

### 9. Git as Item‑Level Temporal Database

Every state change is committed to Git automatically. The Git repository lives inside each root notebook directory.

Each commit message follows a strict format:

```
type: ACTION CONTENT_TYPE: title | context

Metadata description (change statistics, etc.)

Metadata: uuid:ITEM_UUID | parent:PARENT_UUID | root:ROOT_UUID
```

**Actions:** `CREATED`, `UPDATED`, `EDITED`, `RENAMED`, `DELETED`, `RESTORED`, `ERASED`
**Content types:** `NOTE`, `FILE`, `NOTEBOOK`, `SUBNOTEBOOK`

Complete item history is queryable with `git log --grep uuid:<UUID> --all`.
Item‑level searching: find all commits affecting a specific UUID; track item across renames, moves, deletions; reconstruct state at any point; aggregate activity; search deleted/renamed/restored/erased items.

This enables Git to function as a true item‑level temporal database, not just a file‑level version control system. **This is the foundation for deterministic UUID‑level synchronisation.**

---

### 10. Git Resurrection Engine

Centralised engine for all historical item operations:

- `find_deleted_items(query)` – uses `git log --grep "^type: DELETED"`, extracts UUID, reconstructs item from commit before deletion
- `find_renamed_items(query)` – uses `git log --grep "^type: RENAMED"`, reconstructs from commit before rename
- `find_restored_items(query)` – uses `git log --grep "^type: RESTORED"`, returns reconstructed items
- `find_erased_items(query)` – uses `git log --grep "^type: ERASED"`, returns minimal metadata (tombstone)
- `_create_temp_json_for_item(uuid, commit_hash)` – core reconstruction; extracts `structure.json`, `notes.json`, `files.json` from a specific commit, finds item by UUID, creates a minimal temporary directory with the item’s data
- `display_resurrected_item(result_data, ui)` – unified display for any resurrected item
- `_restore_item(result_data, ui)` – restores item to original location, merges content, updates structure, commits as `RESTORED`

The resurrection engine is the single source of truth for all historical operations. Timeline, activity, and search all delegate to it.

---

### 11. Timeline Engine

Specialised engine for item version history:

- `get_item_timeline(uuid, notebook_id, crypto)` – gets all commits mentioning a UUID, returns metadata (commit_hash, date, message)
- `create_version_at_commit(uuid, commit_hash, crypto)` – reconstructs item at a specific commit, delegates to resurrection engine

**Timeline display:** shows versions with dates and actions (CREATED with total characters, UPDATED with change stats, RENAMED with old‑new, DELETED/ERASED as action only). Viewing a version calls `create_version_at_commit` and displays using the resurrection engine’s viewers (read‑only, export available for files).

Timeline is separate from search and activity: search finds items across time, activity shows recent changes across items, timeline shows one item’s complete history – all use the same underlying Git database.

---

### 12. Custom Query Parser for Pinpoint Searching

Order‑independent token recognition with a single positional constraint (the `in*` token must be last). The query format:

```
s [action*] [type*] [date*] [time*] [g*] [text] [in* notebook]
```

**Action filters (wildcard required):** `created*`, `deleted*`, `edited*`, `updated*`, `renamed*`, `restored*`, `erased*`
**Type filters (wildcard required):** `note*`, `file*`, `sub*`, `notebook*`
**Date filter (wildcard required):** `date* DD-MM-YYYY [DD-MM-YYYY]`
**Time shortcuts:** `today*`, `yesterday*`, `thisweek*`, `lastweek*`
**Scope (must be at end):** `in* notebook_name`
**Global override (anywhere):** `g*`
**Text query:** remaining words → substring search, case‑insensitive, AND logic

**Parser behaviour:** filters can appear in any sequence (except `in*` at end); recognised tokens are removed; remaining tokens become text search; single pass, no lookahead except date ranges.

**Intent‑based display:** with action wildcard → no action prefix in results; without action wildcard → action prefix is shown.

Examples:
- `s created* file* meeting in* work`
- `s meeting file* created* in* work` (same result)
- `s deleted* yesterday* report`
- `s g* config in* work`
- `s date* 15-03-2026 20-03-2026 python`
- `s thisweek* important`
- `s renamed*`, `s erased*`

This enables precise, natural language‑like queries without complex syntax.

---

### 13. Unified Search Engine

A single search interface finds all items regardless of state (current, deleted, renamed, restored, erased).

**Search processor:**
1. Resolves target notebooks (context, `in*` scope, or all)
2. Parses the query using the custom query parser
3. Collects current items via simple search (title/content)
4. Collects historical items via the resurrection engine for all action types
5. Deduplicates by UUID
6. Applies type/action/date filters
7. Sorts by date (newest first)
8. Limits to 50 results

**Intent‑based display:**
- With action wildcard → no action prefix (e.g., `"file.txt [work]"`)
- Without action wildcard → action prefix shown (e.g., `"created file: file.txt [work]"`, `"updated note: notes.txt (+15/-23) [work]"`, `"deleted note: old.txt [work]"`, `"renamed note: todo → tasks [work]"`)

**Result formatting:** current notes/files show type, title, location; current notebooks show name, counts (n/f/s), lock status; historical items show action, title, original location; renamed items show old → new; all items show location in brackets using a smart path (relative to context).

This creates a search experience that understands intent, shows appropriate context, never hides history, and adapts to the user.

---

### 14. Relative Ancestor Navigation (Fish‑Eye)

Navigation is based on relative position, not absolute paths.

**Navigation stack:** a single unified list of `{'screen': str, 'id': str, 'page': int}`. Push, pop, replace_page, clear operations. No forward button – it is never needed.

**Jump history:** saves the current position before jumping; maximum 20 entries (FIFO); `jb` command returns to the previous position (temporal navigation).

**Fish‑eye path display:** the full hierarchy is truncated to fit the terminal width. An algorithm maintains 4–7 visible segments (Miller’s Law). Left ellipsis (`...`) for truncated ancestors, right ellipsis for truncated descendants. Example: `...[2]LEVEL3/[3]LEVEL4/[4]LEVEL5/[5]LEVEL6/`

**Number mapping:** each visible segment gets a relative number; numbers reset per screen, independent of absolute depth.

**Jump command `j<number>`:** looks up a notebook by its relative number; if the target is in the current stack, the stack is truncated; otherwise, the system rebuilds the full path by walking the parent chain. Jump history is saved automatically. O(1) lookup, O(d) path reconstruction where `d ≤ 10`.

**Back command `b`:** pops the navigation stack and returns to the exact previous state (same screen, same notebook, same page).

This enables navigation by position, constant cognitive load, muscle memory development, no path memorisation required, and no forward button because forward is never needed.

---

### 15. Activity View (Temporal Aggregation)

Activity view shows changes across time with hierarchical context.

**Collection:** for a notebook, collects all UUIDs in its hierarchy (notebook + all descendants). Uses `git log --grep` with a UUID pattern (OR of all UUIDs). Also fetches `DELETED` commits that might lack a UUID. Results limited to 50, sorted newest first.

**Hierarchical path calculation:** determines where an item sits relative to the viewing notebook and shows a relative path. Examples (viewing notebook “work”):
- Item in `work/notes` → `notes`
- Item in `work/projects/client/docs` → `.../projects/client/docs`
- Item in `work` itself → `work`

**Display format:** `[1] created note: meeting-notes (+245) [work/notes]`, `[2] updated file: config.py (+15/-23) [work/projects]`, `[3] renamed note: todo → tasks [work]`, `[4] deleted sub: old-project [.../archived]`

**Security activity view (password change history):** a specialised subset showing only `SECURITY` commits. Queries `git log` with `--grep "SECURITY:"` and `--grep "root: {uuid}"`. Displays entries as `date | method (old_password/recovery_phrase) | machine (hostname)`. The button appears progressively only after the first password change.

**Character stats:** `CREATED` – total characters; `UPDATED` – added/removed characters (`+X/-Y`); `RENAMED` – shows old → new; `DELETED/ERASED` – no stats.

Activity is history made visible – not a log, but a narrative.

---

### 16. Complete Hierarchy Resurrection

Any item, at any point in its history, can be resurrected.

**Resurrection process:**
1. User finds the item via search (e.g., `deleted*` filter) or activity view
2. Views the item (showing its historical state)
3. Presses `[R]estore`

**Restoration logic:** extracts the parent UUID from the commit metadata. If the parent exists, restores to the original location; if the parent is missing, prompts for a destination. Uses the resurrection engine’s `_restore_item`.

**For notes/files:** content is merged into live `notes.json` / `files.json` (UUID‑keyed); `structure.json` is updated to include the item in the parent’s notes list; Git commit with `RESTORED` message.

**For subnotebooks:** recursively collects all UUIDs in the hierarchy; merges **all** content (all notes and files) into the live files; updates `structure.json` with the complete hierarchy; Git commit summarising the restoration (e.g., `"RESTORED SUBNOTEBOOK: name | to location (X notes, Y subs)"`).

**Safety:** original location preferred; duplicate detection prevents conflicts; UUID unchanged (temporal continuity preserved); content merged, not overwritten.

Restoration works for deleted notes/files, deleted subnotebooks (with all contents), renamed items, and items from any point in the timeline.

---

### 17. git‑filter‑repo as Embedded Module with Custom Filters

`git-filter-repo` is not called as a subprocess; it is dynamically loaded as a Python module:

```python
filter_repo_path = os.path.join(os.path.dirname(__file__), "git_filter_repo.py")
spec = importlib.util.spec_from_file_location("git_filter_repo", filter_repo_path)
git_filter_repo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_filter_repo)
```

The module is modified with an `if __name__ == '__main__'` guard, enabling import without execution. This transforms a command‑line tool into a proper Python library.

**Custom filter classes extend the base `RepoFilter`:**

- **`UUIDEraseFilter`** – removes all commits containing a specific UUID; scans commit messages for the UUID pattern; removes the UUID from blob contents; tracks `commits_removed` and `blobs_removed`; preserves `ERASED` tombstone commits.
- **`NotebookEraseFilter`** – removes entire notebook hierarchies in one pass; takes a notebook UUID and a list of all descendant UUIDs; scans for `root:NOTEBOOK_UUID` pattern; removes all commits containing any UUID in the notebook.

**Command‑line integration:** `--uuid-erase UUID`, `--notebook-erase NOTEBOOK_UUID:UUID1,UUID2,...`

**Safety features:** never runs on the project root; `FILTER_REPO_AVAILABLE` flag for graceful fallback; repository validation before operations; atomic operations with rollback.

This enables programmatic history rewriting, exception handling, integration into applications, and batch operations impossible with CLI tools.

---

### 18. Permanent Erasure with git‑filter‑repo

Two‑tier deletion system:

- **Soft delete (default):** removes from current view only; history preserved in Git; item findable via `deleted*` search; restorable at any time; Git commit `type: DELETED`.
- **Hard erase (permanent):** removes from Git history completely using `git-filter-repo`; creates a tombstone commit marking erasure; not recoverable; Git commit `type: ERASED`.

**Erasure process for a single item:**
1. Identify all commits containing the UUID.
2. Run `UUIDEraseFilter` to remove the UUID from all files.
3. Remove from current view.
4. Create a tombstone commit.
5. Run Git garbage collection.

**Erasure process for an entire notebook:**
1. Collect **all** UUIDs in the notebook hierarchy.
2. Run `NotebookEraseFilter` with all UUIDs.
3. Remove the registry entry.
4. Delete session keys.
5. Delete the notebook folder.
6. Run Git garbage collection.

**Safety features:** confirmation required (“type ‘erase’ to confirm”); never runs on project root; `FILTER_REPO_AVAILABLE` flag for fallback; atomic operations with rollback.

**GDPR compliance:** complete removal of personal data; audit trail via tombstones; configurable per request; can erase entire notebooks.

This is the only operation that breaks UUID continuity.

---

### 19. Crash Recovery with UUID Keying

External editor sessions are protected against crashes.

**Recovery system:** directory `.recovery/` in the application root. Files named `{title}_{uuid[-6:]}.{ext}`. The UUID suffix ensures uniqueness across renames.

**Autosave:** a background thread monitors the temporary file. Every 30 seconds, it saves the content to a recovery file. Continues until the editor closes. UUID keying preserves identity.

**Recovery on access:** when a notebook is opened, the system checks for recovery files. For each file matching the notebook’s UUIDs, it compares the recovery timestamp with the note’s `updated` timestamp. If the recovery is newer, the content was never saved; the system restores the content to the note, commits the change with an edit message, and deletes the recovery file.

**Recovery scenarios:** editor crash, system crash, application crash, power failure. The recovery file persists until successfully merged.

**UUID keying ensures:** recovery files map to the correct notes, survive renames (UUID unchanged), survive moves between notebooks (UUID unchanged), and there is no cross‑notebook contamination.

---

### 20. Configurable Editor System

Users can choose their preferred editor for writing and viewing.

**Configuration file (`config.json`):**
```json
{
    "edit": "micro",
    "view": "micro",
    "info": "Available editors: micro, nvim, vim, helix, hx, emacs -nw, nano, kate, geany, gedit, pluma, mousepad, leafpad, mg, jed, joe"
}
```

**Editor resolution:** first launch creates `config.json` with defaults. The user can edit it manually; changes take effect immediately. No settings screen – configuration is an action, not a persistent UI element.

**Editor selection:** `edit` – editor for writing/modifying notes; `view` – editor for viewing (read‑only mode).

**Editor detection:** tests if the editor exists in `PATH`; falls back to the next available in the list; ensures at least one editor works.

**Special handling:** for `nvim`, `vim`, `emacs`, the system injects autosave commands/configuration. Other editors are launched normally.

**External editor invocation:** a temporary file with the correct extension is created. The editor is launched with the appropriate mode (read‑only if view). Content is read back after the editor closes. A recovery thread monitors during editing.

---

### 21. Data‑as‑UI (Zero Learning Curve)

The interface **is** the data. The data **is** the interface.

- **Numbered items:** every displayed item has a number (`[1]`, `[2]`, …).
- **Numbered commands:** `v1` views item 1, `d2` deletes item 2, `r3` renames item 3, `j4` jumps to position 4.
- **Path numbering:** `[1]root/[2]child/[3]grandchild/`, `j2` jumps to position 2 (child).
- **Footer options:** `[C]reate  [V]iew  [S]earch  [D]elete  [B]ack  [Q]uit` – each a single keystroke.

No menus, no toolbars, no context menus, no modal dialogs (except confirmations). No modes – the same commands work everywhere. No settings screen – configuration dissolves into necessity.

**Cognitive principles:**
- Recognition over recall (users see options)
- Affordance (numbers invite pressing)
- Consistency (same commands everywhere)
- Discoverability (footer shows all options)
- Progressive disclosure (buttons appear only when useful)

**Examples:** notebook list → `[1] Project [2] Work [3] Personal`; note list → `[1] Meeting [2] Todo [3] Ideas`; search results → `[1] file.txt [2] notes.md`; activity → `[1] created note [2] updated file`.

Numbers are not decoration; they are commands. The interface teaches itself through use. No learning curve, no tutorial, no documentation needed to start.

---

### 22. Terminal User Interface as Integral Component

The terminal user interface is not a separate component; it is the visible manifestation of the integrated logic chain described above. Every element of the TUI is a direct expression of the underlying architecture.

- **Navigation:** numbered lists are the navigation layer made visible; the path display is the fish‑eye algorithm rendered; `j3` is relative navigation in action; no forward button because the stack is transparent.
- **Search:** `s` query is unified search at work; results show action/type based on query intent; location brackets show smart path (relative to context).
- **History:** `t` command is timeline reconstruction; `a` command is activity aggregation; `v` on a historical item shows the resurrected state.
- **Operations:** `d` with confirmation is soft delete; `d` + ‘erase’ is hard delete with `git-filter-repo`; `r` is rename (UUID preserved); `x` is export (for files).
- **Navigation controls:** `b` is stack navigation (pop); `jb` is jump back through history (temporal return); page indicators respect working memory limits.
- **Visual elements:** header format maintains cognitive consistency; footer options reflect available operations (contextual); lock icons (🔐/🔒) show encryption state; character stats (`+245/-89`) show edit magnitude.

The TUI cannot be separated from the invention. It is the invention, made visible. The interface disappears. Only the writing remains.

---

### 23. Cross‑Platform Adaptations (Future Implementations)

The invention is platform‑independent. The following adaptations are disclosed as embodiments of the same integrated system:

- **Web adaptation:** relative navigation via numbered elements (clickable); unified search across all states; activity view; timeline; resurrection with confirmation dialog; permanent erasure with admin confirmation; data‑as‑UI; fish‑eye path display adapted to browser width; stack‑based navigation with browser history integration; UUID permanence; Git temporal database via API layer; encryption via Web Crypto API (same AES‑GCM); system fingerprint via browser fingerprinting (fallback to `localStorage`).

- **Desktop native adaptation:** keyboard‑driven navigation with numbered access; unified search; activity view as a native window; timeline interface; resurrection with native dialog; permanent erasure with system‑level confirmation; fish‑eye path display optimised for window width; crash recovery with native file system integration; external editor spawning with syntax highlighting; configurable editor via native preferences; system fingerprint via hardware IDs (same as the terminal version).

- **Mobile adaptation:** spatial navigation via numbered gestures or taps; unified search with touch‑friendly filters; activity view as a scrollable timeline; timeline view; resurrection with swipe gestures; fish‑eye path display adapted to screen width; UUID permanence via local storage; Git temporal database via local storage or API; crash recovery with mobile background processing; biometric unlock for encrypted notebooks.

- **Future platform adaptations:** any future platform that implements relative spatial navigation, unified search across all states, activity view, timeline, resurrection, permanent erasure with confirmation, data‑as‑UI, fish‑eye or adaptive path display, UUID‑based permanent item identity, Git‑based temporal queryability, crash recovery with key‑based restoration, and transparent encryption with system‑bound keys – practices the invention disclosed herein. The specific implementation may adapt to platform constraints, but the cognitive patterns and integrated logic chain remain the property of this prior art.

---

### 24. Cognitive Alignment (Emergent Property)

The following properties emerge from the integrated system:

- **Spatial memory alignment:** relative numbering matches Tversky’s spatial mental models (1992). Users navigate by position, not path. `j3` becomes reflex, not a conscious decision. No forward button eliminates disorientation.
- **Temporal memory alignment:** unified search across all states matches episodic recall. Activity view shows changes over time. Timeline shows evolution – separate but complementary. Users remember “before I deleted it” not timestamps. `jb` command provides temporal return to the previous cognitive context.
- **Working memory alignment:** fish‑eye display (4–6 chunks) matches Miller’s 7±2 (1956). Page indicators maintain orientation without overload. No forward button reduces decision count.
- **Cognitive load alignment:** zero extraneous UI matches Sweller’s load theory (1988). All attention is available for writing. No settings screen means no configuration decisions.
- **Recognition over recall:** users recognise options in the footer. Numbers invite pressing. Commands are discovered, not memorised. Every action is visible on the current screen.
- **Affordance perception:** numbered items afford “press number” (Gibson, 1979). Footer options afford “press letter”. No training required. The interface teaches itself.
- **Cognitive disappearance:** when tool and thought align, the tool disappears. This system disappears. Only the writing remains. The user never thinks about the software.
- **Embodied cognition:** commands migrate to muscle memory (Barsalou, 1999). `j3` becomes reflex, not a conscious decision. The body remembers what the mind forgets.
- **Flow state:** uninterrupted writing enables flow (Csikszentmihalyi, 1990). No notifications, no interruptions, no modals. The system waits. The user writes.
- **Errorless learning:** soft delete prevents permanent data loss from mistakes. Resurrection provides recovery from accidental deletion. Crash recovery ensures work is never lost. The user never experiences irreversible failure.

These theories were not consulted during development. They were discovered afterward and are cited to explain observed behaviour. The system existed before the explanation.

---

### 25. Zero Background Processes (Cognitive Efficiency)

The system performs **no work unless the user initiates an action**:

- No background indexing threads
- No periodic cache refreshes
- No auto‑save timers (only during active editing, and that thread dies when the editor closes)
- No pre‑loading of notebooks or notes
- No background sync processes

All operations – loading, decrypting, searching, committing – happen synchronously in response to user input.

**Memory footprint:**
- Locked notebooks: only a registry entry (~200 bytes)
- Unlocked notebook structure: ~10 KB per 100 notes
- Note content: loaded only when viewed
- Encryption keys: 32 bytes per unlocked notebook
- Timeline/activity results: limited to 50 items

**Lock button as explicit memory manager:** unloads encryption keys from RAM; clears notebook structure (notes, subnotebooks); removes content cache. The user controls what stays in memory, matching the human cognitive model of working memory.

This aligns with the brain’s default mode network: the brain is most active and creative when at rest. No constant background processing. The system is present only when needed.

---

### 26. Portable Secure Session Vaults (Custom Locations)

The secure session vault is no longer fixed to a single location. A `VaultManager` maintains a registry (`vaults_registry.json`) that maps a vault name to an absolute path or URL. Users can:

- Create new vaults at any location (local disk, USB, network share, cloud bucket, WebDAV server)
- Select an existing vault for a notebook
- Switch a notebook from the default vault to a custom vault, and back

Each notebook stores its associated vault identifier in the master registry entry. The `SessionKeyVault` transparently resolves the correct vault file path via the vault registry.

If a custom vault file is missing (e.g., USB unplugged), the system detects this during key resolution and offers the user options: retry, locate the vault manually, or use the recovery phrase to re‑create the entry in a new (or default) vault.

This feature enables **complete physical separation** of the key store from the application and the data, without compromising security.

---

### 27. Trusted Devices Management

The secure session vault stores per‑machine entries that include:

- `timestamp` (creation time)
- `nonce` and `encrypted_keys` (the actual key material)
- `active` flag for the current machine
- `system_name` (hostname) – a human‑readable identifier

The system provides a user interface (`_show_trusted_devices`) that lists all trusted devices for a notebook, marking the current active device. The user can **remove** any entry, including the current machine’s own entry. Removing the current machine’s entry immediately locks the notebook and clears all cached keys; the notebook can only be unlocked again using the recovery phrase.

No central server is involved. Each machine stores its own copy of the vault file, but entries are cryptographically bound to the hardware fingerprint of the machine that created them. Removing an entry from one copy of the vault does **not** affect other copies – but the user can propagate the change by copying the updated vault file.

This provides a **decentralised, offline‑first device revocation mechanism**.

---

### 28. Missing Vault Detection and Active Cache Validation

The `SessionKeyVault` (a transparent dict‑like cache) validates the existence of the underlying vault file **before every cache hit**:

```python
if notebook_id in self._cache:
    vault_path = self.manager._get_vault_path(notebook_id)
    if vault_path and os.path.exists(vault_path):
        return self._cache[notebook_id]
    else:
        del self._cache[notebook_id]   # invalidate immediately
```

If the vault file is missing (USB unplugged, network share unmounted, file deleted), the cached entry is deleted instantly. Subsequent accesses will either fail cleanly (“missing vault”) or trigger a recovery flow (prompt for phrase).

During key resolution (when the cache is empty or invalidated), the system explicitly checks for the vault file. If it is missing, it presents a user dialog with options:
1. Retry (after inserting the missing device)
2. Locate the vault file manually (update the registry)
3. Use the recovery phrase (will create a new vault entry)
4. Cancel

This ensures that **no operation can use stale keys** and that the system can recover gracefully from component loss.

---

### 29. Docker / Cloud Ephemeral Fingerprinting

Because the hardware fingerprint is derived at runtime from the execution environment, the same code can run inside a Docker container or a cloud VM. The container’s fingerprint is based on its container ID, network stack, hostname, and other ephemeral identifiers.

When the container is destroyed, the fingerprint is lost. Any vault entries that were created for that container become undecryptable – even if the container image is re‑started later. This makes the system suitable for **ephemeral, stateless workloads** in the cloud.

Users can:
- Run the application in a Docker container on any cloud provider
- Store the vault file on a separate network share or object storage (e.g., S3)
- Store the notebook data in a public Git repository or on another volume

The three components (app, vault, notebook) can reside on three different cloud services. The system resolves the vault URL via the vault registry, fetches it over HTTPS, decrypts the entry using the container’s runtime fingerprint, and performs the operation – all without trusting the cloud provider.

---

### 30. O(1) Deterministic UUID Chains and Multiple‑Origin Coordination

The system does not use a central database, a transaction manager, or a background orchestrator. Instead, every operation is performed by following **multiple independent UUID resolution chains** that start from different origins:

- **Chain A** – resolves the notebook folder path (from the master registry)
- **Chain B** – resolves the decryption keys (master registry → vault name → vault registry → vault file → entry UUID → hardware fingerprint decryption)
- **Chain C** – prepares Git metadata (UUIDs, change statistics)

These chains execute sequentially (or in parallel when independent) and converge only at the final write (for create/edit/delete) or display (for search/timeline/activity). Each step is an O(1) dictionary lookup or a fixed cryptographic operation. The number of steps is constant, regardless of the total number of notebooks, notes, or trusted devices.

The resolution chain can cross network boundaries (vault file on S3, notebook folder on a network drive, Git remote on GitHub) without changing its complexity.

This architecture is **stateless**: after each operation, all transient state is discarded. The system has no long‑running memory.

---

### 31. Deterministic UUID‑Level Synchronisation (Item‑Level Git Sync)

The system includes a synchronisation mechanism that operates entirely at the UUID level, without relying on Git’s native merge or rebase. The algorithm is deterministic, merge‑free, and requires no user knowledge of Git.

**Core principle:** Each commit changes exactly one UUID. The system groups commits by UUID, forming per‑item chains. For each UUID present on both local and remote, it compares the timestamp of the last commit in each chain and keeps the chain with the newer timestamp. UUIDs present on only one side are kept entirely.

**Commit collection:** For each branch (`HEAD` and `origin/master`), the system runs `git rev-list --no-merges` to get all commit hashes. For each commit, it extracts the UUID from the commit message, the raw encrypted blobs of the three JSON files, and the timestamp, author, and message.

**Grouping by UUID:** All collected commits are grouped by UUID using a dictionary mapping `uuid → list of commits`. Because each commit changes exactly one UUID, the chains are disjoint.

**Conflict resolution:** For each UUID:
- If only one side has commits, keep that chain.
- If both sides have commits, compare the last commit timestamp. Keep the chain with the newer last commit; discard the other chain entirely.

**Cognitive alignment:** For a single user across multiple devices, the mental model is “the latest version is the one I want”. The timestamp rule implements this directly. Non‑conflicting edits (different UUIDs) are always preserved.

**Merging and sorting:** All winning commits (from all UUIDs) are collected and sorted by their original timestamp (ascending). This produces a linear sequence independent of branch topology.

**History reconstruction:** A new orphan branch is created. Encryption marker files (`.tn_test`, `.tn_recovery`, `.tn_password`) are restored. If a common ancestor exists, its state is restored. Then, for each commit in sorted order:
- Write the raw encrypted blobs to the working tree.
- Stage the files.
- Commit with the original author, timestamp, and message (using `GIT_AUTHOR_DATE` and `GIT_COMMITTER_DATE`).

**Replace branch and push:** The original branch is reset to the reconstructed branch and force‑pushed to the remote. The result is a linear, merge‑commit‑free history containing all winning commits from both sides, ordered by their original timestamps.

**No common ancestor (filter‑repo case):** When `git merge-base` returns nothing (histories completely unrelated), the system falls back to comparing timestamps and commit counts. The side with the newer timestamp (or more commits if timestamps are equal) wins, and the other side is replaced.

**Free encrypted sync via any Git remote:** Because the synchronisation uses standard Git remotes, encrypted notebook data can be pushed to any Git hosting platform (GitHub, GitLab, Bitbucket, self‑hosted) without exposing content. No separate sync service, subscription, or proprietary cloud is required.

**Observable behaviour:**
- No merge commits ever appear.
- History is linear after every sync.
- Conflicts are resolved automatically; user only sees a confirmation prompt.
- Encrypted blobs remain encrypted; the sync engine never decrypts them.
- Marker files (`.tn_*`) are preserved.
- Subnotebook hierarchies are recursively merged.

---

### 32. Eternal License

The entire system is released under the **Eternal License**, which explicitly:

- **Prohibits patenting** any concept disclosed in the repository or its documentation
- **Requires no attribution** (attribution is a courtesy, not a demand)
- **Allows** any use, modification, distribution, and building of commercial products
- **Forbids** asserting intellectual property rights over the disclosed ideas, removing or altering the license from the original source, and suing others for implementing the concepts

The license cites **35 U.S.C. § 102(a)(1)** (US) and **EPC Article 54(2)** (Europe), and references **EPO decision G 1/23 (2025)** which establishes that public availability alone is sufficient for prior art.

The license is not a contract; it is a philosophical statement encoded as text. It asserts that the technology belongs to no one.

---

### 33. Prior Art Assertion

I, **sys_ronin**, do hereby establish this document and the accompanying source code repository as prior art under **35 U.S.C. § 102(a)(1)** (United States) and **Articles 54 & 56 of the European Patent Convention (EPC)**.

- **Date of public disclosure:** February 2026 (initial), May 2026 (updated)
- **Mode of disclosure:** public GitHub repository
- **Status:** irrevocable and unwithdrawable

All concepts, implementations, combinations, adaptations, and variations disclosed herein are now and forever part of the public domain.

**No party may:**
- Obtain valid patent claims covering any disclosed concept
- Enforce existing patents against implementations of these concepts
- Assert trade secret protection over any disclosed implementation
- Claim exclusive rights to any combination herein disclosed
- Patent any adaptation or variation that preserves the disclosed cognitive patterns

### Human Cognition as Prior Art

The patterns this system implements are **not inventions**; they are observations of how human cognition already works. A system that implements human cognitive patterns cannot be patented as novel or non‑obvious. The patterns pre‑exist in every human brain. The implementation merely reflects them.

Any future system that preserves these patterns – spatial indexing, temporal recall, working memory limits, recognition over recall, affordance perception, cognitive disappearance, embodied interaction, flow state, errorless learning, zero background processing – practices what is disclosed herein.

This is not a claim of invention. This is an observation of what already exists. The system is not the invention; human cognition is the invention. This system merely implements it.

### Verification

- **Repository:** [https://github.com/sys-ronin/terminal-notes](https://github.com/sys-ronin/terminal-notes)
- **First commit:** February 2026
- **Main prior art** `prior_art_terminal_notes.md`
- **Documents:** `/documents`, `README.md`, `LICENSE`
- **Source code:** all Python files in the repository

All content is public and freely accessible. No confidentiality obligations apply. No embargo period was observed.

---

### 34. Integrated System

The above 33 layers function as an integrated whole. Each layer depends on and serves the layers above. All layers serve the user’s experience of disappearance.

This specific combination constitutes a novel, non‑obvious, and fully disclosed system for human‑computer interaction that mirrors human cognitive patterns. The system is not a collection of features; it is a coherent architecture where each component enables the next.

The UUID permanence enables the three‑JSON architecture. The three‑JSON architecture enables Git as an item‑level temporal database. Git enables resurrection, timeline, activity, and the sync algorithm. The sync algorithm enables cross‑device work without conflict. The encryption architecture (hardware‑bound keys, portable vault, recovery phrase) enables zero‑trust portability – notebooks can be stored anywhere, vaults can be moved, and only the user can decrypt. The cognitive UI makes all of this invisible to the user.

The system was not designed from theory. It emerged from constraints: a single user who could not afford to forget, a tiny laptop, no external monitor, no team, no funding. The alignment with cognitive science was discovered afterward. The code came first. The realisation came later.

**The interface disappears. Only the writing remains. That is the entire point.**

---

**End of Prior Art Disclosure**

*This document is a statement of fact, not a legal opinion. No legal advice is offered. No warranty is provided.*
