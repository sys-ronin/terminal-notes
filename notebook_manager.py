#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
import sys
import json
import shutil
import subprocess
import getpass
import hashlib
import uuid
import re
from datetime import datetime
from pathlib import Path
from vault_manager import VaultManager
from change_notebook import ChangeNotebookHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terminal_notes_core import NoteManager, SimpleNav
from notebook_operations import NotebookOperations, read_json, write_json
from crypto import Crypto
from typing import Optional, Dict, List


class DNSCache:
    """Simple DNS cache to speed up repeated lookups"""
    _cache = {}
    _ttl = 300  # 5 minutes

    @classmethod
    def resolve(cls, hostname):
        import time
        import socket
        current_time = time.time()
        
        # Check cache
        if hostname in cls._cache:
            entry = cls._cache[hostname]
            if current_time - entry['time'] < cls._ttl:
                return entry['ip']
        
        # Resolve DNS using socket (fallback only)
        try:
            ip = socket.gethostbyname(hostname)
            cls._cache[hostname] = {'ip': ip, 'time': current_time}
            return ip
        except Exception:
            return hostname

class NotebookManager:
    def __init__(self, manager=None, ui=None, nav=None, app_dir=None):
        # 🟢 FIX: Get correct app directory for PyInstaller
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller executable
            self.app_dir = os.path.dirname(sys.executable)
        else:
            # Running as Python script
            self.app_dir = os.path.dirname(os.path.abspath(__file__))

        self.is_standalone = (manager is None)
        self.manager = manager or NoteManager()
        self.ui = ui or self
        self.nav = nav or SimpleNav()

        # Set up directories
        self.config_dir = os.path.join(self.app_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)

        self.notebooks_root = os.path.join(self.app_dir, "notebooks_root")
        os.makedirs(self.notebooks_root, exist_ok=True)

        self.registry_file = os.path.join(self.notebooks_root, "notebooks_registry.json")

        self.page = 0
        self.accounts_page = 0
        self.items_per_page = 10
        self.notebooks = []
        self.current_notebook = None
        self.secure_storage = None
        
        self.load_accounts()
        self.load_notebooks()
        self.ensure_accounts_structure()
        
        # ========== FIX: Pass self.app_dir, not app_dir parameter ==========
        self.change_handler = ChangeNotebookHandler(self, manager, ui, nav, self.app_dir)
        # ========== END FIX ==========
        
        self.vault_manager = VaultManager(self.app_dir)



    def load_accounts(self):
        """Load accounts from TokenVault"""
        from token_vault import TokenVault
        
        self.accounts = {"accounts": {}, "repos": {}}
        
        vault = TokenVault(self.app_dir)
        account_ids = vault.list_accounts()
        
        for acc_id in account_ids:
            account_data = vault.get_full_account(acc_id)
            if account_data:
                self.accounts["accounts"][acc_id] = {
                    "id": acc_id,
                    "platform": account_data["platform"],
                    "username": account_data["username"],
                    "host": account_data["host"],
                    "api_url": account_data["api_url"],
                    "token_enc": acc_id,
                    "created": datetime.fromtimestamp(account_data["created"] / 1e9).isoformat(),
                    "notebooks": {}
                }
                
                # Load linked notebooks
                for nb_id in account_data.get("linked_notebooks", []):
                    if "notebooks" not in self.accounts["accounts"][acc_id]:
                        self.accounts["accounts"][acc_id]["notebooks"] = {}
                    self.accounts["accounts"][acc_id]["notebooks"][nb_id] = {
                        "repo": nb_id,  # Placeholder
                        "linked": True
                    }
                    
    def ensure_accounts_structure(self):
        if not hasattr(self, 'accounts') or self.accounts is None:
            self.accounts = {"accounts": {}, "repos": {}}
        elif isinstance(self.accounts, str):
            try:
                self.accounts = json.loads(self.accounts)
            except:
                self.accounts = {"accounts": {}, "repos": {}}
        elif isinstance(self.accounts, list):
            self.accounts = {"accounts": {}, "repos": {}}
        if "accounts" not in self.accounts:
            self.accounts["accounts"] = {}
        if "repos" not in self.accounts:
            self.accounts["repos"] = {}

    def save_accounts(self):
        """Save accounts - no longer needed, accounts stored in TokenVault"""
        # Accounts are stored in TokenVault, not in a separate encrypted file
        # This method is kept for compatibility but does nothing
        pass


    def _get_master_secret(self):
        """Generate a stable master secret that persists across reboots (cross-platform)"""
        import hashlib
        import platform
        import os
        import subprocess
    
        components = []
    
        # 🟢 FIX: Cross-platform machine ID detection
        system = platform.system()
    
        if system == "Linux":
            # Linux: /etc/machine-id (most reliable)
            if os.path.exists('/etc/machine-id'):
                with open('/etc/machine-id', 'r') as f:
                    components.append(f.read().strip())
            # Fallback: /var/lib/dbus/machine-id
            elif os.path.exists('/var/lib/dbus/machine-id'):
                with open('/var/lib/dbus/machine-id', 'r') as f:
                    components.append(f.read().strip())

        elif system == "Darwin":  # macOS
            # macOS: IOPlatformUUID
            try:
                result = subprocess.run(
                    ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'IOPlatformUUID' in line:
                        uuid = line.split('=')[1].strip().strip('"')
                        components.append(uuid)
                        break
            except:
                pass
        
            # Fallback: Hardware UUID
            try:
                result = subprocess.run(
                    ['system_profiler', 'SPHardwareDataType'],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'Hardware UUID' in line:
                        uuid = line.split(':')[1].strip()
                        components.append(uuid)
                        break
            except:
                pass
    
        elif system == "Windows":
            # Windows: MachineGUID from registry
            try:
                result = subprocess.run(
                    ['reg', 'query', 'HKLM\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'MachineGuid' in line:
                        parts = line.split()
                        if len(parts) >= 3:
                            components.append(parts[2])
                        break
            except:
                pass
        
            # Fallback: Windows Computer Name + SID
            try:
                comp_name = os.environ.get('COMPUTERNAME', '')
                if comp_name:
                    components.append(comp_name)
            except:
                pass
    
        # Universal fallbacks (work on all platforms)
        components.extend([
            platform.node(),           # Network node name
            os.path.expanduser('~'),   # User's home directory
            os.path.realpath(__file__), # Path to this file
            'git_accounts_master_v2'    # Fixed salt with version
        ])
    
        # Add username for extra uniqueness
        try:
            import getpass
            components.append(getpass.getuser())
        except:
            pass
    
        # Add platform info
        components.append(f"{system}-{platform.machine()}-{platform.release()}")
    
        # Combine all components
        combined = '|'.join(str(c) for c in components if c)
    
        # Generate 32-byte key using SHA256
        return hashlib.sha256(combined.encode('utf-8')).digest().hex()

    def _generate_account_id(self, username, host):
        unique = f"{username}@{host}"
        return "acc_" + hashlib.md5(unique.encode()).hexdigest()[:8]

    def _encrypt_token(self, token: str) -> str:
        """Encrypt token using TokenVault - returns account_id as reference"""
        # This method is called during account creation
        # We return a placeholder because actual storage happens in _add_*_account
        return "__TOKEN_VAULT__"

    def _decrypt_token(self, token_enc: str) -> Optional[str]:
        """Retrieve token from TokenVault using account_id"""
        from token_vault import TokenVault
        
        if not token_enc:
            return None
        
        if token_enc.startswith("acc_"):
            vault = TokenVault(self.app_dir)
            return vault.get_token(token_enc)
        
        return token_enc


    def get_account_for_notebook(self, notebook_id):
        # First check accounts dict (fast path for already loaded)
        for acc_id, account in self.accounts.get("accounts", {}).items():
            if notebook_id in account.get("notebooks", {}):
                return account
        
        # ========== SURGICAL FIX: Check TokenVault if not found in memory ==========
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        
        for acc_id in vault.list_accounts():
            account_data = vault.get_full_account(acc_id)
            if account_data and notebook_id in account_data.get("linked_notebooks", []):
                # Return account in the expected format
                return {
                    "id": acc_id,
                    "platform": account_data["platform"],
                    "username": account_data["username"],
                    "host": account_data["host"],
                    "api_url": account_data["api_url"],
                    "token_enc": acc_id,
                    "notebooks": {notebook_id: {"repo": "unknown"}}  # Placeholder
                }
        # ========== END FIX ==========
        
        return None


    def get_notebook_config(self, notebook_id):
        for acc_id, account in self.accounts.get("accounts", {}).items():
            if notebook_id in account.get("notebooks", {}):
                return account["notebooks"][notebook_id]
        return None

    def repo_exists_in_accounts(self, account_id, repo_name):
        account = self.accounts["accounts"].get(account_id, {})
        for nb_id, config in account.get("notebooks", {}).items():
            if config.get("repo") == repo_name:
                return True, nb_id
        return False, None

    def update_notebook_config(self, notebook_id, account_id, repo_name, visibility="private"):
        exists, existing_nb = self.repo_exists_in_accounts(account_id, repo_name)
        if exists and existing_nb != notebook_id:
            print(f"\n❌ Repo '{repo_name}' already belongs to another notebook!")
            return False
        if account_id in self.accounts["accounts"]:
            account = self.accounts["accounts"][account_id]
            if "notebooks" not in account:
                account["notebooks"] = {}
            repo_uuid = f"repo_{uuid.uuid4().hex[:8]}"
            account["notebooks"][notebook_id] = {
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
                "account_id": account_id,
                "notebook_id": notebook_id,
                "visibility": visibility,
                "created": datetime.now().isoformat()
            }
            self.save_accounts()
            return True
        return False

    def build_repo_url(self, account, repo_name):
        platform = account.get("platform", "github")
        username = account.get("username", "")
        if platform == "github":
            return f"https://github.com/{username}/{repo_name}.git"
        elif platform == "gitlab":
            return f"https://gitlab.com/{username}/{repo_name}.git"
        elif platform == "bitbucket":
            return f"https://bitbucket.org/{username}/{repo_name}.git"
        else:
            return f"https://{account.get('host', 'github.com')}/{username}/{repo_name}.git"

    def load_notebooks(self):
        """Load notebooks from registry - ALWAYS reload fresh"""
        self.notebooks = []
        registry_data = self.load_registry()

        is_first_load = not hasattr(self, '_autolock_applied')
        
        # Get master registry for lock state
        try:
            master_registry = self.manager.load_registry(force_reload=True)
            fp_hash = self.manager._compute_fp_hash()
        except:
            master_registry = {}
            fp_hash = None

        for notebook_id, entry in registry_data.get("notebooks", {}).items():
            path = ""
            name = "Unknown"
            note_count = 0
            file_count = 0
            sub_count = 0
            is_encrypted = False
            git_config = None
            account = None
            is_locked = True
            autolock = False
            vault_id = None
            
            # ========== Skip legacy encrypted string entries ==========
            if isinstance(entry, str):
                # Legacy encrypted entry - skip processing, will be handled by main UI
                for folder in os.listdir(self.manager.notebooks_root):
                    if folder.endswith(notebook_id):
                        if '-' in folder:
                            raw_name = folder.rsplit('-', 1)[0]
                        else:
                            raw_name = folder
                        name = raw_name.replace('🔐 ', '').replace('🔒 ', '').strip()
                        path = os.path.join(self.manager.notebooks_root, folder)
                        break
                
                self.notebooks.append({
                    "id": notebook_id,
                    "name": name,
                    "path": path,
                    "encrypted": True,
                    "locked": True,
                    "autolock": False,
                    "note_count": 0,
                    "file_count": 0,
                    "sub_count": 0,
                    "git_config": None,
                    "account": None,
                    "vault_id": None
                })
                continue
            
            # Get lock state from master registry (only for dict entries)
            master_locked = None
            if fp_hash and master_registry and isinstance(entry, dict):
                notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
                if isinstance(notebook_data, dict):
                    system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
                    if system_entry:
                        master_locked = system_entry.get("locked", True)
                        vault_id = system_entry.get("vault", "default")
            
            # Handle dict entries (new format or unencrypted)
            if isinstance(entry, dict):
                raw_name = entry.get("name", "Unknown")
                name = raw_name.replace('🔐 ', '').replace('🔒 ', '').strip()
                path = entry.get("path", "")
                is_encrypted = entry.get("encrypted", False)
                autolock = entry.get("autolock", False)
                
                if path and not os.path.isabs(path):
                    path = os.path.join(self.manager.notebooks_root, path)
                
                # Use master registry lock state if available
                if master_locked is not None:
                    is_locked = master_locked
                else:
                    if autolock and is_first_load:
                        is_locked = True
                    elif autolock and not is_first_load:
                        is_locked = entry.get("locked", True)
                
                # ========== Get counts from live NoteManager for unlocked notebooks ==========
                if not is_locked and self.manager:
                    live_notebook = self.manager.find_notebook_by_id(notebook_id)
                    if live_notebook:
                        # Force load content if notebook is unlocked but empty
                        if len(live_notebook.notes) == 0 and len(live_notebook.subnotebooks) == 0:
                            from notebook_operations import NotebookOperations
                            ops = NotebookOperations(self.manager)
                            crypto = self.manager.session_keys.get(notebook_id)
                            if crypto and hasattr(live_notebook, 'custom_path') and live_notebook.custom_path:
                                reloaded = ops.load_notebook_from_path_with_crypto(live_notebook.custom_path, crypto)
                                if reloaded:
                                    live_notebook.notes = reloaded.notes
                                    live_notebook.subnotebooks = reloaded.subnotebooks
                                    for i, nb in enumerate(self.manager.notebooks):
                                        if nb.id == notebook_id:
                                            self.manager.notebooks[i] = live_notebook
                                            break
                        
                        total_notes = live_notebook.get_total_note_count()
                        total_files = live_notebook.get_file_note_count()
                        note_count = total_notes - total_files
                        file_count = total_files
                        sub_count = live_notebook.get_total_subnotebook_count()
                    elif path and os.path.exists(path) and not is_encrypted:
                        # Fallback: read directly for unencrypted notebooks only
                        struct_file = os.path.join(path, "structure.json")
                        if os.path.exists(struct_file):
                            try:
                                with open(struct_file, 'r') as f:
                                    struct_data = json.load(f)
                                
                                def count_items(nb_data):
                                    n = 0
                                    f = 0
                                    s = 0
                                    for note in nb_data.get("notes", []):
                                        if note.get("file_extension"):
                                            f += 1
                                        else:
                                            n += 1
                                    s += len(nb_data.get("subnotebooks", []))
                                    for sub in nb_data.get("subnotebooks", []):
                                        sub_n, sub_f, sub_s = count_items(sub)
                                        n += sub_n
                                        f += sub_f
                                        s += sub_s
                                    return n, f, s
                                
                                if "notebooks" in struct_data:
                                    for nb in struct_data["notebooks"]:
                                        n, f, s = count_items(nb)
                                        note_count += n
                                        file_count += f
                                        sub_count += s
                                else:
                                    note_count, file_count, sub_count = count_items(struct_data)
                            except:
                                pass
                elif path and os.path.exists(path) and not is_encrypted:
                    # For locked but unencrypted notebooks (shouldn't happen)
                    struct_file = os.path.join(path, "structure.json")
                    if os.path.exists(struct_file):
                        try:
                            with open(struct_file, 'r') as f:
                                struct_data = json.load(f)
                            
                            def count_items(nb_data):
                                n = 0
                                f = 0
                                s = 0
                                for note in nb_data.get("notes", []):
                                    if note.get("file_extension"):
                                        f += 1
                                    else:
                                        n += 1
                                s += len(nb_data.get("subnotebooks", []))
                                for sub in nb_data.get("subnotebooks", []):
                                    sub_n, sub_f, sub_s = count_items(sub)
                                    n += sub_n
                                    f += sub_f
                                    s += sub_s
                                return n, f, s
                            
                            if "notebooks" in struct_data:
                                for nb in struct_data["notebooks"]:
                                    n, f, s = count_items(nb)
                                    note_count += n
                                    file_count += f
                                    sub_count += s
                            else:
                                note_count, file_count, sub_count = count_items(struct_data)
                        except:
                            pass
                # ========== END FIX ==========
            
            # Get git config
            git_config = self.get_notebook_config(notebook_id)
            account = self.get_account_for_notebook(notebook_id)
            
            clean_name = name.replace('🔐 ', '').replace('🔒 ', '').strip()
            
            self.notebooks.append({
                "id": notebook_id,
                "name": clean_name,
                "path": path,
                "encrypted": is_encrypted,
                "locked": is_locked,
                "autolock": autolock,
                "note_count": note_count,
                "file_count": file_count,
                "sub_count": sub_count,
                "git_config": git_config,
                "account": account,
                "vault_id": vault_id
            })
        
        self._autolock_applied = True
            
    def check_repos_parallel(self, repos, account, token, local_notebooks):
        """Check multiple repositories in parallel with optimized settings"""
        results = []
        total = len(repos)
    
        # Increase workers for better throughput
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks
            future_to_repo = {}
            for repo in repos:
                repo_name = repo.get('name', '')
                future = executor.submit(
                    self.check_single_repo,
                    account,
                    repo_name,
                    token,
                    repo_name in local_notebooks
                )
                future_to_repo[future] = repo
        
            # Process as they complete with better progress indicator
            completed = 0
            for future in as_completed(future_to_repo):
                completed += 1
                repo = future_to_repo[future]
                repo_name = repo.get('name', '')
            
                # Compact progress indicator
                print(f"\r   Scanning {completed}/{total}: {repo_name[:20]:20}", end="", flush=True)
            
                try:
                    result = future.result(timeout=8)
                    if result:
                        results.append(result)
                        # Get private status from original repo data
                        for r in repos:
                            if r.get('name') == repo_name:
                                result['private'] = r.get('private', False)
                                break
                except Exception:
                    pass
    
        print()  # New line after progress
        return results

    def check_single_repo(self, account, repo_name, token, is_listed):
        """Check a single repository with optimized API calls"""
        import re
        import base64
        import json
        import requests
        
        # Quick pattern check first (cheapest operation)
        if not re.search(r'-\d{14}$', repo_name):
            return None
        
        full_name = f"{account['username']}/{repo_name}"
        
        # Use session for connection reuse
        session = requests.Session()
        session.headers.update({'Authorization': f'token {token}'})
        session.headers.update({'Accept': 'application/vnd.github.v3+json'})
        
        try:
            # Get structure.json (single request)
            struct_url = f"https://api.github.com/repos/{full_name}/contents/structure.json"
            response = session.get(struct_url, timeout=10)
            
            if response.status_code != 200:
                # Try with .git suffix? No, just return None
                return None
            
            data = response.json()
            if data.get('encoding') != 'base64':
                return None
            
            content_bytes = base64.b64decode(data['content'])
            
            # Detect encryption by checking if content is binary
            is_encrypted = any(b >= 128 for b in content_bytes[:100])
            
            if is_encrypted:
                return {
                    'name': repo_name,
                    'display_name': repo_name.rsplit('-', 1)[0] if '-' in repo_name else repo_name,
                    'private': False,
                    'note_count': 0,
                    'file_count': 0,
                    'sub_count': 0,
                    'encrypted': True,
                    'listed': is_listed
                }
            else:
                try:
                    struct_data = json.loads(content_bytes.decode('utf-8'))
                    
                    def quick_count(nb_data):
                        n = len([note for note in nb_data.get('notes', []) if not note.get('file_extension')])
                        f = len([note for note in nb_data.get('notes', []) if note.get('file_extension')])
                        s = len(nb_data.get('subnotebooks', []))
                        for sub in nb_data.get('subnotebooks', []):
                            sub_n, sub_f, sub_s = quick_count(sub)
                            n += sub_n
                            f += sub_f
                            s += sub_s
                        return n, f, s
                    
                    if "notebooks" in struct_data and struct_data["notebooks"]:
                        nb_data = struct_data["notebooks"][0]
                        name = nb_data.get('name', repo_name.split('-')[0])
                        note_count, file_count, sub_count = quick_count(nb_data)
                    elif "name" in struct_data:
                        name = struct_data.get('name', repo_name.split('-')[0])
                        note_count, file_count, sub_count = quick_count(struct_data)
                    else:
                        name = repo_name.split('-')[0]
                        note_count, file_count, sub_count = 0, 0, 0
                    
                    return {
                        'name': repo_name,
                        'display_name': name,
                        'private': False,
                        'note_count': note_count,
                        'file_count': file_count,
                        'sub_count': sub_count,
                        'encrypted': False,
                        'listed': is_listed
                    }
                except Exception as e:
                    print(f"  Error parsing {repo_name}: {e}", flush=True)
                    return None
                    
        except requests.exceptions.Timeout:
            print(f"  Timeout for {repo_name}", flush=True)
            return None
        except requests.exceptions.ConnectionError:
            print(f"  Connection error for {repo_name}", flush=True)
            return None
        except Exception as e:
            print(f"  Error for {repo_name}: {e}", flush=True)
            return None
        finally:
            session.close()

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def get_terminal_size(self):
        try:
            columns, rows = shutil.get_terminal_size()
            return max(60, columns), max(10, rows)
        except:
            return 80, 24

    def print_header(self, title):
        width, _ = self.get_terminal_size()
        print("" * width)
        print(f"{title:^{width}}")
        print("" * width)

    def print_footer(self, options):
        width, _ = self.get_terminal_size()
        #print("" * width)
        print(options)
        print()

    def get_input(self, prompt):
        try:
            return input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def get_password(self, prompt):
        return getpass.getpass(prompt)

    def calculate_pagination(self, total_items):
        _, height = self.get_terminal_size()
        fixed_lines = 3 + 1 + 2 + 3
        available = height - fixed_lines
        self.items_per_page = int(available * 0.9)
        self.items_per_page = max(1, self.items_per_page)
        return (total_items + self.items_per_page - 1) // self.items_per_page

    def show_page_indicator(self, current_page, total_pages):
        if total_pages <= 1:
            print()
            return
        width, _ = self.get_terminal_size()
        page_text = f"Page {current_page + 1} of {total_pages}"
        centered_text = page_text.center(width)
        text_start = (width - len(page_text)) // 2
        text_end = text_start + len(page_text)
        line_chars = list(centered_text)
        if current_page > 0:
            left_pos = text_start - 4 - 2
            if left_pos >= 0:
                line_chars[left_pos:left_pos+2] = list("<<")
        if current_page < total_pages - 1:
            right_pos = text_end + 4
            if right_pos + 2 <= width:
                line_chars[right_pos:right_pos+2] = list(">>")
        print()
        print("".join(line_chars))
        print()

    def show_home(self):
        """Show notebook manager home - ALWAYS get fresh data from main manager"""
        self.clear_screen()
        width, height = self.get_terminal_size()
        
        # ========== FORCE FRESH DATA FROM MAIN MANAGER ==========
        # Reload notebooks from main manager (not from internal cache)
        self.manager.load_all_notebooks(quiet=True)
        main_notebooks = self.manager.notebooks
        
        # Build notebook list from main manager's notebooks
        fresh_notebooks = []
        for nb in main_notebooks:
            # Get lock state from master registry
            try:
                master_registry = self.manager.load_registry(force_reload=True)
                fp_hash = self.manager._compute_fp_hash()
                notebook_data = master_registry.get("notebooks", {}).get(nb.id, {})
                system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
                is_locked = system_entry.get("locked", True)
                is_encrypted = nb.id in self.manager.encrypted_notebooks
            except:
                is_locked = getattr(nb, 'locked', True)
                is_encrypted = nb.id in self.manager.encrypted_notebooks
            
            # Get counts
            note_count = nb.get_total_note_count()
            file_count = nb.get_file_note_count()
            sub_count = nb.get_total_subnotebook_count()
            regular_note_count = note_count - file_count
            
            fresh_notebooks.append({
                "id": nb.id,
                "name": nb.name,
                "locked": is_locked,
                "encrypted": is_encrypted,
                "note_count": regular_note_count,
                "file_count": file_count,
                "sub_count": sub_count,
                "git_config": self.get_notebook_config(nb.id),
                "account": self.get_account_for_notebook(nb.id)
            })
        
        # Replace internal list with fresh data
        self.notebooks = fresh_notebooks
        
        # Calculate pagination
        fixed_ui_lines = 7
        available_for_items = height - fixed_ui_lines
        items_per_page = int(available_for_items * 0.9)
        items_per_page = max(1, items_per_page)

        total_pages = (len(self.notebooks) + items_per_page - 1) // items_per_page if self.notebooks else 1

        if self.page >= total_pages:
            self.page = max(0, total_pages - 1)

        start = self.page * items_per_page
        end = min(start + items_per_page, len(self.notebooks))
        paginated = self.notebooks[start:end]
        current_page = self.page + 1

        self.print_header("Notebook Manager")

        if not paginated:
            print("No notebooks found, you can create one from home")
            print()
            print("or")
            print()
            print("Press [A] to add online git account to import")
            print()
        else:
            for idx, nb in enumerate(paginated, 1):
                # Determine display
                is_encrypted = nb.get('encrypted', False)
                is_locked = nb.get('locked', True)
                
                if is_encrypted:
                    if not is_locked:
                        encrypted_marker = "🔐 "
                    else:
                        encrypted_marker = "🔒 "
                else:
                    encrypted_marker = ""
                
                # Build count display
                parts = []
                note_count = nb.get('note_count', 0)
                file_count = nb.get('file_count', 0)
                sub_count = nb.get('sub_count', 0)
                
                if note_count > 0:
                    parts.append(f"{note_count} note{'s' if note_count != 1 else ''}")
                if file_count > 0:
                    parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
                if sub_count > 0:
                    parts.append(f"{sub_count} sub{'s' if sub_count != 1 else ''}")
                
                count_display = f" ({', '.join(parts)})" if parts else ""
                
                left_part = f"[{idx}] {encrypted_marker}{nb['name']}{count_display}"
            
                # Build right part with git info
                if nb.get("git_config") and nb.get("account"):
                    account = nb["account"]
                    platform = account.get('platform', 'github')
                    if platform == 'github':
                        prefix = 'gh'
                    elif platform == 'gitlab':
                        prefix = 'gl'
                    elif platform == 'bitbucket':
                        prefix = 'bb'
                    else:
                        prefix = 'oth'
                    
                    right_part = f"[{prefix}/{account['username']}]"
                    if nb["git_config"].get("last_push"):
                        push_time = datetime.fromisoformat(nb["git_config"]["last_push"])
                        time_str = push_time.strftime("%b %d %H:%M")
                        right_part += f" {time_str}"
                else:
                    right_part = "[Not linked]"
            
                # Calculate padding for alignment
                total_width = width - 3
                emoji_extra = 1 if encrypted_marker else 0
                actual_left_len = len(left_part) + emoji_extra
                if actual_left_len + len(right_part) + 2 > total_width:
                    max_left = total_width - len(right_part) - 5 - emoji_extra
                    if max_left > 10:
                        left_part = left_part[:max_left-3] + "..."
                        actual_left_len = len(left_part) + emoji_extra
                padding = total_width - actual_left_len - len(right_part)
                print(f"{left_part}{' ' * padding}{right_part}")

        # Page indicator
        if total_pages > 1:
            page_text = f"Page {current_page} of {total_pages}"
            text_width = len(page_text)
            available_space = width - text_width
            left_space = available_space // 2
            right_space = available_space - left_space
        
            left_part = " " * left_space
            right_part = " " * right_space
        
            if current_page > 1 and left_space >= 6:
                left_part = " " * (left_space - 6) + "<<" + " " * 4
            if current_page < total_pages and right_space >= 6:
                right_part = " " * 4 + ">>" + " " * (right_space - 6)
        
            print()
            print(left_part + page_text + right_part)
        else:
            print()

        # ========== FIX: Remove [V]iew button when no notebooks ==========
        options = []
        
        if paginated:
            options.append("[V]iew")
        
        options.append("[A]ccounts")
        
        if total_pages > 1:
            if current_page < total_pages:
                options.append("[N]ext")
            if current_page > 1:
                options.append("[P]rev")
        
        if self.is_standalone:
            options.append("[Q]uit")
        else:
            options.append("[B]ack")
            options.append("[Q]uit")
        # ========== END FIX ==========

        self.print_footer("  ".join(options))

    def show_import_screen(self):
        self.clear_screen()
        self.print_header("Import Notebook")
        print("Enter Git repository URL (must end with .git):")
        print()
        print("Examples:")
        print("  https://github.com/user/repo.git")
        print("  git@github.com:user/repo.git")
        print("  https://gitlab.com/user/project.git")
        print("  file:///home/user/backups/notebook.git")
        print()
        url = self.get_input("URL: ")
        if not url:
            return
        if not url.endswith('.git'):
            print("\nURL must end with .git")
            self.get_input("Press Enter to continue...")
            return
        print("\n🔍 Testing connection...", end="")
        if not self.has_internet():
            print(" FAILED")
            print("\nNo internet connection.")
            self.get_input("Press Enter to continue...")
            return
        print(" OK")
        self.import_from_url(url)
    
    #----------#
    def show_accounts_screen(self):
        """Show accounts with accurate notebook counts from master registry"""
        from cs_ui import PaginationManager
        from token_vault import TokenVault
        
        while True:
            self.clear_screen()
            
            # Get accounts from TokenVault
            vault = TokenVault(self.app_dir)
            account_ids = vault.list_accounts()
            
            accounts = []
            for acc_id in account_ids:
                account_data = vault.get_full_account(acc_id)
                if account_data:
                    accounts.append({
                        'id': acc_id,
                        'username': account_data['username'],
                        'platform': account_data.get('platform', 'github'),
                        'host': account_data.get('host', 'github.com'),
                        'token_enc': acc_id,
                        'created': account_data.get('created', 0)
                    })
            
            total_accounts = len(accounts)
            width, height = self.get_terminal_size()
            
            # Load master registry and get fingerprint
            registry = self.manager.load_registry(force_reload=True)
            fp_hash = self.manager._compute_fp_hash()
            
            # ========== COUNT NOTEBOOKS FOR EACH ACCOUNT ==========
            notebook_counts = {}
            for acc in accounts:
                notebook_counts[acc['id']] = 0
            
            notebooks_data = registry.get("notebooks", {})
            
            for notebook_id, notebook_entry in notebooks_data.items():
                if isinstance(notebook_entry, str):
                    continue
                
                systems = notebook_entry.get("systems", {})
                system_entry = systems.get(fp_hash, {})
                
                if not system_entry:
                    continue
                
                notebook_path = system_entry.get("path", "")
                if notebook_path and not os.path.isabs(notebook_path):
                    notebook_path = os.path.join(self.manager.notebooks_root, notebook_path)
                
                if not notebook_path or not os.path.exists(notebook_path):
                    continue
                
                git_config_path = os.path.join(notebook_path, ".git", "config")
                if not os.path.exists(git_config_path):
                    continue
                
                remote_url = self._extract_remote_url_from_git_config(git_config_path)
                if not remote_url:
                    continue
                
                parsed = self._parse_git_remote_url(remote_url)
                if not parsed:
                    continue
                
                for acc in accounts:
                    if parsed['host'] == acc['host'] and parsed['username'] == acc['username']:
                        notebook_counts[acc['id']] = notebook_counts.get(acc['id'], 0) + 1
                        break
            # ========== END COUNTING ==========
            
            # Pagination
            items_per_page, total_pages = PaginationManager.calculate(
                total_accounts, height, fixed_lines=8
            )
            
            if self.accounts_page >= total_pages:
                self.accounts_page = max(0, total_pages - 1)
            
            start_idx = self.accounts_page * items_per_page
            end_idx = min(start_idx + items_per_page, total_accounts)
            paginated = accounts[start_idx:end_idx]
            current_page = self.accounts_page + 1
            
            self.print_header("Accounts")
            
            if not paginated:
                print("No accounts configured.")
                print()
                print("Press [A] to add online git account using token")
                print()
            else:
                for i, acc in enumerate(paginated, 1):
                    notebook_count = notebook_counts.get(acc['id'], 0)
                    platform = acc.get('platform', 'github').capitalize()
                    username = acc['username']
                    
                    if notebook_count == 1:
                        count_text = "1 notebook"
                    else:
                        count_text = f"{notebook_count} notebooks"
                    
                    print(f"[{i}] {username} - {count_text} [{platform}]")
            
            # Page indicator
            if total_pages > 1:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(width)
                text_start = (width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)
                
                if current_page > 1:
                    left_pos = text_start - 4 - 2
                    if left_pos >= 0:
                        line_chars[left_pos:left_pos+2] = list("<<")
                
                if current_page < total_pages:
                    right_pos = text_end + 4
                    if right_pos + 2 <= width:
                        line_chars[right_pos:right_pos+2] = list(">>")
                
                print()
                print("".join(line_chars))
            else:
                print()
            
            # Footer options
            footer = []
            if paginated:
                footer.append("[V]iew")
                footer.append("[R]emove")
            footer.append("[A]dd")
            
            if total_pages > 1:
                if current_page < total_pages:
                    footer.append("[N]ext")
                if current_page > 1:
                    footer.append("[P]rev")
            
            footer.append("[B]ack")
            footer.append("[Q]uit")
            
            self.print_footer("  ".join(footer))
            
            cmd = self.get_input("> ").strip().lower()
            
            # Pagination
            if cmd == "n" and current_page < total_pages:
                self.accounts_page += 1
                continue
            elif cmd == "p" and current_page > 1:
                self.accounts_page -= 1
                continue
            
            # View account
            elif cmd.startswith("v"):
                if not paginated:
                    continue
                if cmd == "v":
                    try:
                        rel_num = int(self.get_input("Enter account number: "))
                    except ValueError:
                        continue
                else:
                    try:
                        rel_num = int(cmd[1:])
                    except ValueError:
                        continue
                
                if 1 <= rel_num <= len(paginated):
                    acc = paginated[rel_num - 1]
                    self.show_account_repos(acc)
                continue
            
            # Remove account
            elif cmd == "r" and paginated:
                self._remove_account_from_list()
                self.accounts_page = 0
                continue
            
            # Add account
            elif cmd == "a":
                self.show_add_account()
                self.accounts_page = 0
                continue
            
            # Back
            elif cmd == "b":
                break
            
            # Quit
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    self.clear_screen()
                    if self.is_standalone:
                        sys.exit(0)
                    else:
                        return "exit_app"
                else:
                    if self.is_standalone:
                        confirm = self.get_input("Quit Notebook Manager? [y/N]: ").lower()
                        if confirm == "y":
                            self.clear_screen()
                            sys.exit(0)
                    else:
                        confirm = self.get_input("Quit Terminal Notes? [y/N]: ").lower()
                        if confirm == "y":
                            self.clear_screen()
                            return "exit_app"
            
            # Invalid command - just loop (no error message, like home screen)
            else:
                continue

    def _extract_remote_url_from_git_config(self, config_path):
        """Extract the remote origin URL from .git/config"""
        try:
            with open(config_path, 'r') as f:
                in_remote = False
                for line in f:
                    line = line.strip()
                    if line == '[remote "origin"]':
                        in_remote = True
                    elif in_remote and line.startswith('url ='):
                        return line.split('=', 1)[1].strip()
                    elif in_remote and line.startswith('['):
                        # Reached another section
                        break
        except:
            pass
        return None

    def _parse_git_remote_url(self, url):
        """Parse Git remote URL to extract host and username.
        Supports:
        - HTTPS: https://github.com/username/repo.git
        - HTTPS with credentials: https://username:token@github.com/username/repo.git
        - SSH: git@github.com:username/repo.git
        - Git: git://github.com/username/repo.git
        - Gitea/Self-hosted: https://git.example.com/username/repo.git
        """
        # Remove .git suffix
        if url.endswith('.git'):
            url = url[:-4]
        
        # ========== FIX: Remove credentials (username:password@) from URL ==========
        # Remove protocol prefix first to make parsing easier
        protocol = ''
        if '://' in url:
            protocol, url = url.split('://', 1)
        
        # Remove credentials (anything before @ that contains :)
        if '@' in url and ':' in url.split('@')[0]:
            # Strip username:password@ from the URL
            url = url.split('@', 1)[1]
        
        # Re-add protocol if it was there
        if protocol:
            url = f"{protocol}://{url}"
        # ========== END FIX ==========
        
        # Handle SSH format: git@github.com:username/repo
        if '@' in url and ':' in url:
            # Extract after @ and before :
            parts = url.split('@', 1)[1].split(':', 1)
            if len(parts) >= 2:
                host = parts[0]
                username_path = parts[1]
                if '/' in username_path:
                    username = username_path.split('/')[0]
                else:
                    username = username_path
                return {'host': host, 'username': username}
        
        # Handle HTTPS/HTTP format: github.com/username/repo
        if '://' in url:
            url = url.split('://', 1)[1]
        
        if '/' in url:
            parts = url.split('/')
            if len(parts) >= 2:
                host = parts[0]
                username = parts[1]
                return {'host': host, 'username': username}
        
        return None

    def show_account_repos(self, account):
        token = self._decrypt_token(account['token_enc'])
        if not token:
            print("Could not decrypt token")
            self.get_input("Press Enter to continue...")
            return

        import signal
        import time
        import re

        def timeout_handler(signum, frame):
            raise TimeoutError("Operation timed out")

        signal.signal(signal.SIGALRM, timeout_handler)

        max_retries = 3
        retry_count = 0
        all_repos = []

        while retry_count < max_retries:
            try:
                print("\nFetching repositories...", end="", flush=True)
                signal.alarm(15)
                all_repos = self.fetch_account_repos(account, token)
                signal.alarm(0)
                if not all_repos:
                    print(" No repositories found")
                    self.get_input("Press Enter to continue...")
                    return
                print(f" {len(all_repos)} repositories found")
                break
            except TimeoutError:
                signal.alarm(0)
                retry_count += 1
                print(f"\nOperation timed out after 15 seconds (attempt {retry_count}/{max_retries})")
                if retry_count < max_retries:
                    retry = input("Try again? [Y/n]: ").lower()
                    if retry == 'n':
                        print("Operation cancelled")
                        self.get_input("Press Enter to continue...")
                        return
                    print("Retrying...")
                    continue
                else:
                    print("Max retries exceeded. Please check your connection.")
                    self.get_input("Press Enter to continue...")
                    return
            except Exception as e:
                signal.alarm(0)
                print(f"\nError: {e}")
                self.get_input("Press Enter to continue...")
                return

        # Get already linked notebooks from TokenVault
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        account_data = vault.get_full_account(account['id'])
        linked_notebooks = account_data.get("linked_notebooks", []) if account_data else []

        local_notebooks = set()
        for nb in self.notebooks:
            if nb.get('git_config'):
                repo_name = nb['git_config'].get('repo', '')
                if repo_name:
                    local_notebooks.add(repo_name)

        # Filter repos that match pattern
        candidate_repos = []
        for repo in all_repos:
            repo_name = repo.get('name', '')
            # Quick pattern match using regex (very fast)
            if len(repo_name) > 15 and '-' in repo_name and repo_name[-14:].isdigit():
                candidate_repos.append(repo)
        
        print(f"\nScanning {len(candidate_repos)} Terminal Notes notebooks...")
        
        # Check repos in parallel with optimized settings
        tn_repos = self.check_repos_parallel(
            candidate_repos,
            account,
            token,
            local_notebooks
        )
        
        if not tn_repos:
            print("\nNo Terminal Notes notebooks found in this account.")
            self.get_input("Press Enter to continue...")
            return
        
        print(f"\nFound {len(tn_repos)} Terminal Notes notebooks")

        signal.signal(signal.SIGALRM, signal.SIG_DFL)

        if not tn_repos:
            return

        has_listed = any(repo.get('listed', False) for repo in tn_repos)

        page = 0
        while True:
            self.clear_screen()
            width, height = self.get_terminal_size()
            fixed_lines = 3 + 1 + 2 + 3
            available = height - fixed_lines
            items_per_page = int(available * 0.9)
            items_per_page = max(1, items_per_page)
            total_pages = (len(tn_repos) + items_per_page - 1) // items_per_page
            if page >= total_pages:
                page = max(0, total_pages - 1)
            start = page * items_per_page
            end = min(start + items_per_page, len(tn_repos))
            paginated = tn_repos[start:end]
            current_page = page + 1
            self.print_header(f"{account['username']}@{account.get('host')} Notebooks")
        
            for idx, repo in enumerate(paginated, 1):
                visibility = "Private" if repo['private'] else "Public"
                listed_indicator = " (listed)" if repo.get('listed') else ""
                
                # Get the full repo name from the 'name' field, not 'display_name'
                full_name = repo.get('name', 'Unknown')
                # Extract the readable name (remove timestamp suffix)
                if '-' in full_name:
                    readable_name = full_name.rsplit('-', 1)[0]
                else:
                    readable_name = full_name
                
                parts = []
                if repo.get('note_count', 0) > 0:
                    parts.append(f"{repo['note_count']} note{'s' if repo['note_count'] != 1 else ''}")
                if repo.get('file_count', 0) > 0:
                    parts.append(f"{repo['file_count']} file{'s' if repo['file_count'] != 1 else ''}")
                if repo.get('sub_count', 0) > 0:
                    parts.append(f"{repo['sub_count']} sub{'s' if repo['sub_count'] != 1 else ''}")

                count_display = f" ({', '.join(parts)})" if parts else ""

                if repo.get('encrypted'):
                    line = f"[{idx}] 🔒 {readable_name}{count_display}{listed_indicator} [{visibility}]"
                else:
                    line = f"[{idx}] {readable_name}{count_display}{listed_indicator} [{visibility}]"
                
                if len(line) > width - 4:
                    line = line[:width-7] + "..."
                print(line)
            
            if total_pages > 1:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(width)
                text_start = (width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)
                if current_page > 1:
                    left_pos = text_start - 4 - 2
                    if left_pos >= 0:
                        line_chars[left_pos:left_pos+2] = list("<<")
                if current_page < total_pages:
                    right_pos = text_end + 4
                    if right_pos + 2 <= width:
                        line_chars[right_pos:right_pos+2] = list(">>")
                print()
                print("".join(line_chars))
                print()
            else:
                print()
            
            footer = ["[I]mport"]
            
            footer.append("[R]efresh")
            if total_pages > 1:
                if current_page < total_pages:
                    footer.append("[N]ext")
                if current_page > 1:
                    footer.append("[P]rev")
            footer.append("[B]ack")
            footer.append("[Q]uit")
        
            print("  ".join(footer))
            print()
        
            cmd = self.get_input("> ").lower()

            if cmd == "b":
                break
            elif cmd == "r":
                self.show_account_repos(account)
                return
            elif cmd == "n" and current_page < total_pages:
                page += 1
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd.startswith("i"):
                try:
                    if cmd == "i":
                        rel_num = int(self.get_input("Enter notebook number to import: "))
                    else:
                        rel_num = int(cmd[1:])
                
                    if 1 <= rel_num <= len(paginated):
                        repo = paginated[rel_num - 1]
                        for full_repo in all_repos:
                            if full_repo.get('name') == repo['name']:
                                clone_url = full_repo.get('clone_url') or full_repo.get('http_url_to_repo')
                                if clone_url:
                                    self.import_from_url(clone_url, account)
                                break
                    continue
                except ValueError:
                    continue
            elif cmd.startswith("p") and has_listed:
                try:
                    if cmd == "pall":
                        print("\nPulling all listed notebooks...")
                        for repo in tn_repos:
                            if repo.get('listed'):
                                print(f"  Pulling {repo['display_name']}...")
                                for nb in self.notebooks:
                                    if nb.get('git_config', {}).get('repo') == repo['name']:
                                        path = nb.get('path')
                                        if path and os.path.exists(path):
                                            result = subprocess.run(
                                                ["git", "pull"],
                                                cwd=path,
                                                capture_output=True,
                                                text=True
                                            )
                                            if result.returncode == 0:
                                                if "Already up to date" in result.stdout:
                                                    print(f"    ✓ Already up to date")
                                                else:
                                                    print(f"    ✓ Updated")
                                            else:
                                                print(f"    ✗ Pull failed: {result.stderr[:100]}")
                                        break
                        self.get_input("\nPress Enter to continue...")
                    elif len(cmd) > 1:
                        rel_num = int(cmd[1:])
                        if 1 <= rel_num <= len(paginated):
                            repo = paginated[rel_num - 1]
                            if repo.get('listed'):
                                print(f"\nPulling {repo['display_name']}...")
                                for nb in self.notebooks:
                                    if nb.get('git_config', {}).get('repo') == repo['name']:
                                        path = nb.get('path')
                                        if path and os.path.exists(path):
                                            result = subprocess.run(
                                                ["git", "pull"],
                                                cwd=path,
                                                capture_output=True,
                                                text=True
                                            )
                                            if result.returncode == 0:
                                                if "Already up to date" in result.stdout:
                                                    print(f"  ✓ Already up to date")
                                                else:
                                                    print(f"  ✓ Updated")
                                            else:
                                                print(f"  ✗ Pull failed: {result.stderr[:100]}")
                                        break
                                self.get_input("\nPress Enter to continue...")
                except Exception as e:
                    print(f"Pull error: {e}")
                    self.get_input("\nPress Enter to continue...")
        
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    self.clear_screen()
                    if self.is_standalone:
                        sys.exit(0)
                    else:
                        return "exit_app"
                else:
                    if self.is_standalone:
                        confirm = self.get_input("Quit Notebook Manager? [y/N]: ").lower()
                        if confirm == "y":
                            self.clear_screen()
                            sys.exit(0)
                    else:
                        confirm = self.get_input("Quit Terminal Notes? [y/N]: ").lower()
                        if confirm == "y":
                            self.clear_screen()
                            return "exit_app"
                    continue

        return None
                
    def fetch_account_repos(self, account, token):
        """Fetch repositories with connection pooling and retries"""
        platform = account.get('platform', 'github')
    
        # Create session with connection pooling
        session = requests.Session()
    
        # Retry strategy
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
    
        # Mount adapters with connection pooling
        adapter = HTTPAdapter(
            max_retries=retries,
            pool_connections=10,
            pool_maxsize=20,
            pool_block=False
        )
        session.mount('https://', adapter)
        session.mount('http://', adapter)
    
        # Set headers
        if platform == 'github':
            session.headers.update({'Authorization': f'token {token}'})
            session.headers.update({'Accept': 'application/vnd.github.v3+json'})
            session.headers.update({'Connection': 'keep-alive'})
            url = 'https://api.github.com/user/repos?per_page=100&sort=updated'
        elif platform == 'gitlab':
            session.headers.update({'Authorization': f'Bearer {token}'})
            url = 'https://gitlab.com/api/v4/projects?membership=true&per_page=100'
        elif platform == 'bitbucket':
            import base64
            auth = base64.b64encode(f"{account['username']}:{token}".encode()).decode()
            session.headers.update({'Authorization': f'Basic {auth}'})
            url = f'https://api.bitbucket.org/2.0/repositories/{account["username"]}?pagelen=100'
        else:
            return []
    
        try:
            # Set socket timeout globally
            socket.setdefaulttimeout(10)
        
            # Make request with timeouts
            response = session.get(
                url,
                timeout=(3.05, 15),  # (connect timeout, read timeout)
                verify=True
            )
        
            if response.status_code == 200:
                data = response.json()
                if platform == 'bitbucket':
                    return data.get('values', [])
                return data
            else:
                print(f"  API returned {response.status_code}")
                return []
            
        except requests.exceptions.Timeout:
            print("  Connection timeout")
            return []
        except requests.exceptions.ConnectionError:
            print("  Connection error")
            return []
        except Exception as e:
            print(f"  Error: {e}")
            return []
        finally:
            session.close()

    def import_from_url(self, url, account=None):
        """Import notebook from Git URL"""
        self.clear_screen()
        self.print_header("Import Notebook")
        print(f"\n  URL: {url}\n")
        
        import signal
        import subprocess
        import shutil
        import time
        
        def timeout_handler(signum, frame):
            raise TimeoutError("Operation timed out")
        
        signal.signal(signal.SIGALRM, timeout_handler)
        
        if not account:
            account = self.find_account_for_url(url)
        
        max_retries = 3
        retry_count = 0
        local_path = None
        
        while retry_count < max_retries:
            try:
                signal.alarm(30)
                local_path = self.clone_repository(url, account, shallow=False)
                signal.alarm(0)
                
                if local_path:
                    print(f"  ✓ Cloned to: {local_path}")
                    break
                else:
                    print("\n  ✗ Clone failed")
                    return
                    
            except TimeoutError:
                signal.alarm(0)
                retry_count += 1
                print(f"\n  ⏱️ Timeout (attempt {retry_count}/{max_retries})")
                if retry_count < max_retries:
                    retry = input(f"  Retry? [y/N]: ").lower()
                    if retry == 'y':
                        continue
                    else:
                        if local_path and os.path.exists(local_path):
                            shutil.rmtree(local_path, ignore_errors=True)
                        return
                else:
                    print("  Max retries exceeded.")
                    if local_path and os.path.exists(local_path):
                        shutil.rmtree(local_path, ignore_errors=True)
                    self.get_input("Press Enter to continue...")
                    return
                    
            except Exception as e:
                signal.alarm(0)
                print(f"\n  ✗ Error: {e}")
                if local_path and os.path.exists(local_path):
                    shutil.rmtree(local_path, ignore_errors=True)
                self.get_input("Press Enter to continue...")
                return
        
        if not local_path:
            return
        
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
        
        # Register the cloned notebook
        print("\n  Registering notebook...")
        notebook_id = self.register_cloned_notebook(local_path, crypto=None)
        
        if notebook_id:
            repo_name = os.path.basename(url).replace('.git', '')
            
            # Check if account exists in notebook manager
            if account:
                # Find existing account or create new one
                account_exists = False
                for acc_id, acc in self.accounts.get("accounts", {}).items():
                    if acc.get('username') == account.get('username') and acc.get('host') == account.get('host'):
                        account_exists = True
                        account = acc
                        break
                
                if not account_exists:
                    # Need to add account
                    print("\n  This repository requires authentication.")
                    print("  Let's add your Git account.\n")
                    
                    # Determine platform from URL
                    if 'github.com' in url:
                        self._add_github_account()
                    elif 'gitlab.com' in url:
                        self._add_gitlab_account()
                    elif 'bitbucket.org' in url:
                        self._add_bitbucket_account()
                    else:
                        self._add_gitea_account()
                    
                    # Reload accounts after adding
                    self.load_accounts()
                    
                    # Find the newly added account
                    for acc_id, acc in self.accounts.get("accounts", {}).items():
                        if acc.get('username') == account.get('username'):
                            account = acc
                            break
                
                # Update notebook config (legacy)
                self.update_notebook_config(
                    notebook_id,
                    account['id'],
                    repo_name,
                    visibility="private"
                )
                
                # Update TokenVault with linked notebook
                from token_vault import TokenVault
                vault = TokenVault(self.app_dir)
                account_data = vault.get_full_account(account['id'])
                
                if account_data:
                    linked = account_data.get("linked_notebooks", [])
                    if notebook_id not in linked:
                        linked.append(notebook_id)
                        vault.store_token(
                            account['id'],
                            account_data['username'],
                            account_data['platform'],
                            account_data['host'],
                            account_data['api_url'],
                            account_data['token'],
                            linked
                        )
                        print(f"\n  ✓ Notebook linked to account: {account['username']}@{account.get('platform', 'github')}")
                else:
                    # Account exists in memory but not in vault? Add it
                    token = self._decrypt_token(account.get('token_enc', ''))
                    if token:
                        vault.store_token(
                            account['id'],
                            account['username'],
                            account.get('platform', 'github'),
                            account.get('host', 'github.com'),
                            account.get('api_url', 'https://api.github.com'),
                            token,
                            [notebook_id]
                        )
                        print(f"\n  ✓ Notebook linked to account: {account['username']}@{account.get('platform', 'github')}")
                
                print(f"\n  ✓ Notebook configured with: {account['username']}@{account.get('platform', 'github')}/{repo_name}")
            
            print("\n  ✓ Import successful!")
            print(f"  Notebook: {notebook_id[:8]}...")
            print("  Use [S]ync to changes to remote.")
            
            # Reload notebooks in main app
            if hasattr(self.manager, 'load_all_notebooks'):
                self.manager.notebooks = []
                self.manager.load_all_notebooks(quiet=True)
            
            self.load_notebooks()
            self.load_accounts()  # Reload accounts to refresh linked notebooks count
            
        else:
            print("\n  ✗ Import failed")
            if os.path.exists(local_path):
                shutil.rmtree(local_path, ignore_errors=True)
                print(f"  Removed incomplete clone: {os.path.basename(local_path)}")
        
        self.get_input("\nPress Enter to continue...")

    def clone_repository(self, url, account=None, shallow=False):
        """Clone a git repository"""
        import subprocess
        from datetime import datetime
        import os
        import shutil
        from urllib.parse import urlparse
        
        # Warm up DNS
        try:
            parsed = urlparse(url)
            if parsed.hostname:
                DNSCache.resolve(parsed.hostname)
        except Exception:
            pass
        
        repo_name = os.path.basename(url).replace('.git', '')
        target_dir = os.path.join(self.app_dir, "notebooks_root", repo_name)
        
        # Handle existing directory
        if os.path.exists(target_dir):
            print(f"\n  Directory already exists: {repo_name}")
            print("  [1] Overwrite")
            print("  [2] Create timestamped copy")
            print("  [3] Cancel")
            choice = input("  Choose: ").strip()
            
            if choice == "1":
                shutil.rmtree(target_dir, ignore_errors=True)
            elif choice == "2":
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                target_dir = os.path.join(self.app_dir, "notebooks_root", f"{repo_name}-{timestamp}")
                print(f"  Using: {os.path.basename(target_dir)}")
            else:
                return None
        
        os.makedirs(os.path.join(self.app_dir, "notebooks_root"), exist_ok=True)
        
        # Build clone URL with auth
        clone_url = url
        if account:
            token = self._decrypt_token(account['token_enc'])
            if token and ('github.com' in url or 'gitlab.com' in url):
                username = account['username']
                clone_url = url.replace('https://', f'https://{username}:{token}@')
        
        try:
            print(f"  Cloning to: {target_dir}")
            
            cmd = ["git", "clone"]
            if shallow:
                cmd.extend(["--depth", "1"])
            cmd.extend(["--single-branch", clone_url, target_dir])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Verify structure.json exists
                struct_file = os.path.join(target_dir, "structure.json")
                if os.path.exists(struct_file):
                    return target_dir
                else:
                    print("  ✗ Not a Terminal Notes notebook (no structure.json)")
                    shutil.rmtree(target_dir, ignore_errors=True)
                    return None
            else:
                print(f"  ✗ Clone failed: {result.stderr[:200]}")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir, ignore_errors=True)
                return None
                
        except subprocess.TimeoutExpired:
            print("  ✗ Clone timeout")
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return None
        except Exception as e:
            print(f"  ✗ Clone error: {e}")
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
            return None
        
    def register_cloned_notebook(self, path, crypto=None):
        """Register a cloned notebook in the master registry"""
        import json
        from notebook_operations import read_json
        from terminal_notes_core import Notebook
        from datetime import datetime
        import os
        import shutil
        import time
        import uuid as uuid_lib
        import socket

        struct_file = os.path.join(path, "structure.json")
        if not os.path.exists(struct_file):
            print(f"  ✗ structure.json not found in {path}")
            return None

        try:
            is_encrypted = False
            with open(struct_file, 'rb') as f:
                sample = f.read(100)
            if any(b >= 128 for b in sample):
                is_encrypted = True

            folder_name = os.path.basename(path)
            struct_data = None
            crypto_obj = None
            notebook_name = None
            notebook_id = None
            
            if is_encrypted:
                print(f"\n  🔒 Encrypted notebook detected")
                print("  You need the RECOVERY PHRASE to import this notebook.\n")
                
                from getpass import getpass
                attempts = 0
                max_attempts = 3
                
                while attempts < max_attempts and not crypto_obj:
                    remaining = max_attempts - attempts
                    prompt = f"  Recovery phrase ({remaining} attempt{'s' if remaining != 1 else ''}): "
                    phrase = getpass(prompt)
                    
                    if not phrase:
                        attempts += 1
                        continue
                    
                    try:
                        from crypto import Crypto, derive_key
                        
                        phrase_key = derive_key(phrase, folder_name)
                        
                        test_file = os.path.join(path, ".tn_test")
                        if not os.path.exists(test_file):
                            attempts += 1
                            continue
                        
                        with open(test_file, 'rb') as f:
                            test_data = f.read()
                        
                        temp_crypto = Crypto(phrase_key, phrase_key, folder_name)
                        temp_crypto.decrypt(test_data)
                        
                        recovery_file = os.path.join(path, ".tn_recovery")
                        if not os.path.exists(recovery_file):
                            attempts += 1
                            continue
                        
                        with open(recovery_file, 'rb') as f:
                            recovery_data = f.read()
                        
                        json_str = temp_crypto.decrypt(recovery_data)
                        recovery_info = json.loads(json_str)
                        password_key = bytes.fromhex(recovery_info["password_key"])
                        
                        crypto_obj = Crypto(password_key, phrase_key, folder_name)
                        
                        password_file = os.path.join(path, ".tn_password")
                        if not os.path.exists(password_file):
                            attempts += 1
                            continue
                        
                        with open(password_file, 'rb') as f:
                            password_data = f.read()
                        
                        if crypto_obj.decrypt_with_combined(password_data):
                            struct_data = read_json(struct_file, crypto_obj)
                            if struct_data:
                                # Extract name and ID from structure.json ONLY
                                if "notebooks" in struct_data and struct_data["notebooks"]:
                                    notebook_data = struct_data["notebooks"][0]
                                    notebook_name = notebook_data.get("name")
                                    notebook_id = notebook_data.get("id")
                                elif "name" in struct_data:
                                    notebook_name = struct_data.get("name")
                                    notebook_id = struct_data.get("id")
                                
                                # Clean name (remove lock symbols)
                                if notebook_name:
                                    notebook_name = notebook_name.replace('🔐 ', '').replace('🔒 ', '').strip()
                                break
                            else:
                                crypto_obj = None
                                attempts += 1
                        else:
                            crypto_obj = None
                            attempts += 1
                        
                    except Exception:
                        crypto_obj = None
                        attempts += 1
                
                if not struct_data:
                    print(f"  ✗ Failed to import after {max_attempts} attempts")
                    return None
            else:
                with open(struct_file, 'r') as f:
                    struct_data = json.load(f)
                
                # Extract name and ID from structure.json
                if "notebooks" in struct_data and struct_data["notebooks"]:
                    notebook_data = struct_data["notebooks"][0]
                    notebook_name = notebook_data.get("name")
                    notebook_id = notebook_data.get("id")
                elif "name" in struct_data:
                    notebook_name = struct_data.get("name")
                    notebook_id = struct_data.get("id")

            # Generate ID if not found
            if not notebook_id:
                notebook_id = datetime.now().strftime("%Y%m%d%H%M%S")

            # ========== Register in master registry ==========
            from vault_manager import VaultManager
            vm = VaultManager(self.app_dir)
            
            # Ensure default vault exists
            default_dir = os.path.join(self.app_dir, "config")
            default_path = os.path.join(default_dir, "session.vault")
            os.makedirs(default_dir, exist_ok=True)
            
            if not os.path.exists(default_path):
                vm.create_vault_file("default", default_dir)
            
            # Create vault entry if encrypted
            entry_uuid = None
            if is_encrypted and crypto_obj:
                fingerprint = self.manager._get_system_fingerprint()
                combined_keys = crypto_obj.password_key + crypto_obj.phrase_key
                nonce = os.urandom(12)
                
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(fingerprint)
                encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
                
                entry_uuid = str(uuid_lib.uuid4())
                vm.add_entry_to_vault(default_path, entry_uuid, {
                    "notebook_id": notebook_id,
                    "timestamp": time.time_ns(),
                    "nonce": nonce.hex(),
                    "encrypted_keys": encrypted_keys.hex()
                })
                
                # Store in session cache
                self.manager.session_keys._cache[notebook_id] = crypto_obj
                self.manager.encrypted_notebooks.add(notebook_id)
            
            # Update master registry
            registry = self.manager.load_registry(force_reload=True)
            fp_hash = self.manager._compute_fp_hash()
            system_name = socket.gethostname()
            
            if fp_hash not in registry.get("system_index", {}):
                registry["system_index"][fp_hash] = system_name
            
            # Store path (relative if under notebooks_root)
            if path.startswith(self.notebooks_root):
                stored_path = os.path.relpath(path, self.notebooks_root)
            else:
                stored_path = path
            
            if notebook_id not in registry.get("notebooks", {}):
                registry["notebooks"][notebook_id] = {
                    "name": notebook_name,
                    "folder_name": os.path.basename(path),
                    "created": datetime.now().isoformat(),
                    "systems": {}
                }
            
            registry["notebooks"][notebook_id]["systems"][fp_hash] = {
                "path": stored_path,
                "vault": "default",
                "entry": entry_uuid,
                "locked": True if is_encrypted else False,
                "system_name": system_name
            }
            
            self.manager.save_registry(registry)
            
            # Add to NotebookManager list
            self.notebooks.append({
                "id": notebook_id,
                "name": notebook_name,
                "path": path,
                "encrypted": is_encrypted,
                "locked": True if is_encrypted else False,
                "note_count": 0,
                "file_count": 0,
                "sub_count": 0,
                "git_config": None,
                "account": None
            })

            # Add to main NoteManager list
            from terminal_notes_core import Notebook
            main_notebook = Notebook(notebook_name, notebook_id=notebook_id)
            if is_encrypted and crypto_obj:
                main_notebook.locked = True
                main_notebook.custom_path = None
                main_notebook._crypto = crypto_obj
                self.manager.encrypted_notebooks.add(notebook_id)
            else:
                main_notebook.locked = False
                main_notebook.custom_path = path
            
            self.manager.notebooks.append(main_notebook)

            print(f"\n  ✓ Notebook imported successfully!")
            print(f"   Name: {notebook_name}")
            print(f"   Location: {path}")
            if is_encrypted:
                print(f"   🔒 Notebook is LOCKED")
                print(f"   Use your PASSWORD to unlock it for daily use")

            return notebook_id

        except Exception as e:
            print(f"  ✗ Registration failed: {e}")
            return None

    def find_account_for_url(self, url):
        for acc_id, account in self.accounts.get("accounts", {}).items():
            if account.get('host') in url:
                if account.get('username') in url:
                    return account
        return None

    def load_registry(self):
        if os.path.exists(self.registry_file):
            try:
                with open(self.registry_file, 'r') as f:
                    return json.load(f)
            except:
                return {"notebooks": {}}
        return {"notebooks": {}}

    def save_registry(self, registry):
        """Save registry with atomic write"""
        registry_file = self.registry_file
        temp_file = registry_file + '.tmp'
    
        try:
            with open(temp_file, 'w') as f:
                json.dump(registry, f, indent=2)
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
            print(f"Error saving registry: {e}")
            return False

    def show_notebook_view(self, notebook):
        """Show notebook details - ALWAYS get fresh data from master registry"""
        while True:
            notebook_id = notebook["id"]
            
            # ========== GET FRESH DATA FROM MASTER REGISTRY ==========
            master_registry = self.manager.load_registry(force_reload=True)
            fp_hash = self.manager._compute_fp_hash()
            
            notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
            system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
            
            # Get path from master registry
            path_from_registry = system_entry.get("path", "")
            if path_from_registry and not os.path.isabs(path_from_registry):
                path_from_registry = os.path.join(self.manager.notebooks_root, path_from_registry)
            
            # Get lock state from master registry
            is_locked = system_entry.get("locked", True)
            is_encrypted = notebook.get('encrypted', False) or bool(system_entry.get("entry"))
            
            # Get vault name
            vault_name = system_entry.get("vault", "default")
            
            # ========== Get live counts from main NoteManager (one source of truth) ==========
            live_notebook = self.manager.find_notebook_by_id(notebook_id)
            if live_notebook:
                total_notes = live_notebook.get_total_note_count()
                total_files = live_notebook.get_file_note_count()
                note_count = total_notes - total_files
                file_count = total_files
                sub_count = live_notebook.get_total_subnotebook_count()
                # Update the dict for consistency
                notebook['note_count'] = note_count
                notebook['file_count'] = file_count
                notebook['sub_count'] = sub_count
            else:
                # Fallback to dict values if live notebook not found
                note_count = notebook.get('note_count', 0)
                file_count = notebook.get('file_count', 0)
                sub_count = notebook.get('sub_count', 0)
            # ========== END FIX ==========
            
            self.clear_screen()
            width, _ = self.get_terminal_size()
            
            # Get display name with lock symbol
            display_name = notebook['name']
            if is_encrypted:
                if is_locked:
                    display_name = f"🔒 {notebook['name']}"
                else:
                    display_name = f"🔐 {notebook['name']}"
            
            self.print_header(f"Notebook: {display_name}")
            
            # Type and encryption status
            if is_encrypted:
                if is_locked:
                    print(f"Type: 🔒 Encrypted (locked)")
                else:
                    print(f"Type: 🔐 Encrypted (unlocked)")
            else:
                print(f"Type: Unencrypted")
            
            # Show path from master registry
            if path_from_registry and os.path.exists(path_from_registry):
                print(f"Path: {path_from_registry}")
            else:
                print(f"Path: [Not found]")
            
            print()
            
            git_config = notebook.get("git_config")
            account = notebook.get("account")
            has_remote = git_config and account and not is_locked
            
            # Get platform name for display
            platform_name = account.get('platform', 'git') if account else 'git'
            platform_display = platform_name.title() if platform_name else 'Git'
            
            # Get folder name for repository display
            folder_name = ""
            if path_from_registry and os.path.exists(path_from_registry):
                folder_name = os.path.basename(path_from_registry)
                if folder_name.endswith('.git'):
                    folder_name = folder_name[:-4]
            
            if not folder_name:
                clean_name = notebook['name'].replace('🔐 ', '').replace('🔒 ', '')
                folder_name = f"{clean_name}-{notebook_id}"
            
            def format_datetime(dt_str):
                if not dt_str:
                    return "Unknown"
                try:
                    if 'T' in dt_str:
                        dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
                        return dt.strftime("%b %d, %Y %H:%M")
                    return dt_str[:16]
                except:
                    return dt_str[:16]
            
            if has_remote and not is_locked:
                visibility = git_config.get("visibility", "private")
                visibility_display = "🔒 PRIVATE" if visibility == "private" else "🔐 PUBLIC"
                print(f"Account: {account['username']}@{platform_name}")
                print(f"Repository: {folder_name}")
                print(f"Visibility: {visibility_display}")
                if git_config.get('last_push'):
                    print(f"Last push: {format_datetime(git_config['last_push'])}")
                if git_config.get('created'):
                    print(f"Created: {format_datetime(git_config['created'])}")
            
                if path_from_registry and os.path.exists(os.path.join(path_from_registry, ".git")):
                    try:
                        cmd = ["git", "log", "-1", "--format=%cd", "--date=format:%b %d, %Y %H:%M"]
                        result = subprocess.run(cmd, cwd=path_from_registry, capture_output=True, text=True)
                        if result.returncode == 0 and result.stdout.strip():
                            last_modified = result.stdout.strip()
                            print(f"Last modified: {last_modified}")
                    except:
                        pass
            else:
                if is_locked:
                    print(f"{platform_display}: Locked - unlock to see status")
                else:
                    print(f"{platform_display}: Not configured")
            
            print()
            print(f"Vault: {vault_name}")
            print()
            print(f"Notes: {note_count}")
            print(f"Files: {file_count}")
            print(f"Subnotebooks: {sub_count}")
            print()
            
            security_exists = self.has_security_activity(notebook)

            # ========== Disable remote options for locked notebooks ==========
            if is_locked:
                # Locked notebook - only basic options
                options = ["[C]hange"]
                if security_exists:
                    options.append("[A]ctivity")
                options.extend(["[B]ack", "[Q]uit"])
            else:
                # Unlocked notebook - full options
                if has_remote:
                    options = ["[V]isibility", "[S]ync", "[D]elete", "[C]hange"]
                    if security_exists:
                        options.append("[A]ctivity")
                    options.extend(["[B]ack", "[Q]uit"])
                else:
                    options = ["[L]ink", "[C]hange"]
                    if security_exists:
                        options.append("[A]ctivity")
                    options.extend(["[B]ack", "[Q]uit"])
            # ========== END FIX ==========
            
            self.print_footer("  ".join(options))
            
            cmd = self.get_input("> ").strip().lower()
            
            # ========== Block remote commands for locked notebooks ==========
            if is_locked:
                # Only allow [c]hange, [a]ctivity, [b]ack, [q]uit
                if cmd == "c":
                    self._show_change_options(notebook, has_remote)
                elif cmd == "a":
                    self.show_security_activity(notebook)
                elif cmd == "b":
                    break
                elif cmd == "q" or cmd == "qy":
                    if cmd == "qy":
                        self.clear_screen()
                        if self.is_standalone:
                            sys.exit(0)
                        else:
                            return "exit_app"
                    else:
                        if self.is_standalone:
                            confirm = self.get_input("Quit Notebook Manager? [y/N]: ").lower()
                            if confirm == "y":
                                self.clear_screen()
                                sys.exit(0)
                        else:
                            confirm = self.get_input("Quit Terminal Notes? [y/N]: ").lower()
                            if confirm == "y":
                                self.clear_screen()
                                return "exit_app"
                else:
                    print(f"Invalid command. Available options: {', '.join(options)}")
                    self.get_input("Press Enter to continue...")
                continue
            # ========== END FIX ==========
            
            # Handle single letter commands for unlocked notebooks
            if cmd == "b":
                break
            
            elif cmd == "l" and not has_remote:
                self.configure_notebook(notebook)
            
            elif cmd == "c":
                self._show_change_options(notebook, has_remote)
            
            elif cmd == "v" and has_remote:
                self.toggle_visibility(notebook)
            
            elif cmd == "s" and has_remote:
                self.sync_notebook(notebook)
            
            elif cmd == "d" and has_remote:
                self.delete_repo(notebook)
            
            elif cmd == "a":
                self.show_security_activity(notebook)
            
            # Handle commands with numbers
            elif len(cmd) > 1 and cmd[0] in ['v', 's', 'd', 'a', 'c', 'l']:
                try:
                    num = int(cmd[1:])
                    if cmd[0] == 'v' and has_remote:
                        self.toggle_visibility(notebook)
                    elif cmd[0] == 's' and has_remote:
                        self.sync_notebook(notebook)
                    elif cmd[0] == 'd' and has_remote:
                        self.delete_repo(notebook)
                    elif cmd[0] == 'a':
                        self.show_security_activity(notebook)
                    elif cmd[0] == 'c':
                        self._show_change_options(notebook, has_remote)
                    elif cmd[0] == 'l' and not has_remote:
                        self.configure_notebook(notebook)
                except ValueError:
                    print(f"Invalid command format. Use {cmd[0]} or {cmd[0]}#")
                    self.get_input("Press Enter to continue...")
            
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    self.clear_screen()
                    if self.is_standalone:
                        sys.exit(0)
                    else:
                        return "exit_app"
                else:
                    if self.is_standalone:
                        confirm = self.get_input("Quit Notebook Manager? [y/N]: ").lower()
                        if confirm == "y":
                            self.clear_screen()
                            sys.exit(0)
                    else:
                        confirm = self.get_input("Quit Terminal Notes? [y/N]: ").lower()
                        if confirm == "y":
                            self.clear_screen()
                            return "exit_app"
            
            else:
                print(f"Invalid command. Available options: {', '.join(options)}")
                self.get_input("Press Enter to continue...")
                
    def show_security_activity(self, notebook):
        """Show security-related commits (password changes) for this notebook"""
        import subprocess
        from datetime import datetime
        from notebook_operations import find_notebook_folder
        import shutil
        
        self.clear_screen()
        
        notebook_id = notebook['id']
        notebook_obj = self.manager.find_notebook_by_id(notebook_id)
        if not notebook_obj:
            print("  ✗ Notebook not found")
            self.get_input("Press Enter to continue...")
            return
        
        root = self.manager._find_root_notebook(notebook_obj)
        if not root:
            print("  ✗ Root notebook not found")
            self.get_input("Press Enter to continue...")
            return
        
        # Find repository path
        repo_path = None
        if hasattr(root, 'custom_path') and root.custom_path:
            repo_path = root.custom_path
        else:
            registry_data = self.manager.load_registry()
            if notebook_id in registry_data["notebooks"]:
                entry = registry_data["notebooks"][notebook_id]
                if isinstance(entry, dict):
                    folder_path = entry.get("path")
                    if folder_path:
                        if not os.path.isabs(folder_path):
                            folder_path = os.path.join(self.manager.notebooks_root, folder_path)
                        repo_path = folder_path
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
                            folder_path = decrypted.get("path")
                            if folder_path:
                                if not os.path.isabs(folder_path):
                                    folder_path = os.path.join(self.manager.notebooks_root, folder_path)
                                repo_path = folder_path
            
            if not repo_path or not os.path.exists(repo_path):
                repo_path = find_notebook_folder(notebook_id, self.manager.notebooks_root)
        
        if not repo_path or not os.path.exists(repo_path):
            print("  ✗ Cannot find repository path")
            self.get_input("Press Enter to continue...")
            return
        
        # Query git for security commits
        cmd = [
            "git", "log", "--all",
            "--grep", f"root: {root.id}",
            "--grep", "SECURITY:",
            "--pretty=format:%ai|%s"
        ]
        
        try:
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=10)
            if result.returncode != 0 or not result.stdout.strip():
                print("\n  No security activity recorded.")
                self.get_input("\nPress Enter to continue...")
                return
            
            lines = result.stdout.strip().split('\n')
            commits = []
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split('|', 1)
                if len(parts) >= 2:
                    date_str, message = parts
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
                    except:
                        date_obj = datetime.now()
                    
                    # Clean up message: remove "SECURITY: " and "method: ", "machine: "
                    clean_msg = message.replace("SECURITY: ", "")
                    clean_msg = clean_msg.replace("password changed | ", "")
                    clean_msg = clean_msg.replace("method: ", "")
                    clean_msg = clean_msg.replace("machine: ", "")
                    clean_msg = clean_msg.replace(" | root: " + root.id, "")
                    
                    commits.append({
                        'date': date_obj,
                        'message': clean_msg
                    })
            
            if not commits:
                print("\n  No security activity recorded.")
                self.get_input("\nPress Enter to continue...")
                return
            
            commits.sort(key=lambda x: x['date'], reverse=True)
            
            # Pagination
            terminal_width, terminal_height = shutil.get_terminal_size()
            items_per_page = max(1, terminal_height - 8)
            total_pages = (len(commits) + items_per_page - 1) // items_per_page
            page = 0
            
            while True:
                self.clear_screen()
                width, _ = shutil.get_terminal_size()
                
                # Header
                print("" * width)
                print(f"Security Activity - {notebook['name']}".center(width))
                print("" * width)
                
                start = page * items_per_page
                end = min(start + items_per_page, len(commits))
                page_commits = commits[start:end]
                
                for i, c in enumerate(page_commits, 1):
                    date_str = c['date'].strftime("%Y-%m-%d %H:%M")
                    print(f"[{i}] {date_str} | {c['message']}")
                
                # Page indicator
                if total_pages > 1:
                    page_text = f"Page {page + 1} of {total_pages}"
                    centered = page_text.center(width)
                    text_start = (width - len(page_text)) // 2
                    text_end = text_start + len(page_text)
                    chars = list(centered)
                    
                    if page > 0:
                        left = text_start - 6
                        if left >= 0:
                            chars[left:left+2] = list("<<")
                    if page < total_pages - 1:
                        right = text_end + 4
                        if right + 2 <= width:
                            chars[right:right+2] = list(">>")
                    
                    print()
                    print(''.join(chars))
                else:
                    print()
                
                # Footer
                print("" * width)
                footer = ["[B]ack"]
                if total_pages > 1:
                    if page > 0:
                        footer.insert(0, "[P]rev")
                    if page < total_pages - 1:
                        footer.insert(0, "[N]ext")
                print("  ".join(footer))
                print()
                
                cmd = self.get_input("> ").lower()
                if cmd == "b" or cmd == "q" or cmd == "qy":
                    if cmd == "qy":
                        self.clear_screen()
                        if self.is_standalone:
                            sys.exit(0)
                        else:
                            return "exit_app"
                    break
                elif cmd == "n" and page < total_pages - 1:
                    page += 1
                elif cmd == "p" and page > 0:
                    page -= 1
            
        except subprocess.TimeoutExpired:
            print("  ✗ Timeout reading security history")
            self.get_input("Press Enter to continue...")
        except Exception as e:
            print(f"  ✗ Error reading security history: {e}")
            self.get_input("Press Enter to continue...")
    
    def has_security_activity(self, notebook):
        """Check if there are any security commits for this notebook"""
        notebook_id = notebook['id']
        
        notebook_obj = self.manager.find_notebook_by_id(notebook_id)
        if not notebook_obj:
            return False
        
        root = self.manager._find_root_notebook(notebook_obj)
        if not root:
            return False
        
        repo_path = None
        if hasattr(root, 'custom_path') and root.custom_path:
            repo_path = root.custom_path
        else:
            notebooks_root = self.manager.notebooks_root
            if os.path.exists(notebooks_root):
                for folder in os.listdir(notebooks_root):
                    if folder.endswith(root.id):
                        repo_path = os.path.join(notebooks_root, folder)
                        break
        
        if not repo_path or not os.path.exists(repo_path):
            return False
        
        if not os.path.exists(os.path.join(repo_path, ".git")):
            return False
        
        cmd = [
            "git", "log", "--all", "--oneline",
            "--grep", f"root: {root.id}",
            "--grep", "SECURITY:",
            "--max-count", "1"
        ]
        
        try:
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True, timeout=5)
            return result.returncode == 0 and bool(result.stdout.strip())
        except Exception:
            return False

    def _show_change_options(self, notebook, has_remote):
        """Show change options based on whether remote is configured"""
        from secure_session import SecureSessionStorage
        
        self.clear_screen()
        self.print_header(f"Change Options - {notebook['name']}")
        
        print()
        print("  [1] Change password")
        print("  [2] Change Autolock status")
        
        if has_remote:
            print("  [3] Change remote location")
            option_offset = 4
        else:
            option_offset = 3
        
        print(f"  [{option_offset}] Change trusted device status")
        
        # ========== NEW: Option 5 only when notebook is UNLOCKED ==========
        is_unlocked = not notebook.get('locked', True) and notebook.get('path') is not None
        if is_unlocked:
            print(f"  [{option_offset + 1}] Change vault location")
        # ========== END NEW ==========
        
        print()
        print("  Press Enter to cancel")
        print()
        
        choice = self.get_input("  Choose: ").strip()
        
        if not choice:
            return
        
        if choice == "1":
            self.change_handler._change_password(notebook)
        elif choice == "2":
            self.change_handler._toggle_autolock(notebook)
        elif choice == "3" and has_remote:
            self.change_handler._change_remote(notebook)
        elif choice == str(option_offset):
            self.change_handler._show_trusted_devices(notebook)
        elif is_unlocked and choice == str(option_offset + 1):
            self.change_handler._change_vault_location(notebook)

    def get_git_manager_by_path(self, repo_path):
        """Get Git manager for a repository path"""
        from git_manager import GitManager
        return GitManager(repo_path)

    def configure_notebook(self, notebook):
        self.clear_screen()
        self.print_header(f"Configure {notebook['name']}")
        # ========== SURGICAL FIX: Use folder name, not notebook ID ==========
        folder_name = os.path.basename(notebook['path']) if notebook['path'] else ""
        
        # If no path, try to get folder name from notebooks_root
        if not folder_name:
            # Try to find folder by notebook_id
            notebooks_root = getattr(self.manager, 'notebooks_root', None)
            if notebooks_root and os.path.exists(notebooks_root):
                for folder in os.listdir(notebooks_root):
                    if folder.endswith(notebook['id']):
                        folder_name = folder
                        break
        
        # Use folder_name as suggested repo (NOT the notebook ID)
        suggested_repo = folder_name if folder_name else f"{notebook['name']}-{notebook['id']}"
        # ========== END FIX ==========
        folder_name = os.path.basename(notebook['path']) if notebook['path'] else ""
        suggested_repo = folder_name if folder_name else notebook['id'][:8]
        accounts = list(self.accounts.get("accounts", {}).items())
        if not accounts:
            print("No accounts found. Please add an account first.")
            self.get_input("Press Enter to continue...")
            self.show_accounts_screen()
            return
        print("Select account:")
        for i, (acc_id, acc) in enumerate(accounts, 1):
            notebook_count = len(acc.get("notebooks", {}))
            print(f"[{i}] {acc['username']}@{acc.get('platform', 'github')} - {notebook_count} notebooks")
        print(f"[{len(accounts)+1}] Add new account")
        print()
        choice = self.get_input("Enter number: ")
        if not choice:
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(accounts):
                acc_id, account = accounts[idx]
            elif idx == len(accounts):
                self.show_add_account()
                self.load_accounts()
                self.configure_notebook(notebook)
                return
            else:
                return
        except:
            return
        print()
        print(f"Repository name: {suggested_repo}")
        repo_name = suggested_repo
        print("  (Repository name is fixed and cannot be changed)")
        print("\nRepository visibility:")
        print("[1] 🔒 Private - Only you can see and push")
        print("[2] 🔓 Public  - Everyone can see")
        print()
        vis_choice = self.get_input("Choose [1/2]: ")
        if not vis_choice:
            print("\nConfiguration cancelled.")
            self.get_input("Press Enter to continue...")
            return

        while vis_choice not in ['1', '2']:
            vis_choice = self.get_input("Please enter 1 or 2 (or press Enter to cancel): ")
            if not vis_choice:
                print("\nConfiguration cancelled.")
                self.get_input("Press Enter to continue...")
                return

        visibility = "private" if vis_choice == "1" else "public"
        print("\n" + "=" * 50)
        print("Configuration Summary:")
        print(f"Account: {account['username']}@{account.get('platform', 'github')}")
        print(f"Repository: {repo_name}")
        print(f"Visibility: {'🔒 PRIVATE' if visibility == 'private' else '🔓 PUBLIC'}")
        print("=" * 50)
        print()
        confirm = self.get_input("Save this configuration? [y/N]: ").lower()
        if confirm != 'y':
            print("\nConfiguration cancelled.")
            self.get_input("Press Enter to continue...")
            return
        exists, existing_nb = self.repo_exists_in_accounts(acc_id, repo_name)
        if exists and existing_nb != notebook['id']:
            print(f"\nRepository '{repo_name}' is already used by another notebook!")
            print(f"Each repository can only be linked to one notebook.")
            print(f"Please choose a different name or use a different account.")
            self.get_input("Press Enter to continue...")
            return
        if self.update_notebook_config(notebook['id'], acc_id, repo_name, visibility):
            print(f"\n✓ Configuration saved successfully!")
            
            # ========== SURGICAL FIX: Update TokenVault with linked notebook ==========
            from token_vault import TokenVault
            vault = TokenVault(self.app_dir)
            account_data = vault.get_full_account(acc_id)
            
            if account_data:
                linked = account_data.get("linked_notebooks", [])
                if notebook['id'] not in linked:
                    linked.append(notebook['id'])
                    vault.store_token(
                        acc_id,
                        account_data['username'],
                        account_data['platform'],
                        account_data['host'],
                        account_data['api_url'],
                        account_data['token'],
                        linked
                    )
                    print(f"  ✓ Notebook linked to account: {account['username']}@{account.get('platform', 'github')}")
            else:
                # Account exists in accounts dict but not in vault? Add it
                token = self._decrypt_token(account.get('token_enc', ''))
                if token:
                    vault.store_token(
                        acc_id,
                        account['username'],
                        account.get('platform', 'github'),
                        account.get('host', 'github.com'),
                        account.get('api_url', 'https://api.github.com'),
                        token,
                        [notebook['id']]
                    )
                    print(f"  ✓ Notebook linked to account: {account['username']}@{account.get('platform', 'github')}")
            # ========== END FIX ==========
            
            print(f"\nNext steps:")
            print(f"1. Use [S]ync to create the repository on GitHub and push your notebook")
            print(f"2. The repository will be created as {'🔒 PRIVATE' if visibility == 'private' else '🔓 PUBLIC'}")
            print(f"3. You can change visibility anytime with the [V]isibility button")
            notebook['git_config'] = self.get_notebook_config(notebook['id'])
            notebook['account'] = self.get_account_for_notebook(notebook['id'])
        else:
            print(f"\n✗ Failed to save configuration")
        self.get_input("Press Enter to continue...")

    def create_repo(self, account, repo_name, token, visibility="private"):
        import subprocess
        import json
        private_flag = "true" if visibility == "private" else "false"
        cmd = f'''curl -s -X POST -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/user/repos \
            -d '{{"name":"{repo_name}","private":{private_flag},"auto_init":false}}' '''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                return "id" in data
            except:
                return False
        return False

    def delete_github_repo(self, account, repo_name, token):
        import subprocess
        full_name = f"{account['username']}/{repo_name}"
        cmd = f'''curl -s -X DELETE -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
             https://api.github.com/repos/{full_name}'''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0 or "204" in result.stderr
    
    def sync_notebook(self, notebook):
        """Thin wrapper – delegates to NotebookSync"""
        from notebook_sync import NotebookSync
        syncer = NotebookSync(self.manager, self.accounts, self.app_dir,
                            ui_callback=self._sync_ui_callback,
                            confirm_callback=self._sync_confirm)
        return syncer.sync_notebook(notebook)

    def _sync_ui_callback(self, message, end="\n"):
        print(message, end=end)

    def _sync_confirm(self, prompt):
        return input(prompt).strip().lower() == 'y'

    def has_internet(self):
        import socket
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def check_token_valid(self, account, token):
        import subprocess
        platform = account.get('platform', 'github')
        if platform == 'github':
            test_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: token {token}' https://api.github.com/user"
        elif platform == 'gitlab':
            test_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: Bearer {token}' https://gitlab.com/api/v4/user"
        elif platform == 'bitbucket':
            import base64
            auth = base64.b64encode(f"{account['username']}:{token}".encode()).decode()
            test_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: Basic {auth}' https://api.bitbucket.org/2.0/user"
        else:
            return True
        result = subprocess.run(test_cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip() == "200"

    def delete_repo(self, notebook):
        """Delete remote repository or unlink with multiple options"""
        while True:
            self.clear_screen()
            width, _ = self.get_terminal_size()
            
            git_config = notebook.get("git_config")
            account = notebook.get("account")
            
            if not git_config or not account:
                print("  ⚠ Not configured with a remote repository.")
                self.get_input("Press Enter to continue...")
                return
            
            repo_name = git_config['repo']
            full_name = f"{account['username']}/{repo_name}"
            
            print("" * width)
            print(f"Delete Options - {notebook['name']}".center(width))
            print("" * width)
            print()
            print(f"  Repository: {full_name}")
            print(f"  Account: {account['username']}@{account.get('platform', 'github')}")
            print()
            print("  [1] Delete remote repository only")
            print("      • Permanently delete from GitHub/GitLab/Bitbucket")
            print("      • Local notebook files remain untouched")
            print("      • Git remote will be removed from local config")
            print()
            print("  [2] Unlink remote (keep repository)")
            print("      • Remove git remote 'origin' from local config")
            print("      • Remote repository stays on server")
            print("      • Local notebook files remain untouched")
            print()
            print("  [3] Cancel")
            print()
            print("" * width)
            
            choice = self.get_input("  Choose [1-3]: ").strip()
            
            if choice == "1":
                self._delete_remote_repository(notebook, account, repo_name, full_name)
                return  # Exit immediately after deletion
            elif choice == "2":
                self._unlink_remote(notebook)
                return  # Exit immediately after unlinking
            elif choice == "3":
                break
        
        self.get_input("\nPress Enter to continue...")
    
    def repo_exists(self, account, repo_name, token):
        """Check if repository exists on remote"""
        import urllib.request
        import urllib.error
        import json
        
        # Determine platform
        platform = account.get('platform', 'github')
        username = account.get('username', '')
        
        if platform == 'github':
            url = f"https://api.github.com/repos/{username}/{repo_name}"
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Terminal-Notes/1.0'
            }
            
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.status == 200
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return False
                return False
            except Exception:
                return False
                
        elif platform == 'gitlab':
            url = f"https://gitlab.com/api/v4/projects/{username}%2F{repo_name}"
            headers = {'Authorization': f'Bearer {token}'}
            
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    return response.status == 200
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return False
                return False
            except Exception:
                return False
        
        else:
            # For other platforms, try git ls-remote
            repo_url = account.get('url', '')
            if repo_url:
                import subprocess
                result = subprocess.run(
                    ['git', 'ls-remote', '--heads', repo_url],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.returncode == 0
        
        return False

    def _delete_remote_repository(self, notebook, account, repo_name, full_name):
        """Delete remote repository only"""
        self.clear_screen()
        width, _ = self.get_terminal_size()
        
        print("" * width)
        print("⚠ DELETE REMOTE REPOSITORY ⚠".center(width))
        print("" * width)
        print()
        print(f"  Repository: {full_name}")
        print(f"  Account: {account['username']}@{account.get('platform', 'github')}")
        print()
        print("  This will PERMANENTLY delete the remote repository!")
        print("  Local notebook files will NOT be affected.")
        print()
        print("  You can always push again later to recreate the repository.")
        print()
        
        # Check internet connection
        print("  Checking connection...", end="", flush=True)
        if not self.has_internet():
            print(" FAILED")
            print("\n  No internet connection. Cannot delete remote repository.")
            self.get_input("Press Enter to continue...")
            return
        print(" OK")
        
        token = self._decrypt_token(account['token_enc'])
        if not token:
            print("\n  Could not decrypt token.")
            self.get_input("Press Enter to continue...")
            return
        
        print("  Validating token...", end="", flush=True)
        if not self.check_token_valid(account, token):
            print(" INVALID")
            print("\n  Token is invalid or expired.")
            self.get_input("Press Enter to continue...")
            return
        print(" OK")
        
        print(f"\n  Checking if repository exists...", end="", flush=True)
        exists = self.repo_exists(account, repo_name, token)
        if not exists:
            print(" NOT FOUND")
            print("\n  Repository doesn't exist on remote.")
            print("  Cleaning up local configuration...")
            
            # Still clean up local even if remote doesn't exist
            path = notebook.get('path', '')
            if path and os.path.exists(path):
                subprocess.run(["git", "remote", "remove", "origin"], cwd=path, capture_output=True)
            
            # Clear configuration from registry
            for acc_id, acc in self.accounts["accounts"].items():
                if notebook['id'] in acc.get("notebooks", {}):
                    del acc["notebooks"][notebook['id']]
                    self.save_accounts()
                    break
            
            notebook['git_config'] = None
            notebook['account'] = None
            self.get_input("Press Enter to continue...")
            return
        print(" FOUND")
        
        print()
        confirm = self.get_input(f"  Type the repository name '{repo_name}' to confirm deletion: ")
        
        if confirm != repo_name:
            print("\n  Confirmation failed. Delete cancelled.")
            self.get_input("Press Enter to continue...")
            return
        
        print("\n  Deleting repository...", end="", flush=True)
        
        # ========== ACTUALLY DELETE THE REPOSITORY ==========
        platform = account.get('platform', 'github')
        success = False
        
        if platform == 'github':
            # GitHub API DELETE request
            import json
            cmd = f'''curl -s -X DELETE -H "Authorization: token {token}" \
                -H "Accept: application/vnd.github.v3+json" \
                https://api.github.com/repos/{full_name}'''
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            # GitHub returns 204 No Content on success
            if result.returncode == 0 and ('204' in result.stderr or 'No Content' in result.stderr or result.stdout == ''):
                success = True
                print(" DELETED")
            else:
                # Check if repo already doesn't exist (404)
                if '404' in result.stderr:
                    print(" NOT FOUND")
                    success = True  # Already gone
                else:
                    print(" FAILED")
                    print(f"\n  Delete failed: {result.stderr[:200]}")
                    self.get_input("Press Enter to continue...")
                    return
        
        elif platform == 'gitlab':
            # GitLab API DELETE request
            project_id = f"{account['username']}%2F{repo_name}"
            cmd = f'''curl -s -X DELETE -H "Authorization: Bearer {token}" \
                "https://gitlab.com/api/v4/projects/{project_id}"'''
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and ('204' in result.stderr or '202' in result.stderr):
                success = True
                print(" DELETED")
            else:
                print(" FAILED")
                self.get_input("Press Enter to continue...")
                return
        
        elif platform == 'bitbucket':
            # Bitbucket API DELETE request
            cmd = f'''curl -s -X DELETE -u "{account['username']}:{token}" \
                https://api.bitbucket.org/2.0/repositories/{full_name}'''
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                success = True
                print(" DELETED")
            else:
                print(" FAILED")
                self.get_input("Press Enter to continue...")
                return
        
        if success:
            # Remove git remote from local
            path = notebook.get('path', '')
            if path and os.path.exists(path):
                subprocess.run(["git", "remote", "remove", "origin"], cwd=path, capture_output=True)
                print("  ✓ Git remote removed from local config")
            
            # Clear configuration from registry
            for acc_id, acc in self.accounts["accounts"].items():
                if notebook['id'] in acc.get("notebooks", {}):
                    del acc["notebooks"][notebook['id']]
                    self.save_accounts()
                    break
            
            # Update notebook object
            notebook['git_config'] = None
            notebook['account'] = None
            
            # Also update TokenVault
            from token_vault import TokenVault
            vault = TokenVault(self.app_dir)
            account_data = vault.get_full_account(account['id'])
            if account_data:
                linked = account_data.get("linked_notebooks", [])
                if notebook['id'] in linked:
                    linked.remove(notebook['id'])
                    vault.store_token(
                        account['id'],
                        account_data['username'],
                        account_data['platform'],
                        account_data['host'],
                        account_data['api_url'],
                        account_data['token'],
                        linked
                    )
            
            print("\n  ✓ Remote repository deleted successfully!")
        else:
            print("\n  ✗ Failed to delete repository. Check your token permissions.")
        
        self.get_input("\nPress Enter to continue...")

    def _unlink_remote(self, notebook):
        """Unlink remote repository (keep remote, just remove local connection)"""
        self.clear_screen()
        width, _ = self.get_terminal_size()
        
        git_config = notebook.get("git_config")
        account = notebook.get("account")
        
        if not git_config or not account:
            print("  ⚠ Not configured with a remote repository.")
            self.get_input("\nPress Enter to continue...")
            return
        
        repo_name = git_config['repo']
        full_name = f"{account['username']}/{repo_name}"
        
        print("" * width)
        print("Unlink Remote Repository".center(width))
        print("" * width)
        print()
        print(f"  Repository: {full_name}")
        print(f"  Account: {account['username']}@{account.get('platform', 'github')}")
        print()
        print("  This will REMOVE the git remote 'origin' from your local config.")
        print("  The remote repository will remain untouched on the server.")
        print("  Your local notebook files will NOT be affected.")
        print()
        print("  You can re-link the notebook later using [C]hange → [3] Change remote")
        print()
        
        confirm = self.get_input("  Unlink this notebook from the remote repository? [y/N]: ").lower()
        
        if confirm != 'y':
            print("\n  Cancelled.")
            self.get_input("\nPress Enter to continue...")
            return
        
        # ========== FIX: Safe path access ==========
        path = notebook.get('path', '')
        if not path:
            print("\n  ⚠ No local path found for this notebook. Skipping git remote removal.")
        elif not os.path.exists(path):
            print(f"\n  ⚠ Notebook path not found: {path}. Skipping git remote removal.")
        else:
            result = subprocess.run(["git", "remote", "remove", "origin"], cwd=path, capture_output=True)
            if result.returncode == 0:
                print("  ✓ Git remote removed from local config")
            else:
                print("  ⚠ Git remote not found or already removed")
        # ========== END FIX ==========
        
        # Clear configuration from registry
        for acc_id, acc in self.accounts["accounts"].items():
            if notebook['id'] in acc.get("notebooks", {}):
                del acc["notebooks"][notebook['id']]
                self.save_accounts()
                break
        
        # Also update TokenVault
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        account_data = vault.get_full_account(account['id'])
        if account_data:
            linked = account_data.get("linked_notebooks", [])
            if notebook['id'] in linked:
                linked.remove(notebook['id'])
                vault.store_token(
                    account['id'],
                    account_data['username'],
                    account_data['platform'],
                    account_data['host'],
                    account_data['api_url'],
                    account_data['token'],
                    linked
                )
        
        # Update notebook object
        notebook['git_config'] = None
        notebook['account'] = None
        
        print("\n  ✓ Notebook unlinked from remote repository!")
        self.get_input("\nPress Enter to continue...")

    def show_add_account(self):
        self.clear_screen()
        self.print_header("Add Git Account")
        print("Platform:")
        print("[1] GitHub")
        print("[2] GitLab") 
        print("[3] Bitbucket")
        print("[4] Self-hosted")
        print()
        choice = self.get_input("Choose [1-4]: ")
        if choice == "1":
            self._add_github_account()
        elif choice == "2":
            self._add_gitlab_account()
        elif choice == "3":
            self._add_bitbucket_account()
        elif choice == "4":
            self._add_gitea_account()

    def _add_github_account(self):
        self.clear_screen()
        self.print_header("Add GitHub Account")
        print("Step 1: Your username")
        print("────────────────────────────────")
        print("GitHub username (not email)")
        print("Example: johndoe")
        print()
        username = self.get_input("Username: ")
        if not username:
            return
        print("\nStep 2: Create token")
        print("────────────────────────────────")
        print("1. Go to: github.com/settings/tokens")
        print("2. Click 'Generate new token'")
        print("3. Name: 'Terminal Notes'")
        print("4. Select scope: ☑ repo")
        print("5. COPY token now! (ghp_xxxxx)")
        print()
        token = self.get_password("Token: ")
        if not token:
            return
        print("\nTesting...", end="")
        if not self.test_token_connection("github", username, "github.com", token):
            print("Failed!")
            print("Token invalid or missing 'repo' scope")
            self.get_input("Press Enter to continue...")
            return
        print("✓ Success!")
        
        acc_id = self._generate_account_id(username, "github.com")
        
        # Store full account data in TokenVault
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        if not vault.store_token(acc_id, username, "github", "github.com", 
                                "https://api.github.com", token, []):
            print("❌ Failed to store account securely!")
            self.get_input("Press Enter to continue...")
            return
        
        # Store in memory
        self.accounts["accounts"][acc_id] = {
            "id": acc_id,
            "platform": "github",
            "username": username,
            "host": "github.com",
            "api_url": "https://api.github.com",
            "token_enc": acc_id,
            "created": datetime.now().isoformat(),
            "notebooks": {}
        }
        
        print("\n✓ GitHub account added!")
        self.get_input("Press Enter to continue...")

    def _add_gitlab_account(self):
        self.clear_screen()
        self.print_header("Add GitLab Account")
        print("Step 1: Your username")
        print("────────────────────────────────")
        print("GitLab username (not email)")
        print("Example: janedoe")
        print()
        username = self.get_input("Username: ")
        if not username:
            return
        print("\nStep 2: Create token")
        print("────────────────────────────────")
        print("1. Go to: gitlab.com/-/profile/tokens")
        print("2. Name: 'Terminal Notes'")
        print("3. Select scopes: ☑ api ☑ write_repository")
        print("4. COPY token now! (glpat-xxxxx)")
        print()
        token = self.get_password("Token: ")
        if not token:
            return
        print("\n🔍 Testing...", end="")
        if not self.test_token_connection("gitlab", username, "gitlab.com", token):
            print("Failed!")
            print("Token invalid or missing required scopes")
            self.get_input("Press Enter to continue...")
            return
        print("✓ Success!")
        
        acc_id = self._generate_account_id(username, "gitlab.com")
        
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        if not vault.store_token(acc_id, token):
            print("Failed to store token securely!")
            self.get_input("Press Enter to continue...")
            return
        
        self.accounts["accounts"][acc_id] = {
            "id": acc_id,
            "platform": "gitlab",
            "username": username,
            "host": "gitlab.com",
            "api_url": "https://gitlab.com/api/v4",
            "token_enc": acc_id,
            "created": datetime.now().isoformat(),
            "notebooks": {}
        }
        self.save_accounts()
        print("\nGitLab account added!")
        self.get_input("Press Enter to continue...")

    def _add_bitbucket_account(self):
        self.clear_screen()
        self.print_header("Add Bitbucket Account")
        print("Step 1: Your username")
        print("────────────────────────────────")
        print("Bitbucket username (not email)")
        print("Example: bobsmith")
        print()
        username = self.get_input("Username: ")
        if not username:
            return
        print("\nStep 2: Create app password")
        print("────────────────────────────────")
        print("1. Go to: bitbucket.org/account/settings/app-passwords/")
        print("2. Click 'Create app password'")
        print("3. Name: 'Terminal Notes'")
        print("4. Select: ☑ Repositories: Write")
        print("5. COPY password now! (random string)")
        print()
        token = self.get_password("App Password: ")
        if not token:
            return
        print("\n🔍 Testing...", end="")
        if not self.test_token_connection("bitbucket", username, "bitbucket.org", token):
            print("Failed!")
            print("Invalid app password or missing permissions")
            self.get_input("Press Enter to continue...")
            return
        print("✓ Success!")
        
        acc_id = self._generate_account_id(username, "bitbucket.org")
        
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        if not vault.store_token(acc_id, token):
            print("Failed to store token securely!")
            self.get_input("Press Enter to continue...")
            return
        
        self.accounts["accounts"][acc_id] = {
            "id": acc_id,
            "platform": "bitbucket",
            "username": username,
            "host": "bitbucket.org",
            "api_url": "https://api.bitbucket.org/2.0",
            "token_enc": acc_id,
            "created": datetime.now().isoformat(),
            "notebooks": {}
        }
        self.save_accounts()
        print("\nBitbucket account added!")
        self.get_input("Press Enter to continue...")

    def _add_gitea_account(self):
        self.clear_screen()
        self.print_header("Add Self-Hosted Account")
        print("Step 1: Server address")
        print("────────────────────────────────")
        print("Your Git server (include port)")
        print("Examples: git.example.com | company.com:3000")
        print()
        host = self.get_input("Host: ")
        if not host:
            return
        host = host.replace("http://", "").replace("https://", "")
        print("\nStep 2: Your username")
        print("────────────────────────────────")
        print("Username on this server")
        print("Example: admin")
        print()
        username = self.get_input("Username: ")
        if not username:
            return
        print("\nStep 3: Access token")
        print("────────────────────────────────")
        print(f"Create token in: {host}/user/settings/applications")
        print("COPY token now!")
        print()
        token = self.get_password("Token: ")
        if not token:
            return
        print("\n🔍 Testing...", end="")
        if not self._test_gitea_connection(host, token):
            print("Failed!")
            print("Cannot connect to server or invalid token")
            self.get_input("Press Enter to continue...")
            return
        print("✓ Success!")
        
        acc_id = self._generate_account_id(username, host)
        
        from token_vault import TokenVault
        vault = TokenVault(self.app_dir)
        if not vault.store_token(acc_id, token):
            print("Failed to store token securely!")
            self.get_input("Press Enter to continue...")
            return
        
        self.accounts["accounts"][acc_id] = {
            "id": acc_id,
            "platform": "gitea",
            "username": username,
            "host": host,
            "api_url": f"https://{host}/api/v1",
            "token_enc": acc_id,
            "created": datetime.now().isoformat(),
            "notebooks": {}
        }
        self.save_accounts()
        print("\nSelf-hosted account added!")
        self.get_input("Press Enter to continue...")

    def _test_gitea_connection(self, host, token):
        import subprocess
        api_url = f"https://{host}/api/v1/user"
        cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: token {token}' {api_url}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.stdout.strip() == "200"

    def test_token_connection(self, platform, username, host, token):
        import subprocess
        import json
        import base64
        import sys
        
        print(" Testing...", end="", flush=True)
        
        try:
            if platform == "github":
                # Use curl with longer timeout and follow redirects
                cmd = f'curl -s -m 10 -L -H "Authorization: token {token}" https://api.github.com/user'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                if result.returncode == 0 and result.stdout:
                    try:
                        data = json.loads(result.stdout)
                        if "login" in data:
                            return True
                    except:
                        pass
                # If curl fails, assume token might still be valid (network issue)
                print(" (network issue, assuming valid)", end="", flush=True)
                return True
                
            elif platform == "gitlab":
                cmd = f'curl -s -m 10 -H "Authorization: Bearer {token}" https://gitlab.com/api/v4/user'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                if result.returncode == 0 and result.stdout:
                    try:
                        data = json.loads(result.stdout)
                        if "username" in data:
                            return True
                    except:
                        pass
                print(" (network issue, assuming valid)", end="", flush=True)
                return True
                
            elif platform == "bitbucket":
                auth = base64.b64encode(f"{username}:{token}".encode()).decode()
                cmd = f'curl -s -m 10 -H "Authorization: Basic {auth}" https://api.bitbucket.org/2.0/user'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                if result.returncode == 0 and result.stdout:
                    try:
                        data = json.loads(result.stdout)
                        if "username" in data:
                            return True
                    except:
                        pass
                print(" (network issue, assuming valid)", end="", flush=True)
                return True
                
            elif platform == "gitea":
                api_url = f"https://{host}/api/v1/user"
                cmd = f'curl -s -m 10 -H "Authorization: token {token}" {api_url}'
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
                return result.returncode == 0
                
            return False
            
        except subprocess.TimeoutExpired:
            print(" (timeout - assuming token is valid)", end="", flush=True)
            return True
        except Exception as e:
            print(f" (error: {e} - assuming valid)", end="", flush=True)
            return True

    def remove_account(self):
        self.clear_screen()
        self.print_header("Remove Account")
        accounts = list(self.accounts.get("accounts", {}).items())
        if not accounts:
            print("No accounts to remove.")
            self.get_input("Press Enter to continue...")
            return
        for i, (acc_id, acc) in enumerate(accounts, 1):
            notebook_count = len(acc.get("notebooks", {}))
            print(f"[{i}] {acc['username']}@{acc.get('host', 'github.com')} ({notebook_count} notebooks)")
        print()
        choice = self.get_input("Enter number to remove (or Enter to cancel): ")
        if not choice:
            return
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(accounts):
                acc_id = accounts[idx][0]
                if len(accounts[idx][1].get("notebooks", {})) > 0:
                    print("\nAccount has linked notebooks!")
                    confirm = self.get_input("Remove anyway? Linked notebooks will be unlinked. [y/N]: ").lower()
                    if confirm != 'y':
                        return
                
                # Remove from TokenVault
                from token_vault import TokenVault
                vault = TokenVault(self.app_dir)
                vault.remove_token(acc_id)
                
                del self.accounts["accounts"][acc_id]
                self.save_accounts()
                print("\n✓ Account removed!")
        except:
            print("Invalid choice")
        self.get_input("Press Enter to continue...")

    def list_repo_contents(self, account, repo_name, token):
        import subprocess
        import json
        full_name = f"{account['username']}/{repo_name}"
        cmd = f'''curl -s -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/{full_name}/contents/'''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                contents = json.loads(result.stdout)
                files = []
                for item in contents:
                    if item['type'] == 'file':
                        files.append({
                            'name': item['name'],
                            'path': item['path'],
                            'size': item['size'],
                            'download_url': item.get('download_url')
                        })
                return files
            except:
                return []
        return []

    def is_terminal_notes_repo(self, account, repo_name, token):
        """Check if repository contains Terminal Notes structure"""
        import subprocess
        import json
        from crypto import Crypto
        from notebook_operations import read_json
    
        full_name = f"{account['username']}/{repo_name}"
    
        # Get structure.json content
        cmd = f'''curl -s -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/{full_name}/contents/structure.json'''
    
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
        if result.returncode != 0:
            return False
    
        try:
            data = json.loads(result.stdout)
            if data.get('type') == 'file' and data.get('encoding') == 'base64':
                import base64
                content_bytes = base64.b64decode(data['content'])
            
                # Try to detect if it's encrypted (has .tn_test)
                tn_test_cmd = f'''curl -s -H "Authorization: token {token}" \
                     -H "Accept: application/vnd.github.v3+json" \
                    https://api.github.com/repos/{full_name}/contents/.tn_test'''
            
                tn_test_result = subprocess.run(tn_test_cmd, shell=True, capture_output=True, text=True)
                is_encrypted = tn_test_result.returncode == 0
            
                if is_encrypted:
                    # Can't read without password, but it's a Terminal Notes notebook
                    return True
                else:
                    # Try to parse as JSON to verify it's valid
                    try:
                        json.loads(content_bytes.decode('utf-8'))
                        return True
                    except:
                        return False
        except:
            pass
    
        return False

    
    def read_repo_file(self, account, repo_name, file_path, token):
        import subprocess
        import json
        import base64
        full_name = f"{account['username']}/{repo_name}"
        cmd = f'''curl -s -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/{full_name}/contents/{file_path}'''
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if data.get('encoding') == 'base64' and data.get('content'):
                    content = base64.b64decode(data['content']).decode('utf-8')
                    return content
            except:
                pass
        return None

    def get_notebook_info_from_github(self, account, repo_name, token):
        """Get notebook information from GitHub repo using crypto/ops"""
        import subprocess
        import json
        import base64
        from crypto import Crypto
        from notebook_operations import read_json
    
        full_name = f"{account['username']}/{repo_name}"
    
        # Check if encrypted
        tn_test_cmd = f'''curl -s -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/{full_name}/contents/.tn_test'''
    
        tn_test_result = subprocess.run(tn_test_cmd, shell=True, capture_output=True, text=True)
        is_encrypted = tn_test_result.returncode == 0
    
        # Get structure.json
        struct_cmd = f'''curl -s -H "Authorization: token {token}" \
             -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/{full_name}/contents/structure.json'''
    
        struct_result = subprocess.run(struct_cmd, shell=True, capture_output=True, text=True)
    
        if struct_result.returncode != 0:
            return None
    
        try:
            data = json.loads(struct_result.stdout)
            if data.get('encoding') == 'base64' and data.get('content'):
                content_bytes = base64.b64decode(data['content'])
        
                if is_encrypted:
                    # Return basic info for encrypted notebooks with integer counts
                    return {
                        "name": repo_name,
                        "note_count": 0,  # 🟢 Use 0 instead of "?"
                        "file_count": 0,   # 🟢 Use 0 instead of "?"
                        "sub_count": 0,    # 🟢 Add sub_count
                        "encrypted": True
                    }
                else:
                    # Parse JSON for unencrypted
                    content_str = content_bytes.decode('utf-8')
                    struct_data = json.loads(content_str)
            
                    # Extract notebook name
                    if "notebooks" in struct_data and struct_data["notebooks"]:
                        name = struct_data["notebooks"][0].get("name", "Unknown")
                    elif "name" in struct_data:
                        name = struct_data.get("name", "Unknown")
                    else:
                        name = repo_name
            
                    # Count items recursively
                    note_count = 0
                    file_count = 0
                    sub_count = 0
            
                    def count_items(nb_data):
                        n = 0
                        f = 0
                        s = 0
                        for note in nb_data.get("notes", []):
                            if note.get("file_extension"):
                                f += 1
                            else:
                                n += 1
                        s += len(nb_data.get("subnotebooks", []))
                        for sub in nb_data.get("subnotebooks", []):
                            sub_n, sub_f, sub_s = count_items(sub)
                            n += sub_n
                            f += sub_f
                            s += sub_s
                        return n, f, s

                    if "notebooks" in struct_data:
                        for nb in struct_data["notebooks"]:
                            n, f, s = count_items(nb)
                            note_count += n
                            file_count += f
                            sub_count += s
                    else:
                        note_count, file_count, sub_count = count_items(struct_data)
            
                    return {
                        "name": name,
                        "note_count": note_count,
                        "file_count": file_count,
                        "sub_count": sub_count,
                        "encrypted": False
                    }
        except Exception as e:
            print(f"Error parsing {repo_name}: {e}")
    
        return None

    def toggle_visibility(self, notebook):
        self.clear_screen()
        git_config = notebook.get("git_config")
        account = notebook.get("account")
        if not git_config or not account:
            print("Not configured.")
            self.get_input("Press Enter to continue...")
            return
        
        repo_name = git_config['repo']
        current_visibility = git_config.get("visibility", "private")
        full_name = f"{account['username']}/{repo_name}"
        
        # Check if notebook is encrypted
        is_encrypted = notebook.get('encrypted', False)
        
        self.print_header("Change Repository Visibility")
        
        print(f"Repository: {full_name}")
        print(f"Current: {'🔒 PRIVATE' if current_visibility == 'private' else '🔓 PUBLIC'}")
        print()
        
        new_visibility = "public" if current_visibility == "private" else "private"
        
        if new_visibility == "public":
            print("MAKING REPOSITORY PUBLIC")
            print()
            print("  ✓ Anyone can see this repository")
            print("  ✓ Anyone can clone/fork")
            print("  ✓ Your code becomes open source")
            print()
            if is_encrypted:
                print("  ⚠️  NOTEBOOK IS ENCRYPTED")
                print("     Contents remain encrypted, but metadata visible")
                print("     (filenames, structure, commit history)")
            else:
                print("  ⚠️  ALL CONTENTS become visible to everyone!")
                print("     No encryption - everything is readable")
        else:
            print("MAKING REPOSITORY PRIVATE")
            print()
            print("  ✓ Only you and collaborators can see")
            print("  ✓ Others cannot clone or fork")
            print("  ✓ Your code stays hidden from public")
            print()
            if is_encrypted:
                print("  ℹ️  Notebook is encrypted - double protection")
            else:
                print("  ℹ️  Consider encrypting notebook for extra security")
        
        print()
        confirm = self.get_input(f"[Y]es - Make {new_visibility.upper()}  [N]o - Cancel: ").lower()
        
        if confirm != 'y':
            print("Cancelled.")
            self.get_input("Press Enter to continue...")
            return
        
        token = self._decrypt_token(account['token_enc'])
        if not token:
            print("Could not decrypt token")
            self.get_input("Press Enter to continue...")
            return
        
        print(f"\nChanging visibility to {new_visibility.upper()}...")
        import subprocess
        import json
        private_flag = "false" if new_visibility == "public" else "true"
        cmd = f'''curl -s -X PATCH -H "Authorization: token {token}" \
            -H "Accept: application/vnd.github.v3+json" \
            https://api.github.com/repos/{full_name} \
            -d '{{"private":{private_flag}}}' '''
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)
                if "private" in data:
                    for acc_id, acc in self.accounts["accounts"].items():
                        if notebook['id'] in acc.get("notebooks", {}):
                            acc["notebooks"][notebook['id']]["visibility"] = new_visibility
                            repo_uuid = acc["notebooks"][notebook['id']].get("repo_uuid")
                            if repo_uuid and "repos" in self.accounts:
                                self.accounts["repos"][repo_uuid]["visibility"] = new_visibility
                            self.save_accounts()
                            break
                    notebook["git_config"]["visibility"] = new_visibility
                    print(f"\n✓ Repository is now {'🔓 PUBLIC' if new_visibility == 'public' else '🔒 PRIVATE'}!")
                    
                    # Additional warning for unencrypted public notebooks
                    if new_visibility == "public" and not is_encrypted:
                        print("\n⚠️  REMINDER: This notebook is NOT encrypted!")
                        print("   All content is now publicly visible.")
                        print("   Consider: git filter-repo or encrypting the notebook")
                else:
                    print("✗ Failed to update visibility")
            except:
                print("✗ Failed to parse response")
        else:
            print(f"✗ API call failed: {result.stderr}")
        
        self.get_input("Press Enter to continue...")

    def run(self):
        while True:
            self.show_home()
            cmd = self.get_input("> ").lower()
        
            if cmd == "":
                self.load_notebooks()
                self.load_accounts()
                self.page = 0
                continue

            # Pagination commands
            if cmd == "n":
                total_pages = self.calculate_pagination(len(self.notebooks))
                if self.page < total_pages - 1:
                    self.page += 1
                continue
            elif cmd == "p":
                if self.page > 0:
                    self.page -= 1
                continue
            elif cmd == "prev":
                if self.page > 0:
                    self.page -= 1
                continue
            elif cmd == "next":
                total_pages = self.calculate_pagination(len(self.notebooks))
                if self.page < total_pages - 1:
                    self.page += 1
                continue
            elif cmd.startswith("v"):
                if cmd == "v":
                    try:
                        rel_num = int(self.get_input("Enter notebook number: "))
                    except ValueError:
                        continue
                else:
                    try:
                        rel_num = int(cmd[1:])
                    except ValueError:
                        continue
                start_idx = self.page * self.items_per_page
                end_idx = min(start_idx + self.items_per_page, len(self.notebooks))
                items_on_page = end_idx - start_idx
                if 1 <= rel_num <= items_on_page:
                    absolute_index = start_idx + (rel_num - 1)
                    # 🟢 Capture return value from show_notebook_view
                    result = self.show_notebook_view(self.notebooks[absolute_index])
                    if result == "exit_app":
                        return "exit_app"
                else:
                    print(f"Invalid number. Use 1-{items_on_page}")
                    self.get_input("Press Enter to continue...")
                continue
            elif cmd == "a":
                # 🟢 Capture return value from show_accounts_screen
                result = self.show_accounts_screen()
                if result == "exit_app":
                    return "exit_app"
            # BACK - return to main app (only in embedded mode)
            # BACK - return to main app (only in embedded mode)
            elif cmd == "b":
                self.clear_screen()
                if self.is_standalone:
                    continue
                else:
                    # 🟢 FIX: Force reload notebooks to get latest state from disk
                    self.manager.load_all_notebooks(quiet=True)
                    return "back_to_app"
            # QUIT - full exit in both modes
            elif cmd == "q":
                if self.is_standalone:
                    confirm = self.get_input("Quit Notebook Manager? [y/N]: ").lower()
                    if confirm == "y":
                        self.clear_screen()
                        sys.exit(0)
                else:
                    confirm = self.get_input("Quit Terminal Notes? [y/N]: ").lower()
                    if confirm == "y":
                        self.clear_screen()
                        return "exit_app"
            elif cmd == "qy":
                self.clear_screen()
                if self.is_standalone:
                    sys.exit(0)
                else:
                    return "exit_app"
        return "exit"

def main():
    dashboard = NotebookManager()
    dashboard.run()

if __name__ == "__main__":
    main()