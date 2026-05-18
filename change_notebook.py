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
        """Toggle autolock flag for this notebook (UPDATED for master registry)"""
        notebook_id = notebook['id']
        
        # Load master registry
        master_registry = self.manager.load_registry(force_reload=True)
        
        if notebook_id not in master_registry.get("notebooks", {}):
            print("\n  ✗ Notebook not found in registry")
            self.get_input("\nPress Enter to continue...")
            return
        
        notebook_data = master_registry["notebooks"][notebook_id]
        current_autolock = notebook_data.get("autolock", False)
        
        # Toggle
        new_autolock = not current_autolock
        
        # Update master registry
        notebook_data["autolock"] = new_autolock
        self.manager.save_registry(master_registry)
        
        # ========== Clear and accurate message ==========
        if new_autolock:
            print("\n  ✓ Autolock ENABLED")
            print("     Notebook will be LOCKED when you restart the app.")
            print("     You will need to unlock it manually after each restart.")
        else:
            print("\n  ✓ Autolock DISABLED")
            print("     Notebook will stay UNLOCKED across app restarts.")
            print("     (Only lock manually with [L] button)")
        
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
        """Change password using old password - UPDATED for master registry"""
        from getpass import getpass
        from crypto import Crypto, derive_key
        from secure_session import SecureSessionStorage
        import hashlib
        import subprocess
        import platform
        import time
        import uuid as uuid_lib

        self.clear_screen()
        self.print_header(f"Change Password - {notebook['name']}")

        notebook_id = notebook['id']
        notebook_obj = self.manager.find_notebook_by_id(notebook_id)
        if not notebook_obj:
            print("\n  Notebook not found")
            self.get_input("Press Enter to continue...")
            return

        # Get current crypto from session (notebook must be unlocked)
        crypto = self.manager.session_keys.get(notebook_id)
        if not crypto:
            print("\n  Notebook must be unlocked first.")
            self.get_input("Press Enter to continue...")
            return

        # Get folder path from master registry
        fp_hash = self.manager._compute_fp_hash()
        master_registry = self.manager.load_registry(force_reload=True)
        notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
        system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
        
        folder_path = system_entry.get("path")
        if folder_path and not os.path.isabs(folder_path):
            folder_path = os.path.join(self.manager.notebooks_root, folder_path)
        
        if not folder_path or not os.path.exists(folder_path):
            print("\n  Notebook path not found")
            self.get_input("Press Enter to continue...")
            return

        folder_name = os.path.basename(folder_path)
        
        # Get stored password key from current crypto
        stored_pw_key = crypto.password_key
        stored_ph_key = crypto.phrase_key

        print()
        old_password = getpass("  Old password: ")
        if not old_password:
            print("\n  Cancelled.")
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
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()

        # Update .tn_recovery and .tn_password files
        recovery_file = os.path.join(folder_path, ".tn_recovery")
        crypto.create_recovery_file(recovery_file, new_hash, new_pw_key)

        new_crypto = Crypto(new_pw_key, stored_ph_key, folder_name)
        password_file = os.path.join(folder_path, ".tn_password")
        new_crypto.create_password_file(password_file)

        # Update vault entry for this system
        entry_uuid = system_entry.get("entry")
        vault_name = system_entry.get("vault", "default")
        vault_path = self.manager.vault_manager.get_vault_path(vault_name)
        
        if entry_uuid and vault_path and os.path.exists(vault_path):
            fingerprint = self.manager._get_system_fingerprint()
            combined_keys = new_pw_key + stored_ph_key
            nonce = os.urandom(12)
            
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(fingerprint)
            encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
            
            self.manager.vault_manager.add_entry_to_vault(vault_path, entry_uuid, {
                "notebook_id": notebook_id,
                "timestamp": time.time_ns(),
                "nonce": nonce.hex(),
                "encrypted_keys": encrypted_keys.hex()
            })

        # Update session cache
        self.manager.session_keys._cache[notebook_id] = new_crypto

        # Git commit
        system_name = platform.node()
        try:
            git_manager = self.manager.get_git_manager_by_path(folder_path)
            git_manager._run_git_command(["git", "add", ".tn_recovery", ".tn_password"])
            git_manager._run_git_command([
                "git", "commit", "-m",
                f"SECURITY: password changed | method: old_password | machine: {system_name} | root: {notebook_id}"
            ])
        except Exception:
            pass

        # Lock the notebook (forces re-unlock with new password)
        if notebook_id in self.manager.session_keys._cache:
            del self.manager.session_keys._cache[notebook_id]
        
        for nb in self.manager.notebooks:
            if nb.id == notebook_id:
                nb.custom_path = None
                nb.locked = True
                if hasattr(nb, '_crypto'):
                    delattr(nb, '_crypto')
                break

        # Update master registry lock state
        if system_entry:
            system_entry["locked"] = True
            self.manager.save_registry(master_registry)

        print("\n  Password changed.")
        print("  Notebook is now locked.")
        print("  Use your new password to unlock.")
        self.get_input("\nPress Enter to continue...")

    def _change_password_with_phrase(self, notebook):
        """Change password using recovery phrase - UPDATED for master registry"""
        from getpass import getpass
        from crypto import Crypto, derive_key
        from secure_session import SecureSessionStorage
        import hashlib
        import json
        import subprocess
        import platform
        import time
        import uuid as uuid_lib

        self.clear_screen()
        self.print_header(f"Change Password - {notebook['name']}")

        notebook_id = notebook['id']
        
        # Get folder path from master registry
        fp_hash = self.manager._compute_fp_hash()
        master_registry = self.manager.load_registry(force_reload=True)
        notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
        system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
        
        folder_path = system_entry.get("path")
        if folder_path and not os.path.isabs(folder_path):
            folder_path = os.path.join(self.manager.notebooks_root, folder_path)
        
        if not folder_path or not os.path.exists(folder_path):
            print("\n  Notebook path not found")
            self.get_input("Press Enter to continue...")
            return

        folder_name = os.path.basename(folder_path)

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
        new_hash = hashlib.sha256(new_password.encode()).hexdigest()
        
        crypto = Crypto(old_pw_key, phrase_key, folder_name)
        crypto.create_recovery_file(recovery_file, new_hash, new_pw_key)

        new_crypto = Crypto(new_pw_key, phrase_key, folder_name)
        password_file = os.path.join(folder_path, ".tn_password")
        new_crypto.create_password_file(password_file)

        # Update vault entry for this system
        entry_uuid = system_entry.get("entry")
        vault_name = system_entry.get("vault", "default")
        vault_path = self.manager.vault_manager.get_vault_path(vault_name)
        
        if entry_uuid and vault_path and os.path.exists(vault_path):
            fingerprint = self.manager._get_system_fingerprint()
            combined_keys = new_pw_key + phrase_key
            nonce = os.urandom(12)
            
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            aesgcm = AESGCM(fingerprint)
            encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
            
            self.manager.vault_manager.add_entry_to_vault(vault_path, entry_uuid, {
                "notebook_id": notebook_id,
                "timestamp": time.time_ns(),
                "nonce": nonce.hex(),
                "encrypted_keys": encrypted_keys.hex()
            })

        # Update session cache
        self.manager.session_keys._cache[notebook_id] = new_crypto

        # Git commit
        system_name = platform.node()
        try:
            git_manager = self.manager.get_git_manager_by_path(folder_path)
            git_manager._run_git_command(["git", "add", ".tn_recovery", ".tn_password"])
            git_manager._run_git_command([
                "git", "commit", "-m",
                f"SECURITY: password changed | method: recovery_phrase | machine: {system_name} | root: {notebook_id}"
            ])
        except Exception as e:
            print(f"  Git commit failed: {e}")

        # Lock the notebook
        if notebook_id in self.manager.session_keys._cache:
            del self.manager.session_keys._cache[notebook_id]
        
        for nb in self.manager.notebooks:
            if nb.id == notebook_id:
                nb.custom_path = None
                nb.locked = True
                if hasattr(nb, '_crypto'):
                    delattr(nb, '_crypto')
                break

        # Update master registry lock state
        if system_entry:
            system_entry["locked"] = True
            self.manager.save_registry(master_registry)

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
        """Show trusted devices list from all reachable vaults"""
        from secure_session import SecureSessionStorage
        import shutil
        import socket
        import os
        
        notebook_id = notebook['id']
        
        # Get vault_manager from notebook_manager
        vm = self.notebook_manager.vault_manager
        
        # Get all reachable vaults from master registry
        try:
            master_registry = self.manager.load_registry(force_reload=True)
            fp_hash = self.manager._compute_fp_hash()
            current_system_name = socket.gethostname()
        except:
            master_registry = {}
            fp_hash = None
            current_system_name = "unknown"
        
        # Collect all entries from all reachable vaults
        all_entries = []
        
        if fp_hash and master_registry:
            notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
            
            # Get all system entries for this notebook (from all vaults)
            systems = notebook_data.get("systems", {})
            
            for system_fp_hash, system_entry in systems.items():
                vault_name = system_entry.get("vault", "default")
                entry_uuid = system_entry.get("entry")
                system_name = system_entry.get("system_name", system_fp_hash[:16])  # ← Use stored name
                
                if not entry_uuid:
                    continue
                
                # Get vault path
                vault_path = vm.get_vault_path(vault_name)
                if not vault_path or not os.path.exists(vault_path):
                    continue
                
                # Read entry from vault to get trusted device info
                entry_data = vm.get_entry_from_vault(vault_path, entry_uuid)
                if entry_data:
                    timestamp = entry_data.get("timestamp", 0)
                    
                    # Check if this is the current system
                    is_current = (system_fp_hash == fp_hash)
                    
                    all_entries.append({
                        "timestamp": timestamp,
                        "system_name": system_name,
                        "system_fp_hash": system_fp_hash,
                        "vault_name": vault_name,
                        "active": is_current,
                        "entry_uuid": entry_uuid,
                        "vault_path": vault_path
                    })
        
        # Also check legacy vaults for backward compatibility
        try:
            old_storage = SecureSessionStorage(self.app_dir)
            old_entries = old_storage.list_entries(notebook_id)
            for entry in old_entries:
                # Check if already in list by system_name
                if not any(e.get("system_name") == entry.get("system_name") for e in all_entries):
                    all_entries.append({
                        "timestamp": entry.get("timestamp", 0),
                        "system_name": entry.get("system_name", "unknown"),
                        "active": entry.get("active", False),
                        "legacy": True
                    })
        except:
            pass
        
        # Sort by timestamp (newest first)
        all_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        
        if not all_entries:
            print("\n  No trusted devices found.")
            self.get_input("\nPress Enter to continue...")
            return
        
        page = 0
        
        while True:
            self.clear_screen()
            width, height = shutil.get_terminal_size()
            
            # Header
            print("" * width)
            header = f"Trusted Devices - {notebook['name']}"
            print(f"{header:^{width}}")
            print("" * width)
            print()
            
            # Pagination
            from cs_ui import PaginationManager
            items_per_page, total_pages = PaginationManager.calculate(
                len(all_entries), height, fixed_lines=8
            )
            
            if page >= total_pages:
                page = max(0, total_pages - 1)
            
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(all_entries))
            page_entries = all_entries[start_idx:end_idx]
            current_page = page + 1
            
            # Display entries
            for i, entry in enumerate(page_entries, 1):
                is_current = entry.get("active", False)
                system_name = entry.get("system_name", "unknown")
                vault_name = entry.get("vault_name", "default")
                is_legacy = entry.get("legacy", False)
                
                if is_current:
                    line = f"[{i}] {system_name} [ACTIVE]"
                else:
                    line = f"[{i}] {system_name}"
                
                # Show vault info for non-legacy entries
                if not is_legacy and vault_name != "default":
                    line += f" (vault: {vault_name})"
                elif is_legacy:
                    line += " (legacy)"
                
                # Truncate if too long
                if len(line) > width - 4:
                    line = line[:width-7] + "..."
                
                print(line)
            
            # Page indicator
            if total_pages > 1:
                print()
                PaginationManager.show_indicator(page, total_pages, width)
            else:
                print()
            
            # Footer
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
                    is_current = entry.get("active", False)
                    system_fp_hash = entry.get("system_fp_hash")
                    entry_uuid = entry.get("entry_uuid")
                    vault_path = entry.get("vault_path")
                    is_legacy = entry.get("legacy", False)
                    
                    if is_current:
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
                        
                        # Remove from master registry (system entry)
                        if system_fp_hash and master_registry:
                            notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
                            if system_fp_hash in notebook_data.get("systems", {}):
                                del notebook_data["systems"][system_fp_hash]
                                if not notebook_data["systems"]:
                                    del master_registry["notebooks"][notebook_id]
                                self.manager.save_registry(master_registry)
                        
                        # Remove from vault
                        if entry_uuid and vault_path and os.path.exists(vault_path):
                            vm.remove_entry_from_vault(vault_path, entry_uuid)
                        
                        self._lock_notebook_immediately(notebook_id)
                        print("\n  ✓ This machine's trust removed.")
                        print("  ✓ Notebook locked.")
                        self.get_input("\nPress Enter to continue...")
                        return
                    
                    else:
                        print(f"\n  Remove trusted device '{entry['system_name']}'?")
                        confirm = self.get_input("\n  Confirm removal? [y/N]: ").lower()
                        
                        if confirm == 'y':
                            # Remove from master registry
                            if system_fp_hash and master_registry:
                                notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
                                if system_fp_hash in notebook_data.get("systems", {}):
                                    del notebook_data["systems"][system_fp_hash]
                                    self.manager.save_registry(master_registry)
                            
                            # Remove from vault
                            if entry_uuid and vault_path and os.path.exists(vault_path):
                                vm.remove_entry_from_vault(vault_path, entry_uuid)
                            
                            # Remove from legacy storage if present
                            if is_legacy:
                                old_storage = SecureSessionStorage(self.app_dir)
                                old_storage.remove_entry(notebook_id, entry.get("timestamp"))
                            
                            print(f"\n  ✓ Device removed successfully!")
                            
                            # Refresh entries
                            all_entries = [e for e in all_entries if e.get("system_fp_hash") != system_fp_hash]
                            page = 0
                            if not all_entries:
                                print("\n  No trusted devices remain.")
                                self.get_input("\nPress Enter to continue...")
                                break
                        else:
                            print("\n  Cancelled.")
                            self.get_input("\nPress Enter to continue...")
    
    def _change_vault_location(self, notebook):
        """Change vault location for current system only (notebook unlocked)"""
        from secure_session import SecureSessionStorage
        import json
        import os
        import time
        import uuid as uuid_lib

        self.clear_screen()
        self.print_header(f"Change Vault Location - {notebook['name']}")

        notebook_id = notebook['id']
        crypto = self.manager.session_keys.get(notebook_id)
        if not crypto:
            print("\n  Notebook must be unlocked first.")
            self.get_input("\nPress Enter to continue...")
            return

        # Get current system fingerprint hash
        fp_hash = self.manager._compute_fp_hash()
        
        # Load master registry
        registry = self.manager.load_registry(force_reload=True)
        
        # Get current system entry
        notebook_data = registry.get("notebooks", {}).get(notebook_id)
        current_system_entry = None
        if notebook_data:
            current_system_entry = notebook_data.get("systems", {}).get(fp_hash)
        
        if not current_system_entry:
            print("\n  Notebook not registered on this system.")
            self.get_input("\nPress Enter to continue...")
            return
        
        # Get current vault info
        current_vault_name = current_system_entry.get("vault", "default")
        current_entry_uuid = current_system_entry.get("entry")
        current_vault_path = self.manager.vault_manager.get_vault_path(current_vault_name)
        
        # Format display path
        def format_vault_path(vault_name, vault_path):
            if vault_name == "default":
                return "config/session.vault"
            if vault_path:
                return os.path.basename(vault_path)
            return "unknown"
        
        print(f"\n  Current: {current_vault_name if current_vault_name != 'default' else 'DEFAULT'}")
        print(f"           {format_vault_path(current_vault_name, current_vault_path)}")
        print()

        # STEP 2: Present options
        options = []
        option_num = 1

        all_vaults = self.manager.vault_manager.list_vaults()
        custom_vaults = {k: v for k, v in all_vaults.items() if k != "default"}

        seen_locations = set()

        for vault_name, vault_path in list(custom_vaults.items())[:5]:
            if current_vault_name == vault_name:
                continue
            if vault_path in seen_locations:
                continue
            
            seen_locations.add(vault_path)
            display_location = format_vault_path(vault_name, vault_path)
            print(f"  [{option_num}] {display_location}")
            options.append(("existing", option_num, vault_name, vault_path))
            option_num += 1

        print(f"  [{option_num}] Create new vault")
        options.append(("new", option_num))
        option_num += 1

        if current_vault_name != "default":
            print(f"  [{option_num}] Default vault")
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

        target_vault_name = None
        target_vault_path = None

        for opt in options:
            if len(opt) >= 2 and opt[1] == choice_num:
                if opt[0] == "default":
                    target_vault_name = "default"
                    target_vault_path = os.path.join(self.app_dir, "config", "session.vault")
                elif opt[0] == "existing":
                    target_vault_name = opt[2]
                    target_vault_path = opt[3]
                elif opt[0] == "new":
                    result = self._create_new_vault_location(notebook)
                    if result:
                        target_vault_name, target_vault_path = result
                    else:
                        return
                elif opt[0] == "back":
                    return
                break

        if not target_vault_name or not target_vault_path:
            return

        # STEP 3: Show confirmation
        self.clear_screen()
        self.print_header(f"Change Vault Location - {notebook['name']}")

        print()
        print(f"  From: {current_vault_name if current_vault_name != 'default' else 'DEFAULT'}")
        print(f"        {format_vault_path(current_vault_name, current_vault_path)}")
        print()
        print(f"  To:   {target_vault_name if target_vault_name != 'default' else 'DEFAULT'}")
        print(f"        {format_vault_path(target_vault_name, target_vault_path)}")
        print()
        
        confirm = self.get_input("  Confirm change? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("\n  Cancelled.")
            self.get_input("\nPress Enter to continue...")
            return

        # STEP 4: Ensure target vault exists
        if not os.path.exists(target_vault_path):
            os.makedirs(os.path.dirname(target_vault_path), exist_ok=True)
            if target_vault_name != "default":
                self.manager.vault_manager.create_vault_file(target_vault_name, os.path.dirname(target_vault_path))
            else:
                with open(target_vault_path, 'w') as f:
                    json.dump({"version": 2, "entries": {}}, f)

        # STEP 5: Get current entry data from old vault
        entry_data = None
        if current_entry_uuid:
            entry_data = self.manager.vault_manager.get_entry_from_vault(current_vault_path, current_entry_uuid)
        
        if not entry_data:
            print("\n  Could not retrieve current vault entry.")
            self.get_input("\nPress Enter to continue...")
            return
        
        # STEP 6: Write entry to new vault (preserve same entry_uuid)
        success = self.manager.vault_manager.add_entry_to_vault(
            target_vault_path, current_entry_uuid, entry_data
        )
        
        if not success:
            print("\n  Failed to write to new vault.")
            self.get_input("\nPress Enter to continue...")
            return
        
        migrated_count = 1
        
        # Also copy any other entries for this notebook from old vault (other systems)
        old_vault_data = self.manager.vault_manager.read_vault_file(current_vault_path)
        for uuid, entry in old_vault_data.get("entries", {}).items():
            if uuid != current_entry_uuid and entry.get("notebook_id") == notebook_id:
                self.manager.vault_manager.add_entry_to_vault(target_vault_path, uuid, entry)
                migrated_count += 1

        # STEP 7: Remove old entries from old vault
        for uuid in list(old_vault_data.get("entries", {}).keys()):
            entry = old_vault_data["entries"][uuid]
            if entry.get("notebook_id") == notebook_id:
                self.manager.vault_manager.remove_entry_from_vault(current_vault_path, uuid)

        # STEP 8: Update master registry for current system
        registry = self.manager.load_registry(force_reload=True)
        
        if notebook_id not in registry.get("notebooks", {}):
            registry["notebooks"][notebook_id] = {
                "name": notebook['name'],
                "folder_name": os.path.basename(notebook.get('path', '')),
                "created": datetime.now().isoformat(),
                "systems": {}
            }
        
        # Update current system's entry
        registry["notebooks"][notebook_id]["systems"][fp_hash] = {
            "path": current_system_entry.get("path"),
            "vault": target_vault_name,
            "entry": current_entry_uuid,
            "locked": False  # Keep unlocked after migration
        }
        
        self.manager.save_registry(registry)

        # STEP 9: Update vault registry (no longer needed - vault paths are in vault_manager)
        # The vault registry is already updated when we created the vault file

        # STEP 10: Clear caches and reload
        if notebook_id in self.manager.session_keys:
            del self.manager.session_keys[notebook_id]
        if hasattr(self.manager.session_keys, 'clear_cache'):
            self.manager.session_keys.clear_cache(notebook_id)
        self.manager.encrypted_notebooks.discard(notebook_id)
        
        self.manager.load_all_notebooks(quiet=True)
        self.notebook_manager.load_notebooks()
        
        # Update the passed-in notebook dict
        fresh_core = self.manager.find_notebook_by_id(notebook_id)
        if fresh_core:
            notebook['vault_id'] = target_vault_name if target_vault_name != "default" else None
            notebook['locked'] = fresh_core.locked
            notebook['path'] = fresh_core.custom_path

        # STEP 11: Final confirmation
        display_name = target_vault_name if target_vault_name != "default" else "DEFAULT"
        print(f"\n  Vault changed to: {display_name}")
        print(f"  Migrated {migrated_count} trusted device entries")
        self.get_input("\nPress Enter to continue...")


    def _create_new_vault_location(self, notebook):
        """Create a new vault location - with .vault file naming"""
        import json
        import uuid
        
        self.clear_screen()
        self.print_header("Create New Vault Location")
        
        print()
        print("  Enter the DIRECTORY where the vault file will be stored.")
        print("  Vault files use .vault extension (e.g., vault_abc123.vault)")
        print()
        print("  Examples:")
        print("    /mnt/usb/          → creates /mnt/usb/vault_xxx.vault")
        print("    /home/user/.vaults/ → creates /home/user/.vaults/vault_xxx.vault")
        print("    D:\\vaults\\        → creates D:\\vaults\\vault_xxx.vault")
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
            except Exception as e:
                print(f"\n  ✗ Cannot create directory: {e}")
                self.get_input("Press Enter to continue...")
                return None
        
        # Check for existing .vault files in this directory
        existing_vault_files = []
        for f in os.listdir(location):
            filepath = os.path.join(location, f)
            if os.path.isfile(filepath) and (f.endswith('.vault') or f == 'session.vault'):
                existing_vault_files.append(filepath)
        
        vm = self.notebook_manager.vault_manager
        
        if existing_vault_files:
            print(f"\n  Found {len(existing_vault_files)} existing vault file(s):")
            for i, vf in enumerate(existing_vault_files, 1):
                vault_id = vm.get_vault_id_from_file(vf)
                print(f"    [{i}] {os.path.basename(vf)} (ID: {vault_id})")
            
            print()
            print("  Options:")
            print("    1) Use existing vault")
            print("    2) Create new vault (will create new .vault file)")
            print("    3) Cancel")
            print()
            
            choice = self.get_input("  Choose [1-3]: ").strip()
            
            if choice == "1":
                # 🟢 FIX: Auto-select if only one vault exists
                if len(existing_vault_files) == 1:
                    selected_file = existing_vault_files[0]
                    vault_id = vm.get_vault_id_from_file(selected_file)
                    print(f"\n  Using existing vault: {vault_id}")
                    
                    # Ensure vault exists in registry
                    if not vm.get_vault_path(vault_id):
                        vm.set_vault_path(vault_id, selected_file)
                    
                    return vault_id, selected_file
                else:
                    print()
                    file_choice = self.get_input(f"  Select vault [1-{len(existing_vault_files)}]: ").strip()
                    try:
                        idx = int(file_choice) - 1
                        if 0 <= idx < len(existing_vault_files):
                            selected_file = existing_vault_files[idx]
                            vault_id = vm.get_vault_id_from_file(selected_file)
                            
                            # Ensure vault exists in registry
                            if not vm.get_vault_path(vault_id):
                                vm.set_vault_path(vault_id, selected_file)
                            
                            print(f"\n  Using existing vault: {vault_id}")
                            return vault_id, selected_file
                    except:
                        pass
                    return None
            
            elif choice == "2":
                # Create new vault
                vault_id = f"vault_{uuid.uuid4().hex[:8]}"
                vault_file_path = os.path.join(location, f"{vault_id}.vault")
                
                if os.path.exists(vault_file_path):
                    print(f"\n  ✗ File already exists: {vault_file_path}")
                    self.get_input("Press Enter to continue...")
                    return None
                
                # Create vault file
                vm.create_vault_file(vault_id, location)
                
                print(f"\n  ✓ Created new vault: {vault_id}")
                print(f"     File: {os.path.basename(vault_file_path)}")
                return vault_id, vault_file_path
            
            else:
                return None
        
        # No existing vaults - create new
        vault_id = f"vault_{uuid.uuid4().hex[:8]}"
        vault_file_path = os.path.join(location, f"{vault_id}.vault")
        
        vm.create_vault_file(vault_id, location)
        
        print(f"\n  ✓ Created new vault: {vault_id}")
        print(f"     File: {os.path.basename(vault_file_path)}")
        
        return vault_id, vault_file_path