# Terminal Notes - Module Documentation

## Overview
Terminal Notes is a terminal-based, encrypted, Git-backed hierarchical note-taking system with dual-key encryption, per-machine vaults, and comprehensive search/history features.

---

## 1. `crypto.py`

**Responsibility:** Core encryption/decryption and key management

| Component | Description |
|-----------|-------------|
| `derive_key()` | Derives 32-byte key from secret + folder name using SHA256 |
| `combine_keys()` | Combines two 32-byte keys into one master key |
| `generate_phrase()` | Generates random BIP-39 style recovery phrase (8-24 words) |
| `validate_phrase()` | Validates a phrase against BIP-39 word list |
| `Crypto` class | Main encryption interface with dual-key support (password + phrase) |
| `encrypt()` / `decrypt()` | AES-GCM encryption/decryption with TN_ENC magic header |
| `create_recovery_file()` | Creates `.tn_recovery` file (password hash + key encrypted with phrase) |
| `create_password_file()` | Creates `.tn_password` file (combined_key self-encrypted for verification) |
| `create_test_marker()` | Creates `.tn_test` verification file |
| `retrieve_for_folder()` | Class method to load keys from secure session vault |

**Dependencies:** `cryptography.hazmat.primitives.ciphers.aead.AESGCM`

---

## 2. `git_manager.py`

**Responsibility:** Git repository operations and commit message generation

| Component | Description |
|-----------|-------------|
| `GitManager` class | Wraps git commands for notebook repositories |
| `init_repo()` | Initializes git repository (no auto-commit) |
| `commit_silently()` | Stages and commits with atomic operations |
| `generate_commit_message()` | Creates structured commit messages with metadata |
| `commit_notebook_creation()` | Commit for new notebook |
| `commit_note_creation()` | Commit for new note (includes change stats) |
| `commit_note_edit()` | Commit for note edit (+/- character counts) |
| `commit_note_deletion()` | Commit for note deletion |
| `commit_note_rename()` | Commit for note rename |
| `commit_subnotebook_*()` | Commits for subnotebook operations |
| `commit_restoration()` | Commit for restored items |
| `detect_note_type()` | Classifies notes as Quick/Text/Detailed/Formatted |
| `detect_file_purpose()` | Detects file purpose from extension (80+ types) |
| `_count_char_changes()` | Counts actual character additions/removals between strings |

**Commit Message Format:** `type: ACTION CONTENT_TYPE: title | context` with metadata containing UUIDs

---

## 3. `notebook_operations.py`

**Responsibility:** Universal JSON file operations and notebook CRUD with crypto support

| Component | Description |
|-----------|-------------|
| `CryptoManager` class | Centralized key management with vault-backed caching |
| `read_json()` | Reads JSON file with automatic decryption |
| `write_json()` | Writes JSON file with atomic rename and encryption |
| `read_bytes()` | Reads JSON from bytes (git show) with decryption |
| `encrypt_registry_entry()` | Encrypts registry entries for storage |
| `decrypt_registry_entry()` | Decrypts registry entries |
| `find_notebook_folder()` | Scans for notebook folder by ID |
| `NotebookOperations` class | All CRUD operations for notebooks |
| `save_notebook()` | Saves structure.json, notes.json, files.json with selective saving |
| `load_notebook_from_path()` | Loads notebook from filesystem with auto crypto detection |
| `create_note()` | Creates note with atomic commit |
| `edit_note()` | Edits note, saves only affected content file |
| `delete_note()` | Deletes note with git commit |
| `rename_note()` | Renames note (modifies structure.json only) |
| `create_file()` | Creates file note with extension |
| `export_file()` | Exports file note to filesystem |
| `create_subnotebook()` | Creates subnotebook (structure.json only) |
| `delete_subnotebook()` | Deletes subnotebook |
| `rename_subnotebook()` | Renames subnotebook |
| `delete_notebook()` | Complete notebook deletion |

---

## 4. `secure_session.py`

**Responsibility:** Binary vault storage for encrypted notebook keys (zero-trust design)

| Component | Description |
|-----------|-------------|
| `SecureSessionStorage` class | Binary vault manager |
| `_get_system_fingerprint()` | Generates 32-byte fingerprint from hardware (never stored) |
| `store_keys()` | Stores encrypted keys in vault, returns entry UUID |
| `get_keys()` | Retrieves and decrypts keys by UUID |
| `get_keys_with_verification()` | Unlock flow with password and recovery phrase |
| `add_entry()` | Adds or updates vault entry |
| `get_entry()` | Retrieves single entry by UUID |
| `remove_session_key()` | Removes entries for a notebook |
| `list_stored_notebooks()` | Lists all notebooks with stored entries |
| `_read_vault()` / `_write_vault()` | Binary vault I/O with version 2 format |
| `_recover_with_phrase()` | Recovery phrase flow for new machine unlock |

**Vault Format:** Binary file with version, entry count, and per-entry UUID, notebook_id, timestamp, nonce, encrypted_keys

---

## 5. `session_key_vault.py`

**Responsibility:** In-memory cache for unlocked crypto keys with vault persistence

| Component | Description |
|-----------|-------------|
| `SessionKeyVault` class | Dictionary-like interface for crypto keys |
| `__getitem__()` | Retrieves crypto (reads from vault if not cached) |
| `__setitem__()` | Stores crypto (caches and writes to vault) |
| `__contains__()` | Checks if keys exist in vault |
| `lock()` | Removes from cache (locks notebook) |
| `unlock()` | Adds to cache (unlocks notebook) |
| `is_unlocked()` | Checks if notebook is currently unlocked |
| `clear_cache()` | Clears specific or all cached keys |

**Note:** Vault entries are NEVER deleted, only RAM cache is cleared on lock

---

## 6. `terminal_notes_core.py`

**Responsibility:** Data models, central NoteManager, master registry, and core orchestration

| Component | Description |
|-----------|-------------|
| `Note` class | Note data model (title, content, UUID, timestamps, file_extension) |
| `Notebook` class | Hierarchical notebook model (notes, subnotebooks) |
| `NoteManager` class | Central orchestrator - THE CORE |
| `load_all_notebooks()` | Loads notebooks from master registry with lock state |
| `create_notebook()` | Full notebook creation (encrypted/unencrypted) |
| `get_crypto()` | Unlock flow with password/recovery phrase |
| `_get_crypto_from_vault()` | Reads crypto from vault by entry UUID |
| `_write_crypto_to_vault()` | Writes crypto to vault (replaces entry) |
| `load_registry()` | Loads master registry (notebooks + system_index) |
| `save_registry()` | Saves master registry atomically |
| `register_notebook()` | Registers notebook in master registry |
| `unregister_notebook()` | Removes notebook from registry |
| `_compute_fp_hash()` | Computes system fingerprint hash for registry indexing |
| `_get_current_system_entry()` | Gets current system's entry for a notebook |
| `_update_system_entry()` | Updates current system's entry |
| `find_notebook_by_id()` | Finds notebook by ID recursively |
| `find_note_by_id()` | Finds note by ID recursively |
| `get_git_manager()` | Gets or creates Git manager for a notebook |
| `_find_root_notebook()` | Finds root notebook for any nested notebook |
| `SimpleNav` class | Simple navigation stack (push/pop/current) |

**Master Registry Format:**
```json
{
  "version": 2,
  "system_index": {"fp_hash": "system_name"},
  "notebooks": {
    "notebook_id": {
      "name": "notebook_name",
      "systems": {
        "fp_hash": {"path": "...", "vault": "default", "entry": "uuid", "locked": true}
      }
    }
  }
}
```

---

## 7. `terminal_notes_ui.py`

**Responsibility:** Terminal UI, screen rendering, command processing, and user interaction

| Component | Description |
|-----------|-------------|
| `TerminalNotes` class | Main UI controller |
| `show_home_screen()` | Displays root notebooks list with pagination |
| `show_notebook_view_screen()` | Displays notebook contents (notes + files) |
| `show_subnotebooks_view_screen()` | Displays subnotebooks list |
| `show_note_view_screen()` | Displays note content with pagination |
| `process_command()` | Routes commands based on current screen |
| `create_note()` | Creates new note (internal/external editor) |
| `create_file_note()` | Creates specialized file note (80+ extensions) |
| `edit_note()` | Edits note with autosave recovery |
| `rename_note()` | Renames note |
| `delete_note()` | Deletes note (forget/erase) |
| `external_editor_with_recovery()` | Launches external editor with autosave thread |
| `internal_editor()` | Simple built-in editor (Ctrl+D to save) |
| `get_smart_header_path()` | Smart path truncation with numbered navigation |
| `get_numbered_path_info()` | Maps jump numbers to notebooks in path |
| `should_show_jump()` | Determines if jump button should be shown |
| `process_jump_command()` | Jumps to numbered notebook in hierarchy |
| `handle_search()` | Universal search handler (works from any screen) |
| `show_create_import_menu()` | Unified create/import menu |
| `calculate_note_pagination()` | Calculates pagination for note content |
| `wrap_text()` | Word wraps text for display |

**Supported Commands:** `v` (view), `c` (create), `e` (edit), `d` (delete), `r` (rename), `s` (search), `j#` (jump), `jb` (jump back), `l` (lock/unlock), `m` (manage), `n`/`p` (next/prev page), `b` (back), `q` (quit)

---

## 8. `vault_manager.py`

**Responsibility:** Vault registry management and binary vault file I/O

| Component | Description |
|-----------|-------------|
| `VaultManager` class | Manages vault registry and file operations |
| `load_vault_registry()` | Loads vaults_registry.json |
| `save_vault_registry()` | Saves vault registry atomically |
| `get_vault_path()` | Gets absolute path for a vault by name |
| `set_vault_path()` | Sets or updates vault path in registry |
| `list_vaults()` | Lists all vaults with their paths |
| `create_vault_file()` | Creates new empty vault file |
| `read_vault_file()` | Reads binary vault file (version 2 format) |
| `write_vault_file()` | Writes binary vault file atomically |
| `add_entry_to_vault()` | Adds/updates entry in vault |
| `get_entry_from_vault()` | Gets entry by UUID |
| `remove_entry_from_vault()` | Removes entry by UUID |
| `copy_entry_to_vault()` | Copies entry between vaults |
| `get_vault_id_from_file()` | Extracts vault ID from .vault file |
| `ensure_default_vault()` | Ensures default vault exists |

**Vault Registry Format:**
```json
{
  "version": 1,
  "vaults": {
    "default": {"path": "config/session.vault", "updated": "iso_timestamp"},
    "custom_vault": {"path": "/absolute/path/custom.vault", "updated": "iso_timestamp"}
  }
}
```

---

## 9. `change_notebook.py`

**Responsibility:** Notebook modification operations (password, autolock, remote, trusted devices, vault location)

| Component | Description |
|-----------|-------------|
| `ChangeNotebookHandler` class | Handles all notebook change operations |
| `_change_password()` | Password change (old password or recovery phrase) |
| `_change_password_with_old()` | Changes password using old password |
| `_change_password_with_phrase()` | Changes password using recovery phrase |
| `_toggle_autolock()` | Toggles autolock flag in master registry |
| `_change_remote()` | Changes Git remote repository |
| `_show_trusted_devices()` | Lists all trusted devices from all reachable vaults |
| `_change_vault_location()` | Migrates notebook keys to different vault |
| `_create_new_vault_location()` | Creates new vault location with .vault file |

**Security Note:** Password changes update `.tn_recovery`, `.tn_password`, and vault entry, then lock the notebook

---

## 10. `comprehensive_search.py`

**Responsibility:** Unified search engine (current + historical items)

| Component | Description |
|-----------|-------------|
| `ComprehensiveSearch` class | Main search orchestrator |
| `process()` | Main search processor (routes based on mode) |
| `_get_search_items()` | Collects items for normal search |
| `_resolve_notebooks()` | Determines which notebooks to search (scope/global) |
| `_apply_filters()` | Applies action, type, and date filters |
| `_deduplicate()` | Removes duplicates by UUID |
| `_get_action()` | Extracts action from commit message or result |
| `_get_type()` | Determines item type (note/file/notebook/sub) |
| `search_in_notebook()` | Convenience method for notebook-scoped search |
| `show_note_timeline()` | Shows timeline for a note |

**Supported Query Syntax:**
- `created*`, `deleted*`, `edited*`, `renamed*`, `restored*`, `erased*`
- `note*`, `file*`, `notebook*`, `sub*`
- `in* notebookname`
- `g*` or `global*`
- `date* DD-MM-YYYY` or `date* DD-MM-YYYY DD-MM-YYYY`
- `today*`, `yesterday*`, `thisweek*`, `lastweek*`

---

## 11. `cs_ui.py`

**Responsibility:** Search results display and interaction UI

| Component | Description |
|-----------|-------------|
| `PaginationManager` class | Reusable pagination calculations |
| `ResultFormatter` class | Formats search results for display |
| `show_search()` | Main search results screen with pagination |
| `show_timeline()` | Timeline versions display |
| `_format_historical_with_action()` | Formats historical items WITH action prefix |
| `_format_historical_no_action()` | Formats historical items WITHOUT action prefix |
| `format_path()` | Smart path truncation for display |

**Display Format:** `[i] title (with stats)                                      [path]`

---

## 12. `query_parser.py`

**Responsibility:** Parses search queries into structured components

| Component | Description |
|-----------|-------------|
| `QueryParser` class | Central query parser |
| `parse()` | Parses query into structured dict |
| `format_for_display()` | Formats parsed query for display (removes wildcards) |

**Pattern Definitions:**
- `PATTERNS['actions']` - Maps `created*` → `['CREATED']`, etc.
- `PATTERNS['types']` - Maps `note*` → `'note'`, etc.
- `PATTERNS['global']` - `['g*', 'global*']`
- `PATTERNS['date']` - Regex for `date* DD-MM-YYYY`
- `PATTERNS['time_ranges']` - Maps `today*` → `'today'`, etc.

**Output Format:**
```python
{
  'actions': ['CREATED', 'DELETED'],  # or None
  'type': 'note',                      # or None
  'date_range': (start, end),          # or None
  'scope': {'notebook': 'name'},       # or None
  'is_global': False,
  'text': 'search text'
}
```

---

## 13. `git_resurrection.py`

**Responsibility:** Extracts historical items from Git history (deleted, renamed, erased, restored)

| Component | Description |
|-----------|-------------|
| `GitHistoryMiner` class | Git history mining engine |
| `find_deleted_items()` | Finds deleted notes/files/subnotebooks |
| `find_renamed_items()` | Finds renamed items (old → new names) |
| `find_erased_items()` | Finds permanently erased items (tombstones) |
| `find_restored_items()` | Finds restored items |
| `_create_temp_json_for_item()` | Reconstructs item at specific commit into temp directory |
| `_get_historical_json()` | Gets JSON file from git history with crypto support |
| `_get_commit_before()` | Gets commit hash before a given commit |
| `_extract_uuid_from_message()` | Extracts UUID from commit message |
| `_restore_item()` | Restores item (delegates to restore.py) |
| `cleanup_temp_files()` | Cleans up temporary directories |
| `parse_change_stats()` | Parses `change: 12(+) 5(-) totalc:17` from commit messages |

**Note:** Uses `git log --grep` to find commits, then `git show` to extract files

---

## 14. `res_ui.py`

**Responsibility:** Displays resurrected (historical) items with full UI interaction

| Component | Description |
|-----------|-------------|
| `ResurrectedUI` class | UI for historical items |
| `display_item()` | Main entry point (routes to note/notebook display) |
| `_display_note()` | Displays historical note (with timeline line) |
| `_display_notebook()` | Displays historical subnotebook (temporary manager) |
| `_display_erased_item()` | Displays tombstone for erased items |
| `_trigger_restore()` | Triggers restore operation |
| `_create_temp_manager()` | Creates temporary manager for resurrected data |
| `_export_file()` | Exports file to filesystem |

**Features:** [V]iew, [T]imeline, [R]estore, [X]port (files), [P]rev/[N]ext pagination

---

## 15. `search_system.py`

**Responsibility:** Simple current-only search (no Git history)

| Component | Description |
|-----------|-------------|
| `SimpleSearch` class | Basic search over current items |
| `search()` | Searches current notes/files/notebooks |
| `get_search_page_size()` | Calculates pagination size |

**Search Scope:** Title, content (for notes), notebook names (recursive)
**Note:** Skips locked encrypted notebooks entirely

---

## 16. `timeline_engine.py`

**Responsibility:** Version timeline for any item (notes, files, notebooks)

| Component | Description |
|-----------|-------------|
| `TimelineEngine` class | Timeline generation engine |
| `get_item_timeline()` | Gets all historical versions of an item |
| `create_version_at_commit()` | Reconstructs item at specific commit into temp directory |
| `_get_notebook_path()` | Gets filesystem path for notebook |
| `_get_file_at_commit()` | Gets file content at specific commit with crypto |
| `_determine_type()` | Determines item type (note/file/notebook/subnotebook) |
| `_reconstruct_note()` | Reconstructs note/file at commit |
| `_reconstruct_notebook()` | Reconstructs notebook/subnotebook at commit |
| `cleanup()` | Removes all temporary directories |

**Special Handling:** For DELETED commits, uses parent commit to show last valid version

---

## 17. `eraser.py`

**Responsibility:** Soft and hard deletion of items (with Git history rewriting)

| Component | Description |
|-----------|-------------|
| `Eraser` class | Deletion operations |
| `delete_item()` | Universal delete method (forget/erase) |
| `_soft_delete()` | Removes from current view, commits `type: DELETED` |
| `_hard_delete()` | Purges from Git history using filter-repo, commits `type: ERASED` tombstone |
| `_purge_from_git()` | Runs git-filter-repo to remove UUID from all commits |
| `_git_filter_all()` | Executes UUID erase filter |
| `standard_delete_notebook()` | Standard notebook deletion (folder removal) |
| `secure_erase_notebook()` | Complete notebook erasure + vault entry removal |

**Tombstone Commit Format:**
```
type: ERASED NOTE: note title | in notebook_name

Metadata: uuid:abc123 parent:def456 root:ghi789
This item was permanently erased from history.
```

---

## 18. `git_filter_repo.py`

**Responsibility:** Modified git-filter-repo with custom filters for UUID/notebook erasure

| Component | Description |
|-----------|-------------|
| `RepoFilter` class | Base filtering engine (from git-filter-repo) |
| `UUIDEraseFilter` class | Removes all traces of a UUID from history |
| `NotebookEraseFilter` class | Removes entire notebook and all its UUIDs |
| `_tweak_commit()` | Overridden to remove commits containing target UUIDs |
| `_tweak_blob()` | Removes UUIDs from blob contents |

**Usage:**
- `--uuid-erase UUID` - Remove single UUID from history
- `--notebook-erase NOTEBOOK_UUID:UUID1,UUID2,...` - Remove entire notebook

**Note:** This is a complete copy of git-filter-repo (open source) with custom modifications

---

## 19. `editor_config.py`

**Responsibility:** Centralized editor configuration with forced autosave

| Component | Description |
|-----------|-------------|
| `EditorConfig` class | Editor management |
| `NVIM_AUTOSAVE` | NeoVim autosave commands |
| `VIM_AUTOSAVE` | Vim autosave commands |
| `EMACS_AUTOSAVE` | Emacs autosave commands |
| `MICRO_AUTOSAVE` | Micro editor settings JSON |
| `HELIX_AUTOSAVE` | Helix editor TOML config |
| `get_editor_list()` | Returns ordered list of editors (preferred first) |
| `get_launch_command()` | Builds shell command with autosave injection |
| `_ensure_autosave_config()` | Writes config files for editors if missing |

**Supported Editors:** micro, nvim, vim, helix, hx, emacs, nano, kate, geany, gedit, pluma, mousepad, leafpad, mg, jed, joe

---

## 20. `notebook_importer.py`

**Responsibility:** Import existing notebooks from local filesystem

| Component | Description |
|-----------|-------------|
| `NotebookImporter` class | Notebook import operations |
| `import_notebook_flow_with_path()` | Main import flow with provided path |
| `_check_if_encrypted()` | Detects if notebook is encrypted |
| `_import_encrypted()` | Imports encrypted notebook (requires recovery phrase) |
| `_import_unencrypted()` | Imports unencrypted notebook (direct JSON read) |

**Import Process:**
1. Detect encryption (check `.tn_test` or binary content)
2. If encrypted: prompt for recovery phrase, decrypt, register in vault
3. If unencrypted: read JSON files, register in master registry
4. Add to notebook list

---

## 21. `notebook_manager.py`

**Responsibility:** Advanced notebook management (Git remotes, accounts, push/pull)

| Component | Description |
|-----------|-------------|
| `NotebookManager` class | Remote notebook management |
| `load_accounts()` | Loads Git accounts from TokenVault |
| `show_accounts_screen()` | Displays accounts list with pagination |
| `show_account_repos()` | Shows repositories for an account |
| `import_from_url()` | Imports notebook from Git URL |
| `clone_repository()` | Clones git repository (with auth) |
| `register_cloned_notebook()` | Registers cloned notebook in master registry |
| `push_notebook()` | Pushes notebook to remote (creates repo if needed) |
| `toggle_visibility()` | Changes repository visibility (private/public) |
| `delete_repo()` | Deletes remote repository |
| `_add_github_account()` | Adds GitHub account (token with repo scope) |
| `_add_gitlab_account()` | Adds GitLab account (token with api+write_repository) |
| `_add_bitbucket_account()` | Adds Bitbucket account (app password) |
| `_add_gitea_account()` | Adds self-hosted account |
| `check_repos_parallel()` | Parallel repository scanning (improves performance) |
| `get_vault_id_from_file()` | Extracts vault ID from .vault file |

**Supported Platforms:** GitHub, GitLab, Bitbucket, Gitea (self-hosted)

---

## 22. `recovery_system.py`

**Responsibility:** Autosave recovery for unsaved editor content

| Component | Description |
|-----------|-------------|
| `RecoverySystem` class | Autosave recovery management |
| `save_recovery_file()` | Saves autosave recovery file (atomic write) |
| `get_recovery_files_for_notebook()` | Gets all recovery files for a notebook |
| `recover_notebook_content()` | Recovers unsaved content on notebook load |
| `cleanup_stale_recovery_files()` | Cleans old recovery files (>24 hours) |
| `get_recovery_filename()` | Generates filename using UUID suffix |

**Recovery File Location:** `<app_dir>/.recovery/`
**Naming Format:** `{title}_{uuid_suffix}.{ext}` or `{title}_{uuid_suffix}` (for notes)

---

## 23. `restore.py`

**Responsibility:** Restores deleted/erased items from Git history

| Component | Description |
|-----------|-------------|
| `Restore` class | Restoration operations |
| `restore_item()` | Restores single note/file (creates backup before changes) |
| `restore_subnotebook()` | Restores entire subnotebook hierarchy (atomic) |
| `_merge_json_files()` | Merges source JSON into destination (with crypto support) |
| `_update_structure()` | Updates structure.json with restored item |
| `_atomic_filtered_merge()` | Merges only allowed UUIDs (for subnotebooks) |
| `_collect_all_uuids()` | Collects all UUIDs in a notebook hierarchy |
| `_create_temp_manager()` | Creates temporary manager for temp data |

**Restore Process:**
1. Create backups of all affected JSON files
2. Merge content files (notes.json, files.json)
3. Update structure.json
4. Commit `type: RESTORED` with metadata
5. Remove backups on success, restore on failure

---

## 24. `path_utils.py`

**Responsibility:** Platform-agnostic path utilities

| Component | Description |
|-----------|-------------|
| `get_app_dir()` | Returns application directory (works for script and PyInstaller) |
| `get_assets_dir()` | Returns assets directory (where crypto files are) |

**PyInstaller Support:** Detects `sys.frozen` to differentiate between script and executable

---

## Module Dependency Graph

```
                    ┌─────────────────┐
                    │ terminal_notes  │
                    │      _ui.py     │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ comprehensive  │  │  notebook_     │  │   recovery_    │
│   _search.py   │  │   manager.py   │  │    system.py   │
└───────┬────────┘  └───────┬────────┘  └────────────────┘
        │                   │
        ▼                   ▼
┌────────────────┐  ┌────────────────┐
│    cs_ui.py    │  │  change_       │
│  query_parser  │  │  notebook.py   │
│  search_system │  └───────┬────────┘
│  git_resurrect │          │
│  timeline_eng  │          │
└───────┬────────┘          │
        │                   │
        └─────────┬─────────┘
                  │
                  ▼
         ┌────────────────┐
         │  terminal_     │
         │  notes_core.py │
         └───────┬────────┘
                 │
    ┌────────────┼────────────┬────────────┐
    │            │            │            │
    ▼            ▼            ▼            ▼
┌────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐
│ crypto │  │   git_   │  │ notebook │  │  vault_    │
│  .py   │  │ manager  │  │_operations│  │ manager.py │
└────────┘  └──────────┘  └──────────┘  └────────────┘
                 │              │
                 ▼              ▼
         ┌────────────┐  ┌────────────┐
         │   eraser   │  │  restore   │
         │    .py     │  │    .py     │
         └────────────┘  └────────────┘
                 │
                 ▼
         ┌────────────────┐
         │ git_filter_    │
         │    repo.py     │
         └────────────────┘
```
