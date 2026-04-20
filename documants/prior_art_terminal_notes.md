===============================================================================
                          PRIOR ART DISCLOSURE
                      Terminal Notes Integrated System
                           (COMPREHENSIVE)
===============================================================================

------------------------------------------------------------------------------
                          DEFENSIVE PUBLICATION
------------------------------------------------------------------------------

===============================================================================
                                SUMMARY
===============================================================================

Date of publication: February 2026 (initial), April 2026 (updated)
Repository: https://github.com/sys-ronin/terminal-notes
Status: Public, irrevocable, timestamped

This document establishes prior art for the complete integrated system described herein.
All concepts, implementations, combinations, and future adaptations disclosed are now part of the public domain.

No party may patent these concepts. No party may claim exclusive rights.
This is not a request. This is a statement of fact.

===============================================================================
                            DISCLOSED CONCEPTS
===============================================================================

------------------------------------------------------------------------------
1. UUID PERMANENCE (ITEM IDENTITY)
------------------------------------------------------------------------------

Every item (note, notebook, file, subnotebook) receives a UUID at creation.
UUID is never changed throughout the item's lifetime. It survives:
- Rename operations
- Move operations between notebooks
- Deletion and resurrection from history
- Export and re-import across machines
- Git commit history (every commit references UUID)
- Platform migration (Linux, macOS, Windows)
- Hard erase (UUID persists in commit history until purged via git-filter-repo)

UUIDs enable:
- Item tracking across time
- Resurrection of deleted items
- Timeline reconstruction
- Activity aggregation
- Cross-notebook reference integrity
- Recovery after crashes
- O(1) dictionary lookups in memory
- Deterministic navigation through parent-child relationships

UUID format: timestamp-based (YYYYMMDDHHMMSS) for simple items, RFC 4122 UUID4 for complex.
All operations use UUID as primary key, never name or path.

------------------------------------------------------------------------------
2. INFINITE NESTED SUBNOTEBOOKS WITH FULL CONTENT
------------------------------------------------------------------------------

Notebooks can contain unlimited nested subnotebooks, forming arbitrary depth hierarchies.
Each subnotebook is a full notebook object with its own UUID, name, parent ID reference,
notes collection, and subnotebooks collection (recursive).

Content inheritance:
- Notes in subnotebooks are stored in parent's notes.json/files.json
- Full content of entire hierarchy is accessible from root
- No depth limit - recursion handles any nesting level
- Search traverses entire tree automatically
- Activity view aggregates changes across entire hierarchy

The tree structure enables project organization, hierarchical categorization,
unlimited depth without performance degradation, independent versioning,
and selective restoration of branches.

------------------------------------------------------------------------------
3. NOTEBOOK REGISTRY & PORTABILITY
------------------------------------------------------------------------------

Central registry (notebooks_registry.json) maps notebook UUID → filesystem path.
Registry entries for encrypted notebooks are themselves encrypted with the notebook's key.

Notebooks can live in any location:
- Default directory (notebooks_root/)
- Custom user-specified paths
- External drives, network shares, Docker volumes, cloud-synced folders
- USB drives (portable)

Path handling:
- Paths stored relative to notebooks_root when possible
- Absolute paths preserved for external locations
- Cross-platform normalization prevents duplicate detection failures
- Missing paths detected and flagged during load

Custom paths persist in structure.json within each notebook.
Notebooks are self-contained and can be moved manually.
Re-import detects existing paths and prevents duplicates.

------------------------------------------------------------------------------
4. NOTEBOOK MANAGER WITH GIT ACCOUNT INTEGRATION
------------------------------------------------------------------------------

Centralized manager for all notebooks with Git account integration:

Account system:
- Encrypted storage of Git credentials using zero-trust binary vault
- Supports multiple platforms: GitHub, GitLab, Bitbucket, self-hosted Gitea
- Account ID generated from username@host
- Per-notebook repository configuration
- Multiple entries per account (one per trusted machine)

Repository management:
- Link notebook to Git repository
- Create repository on first push
- Push with authentication via stored token
- Pull updates for listed notebooks
- Change visibility (public/private)
- Delete remote repository
- Test connection with timeout and retry
- Change remote account and repository

Parallel operations:
- Multi-threaded repository scanning with connection pooling
- DNS caching for performance
- Timeout handling with retry logic
- Progress indicators for batch operations

Notebook discovery:
- Scan accounts for Terminal Notes repositories
- Detect encryption status remotely
- Parse structure.json to extract metadata without cloning
- Show counts (notes, files, subs) remotely
- Link existing notebooks to accounts

This creates a complete notebook lifecycle management system integrated with Git hosting platforms.

------------------------------------------------------------------------------
5. THREE-FILE ATOMIC ARCHITECTURE
------------------------------------------------------------------------------

Each notebook is a self-contained directory with exactly three JSON files:

structure.json
    Contains hierarchy only. No content.
    Stores: UUIDs, names, parent-child relationships, custom_path.
    Enables tree navigation without loading content.
    Small size allows fast loading even with thousands of notes.

notes.json
    UUID → content mapping for regular text notes.
    Keys are UUIDs, values are plain text content.
    Human-readable, Git-diffable, searchable.

files.json
    UUID → content mapping for file notes (80+ extensions).
    Keys are UUIDs, values are file content.
    Extensions stored in structure.json for syntax highlighting.
    Enables extension-based search.

Write operations are atomic:
    1. Write to .tmp file
    2. fsync() to force disk flush
    3. rename() atomic operation
    4. Original file replaced only on success

Crash recovery is inherent:
    Partial writes affect only .tmp files
    .tmp files ignored on next startup
    No corruption possible

This separation enables:
- Resurrection (reconstruct items from history)
- Timeline (version history per item)
- Activity view (aggregated changes across hierarchy)
- Git efficiency (small deltas, meaningful diffs)
- Memory efficiency (load structure without content)

------------------------------------------------------------------------------
6. CUSTOM ENCRYPTION ARCHITECTURE (ZERO-TRUST, PORTABLE, HARDWARE-BOUND)
------------------------------------------------------------------------------

A novel encryption architecture that integrates seamlessly with all operations:

Key derivation (one-way, irreversible):
    Kp = SHA256(password + b':' + folder_name)     # password key
    Ks = SHA256(phrase + b':' + folder_name)       # phrase key (never changes)
    Kc = SHA256(Kp + Ks)                           # combined key

    Folder name is PART OF THE KEY. Renaming folder = permanent data loss.
    This creates a physical binding between key and storage location.

Three verification files per notebook:
    .tn_test        → "VERIFICATION" encrypted with Ks (phrase key)
    .tn_recovery    → password_key (Kp) encrypted with Ks
    .tn_password    → combined_key (Kc) encrypted with Kc (self-referential)

Encryption format:
    Magic header: b"TN_ENC" (6 bytes) prepended to all encrypted data
    Nonce: 12 random bytes per encryption
    Ciphertext: AES-GCM encrypted data with authentication tag

File structure:
    structure.json → fully encrypted (binary)
    notes.json → fully encrypted (binary)
    files.json → fully encrypted (binary)
    .tn_test → encrypted verification marker

Registry encryption:
    Notebook entries in registry are encrypted with notebook's key
    registry["notebooks"][notebook.id] = encrypted_hex_string
    Prevents metadata leakage about encrypted notebooks

Lock/Unlock mechanism (explicit memory manager):
    Locked: custom_path = None, session_key removed, keys cleared from RAM, shows 🔒
    Unlocked: custom_path restored, session_key present, shows 🔐
    Content inaccessible when locked
    Structure metadata (counts) still visible when locked

Autolock flag (per‑notebook):
    Stored in registry entry as boolean `autolock`.
    When enabled, the notebook is forced into locked state on every application startup,
    regardless of its previous lock state. Encryption keys are cleared from memory.
    User can toggle via change options menu.
    Useful for shared computers or sensitive notebooks.

Password change (instant, no re-encryption):
    Only .tn_recovery and .tn_password are updated
    Ks (phrase key) never changes
    Notebook content remains encrypted with Ks

Cross-machine synchronization:
    Each trusted machine adds its own entry in session.vault
    Entry encrypted with SHA256(timestamp + machine fingerprint)
    Fingerprint never stored - derived at runtime
    New machine requires phrase once, then password only
    Old entries remain for other machines

------------------------------------------------------------------------------
7. ZERO-TRUST BINARY VAULT (SESSION STORAGE)
------------------------------------------------------------------------------

Keys are stored in a portable, tamper-evident binary vault (session.vault):

Vault format (version 4):
    [4 bytes] version
    For each notebook:
        [4 bytes] id_length
        [variable] notebook_id (UTF-8, plain for lookup)
        [4 bytes] num_entries
        For each entry (one per trusted machine):
            [8 bytes] timestamp
            [12 bytes] nonce
            [4 bytes] encrypted_keys_length
            [variable] encrypted_keys (AES-GCM)
            [1 byte] active_flag (O(1) lookup)
            [8 bytes] created_timestamp

Key derivation for each entry:
    encryption_key = SHA256(timestamp + current_fingerprint)
    Fingerprint is derived from hardware at runtime, NEVER stored

Active flag:
    Indicates which entry belongs to current machine
    Enables O(1) lookup without trial decryption
    Falls back to trial decryption if flag is wrong

System fingerprint generation (runtime only, never stored):
    - Linux: /etc/machine-id, product_uuid, CPU info
    - macOS: IOPlatformUUID, hardware UUID, serial number
    - Windows: MachineGUID, ComputerName, SID
    - Fallback: hostname, username, platform info, file paths

Properties:
    - No outer encryption (vault is open binary)
    - No fingerprint stored anywhere
    - Tamper-evident (any change breaks decryption)
    - Portable (copy vault between machines)
    - Multi-machine (one entry per trusted machine)
    - Zero-trust (vault contains no machine identifiers)

------------------------------------------------------------------------------
8. UNIVERSAL JSON HANDLER WITH AUTOMATIC CRYPTO
------------------------------------------------------------------------------

Single unified handler for all JSON operations across entire application:

read_json(filepath, crypto=None)
    Reads ANY JSON file from disk
    Automatically decrypts if crypto provided
    Returns parsed dict or None on failure

write_json(filepath, data, crypto=None)
    Writes ANY JSON file with atomic pattern
    Encrypts automatically if crypto provided
    Guarantees no partial writes

read_bytes(raw_bytes, crypto=None)
    Reads JSON from bytes (git show output)
    Decrypts if crypto provided

_parse_json(raw, crypto)
    SINGLE POINT where decryption happens
    Every JSON read passes through here
    Try decryption first, fallback to plain text

All operations (load, save, merge, filter) use these handlers.
Encryption is invisible. Callers just pass crypto when available.
The entire application is encryption-aware without knowing it.

------------------------------------------------------------------------------
9. GIT AS ITEM-LEVEL TEMPORAL DATABASE
------------------------------------------------------------------------------

Every state change is committed to Git automatically.
Git repository lives inside each root notebook directory.

Each commit message follows strict format:

    type: ACTION CONTENT_TYPE: title | context

    Metadata description (change statistics, etc.)

    Metadata: uuid:ITEM_UUID | parent:PARENT_UUID | root:ROOT_UUID

Actions:
- CREATED    → item creation (with total character count)
- UPDATED    → content edit (with added/removed character counts +X/-Y)
- EDITED     → synonym for UPDATED
- RENAMED    → title change (shows old → new)
- DELETED    → removal from current view
- RESTORED   → resurrection from history
- ERASED     → permanent removal (tombstone commit)

Content types:
- NOTE, FILE, NOTEBOOK, SUBNOTEBOOK

Complete item history is queryable via:

    git log --grep uuid:<UUID> --all

Item-level searching:
    Find all commits affecting a specific UUID
    Track item across renames, moves, deletions
    Reconstruct state at any point in time
    Aggregate activity across all items
    Search deleted items (deleted*)
    Search renamed items (renamed*)
    Search restored items (restored*)
    Search erased items (erased*)

This enables Git to function as a true item-level temporal database,
not just a file-level version control system.

------------------------------------------------------------------------------
10. GIT RESURRECTION ENGINE
------------------------------------------------------------------------------

Centralized engine for all historical item operations:

find_deleted_items(query)
    Finds all deleted items matching query
    Uses git log --grep "^type: DELETED"
    Extracts UUID from commit metadata
    Reconstructs item from commit BEFORE deletion

find_renamed_items(query)
    Finds all renamed items matching query
    Uses git log --grep "^type: RENAMED"
    Extracts old and new names from commit
    Reconstructs item from commit BEFORE rename

find_restored_items(query)
    Finds all restored items matching query
    Uses git log --grep "^type: RESTORED"
    Returns reconstructed items from restore commits

find_erased_items(query)
    Finds all permanently erased items (tombstones)
    Uses git log --grep "^type: ERASED"
    Returns minimal metadata (title, UUID, parent)
    Content unavailable (permanently removed)

_create_temp_json_for_item(uuid, commit_hash)
    Core reconstruction function
    Extracts structure.json at specific commit
    Finds item by UUID in historical structure
    Creates minimal hierarchy containing just that item
    Extracts content from notes.json/files.json
    Returns dict with temp_dir containing reconstructed files

display_resurrected_item(result_data, ui)
    Unified display for any resurrected item
    Detects type (note/file/subnotebook)
    Uses appropriate viewer with full pagination
    Includes [R]estore button

_restore_item(result_data, ui)
    Restores item to original location
    Finds parent UUID from commit metadata
    Merges content into live notes.json/files.json
    Updates structure.json with item
    Commits restoration with metadata
    Refreshes search results automatically

The resurrection engine is the single source of truth for all historical operations.
Timeline, activity, search all delegate to it.

------------------------------------------------------------------------------
11. TIMELINE ENGINE
------------------------------------------------------------------------------

Specialized engine for item version history:

get_item_timeline(uuid, notebook_id, crypto)
    Gets all commits mentioning specific UUID
    Returns list of version metadata (commit_hash, date, message)

create_version_at_commit(uuid, commit_hash, crypto)
    Reconstructs item at specific commit
    Delegates to resurrection engine
    Returns full version data with temp_dir

Timeline display:
    Shows versions with dates and actions
    CREATED: shows total characters
    UPDATED: shows change stats (+X/-Y)
    RENAMED: shows old → new
    DELETED/ERASED: just action

Viewing a version:
    Calls create_version_at_commit
    Displays using resurrection engine's viewers
    Read-only mode, export available for files

Timeline is separate from search and activity:
    Search: finds items across time
    Activity: shows recent changes across items
    Timeline: shows one item's complete history
    All use same underlying git database

------------------------------------------------------------------------------
12. CUSTOM QUERY PARSER FOR PINPOINT SEARCHING
------------------------------------------------------------------------------

Order-independent token recognition with single positional constraint:

Query format (any order except in*):
    s [action*] [type*] [date*] [time*] [g*] [text] [in* notebook]

Action filters (wildcard required):
    created*, deleted*, edited*, updated*, renamed*, restored*, erased*

Type filters (wildcard required):
    note*, file*, sub*, notebook*

Date filter (wildcard required):
    date* DD-MM-YYYY [DD-MM-YYYY]  → single day or range

Time shortcuts (wildcard required):
    today*, yesterday*, thisweek*, lastweek*

Scope (MUST be at end):
    in* notebook_name  → search in notebook and all descendants

Global override (anywhere):
    g*  → forces global search, ignores context

Text query:
    Remaining words → substring search across titles/content, case-insensitive, AND logic

Parser behavior:
    - Filters can appear in ANY sequence (except in* at end)
    - Recognized tokens removed from query
    - Remaining tokens become text search
    - Single pass, no lookahead except date ranges

Intent-based display:
    With action wildcard → NO action prefix in results
    Without action wildcard → SHOW action prefix in results

Examples:
    s created* file* meeting in* work          → created files with "meeting" in work
    s meeting file* created* in* work          → same result (order independent)
    s deleted* yesterday* report               → items deleted yesterday with "report"
    s g* config in* work                       → global search for "config" (ignores work)
    s date* 15-03-2026 20-03-2026 python       → items with "python" in date range
    s thisweek* important                      → items from this week with "important"
    s renamed*                                 → find all renamed items
    s erased*                                  → find all permanently erased items

This enables precise, natural language-like queries without complex syntax.

------------------------------------------------------------------------------
13. UNIFIED SEARCH ENGINE
------------------------------------------------------------------------------

Single search interface finds all items regardless of state.

Search processor:
    Resolves target notebooks (context, in* scope, or all)
    Parses query using custom query parser
    Collects current items via simple_search (title/content)
    Collects historical items via resurrection engine for ALL action types
    Deduplicates by UUID
    Applies type/action/date filters
    Sorts by date (newest first)
    Limits to 50 results

Intent-based display:
    With action wildcard (created*): NO action prefix
        "file.txt [work]"
    Without action wildcard: SHOW action prefix
        "created file: file.txt [work]"
        "updated note: notes.txt (+15/-23) [work]"
        "deleted note: old.txt [work]"
        "renamed note: todo → tasks [work]"

Result formatting:
    Current notes/files: show type, title, location
    Current notebooks: show name, counts (n/f/s), lock status
    Historical items: show action, title, original location
    Renamed items: show old → new
    All items show location in brackets using smart path (relative to context)

This creates a search experience that understands intent,
shows appropriate context, never hides history, and adapts to the user.

------------------------------------------------------------------------------
14. RELATIVE ANCESTOR NAVIGATION (FISH-EYE)
------------------------------------------------------------------------------

Navigation is based on relative position, not absolute paths.

Navigation stack (single unified stack):
    Simple list of {'screen': str, 'id': str, 'page': int}
    Push, pop, replace_page, clear operations
    No forward button - never needed

Jump history:
    Save current position before jumping
    Maximum 20 entries (FIFO)
    jb command returns to previous position (temporal navigation)

Fish-eye path display:
    Full hierarchy truncated to terminal width
    Algorithm maintains 4-7 visible segments (Miller's Law)
    Left ellipsis (...) for truncated ancestors
    Right ellipsis for truncated descendants
    Result: ...[2]LEVEL3/[3]LEVEL4/[4]LEVEL5/[5]LEVEL6/

Number mapping:
    Each visible segment gets relative number
    Numbers reset per screen, independent of absolute depth

Jump command: j<number>
    Looks up UUID by relative number
    If target in current stack: truncate stack
    If target not in stack: rebuild full path by walking parent chain
    Jump history saved automatically
    O(1) lookup, O(d) path reconstruction where d ≤ 10

Back command: b
    Pops the navigation stack
    Returns to exact previous state (same screen, same notebook, same page)

This enables navigation by position, constant cognitive load,
muscle memory development, no path memorization required,
and no forward button because forward is never needed.

------------------------------------------------------------------------------
15. ACTIVITY VIEW (TEMPORAL AGGREGATION)
------------------------------------------------------------------------------

Activity view shows changes across time with hierarchical context.

Collection:
    For notebook mode: collects all UUIDs in hierarchy (notebook + all descendants)
    Uses git log --grep with UUID pattern (OR of all UUIDs)
    Also fetches DELETED commits that might lack UUID
    Results limited to 50, sorted newest first

Hierarchical path calculation:
    Determines where item sits relative to viewing notebook
    Shows relative path from viewing point
    Examples (viewing notebook "work"):
        Item in "work/notes" → "notes"
        Item in "work/projects/client/docs" → ".../projects/client/docs"
        Item in "work" itself → "work"

Display format:
    [1] created note: meeting-notes (+245) [work/notes]
    [2] updated file: config.py (+15/-23) [work/projects]
    [3] renamed note: todo → tasks [work]
    [4] deleted sub: old-project [.../archived]

Security activity view (password change history):
    Specialized subset of activity view showing only SECURITY commits.
    Queries git log with --grep "SECURITY:" and --grep "root: {uuid}".
    Displays entries as: date | method (old_password/recovery_phrase) | machine (hostname).
    Button appears progressively only after first password change.
    Uses same pagination and navigation as main activity view.

Character stats:
    CREATED: total characters
    UPDATED: added/removed characters (+X/-Y)
    RENAMED: shows old → new
    DELETED/ERASED: no stats

Activity is history made visible — not a log, but a narrative.

------------------------------------------------------------------------------
16. COMPLETE HIERARCHY RESURRECTION
------------------------------------------------------------------------------

Any item, at any point in its history, can be resurrected.

Resurrection process:
    1. User finds item via search (deleted* filter) or activity view
    2. Views item (shows historical state)
    3. Presses [R]estore

Restoration logic:
    Extracts parent UUID from commit metadata
    If parent exists: restore to original location
    If parent missing: prompt for destination
    Uses resurrection engine's _restore_item

For notes/files:
    Content merged into live notes.json/files.json (UUID-keyed)
    Structure.json updated to include item in parent's notes[]
    Git commit: "RESTORED NOTE: title | to location"

For subnotebooks:
    Recursively collects all UUIDs in hierarchy
    Merges ALL content (all notes and files) into live files
    Updates structure.json with complete hierarchy
    Git commit: "RESTORED SUBNOTEBOOK: name | to location (X notes, Y subs)"

Safety:
    Original location preferred (maintains hierarchy)
    Duplicate detection prevents conflicts
    UUID unchanged (temporal continuity preserved)
    Content merged, not overwritten

Restoration works for deleted notes/files, deleted subnotebooks (with all contents),
renamed items, and items from any point in timeline.

------------------------------------------------------------------------------
17. GIT-FILTER-REPO AS EMBEDDED MODULE WITH CUSTOM FILTERS
------------------------------------------------------------------------------

git-filter-repo is not called as a subprocess. It is dynamically loaded as a Python module:

    filter_repo_path = os.path.join(os.path.dirname(__file__), "git_filter_repo.py")
    spec = importlib.util.spec_from_file_location("git_filter_repo", filter_repo_path)
    git_filter_repo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(git_filter_repo)

The module is modified with an `if __name__ == '__main__'` guard, enabling import without execution.
This transforms a command-line tool into a proper Python library.

Custom filter classes extend the base RepoFilter:

UUIDEraseFilter
    - Removes all commits containing a specific UUID
    - Scans commit messages for UUID pattern
    - Removes UUID from blob contents
    - Tracks commits_removed and blobs_removed
    - Preserves ERASED tombstone commits

NotebookEraseFilter
    - Removes entire notebook hierarchies in one pass
    - Takes notebook UUID and list of all descendant UUIDs
    - Scans for root:NOTEBOOK_UUID pattern
    - Removes all commits containing any UUID in the notebook

Command-line integration:
    --uuid-erase UUID
    --notebook-erase NOTEBOOK_UUID:UUID1,UUID2,...

Safety features:
    - Never runs on project root
    - FILTER_REPO_AVAILABLE flag for graceful fallback
    - Repository validation before operations
    - Atomic operations with rollback

This enables programmatic history rewriting, exception handling,
integration into applications, and batch operations impossible with CLI tools.

------------------------------------------------------------------------------
18. PERMANENT ERASURE WITH GIT-FILTER-REPO
------------------------------------------------------------------------------

Two-tier deletion system:

Soft delete (default):
    Removes from current view only
    History preserved in Git
    Item findable via deleted* search
    Restorable at any time
    Git commit: "DELETED NOTE: title"

Hard erase (permanent):
    Removes from Git history completely
    Uses git-filter-repo custom filters
    Creates tombstone commit marking erasure
    Not recoverable
    Git commit: "ERASED NOTE: title (tombstone)"

Erasure process for single item:
    1. Identify all commits containing UUID
    2. Run UUIDEraseFilter to remove UUID from all files
    3. Remove from current view
    4. Create tombstone commit
    5. Git garbage collection

Erasure process for entire notebook:
    1. Collect ALL UUIDs in notebook hierarchy
    2. Run NotebookEraseFilter with all UUIDs
    3. Remove registry entry
    4. Delete session keys
    5. Delete notebook folder
    6. Git garbage collection

Safety features:
    Confirmation required ("type 'erase' to confirm")
    Never runs on project root
    FILTER_REPO_AVAILABLE flag for fallback
    Atomic operations with rollback

GDPR compliance:
    Complete removal of personal data
    Audit trail via tombstones
    Configurable per request
    Can erase entire notebooks

This is the only operation that breaks UUID continuity.

------------------------------------------------------------------------------
19. CRASH RECOVERY WITH UUID KEYING
------------------------------------------------------------------------------

External editor sessions are protected against crashes.

Recovery system:
    Directory: .recovery/ in application root
    Files named: {title}_{uuid[-6:]}.{ext}
    UUID suffix ensures uniqueness across renames

Autosave:
    Background thread monitors temp file
    Every 30 seconds, saves content to recovery file
    Continues until editor closed
    UUID keying preserves identity

Recovery on access:
    When notebook opened, check for recovery files
    For each file matching notebook UUIDs:
        Compare recovery timestamp with note.updated
        If recovery newer: content was never saved
        Restore content to note
        Commit to Git with edit message
        Delete recovery file

Recovery scenarios:
    Editor crash, system crash, application crash, power failure
    Recovery file persists until successfully merged

UUID keying ensures:
    Recovery files map to correct notes
    Survives renames (UUID unchanged)
    Survives moves between notebooks (UUID unchanged)
    No cross-notebook contamination

------------------------------------------------------------------------------
20. CONFIGURABLE EDITOR SYSTEM
------------------------------------------------------------------------------

Users can choose their preferred editor for writing and viewing.

Configuration file (config.json):
    {
        "edit": "micro",
        "view": "micro",
        "info": "Available editors: micro, nvim, vim, helix, hx, emacs -nw, nano, kate, geany, gedit, pluma, mousepad, leafpad, mg, jed, joe"
    }

Editor resolution:
    First launch creates config.json with defaults
    User can edit manually, changes take effect immediately
    No settings screen - configuration is an action, not a persistent UI element

Editor selection:
    edit: editor for writing/modifying notes
    view: editor for viewing (read-only mode)

Editor detection:
    Tests if editor exists in PATH
    Falls back to next available in list
    Ensures at least one editor works

Special handling:
    nvim, vim, emacs: inject autosave commands/configuration
    Other editors: launch normally

External editor invocation:
    Temporary file with correct extension
    Editor launched with appropriate mode (read-only if view)
    Content read back after editor closes
    Recovery thread monitors during editing

------------------------------------------------------------------------------
21. DATA-AS-UI (ZERO LEARNING CURVE)
------------------------------------------------------------------------------

The interface is the data. The data is the interface.

Numbered items:
    Every displayed item has a number
    [1] Note title, [2] Subnotebook name, [3] Search result, [4] Activity entry

Numbered commands:
    v1 → view item 1, d2 → delete item 2, r3 → rename item 3, j4 → jump to position 4

Path numbering:
    [1]root/[2]child/[3]grandchild/
    j2 → jump to position 2 (child)

Footer options:
    [C]reate  [V]iew  [S]earch  [D]elete  [B]ack  [Q]uit
    Each is a single keystroke

No menus, no toolbars, no context menus, no modal dialogs (except confirmations)
No modes - same commands work everywhere
No settings screen - configuration dissolves into necessity

Cognitive principles:
    Recognition over recall (users see options)
    Affordance (numbers invite pressing)
    Consistency (same commands everywhere)
    Discoverability (footer shows all options)
    Progressive disclosure (buttons appear only when useful)

The data IS the interface:
    Notebook list → [1] Project [2] Work [3] Personal
    Note list → [1] Meeting [2] Todo [3] Ideas
    Search results → [1] file.txt [2] notes.md
    Activity → [1] created note [2] updated file

Numbers are not decoration. They are commands.
The interface teaches itself through use.
No learning curve. No tutorial. No documentation needed to start.

------------------------------------------------------------------------------
22. TERMINAL USER INTERFACE AS INTEGRAL COMPONENT
------------------------------------------------------------------------------

The terminal user interface is not a separate component. It is the visible manifestation of the integrated logic chain described above.

Every element of the TUI is a direct expression of the underlying architecture:

Navigation:
    Numbered lists are the navigation layer made visible
    Path display is the fish-eye algorithm rendered
    j3 command is relative navigation in action
    No forward button because stack is transparent

Search:
    s query is unified search at work
    Results show action/type based on query intent
    Location brackets show smart path (relative to context)

History:
    t command is timeline reconstruction
    a command is activity aggregation
    v command on historical item shows resurrected state

Operations:
    d with confirmation is soft delete
    d + 'erase' is hard delete with filter-repo
    r is rename (UUID preserved)
    x is export (for files)

Navigation controls:
    b command is stack navigation (pop)
    jb is jump back through history (temporal return)
    Page indicators respect working memory limits

Visual elements:
    Header format maintains cognitive consistency
    Footer options reflect available operations (contextual)
    Lock icons (🔐/🔒) show encryption state
    Character stats (+245/-89) show edit magnitude

The TUI cannot be separated from the invention. It is the invention, made visible.
The interface disappears. Only the writing remains.

------------------------------------------------------------------------------
23. CROSS-PLATFORM ADAPTATIONS (FUTURE IMPLEMENTATIONS)
------------------------------------------------------------------------------

The invention is platform-independent. The following adaptations are disclosed as embodiments of the same integrated system:

WEB ADAPTATION
------------------------------------------------------------------------------
- Relative navigation via numbered elements (clickable)
- Unified search across all states with type/action filters
- Activity view for temporal aggregation
- Timeline for version history
- Resurrection with confirmation dialog
- Permanent erasure with admin confirmation
- Data-as-UI with all displayed items actionable
- Fish-eye path display adapted to browser width
- Stack-based navigation with browser history integration
- UUID permanence maintained across sessions
- Git temporal database accessible via API layer
- Encryption via Web Crypto API (same AES-GCM)
- System fingerprint via browser fingerprinting (fallback to localStorage)

DESKTOP NATIVE ADAPTATION
------------------------------------------------------------------------------
- Keyboard-driven navigation with numbered access
- Unified search across all states
- Activity view as native window
- Timeline interface for version history
- Resurrection with native dialog
- Permanent erasure with system-level confirmation
- Fish-eye path display optimized for window width
- Crash recovery with native file system integration
- External editor spawning with syntax highlighting
- Configurable editor via native preferences
- System fingerprint via hardware IDs (same as terminal version)

MOBILE ADAPTATION
------------------------------------------------------------------------------
- Spatial navigation via numbered gestures or taps
- Unified search with touch-friendly filters
- Activity view as scrollable timeline
- Timeline view for version history
- Resurrection with swipe gestures
- Fish-eye path display adapted to screen width
- UUID permanence via local storage
- Git temporal database via local storage or API
- Crash recovery with mobile background processing
- Biometric unlock for encrypted notebooks

FUTURE PLATFORM ADAPTATIONS
------------------------------------------------------------------------------
Any future platform that implements:
- Relative spatial navigation to hierarchical data
- Unified search across all states (current, deleted, renamed)
- Activity view for temporal aggregation
- Timeline interface for version history
- Resurrection capability for any deleted item
- Permanent erasure with confirmation
- Data-as-UI with actionable displayed elements
- Fish-eye or adaptive path display
- UUID-based permanent item identity
- Git-based temporal queryability
- Crash recovery with key-based restoration
- Transparent encryption with system-bound keys

...practices the invention disclosed herein. The specific implementation may adapt to platform constraints, but the cognitive patterns and integrated logic chain remain the property of this prior art.

------------------------------------------------------------------------------
24. COGNITIVE ALIGNMENT (EMERGENT PROPERTY)
------------------------------------------------------------------------------

The following properties emerge from the integrated system:

Spatial memory alignment
    Relative numbering matches Tversky's spatial mental models (1992).
    Users navigate by position, not path.
    j3 becomes reflex, not conscious decision.
    No forward button eliminates disorientation.

Temporal memory alignment
    Unified search across all states matches episodic recall.
    Activity view shows changes over time.
    Timeline shows evolution — separate but complementary.
    Users remember "before I deleted it" not timestamps.
    jb command provides temporal return to previous cognitive context.

Working memory alignment
    Fish-eye display (4-6 chunks) matches Miller's 7±2 (1956).
    Page indicators maintain orientation without overload.
    No forward button reduces decision count.

Cognitive load alignment
    Zero extraneous UI matches Sweller's load theory (1988).
    All attention is available for writing.
    No settings screen means no configuration decisions.

Recognition over recall
    Users recognize options in footer.
    Numbers invite pressing.
    Commands are discovered, not memorized.
    Every action is visible on current screen.

Affordance perception
    Numbered items afford "press number" (Gibson, 1979).
    Footer options afford "press letter".
    No training required. The interface teaches itself.

Cognitive disappearance
    When tool and thought align, the tool disappears.
    This system disappears. Only the writing remains.
    The user never thinks about the software.

Embodied cognition
    Commands migrate to muscle memory (Barsalou, 1999).
    j3 becomes reflex, not conscious decision.
    The body remembers what the mind forgets.

Flow state
    Uninterrupted writing enables flow (Csikszentmihlyi, 1990).
    No notifications, no interruptions, no modals.
    The system waits. The user writes.

Errorless learning
    Soft delete prevents permanent data loss from mistakes.
    Resurrection provides recovery from accidental deletion.
    Crash recovery ensures work is never lost.
    The user never experiences irreversible failure.

These theories were not consulted during development.
They were discovered afterward and are cited to explain observed behavior.
The system existed before the explanation.

------------------------------------------------------------------------------
25. ZERO BACKGROUND PROCESSES (COGNITIVE EFFICIENCY)
------------------------------------------------------------------------------

The system performs no work unless the user initiates an action:

- No background indexing threads
- No periodic cache refreshes
- No auto-save timers (only during active editing, and that thread dies when editor closes)
- No pre-loading of notebooks or notes
- No background sync processes

All operations—loading, decrypting, searching, committing—happen synchronously in response to user input.

Memory footprint:
    Locked notebooks: only registry entry (~200 bytes)
    Unlocked notebook structure: ~10KB per 100 notes
    Note content: loaded only when viewed
    Encryption keys: 32 bytes per unlocked notebook
    Timeline/activity results: limited to 50 items

Lock button as explicit memory manager:
    Unloads encryption keys from RAM
    Clears notebook structure (notes, subnotebooks)
    Removes content cache
    User controls what stays in memory
    Matches human cognitive model of working memory

This aligns with the brain's default mode network:
    The brain is most active and creative when at rest
    No constant background processing
    The system is present only when needed

------------------------------------------------------------------------------
26. INTEGRATED SYSTEM
------------------------------------------------------------------------------

The above twenty-six layers function as an integrated whole.
Each layer depends on and serves the layers above.
All layers serve the user's experience of disappearance.

This specific combination constitutes a novel, non-obvious, and fully disclosed system for human-computer interaction that mirrors human cognitive patterns.

===============================================================================
                            PRIOR ART ASSERTION
===============================================================================

I, sys_ronin, do hereby establish this document and the accompanying
source code repository as prior art under **35 U.S.C. § 102(a)(1)** 
and **Articles 54 & 56 of the European Patent Convention (EPC)**.

Date of public disclosure: February 2026 (initial), April 2026 (updated)
Mode of disclosure: Public GitHub repository
Status: Irrevocable and unwithdrawable

All concepts, implementations, combinations, adaptations, and variations disclosed herein are now and forever part of the public domain.

No party may:
- Obtain valid patent claims covering any disclosed concept
- Enforce existing patents against implementations of these concepts
- Assert trade secret protection over any disclosed implementation
- Claim exclusive rights to any combination herein disclosed
- Patent any adaptation or variation that preserves the disclosed cognitive patterns

------------------------------------------------------------------------------
                    HUMAN COGNITION AS PRIOR ART
------------------------------------------------------------------------------

The patterns this system implements are not inventions.
They are observations of how human cognition already works.

A system that implements human cognitive patterns
cannot be patented as novel or non-obvious.

The patterns pre-exist in every human brain.
The implementation merely reflects them.

Any future system that preserves these patterns
—spatial indexing, temporal recall, working memory limits,
recognition over recall, affordance perception,
cognitive disappearance, embodied interaction, flow state,
errorless learning, zero background processing—
practices what is disclosed herein.

This is not a claim of invention.
This is an observation of what already exists.

The system is not the invention.
Human cognition is the invention.
This system merely implements it.

------------------------------------------------------------------------------

All concepts, implementations, combinations, adaptations, and variations disclosed herein — including but not limited to those that reflect, implement, or are derived from the cognitive patterns described above — are now and forever part of the public domain.

No party may claim exclusive rights to any implementation that preserves these cognitive patterns, as the patterns themselves are not invented but observed.

This disclosure is made in the public interest.
It may be cited in any patent examination, litigation, or prior art search.

No legal advice is offered. No warranty is provided.
This document is a statement of fact, not a legal opinion.

===============================================================================
                            VERIFICATION
===============================================================================

Repository:    https://github.com/sys-ronin/terminal-notes
First commit:  April 2026
Documents:     prior_arts_terminal_notes.md (this document)
              /documents/*.*
              LICENSE
              README.md
Sourcecode:    source/*.*

All content is public and freely accessible.
No confidentiality obligations apply.
No embargo period was observed.

===============================================================================
END OF PRIOR ART DISCLOSURE
===============================================================================
