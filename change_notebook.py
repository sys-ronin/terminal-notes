#!/usr/bin/env python3
"""
Change Notebook Handler - Manages notebook modification operations
"""

import sys
sys.dont_write_bytecode = True

import os
import shutil
import socket
import subprocess
import json
import uuid
import time
import hashlib
import socket
from datetime import datetime
from getpass import getpass

class ChangeNotebookHandler:
    def __init__(self, notebook_manager, note_manager, ui, nav, app_dir):
        self.notebook_manager = notebook_manager
        self.manager = note_manager
        self.ui = ui
        self.nav = nav
        self.app_dir = app_dir
        # Need references to accounts and other notebook_manager attributes
        self.accounts = notebook_manager.accounts
        self.config_dir = notebook_manager.config_dir
    
    # ========== Delegate methods to notebook_manager ==========
    def get_input(self, prompt):
        return self.notebook_manager.get_input(prompt)
    
    def clear_screen(self):
        self.notebook_manager.clear_screen()
    
    def print_header(self, title):
        self.notebook_manager.print_header(title)
    
    def load_accounts(self):
        self.notebook_manager.load_accounts()
    
    def save_accounts(self):
        self.notebook_manager.save_accounts()
    
    def _decrypt_token(self, token_enc):
        return self.notebook_manager._decrypt_token(token_enc)
    
    def fetch_account_repos(self, account, token):
        return self.notebook_manager.fetch_account_repos(account, token)
    
    def show_add_account(self):
        self.notebook_manager.show_add_account()
    # ========== End delegate methods ==========
    
    def handle_choice(self, choice, notebook, has_remote, option_offset):
        """Handle menu choice and delegate to appropriate method"""
        if choice == "1":
            self._change_password(notebook)
        elif choice == "2":
            self._toggle_autolock(notebook)
        elif choice == "3" and has_remote:
            self._change_remote(notebook)
        elif choice == str(option_offset):
            self._show_trusted_devices(notebook)
        return None
    
    def _toggle_autolock(self, notebook):
        """Toggle autolock flag for this notebook"""
        notebook_id = notebook['id']
        
        # Load current registry
        registry_data = self.manager.load_registry()
        
        if notebook_id not in registry_data["notebooks"]:
            print("\n  ✗ Notebook not found in registry")
            self.get_input("\nPress Enter to continue...")
            return
        
        entry = registry_data["notebooks"][notebook_id]
        current_autolock = False
        
        # Get current autolock value
        if isinstance(entry, dict):
            current_autolock = entry.get("autolock", False)
        elif isinstance(entry, str):
            from secure_session import SecureSessionStorage
            from crypto import Crypto
            from notebook_operations import decrypt_registry_entry
            
            storage = SecureSessionStorage(self.manager.app_dir)
            stored_pw_key, stored_ph_key = storage.get_keys(notebook_id)
            
            if stored_pw_key and stored_ph_key:
                temp_crypto = Crypto(stored_pw_key, stored_ph_key, "temp")
                decrypted = decrypt_registry_entry(entry, temp_crypto)
                if decrypted:
                    current_autolock = decrypted.get("autolock", False)
        
        # Toggle
        new_autolock = not current_autolock
        
        # Update registry
        if isinstance(entry, dict):
            entry["autolock"] = new_autolock
            self.manager.save_registry(registry_data)
        elif isinstance(entry, str):
            from secure_session import SecureSessionStorage
            from crypto import Crypto
            from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
            
            storage = SecureSessionStorage(self.manager.app_dir)
            stored_pw_key, stored_ph_key = storage.get_keys(notebook_id)
            
            if stored_pw_key and stored_ph_key:
                temp_crypto = Crypto(stored_pw_key, stored_ph_key, "temp")
                decrypted = decrypt_registry_entry(entry, temp_crypto)
                if decrypted:
                    decrypted["autolock"] = new_autolock
                    
                    folder_name = None
                    if notebook.get('path'):
                        folder_name = os.path.basename(notebook['path'])
                    else:
                        clean_name = notebook['name'].replace('🔐 ', '').replace('🔒 ', '')
                        folder_name = f"{clean_name}-{notebook_id}"
                    
                    crypto = Crypto(stored_pw_key, stored_ph_key, folder_name)
                    new_entry = encrypt_registry_entry(decrypted, crypto)
                    if new_entry:
                        registry_data["notebooks"][notebook_id] = new_entry
                        self.manager.save_registry(registry_data)
        
        # ========== FIX: Clear and accurate message ==========
        if new_autolock:
            print("\n  ✓ Autolock ENABLED")
            print("     Notebook will be LOCKED when you restart the app.")
            print("     You will need to unlock it manually after each restart.")
        else:
            print("\n  ✓ Autolock DISABLED")
            print("     Notebook will stay UNLOCKED across app restarts.")
            print("     (Only lock manually with [L] button)")
        # ========== END FIX ==========
        
        self.get_input("\nPress Enter to continue...")

    def _change_password(self, notebook):
        """Change notebook password"""
        self.clear_screen()
        self.print_header(f"Change Password - {notebook['name']}")
        
        print()
        print("  [1] Using old password")
        print("  [2] Using recovery phrase")
        print()
        print("  Press Enter to cancel")
        print()
        
        choice = self.get_input("  Choose: ").strip()
        
        if not choice:
            return
        
        if choice == "1":
            self._change_password_with_old(notebook)
        elif choice == "2":
            self._change_password_with_phrase(notebook)

    def _change_password_with_old(self, notebook):
        """Change password using old password"""
        from getpass import getpass
        from crypto import Crypto, derive_key
        from secure_session import SecureSessionStorage
        import hashlib
        import subprocess
        import platform
        
        self.clear_screen()
        self.print_header(f"Change Password - {notebook['name']}")
        
        print()
        old_password = getpass("  Old password: ")
        if not old_password:
            print("\n  Cancelled.")
            self.get_input("Press Enter to continue...")
            return
        
        # Verify old password
        folder_path = notebook['path']
        if not folder_path or not os.path.exists(folder_path):
            print("\n  Notebook path not found")
            self.get_input("Press Enter to continue...")
            return
        
        folder_name = os.path.basename(folder_path)
        notebook_id = notebook['id']
        
        storage = SecureSessionStorage(self.manager.app_dir)
        stored_pw_key, stored_ph_key = storage.get_keys(notebook_id)
        
        if not stored_pw_key:
            print("\n  No stored keys found. Try using recovery phrase.")
            self.get_input("Press Enter to continue...")
            return
        
        old_pw_key = derive_key(old_password, folder_name)
        
        if old_pw_key != stored_pw_key:
            print("\n  Wrong password.")
            self.get_input("Press Enter to continue...")
            return
        
        print()
        new_password = getpass("  New password: ")
        if not new_password:
            print("\n  Cancelled.")
            return
        
        confirm = getpass("  Confirm password: ")
        if new_password != confirm:
            print("\n  Passwords do not match.")
            self.get_input("Press Enter to continue...")
            return
        
        new_pw_key = derive_key(new_password, folder_name)
        
        crypto = Crypto(stored_pw_key, stored_ph_key, folder_name)
        
        test_file = os.path.join(folder_path, ".tn_test")
        if not crypto.verify_test_marker(test_file):
            print("\n  Verification failed.")
            self.get_input("Press Enter to continue...")
            return
        
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        recovery_file = os.path.join(folder_path, ".tn_recovery")
        crypto.create_recovery_file(recovery_file, new_hash, new_pw_key)
        
        new_crypto = Crypto(new_pw_key, stored_ph_key, folder_name)
        password_file = os.path.join(folder_path, ".tn_password")
        new_crypto.create_password_file(password_file)
        
        storage.store_keys(notebook_id, new_pw_key, stored_ph_key)
        
        # Get root notebook UUID for security commit
        notebook_obj = self.manager.find_notebook_by_id(notebook_id)
        root = self.manager._find_root_notebook(notebook_obj) if notebook_obj else None
        root_uuid = root.id if root else notebook_id
        system_name = platform.node()
        
        try:
            git_manager = self.manager.get_git_manager_by_path(folder_path)
            git_manager._run_git_command(["git", "add", ".tn_recovery", ".tn_password"])
            git_manager._run_git_command([
                "git", "commit", "-m",
                f"SECURITY: password changed | method: old_password | machine: {system_name} | root: {root_uuid}"
            ])
        except Exception:
            pass
        
        # Force lock
        if notebook_id in self.manager.session_keys:
            del self.manager.session_keys[notebook_id]
        
        for nb in self.manager.notebooks:
            if nb.id == notebook_id:
                nb.custom_path = None
                nb.locked = True
                if hasattr(nb, '_crypto'):
                    delattr(nb, '_crypto')
                break
        
        registry_data = self.manager.load_registry()
        if notebook_id in registry_data["notebooks"]:
            entry = registry_data["notebooks"][notebook_id]
            if isinstance(entry, dict):
                entry["locked"] = True
                self.manager.save_registry(registry_data)
            elif isinstance(entry, str):
                from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                decrypted = decrypt_registry_entry(entry, crypto)
                if decrypted:
                    decrypted["locked"] = True
                    new_entry = encrypt_registry_entry(decrypted, new_crypto)
                    if new_entry:
                        registry_data["notebooks"][notebook_id] = new_entry
                        self.manager.save_registry(registry_data)
        
        print("\n  Password changed.")
        print("  Notebook is now locked.")
        print("  Use your new password to unlock.")
        self.get_input("\nPress Enter to continue...")

    def _change_password_with_phrase(self, notebook):
        """Change password using recovery phrase"""
        from getpass import getpass
        from crypto import Crypto, derive_key
        from secure_session import SecureSessionStorage
        import hashlib
        import json
        import subprocess
        import platform
        
        self.clear_screen()
        self.print_header(f"Change Password - {notebook['name']}")
        
        folder_path = notebook['path']
        if not folder_path or not os.path.exists(folder_path):
            print("\n  Notebook path not found")
            self.get_input("Press Enter to continue...")
            return
        
        folder_name = os.path.basename(folder_path)
        notebook_id = notebook['id']
        
        print()
        phrase = getpass("  Recovery phrase: ")
        if not phrase:
            print("\n  Cancelled.")
            return
        
        phrase_key = derive_key(phrase, folder_name)
        temp_crypto = Crypto(None, phrase_key, folder_name)
        
        test_file = os.path.join(folder_path, ".tn_test")
        if not os.path.exists(test_file):
            print("\n  Invalid notebook format")
            self.get_input("Press Enter to continue...")
            return
        
        try:
            with open(test_file, 'rb') as f:
                test_data = f.read()
            temp_crypto.decrypt(test_data)
        except Exception:
            print("\n  Wrong recovery phrase.")
            self.get_input("Press Enter to continue...")
            return
        
        recovery_file = os.path.join(folder_path, ".tn_recovery")
        if not os.path.exists(recovery_file):
            print("\n  Invalid notebook format")
            self.get_input("Press Enter to continue...")
            return
        
        with open(recovery_file, 'rb') as f:
            recovery_data = f.read()
        
        json_str = temp_crypto.decrypt(recovery_data)
        recovery_info = json.loads(json_str)
        old_pw_key = bytes.fromhex(recovery_info["password_key"])
        
        print()
        new_password = getpass("  New password: ")
        if not new_password:
            print("\n  Cancelled.")
            return
        
        confirm = getpass("  Confirm password: ")
        if new_password != confirm:
            print("\n  Passwords do not match.")
            self.get_input("Press Enter to continue...")
            return
        
        new_pw_key = derive_key(new_password, folder_name)
        crypto = Crypto(old_pw_key, phrase_key, folder_name)
        
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        crypto.create_recovery_file(recovery_file, new_hash, new_pw_key)
        
        new_crypto = Crypto(new_pw_key, phrase_key, folder_name)
        password_file = os.path.join(folder_path, ".tn_password")
        new_crypto.create_password_file(password_file)
        
        storage = SecureSessionStorage(self.manager.app_dir)
        storage.store_keys(notebook_id, new_pw_key, phrase_key)
        
        # Get root notebook UUID for security commit
        notebook_obj = self.manager.find_notebook_by_id(notebook_id)
        if notebook_obj:
            root = self.manager._find_root_notebook(notebook_obj)
            root_uuid = root.id if root else notebook_id
        else:
            root_uuid = notebook_id
        system_name = platform.node()
        
        try:
            git_manager = self.manager.get_git_manager_by_path(folder_path)
            git_manager._run_git_command(["git", "add", ".tn_recovery", ".tn_password"])
            git_manager._run_git_command([
                "git", "commit", "-m",
                f"SECURITY: password changed | method: recovery_phrase | machine: {system_name} | root: {root_uuid}"
            ])
        except Exception as e:
            print(f"  Git commit failed: {e}")
        
        # Force lock
        if notebook_id in self.manager.session_keys:
            del self.manager.session_keys[notebook_id]
        
        for nb in self.manager.notebooks:
            if nb.id == notebook_id:
                nb.custom_path = None
                nb.locked = True
                if hasattr(nb, '_crypto'):
                    delattr(nb, '_crypto')
                break
        
        registry_data = self.manager.load_registry()
        if notebook_id in registry_data["notebooks"]:
            entry = registry_data["notebooks"][notebook_id]
            if isinstance(entry, dict):
                entry["locked"] = True
                self.manager.save_registry(registry_data)
            elif isinstance(entry, str):
                from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                decrypted = decrypt_registry_entry(entry, crypto)
                if decrypted:
                    decrypted["locked"] = True
                    new_entry = encrypt_registry_entry(decrypted, new_crypto)
                    if new_entry:
                        registry_data["notebooks"][notebook_id] = new_entry
                        self.manager.save_registry(registry_data)
        
        print("\n  Password changed.")
        print("  Notebook is now locked.")
        print("  Use your new password to unlock.")
        self.get_input("\nPress Enter to continue...")

    def _change_remote(self, notebook):
        """Change remote repository for notebook"""
        self.clear_screen()
        self.print_header(f"Change Remote - {notebook['name']}")
        
        current_config = notebook.get("git_config")
        current_account = notebook.get("account")
        
        if not current_config or not current_account:
            print("\n  No remote configured.")
            self.get_input("Press Enter to continue...")
            return
        
        accounts = list(self.accounts.get("accounts", {}).items())
        if not accounts:
            print("\n  No accounts found.")
            self.get_input("Press Enter to continue...")
            return
        
        current_name = f"{current_account['username']}@{current_account.get('platform', 'github')}"
        print(f"\n  Current: {current_name}/{current_config['repo']}\n")
        
        # Select account
        for i, (acc_id, acc) in enumerate(accounts, 1):
            nb_count = len(acc.get("notebooks", {}))
            print(f"  [{i}] {acc['username']}@{acc.get('platform', 'github')} ({nb_count} notebooks)")
        print(f"  [{len(accounts)+1}] Add new account")
        print()
        print("  Press Enter to cancel")
        print()
        
        choice = self.get_input("  Choose: ").strip()
        if not choice:
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(accounts):
                acc_id, account = accounts[idx]
                
                # Check if this is the same account already linked
                if acc_id == current_account['id']:
                    print("\n  ⚠ Already linked to this account.")
                    print(f"     Current: {current_account['username']}@{current_account.get('platform', 'github')}")
                    self.get_input("\nPress Enter to continue...")
                    return
                    
            elif idx == len(accounts):
                self.show_add_account()
                self.load_accounts()
                self._change_remote(notebook)
                return
            else:
                return
        except:
            return
        
        token = self._decrypt_token(account['token_enc'])
        if not token:
            print("\n  Could not decrypt token.")
            self.get_input("Press Enter to continue...")
            return
        
        print(f"\n  Fetching repositories for {account['username']}...")
        repos = self.fetch_account_repos(account, token)
        
        if not repos:
            print("  No repositories found.")
            self.get_input("Press Enter to continue...")
            return
        
        # Get current repo name
        current_repo = current_config['repo']
        notebook_id = notebook['id']
        
        # Also get linked notebooks from TokenVault
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        linked_notebooks = vault.get_linked_notebooks(account['id'])
        
        print()
        for i, repo in enumerate(repos, 1):
            repo_name = repo.get('name', 'Unknown')
            marker = ""
            if repo_name == current_repo:
                marker = " (current)"
            elif repo_name in linked_notebooks:
                marker = " (linked to another notebook)"
            print(f"  [{i}] {repo_name}{marker}")
        print()
        print("  Press Enter to cancel")
        print()
        
        choice = self.get_input("  Choose: ").strip()
        if not choice:
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(repos):
                repo = repos[idx]
                repo_name = repo.get('name')
                
                # Check if this repo is already linked to another notebook
                if repo_name in linked_notebooks and repo_name != current_repo:
                    print(f"\n  ⚠ Repository '{repo_name}' is already linked to another notebook!")
                    print("     Each repository can only be linked to one notebook.")
                    self.get_input("\nPress Enter to continue...")
                    return
            else:
                return
        except:
            return
        
        print(f"\n  Change to: {account['username']}@{account.get('platform', 'github')}/{repo_name}")
        confirm = input("  Confirm? [y/N]: ").lower()
        
        if confirm != 'y':
            print("\n  Cancelled.")
            self.get_input("Press Enter to continue...")
            return
        
        visibility = current_config.get("visibility", "private")
        
        # Remove old link from old account's TokenVault
        old_vault = TokenVault(self.app_dir)
        old_account_data = old_vault.get_full_account(current_account['id'])
        if old_account_data:
            old_linked = old_account_data.get("linked_notebooks", [])
            if notebook_id in old_linked:
                old_linked.remove(notebook_id)
                old_vault.store_token(
                    current_account['id'],
                    old_account_data["username"],
                    old_account_data["platform"],
                    old_account_data["host"],
                    old_account_data["api_url"],
                    old_account_data["token"],
                    old_linked
                )
        
        # Update notebook config in accounts dict
        for acc_id, acc in self.accounts["accounts"].items():
            if notebook['id'] in acc.get("notebooks", {}):
                del acc["notebooks"][notebook['id']]
        
        if account['id'] not in self.accounts["accounts"]:
            self.accounts["accounts"][account['id']] = account
        
        if "notebooks" not in self.accounts["accounts"][account['id']]:
            self.accounts["accounts"][account['id']]["notebooks"] = {}
        
        repo_uuid = f"repo_{uuid.uuid4().hex[:8]}"
        self.accounts["accounts"][account['id']]["notebooks"][notebook['id']] = {
            "repo": repo_name,
            "repo_uuid": repo_uuid,
            "visibility": visibility,
            "last_push": None,
            "created": datetime.now().isoformat()
        }
        
        if "repos" not in self.accounts:
            self.accounts["repos"] = {}
        
        self.accounts["repos"][repo_uuid] = {
            "name": repo_name,
            "account_id": account['id'],
            "notebook_id": notebook['id'],
            "visibility": visibility,
            "created": datetime.now().isoformat()
        }
        
        self.save_accounts()
        
        # Update new account's TokenVault with linked notebook
        new_vault = TokenVault(self.app_dir)
        new_account_data = new_vault.get_full_account(account['id'])
        if new_account_data:
            new_linked = new_account_data.get("linked_notebooks", [])
            if notebook_id not in new_linked:
                new_linked.append(notebook_id)
                new_vault.store_token(
                    account['id'],
                    new_account_data["username"],
                    new_account_data["platform"],
                    new_account_data["host"],
                    new_account_data["api_url"],
                    new_account_data["token"],
                    new_linked
                )
        
        print("\n  ✓ Remote changed.")
        print(f"     New account: {account['username']}@{account.get('platform', 'github')}")
        print(f"     New repository: {repo_name}")
        self.get_input("\nPress Enter to continue...")

    def _show_trusted_devices(self, notebook):
        """Show trusted devices list with pagination"""
        from secure_session import SecureSessionStorage
        import shutil
        import socket
        
        storage = SecureSessionStorage(self.app_dir)
        entries = storage.list_entries(notebook['id'])
        current_hostname = socket.gethostname()
        
        if not entries:
            print("\n  No trusted devices found.")
            self.get_input("\nPress Enter to continue...")
            return
        
        page = 0
        
        while True:
            self.clear_screen()
            width, height = shutil.get_terminal_size()
            
            # Header - centered
            print("" * width)
            header = f"Trusted Devices - {notebook['name']}"
            print(f"{header:^{width}}")
            print("" * width)
            print()
            
            # Pagination
            from cs_ui import PaginationManager
            items_per_page, total_pages = PaginationManager.calculate(
                len(entries), height, fixed_lines=8
            )
            
            if page >= total_pages:
                page = max(0, total_pages - 1)
            
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(entries))
            page_entries = entries[start_idx:end_idx]
            current_page = page + 1
            
            # Display entries - LEFT ALIGNED (no spaces before [1])
            for i, entry in enumerate(page_entries, 1):
                is_current = entry.get('system_name') == current_hostname
                is_active = entry.get('active', False)
                
                # Only show [ACTIVE] for active device
                if is_current and is_active:
                    line = f"[{i}] {entry['system_name']} [ACTIVE]"
                else:
                    line = f"[{i}] {entry['system_name']}"
                
                # Truncate if too long
                if len(line) > width - 4:
                    line = line[:width-7] + "..."
                
                print(line)
            
            # Page indicator with << >> arrows
            if total_pages > 1:
                print()
                PaginationManager.show_indicator(page, total_pages, width)
            else:
                print()
            
            # Footer - consistent with all other screens
            print("" * width)
            footer = ["[D]elete", "[B]ack"]
            if total_pages > 1:
                if page > 0:
                    footer.insert(0, "[P]rev")
                if page < total_pages - 1:
                    footer.insert(0, "[N]ext")
            print("  ".join(footer))
            print()
            
            cmd = self.get_input("> ").lower()
            
            if cmd == "b":
                break
            elif cmd == "n" and page < total_pages - 1:
                page += 1
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd.startswith("d"):
                if cmd == "d":
                    try:
                        idx = int(self.get_input("Enter device number to remove: ")) - 1
                    except ValueError:
                        continue
                else:
                    try:
                        idx = int(cmd[1:]) - 1
                    except ValueError:
                        continue
                
                if 0 <= idx < len(page_entries):
                    entry = page_entries[idx]
                    is_current = entry.get('system_name') == current_hostname
                    is_active = entry.get('active', False)
                    
                    if is_current and is_active:
                        print("\n  ⚠️  WARNING: You are removing THIS machine's trusted status!")
                        print("     After removal:")
                        print("     • This notebook will LOCK immediately")
                        print("     • You will need your RECOVERY PHRASE to unlock again")
                        print("     • This machine will no longer be trusted")
                        print()
                        confirm = self.get_input("     Type 'CONFIRM' to proceed: ").strip()
                        
                        if confirm != 'CONFIRM':
                            print("\n  Cancelled.")
                            self.get_input("\nPress Enter to continue...")
                            continue
                        
                        if storage.remove_entry(notebook['id'], entry['timestamp']):
                            self._lock_notebook_immediately(notebook['id'])
                            print("\n  ✓ This machine's trust removed.")
                            print("  ✓ Notebook locked.")
                            self.get_input("\nPress Enter to continue...")
                            return
                        else:
                            print("\n  ✗ Failed to remove device.")
                            self.get_input("\nPress Enter to continue...")
                    
                    else:
                        print(f"\n  Remove trusted device '{entry['system_name']}'?")
                        print("  This machine will need the recovery phrase to unlock again.")
                        confirm = self.get_input("\n  Confirm removal? [y/N]: ").lower()
                        
                        if confirm == 'y':
                            if storage.remove_entry(notebook['id'], entry['timestamp']):
                                print(f"\n  ✓ Device removed successfully!")
                                entries = storage.list_entries(notebook['id'])
                                page = 0
                                if not entries:
                                    print("\n  No trusted devices remain.")
                                    self.get_input("\nPress Enter to continue...")
                                    break
                            else:
                                print("\n  ✗ Failed to remove device.")
                                self.get_input("\nPress Enter to continue...")
                        else:
                            print("\n  Cancelled.")
                            self.get_input("\nPress Enter to continue...")

    def _lock_notebook_immediately(self, notebook_id):
        """Lock a notebook immediately (clear session keys, mark locked)"""
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if notebook:
            # Clear session keys
            if notebook_id in self.manager.session_keys:
                del self.manager.session_keys[notebook_id]
            
            # Clear crypto from notebook object
            if hasattr(notebook, '_crypto'):
                delattr(notebook, '_crypto')
            
            # Mark as locked
            notebook.locked = True
            notebook.custom_path = None
            
            # Update registry
            registry_data = self.manager.load_registry()
            if notebook_id in registry_data["notebooks"]:
                entry = registry_data["notebooks"][notebook_id]
                if isinstance(entry, dict):
                    entry["locked"] = True
                    self.manager.save_registry(registry_data)
            
            # Reload notebooks to reflect lock state
            self.manager.load_all_notebooks(quiet=True)
    
    def _change_vault_location(self, notebook):
        """Change vault location for this notebook (only when unlocked)"""
        from secure_session import SecureSessionStorage
        import time
        import hashlib
        import socket
        
        self.clear_screen()
        self.print_header(f"Change Vault Location - {notebook['name']}")
        
        # Read current vault_id from notebook registry
        registry_data = self.manager.load_registry()
        notebook_entry = registry_data.get("notebooks", {}).get(notebook['id'])
        
        current_vault_id = None
        if isinstance(notebook_entry, dict):
            current_vault_id = notebook_entry.get("vault_id")
        elif isinstance(notebook_entry, str):
            crypto = self.manager.session_keys.get(notebook['id'])
            if crypto:
                from notebook_operations import decrypt_registry_entry
                decrypted = decrypt_registry_entry(notebook_entry, crypto)
                if decrypted:
                    current_vault_id = decrypted.get("vault_id")
        
        # Display current vault
        if current_vault_id:
            vault_path = self.notebook_manager.vault_manager.get_vault_path(current_vault_id)
            if vault_path:
                print(f"\n  Current vault: {current_vault_id} ({vault_path})")
            else:
                print(f"\n  Current vault: Default (config/session.vault)")
                current_vault_id = None
        else:
            default_path = os.path.join(self.app_dir, "config", "session.vault")
            print(f"\n  Current vault: Default ({default_path})")
        
        print()
        
        # Build options
        options = []
        option_num = 1

        # List all existing custom vaults from vault registry
        all_vaults = self.notebook_manager.vault_manager.list_vaults()
        custom_vaults = {k: v for k, v in all_vaults.items() if k != "default"}

        for vault_id, vault in custom_vaults.items():
            if current_vault_id and vault_id == current_vault_id:
                continue
            location = vault.get('location', 'unknown')
            print(f"  [{option_num}] {vault_id} - {location}")
            options.append(("existing", option_num, vault_id))
            option_num += 1

        # Create new vault
        print(f"  [{option_num}] Create new vault location")
        options.append(("new", option_num))
        option_num += 1

        # Only show "Switch to default vault" if NOT already on default
        if current_vault_id and current_vault_id != "default":
            print(f"  [{option_num}] Switch to default vault")
            options.append(("default", option_num))
            option_num += 1

        print(f"  [{option_num}] Back")
        
        print()
        choice = self.get_input("  Choose: ").strip()
        
        if not choice:
            return
        
        try:
            choice_num = int(choice)
        except:
            return
        
        target_vault_id = None
        target_location = None
        
        for opt in options:
            if len(opt) >= 2 and opt[1] == choice_num:
                if opt[0] == "default":
                    target_vault_id = None
                    target_location = "default"
                elif opt[0] == "existing":
                    target_vault_id = opt[2]
                    target_location = self.notebook_manager.vault_manager.get_vault_path(target_vault_id)
                elif opt[0] == "new":
                    result = self._create_new_vault_location(notebook)
                    if result:
                        target_vault_id, target_location = result
                    else:
                        return
                elif opt[0] == "back":
                    return
                break
        
        if target_vault_id is None and target_location != "default":
            print("\n  Cancelled.")
            self.get_input("Press Enter to continue...")
            return
        
        print(f"\n  Changing vault...")
        
        # Get current system fingerprint
        if current_vault_id:
            old_vault_path = self.notebook_manager.vault_manager.get_vault_path(current_vault_id)
            if old_vault_path:
                old_storage = SecureSessionStorage(self.app_dir, vault_path=old_vault_path)
            else:
                old_storage = SecureSessionStorage(self.app_dir)
        else:
            old_storage = SecureSessionStorage(self.app_dir)
        
        # Get system info
        fingerprint = old_storage._get_system_fingerprint()
        fingerprint_hash = hashlib.sha256(fingerprint).hexdigest()[:16]
        system_name = socket.gethostname()
        timestamp = time.time_ns()
        
        # Remove from old vault if custom
        if current_vault_id:
            old_vault_path = self.notebook_manager.vault_manager.get_vault_path(current_vault_id)
            if old_vault_path:
                old_storage.remove_entry(notebook['id'], None)
                self.notebook_manager.vault_manager.remove_notebook_from_vault(current_vault_id, notebook['id'])
                print(f"  ✓ Removed from old vault: {current_vault_id}")
        
        # Add to new vault
        if target_location == "default":
            new_storage = SecureSessionStorage(self.app_dir)
            new_vault_id = None
            print(f"  ✓ Switching to default vault")
        else:
            new_storage = SecureSessionStorage(self.app_dir, vault_path=target_location)
            new_vault_id = target_vault_id
            print(f"  ✓ Adding to new vault: {new_vault_id}")
        
        # Add current system to new vault
        new_storage._add_entry(notebook['id'], fingerprint, fingerprint_hash, system_name, timestamp)
        print(f"  ✓ System added to new vault")
        
        # ========== FIX: Re-encrypt registry entry with new vault's crypto ==========
        # Get the crypto key from the new vault to re-encrypt registry entry
        new_crypto = None
        if new_vault_id:
            if new_vault_id == "default":
                vault_path = os.path.join(self.app_dir, "config", "session.vault")
            else:
                vault_path = target_location
            
            if vault_path and os.path.exists(vault_path):
                from secure_session import SecureSessionStorage
                from crypto import Crypto
                temp_storage = SecureSessionStorage(self.app_dir, vault_path=vault_path)
                pw_key, ph_key = temp_storage.get_keys(notebook['id'])
                if pw_key and ph_key:
                    folder_name = os.path.basename(notebook.get('path', '')) if notebook.get('path') else f"{notebook['name']}-{notebook['id']}"
                    new_crypto = Crypto(pw_key, ph_key, folder_name)
        # ========== END FIX ==========
        
        # Update notebook registry with new vault_id
        registry_data = self.manager.load_registry()
        notebook_entry = registry_data.get("notebooks", {}).get(notebook['id'])
        
        if isinstance(notebook_entry, dict):
            if new_vault_id:
                notebook_entry["vault_id"] = new_vault_id
            else:
                notebook_entry.pop("vault_id", None)
            self.manager.save_registry(registry_data)
            print(f"  ✓ Notebook registry updated")
        elif isinstance(notebook_entry, str):
            # ========== FIX: Use new_crypto to re-encrypt ==========
            if new_crypto:
                from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                decrypted = decrypt_registry_entry(notebook_entry, new_crypto)
                if decrypted:
                    if new_vault_id:
                        decrypted["vault_id"] = new_vault_id
                    else:
                        decrypted.pop("vault_id", None)
                    new_entry = encrypt_registry_entry(decrypted, new_crypto)
                    if new_entry:
                        registry_data["notebooks"][notebook['id']] = new_entry
                        self.manager.save_registry(registry_data)
                        print(f"  ✓ Notebook registry re-encrypted with new vault")
            else:
                # Fallback to old method
                crypto = self.manager.session_keys.get(notebook['id'])
                if crypto:
                    from notebook_operations import decrypt_registry_entry, encrypt_registry_entry
                    decrypted = decrypt_registry_entry(notebook_entry, crypto)
                    if decrypted:
                        if new_vault_id:
                            decrypted["vault_id"] = new_vault_id
                        else:
                            decrypted.pop("vault_id", None)
                        new_entry = encrypt_registry_entry(decrypted, crypto)
                        if new_entry:
                            registry_data["notebooks"][notebook['id']] = new_entry
                            self.manager.save_registry(registry_data)
                            print(f"  ✓ Notebook registry updated")
            # ========== END FIX ==========
        
        # Update in-memory notebook object
        notebook['vault_id'] = new_vault_id
        
        # Update the notebook in self.notebooks list
        for i, nb in enumerate(self.notebook_manager.notebooks):
            if nb.get('id') == notebook['id']:
                self.notebook_manager.notebooks[i]['vault_id'] = new_vault_id
                break
        
        # Show final message
        if target_location == "default":
            print(f"\n  ✓ Vault changed successfully!")
            print(f"     New vault: Default (config/session.vault)")
        else:
            print(f"\n  ✓ Vault changed successfully!")
            print(f"     New vault: {new_vault_id} ({target_location})")
        print(f"     Notebook stays UNLOCKED (keys kept in memory)")
        
        self.get_input("\nPress Enter to continue...")
    
    def _create_new_vault_location(self, notebook):
        """Create a new vault location"""
        import json
        
        self.clear_screen()
        self.print_header("Create New Vault Location")
        
        print()
        print("  Enter the DIRECTORY where the vault file will be stored.")
        print("  The file 'session.vault' will be created automatically inside.")
        print()
        print("  Examples:")
        print("    /mnt/usb/")
        print("    /home/user/.vaults/")
        print("    D:\\vaults\\")
        print()
        
        location = self.get_input("  Directory path: ").strip()
        
        if not location:
            print("\n  Cancelled.")
            self.get_input("Press Enter to continue...")
            return None
        
        # Ensure directory exists
        if not os.path.exists(location):
            try:
                os.makedirs(location, exist_ok=True)
                print(f"  ✓ Created directory: {location}")
            except Exception as e:
                print(f"\n  ✗ Cannot create directory: {e}")
                self.get_input("Press Enter to continue...")
                return None
        
        # Full path to vault file
        vault_file_path = os.path.join(location, "session.vault")
        
        # Check if vault already exists at this location
        existing_vault_id = self.notebook_manager.vault_manager.vault_exists(vault_file_path)
        
        if existing_vault_id:
            print(f"\n  ⚠️ A vault already exists at this location.")
            print(f"     Vault ID: {existing_vault_id}")
            use_existing = self.get_input("     Use existing vault? [y/N]: ").lower()
            if use_existing == 'y':
                self.notebook_manager.vault_manager.add_notebook_to_vault(existing_vault_id, notebook['id'])
                return existing_vault_id, vault_file_path
            else:
                return None
        
        # Create new vault entry
        vault_id = self.notebook_manager.vault_manager.create_vault(vault_file_path)
        self.notebook_manager.vault_manager.add_notebook_to_vault(vault_id, notebook['id'])
        
        # Create empty vault file
        try:
            empty_vault = {"notebooks": {}}
            with open(vault_file_path, 'w') as f:
                json.dump(empty_vault, f)
            print(f"  ✓ Created vault file: {vault_file_path}")
        except Exception as e:
            print(f"  ⚠️ Could not create vault file: {e}")
        
        print(f"\n  ✓ New vault created: {vault_id}")
        print(f"     Location: {vault_file_path}")
        
        self.get_input("\nPress Enter to continue...")
        
        return vault_id, vault_file_path