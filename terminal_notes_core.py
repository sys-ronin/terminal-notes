#!/usr/bin/env python3
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(current_dir, 'project', 'assets')
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(assets_dir, 'cffi'))
sys.path.insert(0, os.path.join(assets_dir, 'cryptography'))
import sys
sys.dont_write_bytecode = True

import json
import subprocess
import tempfile
import shutil
import readline
import traceback
import uuid
import getpass
import re
import hashlib

def _safe_folder_name(name, notebook_id):
    """Convert name to safe folder name: lowercase, spaces to hyphens, keep underscores."""
    # Replace spaces with hyphens, convert to lowercase
    safe = name.replace(' ', '-').lower()
    # Remove any character not alphanumeric, hyphen, or underscore
    safe = re.sub(r'[^a-z0-9\-_]', '', safe)
    # Fallback if empty
    if not safe:
        safe = 'notebook'
    return f"{safe}-{notebook_id}"


from crypto import Crypto
from datetime import datetime
from pathlib import Path
from git_manager import GitManager
from notebook_operations import read_json, write_json, decrypt_registry_entry, find_notebook_folder

# Import the secure session storage
try:
    from secure_session import SecureSessionStorage
    HAS_SECURE_STORAGE = True
except ImportError:
    HAS_SECURE_STORAGE = False

def ensure_uuid(id_value):
    """
    Keeps your old timestamp IDs working,
    but generates a UUID for new items automatically.
    """
    if not id_value:
        return str(uuid.uuid4())
    # If it's an old timestamp ID (all digits, less than 20 chars), keep it
    if re.match(r"^\d{8,20}$", str(id_value)):
        return id_value
    # If it's already a UUID, keep it
    return str(id_value)


class Note:
    def __init__(self, title, content="", note_id=None, created_with="internal"):
        self.id = ensure_uuid(note_id or datetime.now().strftime("%Y%m%d%H%M%S"))
        self.title = title
        self.content = content
        self.created = datetime.now()
        self.updated = datetime.now()
        self.created_with = created_with
        self.file_extension = None       
        self._crypto = None

    def to_dict(self):
        data = {
            "id": self.id,
            "title": self.title,
            # CONTENT REMOVED - now stored in content.json only
            "created": self.created.isoformat(),
            "updated": self.updated.isoformat(),
            "created_with": self.created_with,
        }
        if self.file_extension:
            data["file_extension"] = self.file_extension
        return data

    @classmethod
    def from_dict(cls, data):
        # Start with empty content - will be filled from content.json
        note = cls(
            data["title"],
            "",  # Empty content - will be loaded from content.json
            data["id"],
            data.get("created_with", "internal"),
        )
        note.created = datetime.fromisoformat(data["created"])
        note.updated = datetime.fromisoformat(data["updated"])
        note.file_extension = data.get("file_extension")
        # 🟢 ADD THIS LINE - preserve crypto when recreating from dict
        note._crypto = data.get("_crypto")  # Pass through crypto if present
        return note

    @property
    def is_file_note(self):
        return self.file_extension is not None


class Notebook:
    def __init__(self, name, parent_id=None, notebook_id=None):
        self.id = ensure_uuid(notebook_id or datetime.now().strftime("%Y%m%d%H%M%S"))
        self.name = name
        self.parent_id = parent_id
        self.notes = []
        self.subnotebooks = []
        self.custom_path = None
        self.locked = False
        self.vault_id = None  # ← NEW: None = use default vault

    def get_total_note_count(self):
        count = len(self.notes)
        for sub_nb in self.subnotebooks:
            count += sub_nb.get_total_note_count()
        return count

    def get_total_subnotebook_count(self):
        count = len(self.subnotebooks)
        for sub_nb in self.subnotebooks:
            count += sub_nb.get_total_subnotebook_count()
        return count

    def to_dict(self):
        data = {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "notes": [note.to_dict() for note in self.notes],
            "subnotebooks": [nb.to_dict() for nb in self.subnotebooks],
        }
        if hasattr(self, 'custom_path') and self.custom_path:
            data["custom_path"] = self.custom_path
        return data

    @classmethod
    def from_dict(cls, data):
        notebook = cls(data["name"], data["parent_id"], data["id"])
        notebook.notes = []
        for note_data in data["notes"]:
            if 'title' in note_data:
                notebook.notes.append(Note.from_dict(note_data))
        notebook.subnotebooks = [
            Notebook.from_dict(nb_data) for nb_data in data["subnotebooks"]
        ]
        if "custom_path" in data:
            notebook.custom_path = data["custom_path"]
        # 🟢 ADD THIS LINE - preserve crypto when recreating from dict
        notebook._crypto = data.get("_crypto")
        return notebook
    
    def get_file_note_count(self):
        count = 0
        for note in self.notes:
            if note.is_file_note:
                count += 1
        for sub_nb in self.subnotebooks:
            count += sub_nb.get_file_note_count()
        return count


class NoteManager:
    def __init__(self, app_dir=None):
        # Check for environment variables first (Docker override)
        custom_notebooks_root = os.environ.get('TN_NOTEBOOKS_ROOT')
        custom_config_dir = os.environ.get('TN_CONFIG_DIR')
        
        if app_dir is not None:
            self.app_dir = app_dir
        else:
            if getattr(sys, 'frozen', False):
                self.app_dir = os.path.dirname(sys.executable)
            else:
                self.app_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Use environment variable if set (for Docker)
        if custom_notebooks_root:
            self.notebooks_root = custom_notebooks_root
        else:
            self.notebooks_root = os.path.join(self.app_dir, "notebooks_root")
        
        self.ensure_notebooks_root()
        self.notebooks = []
        self.git_managers = {}
        self.encrypted_notebooks = set()
        self.session_keys = {}
        self._search_loaded = False
        self._crypto = None

        # Initialize secure session storage
        self.secure_storage = None
        if HAS_SECURE_STORAGE:
            try:
                # Pass custom config dir if set
                if custom_config_dir:
                    self.secure_storage = SecureSessionStorage(custom_config_dir)
                else:
                    self.secure_storage = SecureSessionStorage(self.app_dir)
                self._load_all_stored_keys()
                self._load_session_keys_from_storage()
            except Exception as e:
                print(f"⚠ Could not initialize secure storage: {e}")

        self.load_all_notebooks()
        self._just_created = False
    
    def _get_vault_path_for_notebook(self, notebook):
        """Get the vault path for a notebook (default or custom)"""
        from vault_manager import VaultManager
        
        if hasattr(notebook, 'vault_id') and notebook.vault_id:
            # Custom vault
            vault_manager = VaultManager(self.app_dir)
            vault_path = vault_manager.get_vault_path(notebook.vault_id)
            if vault_path:
                return vault_path
        
        # Default vault
        return os.path.join(self.app_dir, "config", "session.vault")

    def _load_all_stored_keys(self):
        """Load ALL stored keys from permanent storage at startup"""
        if not self.secure_storage:
            return
    
        try:
            stored_notebooks = self.secure_storage.list_stored_notebooks()
            for folder_name, metadata in stored_notebooks.items():
                # Extract notebook_id from folder name
                if '-' in folder_name:
                    notebook_id = folder_name.split('-')[-1]
                    # Retrieve the key
                    from crypto import Crypto
                    crypto = Crypto.retrieve_for_folder(folder_name)
                    if crypto:
                        self.session_keys[notebook_id] = crypto
                        self.encrypted_notebooks.add(notebook_id)
        except Exception as e:
            print(f"Warning: Could not load stored keys: {e}")
    
    def load_for_search(self):
        """Load all unlocked notebook content silently - INCLUDING SUBNOTEBOOKS"""
        if self._search_loaded:
            return True
    
        for notebook in self.notebooks:
            if hasattr(notebook, '_notes_loaded') and notebook._notes_loaded:
                continue
            
            if notebook.id in self.session_keys:
                crypto = self.session_keys[notebook.id]
                if hasattr(notebook, 'custom_path') and notebook.custom_path:
                    from notebook_operations import NotebookOperations
                    ops = NotebookOperations(self)
                    loaded = ops.load_notebook_from_path_with_crypto(notebook.custom_path, crypto)
                    if loaded:
                        notebook.notes = loaded.notes
                        notebook.subnotebooks = loaded.subnotebooks
                        notebook._notes_loaded = True
    
        self._search_loaded = True
        return True
            
    def unload_notebook(self, notebook_id):
        """Unload a notebook's content when locked"""
        notebook = self.find_notebook_by_id(notebook_id)
        if notebook:
            print(f"  Unloading: {notebook.name}")
            notebook.notes = []
            notebook.subnotebooks = []
            notebook._notes_loaded = False
            # Remove from session keys
            if notebook_id in self.session_keys:
                del self.session_keys[notebook_id]
            
##############################################################################
    
    def ensure_crypto(self, notebook, note=None):
        """
        Centralized method to ensure crypto is attached to notebook and optionally a note.
        Returns the crypto key if available, None otherwise.
        """
        if notebook.id not in self.encrypted_notebooks:
            return None
    
        # Case 1: Notebook already has crypto
        if hasattr(notebook, '_crypto') and notebook._crypto:
            crypto = notebook._crypto
        else:
            # Case 2: Try to get from session
            crypto = self.session_keys.get(notebook.id)
            if crypto:
                notebook._crypto = crypto
    
        # If we have crypto, ensure it's propagated
        if crypto:
            # Attach to notebook if not already
            if not hasattr(notebook, '_crypto') or not notebook._crypto:
                notebook._crypto = crypto
        
            # Attach to specific note if provided
            if note and (not hasattr(note, '_crypto') or not note._crypto):
                note._crypto = crypto
    
        return crypto

    def ensure_note_crypto(self, note, notebook):
        """Convenience method to ensure crypto on a note"""
        return self.ensure_crypto(notebook, note)
    
    def _propagate_crypto_to_subnotebooks(self, notebook, crypto):
        """Recursively set _crypto on all subnotebooks and their notes"""
        if not notebook:
            return
    
        # Set crypto on this notebook
        notebook._crypto = crypto
    
        # Set on all notes in this notebook
        for note in notebook.notes:
            note._crypto = crypto
    
        # Recursively process subnotebooks
        for sub in notebook.subnotebooks:
            self._propagate_crypto_to_subnotebooks(sub, crypto)
    
##############################################################################
    
    # terminal_notes_core.py - Updated get_crypto for dual-key system

    # terminal_notes_core.py - Fix get_crypto to work with old lock/unlock

    def get_crypto(self, notebook_id):
        """Get crypto for a notebook - handles locked state and prompts for password/phrase"""
        from crypto import Crypto
        from secure_session import SecureSessionStorage
        import os
        from notebook_operations import find_notebook_folder, decrypt_registry_entry
        from getpass import getpass
        from crypto import derive_key

        # Find the notebook
        notebook = self.find_notebook_by_id(notebook_id)
        if not notebook:
            return None

        # Check if notebook is encrypted
        if notebook_id not in self.encrypted_notebooks:
            return None

        # If notebook is locked or has no custom_path
        if notebook.locked or not hasattr(notebook, 'custom_path') or not notebook.custom_path:
            
            # Clear any stale session key
            if notebook_id in self.session_keys:
                del self.session_keys[notebook_id]
            
            clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
            folder_name = f"{clean_name}-{notebook_id}"
            
            # Get folder path first (from registry or scan)
            registry_data = self.load_registry()
            folder_path = None
            
            if notebook_id in registry_data["notebooks"]:
                entry = registry_data["notebooks"][notebook_id]
                
                if isinstance(entry, dict):
                    folder_path = entry.get("path")
                elif isinstance(entry, str):
                    # Try to get keys from secure session to decrypt the path
                    storage = SecureSessionStorage(self.app_dir)
                    stored_pw_key, stored_ph_key = storage.get_keys(notebook_id)
                    
                    if stored_pw_key and stored_ph_key:
                        temp_crypto = Crypto(stored_pw_key, stored_ph_key, "temp")
                        decrypted = decrypt_registry_entry(entry, temp_crypto)
                        if decrypted:
                            folder_path = decrypted.get("path")
            
            if folder_path and not os.path.isabs(folder_path):
                folder_path = os.path.join(self.notebooks_root, folder_path)
            
            if not folder_path or not os.path.exists(folder_path):
                folder_path = find_notebook_folder(notebook_id, self.notebooks_root)
            
            if not folder_path or not os.path.exists(folder_path):
                print(f"❌ Cannot find notebook folder for {notebook.name}")
                return None
            
            # Now prompt for password or phrase
            storage = SecureSessionStorage(self.app_dir)
            stored_pw_key, stored_ph_key = storage.get_keys(notebook_id)
            
            # If we have keys in secure session, verify password
            if stored_pw_key and stored_ph_key:
                attempts = 0
                max_attempts = 3
                password_verified = False
                
                while attempts < max_attempts and not password_verified:
                    remaining = max_attempts - attempts
                    password = getpass(f"Password ({remaining} attempts remaining): ")
                    derived_key = derive_key(password, folder_name)
                    
                    if derived_key == stored_pw_key:
                        password_verified = True
                        break
                    else:
                        attempts += 1
                        if attempts < max_attempts:
                            print("Wrong password. Try again.")
                
                if not password_verified:
                    print("Too many failed attempts.")
                    return None
                
                # Create crypto and verify with .tn_test
                crypto = Crypto(stored_pw_key, stored_ph_key, folder_name)
                test_file = os.path.join(folder_path, ".tn_test")
                if not crypto.verify_test_marker(test_file):
                    return None
                
                self.session_keys[notebook_id] = crypto
                notebook.custom_path = folder_path
                notebook._crypto = crypto
                notebook.locked = False
                
                # Refresh notebook content
                self._refresh_encrypted_notebook(notebook, crypto)
                
                # Update registry lock status
                if notebook_id in registry_data["notebooks"]:
                    entry = registry_data["notebooks"][notebook_id]
                    if isinstance(entry, dict):
                        entry["locked"] = False
                        self.save_registry(registry_data)
                    elif isinstance(entry, str):
                        from notebook_operations import encrypt_registry_entry
                        decrypted = decrypt_registry_entry(entry, crypto)
                        if decrypted:
                            decrypted["locked"] = False
                            new_entry = encrypt_registry_entry(decrypted, crypto)
                            if new_entry:
                                registry_data["notebooks"][notebook_id] = new_entry
                                self.save_registry(registry_data)
                
                return crypto
            
            # No keys in secure session - first time on this machine
            # Use get_keys_with_verification which will prompt for phrase
            password_key, phrase_key = storage.get_keys_with_verification(
                notebook_id, folder_path, folder_name
            )
            
            if password_key is None or phrase_key is None:
                return None
            
            crypto = Crypto(password_key, phrase_key, folder_name)
            
            # Verify with .tn_test
            test_file = os.path.join(folder_path, ".tn_test")
            if not crypto.verify_test_marker(test_file):
                return None
            
            self.session_keys[notebook_id] = crypto
            notebook.custom_path = folder_path
            notebook._crypto = crypto
            notebook.locked = False
            
            # Refresh notebook content
            self._refresh_encrypted_notebook(notebook, crypto)
            
            # Update registry lock status
            if notebook_id in registry_data["notebooks"]:
                entry = registry_data["notebooks"][notebook_id]
                if isinstance(entry, dict):
                    entry["locked"] = False
                    self.save_registry(registry_data)
                elif isinstance(entry, str):
                    from notebook_operations import encrypt_registry_entry
                    decrypted = decrypt_registry_entry(entry, crypto)
                    if decrypted:
                        decrypted["locked"] = False
                        new_entry = encrypt_registry_entry(decrypted, crypto)
                        if new_entry:
                            registry_data["notebooks"][notebook_id] = new_entry
                            self.save_registry(registry_data)
            
            return crypto
        
        # Already unlocked
        else:
            if notebook_id in self.session_keys:
                return self.session_keys[notebook_id]
            return None


    def _refresh_encrypted_notebook(self, notebook, crypto):
        """Replace the locked placeholder with the real decrypted notebook data"""
        try:
            if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                return
            
            folder_path = notebook.custom_path
            
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self)
            real_notebook = ops.load_notebook_from_path_with_crypto(folder_path, crypto)
            
            if not real_notebook:
                return
            
            clean_name = real_notebook.name.replace('🔐 ', '')
            real_notebook.name = clean_name
            real_notebook.custom_path = folder_path
            real_notebook._crypto = crypto
            
            # Copy all notes and subnotebooks
            notebook.notes = real_notebook.notes
            notebook.subnotebooks = real_notebook.subnotebooks
            
            # Propagate crypto
            ops._propagate_crypto(notebook, crypto)
            
            # Update in manager's list
            for i, nb in enumerate(self.notebooks):
                if nb.id == notebook.id:
                    self.notebooks[i] = notebook
                    break
                    
        except Exception as e:
            print(f"Error refreshing notebook: {e}")
     
    def _load_session_keys_from_storage(self):
        """Pre-load session keys from permanent storage into memory"""
        if not self.secure_storage:
            return

        try:
            stored_notebooks = self.secure_storage.list_stored_notebooks()
            registry_data = self.load_registry()
    
            for folder_name, metadata in stored_notebooks.items():
                # folder_name is like "notebookname-20260302123456"
                # Extract notebook_id (the UUID part after the hyphen)
                if '-' in folder_name:
                    notebook_id = folder_name.split('-')[-1]
            
                    # Only load if this notebook is still in registry
                    if notebook_id in registry_data["notebooks"]:
                        # Retrieve the key from permanent storage
                        from crypto import Crypto
                        crypto = Crypto.retrieve_for_folder(folder_name)
                
                        if crypto:
                            # Store in session_keys for quick access
                            self.session_keys[notebook_id] = crypto
                    
                            # Mark as encrypted
                            self.encrypted_notebooks.add(notebook_id)
                    
        except Exception as e:
            print(f"Warning: Could not load session keys: {e}")
    
    def get_registry_file(self):
        """Get the path to the registry file"""
        return os.path.join(self.notebooks_root, "notebooks_registry.json")

    def ensure_notebooks_root(self):
        if not os.path.exists(self.notebooks_root):
            os.makedirs(self.notebooks_root)
    
    def notebook_exists(self, notebook_name):
        """Check if notebook exists by name in registry ONLY"""
        registry_data = self.load_registry()
        for notebook_info in registry_data["notebooks"].values():
            if notebook_info["name"] == notebook_name:
                return True
        return False

    def save_notebook(self, notebook, folder_path=None, save_notes=True, save_files=True):
        # Use ops to save with selective file saving
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        return ops.save_notebook(notebook, folder_path, save_notes, save_files)
    
    def load_notebook_hierarchy(self, notebook, crypto=None):
        """Recursively load an encrypted notebook and all subnotebooks"""
        if not crypto and notebook.id in self.encrypted_notebooks:
            # Get crypto for this notebook
            crypto = self.session_keys.get(notebook.id)
            if not crypto:
                from crypto import Crypto
                folder_name = f"{notebook.name}-{notebook.id}"
                crypto = Crypto.retrieve_for_folder(folder_name)
    
        # Load this notebook's content if encrypted
        if crypto and notebook.id in self.encrypted_notebooks:
            loaded = self.load_notebook(notebook.name)
            if loaded:
                # Replace the notebook object with loaded one
                notebook.notes = loaded.notes
                notebook.subnotebooks = loaded.subnotebooks
    
        # Recursively load all subnotebooks
        for sub in notebook.subnotebooks:
            if sub.id in self.encrypted_notebooks:
                # Each subnotebook needs its own crypto (same key?)
                # For now, assume same key works for whole hierarchy
                self.load_notebook_hierarchy(sub, crypto)
    
        return notebook

    def _get_notebook_id(self, notebook_name):
        """Helper to get notebook ID from name"""
        for nb in self.notebooks:
            if nb.name == notebook_name:
                return nb.id
        return None

    def load_all_notebooks(self, quiet=True):
        """Load notebooks from registry - registry is the source of truth"""
        self.notebooks = []
        registry_data = self.load_registry()

        # ========== SURGICAL FIX: Track if this is first load ==========
        first_load = not hasattr(self, '_initial_load_complete')
        # ========== END FIX ==========

        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)

        def get_name_from_folder(nid):
            """Extract notebook name from folder name (format: name-{id})"""
            if os.path.exists(self.notebooks_root):
                for folder in os.listdir(self.notebooks_root):
                    if folder.endswith(nid):
                        if '-' in folder:
                            name_part = folder.rsplit('-', 1)[0]
                            return name_part
                        else:
                            return folder
            return None

        for notebook_id, entry in registry_data.get("notebooks", {}).items():
            notebook = None
            
            if isinstance(entry, str):
                crypto = self.session_keys.get(notebook_id)
                real_name = None
                is_locked = True
                folder_path = None
                autolock = False
                
                if not crypto:
                    from crypto import Crypto
                    from secure_session import SecureSessionStorage
                    
                    storage = SecureSessionStorage(self.app_dir)
                    stored_pw_key, stored_ph_key = storage.get_keys(notebook_id)
                    
                    if stored_pw_key and stored_ph_key:
                        from notebook_operations import decrypt_registry_entry
                        if isinstance(stored_pw_key, str):
                            stored_pw_key = stored_pw_key.encode()
                        if isinstance(stored_ph_key, str):
                            stored_ph_key = stored_ph_key.encode()

                        if len(stored_pw_key) == 32 and len(stored_ph_key) == 32:
                            temp_crypto = Crypto(stored_pw_key, stored_ph_key, "temp")
                            decrypted = decrypt_registry_entry(entry, temp_crypto)
                            
                            if decrypted:
                                real_name = decrypted.get("name")
                                is_locked = decrypted.get("locked", True)
                                autolock = decrypted.get("autolock", False)
                                folder_path = decrypted.get("path")
                                
                                if folder_path:
                                    if not os.path.isabs(folder_path):
                                        folder_path = os.path.join(self.notebooks_root, folder_path)
                                    folder_name = os.path.basename(folder_path)
                                    crypto = Crypto(stored_pw_key, stored_ph_key, folder_name)
                                    self.session_keys[notebook_id] = crypto
                
                if crypto and real_name is None:
                    from notebook_operations import decrypt_registry_entry
                    decrypted = decrypt_registry_entry(entry, crypto)
                    
                    if decrypted:
                        real_name = decrypted.get("name")
                        is_locked = decrypted.get("locked", True)
                        autolock = decrypted.get("autolock", False)
                        folder_path = decrypted.get("path")
                        
                        if folder_path and not os.path.isabs(folder_path):
                            folder_path = os.path.join(self.notebooks_root, folder_path)
                
                # REMOVED autolock force-lock from here
                
                if crypto and real_name:
                    if not is_locked and folder_path and os.path.exists(folder_path):
                        notebook = ops.load_notebook_from_path_with_crypto(folder_path, crypto)
                        if notebook:
                            notebook.name = real_name
                            notebook.custom_path = folder_path
                            notebook._crypto = crypto
                            notebook.locked = False
                            self.encrypted_notebooks.add(notebook_id)
                        else:
                            name_from_folder = get_name_from_folder(notebook_id)
                            final_name = name_from_folder if name_from_folder else real_name
                            notebook = Notebook(final_name, notebook_id=notebook_id)
                            notebook.locked = True
                            notebook.custom_path = None
                            notebook._crypto = None
                            self.encrypted_notebooks.add(notebook_id)
                    else:
                        name_from_folder = get_name_from_folder(notebook_id)
                        final_name = name_from_folder if name_from_folder else real_name
                        notebook = Notebook(final_name, notebook_id=notebook_id)
                        notebook.locked = True
                        notebook.custom_path = None
                        notebook._crypto = None
                        self.encrypted_notebooks.add(notebook_id)
                else:
                    name_from_folder = get_name_from_folder(notebook_id)
                    if name_from_folder:
                        final_name = name_from_folder
                    else:
                        final_name = f"Encrypted-{notebook_id[:8]}"
                    
                    notebook = Notebook(final_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    notebook._crypto = None
                    self.encrypted_notebooks.add(notebook_id)
            
            elif isinstance(entry, dict):
                name = entry.get("name")
                if not name:
                    if not quiet:
                        print(f"  ⚠ Registry entry for {notebook_id[:8]} has no name, skipping")
                    continue
            
                folder_path = entry.get("path")
                autolock = entry.get("autolock", False)
                
                if folder_path and not os.path.isabs(folder_path):
                    folder_path = os.path.join(self.notebooks_root, folder_path)
            
                if folder_path and os.path.exists(folder_path):
                    struct_file = os.path.join(folder_path, "structure.json")
                    if os.path.exists(struct_file):
                        try:
                            with open(struct_file, 'r') as f:
                                struct_data = json.load(f)
                        
                            files_file = os.path.join(folder_path, "files.json")
                            files_data = {}
                            if os.path.exists(files_file):
                                with open(files_file, 'r') as f:
                                    files_data = json.load(f)
                        
                            from terminal_notes_core import Notebook as TempNotebook
                            temp_nb = TempNotebook.from_dict(struct_data)
                        
                            notebook = Notebook(name, notebook_id=notebook_id)
                            notebook.custom_path = folder_path
                        
                            notebook.notes = []
                            for note in temp_nb.notes:
                                is_file = note.id in files_data
                                new_note = Note(note.title, "", note.id, note.created_with)
                                if is_file:
                                    new_note.file_extension = note.file_extension or 'txt'
                                new_note.created = note.created
                                new_note.updated = note.updated
                                notebook.notes.append(new_note)
                        
                            notebook.subnotebooks = temp_nb.subnotebooks
                            notebook.locked = False
                        
                        except Exception as e:
                            if not quiet:
                                print(f"  Error loading {name}: {e}")
                            notebook = Notebook(name, notebook_id=notebook_id)
                            notebook.custom_path = folder_path
                            notebook.locked = False
                    else:
                        notebook = Notebook(name, notebook_id=notebook_id)
                        notebook.custom_path = folder_path
                        notebook.locked = False
                else:
                    notebook = Notebook(name, notebook_id=notebook_id)
                    notebook.locked = False

            if notebook:
                self.notebooks.append(notebook)

        # ========== SURGICAL FIX: Apply autolock ONCE after all notebooks are loaded ==========
        if first_load:
            registry_updated = False
            for notebook in self.notebooks:
                if notebook.id in self.encrypted_notebooks:
                    # Check registry for autolock flag
                    entry = registry_data.get("notebooks", {}).get(notebook.id)
                    autolock = False
                    crypto = self.session_keys.get(notebook.id)
                    
                    if isinstance(entry, dict):
                        autolock = entry.get("autolock", False)
                    elif isinstance(entry, str) and crypto:
                        from notebook_operations import decrypt_registry_entry
                        decrypted = decrypt_registry_entry(entry, crypto)
                        if decrypted:
                            autolock = decrypted.get("autolock", False)
                    
                    if autolock:
                        # Lock the notebook
                        notebook.locked = True
                        notebook.custom_path = None
                        
                        # Clear session key from manager
                        if notebook.id in self.session_keys:
                            del self.session_keys[notebook.id]
                        
                        # Clear crypto from notebook object
                        if hasattr(notebook, '_crypto'):
                            delattr(notebook, '_crypto')
                        
                        # ========== CRITICAL: Update registry to locked = True ==========
                        if notebook.id in registry_data["notebooks"]:
                            entry = registry_data["notebooks"][notebook.id]
                            
                            if isinstance(entry, dict):
                                entry["locked"] = True
                                registry_updated = True
                            elif isinstance(entry, str) and crypto:
                                from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                                decrypted = decrypt_registry_entry(entry, crypto)
                                if decrypted:
                                    decrypted["locked"] = True
                                    new_entry = encrypt_registry_entry(decrypted, crypto)
                                    if new_entry:
                                        registry_data["notebooks"][notebook.id] = new_entry
                                        registry_updated = True
                        # ========== END CRITICAL ==========
            
            # Save registry if any updates were made
            if registry_updated:
                self.save_registry(registry_data)
            
            self._initial_load_complete = True
        # ========== END FIX ==========

        return self.notebooks
    
    def save_data(self):
        for notebook in self.notebooks:
            # 🟢 FIX: Skip locked notebooks entirely
            if notebook.id in self.encrypted_notebooks:
                if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                    continue  # Skip this notebook - it's locked
                
            # Get folder_path from the notebook or calculate it
            if hasattr(notebook, 'custom_path') and notebook.custom_path:
                folder_path = notebook.custom_path
            else:
                folder_path = notebook.custom_path
    
            self.save_notebook(notebook, folder_path)
            
    def find_notebook_by_id(self, notebook_id, notebooks=None):
        """Find notebook by ID recursively"""
        if notebooks is None:
            notebooks = self.notebooks

        for notebook in notebooks:
            if notebook.id == notebook_id:
                return notebook
            found = self.find_notebook_by_id(notebook_id, notebook.subnotebooks)
            if found:
                return found
        return None
            
    def delete_notebook(self, notebook_to_delete):
        """Delete notebook - delegated to ops"""
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        return ops.delete_notebook(notebook_to_delete)

    def find_note_by_id(self, notebook_id, note_id):
        def search_recursive(notebooks):
            for notebook in notebooks:
                for note in notebook.notes:
                    if note.id == note_id:
                        return note, notebook
                if notebook.subnotebooks:
                    found_note, found_notebook = search_recursive(notebook.subnotebooks)
                    if found_note:
                        return found_note, found_notebook
            return None, None

        if notebook_id:
            notebook = self.find_notebook_by_id(notebook_id)
            if notebook:
                for note in notebook.notes:
                    if note.id == note_id:
                        return note, notebook

        return search_recursive(self.notebooks)

    def get_notebook_hierarchy(self, notebook_id):
        def find_hierarchy(current_id, current_notebooks, current_path):
            for notebook in current_notebooks:
                if notebook.id == current_id:
                    return current_path + [notebook]
                found = find_hierarchy(
                    current_id, notebook.subnotebooks, current_path + [notebook]
                )
                if found:
                    return found
            return None

        return find_hierarchy(notebook_id, self.notebooks, [])
    
    def _apply_file_content_to_notebook(self, notebook, notes_map, files_map):
        """Delegate to ops - maintained for backward compatibility"""
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        ops._apply_file_content_to_notebook(notebook, notes_map, files_map)

    def get_total_note_count(self):
        count = 0
        for notebook in self.notebooks:
            count += notebook.get_total_note_count()
        return count

    def get_total_notebook_count(self):
        count = 0
        for notebook in self.notebooks:
            count += 1 + notebook.get_total_subnotebook_count()
        return count

    def get_git_manager(self, notebook):
        """Get or create Git manager for notebook - notebook MUST have custom_path"""
        if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
            raise ValueError(f"Notebook {notebook.name} has no custom_path set")
    
        folder_path = notebook.custom_path
    
        if folder_path not in self.git_managers:
            self.git_managers[folder_path] = GitManager(folder_path)
    
        return self.git_managers[folder_path]
    
    def get_git_manager_by_path(self, repo_path):
        """Get Git manager for a repository path"""
        from git_manager import GitManager
        if repo_path not in self.git_managers:
            self.git_managers[repo_path] = GitManager(repo_path)
        return self.git_managers[repo_path]
    
    # terminal_notes_core.py - Updated create_notebook method

    def create_notebook(self, name, custom_path=None, encrypt=False, phrase=None):
        """
        Create notebook with dual-key encryption (password + phrase).
        """
        from datetime import datetime
        import os
        from notebook_operations import NotebookOperations, write_json
        from crypto import Crypto, derive_key, generate_phrase
        from secure_session import SecureSessionStorage
        from getpass import getpass
        import subprocess
        import shutil

        datetime_stamp = datetime.now().strftime("%Y%g%d%H%M%S")
        notebook = Notebook(name, notebook_id=datetime_stamp)

        safe_folder = _safe_folder_name(name, notebook.id)
        folder_name = safe_folder

        if custom_path:
            base_path = os.path.expanduser(custom_path)
            folder_path = os.path.join(base_path, folder_name)
        else:
            folder_path = os.path.join(self.notebooks_root, folder_name)

        notebook.custom_path = folder_path

        # Handle encryption
        crypto = None
        recovery_phrase = phrase
        password = None
        password_key = None
        phrase_key = None

        if encrypt:
            # ========== STEP 1: TRUSTED SYSTEM NOTICE ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\n" + "─" * 60)
            print("  TRUSTED SYSTEM NOTICE")
            print("─" * 60)
            print()
            print("  🔐 This notebook will be TIED to THIS machine.")
            print()
            print("  • On THIS computer: unlock with your password only.")
            print("  • On ANOTHER computer: you will need the RECOVERY PHRASE.")
            print()
            print("  ⚠️  Without the recovery phrase, you CANNOT open this")
            print("     notebook on a different machine or after OS reinstall.")
            print()
            print("  ✅ The recovery phrase (next step) is your ONLY backup.")
            print()
            input("\n  Press Enter to continue...")
            # ========== END STEP 1 ==========
            
            # ========== STEP 2: FOLDER NAME IMPORTANCE ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\n" + "─" * 60)
            print("  ENCRYPTED NOTEBOOK SETUP")
            print("─" * 60)
            print()
            print("  📁 IMPORTANT: Folder Name = Notebook ID")
            print("     Your notebook will be stored in a folder named:")
            print(f"     \"{safe_folder}\"")
            print("     This folder name is part of the encryption key.")
            print("     Do NOT rename the folder after creation!")
            print()
            input("  Press Enter to continue...")
            # ========== END STEP 2 ==========
            
            # ========== STEP 3: MASTER PASSWORD ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\n" + "─" * 60)
            print("  MASTER PASSWORD")
            print("─" * 60)
            print()
            print("  This password will be used to unlock your notebook.")
            print("  • Choose a strong password (8+ characters recommended)")
            print("  • Mix uppercase, lowercase, numbers, and symbols")
            print("  • Don't use common words or personal information")
            print()
            
            attempts = 0
            max_attempts = 3
            password = None
            
            while attempts < max_attempts:
                password = getpass("  Master password: ")
                if not password:
                    attempts += 1
                    remaining = max_attempts - attempts
                    if remaining > 0:
                        print(f"\n  Password cannot be empty. {remaining} attempt(s) left.\n")
                    continue
                
                # Password strength meter
                strength_score = 0
                strength_feedback = []
                
                if len(password) >= 12:
                    strength_score += 3
                    strength_feedback.append("    ✓ Excellent length (12+ chars)")
                elif len(password) >= 8:
                    strength_score += 2
                    strength_feedback.append("    ✓ Good length (8-11 chars)")
                elif len(password) >= 6:
                    strength_score += 1
                    strength_feedback.append("    ⚠️  Minimum length (6-7 chars)")
                else:
                    strength_feedback.append("    ✗ Too short (<6 chars) - WEAK")
                
                has_upper = any(c.isupper() for c in password)
                has_lower = any(c.islower() for c in password)
                has_digit = any(c.isdigit() for c in password)
                has_symbol = any(not c.isalnum() for c in password)
                
                variety_count = sum([has_upper, has_lower, has_digit, has_symbol])
                
                if variety_count >= 4:
                    strength_score += 3
                    strength_feedback.append("    ✓ Excellent variety (upper+lower+number+symbol)")
                elif variety_count >= 3:
                    strength_score += 2
                    strength_feedback.append("    ✓ Good variety (mixed character types)")
                elif variety_count >= 2:
                    strength_score += 1
                    strength_feedback.append("    ⚠️  Limited variety")
                else:
                    strength_feedback.append("    ✗ Poor variety - WEAK")
                
                common_patterns = ['password', '123456', 'qwerty', 'admin', 'letmein', 'welcome']
                if password.lower() in common_patterns:
                    strength_score = 0
                    strength_feedback = ["    ✗ Common password detected - VERY WEAK"]
                
                if strength_score >= 6:
                    strength_level = "💪 STRONG"
                elif strength_score >= 4:
                    strength_level = "👍 GOOD"
                elif strength_score >= 2:
                    strength_level = "⚠️  WEAK"
                else:
                    strength_level = "🔴 VERY WEAK"
                
                print(f"\n  Password strength: {strength_level}")
                for fb in strength_feedback:
                    print(fb)
                
                if strength_score < 4:
                    print("\n  ⚠️  This password is weak and may be vulnerable to attacks.")
                    print("     Consider using a stronger password.")
                    proceed = input("     Continue with this password? [y/N]: ").strip().lower()
                    if proceed != 'y':
                        print("\n  Try again with a stronger password.\n")
                        password = None
                        attempts += 1
                        continue
                
                confirm = getpass("\n  Confirm password: ")
                if password == confirm:
                    break
                else:
                    attempts += 1
                    remaining = max_attempts - attempts
                    if remaining > 0:
                        print(f"\n  Passwords do not match. {remaining} attempt(s) left.\n")
            
            if not password:
                print("\n  No password provided. Cancelling notebook creation.")
                return None
            # ========== END STEP 3 ==========
            
            # ========== STEP 4: SECURITY REMINDER ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\n" + "─" * 60)
            print("  SECURITY REMINDER")
            print("─" * 60)
            print()
            print("  • The folder name is part of the encryption key")
            print("  • Do NOT rename the notebook folder")
            print("  • Backup your recovery phrase (next step)")
            print()
            input("  Press Enter to continue...")
            # ========== END STEP 4 ==========
            
            # ========== STEP 5: RECOVERY PHRASE ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print("\n" + "─" * 60)
            print("  RECOVERY PHRASE")
            print("─" * 60)
            print()
            print("  A recovery phrase can help you recover your notebook if you:")
            print("    • Forget your password")
            print("    • Move to a new computer")
            print("    • Your machine fingerprint changes")
            print()
            print("  The phrase is NOT stored anywhere. You must write it down.")
            print("  This is REQUIRED for encrypted notebooks.")
            print()
            input("  Press Enter to continue...")
            
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                print("\n" + "─" * 60)
                print("  CHOOSE PHRASE TYPE")
                print("─" * 60)
                print()
                print("  1) Auto-generate (random words)")
                print("  2) Use my own phrase")
                print()
                choice = input("  Choose [1-2]: ").strip()
                
                if not choice:
                    print("\n  Cancel notebook creation? [y/N]: ", end='')
                    confirm = input().strip().lower()
                    if confirm == 'y':
                        print("\n  Cancelled.")
                        return None
                    continue
                
                if choice == '1':
                    while True:
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print("\n" + "─" * 60)
                        print("  CHOOSE LENGTH")
                        print("─" * 60)
                        print()
                        print("  1) 8 words   (good for quick recovery)")
                        print("  2) 12 words  (standard, highly secure)")
                        print("  3) 16 words  (very secure)")
                        print("  4) 20 words  (paranoid)")
                        print("  5) 24 words  (maximum security)")
                        print()
                        len_choice = input("  Choose [1-5]: ").strip()
                        
                        if not len_choice:
                            print("\n  Cancel notebook creation? [y/N]: ", end='')
                            confirm = input().strip().lower()
                            if confirm == 'y':
                                print("\n  Cancelled.")
                                return None
                            continue
                        
                        word_count_map = {'1': 8, '2': 12, '3': 16, '4': 20, '5': 24}
                        if len_choice in word_count_map:
                            word_count = word_count_map[len_choice]
                            break
                        else:
                            print("\n  Invalid choice. Please enter 1, 2, 3, 4, or 5.\n")
                            input("  Press Enter to continue...")
                    
                    recovery_phrase = generate_phrase(word_count)
                    
                    os.system('clear' if os.name == 'posix' else 'cls')
                    print("\n" + "─" * 60)
                    print("  YOUR RECOVERY PHRASE")
                    print("─" * 60)
                    print()
                    print(f"  {recovery_phrase}")
                    print()
                    print("  Store this phrase safely!")
                    print()
                    print("  • Write it down on paper")
                    print("  • Save it in a password manager")
                    print("  • Take a photo (store securely)")
                    print()
                    print("  [Y] Yes, I've saved it  [C] Copy to clipboard")
                    print()
                    
                    while True:
                        copy_choice = input("  > ").strip().lower()
                        
                        if copy_choice == 'y':
                            print("\n  Press Enter when you have written it down.")
                            input()
                            break
                        
                        elif copy_choice == 'c':
                            copied = False
                            method_used = None
                            
                            for cmd_name, cmd_args in [
                                ('pbcopy', ['pbcopy']),
                                ('clip', ['clip']),
                                ('xclip', ['xclip', '-selection', 'clipboard']),
                                ('wl-copy', ['wl-copy']),
                                ('xsel', ['xsel', '-i', '-b'])
                            ]:
                                if not copied and shutil.which(cmd_args[0]):
                                    try:
                                        proc = subprocess.Popen(cmd_args, stdin=subprocess.PIPE)
                                        proc.communicate(input=recovery_phrase.encode())
                                        copied = True
                                        method_used = cmd_args[0]
                                    except:
                                        pass
                            
                            if copied:
                                print(f"\n  Copied to clipboard using {method_used}!")
                                print("     Paste it into your password manager.")
                            else:
                                print("\n  Could not copy automatically.")
                                print("     Please copy manually.")
                            
                            print("\n  Press Enter when you have saved it.")
                            input()
                            break
                        
                        else:
                            print("\n  Invalid choice. Press [Y] for yes or [C] to copy.")
                    
                    break
                    
                elif choice == '2':
                    while True:
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print("\n" + "─" * 60)
                        print("  CREATE YOUR RECOVERY PHRASE")
                        print("─" * 60)
                        print()
                        print("  Your recovery phrase is the ONLY way to recover this notebook.")
                        print()
                        print("  REQUIREMENTS:           |  EXAMPLES:                          ")
                        print("  • 20+ characters        |  ✓ My! dog Fluffy ate 3 socks       ")
                        print("  • 4+ words recommended  |  ✓ Purple@monkey dishwasher 2024!   ")
                        print("  • Memorable & hard guess|  ✓ Cats & dogs are 2+2=4 ever!      ")
                        print("  • Add symbols & numbers |  ✓ 🐶 My dog ate 3 🍕 yesterday!     ")
                        print("  • Mix cases & misspell  |                                     ")
                        print("  • Use emojis 🐱 🎉 💪    |  ✗ password123 (too short)          ")
                        print("                           |  ✗ my secret phrase (3 words)      ")
                        print("                           |  ✗ aaaaaaaaaaaa (same char)        ")
                        print()
                        print("  TIPS: Add @ # $ % ! & + = ? | Numbers | Mixed case | Emojis 🐶")
                        print()
                        
                        recovery_phrase = input("  Enter your recovery phrase: ").strip()
                        
                        if not recovery_phrase:
                            print("\n  Cancel notebook creation? [y/N]: ", end='')
                            confirm = input().strip().lower()
                            if confirm == 'y':
                                print("\n  Cancelled.")
                                return None
                            continue
                        
                        if len(recovery_phrase) < 20:
                            print(f"\n  Too short ({len(recovery_phrase)}/20 characters)")
                            print("     Add more words or characters.")
                            input("\n  Press Enter to continue...")
                            continue
                        
                        if len(set(recovery_phrase.replace(' ', ''))) == 1:
                            print("\n  Too simple! All characters are the same.")
                            input("\n  Press Enter to continue...")
                            continue
                        
                        # Calculate strength
                        score = 0
                        feedback = []
                        
                        if len(recovery_phrase) >= 40:
                            score += 3
                            feedback.append("  Excellent length (40+ chars)")
                        elif len(recovery_phrase) >= 30:
                            score += 2
                            feedback.append("  Good length (30-39 chars)")
                        elif len(recovery_phrase) >= 20:
                            score += 1
                            feedback.append("  Acceptable length (20-29 chars)")
                        
                        words = recovery_phrase.split()
                        if len(words) >= 8:
                            score += 2
                            feedback.append("  Many words (8+)")
                        elif len(words) >= 5:
                            score += 1
                            feedback.append("  Multiple words (5-7)")
                        elif len(words) >= 4:
                            feedback.append("  Only 4 words - consider adding more")
                        else:
                            feedback.append("  Few words (<4) - less secure")
                        
                        has_upper = any(c.isupper() for c in recovery_phrase)
                        has_digit = any(c.isdigit() for c in recovery_phrase)
                        has_symbol = any(not c.isalnum() and not c.isspace() for c in recovery_phrase)
                        symbol_count = sum(1 for c in recovery_phrase if not c.isalnum() and not c.isspace())
                        
                        if has_upper:
                            score += 1
                            feedback.append("  Has uppercase letters")
                        if has_digit:
                            score += 1
                            feedback.append("  Has numbers")
                        if has_symbol:
                            score += 2
                            feedback.append(f"  Has symbols ({symbol_count} found) - Excellent!")
                        else:
                            feedback.append("  Tip: Add symbols (@, #, $, %, !, &, +, =, ?)")
                        
                        if ' ' not in recovery_phrase:
                            feedback.append("  Warning: Single word is less secure")
                            confirm = input("\n     Continue anyway? [y/N]: ").strip().lower()
                            if confirm != 'y':
                                continue
                        
                        if score >= 8:
                            strength = "EXCELLENT"
                        elif score >= 6:
                            strength = "GOOD"
                        elif score >= 4:
                            strength = "ACCEPTABLE"
                        else:
                            strength = "WEAK - Not recommended"
                        
                        print(f"\n  PHRASE STRENGTH: {strength}")
                        for fb in feedback:
                            print(f"  {fb}")
                        print(f"  Total characters: {len(recovery_phrase)}")
                        print(f"  Total words: {len(words)}")
                        
                        if not has_symbol and score >= 4:
                            print("\n  PRO TIP: Adding symbols would make this phrase EXCELLENT!")
                        
                        if score < 5:
                            print("\n  This phrase is WEAK and may be vulnerable to attacks.")
                            confirm = input("     Use it anyway? [y/N]: ").strip().lower()
                            if confirm != 'y':
                                continue
                        else:
                            confirm = input("\n  Use this recovery phrase? [Y/n]: ").strip().lower()
                            if confirm == 'n':
                                continue
                        
                        # Display final phrase
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print("\n" + "─" * 60)
                        print("  YOUR RECOVERY PHRASE")
                        print("─" * 60)
                        print()
                        print(f"  {recovery_phrase}")
                        print()
                        print("  Store this phrase safely!")
                        print()
                        print("  • Write it down on paper")
                        print("  • Save it in a password manager")
                        print("  • Take a photo (store securely)")
                        print()
                        print("  [Y] Yes, I've saved it  [C] Copy to clipboard")
                        print()
                        
                        while True:
                            copy_choice = input("  > ").strip().lower()
                            
                            if copy_choice == 'y':
                                print("\n  Press Enter when you have written it down.")
                                input()
                                break
                            
                            elif copy_choice == 'c':
                                copied = False
                                method_used = None
                                
                                for cmd_name, cmd_args in [
                                    ('pbcopy', ['pbcopy']),
                                    ('clip', ['clip']),
                                    ('xclip', ['xclip', '-selection', 'clipboard']),
                                    ('wl-copy', ['wl-copy']),
                                    ('xsel', ['xsel', '-i', '-b'])
                                ]:
                                    if not copied and shutil.which(cmd_args[0]):
                                        try:
                                            proc = subprocess.Popen(cmd_args, stdin=subprocess.PIPE)
                                            proc.communicate(input=recovery_phrase.encode())
                                            copied = True
                                            method_used = cmd_args[0]
                                        except:
                                            pass
                                
                                if copied:
                                    print(f"\n  Copied to clipboard using {method_used}!")
                                    print("     Paste it into your password manager.")
                                else:
                                    print("\n  Could not copy automatically.")
                                    print("     Please copy manually.")
                                
                                print("\n  Press Enter when you have saved it.")
                                input()
                                break
                            
                            else:
                                print("\n  Invalid choice. Press [Y] for yes or [C] to copy.")
                        
                        break
                    break
                else:
                    print("\n  Invalid choice. Please enter 1 or 2.")
                    input("  Press Enter to continue...")
            # ========== END STEP 5 ==========
            
            # Create crypto with dual-key system
            folder_name = os.path.basename(folder_path)
            crypto = Crypto.from_password_and_phrase(password, recovery_phrase, folder_name)
            
            # Extract keys
            password_key = crypto.password_key
            phrase_key = crypto.phrase_key
            
            # Store in session memory
            self.session_keys[notebook.id] = crypto
            self.encrypted_notebooks.add(notebook.id)

        # Create folder
        os.makedirs(folder_path, exist_ok=True)

        # Create all three files
        struct_file = os.path.join(folder_path, "structure.json")
        notes_file = os.path.join(folder_path, "notes.json")
        files_file = os.path.join(folder_path, "files.json")

        # Write structure
        write_json(struct_file, notebook.to_dict(), crypto)

        # Write empty content files
        write_json(notes_file, {}, crypto)
        write_json(files_file, {}, crypto)

        # If encrypted, create encryption files
        if encrypt and crypto:
            crypto.create_test_marker(os.path.join(folder_path, ".tn_test"))
            
            # Create recovery files
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            password_key = derive_key(password, folder_name)
            crypto.create_recovery_file(os.path.join(folder_path, ".tn_recovery"), password_hash, password_key)
            crypto.create_password_file(os.path.join(folder_path, ".tn_password"))
            
            # Store keys in secure session
            storage = SecureSessionStorage(self.app_dir)
            storage.store_keys(notebook.id, password_key, phrase_key)

        # Initialize Git
        try:
            git_manager = self.get_git_manager(notebook)
            git_manager.init_repo(notebook.name, custom_path=bool(custom_path))
            
            # Add ALL files
            git_manager._run_git_command(["git", "add", "structure.json"])
            git_manager._run_git_command(["git", "add", "notes.json"])
            git_manager._run_git_command(["git", "add", "files.json"])
            if encrypt and crypto:
                git_manager._run_git_command(["git", "add", ".tn_test"])
                git_manager._run_git_command(["git", "add", ".tn_recovery"])
                git_manager._run_git_command(["git", "add", ".tn_password"])
            
            # Initial commit
            git_manager.commit_notebook_creation(
                notebook.id, notebook.name, 0, 0, custom_path=custom_path
            )
            
        except Exception as e:
            print(f"  ⚠ Git init failed: {e}")

        # Register in registry
        self.register_notebook(notebook, folder_path)

        if encrypt and crypto:
            registry_data = self.load_registry()
            if notebook.id in registry_data["notebooks"]:
                entry = registry_data["notebooks"][notebook.id]
                if isinstance(entry, dict):
                    entry["locked"] = False
                    self.save_registry(registry_data)
                elif isinstance(entry, str):
                    from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                    decrypted = decrypt_registry_entry(entry, crypto)
                    if decrypted:
                        decrypted["locked"] = False
                        new_entry = encrypt_registry_entry(decrypted, crypto)
                        if new_entry:
                            registry_data["notebooks"][notebook.id] = new_entry
                            self.save_registry(registry_data)

            notebook.locked = False
            notebook._crypto = crypto

        self.notebooks.append(notebook)

        print(f"\n  Notebook created successfully!")
        print(f"   Name: {name}")
        print(f"   Folder: {folder_name}")
        print(f"   Location: {folder_path}")
        if encrypt:
            print(f"   🔐 Encrypted with password + recovery phrase")
            print(f"   Recovery phrase saved - store it safely!")

        self._just_created = True
        return notebook
    
    def create_note(self, notebook, title, content, created_with="internal"):
        """Create a new note - delegated to ops (handles crypto & git)"""
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        return ops.create_note(notebook, title, content, created_with)

    def edit_note(self, note, notebook, new_content):
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        ops.edit_note(note, notebook, new_content)

    def delete_note(self, note, notebook, delete_type='forget'):
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        ops.delete_note(note, notebook, delete_type)

    def rename_note(self, note, notebook, new_title):
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        ops.rename_note(note, notebook, new_title)

    def create_file_note(self, notebook, filename, content, extension):
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        return ops.create_file(notebook, filename, content, extension)
                
    # ADD THIS NEW METHOD (replaces the old one)
    def get_notebook_file_paths(self, notebook):
        """Get file paths - notebook MUST have custom_path set from registry"""
        if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
            raise ValueError(f"Notebook {notebook.name} has no custom_path set!")
    
        folder_path = notebook.custom_path
        return (
            os.path.join(folder_path, "structure.json"),
            os.path.join(folder_path, "notes.json"),
            os.path.join(folder_path, "files.json")
        )

    
    def find_notebook_by_name(self, name):
        """Find notebook by name (exact match, with or without lock icon)"""
        search_names = [name, name.replace('🔐 ', ''), f"🔐 {name.replace('🔐 ', '')}"]
    
        for notebook in self.notebooks:
            if notebook.name in search_names:
                return notebook
        return None

    def save_registry(self, registry_data):
        """Save registry with atomic write"""
        registry_file = self.get_registry_file()
        temp_file = registry_file + '.tmp'

        from notebook_operations import encrypt_registry_entry

        encrypted_registry = {"notebooks": {}}

        for nb_id, entry in registry_data.get("notebooks", {}).items():
            if isinstance(entry, str):
                encrypted_registry["notebooks"][nb_id] = entry
                continue
        
            notebook = self.find_notebook_by_id(nb_id)
            is_encrypted = nb_id in self.encrypted_notebooks
        
            if is_encrypted and nb_id in self.session_keys:
                crypto = self.session_keys[nb_id]
            
                clean_entry = {
                    "name": entry.get("name", ""),
                    "path": entry.get("path", ""),
                    "encrypted": True,
                    "locked": entry.get("locked", False)
                }
            
                encrypted = encrypt_registry_entry(clean_entry, crypto)
                if encrypted:
                    encrypted_registry["notebooks"][nb_id] = encrypted
                else:
                    encrypted_registry["notebooks"][nb_id] = clean_entry
        
            elif is_encrypted:
                encrypted_registry["notebooks"][nb_id] = {
                    "name": entry.get("name", "Unknown"),
                    "encrypted": True,
                    "locked": True
                }
            else:
                encrypted_registry["notebooks"][nb_id] = {
                    "name": entry.get("name", ""),
                    "path": entry.get("path", ""),
                    "encrypted": False,
                    "locked": False
                }

        try:
            with open(temp_file, 'w') as f:
                json.dump(encrypted_registry, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        
            os.rename(temp_file, registry_file)
            return True
        except Exception as e:
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return False

    def load_registry(self):
        """Load the notebook registry"""
        registry_file = self.get_registry_file()
    
        if not os.path.exists(registry_file):
            return {"notebooks": {}}
    
        try:
            with open(registry_file, 'r') as f:
                registry_data = json.load(f)
            return registry_data
        except Exception as e:
            print(f"Error loading registry: {e}")
            return {"notebooks": {}}
    
    def register_notebook(self, notebook, folder_path, is_import=False):
        """Register a notebook - ONLY for root notebooks!"""
        
        # ========== SURGICAL FIX: Never register subnotebooks ==========
        if notebook.parent_id is not None:
            print(f"  ⚠ Skipping registry for subnotebook: {notebook.name}")
            return
        # ========== END FIX ==========
        registry_data = self.load_registry()

        if folder_path.startswith(self.notebooks_root):
            rel_path = os.path.relpath(folder_path, self.notebooks_root)
        else:
            rel_path = folder_path

        clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
        is_encrypted = notebook.id in self.encrypted_notebooks

        # NEWLY CREATED notebooks should start unlocked
        if is_import and is_encrypted:
            is_locked = True
        else:
            is_locked = False

        entry_data = {
            "name": clean_name,
            "path": rel_path,
            "encrypted": is_encrypted,
            "locked": is_locked,
            "created": datetime.now().isoformat()
        }
                
        if is_encrypted:
            from notebook_operations import encrypt_registry_entry
            crypto = self.session_keys.get(notebook.id)
            if crypto:
                encrypted_entry = encrypt_registry_entry(entry_data, crypto)
                if encrypted_entry:
                    registry_data["notebooks"][notebook.id] = encrypted_entry
                else:
                    registry_data["notebooks"][notebook.id] = entry_data
            else:
                registry_data["notebooks"][notebook.id] = entry_data
        else:
            registry_data["notebooks"][notebook.id] = entry_data

        self.save_registry(registry_data)
        
    def unregister_notebook(self, notebook_id):
        """Remove a notebook from the registry and clean up its session key"""
        registry_data = self.load_registry()

        if notebook_id in registry_data["notebooks"]:
            # Get the folder name before deleting
            notebook = self.find_notebook_by_id(notebook_id)
            folder_name = None
            if notebook:
                if hasattr(notebook, 'custom_path') and notebook.custom_path:
                    folder_name = os.path.basename(notebook.custom_path)
                else:
                    clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
                    folder_name = f"{clean_name}-{notebook.id}"
            
            # Remove from session keys
            if notebook_id in self.session_keys:
                del self.session_keys[notebook_id]
            
            # ========== SURGICAL FIX: Remove from permanent storage (try both formats) ==========
            if self.secure_storage:
                # Try notebook_id first (current format)
                if not self.secure_storage.remove_session_key(notebook_id):
                    # Fallback to folder_name (legacy format)
                    if folder_name:
                        self.secure_storage.remove_session_key(folder_name)
            # ========== END FIX ==========
            
            del registry_data["notebooks"][notebook_id]
            self.save_registry(registry_data)

    def create_subnotebook(self, parent_notebook, name):
        """Create subnotebook - ONLY modifies structure.json, NO folder"""
        subnotebook = Notebook(name, parent_id=parent_notebook.id)
        parent_notebook.subnotebooks.append(subnotebook)

        # ========== CRITICAL: Ensure no custom_path for subnotebook ==========
        subnotebook.custom_path = None
        # ========== END CRITICAL ==========

        root_notebook = self._find_root_notebook(parent_notebook)
        
        # Save ONLY structure.json of the root
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
        ops.save_notebook(root_notebook, save_notes=False, save_files=False)

        # Git commit
        try:
            git_manager = self.get_git_manager(root_notebook)
            git_manager.commit_subnotebook_creation(
                subnotebook.id, name, parent_notebook, 0, root_uuid=root_notebook.id
            )
        except Exception:
            pass

        return subnotebook

    def _find_root_notebook(self, notebook):
        """Find the root notebook for any nested notebook"""
        current = notebook
        while current.parent_id:
            current = self.find_notebook_by_id(current.parent_id)
            if not current:
                break
        return current
    
    def notebook_exists_by_path(self, folder_path):
        """Check if path already registered - registry is source of truth"""
        registry_data = self.load_registry()
        normalized_path = self.normalize_path_for_comparison(folder_path)
    
        for notebook_id, notebook_info in registry_data["notebooks"].items():
            # Skip encrypted string entries (can't check path without decrypting)
            if isinstance(notebook_info, str):
                continue
        
            # Check dictionary entries
            if isinstance(notebook_info, dict):
                registered_path = notebook_info.get("path", "")
                if registered_path:
                    full_registered_path = registered_path
                    if not os.path.isabs(registered_path):
                        full_registered_path = os.path.join(self.notebooks_root, registered_path)
                
                    if self.normalize_path_for_comparison(full_registered_path) == normalized_path:
                        return True
        return False

    def normalize_path_for_comparison(self, path):
        """Normalize path for cross-platform comparison"""
        if not path:
            return ""
        expanded = os.path.expanduser(path)
        absolute = os.path.abspath(expanded)
        normalized = os.path.normcase(absolute)
        return normalized
    
    def get_notebook_metadata(self, notebook_id):
        notebook = self.find_notebook_by_id(notebook_id)
        if not notebook:
            return None
    
        # Use ops to get metadata
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self)
    
        return ops.get_notebook_metadata(notebook_id)
   
class SimpleNav:
    """One stack to rule them all - follows the single path"""

    def __init__(self):
        self.stack = []
        self.jump_history = []

    def push(self, screen, nav_id=None, page=0):
        """Move deeper into the tree"""
        self.stack.append(
            {"screen": screen, "id": nav_id, "page": page}
        )

    def pop(self):
        """Move up toward root"""
        if len(self.stack) > 1:
            return self.stack.pop()
        return None

    def current(self):
        """Current location in the tree"""
        return self.stack[-1] if self.stack else None

    def replace_page(self, page):
        """Stay at same tree node, just change page"""
        if self.stack:
            self.stack[-1]["page"] = page

    def clear(self):
        """Reset navigation"""
        self.stack = []

    def save_jump_position(self):
        """Save current position to jump history"""
        if not hasattr(self, "jump_history"):
            self.jump_history = []
        if self.stack:
            self.jump_history.append(self.stack.copy())
            if len(self.jump_history) > 20:
                self.jump_history.pop(0)

    def jump_back(self):
        """Jump back to previous position"""
        if not hasattr(self, "jump_history"):
            self.jump_history = []
        if self.jump_history:
            previous_position = self.jump_history.pop()
            self.stack = previous_position
            self.replace_page(0)
            return self.current()
        return None