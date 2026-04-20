"""
notebook_operations.py - Universal JSON file handler with automatic encryption.
Supports dual-key encryption system (password + phrase) with backward compatibility.
"""

import os
import json
import hashlib
from typing import Optional, Dict
from datetime import datetime


# =============================================================================
# CRYPTO MANAGER - Centralized key management
# =============================================================================

class CryptoManager:
    """Centralized crypto management for all operations"""
    
    def __init__(self, manager):
        self.manager = manager
        self._key_cache = {}  # Cache crypto keys by notebook_id
    
    def get_key(self, notebook_id: str, folder_name: str = None):
        """
        Get crypto key for a notebook.
        Tries: cache → session → permanent storage → folder scanning
        """
        # Check cache first
        if notebook_id in self._key_cache:
            return self._key_cache[notebook_id]
        
        # Try session keys
        if notebook_id in self.manager.session_keys:
            key = self.manager.session_keys[notebook_id]
            self._key_cache[notebook_id] = key
            return key
        
        # Try permanent storage with folder name
        if folder_name:
            from crypto import Crypto
            key = Crypto.retrieve_for_folder(folder_name)
            if key:
                self.manager.session_keys[notebook_id] = key
                self._key_cache[notebook_id] = key
                return key
        
        # Try to find folder by scanning
        if not folder_name:
            from notebook_operations import find_notebook_folder
            found = find_notebook_folder(notebook_id, self.manager.notebooks_root)
            if found:
                folder = os.path.basename(found)
                base = folder.split('-')[0] if '-' in folder else folder
                folder_name = f"{base}-{notebook_id}"
                return self.get_key(notebook_id, folder_name)
        
        return None
    
    def get_key_for_notebook(self, notebook):
        """Get key using notebook object"""
        if hasattr(notebook, 'custom_path') and notebook.custom_path:
            folder_name = os.path.basename(notebook.custom_path)
        else:
            clean = notebook.name.replace('🔐 ', '')
            folder_name = f"{clean}-{notebook.id}"
        return self.get_key(notebook.id, folder_name)
    
    def clear_cache(self, notebook_id=None):
        """Clear key cache"""
        if notebook_id:
            self._key_cache.pop(notebook_id, None)
        else:
            self._key_cache.clear()


# =============================================================================
# UNIVERSAL JSON HANDLER
# =============================================================================

def read_json(filepath: str, crypto=None) -> Optional[Dict]:
    """
    Read ANY JSON file. Decrypts automatically if crypto provided.
    Returns parsed dict, or None if failed.
    """
    try:
        with open(filepath, 'rb') as f:
            raw = f.read()
        return _parse_json(raw, crypto)
    except Exception:
        return None


def write_json(filepath: str, data: Dict, crypto=None) -> bool:
    """Write JSON file with atomic rename - SAFE for encrypted data"""
    temp_path = filepath + '.tmp'
    
    try:
        # Convert to JSON string
        json_str = json.dumps(data, indent=2)
        
        # Encrypt if needed
        if crypto:
            final_data = crypto.encrypt(json_str)
            mode = 'wb'
        else:
            final_data = json_str.encode('utf-8')
            mode = 'wb'
        
        # Write to temp file
        with open(temp_path, mode) as f:
            f.write(final_data)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic rename
        os.rename(temp_path, filepath)
        return True
        
    except Exception as e:
        # Clean up temp file
        if os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except:
                pass
        print(f"Error writing {filepath}: {e}")
        return False


def read_bytes(raw_bytes: bytes, crypto=None) -> Optional[Dict]:
    """Read JSON from bytes (like from git show). Decrypts if crypto provided."""
    return _parse_json(raw_bytes, crypto)


def _parse_json(raw: bytes, crypto=None) -> Optional[Dict]:
    """
    Internal: The ONE place where decryption happens.
    Every JSON read in the entire app passes through here.
    """
    if not raw:
        return None
    
    # Try decryption if we have crypto
    if crypto:
        try:
            decrypted = crypto.decrypt(raw)
            return json.loads(decrypted)
        except Exception:
            # Decryption failed - maybe it's plain text?
            pass
    
    # Try as plain text
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return None


def encrypt_registry_entry(entry_data: Dict, crypto) -> str:
    """Encrypt a registry entry using the notebook's crypto key."""
    try:
        json_str = json.dumps(entry_data)
        encrypted = crypto.encrypt(json_str)
        return encrypted.hex()
    except Exception as e:
        print(f"  Failed to encrypt registry entry: {e}")
        return None


def decrypt_registry_entry(entry_hex: str, crypto) -> Optional[Dict]:
    """Decrypt a registry entry using the provided crypto key."""
    try:
        encrypted = bytes.fromhex(entry_hex)
        json_str = crypto.decrypt(encrypted)
        return json.loads(json_str)
    except Exception as e:
        print(f"  Failed to decrypt registry entry: {e}")
        return None


def find_notebook_folder(notebook_id: str, notebooks_root: str) -> Optional[str]:
    """Scan notebooks_root for a folder matching this notebook_id."""
    if not os.path.exists(notebooks_root):
        return None
    
    for folder in os.listdir(notebooks_root):
        folder_path = os.path.join(notebooks_root, folder)
        if os.path.isdir(folder_path) and folder.endswith(notebook_id):
            return folder_path
    return None


# =============================================================================
# NOTEBOOK OPERATIONS
# =============================================================================

class NotebookOperations:
    """
    One class to rule all notebook operations.
    Every method uses read_json/write_json for automatic crypto.
    _crypto attribute is used throughout.
    """
    
    def __init__(self, manager):
        self.manager = manager
        self._crypto_cache = {}  # Cache crypto keys for performance
        self.crypto = CryptoManager(manager)
    
    # -------------------------------------------------------------------------
    # CRYPTO MANAGEMENT
    # -------------------------------------------------------------------------
    
    def get_crypto(self, notebook_id: str):
        """Get crypto key with caching"""
        if notebook_id in self._crypto_cache:
            return self._crypto_cache[notebook_id]
        
        crypto = self.manager.get_crypto(notebook_id)
        if crypto:
            self._crypto_cache[notebook_id] = crypto
        return crypto
    
    def ensure_crypto(self, notebook):
        """Ensure notebook has _crypto attached"""
        if hasattr(notebook, '_crypto') and notebook._crypto:
            return notebook._crypto
        
        crypto = self.get_crypto(notebook.id)
        if crypto:
            notebook._crypto = crypto
            self._propagate_crypto(notebook, crypto)
        return crypto
    
    def _propagate_crypto(self, notebook, crypto):
        """Recursively set _crypto on all notes and subnotebooks"""
        notebook._crypto = crypto
        for note in notebook.notes:
            note._crypto = crypto
        for sub in notebook.subnotebooks:
            self._propagate_crypto(sub, crypto)
    
    # -------------------------------------------------------------------------
    # PATH HELPERS
    # -------------------------------------------------------------------------
    
    def _get_notebook_path(self, notebook) -> str:
        """Get correct path for ANY notebook - ROOT ONLY"""
        
        # ========== SAFETY: Subnotebooks should never call this ==========
        if notebook.parent_id is not None:
            # Find root instead
            root = self.manager._find_root_notebook(notebook)
            if root:
                return self._get_notebook_path(root)
            raise ValueError(f"Cannot get path for subnotebook: {notebook.name}")
        # ========== END SAFETY ==========
        
        if hasattr(notebook, 'custom_path') and notebook.custom_path:
            return notebook.custom_path
        
        clean_name = notebook.name.replace('🔐 ', '')
        folder_name = f"{clean_name}-{notebook.id}"
        return os.path.join(self.manager.notebooks_root, folder_name)
    
    def _get_file_paths(self, notebook):
        """Get all three JSON file paths for a notebook"""
        folder = self._get_notebook_path(notebook)
        return (
            os.path.join(folder, "structure.json"),
            os.path.join(folder, "notes.json"),
            os.path.join(folder, "files.json")
        )
    
    # -------------------------------------------------------------------------
    # NOTEBOOK LOAD/SAVE
    # -------------------------------------------------------------------------
    
    def load_notebook_from_path_with_crypto(self, folder_path, crypto):
        """Load complete notebook from path with crypto - returns fully populated notebook"""
        from terminal_notes_core import Notebook

        structure_file = os.path.join(folder_path, "structure.json")
        notes_file = os.path.join(folder_path, "notes.json")
        files_file = os.path.join(folder_path, "files.json")

        # Read structure
        struct_data = read_json(structure_file, crypto)
        if not struct_data:
            return None

        # Read content
        notes_data = read_json(notes_file, crypto) or {}
        files_data = read_json(files_file, crypto) or {}

        # Create notebook from structure
        notebook = Notebook.from_dict(struct_data)
        
        # Ensure clean name
        notebook.name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
        notebook.custom_path = folder_path
        notebook._crypto = crypto

        # Apply content to all notes
        def apply_content_to_notebook(nb):
            for note in nb.notes:
                if note.is_file_note and note.id in files_data:
                    note.content = files_data[note.id]
                elif not note.is_file_note and note.id in notes_data:
                    note.content = notes_data[note.id]
                note._crypto = crypto
            for sub in nb.subnotebooks:
                apply_content_to_notebook(sub)

        apply_content_to_notebook(notebook)
        return notebook
    
    def load_notebook_from_path(self, folder_path):
        """Load notebook from any folder path - auto-detects encryption"""
        from terminal_notes_core import Notebook
    
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(self.manager.notebooks_root, folder_path)
    
        structure_file = os.path.join(folder_path, "structure.json")
        if not os.path.exists(structure_file):
            return None

        # Check if encrypted
        is_encrypted = os.path.exists(os.path.join(folder_path, ".tn_test"))
    
        if is_encrypted:
            # Encrypted - need crypto
            # This will be handled by the caller
            return None
    
        # Unencrypted - load directly
        with open(structure_file, 'r') as f:
            structure_data = json.load(f)
    
        notebook = Notebook.from_dict(structure_data)
        notebook.custom_path = folder_path
        notebook.name = notebook.name.replace('🔐 ', '')
    
        # Load content
        notes_file = os.path.join(folder_path, "notes.json")
        files_file = os.path.join(folder_path, "files.json")
    
        notes_map = {}
        files_map = {}
    
        if os.path.exists(notes_file):
            with open(notes_file, 'r') as f:
                notes_map = json.load(f)
    
        if os.path.exists(files_file):
            with open(files_file, 'r') as f:
                files_map = json.load(f)
    
        self._apply_file_content_to_notebook(notebook, notes_map, files_map)
        return notebook
    
    def _apply_file_content_to_notebook(self, notebook, notes_map, files_map):
        """Apply separated content back to notes"""
        for note in notebook.notes:
            if note.is_file_note and note.id in files_map:
                note.content = files_map[note.id]
            elif not note.is_file_note and note.id in notes_map:
                note.content = notes_map[note.id]
        for sub_nb in notebook.subnotebooks:
            self._apply_file_content_to_notebook(sub_nb, notes_map, files_map)
    
    def save_notebook(self, notebook, folder_path=None, save_notes=True, save_files=True):
        """Save notebook with atomic writes - USING OPS"""
        # ========== SURGICAL FIX: Subnotebooks don't get folders ==========
        if notebook.parent_id is not None:
            # This is a subnotebook - find root and save that instead
            root = self.manager._find_root_notebook(notebook)
            if root and root.id != notebook.id:
                return self.save_notebook(root, folder_path, save_notes, save_files)
        # ========== END FIX ==========
        try:
            if folder_path is None:
                folder_path = self._get_notebook_path(notebook)
        
            os.makedirs(folder_path, exist_ok=True)
        
            struct_file = os.path.join(folder_path, "structure.json")
            notes_file = os.path.join(folder_path, "notes.json")
            files_file = os.path.join(folder_path, "files.json")
        
            crypto = notebook._crypto if hasattr(notebook, '_crypto') else None
        
            # Write structure
            write_json(struct_file, notebook.to_dict(), crypto)
        
            # Extract content
            notes_map, files_map = self._extract_content(notebook)
        
            # Write content files
            if save_notes:
                write_json(notes_file, notes_map, crypto)
        
            if save_files:
                write_json(files_file, files_map, crypto)
        
            return True
        except Exception as e:
            print(f"Save failed: {e}")
            return False
    
    def _extract_content(self, notebook):
        """Separate notes and files content - STRICT SEPARATION"""
        notes = {}
        files = {}

        def extract_from_notebook(nb):
            for note in nb.notes:
                if note.is_file_note:
                    files[note.id] = note.content
                else:
                    notes[note.id] = note.content
            for sub in nb.subnotebooks:
                extract_from_notebook(sub)

        extract_from_notebook(notebook)
        return notes, files
    
    def _apply_content(self, notebook, notes, files):
        """Apply content to notebook"""
        def apply_to_notebook(nb):
            for note in nb.notes:
                if note.is_file_note:
                    if note.id in files:
                        note.content = files[note.id]
                else:
                    if note.id in notes:
                        note.content = notes[note.id]
            for sub in nb.subnotebooks:
                apply_to_notebook(sub)
        
        apply_to_notebook(notebook)
    
    def _load_encrypted_notebook_from_registry(self, notebook_id, encrypted_entry):
        """Load encrypted notebook from registry entry - with lock state support"""
        from terminal_notes_core import Notebook
        from crypto import Crypto
        from notebook_operations import find_notebook_folder, decrypt_registry_entry, read_json

        crypto = None
        notebook_info = None
        is_locked = False

        # Try all stored keys
        if self.manager.secure_storage:
            stored = self.manager.secure_storage.list_stored_notebooks()
            for folder_name in stored:
                if folder_name.endswith(notebook_id):
                    crypto = Crypto.retrieve_for_folder(folder_name)
                    if crypto:
                        self.manager.session_keys[notebook_id] = crypto
                        break

        # Try to decrypt the entry
        if crypto:
            notebook_info = decrypt_registry_entry(encrypted_entry, crypto)
            if notebook_info:
                is_locked = notebook_info.get("locked", False)

        # Use decrypted info
        if notebook_info:
            folder_path = notebook_info.get("path")
            actual_name = notebook_info.get("name", "Unknown")
            is_locked = notebook_info.get("locked", False)

            if folder_path and not os.path.isabs(folder_path):
                folder_path = os.path.join(self.manager.notebooks_root, folder_path)

            notebook = Notebook(actual_name, notebook_id=notebook_id)
            notebook._crypto = crypto
            self.manager.encrypted_notebooks.add(notebook_id)
    
            if is_locked:
                notebook.locked = True
                notebook.custom_path = None
            else:
                notebook.custom_path = folder_path if folder_path and os.path.exists(folder_path) else None

                if notebook.custom_path and crypto:
                    try:
                        struct_file = os.path.join(folder_path, "structure.json")
                        struct_data = read_json(struct_file, crypto)
                        if struct_data:
                            from terminal_notes_core import Notebook as TempNotebook
                            temp_nb = TempNotebook.from_dict(struct_data)
                            
                            def count_items(nb):
                                note_count = 0
                                file_count = 0
                                for note in nb.notes:
                                    if note.is_file_note:
                                        file_count += 1
                                    else:
                                        note_count += 1
                                sub_count = len(nb.subnotebooks)
                                for sub in nb.subnotebooks:
                                    sub_note_count, sub_file_count, sub_sub_count = count_items(sub)
                                    note_count += sub_note_count
                                    file_count += sub_file_count
                                    sub_count += sub_sub_count
                                return note_count, file_count, sub_count
                            
                            note_count, file_count, sub_count = count_items(temp_nb)
                            notebook._note_count = note_count
                            notebook._file_count = file_count
                            notebook._sub_count = sub_count
                            notebook._structure_data = struct_data
                    except Exception:
                        notebook.custom_path = None
                        notebook.locked = True
    
            return notebook

        # Try to find folder by scanning
        found_path = find_notebook_folder(notebook_id, self.manager.notebooks_root)

        if found_path:
            folder_name = os.path.basename(found_path)
            actual_name = folder_name.split('-')[0] if '-' in folder_name else folder_name

            if not crypto:
                crypto = Crypto.retrieve_for_folder(folder_name)
                if crypto:
                    self.manager.session_keys[notebook_id] = crypto

            if crypto:
                try:
                    struct_file = os.path.join(found_path, "structure.json")
                    notes_file = os.path.join(found_path, "notes.json")
                    files_file = os.path.join(found_path, "files.json")

                    struct_data = read_json(struct_file, crypto)
                    if struct_data:
                        notes_data = read_json(notes_file, crypto) or {}
                        files_data = read_json(files_file, crypto) or {}

                        notebook = Notebook.from_dict(struct_data)
                        notebook.name = notebook.name.replace('🔐 ', '')
                        notebook._crypto = crypto
                        notebook.custom_path = found_path
                        self.manager.encrypted_notebooks.add(notebook_id)
                        self._apply_file_content_to_notebook(notebook, notes_data, files_data)

                        notebook._cached_note_count = len(notes_data)
                        notebook._cached_file_count = len(files_data)
                        notebook._cached_sub_count = len(notebook.subnotebooks)
                        notebook._metadata_loaded = True
                        return notebook
                except Exception:
                    pass

            # Locked placeholder
            notebook = Notebook(actual_name, notebook_id=notebook_id)
            notebook.locked = True
            notebook.custom_path = None
            self.manager.encrypted_notebooks.add(notebook_id)
            return notebook

        # Fallback
        notebook = Notebook(f"Locked-{notebook_id[:8]}", notebook_id=notebook_id)
        notebook.locked = True
        return notebook
    
    def _load_unencrypted_notebook_from_registry(self, entry):
        """Load unencrypted notebook from registry entry"""
        from terminal_notes_core import Notebook
    
        folder_path = entry.get("path")
        if not folder_path:
            return None
    
        if not os.path.isabs(folder_path):
            folder_path = os.path.join(self.manager.notebooks_root, folder_path)
    
        if not os.path.exists(folder_path):
            return None
    
        try:
            struct_file = os.path.join(folder_path, "structure.json")
            notes_file = os.path.join(folder_path, "notes.json")
            files_file = os.path.join(folder_path, "files.json")
        
            with open(struct_file, 'r') as f:
                structure_data = json.load(f)
        
            notebook = Notebook.from_dict(structure_data)
            notebook.custom_path = folder_path
            notebook.name = notebook.name.replace('🔐 ', '')
        
            notes_map = {}
            files_map = {}
        
            if os.path.exists(notes_file):
                with open(notes_file, 'r') as f:
                    notes_map = json.load(f)
        
            if os.path.exists(files_file):
                with open(files_file, 'r') as f:
                    files_map = json.load(f)
        
            self._apply_file_content_to_notebook(notebook, notes_map, files_map)
        
            test_file = os.path.join(folder_path, ".tn_test")
            if os.path.exists(test_file):
                self.manager.encrypted_notebooks.add(notebook.id)
        
            return notebook
        
        except Exception:
            return None
    
    def load_unencrypted_notebook(self, entry):
        """Public method to load unencrypted notebook"""
        return self._load_unencrypted_notebook_from_registry(entry)
    
    def get_notebook_metadata(self, notebook_id):
        """Get notebook metadata without fully loading the notebook"""
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return None
    
        if hasattr(notebook, '_metadata_loaded') and notebook._metadata_loaded:
            return {
                'note_count': notebook._cached_note_count,
                'file_count': notebook._cached_file_count,
                'sub_count': notebook._cached_sub_count,
                'name': notebook.name,
                'id': notebook.id,
                'is_encrypted': notebook.id in self.manager.encrypted_notebooks
            }
    
        if notebook.id in self.manager.encrypted_notebooks:
            crypto = self.manager.session_keys.get(notebook.id)
            if not crypto:
                return {
                    'note_count': 0,
                    'file_count': 0,
                    'sub_count': 0,
                    'name': notebook.name,
                    'id': notebook.id,
                    'is_encrypted': True
                }
        
            try:
                folder_path = notebook.custom_path
                if not folder_path:
                    return None
            
                struct_file = os.path.join(folder_path, "structure.json")
                struct_data = read_json(struct_file, crypto)
            
                if struct_data:
                    from terminal_notes_core import Notebook
                    temp_nb = Notebook.from_dict(struct_data)
                
                    notebook._cached_note_count = temp_nb.get_total_note_count()
                    notebook._cached_file_count = temp_nb.get_file_note_count()
                    notebook._cached_sub_count = temp_nb.get_total_subnotebook_count()
                    notebook._metadata_loaded = True
                
                    return {
                        'note_count': notebook._cached_note_count,
                        'file_count': notebook._cached_file_count,
                        'sub_count': notebook._cached_sub_count,
                        'name': notebook.name,
                        'id': notebook.id,
                        'is_encrypted': True
                    }
            except Exception:
                return {
                    'note_count': 0,
                    'file_count': 0,
                    'sub_count': 0,
                    'name': notebook.name,
                    'id': notebook.id,
                    'is_encrypted': True
                }
    
        return {
            'note_count': notebook.get_total_note_count(),
            'file_count': notebook.get_file_note_count(),
            'sub_count': notebook.get_total_subnotebook_count(),
            'name': notebook.name,
            'id': notebook.id,
            'is_encrypted': notebook.id in self.manager.encrypted_notebooks
        }
    
    # -------------------------------------------------------------------------
    # NOTE OPERATIONS
    # -------------------------------------------------------------------------
    
    def get_note_content(self, note_id: str, notebook_id: str) -> Optional[str]:
        """Get note content with automatic decryption"""
        note, notebook = self.manager.find_note_by_id(notebook_id, note_id)
        if not note or not notebook:
            return None
        return note.content
    
    def create_note(self, notebook, title, content="", editor="internal"):
        """Create a new note - SINGLE ATOMIC COMMIT with content"""
        from terminal_notes_core import Note

        # Ensure crypto is attached
        self.ensure_crypto(notebook)

        note = Note(title, content, created_with=editor)
        notebook.notes.append(note)

        root = self.manager._find_root_notebook(notebook)
        self.save_notebook(root, save_notes=True, save_files=False)

        for i, nb in enumerate(self.manager.notebooks):
            if nb.id == root.id:
                self.manager.notebooks[i] = root
                break

        if notebook.id != root.id:
            for i, root_nb in enumerate(self.manager.notebooks):
                updated = self._update_notebook_tree(root_nb, notebook.id, notebook)
                if updated:
                    self.manager.notebooks[i] = updated
                    break

        self._git_commit(notebook, lambda git: git.commit_note_creation(
            note.id, title, notebook.name, editor, content,
            parent_uuid=notebook.id,
            root_uuid=root.id
        ))

        return note
    
    def _update_notebook_tree(self, notebook, target_id, updated_notebook):
        """Recursively find and update a notebook in the tree"""
        if notebook.id == target_id:
            return updated_notebook
    
        for i, sub in enumerate(notebook.subnotebooks):
            if sub.id == target_id:
                notebook.subnotebooks[i] = updated_notebook
                return notebook
            result = self._update_notebook_tree(sub, target_id, updated_notebook)
            if result:
                return notebook
    
        return None
    
    def edit_note(self, note, notebook, new_content):
        """Edit a note - automatically handles versions"""
        old = note.content
        note.content = new_content
        note.updated = datetime.now()

        # ========== FIX: Save only the appropriate content file ==========
        if note.is_file_note:
            # File note: only save files.json
            self.save_notebook(notebook, save_notes=False, save_files=True)
        else:
            # Regular note: only save notes.json
            self.save_notebook(notebook, save_notes=True, save_files=False)
        # ========== END FIX ==========

        for i, nb in enumerate(self.manager.notebooks):
            if nb.id == notebook.id:
                self.manager.notebooks[i] = notebook
                break

        self._git_commit(notebook, lambda git: git.commit_note_edit(
            note.id, note.title, notebook.name, old, new_content,
            is_file_note=note.is_file_note,  # ← Already fixed earlier
            parent_uuid=notebook.id,
            root_uuid=self.manager._find_root_notebook(notebook).id
        ))
    
    def delete_note(self, note, notebook, delete_type='forget'):
        """Delete a note - history preserved in git"""
        self.ensure_crypto(notebook)
        
        note_id = note.id
        title = note.title
        is_file = note.is_file_note
    
        notebook.notes.remove(note)
        self.manager.save_notebook(notebook)
        self._git_commit(notebook, lambda git: git.commit_note_deletion(
            note_id, title, notebook.name, is_file,
            parent_uuid=notebook.id,
            root_uuid=self.manager._find_root_notebook(notebook).id
        ))
    
    def rename_note(self, note, notebook, new_title):
        """Rename a note - ONLY modifies structure.json"""
        self.ensure_crypto(notebook)
        
        old_title = note.title
        note.title = new_title
        note.updated = datetime.now()

        root = self.manager._find_root_notebook(notebook)
        self.save_notebook(root, save_notes=False, save_files=False)
    
        for i, nb in enumerate(self.manager.notebooks):
            if nb.id == root.id:
                self.manager.notebooks[i] = root
                break

        self._git_commit(notebook, lambda git: git.commit_note_rename(
            note.id, old_title, new_title, notebook.name, note.is_file_note,
            parent_uuid=notebook.id,
            root_uuid=root.id
        ))
    
    # -------------------------------------------------------------------------
    # FILE OPERATIONS
    # -------------------------------------------------------------------------
    
    def create_file(self, notebook, filename: str, content: str, ext: str):
        """Create a file note"""
        from terminal_notes_core import Note
        
        self.ensure_crypto(notebook)
        
        note = Note(filename, content, created_with="external")
        note.file_extension = ext
        notebook.notes.append(note)
        
        root = self.manager._find_root_notebook(notebook)
        self.manager.save_notebook(root, save_notes=False, save_files=True)
        
        self._git_commit(notebook, lambda git: git.commit_file_creation(
            note.id, filename, notebook.name, ext, content,
            parent_uuid=notebook.id,
            root_uuid=root.id
        ))
        
        return note
    
    def export_file(self, note, export_dir: str) -> bool:
        """Export file note to filesystem"""
        if not note.is_file_note:
            return False
        
        export_path = os.path.join(export_dir, note.title)
        try:
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(note.content)
            return True
        except Exception:
            return False
    
    # -------------------------------------------------------------------------
    # SUBNOTEBOOK OPERATIONS
    # -------------------------------------------------------------------------
    
    def create_subnotebook(self, parent, name: str):
        """Create a subnotebook - ONLY modifies structure.json"""
        from terminal_notes_core import Notebook

        self.ensure_crypto(parent)

        sub = Notebook(name, parent_id=parent.id)
        parent.subnotebooks.append(sub)

        root = self.manager._find_root_notebook(parent)

        self.save_notebook(root, save_notes=False, save_files=False)

        for i, nb in enumerate(self.manager.notebooks):
            if nb.id == root.id:
                self.manager.notebooks[i] = root
                break

        if parent.id != root.id:
            for i, root_nb in enumerate(self.manager.notebooks):
                updated = self._update_notebook_tree(root_nb, parent.id, parent)
                if updated:
                    self.manager.notebooks[i] = updated
                    break

        self._git_commit(parent, lambda git: git.commit_subnotebook_creation(
            sub.id, name, parent, 0,
            root_uuid=root.id
        ))

        return sub
    
    def delete_subnotebook(self, subnotebook, parent):
        """Delete a subnotebook"""
        self.ensure_crypto(parent)
        
        sub_id = subnotebook.id
        sub_name = subnotebook.name
        
        parent.subnotebooks.remove(subnotebook)
        self.save_notebook(parent)
        self._git_commit(parent, lambda git: git.commit_subnotebook_deletion(
            sub_id, sub_name, parent.name,
            root_uuid=self.manager._find_root_notebook(parent).id
        ))
    
    def rename_subnotebook(self, subnotebook, parent, new_name: str):
        """Rename a subnotebook - ONLY modifies structure.json"""
        self.ensure_crypto(parent)
        
        old_name = subnotebook.name
        subnotebook.name = new_name
    
        root = self.manager._find_root_notebook(parent)
        self.save_notebook(root, save_notes=False, save_files=False)
    
        for i, nb in enumerate(self.manager.notebooks):
            if nb.id == root.id:
                self.manager.notebooks[i] = root
                break
    
        if parent.id != root.id:
            for i, nb in enumerate(self.manager.notebooks):
                if nb.id == parent.id:
                    self.manager.notebooks[i] = parent
                    break
    
        for i, nb in enumerate(self.manager.notebooks):
            updated = self._update_subnotebook_in_tree(nb, subnotebook.id, new_name)
            if updated:
                self.manager.notebooks[i] = updated
                break
    
        self._git_commit(parent, lambda git: git.commit_subnotebook_rename(
            subnotebook.id, old_name, new_name, parent.name,
            parent_uuid=parent.id,
            root_uuid=root.id
        ))
    
    def _update_subnotebook_in_tree(self, notebook, target_id, new_name):
        """Recursively find and update a subnotebook by ID"""
        if notebook.id == target_id:
            notebook.name = new_name
            return notebook
    
        for i, sub in enumerate(notebook.subnotebooks):
            if sub.id == target_id:
                sub.name = new_name
                return notebook
            updated = self._update_subnotebook_in_tree(sub, target_id, new_name)
            if updated:
                return notebook
    
        return None
    
    # -------------------------------------------------------------------------
    # GIT HELPERS
    # -------------------------------------------------------------------------
    
    def _git_commit(self, notebook, commit_func):
        """Universal git commit helper - Git is optional"""
        try:
            root = self.manager._find_root_notebook(notebook)
            git = self.manager.get_git_manager(root)
            commit_func(git)
        except Exception:
            pass  # Git failures don't break the app
    
    def delete_notebook(self, notebook_to_delete):
        """Delete a notebook completely"""
        registry_data = self.manager.load_registry()
        notebook_path = None
    
        if notebook_to_delete.id in registry_data["notebooks"]:
            entry = registry_data["notebooks"][notebook_to_delete.id]
            if isinstance(entry, dict):
                notebook_path = entry.get("path")
                if notebook_path and not os.path.isabs(notebook_path):
                    notebook_path = os.path.join(self.manager.notebooks_root, notebook_path)
    
        for i, notebook in enumerate(self.manager.notebooks):
            if notebook.id == notebook_to_delete.id:
                self.manager.notebooks.pop(i)
                break
    
        self.manager.unregister_notebook(notebook_to_delete.id)
    
        if notebook_path and os.path.exists(notebook_path):
            import shutil
            shutil.rmtree(notebook_path)
            print(f"  ⚠ Deleted folder: {notebook_path}")