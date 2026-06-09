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
import socket
import uuid as uuid_lib
from session_key_vault import SessionKeyVault
from typing import Optional, Tuple, Dict, List
from vault_manager import VaultManager

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
        if hasattr(self, 'vault_id') and self.vault_id:
            data["vault_id"] = self.vault_id  # ← NEW
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
        if "vault_id" in data:  # ← NEW
            notebook.vault_id = data["vault_id"]
        if "_crypto" in data:
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
        self.session_keys = SessionKeyVault(self)
        
        # Initialize vault helper
        self._search_loaded = False
        self._crypto = None
        self._registry_cache = None

        # Initialize secure session storage
        self.secure_storage = None
        if HAS_SECURE_STORAGE:
            try:
                if custom_config_dir:
                    self.secure_storage = SecureSessionStorage(custom_config_dir)
                else:
                    self.secure_storage = SecureSessionStorage(self.app_dir)
                self._load_all_stored_keys()
                self._load_session_keys_from_storage()
            except Exception as e:
                print(f"⚠ Could not initialize secure storage: {e}")
        
        # ========== FIX: Initialize vault_manager ==========
        from vault_manager import VaultManager
        self.vault_manager = VaultManager(self.app_dir)
        
        # 🆕 ENSURE VAULT REGISTRY EXISTS
        self._ensure_vault_registry_exists()
        # ========== END FIX ==========

        self.load_all_notebooks()
        self._just_created = False
    
    def _ensure_vault_registry_exists(self):
        """Ensure vault registry exists with default entry"""
        from vault_manager import VaultManager
        
        # Check if any vaults exist in registry
        vault_registry = self.vault_manager.load_vault_registry()
        
        # If no vaults registered OR default vault missing, create default
        if not vault_registry.get("vaults") or "default" not in vault_registry.get("vaults", {}):
            default_dir = os.path.join(self.app_dir, "config")
            os.makedirs(default_dir, exist_ok=True)
            default_path = os.path.join(default_dir, "session.vault")
            
            # Check if vault file exists or create it
            if os.path.exists(default_path):
                # File exists but not in registry - re-register it
                self.vault_manager.set_vault_path("default", default_path)
            else:
                # Create new vault file and registry entry
                self.vault_manager.create_vault_file("default", default_dir)

    def _load_all_stored_keys(self):
        """Load ALL stored keys from permanent storage at startup"""
        if not self.secure_storage:
            return

        try:
            stored_notebooks = self.secure_storage.list_stored_notebooks()
            
            # If no stored notebooks or not a dict, just return silently
            if not stored_notebooks or not isinstance(stored_notebooks, dict):
                return
            
            for folder_name, metadata in stored_notebooks.items():
                if isinstance(folder_name, str) and '-' in folder_name:
                    notebook_id = folder_name.split('-')[-1]
                    from crypto import Crypto
                    crypto = Crypto.retrieve_for_folder(folder_name)
                    if crypto:
                        self.session_keys[notebook_id] = crypto
                        self.encrypted_notebooks.add(notebook_id)
        except Exception:
            # Silently ignore any errors - fresh start
            pass
    
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
        """Unload a notebook's content when locked (keeps vault entry intact)"""
        notebook = self.find_notebook_by_id(notebook_id)
        if notebook:
            print(f"  Unloading: {notebook.name}")
            notebook.notes = []
            notebook.subnotebooks = []
            notebook.locked = True
            notebook.custom_path = None
            notebook._notes_loaded = False
            # Remove from session keys (cached crypto)
            if notebook_id in self.session_keys:
                del self.session_keys[notebook_id]
            # Clear SessionKeyVault cache
            if hasattr(self.session_keys, 'clear_cache'):
                self.session_keys.clear_cache(notebook_id)
            # DO NOT delete from vault - keep the entry for future unlocks
            
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
        from notebook_operations import find_notebook_folder
        from getpass import getpass
        from crypto import derive_key
        import time
        import uuid as uuid_lib
        import socket
        from datetime import datetime

        # Find the notebook
        notebook = self.find_notebook_by_id(notebook_id)
        if not notebook:
            return None

        # Check if notebook is encrypted
        if notebook_id not in self.encrypted_notebooks:
            return None

        # Get system entry from master registry
        fp_hash = self._compute_fp_hash()
        registry = self.load_registry(force_reload=True)
        
        notebook_data = registry.get("notebooks", {}).get(notebook_id)
        system_entry = None
        if notebook_data:
            system_entry = notebook_data.get("systems", {}).get(fp_hash)
        
        if not system_entry:
            return None
        
        # Get vault path and entry UUID
        vault_name = system_entry.get("vault", "default")
        entry_uuid = system_entry.get("entry")
        vault_path = self.vault_manager.get_vault_path(vault_name)
        
        is_custom_vault = vault_name != "default"
        
        # Read lock state directly from master registry
        is_locked = system_entry.get("locked", True)

        if is_locked or not hasattr(notebook, 'custom_path') or not notebook.custom_path:
            
            # Clear any stale session key
            if notebook_id in self.session_keys:
                del self.session_keys[notebook_id]
            
            clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
            folder_name = f"{clean_name}-{notebook_id}"
            
            # Get folder path
            folder_path = None
            if system_entry:
                folder_path = system_entry.get("path")
                if folder_path and not os.path.isabs(folder_path):
                    folder_path = os.path.join(self.notebooks_root, folder_path)

            if not folder_path or not os.path.exists(folder_path):
                folder_path = find_notebook_folder(notebook_id, self.notebooks_root)

            if not folder_path or not os.path.exists(folder_path):
                print(f"❌ Cannot find notebook folder for {notebook.name}")
                return None

            # ========== FIX: Use actual folder name from filesystem ==========
            actual_folder_name = os.path.basename(folder_path)
            # Extract the name part (remove the timestamp suffix)
            if '-' in actual_folder_name:
                name_part = actual_folder_name.rsplit('-', 1)[0]
            else:
                name_part = actual_folder_name
            # Reconstruct the folder_name as it was during creation
            folder_name = f"{name_part}-{notebook_id}"
            # ========== END FIX ==========
            
            # Check if vault exists - if not, offer recovery options
            if not vault_path or not os.path.exists(vault_path):
                self._invalidate_all_crypto(notebook_id)
                
                retry_count = 0
                max_retries = 3
                
                while retry_count < max_retries:
                    if is_custom_vault:
                        print(f"\n  ❌ Custom vault is configured but missing")
                        print(f"     Notebook has vault: {vault_name}")
                        print(f"     Expected location: {vault_path}")
                    else:
                        print(f"\n  ❌ Vault file not found: {vault_path}")
                        print(f"     This notebook uses the default vault.")
                    
                    print("     This notebook requires the vault file to unlock.")
                    print("     Please insert the USB drive or locate the vault file.")
                    print()
                    print("  Options:")
                    print("    1) Retry (I've inserted the USB drive)")
                    print("    2) Locate vault file manually")
                    print("    3) Use recovery phrase (will create new vault)")
                    print("    4) Cancel")
                    print()
                    
                    try:
                        choice = input("  Choose [1-4]: ").strip()
                    except:
                        choice = "4"
                    
                    if choice == "1":
                        retry_count += 1
                        if vault_name == "default":
                            vault_path = os.path.join(self.app_dir, "config", "session.vault")
                        else:
                            from vault_manager import VaultManager
                            vm = VaultManager(self.app_dir)
                            vm.reload()
                            vault_path = vm.get_vault_path(vault_name)
                        
                        if vault_path and os.path.exists(vault_path):
                            print("\n  ✓ Vault found! Continuing with unlock...")
                            break
                        else:
                            remaining = max_retries - retry_count
                            if remaining > 0:
                                print(f"\n  ⚠️ Vault still not found. {remaining} attempt(s) remaining.")
                            continue
                    
                    elif choice == "2":
                        new_location = input("  Enter vault file path: ").strip()
                        if new_location and os.path.exists(new_location):
                            from vault_manager import VaultManager
                            vm = VaultManager(self.app_dir)
                            vault_id_from_file = vm.get_vault_id_from_file(new_location)
                            if vault_id_from_file:
                                self._update_system_entry(notebook_id, {
                                    "path": system_entry.get("path") if system_entry else folder_path,
                                    "vault": vault_id_from_file,
                                    "entry": system_entry.get("entry") if system_entry else None,
                                    "locked": True
                                })
                                vault_name = vault_id_from_file
                                vault_path = new_location
                            else:
                                new_vault_name = f"vault_{uuid_lib.uuid4().hex[:8]}"
                                new_vault_path = self.vault_manager.create_vault_file(new_vault_name, os.path.dirname(new_location))
                                self._update_system_entry(notebook_id, {
                                    "path": system_entry.get("path") if system_entry else folder_path,
                                    "vault": new_vault_name,
                                    "entry": system_entry.get("entry") if system_entry else None,
                                    "locked": True
                                })
                                vault_name = new_vault_name
                                vault_path = new_vault_path
                            print("  ✓ Vault location updated. Please try again.")
                            input("\nPress Enter to continue...")
                            registry = self.load_registry(force_reload=True)
                            notebook_data = registry.get("notebooks", {}).get(notebook_id)
                            system_entry = notebook_data.get("systems", {}).get(fp_hash) if notebook_data else None
                            entry_uuid = system_entry.get("entry") if system_entry else None
                            continue
                        else:
                            print("  ✗ Invalid vault path.")
                            continue
                    
                    elif choice == "3":
                        break
                    
                    else:
                        return None
                
                if retry_count >= max_retries and (not vault_path or not os.path.exists(vault_path)):
                    print("\n  Too many retries. Please try again later.")
                    input("\nPress Enter to continue...")
                    return None
            
            # Get keys from vault by UUID
            if entry_uuid and vault_path and os.path.exists(vault_path):
                entry_data = self.vault_manager.get_entry_from_vault(vault_path, entry_uuid)
                if entry_data:
                    fingerprint = self._get_system_fingerprint()
                    try:
                        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                        nonce = bytes.fromhex(entry_data["nonce"])
                        encrypted_keys = bytes.fromhex(entry_data["encrypted_keys"])
                        aesgcm = AESGCM(fingerprint)
                        decrypted = aesgcm.decrypt(nonce, encrypted_keys, None)
                        stored_pw_key = decrypted[:32]
                        stored_ph_key = decrypted[32:64]
                        
                        # Prompt for password
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
                        
                        crypto = Crypto(stored_pw_key, stored_ph_key, folder_name)
                        test_file = os.path.join(folder_path, ".tn_test")
                        if not crypto.verify_test_marker(test_file):
                            return None
                        
                        # Unlock notebook - update registry to unlocked
                        self._update_system_entry(notebook_id, {
                            "path": system_entry.get("path") if system_entry else folder_path,
                            "vault": vault_name,
                            "entry": entry_uuid,
                            "locked": False
                        })
                        
                        # Store in session cache (RAM)
                        self.session_keys._cache[notebook_id] = crypto
                        notebook.custom_path = folder_path
                        notebook._crypto = crypto
                        notebook.locked = False
                        
                        return crypto
                        
                    except Exception:
                        pass
            
            # Recovery phrase flow
            if vault_path and os.path.exists(vault_path):
                storage = SecureSessionStorage(self.app_dir, vault_path=vault_path)
            else:
                storage = SecureSessionStorage(self.app_dir)
            
            password_key, phrase_key = storage.get_keys_with_verification(
                notebook_id, folder_path, folder_name
            )
            
            if password_key is None or phrase_key is None:
                return None
            
            crypto = Crypto(password_key, phrase_key, folder_name)
            test_file = os.path.join(folder_path, ".tn_test")
            if not crypto.verify_test_marker(test_file):
                return None
            
            # Create new vault entry for this system
            fingerprint = self._get_system_fingerprint()
            combined_keys = password_key + phrase_key
            nonce = os.urandom(12)
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(fingerprint)
            encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
            
            new_entry_uuid = str(uuid_lib.uuid4())
            
            if not vault_path or not os.path.exists(vault_path):
                vault_path = self.vault_manager.ensure_default_vault()
                vault_name = "default"
            
            self.vault_manager.add_entry_to_vault(vault_path, new_entry_uuid, {
                "notebook_id": notebook_id,
                "timestamp": time.time_ns(),
                "nonce": nonce.hex(),
                "encrypted_keys": encrypted_keys.hex()
            })
            
            registry = self.load_registry(force_reload=True)
            if notebook_id not in registry.get("notebooks", {}):
                registry["notebooks"][notebook_id] = {
                    "name": notebook.name,
                    "folder_name": os.path.basename(folder_path),
                    "created": datetime.now().isoformat(),
                    "systems": {}
                }
            
            if fp_hash not in registry.get("system_index", {}):
                registry["system_index"][fp_hash] = socket.gethostname()
            
            if folder_path.startswith(self.notebooks_root):
                stored_path = os.path.relpath(folder_path, self.notebooks_root)
            else:
                stored_path = folder_path
            
            if notebook_id not in registry["notebooks"]:
                registry["notebooks"][notebook_id] = {}
            
            registry["notebooks"][notebook_id]["systems"][fp_hash] = {
                "path": stored_path,
                "vault": vault_name,
                "entry": new_entry_uuid,
                "locked": False
            }
            
            self.save_registry(registry)
            
            self.session_keys._cache[notebook_id] = crypto
            notebook.custom_path = folder_path
            notebook._crypto = crypto
            notebook.locked = False
            
            return crypto
        
        else:
            if notebook_id in self.session_keys._cache:
                return self.session_keys._cache[notebook_id]
            return None
        
    def _invalidate_notebook_crypto(self, notebook_id):
        """Clear all cached crypto for a notebook"""
        notebook = self.find_notebook_by_id(notebook_id)
        if notebook:
            if hasattr(notebook, '_crypto'):
                delattr(notebook, '_crypto')
            notebook.locked = True
        
        if notebook_id in self.session_keys:
            del self.session_keys[notebook_id]
        
        if hasattr(self, 'ops') and hasattr(self.ops, '_crypto_cache'):
            self.ops._crypto_cache.pop(notebook_id, None)
        
        if hasattr(self, 'ops') and hasattr(self.ops.crypto, '_key_cache'):
            self.ops.crypto._key_cache.pop(notebook_id, None)
    
    def _update_notebook_vault_id(self, notebook_id, vault_id):
        """Update notebook registry with new vault_id"""
        registry_data = self.load_registry()
        entry = registry_data.get("notebooks", {}).get(notebook_id)
        
        if isinstance(entry, dict):
            entry["vault_id"] = vault_id
            self.save_registry(registry_data)
        elif isinstance(entry, str):
            crypto = self.session_keys.get(notebook_id)
            if crypto:
                from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                decrypted = decrypt_registry_entry(entry, crypto)
                if decrypted:
                    decrypted["vault_id"] = vault_id
                    new_entry = encrypt_registry_entry(decrypted, crypto)
                    if new_entry:
                        registry_data["notebooks"][notebook_id] = new_entry
                        self.save_registry(registry_data)
    
    #############################################################

    def get_notebook_status(self, notebook_id):
        """Get notebook status including vault availability"""
        notebook = self.find_notebook_by_id(notebook_id)
        if not notebook:
            return {"exists": False}
        
        # Get fresh lock status from registry
        registry_data = self.load_registry()
        entry = registry_data.get("notebooks", {}).get(notebook_id)
        
        registry_locked = True
        if isinstance(entry, dict):
            registry_locked = entry.get("locked", True)
        elif isinstance(entry, str):
            crypto = self.session_keys.get(notebook_id)
            if crypto:
                from notebook_operations import decrypt_registry_entry
                decrypted = decrypt_registry_entry(entry, crypto)
                if decrypted:
                    registry_locked = decrypted.get("locked", True)
        
        vault_path = self._get_vault_path(notebook_id)
        vault_available = vault_path and os.path.exists(vault_path) if vault_path else False
        
        is_locked = registry_locked
        
        return {
            "exists": True,
            "locked": is_locked,
            "registry_locked": registry_locked,
            "vault_available": vault_available,
            "vault_path": vault_path,
            "name": notebook.name,
            "is_encrypted": notebook_id in self.encrypted_notebooks
        }
        
    def _get_crypto_from_vault(self, notebook_id):
        """Get crypto from vault using entry UUID"""
        system_entry = self._get_current_system_entry(notebook_id)
        if not system_entry:
            return None
        
        entry_uuid = system_entry.get("entry")
        vault_name = system_entry.get("vault", "default")
        
        if not entry_uuid:
            return None
        
        vault_path = self.vault_manager.get_vault_path(vault_name)
        if not vault_path or not os.path.exists(vault_path):
            return None
        
        entry_data = self.vault_manager.get_entry_from_vault(vault_path, entry_uuid)
        if not entry_data:
            return None
        
        fingerprint = self._get_system_fingerprint()
        
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = bytes.fromhex(entry_data["nonce"])
            encrypted_keys = bytes.fromhex(entry_data["encrypted_keys"])
            aesgcm = AESGCM(fingerprint)
            decrypted = aesgcm.decrypt(nonce, encrypted_keys, None)
            
            password_key = decrypted[:32]
            phrase_key = decrypted[32:64]
            
            # Get folder path
            folder_path = system_entry.get("path")
            if folder_path and not os.path.isabs(folder_path):
                folder_path = os.path.join(self.notebooks_root, folder_path)
            
            if not folder_path:
                folder_path = self._find_notebook_folder(notebook_id)
            
            folder_name = os.path.basename(folder_path) if folder_path else f"notebook-{notebook_id}"
            
            from crypto import Crypto
            return Crypto(password_key, phrase_key, folder_name)
            
        except Exception:
            return None
    
    def _get_vault_path(self, notebook_id):
        """Get vault path using new vault manager"""
        system_entry = self._get_current_system_entry(notebook_id)
        if not system_entry:
            default_path = os.path.join(self.app_dir, "config", "session.vault")
            return default_path if os.path.exists(default_path) else None
        
        vault_name = system_entry.get("vault", "default")
        return self.vault_manager.get_vault_path(vault_name)

    def _write_crypto_to_vault(self, notebook_id, crypto):
        """Write crypto to vault - REPLACES existing entry using same UUID"""
        import time
        import uuid as uuid_lib
        
        # Get the existing entry UUID for this system from master registry
        fp_hash = self._compute_fp_hash()
        registry = self.load_registry()
        notebook_data = registry.get("notebooks", {}).get(notebook_id)
        
        if not notebook_data:
            # Should not happen for encrypted notebook
            return
        
        system_entry = notebook_data.get("systems", {}).get(fp_hash)
        if not system_entry:
            # Should not happen - system not registered
            return
        
        entry_uuid = system_entry.get("entry")
        vault_name = system_entry.get("vault", "default")
        
        if not entry_uuid:
            # Create new UUID if missing (shouldn't happen)
            entry_uuid = str(uuid_lib.uuid4())
            # Also need to update registry with this UUID
            system_entry["entry"] = entry_uuid
            self.save_registry(registry)
        
        vault_path = self.vault_manager.get_vault_path(vault_name)
        if not vault_path or not os.path.exists(vault_path):
            vault_path = self.vault_manager.ensure_default_vault()
        
        fingerprint = self._get_system_fingerprint()
        combined_keys = crypto.password_key + crypto.phrase_key
        nonce = os.urandom(12)
        
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(fingerprint)
        encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
        
        # REPLACE the entry (same UUID, overwrite)
        self.vault_manager.add_entry_to_vault(vault_path, entry_uuid, {
            "notebook_id": notebook_id,
            "timestamp": time.time_ns(),
            "nonce": nonce.hex(),
            "encrypted_keys": encrypted_keys.hex()
        })

    def _vault_has_keys(self, notebook_id):
        """Check if vault has keys - NO RECURSION"""
        from secure_session import SecureSessionStorage
        
        # Direct approach - don't call _get_vault_path if it causes recursion
        try:
            # Get vault path without recursion
            registry_data = self.load_registry(force_reload=True)
            entry = registry_data.get("notebooks", {}).get(notebook_id)
            
            vault_id = None
            if isinstance(entry, dict):
                vault_id = entry.get("vault_id")
            else:
                notebook = self.find_notebook_by_id(notebook_id)
                if notebook and hasattr(notebook, 'vault_id') and notebook.vault_id:
                    vault_id = notebook.vault_id
            
            if vault_id == "default":
                vault_path = os.path.join(self.app_dir, "config", "session.vault")
            elif vault_id:
                from vault_manager import VaultManager
                vm = VaultManager(self.app_dir)
                vm.reload()
                vault_path = vm.get_vault_path(vault_id)
            else:
                vault_path = os.path.join(self.app_dir, "config", "session.vault")
            
            if not vault_path or not os.path.exists(vault_path):
                return False
            
            storage = SecureSessionStorage(self.app_dir, vault_path=vault_path)
            pw, ph = storage.get_keys(notebook_id)
            return pw is not None and ph is not None
        except Exception:
            return False

    def _delete_from_vault(self, notebook_id):
        """Remove keys from vault - using entry UUID from master registry"""
        from secure_session import SecureSessionStorage
        
        # Get system entry to find entry_uuid
        fp_hash = self._compute_fp_hash()
        registry = self.load_registry()
        notebook_data = registry.get("notebooks", {}).get(notebook_id)
        system_entry = None
        if notebook_data:
            system_entry = notebook_data.get("systems", {}).get(fp_hash)
        
        if not system_entry:
            return
        
        entry_uuid = system_entry.get("entry")
        vault_name = system_entry.get("vault", "default")
        
        if not entry_uuid:
            return
        
        vault_path = self.vault_manager.get_vault_path(vault_name)
        if not vault_path or not os.path.exists(vault_path):
            return
        
        # Remove entry by UUID
        self.vault_manager.remove_entry_from_vault(vault_path, entry_uuid)
    
    def _invalidate_all_crypto(self, notebook_id):
        """Clear all cached crypto for a notebook"""
        notebook = self.find_notebook_by_id(notebook_id)
        if notebook:
            if hasattr(notebook, '_crypto'):
                delattr(notebook, '_crypto')
            notebook.locked = True
        
        # Direct dict access, not through __getitem__
        if notebook_id in self.session_keys._cache:
            del self.session_keys._cache[notebook_id]
        
        if hasattr(self, 'ops') and hasattr(self.ops, '_crypto_cache'):
            self.ops._crypto_cache.pop(notebook_id, None)
        
        if hasattr(self, 'ops') and hasattr(self.ops.crypto, '_key_cache'):
            self.ops.crypto._key_cache.pop(notebook_id, None)

    def _refresh_encrypted_notebook(self, notebook, crypto):
        """Replace locked placeholder with real decrypted notebook data"""
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
            
            # If no stored notebooks or not a dict, just return silently
            if not stored_notebooks or not isinstance(stored_notebooks, dict):
                return
            
            registry_data = self.load_registry()
            
            for folder_name, metadata in stored_notebooks.items():
                if not isinstance(folder_name, str) or '-' not in folder_name:
                    continue
                    
                notebook_id = folder_name.split('-')[-1]
                
                # Check if notebook exists in registry
                if notebook_id in registry_data.get("notebooks", {}):
                    from crypto import Crypto
                    crypto = Crypto.retrieve_for_folder(folder_name)
                    if crypto:
                        self.session_keys[notebook_id] = crypto
                        self.encrypted_notebooks.add(notebook_id)
                        
        except Exception:
            # Silently ignore - fresh start
            pass
    
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
        """Load notebooks using master registry with system index"""
        from crypto import Crypto
        import socket
        
        self.notebooks = []
        
        # Load master registry
        registry = self.load_registry(force_reload=True)
        
        # Get current system fingerprint hash
        fp_hash = self._compute_fp_hash()
        fingerprint = self._get_system_fingerprint()
        
        # Register system if new
        if fp_hash not in registry.get("system_index", {}):
            registry["system_index"][fp_hash] = socket.gethostname()
            self.save_registry(registry)
            registry = self.load_registry(force_reload=True)
        
        # Load vault registry
        vault_registry = self.vault_manager.list_vaults()
        
        # Track if registry needs saving
        registry_updated = False
        
        # Process each notebook in master registry
        for notebook_id, notebook_data in registry.get("notebooks", {}).items():
            # Skip legacy encrypted string entries
            if isinstance(notebook_data, str):
                if not quiet:
                    print(f"  ⚠ Legacy encrypted entry for {notebook_id}, skipping")
                continue
            
            # Skip if not a dictionary
            if not isinstance(notebook_data, dict):
                if not quiet:
                    print(f"  ⚠ Invalid notebook data type for {notebook_id}: {type(notebook_data)}")
                continue
            
            # Check if this system has an entry
            system_entry = notebook_data.get("systems", {}).get(fp_hash)
            
            if not system_entry:
                continue
            
            # ========== Get lock state with autolock enforcement ==========
            is_locked = system_entry.get("locked", True)
            notebook_path = system_entry.get("path")
            
            # Only apply autolock on first load (app startup)
            first_load = not hasattr(self, '_initial_load_complete')
            autolock = notebook_data.get("autolock", False)
            if autolock and first_load:
                # Force locked state only on app restart
                is_locked = True
                if not system_entry.get("locked", True):
                    system_entry["locked"] = True
                    registry_updated = True
            # ========== END AUTOLOCK FIX ==========

            if notebook_path and not os.path.isabs(notebook_path):
                notebook_path = os.path.join(self.notebooks_root, notebook_path)

            # ========== FIX: Don't skip if path doesn't exist - show as locked placeholder ==========
            path_exists = notebook_path and os.path.exists(notebook_path)
            if not path_exists:
                if not quiet:
                    print(f"  ⚠ Notebook {notebook_id} folder not found at: {notebook_path}")
                # Still create a locked placeholder
                actual_name = notebook_data.get("name", "Unknown")
                notebook = Notebook(actual_name, notebook_id=notebook_id)
                notebook.locked = True
                notebook.custom_path = None
                self.notebooks.append(notebook)
                self.encrypted_notebooks.add(notebook_id)
                if not quiet:
                    print(f"  🔒 Loaded (locked - folder missing): {notebook.name}")
                continue
            # ========== END FIX ==========
            
            # Check if encrypted
            is_encrypted = os.path.exists(os.path.join(notebook_path, ".tn_test"))
            
            if is_encrypted:
                entry_uuid = system_entry.get("entry")
                vault_name = system_entry.get("vault", "default")
                
                if not entry_uuid:
                    if not quiet:
                        print(f"  ⚠ No entry UUID for notebook {notebook_id}")
                    # ========== FIX: Add as locked notebook ==========
                    actual_name = notebook_data.get("name", "Unknown")
                    notebook = Notebook(actual_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    self.notebooks.append(notebook)
                    self.encrypted_notebooks.add(notebook_id)
                    if not quiet:
                        print(f"  🔒 Loaded (locked - no UUID): {notebook.name}")
                    continue
                    # ========== END FIX ==========
                
                vault_path = vault_registry.get(vault_name)
                if not vault_path:
                    vault_path = self.vault_manager.get_vault_path(vault_name)
                
                # ========== FIX: Vault missing - show as locked, don't skip ==========
                if not vault_path or not os.path.exists(vault_path):
                    if not quiet:
                        print(f"  ⚠ Vault {vault_name} not accessible for notebook {notebook_id}")
                    # Add as locked notebook instead of skipping
                    actual_name = notebook_data.get("name", "Unknown")
                    notebook = Notebook(actual_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    self.notebooks.append(notebook)
                    self.encrypted_notebooks.add(notebook_id)
                    if not quiet:
                        print(f"  🔒 Loaded (locked - vault missing): {notebook.name}")
                    continue
                # ========== END FIX ==========
                
                if is_locked:
                    # Get the actual notebook name from registry, not from folder
                    actual_name = notebook_data.get("name", "Unknown")
                    notebook = Notebook(actual_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    self.notebooks.append(notebook)
                    self.encrypted_notebooks.add(notebook_id)
                    # ========== FIX: Clear any stale cache for locked notebook ==========
                    if notebook_id in self.session_keys._cache:
                        del self.session_keys._cache[notebook_id]
                    # ========== END FIX ==========
                    if not quiet:
                        print(f"  🔒 Loaded (locked): {notebook.name}")
                    continue
                
                # Unlocked - decrypt
                entry_data = self.vault_manager.get_entry_from_vault(vault_path, entry_uuid)
                if not entry_data:
                    if not quiet:
                        print(f"  ⚠ Entry {entry_uuid} not found in vault for notebook {notebook_id}")
                    # ========== FIX: Add as locked notebook ==========
                    actual_name = notebook_data.get("name", "Unknown")
                    notebook = Notebook(actual_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    self.notebooks.append(notebook)
                    self.encrypted_notebooks.add(notebook_id)
                    if not quiet:
                        print(f"  🔒 Loaded (locked - entry missing): {notebook.name}")
                    continue
                    # ========== END FIX ==========
                
                try:
                    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                    nonce = bytes.fromhex(entry_data["nonce"])
                    encrypted_keys = bytes.fromhex(entry_data["encrypted_keys"])
                    aesgcm = AESGCM(fingerprint)
                    decrypted = aesgcm.decrypt(nonce, encrypted_keys, None)
                    
                    password_key = decrypted[:32]
                    phrase_key = decrypted[32:64]
                    
                    folder_name = os.path.basename(notebook_path)
                    actual_name = notebook_data.get("name", folder_name.split('-')[0])

                    crypto = Crypto(password_key, phrase_key, folder_name)
                    
                    notebook = self._load_notebook_from_path(notebook_path, crypto)
                    if notebook:
                        notebook._crypto = crypto
                        notebook.locked = False
                        notebook.custom_path = notebook_path
                        notebook.vault_id = vault_name if vault_name != "default" else None
                        self.notebooks.append(notebook)
                        self.encrypted_notebooks.add(notebook_id)
                        self.session_keys._cache[notebook_id] = crypto
                        if not quiet:
                            print(f"  ✓ Loaded: {notebook.name}")
                    else:
                        if not quiet:
                            print(f"  ✗ Failed to load notebook {notebook_id}")
                        # ========== FIX: Add as locked placeholder ==========
                        notebook = Notebook(actual_name, notebook_id=notebook_id)
                        notebook.locked = True
                        notebook.custom_path = None
                        self.notebooks.append(notebook)
                        self.encrypted_notebooks.add(notebook_id)
                        if not quiet:
                            print(f"  🔒 Loaded (locked - load failed): {notebook.name}")
                        # ========== END FIX ==========
                except Exception as e:
                    if not quiet:
                        print(f"  ✗ Failed to decrypt notebook {notebook_id}: {e}")
                    # ========== FIX: Add as locked placeholder on decryption error ==========
                    actual_name = notebook_data.get("name", "Unknown")
                    notebook = Notebook(actual_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    self.notebooks.append(notebook)
                    self.encrypted_notebooks.add(notebook_id)
                    if not quiet:
                        print(f"  🔒 Loaded (locked - decrypt failed): {notebook.name}")
                    # ========== END FIX ==========
            else:
                # Unencrypted notebook
                notebook = self._load_notebook_from_path(notebook_path)
                if notebook:
                    notebook.locked = False
                    notebook.custom_path = notebook_path
                    self.notebooks.append(notebook)
                    if not quiet:
                        print(f"  ✓ Loaded (unencrypted): {notebook.name}")
                else:
                    # ========== FIX: Even unencrypted notebooks that fail to load get a placeholder ==========
                    actual_name = notebook_data.get("name", "Unknown")
                    notebook = Notebook(actual_name, notebook_id=notebook_id)
                    notebook.locked = True
                    notebook.custom_path = None
                    self.notebooks.append(notebook)
                    if not quiet:
                        print(f"  🔒 Loaded (locked - unencrypted load failed): {notebook.name}")
                    # ========== END FIX ==========
        
        # Save registry if autolock updated any entries
        if registry_updated:
            self.save_registry(registry)
        
        # Handle first load autolock (backward compatibility)
        first_load = not hasattr(self, '_initial_load_complete')
        if first_load:
            registry_updated = False
            for notebook in self.notebooks:
                if notebook.id in self.encrypted_notebooks:
                    notebook_data = registry.get("notebooks", {}).get(notebook.id, {})
                    if isinstance(notebook_data, dict):
                        autolock = notebook_data.get("autolock", False)
                        
                        if autolock:
                            notebook.locked = True
                            notebook.custom_path = None
                            
                            if notebook.id in self.session_keys:
                                del self.session_keys[notebook.id]
                            
                            if hasattr(notebook, '_crypto'):
                                delattr(notebook, '_crypto')
                            
                            if notebook.id in registry.get("notebooks", {}):
                                if isinstance(registry["notebooks"][notebook.id], dict):
                                    if "autolock_locked" not in registry["notebooks"][notebook.id]:
                                        registry["notebooks"][notebook.id]["autolock_locked"] = True
                                        registry_updated = True
            
            if registry_updated:
                self.save_registry(registry)
            
            self._initial_load_complete = True
        
        return self.notebooks
    
    def _load_notebook_from_path(self, notebook_path: str, crypto=None):
        """Load notebook from filesystem path with optional crypto for decryption"""
        from notebook_operations import read_json
        from terminal_notes_core import Notebook as TempNotebook
        import json
        
        struct_file = os.path.join(notebook_path, "structure.json")
        if not os.path.exists(struct_file):
            return None
        
        try:
            # Read structure.json with crypto support
            struct_data = read_json(struct_file, crypto)
            if not struct_data:
                # Try reading as plain JSON if encrypted read failed
                with open(struct_file, 'r') as f:
                    struct_data = json.load(f)
            
            # Handle different structure formats
            if "notebooks" in struct_data and struct_data["notebooks"]:
                notebook_data = struct_data["notebooks"][0]
            else:
                notebook_data = struct_data
            
            # Create notebook
            notebook = TempNotebook.from_dict(notebook_data)
            notebook.custom_path = notebook_path
            
            # Load content files with crypto support
            notes_file = os.path.join(notebook_path, "notes.json")
            files_file = os.path.join(notebook_path, "files.json")
            
            notes_data = {}
            files_data = {}
            
            if os.path.exists(notes_file):
                notes_data = read_json(notes_file, crypto) or {}
            if os.path.exists(files_file):
                files_data = read_json(files_file, crypto) or {}
            
            # Apply content to notes
            def apply_content(nb):
                for note in nb.notes:
                    if note.is_file_note and note.id in files_data:
                        note.content = files_data[note.id]
                    elif not note.is_file_note and note.id in notes_data:
                        note.content = notes_data[note.id]
                for sub in nb.subnotebooks:
                    apply_content(sub)
            
            apply_content(notebook)
            return notebook
            
        except Exception as e:
            print(f"Error loading notebook from {notebook_path}: {e}")
            return None
    
    def _extract_notebook_id_from_folder(self, folder_name: str) -> str:
        """Extract notebook_id from folder name (format: name-id)"""
        if '-' in folder_name:
            return folder_name.split('-')[-1]
        return folder_name
    
    def get_vault_path(self, vault_name: str) -> Optional[str]:
        """Get absolute file path for a vault by name"""
        registry = self.load_vault_registry()
        
        # Special case: "default" always resolves to config/session.vault relative to app_dir
        if vault_name == "default":
            # Check if default exists in registry with relative path
            default_vault = registry.get("vaults", {}).get("default")
            if default_vault:
                stored_path = default_vault.get("path")
                if stored_path:
                    # Resolve relative path to absolute
                    return os.path.join(self.app_dir, stored_path)
            # Fallback
            return os.path.join(self.app_dir, "config", "session.vault")
        
        vault = registry.get("vaults", {}).get(vault_name)
        if vault:
            return vault.get("path")
        return None 
    
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
        import json
        import time
        import uuid as uuid_lib
        import socket

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
            # ========== COMBINED TRUSTED SYSTEM + FOLDER NOTICE ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print()
            print("  This notebook will be TIED to THIS machine.")
            print("  On THIS computer: unlock with your password only.")
            print("  On ANOTHER computer: you will need the RECOVERY PHRASE.")
            print()
            print("  Folder name: " + safe_folder)
            print("  This folder name is part of the encryption key.")
            print("  Do NOT rename the folder after creation.")
            print()
            print("  The recovery phrase (next step) is your ONLY backup.")
            print()
            input("  Press Enter to continue...")
            # ========== END COMBINED ==========
            
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
                
                # Password strength meter (keep existing code)
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
            
            # ========== COMBINED SECURITY REMINDER + RECOVERY PHRASE INFO ==========
            os.system('clear' if os.name == 'posix' else 'cls')
            print()
            print("  • The folder name is part of the encryption key")
            print("  • Do NOT rename the notebook folder")
            print("  • Backup your recovery phrase (next step)")
            print()
            print("  A recovery phrase helps you recover your notebook if you:")
            print("    • Forget your password")
            print("    • Move to a new computer")
            print("    • Your machine fingerprint changes")
            print()
            print("  The phrase is NOT stored anywhere. You must write it down.")
            print("  This is REQUIRED for encrypted notebooks.")
            print()
            input("  Press Enter to continue...")
            # ========== END COMBINED ==========
            
            # Recovery phrase generation/input (keep existing code)
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
                    # Auto-generate phrase (keep existing code)
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
                    # User-provided phrase (keep existing code)
                    while True:
                        os.system('clear' if os.name == 'posix' else 'cls')
                        print("\n" + "─" * 60)
                        print("  CREATE YOUR RECOVERY PHRASE")
                        print("─" * 60)
                        print()
                        print("  Your recovery phrase is the ONLY way to recover this notebook.")
                        # ... keep existing phrase validation code ...
                        recovery_phrase = input("  Enter your recovery phrase: ").strip()
                        # ... validation ...
                        break
                    break
                else:
                    print("\n  Invalid choice. Please enter 1 or 2.")
                    input("  Press Enter to continue...")
            # ========== END RECOVERY PHRASE ==========
            
            # Create crypto with dual-key system
            folder_name = os.path.basename(folder_path)
            crypto = Crypto.from_password_and_phrase(password, recovery_phrase, folder_name)
            
            # Extract keys
            password_key = crypto.password_key
            phrase_key = crypto.phrase_key

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

        # ========== NEW: Register with master registry ==========
        from vault_manager import VaultManager
        vm = VaultManager(self.app_dir)
        default_dir = os.path.join(self.app_dir, "config")
        default_path = os.path.join(default_dir, "session.vault")

        # Create config directory if it doesn't exist
        os.makedirs(default_dir, exist_ok=True)

        # Create default vault if it doesn't exist
        if not os.path.exists(default_path):
            vm.create_vault_file("default", default_dir)

        # For encrypted notebooks, create entry in default vault
        # For encrypted notebooks, create entry in default vault FIRST
        # For encrypted notebooks, create entry in default vault FIRST
        entry_uuid = None
        if encrypt and crypto:
            fingerprint = self._get_system_fingerprint()
            combined_keys = crypto.password_key + crypto.phrase_key
            nonce = os.urandom(12)
            
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(fingerprint)
            encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
            
            entry_uuid = str(uuid_lib.uuid4())
            
            # Add entry to default vault
            vm.add_entry_to_vault(default_path, entry_uuid, {
                "notebook_id": notebook.id,
                "timestamp": time.time_ns(),
                "nonce": nonce.hex(),
                "encrypted_keys": encrypted_keys.hex()
            })
            
            # Store in session memory WITHOUT triggering vault write
            self.session_keys._cache[notebook.id] = crypto
            self.encrypted_notebooks.add(notebook.id)
            
        else:
            # For unencrypted notebooks, normal assignment is fine
            self.session_keys[notebook.id] = crypto

        # Register in master registry (continued...)

        # Register in master registry
        registry = self.load_registry()

        # Get current system fingerprint hash
        fp_hash = self._compute_fp_hash()
        system_name = socket.gethostname()

        # Register system in system_index if new
        if fp_hash not in registry.get("system_index", {}):
            registry["system_index"][fp_hash] = system_name

        # Create notebook entry
        if notebook.id not in registry.get("notebooks", {}):
            registry["notebooks"][notebook.id] = {
                "name": name,
                "folder_name": safe_folder,
                "created": datetime.now().isoformat(),
                "systems": {}
            }

        # Store path (relative if under notebooks_root)
        if folder_path.startswith(self.notebooks_root):
            stored_path = os.path.relpath(folder_path, self.notebooks_root)
        else:
            stored_path = folder_path

        # Add current system entry
        registry["notebooks"][notebook.id]["systems"][fp_hash] = {
            "path": stored_path,
            "vault": "default",
            "entry": entry_uuid,
            "locked": False,  # ← New notebook starts unlocked
            "system_name": system_name  # ← ADD THIS

        }

        self.save_registry(registry)

        # ========== REMOVED: vm.add_notebook_to_vault - not needed ==========
        # The vault registry now tracks entries via the master registry

        # Update notebook object
        if encrypt and crypto:
            notebook.locked = False
            notebook._crypto = crypto
            notebook.vault_id = None  # No single vault_id

        self.notebooks.append(notebook)

        print(f"\n  Notebook created successfully!")
        print(f"   Name: {name}")
        print(f"   Folder: {safe_folder}")
        print(f"   Location: {folder_path}")
        if encrypt:
            print(f"   🔐 Encrypted with password + recovery phrase")
            print(f"   Recovery phrase saved - store it safely!")

        self._just_created = True
        return notebook
    
    def _ensure_default_vault(self):
        """Ensure default vault exists using new vault manager"""
        from vault_manager import VaultManager
        vm = VaultManager(self.app_dir)
        default_dir = os.path.join(self.app_dir, "config")
        default_path = os.path.join(default_dir, "session.vault")
        
        os.makedirs(default_dir, exist_ok=True)
        
        if not os.path.exists(default_path):
            vm.create_vault_file("default", default_dir)
        
        return default_path
    
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
        """Save master registry atomically"""
        registry_file = self.get_registry_file()
        temp_file = registry_file + '.tmp'
        
        try:
            with open(temp_file, 'w') as f:
                json.dump(registry_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            os.rename(temp_file, registry_file)
            self._registry_cache = registry_data
            return True
        except Exception as e:
            print(f"Error saving registry: {e}")
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass
            return False

    def load_registry(self, force_reload=False):
        """Load master registry (notebooks + system_index)"""
        if self._registry_cache is not None and not force_reload:
            return self._registry_cache
        
        registry_file = self.get_registry_file()
        
        if not os.path.exists(registry_file):
            self._registry_cache = {
                "version": 2,
                "system_index": {},
                "notebooks": {}
            }
            self._ensure_vault_registry_exists()
            return self._registry_cache
        
        try:
            with open(registry_file, 'r') as f:
                self._registry_cache = json.load(f)
                # Ensure required keys exist
                if "notebooks" not in self._registry_cache:
                    self._registry_cache["notebooks"] = {}
                if "system_index" not in self._registry_cache:
                    self._registry_cache["system_index"] = {}
                return self._registry_cache
        except Exception as e:
            print(f"Error loading registry: {e}")
            self._registry_cache = {
                "version": 2,
                "system_index": {},
                "notebooks": {}
            }
            return self._registry_cache
    
    def register_notebook(self, notebook, folder_path, is_import=False):
        """Register a notebook - stores plain JSON (no encryption needed)"""
        
        if notebook.parent_id is not None:
            print(f"  ⚠ Skipping registry for subnotebook: {notebook.name}")
            return
        
        registry = self.load_registry()
        
        if folder_path.startswith(self.notebooks_root):
            rel_path = os.path.relpath(folder_path, self.notebooks_root)
        else:
            rel_path = folder_path
        
        clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
        is_encrypted = notebook.id in self.encrypted_notebooks
        
        # Get current system fingerprint hash
        fp_hash = self._compute_fp_hash()
        
        # Register system in system_index if new
        if fp_hash not in registry.get("system_index", {}):
            registry["system_index"][fp_hash] = socket.gethostname()
        
        # Create notebook entry if not exists
        if notebook.id not in registry.get("notebooks", {}):
            registry["notebooks"][notebook.id] = {
                "name": clean_name,
                "folder_name": os.path.basename(folder_path),
                "created": datetime.now().isoformat(),
                "systems": {}
            }
        
        # For encrypted notebooks, we need entry_uuid from vault
        entry_uuid = None
        if is_encrypted:
            crypto = self.session_keys.get(notebook.id)
            if crypto:
                # During creation, we need to generate entry_uuid
                # This will be set separately
                pass
        
        # Add current system entry
        registry["notebooks"][notebook.id]["systems"][fp_hash] = {
            "path": rel_path,
            "vault": "default",  # Will be updated if user changes vault
            "entry": entry_uuid
        }
        
        self.save_registry(registry)
    
    def _register_and_unlock(self, notebook_id: str, notebook) -> Optional[Crypto]:
        """Register notebook on current system and unlock"""
        from getpass import getpass
        from crypto import Crypto, derive_key
        import time
        import uuid
        
        print(f"\n  Notebook not registered on this system.")
        print(f"  You need the recovery phrase to unlock it.")
        
        recovery_phrase = getpass("  Recovery phrase: ")
        if not recovery_phrase:
            return None
        
        # Find notebook folder
        folder_path = self._find_notebook_folder(notebook_id)
        if not folder_path:
            print(f"  Cannot find notebook folder")
            return None
        
        folder_name = os.path.basename(folder_path)
        
        # Decrypt .tn_recovery
        tn_recovery_path = os.path.join(folder_path, ".tn_recovery")
        if not os.path.exists(tn_recovery_path):
            print(f"  Missing .tn_recovery file")
            return None
        
        try:
            phrase_key = derive_key(recovery_phrase, folder_name)
            temp_crypto = Crypto(None, phrase_key, folder_name)
            
            with open(tn_recovery_path, 'rb') as f:
                recovery_data = f.read()
            
            json_str = temp_crypto.decrypt(recovery_data)
            recovery_info = json.loads(json_str)
            password_key = bytes.fromhex(recovery_info["password_key"])
            
            # Create crypto
            crypto = Crypto(password_key, phrase_key, folder_name)
            
            # Verify test marker
            test_file = os.path.join(folder_path, ".tn_test")
            if not crypto.verify_test_marker(test_file):
                print(f"  Verification failed")
                return None
            
            # Store in vault
            fingerprint = self._get_system_fingerprint()
            combined_keys = password_key + phrase_key
            nonce = os.urandom(12)
            
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(fingerprint)
            encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
            
            entry_uuid = str(uuid.uuid4())
            
            # Add to default vault
            default_vault_path = self.vault_manager.ensure_default_vault()
            self.vault_manager.add_entry_to_vault(default_vault_path, entry_uuid, {
                "notebook_id": notebook_id,
                "timestamp": time.time_ns(),
                "nonce": nonce.hex(),
                "encrypted_keys": encrypted_keys.hex()
            })
            
            # Update master registry
            registry = self.load_registry()
            fp_hash = self._compute_fp_hash()
            
            if fp_hash not in registry["system_index"]:
                registry["system_index"][fp_hash] = socket.gethostname()
            
            if notebook_id not in registry["notebooks"]:
                registry["notebooks"][notebook_id] = {
                    "name": notebook.name,
                    "folder_name": folder_name,
                    "created": datetime.now().isoformat(),
                    "systems": {}
                }
            
            # Store path (relative if under notebooks_root)
            if folder_path.startswith(self.notebooks_root):
                stored_path = os.path.relpath(folder_path, self.notebooks_root)
            else:
                stored_path = folder_path
            
            registry["notebooks"][notebook_id]["systems"][fp_hash] = {
                "path": stored_path,
                "vault": "default",
                "entry": entry_uuid
            }
            
            self.save_registry(registry)
            
            # Cache and unlock
            self.session_keys[notebook_id] = crypto
            notebook.custom_path = folder_path
            notebook._crypto = crypto
            notebook.locked = False
            
            print(f"  ✓ Notebook registered and unlocked")
            return crypto
            
        except Exception as e:
            print(f"  Registration failed: {e}")
            return None
        
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
            
            # ========== FIX: Remove from in-memory notebooks list ==========
            self.notebooks = [nb for nb in self.notebooks if nb.id != notebook_id]
            # ========== END FIX ==========
            
            # ========== FIX: Remove from encrypted_notebooks set ==========
            self.encrypted_notebooks.discard(notebook_id)
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
    
    # ========================================================================
    # NEW HELPER METHODS (internal use only)
    # ========================================================================

    def _get_system_fingerprint(self) -> bytes:
        if not self.secure_storage:
            from secure_session import SecureSessionStorage
            self.secure_storage = SecureSessionStorage(self.app_dir)
        return self.secure_storage._get_system_fingerprint()

    def _compute_fp_hash(self) -> str:
        fingerprint = self._get_system_fingerprint()
        system_name = socket.gethostname()
        combined = fingerprint + system_name.encode()
        return hashlib.sha256(combined).hexdigest()[:16]

    def _get_current_system_entry(self, notebook_id: str) -> Optional[Dict]:
        """Get the current system's entry for a notebook from master registry"""
        fp_hash = self._compute_fp_hash()
        registry = self.load_registry()
        
        notebook_data = registry.get("notebooks", {}).get(notebook_id)
        if not notebook_data:
            return None
        
        return notebook_data.get("systems", {}).get(fp_hash)

    def _update_system_entry(self, notebook_id, entry_data):
        """Update current system's entry for a notebook"""
        fp_hash = self._compute_fp_hash()
        registry = self.load_registry()
        
        if notebook_id not in registry["notebooks"]:
            registry["notebooks"][notebook_id] = {
                "name": "",
                "folder_name": "",
                "created": datetime.now().isoformat(),
                "systems": {}
            }
        
        if "systems" not in registry["notebooks"][notebook_id]:
            registry["notebooks"][notebook_id]["systems"] = {}
        
        existing = registry["notebooks"][notebook_id]["systems"].get(fp_hash, {})
        
        # Preserve system_name if not provided in entry_data
        if "system_name" not in entry_data and "system_name" in existing:
            entry_data["system_name"] = existing["system_name"]
        
        entry_data["locked"] = entry_data.get("locked", existing.get("locked", True))
        
        registry["notebooks"][notebook_id]["systems"][fp_hash] = entry_data
        return self.save_registry(registry)
   
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