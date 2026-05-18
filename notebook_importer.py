#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True

import os
import json
import subprocess
from pathlib import Path
from getpass import getpass
import hashlib


class NotebookImporter:
    def __init__(self, note_manager, ui_controller):
        self.manager = note_manager
        self.ui = ui_controller
        self._current_crypto = None

    def import_notebook_flow_with_path(self, provided_path):
        """Import notebook with pre-provided path"""
        self.ui.clear_screen()
        self.ui.print_header("Import Existing Notebook")
    
        import_path = provided_path
    
        # Normalize path
        import_path = os.path.expanduser(import_path)
        import_path = os.path.abspath(import_path)
    
        # Check if folder exists
        if not os.path.exists(import_path):
            print("✗ Path does not exist")
            self.ui.get_input("Press Enter to continue...")
            return "failed"
    
        if not os.path.isdir(import_path):
            print("✗ Path is not a directory")
            self.ui.get_input("Press Enter to continue...")
            return "failed"
    
        # Check if it's encrypted
        is_encrypted = self._check_if_encrypted(import_path)
    
        if is_encrypted:
            return self._import_encrypted(import_path)
        else:
            return self._import_unencrypted(import_path)
    
    def _check_if_encrypted(self, folder_path):
        """Check if notebook is encrypted"""
        # Check for .tn_test marker
        test_file = os.path.join(folder_path, ".tn_test")
        if os.path.exists(test_file):
            return True
        
        # Check if structure.json is binary
        struct_file = os.path.join(folder_path, "structure.json")
        if os.path.exists(struct_file):
            try:
                with open(struct_file, 'rb') as f:
                    sample = f.read(100)
                # If it contains high-bit bytes, it's likely encrypted
                if any(b >= 128 for b in sample):
                    return True
            except:
                pass
        
        return False
    
    def _import_encrypted(self, folder_path):
        """Import encrypted notebook using recovery phrase - UPDATED for master registry"""
        from crypto import Crypto, derive_key
        from terminal_notes_core import Notebook
        from notebook_operations import read_json, write_json, encrypt_registry_entry
        from datetime import datetime
        import os
        import json
        import time
        import uuid as uuid_lib
        import socket

        folder_path = os.path.abspath(folder_path)
        folder_name = os.path.basename(folder_path)
        
        # Extract notebook_id from folder name
        if '-' in folder_name:
            notebook_id = folder_name.split('-')[-1]
        else:
            notebook_id = folder_name

        print(f"\n  Folder: {folder_name}")
        print()
        print("  🔒 Encrypted notebook detected")
        print("  You need the RECOVERY PHRASE to import this notebook.\n")

        from getpass import getpass
        attempts = 0
        max_attempts = 3
        crypto = None
        password_key = None
        phrase_key = None

        while attempts < max_attempts and not crypto:
            remaining = max_attempts - attempts
            prompt = f"  Recovery phrase ({remaining} attempt{'s' if remaining != 1 else ''}): "
            phrase = getpass(prompt)
            
            if not phrase:
                attempts += 1
                if attempts < max_attempts:
                    print(f"  Phrase cannot be empty. {max_attempts - attempts} attempts left.\n")
                continue
            
            try:
                phrase_key = derive_key(phrase, folder_name)
                temp_crypto = Crypto(None, phrase_key, folder_name)
                
                test_file = os.path.join(folder_path, ".tn_test")
                if not os.path.exists(test_file):
                    print("  ✗ Invalid notebook format: .tn_test missing")
                    attempts += 1
                    continue
                
                with open(test_file, 'rb') as f:
                    test_data = f.read()
                temp_crypto.decrypt(test_data)
                
                recovery_file = os.path.join(folder_path, ".tn_recovery")
                if not os.path.exists(recovery_file):
                    print("  ✗ Invalid notebook format: .tn_recovery missing")
                    attempts += 1
                    continue
                
                with open(recovery_file, 'rb') as f:
                    recovery_data = f.read()
                
                json_str = temp_crypto.decrypt(recovery_data)
                recovery_info = json.loads(json_str)
                password_key = bytes.fromhex(recovery_info["password_key"])
                
                crypto = Crypto(password_key, phrase_key, folder_name)
                
                password_file = os.path.join(folder_path, ".tn_password")
                if os.path.exists(password_file):
                    with open(password_file, 'rb') as f:
                        password_data = f.read()
                    if not crypto.decrypt_with_combined(password_data):
                        raise Exception("Password verification failed")
                
                print("  ✓ Recovery phrase accepted! Notebook unlocked.")
                
            except Exception as e:
                attempts += 1
                if attempts < max_attempts:
                    print(f"  ✗ Wrong recovery phrase! {max_attempts - attempts} attempts left.\n")
                else:
                    print("  ✗ Too many failed attempts.")
                    self.ui.get_input("Press Enter to continue...")
                    return "failed"
        
        if not crypto:
            return "failed"

        # Read structure
        struct_file = os.path.join(folder_path, "structure.json")
        struct_data = read_json(struct_file, crypto)
        if not struct_data:
            print("  ✗ Could not read notebook structure")
            self.ui.get_input("Press Enter to continue...")
            return "failed"

        # Create notebook object
        notebook = Notebook.from_dict(struct_data)
        clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
        notebook.name = clean_name
        notebook.custom_path = folder_path
        notebook._crypto = crypto
        notebook.locked = False

        # Load content
        notes_file = os.path.join(folder_path, "notes.json")
        files_file = os.path.join(folder_path, "files.json")
        notes_data = read_json(notes_file, crypto) or {}
        files_data = read_json(files_file, crypto) or {}

        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        ops._apply_file_content_to_notebook(notebook, notes_data, files_data)

        # Check for duplicate
        if self.manager.notebook_exists_by_path(folder_path):
            print("  ✗ Notebook already imported")
            self.ui.get_input("Press Enter to continue...")
            return "failed"

        # Create vault entry for this system
        from vault_manager import VaultManager
        vm = VaultManager(self.manager.app_dir)
        
        default_dir = os.path.join(self.manager.app_dir, "config")
        default_path = os.path.join(default_dir, "session.vault")
        os.makedirs(default_dir, exist_ok=True)
        
        if not os.path.exists(default_path):
            vm.create_vault_file("default", default_dir)
        
        fingerprint = self.manager._get_system_fingerprint()
        combined_keys = crypto.password_key + crypto.phrase_key
        nonce = os.urandom(12)
        
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(fingerprint)
        encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
        
        entry_uuid = str(uuid_lib.uuid4())
        vm.add_entry_to_vault(default_path, entry_uuid, {
            "notebook_id": notebook.id,
            "timestamp": time.time_ns(),
            "nonce": nonce.hex(),
            "encrypted_keys": encrypted_keys.hex()
        })
        
        # Store in session cache
        self.manager.session_keys._cache[notebook.id] = crypto
        self.manager.encrypted_notebooks.add(notebook.id)

        # Update master registry
        fp_hash = self.manager._compute_fp_hash()
        system_name = socket.gethostname()
        registry = self.manager.load_registry()
        
        if fp_hash not in registry.get("system_index", {}):
            registry["system_index"][fp_hash] = system_name
        
        # Store path (relative if under notebooks_root)
        if folder_path.startswith(self.manager.notebooks_root):
            stored_path = os.path.relpath(folder_path, self.manager.notebooks_root)
        else:
            stored_path = folder_path
        
        if notebook.id not in registry.get("notebooks", {}):
            registry["notebooks"][notebook.id] = {
                "name": clean_name,
                "folder_name": folder_name,
                "created": datetime.now().isoformat(),
                "systems": {}
            }
        
        registry["notebooks"][notebook.id]["systems"][fp_hash] = {
            "path": stored_path,
            "vault": "default",
            "entry": entry_uuid,
            "locked": False,
            "system_name": system_name
        }
        
        self.manager.save_registry(registry)
        
        # Add to notebook list
        self.manager.notebooks.append(notebook)

        print(f"\n  ✓ Notebook imported successfully!")
        print(f"   Name: {notebook.name}")
        print(f"   Location: {folder_path}")
        print(f"   🔐 Notebook is UNLOCKED on this system")

        self.ui.get_input("Press Enter to continue...")
        return "success"
    
    def _import_unencrypted(self, folder_path):
        """Import unencrypted notebook"""
        try:
            from terminal_notes_core import Notebook
            
            folder_name = os.path.basename(folder_path)
            print(f"  Folder: {folder_name}")
            
            # Load notebook
            struct_file = os.path.join(folder_path, "structure.json")
            with open(struct_file, 'r') as f:
                structure_data = json.load(f)
            
            notebook = Notebook.from_dict(structure_data)
            notebook.custom_path = folder_path
            
            # Load content
            notes_file = os.path.join(folder_path, "notes.json")
            files_file = os.path.join(folder_path, "files.json")
            
            notes_map = {}
            if os.path.exists(notes_file):
                with open(notes_file, 'r') as f:
                    notes_map = json.load(f)
            
            files_map = {}
            if os.path.exists(files_file):
                with open(files_file, 'r') as f:
                    files_map = json.load(f)
            
            # Apply content
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
            ops._apply_file_content_to_notebook(notebook, notes_map, files_map)
            
            # Check for duplicate
            if self.manager.notebook_exists_by_path(folder_path):
                print("  ✗ Notebook already imported")
                self.ui.get_input("Press Enter to continue...")
                return "failed"
            
            # Register
            self.manager.register_notebook(notebook, folder_path)
            self.manager.notebooks.append(notebook)
            self.manager.save_data()
            
            print(f"\n  ✓ Notebook imported successfully!")
            print(f"   Name: {notebook.name}")
            print(f"   Location: {folder_path}")
            self.ui.get_input("Press Enter to continue...")
            return "success"
            
        except Exception as e:
            print(f"  ✗ Import failed: {e}")
            self.ui.get_input("Press Enter to continue...")
            return "failed"