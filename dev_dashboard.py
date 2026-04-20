#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
"""
Terminal Notes Git Manager
Focused on project repository only - excludes notebooks_root
GitHub integration with token management
"""

import os
import sys
import subprocess
import json
import shutil
import getpass
import re
from pathlib import Path
from datetime import datetime
from crypto import Crypto
import socket
import select
import urllib.request
import urllib.error
import json
import time
from datetime import datetime


def github_api_request(url, token, timeout=10):
    """Make GitHub API request with timeout and retry"""
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'Terminal-Notes/1.0'
    }
    
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            
            # Create custom opener with timeout
            opener = urllib.request.build_opener()
            response = opener.open(req, timeout=timeout)
            data = json.loads(response.read().decode())
            
            return data, None
            
        except urllib.error.HTTPError as e:
            if e.code == 403 and 'rate limit' in str(e).lower():
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            return None, f"HTTP {e.code}: {e.reason}"
            
        except (urllib.error.URLError, socket.timeout) as e:
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))
                continue
            return None, f"Connection error: {str(e)}"
            
        except Exception as e:
            return None, str(e)
    
    return None, "Max retries exceeded"

class NetworkOptimizer:
    """Network optimization using only standard library"""
    
    # DNS cache
    _dns_cache = {}
    _dns_cache_time = {}
    _dns_ttl = 300  # 5 minutes
    
    @classmethod
    def resolve_dns(cls, hostname):
        """DNS lookup with caching"""
        current_time = time.time()
        
        # Check cache
        if hostname in cls._dns_cache:
            if current_time - cls._dns_cache_time.get(hostname, 0) < cls._dns_ttl:
                return cls._dns_cache[hostname]
        
        # Resolve DNS
        try:
            ip = socket.gethostbyname(hostname)
            cls._dns_cache[hostname] = ip
            cls._dns_cache_time[hostname] = current_time
            return ip
        except socket.gaierror:
            return hostname
    
    @classmethod
    def create_connection(cls, host, port, timeout=5):
        """Create socket connection with timeout"""
        try:
            # Resolve DNS first
            ip = cls.resolve_dns(host)
            
            # Create socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Connect with timeout using select
            start = time.time()
            sock.connect((ip, port))
            connect_time = time.time() - start
            
            return sock, connect_time
        except Exception:
            return None, None

    def github_api_request(url, token, timeout=10):
        """Make GitHub API request with timeout and retry"""
        import urllib.request
        import urllib.error
        import json
    
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'Terminal-Notes/1.0'
        }
    
        max_retries = 3
        retry_delay = 1
    
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(url, headers=headers)
            
                # Use socket-level timeout
                response = urllib.request.urlopen(req, timeout=timeout)
                data = json.loads(response.read().decode())
            
                return data, None
            
            except urllib.error.HTTPError as e:
                if e.code == 403 and 'rate limit' in str(e).lower():
                    # Rate limit hit, wait and retry
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (attempt + 1))
                        continue
                return None, f"HTTP {e.code}: {e.reason}"
            
            except (urllib.error.URLError, socket.timeout) as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                return None, f"Connection error: {str(e)}"
            
            except Exception as e:
                return None, str(e)
    
        return None, "Max retries exceeded"

    def git_clone_with_timeout(url, target_dir, timeout=30):
        """Clone git repository with timeout using subprocess"""
        import subprocess
        import shlex
    
        # Parse hostname for DNS cache
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.hostname:
            NetworkOptimizer.resolve_dns(parsed.hostname)
    
        # Build git command
        cmd = ['git', 'clone', '--depth', '1', '--single-branch', url, target_dir]
    
        try:
            # Use subprocess with timeout
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
        
            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, f"Clone timed out after {timeout} seconds"
        except Exception as e:
            return False, str(e)

    def check_internet_connection(timeout=3):
        """Check internet connection by connecting to reliable hosts"""
        hosts = [
            ('github.com', 443),
            ('api.github.com', 443),
            ('8.8.8.8', 53)  # Google DNS
        ]
    
        for host, port in hosts:
            sock, connect_time = NetworkOptimizer.create_connection(host, port, timeout)
            if sock:
                sock.close()
                return True, connect_time
    
        return False, None

class ProjectGitManager:
    def __init__(self):
        self.project_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_dir = os.path.join(self.project_dir, "config")
    
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
    
        self.config_file = os.path.join(self.config_dir, ".git_manager_config.json")
        self.token_file = os.path.join(self.config_dir, ".github_token.enc")
        self.load_config()
        
    def load_config(self):
        """Load or create manager config"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except:
                self.config = self.get_default_config()
        else:
            self.config = self.get_default_config()
        self.save_config()
    
    def get_default_config(self):
        """Get default configuration"""
        return {
            "github_username": "",
            "default_remote": "origin",
            "default_branch": "main",
            "last_sync": None,
            "excluded_folders": ["notebooks_root", "__pycache__", ".git"]
        }
    
    def save_config(self):
        """Save manager config"""
        with open(self.config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def save_token(self, token):
        try:
            from dev_vault import DevVault
            vault = DevVault(self.project_dir)
            username = self.config.get('github_username', '')
            
            if vault.store_token(token, username):
                self.config['token_exists'] = True
                self.save_config()
                print("✓ Token saved securely")
                return True
            else:
                print("✗ Failed to save token")
                return False
        except Exception as e:
            print(f"Error saving token: {e}")
            return False

    def get_token(self):
        try:
            from dev_vault import DevVault
            vault = DevVault(self.project_dir)
            token = vault.get_token()
            self.config['token_exists'] = token is not None
            self.save_config()
            return token
        except Exception as e:
            print(f"Error retrieving token: {e}")
            return None

    def delete_token(self):
        try:
            from dev_vault import DevVault
            vault = DevVault(self.project_dir)
            result = vault.delete_token()
            if result:
                self.config['token_exists'] = False
                self.save_config()
            return result
        except Exception as e:
            print(f"Error deleting token: {e}")
            return False
    
    def test_token_connection(self, token):
        """Test if token is valid using GitHub API"""
        import urllib.request
        import json
        
        # If we have username in config, use it for testing
        username = self.config.get('github_username', '')
        
        try:
            req = urllib.request.Request(
                "https://api.github.com/user",
                headers={'Authorization': f'token {token}'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                if 'login' in data:
                    # Update username if not set
                    if not self.config.get('github_username'):
                        self.config['github_username'] = data['login']
                        self.save_config()
                    return True
            return False
        except Exception:
            return False
    
    def prompt_for_token(self):
        """Prompt for GitHub token"""
        print("\nGitHub Personal Access Token (input hidden):")
        print("  Create one at: https://github.com/settings/tokens")
        print("  Required scopes: 'repo' (full) or 'public_repo'")
        print()
        token = getpass.getpass("Token: ")
        
        if token:
            # Test token
            if self.test_token_connection(token):
                save = input("Save token securely? [y/N]: ").lower()
                if save == 'y':
                    # Also get username for metadata
                    username = self.config.get('github_username', '')
                    if not username:
                        username = input("GitHub username (for metadata): ").strip()
                        if username:
                            self.config['github_username'] = username
                            self.save_config()
                    
                    if self.save_token(token):
                        print("✓ Token saved securely")
                return token
            else:
                print("✗ Token validation failed")
                return None
        return None
    
    def test_saved_token(self):
        """Test if saved token is valid"""
        self.clear_screen()
        self.print_header("Test Saved Token")
        
        token = self.get_token()
        
        if not token:
            print("\n⚠️  No token found.")
            manual_token = self.get_password("Enter token manually to test: ")
            if manual_token:
                token = manual_token
            else:
                print("\n❌ No token provided.")
                self.get_input("Press Enter to continue...")
                return
        
        username = self.config.get('github_username', '')
        if not username:
            username = self.get_input("GitHub username for testing: ")
        
        print("\nTesting token with timeout...")
        
        if self.test_token_connection(token):
            print(f"✓ Token valid")
            # Get user info from API
            import urllib.request
            import json
            try:
                req = urllib.request.Request(
                    "https://api.github.com/user",
                    headers={'Authorization': f'token {token}'}
                )
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                    print(f"  User: {data.get('login', username)}")
                    print(f"  Name: {data.get('name', 'N/A')}")
                    print(f"  Public repos: {data.get('public_repos', 0)}")
            except:
                pass
        else:
            print("✗ Token invalid or expired")
        
        self.get_input("Press Enter to continue...")
    
    def git_command_with_timeout(self, command, cwd=None, timeout=30):
        """Run git command with timeout"""
        import subprocess
        import shlex
    
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        except subprocess.TimeoutExpired:
            return {
                'success': False,
                'error': f"Command timed out after {timeout} seconds"
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def clear_screen(self):
        os.system('clear' if os.name == 'posix' else 'cls')
    
    def print_header(self, title):
        term_width = shutil.get_terminal_size().columns
        print('' * term_width)
        print(title.center(term_width))
        print('' * term_width)
        print()
    
    def print_separator(self):
        term_width = shutil.get_terminal_size().columns
        print("" * term_width)
    
    def get_input(self, prompt):
        return input(prompt).strip()
    
    def get_password(self, prompt):
        return getpass.getpass(prompt)
    
    def run_git_command(self, command, capture=True, timeout=30):
        """Run git command in project directory with timeout"""
        try:
            # Ensure we're in project dir
            os.chdir(self.project_dir)
        
            # Split command string into list if needed
            if isinstance(command, str):
                cmd_list = command.split()
            else:
                cmd_list = command
        
            result = subprocess.run(
                cmd_list,
                capture_output=capture,
                text=True,
                timeout=timeout
            )
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout if capture else '',
                'stderr': result.stderr if capture else ''
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': f'Command timed out after {timeout} seconds'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def is_git_repo(self):
        """Check if project is a git repository"""
        git_dir = os.path.join(self.project_dir, '.git')
        return os.path.exists(git_dir)
    
    def init_repo(self):
        """Initialize git repository if needed"""
        if not self.is_git_repo():
            print("\nInitializing git repository...")
            result = self.run_git_command("git init")
            if result['success']:
                print("✓ Git repository initialized")
                
                # Create .gitignore
                self.create_gitignore()
                return True
            else:
                print("✗ Failed to initialize")
                return False
        return True
    
    def create_gitignore(self):
        """Create .gitignore with excluded folders"""
        gitignore_path = os.path.join(self.project_dir, '.gitignore')
        
        if not os.path.exists(gitignore_path):
            with open(gitignore_path, 'w') as f:
                f.write("# Python\n")
                f.write("__pycache__/\n")
                f.write("*.pyc\n")
                f.write("*.pyo\n")
                f.write("*.pyd\n")
                f.write(".Python\n")
                f.write("env/\n")
                f.write("venv/\n")
                f.write("ENV/\n")
                f.write("env.bak/\n")
                f.write("venv.bak/\n")
                f.write("\n")
                f.write("# Notebooks root (excluded)\n")
                f.write("notebooks_root/\n")
                f.write("\n")
                f.write("# Token storage\n")
                f.write(".github_token.enc\n")
                f.write(".git_manager_config.json\n")
                f.write("\n")
                f.write("# Editor\n")
                f.write(".vscode/\n")
                f.write(".idea/\n")
                f.write("*.swp\n")
                f.write("*.swo\n")
                f.write("*~\n")
            
            print("✓ .gitignore created (notebooks_root excluded)")
            
            # Add .gitignore to git
            self.run_git_command("git add .gitignore")
    
    def get_repo_info(self):
        """Get comprehensive repository information"""
        info = {
            'is_git': self.is_git_repo(),
            'remotes': [],
            'branches': [],
            'current_branch': '',
            'status': '',
            'ahead': 0,
            'behind': 0,
            'uncommitted': False
        }
        
        if not info['is_git']:
            return info
        
        # Get remotes - REMOVE quiet=True
        result = self.run_git_command("git remote -v")
        if result['success'] and result['stdout']:
            for line in result['stdout'].strip().split('\n'):
                if '(fetch)' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        info['remotes'].append({
                            'name': parts[0],
                            'url': parts[1],
                            'type': 'fetch'
                        })
        
        # Get branches - REMOVE quiet=True
        result = self.run_git_command("git branch -a")
        if result['success'] and result['stdout']:
            for line in result['stdout'].split('\n'):
                line = line.strip()
                if line:
                    is_current = line.startswith('*')
                    branch = line[2:] if line.startswith('* ') else line
                    if not branch.startswith('remotes/'):
                        info['branches'].append({
                            'name': branch,
                            'current': is_current,
                            'local': True
                        })
        
        # Get current branch - REMOVE quiet=True
        result = self.run_git_command("git branch --show-current")
        if result['success']:
            info['current_branch'] = result['stdout'].strip()
        
        # Get status - REMOVE quiet=True
        result = self.run_git_command("git status -s")
        if result['success']:
            info['status'] = result['stdout']
            info['uncommitted'] = bool(result['stdout'].strip())
        
        # Get ahead/behind counts - REMOVE quiet=True from these too
        if info['current_branch']:
            result = self.run_git_command(f"git rev-list --count @{{u}}..HEAD 2>/dev/null")
            if result['success'] and result['stdout'].strip():
                info['ahead'] = int(result['stdout'].strip())
            
            result = self.run_git_command(f"git rev-list --count HEAD..@{{u}} 2>/dev/null")
            if result['success'] and result['stdout'].strip():
                info['behind'] = int(result['stdout'].strip())
        
        return info
    
    def commit_changes(self):
        """Step-by-step commit process"""
        import subprocess  # 🟢 ADD THIS AT THE TOP
        import shlex      # 🟢 ADD THIS IF NEEDED
        
        self.clear_screen()
        self.print_header("Commit Changes")
    
        info = self.get_repo_info()
    
        if not info['is_git']:
            print("Not a git repository. Initialize first.")
            input("\nPress Enter to continue...")
            return
    
        # Show current status
        print("Current status:")
        print("-" * 50)
        if info['status']:
            print(info['status'])
        else:
            print("No changes to commit.")
            input("\nPress Enter to continue...")
            return
    
        print()
    
        # Step 1: Choose files to stage
        print("Step 1: Stage files")
        print("Options:")
        print("  1. Stage all files (git add .)")
        print("  2. Stage specific files")
        print("  3. Stage interactively")
        print("  4. Skip to commit (use already staged)")
        print()
    
        choice = self.get_input("Choose [1-4]: ")
    
        if choice == "1":
            result = self.run_git_command("git add .")
            if result['success']:
                print("✓ All files staged")
            else:
                print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
                input("\nPress Enter to continue...")
                return
    
        elif choice == "2":
            result = self.run_git_command("git status -s")
            files = result['stdout'].strip().split('\n')
        
            if files and files[0]:
                print("\nFiles:")
                for i, line in enumerate(files, 1):
                    status = line[:2]
                    filepath = line[3:]
                    print(f"  [{i}] {status} {filepath}")
            
                print()
                file_nums = self.get_input("Enter file numbers to stage (comma-separated): ")
            
                try:
                    indices = [int(x.strip()) - 1 for x in file_nums.split(',')]
                    for idx in indices:
                        if 0 <= idx < len(files):
                            filepath = files[idx][3:]
                            self.run_git_command(f"git add \"{filepath}\"")
                            print(f"  Staged: {filepath}")
                except:
                    print("Invalid input")
    
        elif choice == "3":
            os.system("git add -i")
    
        elif choice == "4":
            print("Using currently staged files")
    
        staged = self.run_git_command("git diff --cached --name-only")
        if staged['success'] and staged['stdout']:
            print("\nStaged files:")
            for file in staged['stdout'].split('\n'):
                if file:
                    print(f"  {file}")
        else:
            print("\nNo files staged for commit.")
            unstage = self.get_input("Stage all files now? [y/N]: ").lower()
            if unstage == 'y':
                self.run_git_command("git add .")
                print("All files staged")
            else:
                return
    
        print()
    
        # Step 2: Write commit message
        print("Step 2: Write commit message")
        print("Options:")
        print("  1. Single line message (quick)")
        print("  2. Open editor for full commit message")
        print("  3. Use template")
        print()
    
        msg_choice = self.get_input("Choose [1-3]: ")
    
        commit_msg = ""
        commit_desc = ""
    
        if msg_choice == "1":
            commit_msg = self.get_input("Commit message: ")
            if not commit_msg:
                print("Commit message cannot be empty")
                return
            commit_desc = ""
    
        elif msg_choice == "2":
            print("\nOpening editor for commit message...")
        
            import tempfile
            import subprocess
        
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as f:
                f.write("\n")
                f.write("# Please enter the commit message for your changes.\n")
                f.write("# Lines starting with '#' will be ignored.\n")
                f.write("#\n")
            
                staged = self.run_git_command("git diff --cached --name-only")
                if staged['success'] and staged['stdout']:
                    f.write("# Staged files:\n")
                    for file in staged['stdout'].split('\n'):
                        if file:
                            f.write(f"#   {file}\n")
            
                f.write("#\n")
                f.write("# Changes to be committed:\n")
                stats = self.run_git_command("git diff --cached --stat")
                if stats['success'] and stats['stdout']:
                    for line in stats['stdout'].split('\n'):
                        if line:
                            f.write(f"# {line}\n")
            
                f.flush()
                temp_path = f.name
        
            editor = self.run_git_command("git var GIT_EDITOR")
            if editor['success'] and editor['stdout'].strip():
                git_editor = editor['stdout'].strip()
            else:
                git_editor = os.environ.get('EDITOR', 'nano')
        
            subprocess.call(f"{git_editor} {temp_path}", shell=True)
        
            with open(temp_path, 'r') as f:
                lines = f.readlines()
        
            os.unlink(temp_path)
        
            commit_lines = [line.rstrip() for line in lines if not line.startswith('#')]
            if not commit_lines or not any(commit_lines):
                print("Empty commit message. Commit cancelled.")
                return
        
            commit_msg = commit_lines[0].strip()
            commit_desc = '\n'.join([line for line in commit_lines[1:] if line.strip()])
    
        elif msg_choice == "3":
            print("\nCommon commit types:")
            print("  feat:     New feature")
            print("  fix:      Bug fix")
            print("  docs:     Documentation")
            print("  style:    Code style")
            print("  refactor: Code refactoring")
            print("  test:     Testing")
            print("  chore:    Maintenance")
            print()
            commit_msg = self.get_input("Commit message (type: description): ")
            if not commit_msg:
                return
            commit_desc = ""
    
        print("\n" + "=" * 50)
        print("Commit review:")
        print("-" * 50)
        print(f"Message: {commit_msg}")
        if commit_desc:
            print(f"Description:\n{commit_desc}")
        print("-" * 50)
    
        stats = self.run_git_command("git diff --cached --stat")
        if stats['success'] and stats['stdout']:
            print(stats['stdout'])
    
        print()
        confirm = input("Proceed with commit? [y/N]: ").strip().lower()
    
        if confirm == 'y':
            # Properly escape and quote the commit message
            if commit_desc:
                # 🟢 FIX: Build command as list to avoid shell parsing issues
                import shlex
                cmd_parts = ["git", "commit", "-m", commit_msg]
                for line in commit_desc.split('\n'):
                    if line.strip():
                        cmd_parts.extend(["-m", line])
    
                # Use subprocess with list format instead of shell string
                print(f"\nRunning: git commit with {len(cmd_parts)-2} message parts")
                result = subprocess.run(cmd_parts, cwd=self.project_dir, capture_output=True, text=True)
            else:
                # Single message - still use list format for consistency
                cmd_parts = ["git", "commit", "-m", commit_msg]
                result = subprocess.run(cmd_parts, cwd=self.project_dir, capture_output=True, text=True)
        
            if result.returncode == 0:
                print("\n✓ Commit successful!")
                if result.stdout:
                    print(result.stdout)
            else:
                print("\n✗ Commit failed:")
                print(result.stderr)

        else:
            print("Commit cancelled")
    
        input("\nPress Enter to continue...")
    
    
    def show_commit_template(self):
        """Show commit message template"""
        template = """
# Commit Message Guidelines
# 
# Format: <type>: <description>
# 
# Types:
#   feat:     A new feature
#   fix:      A bug fix
#   docs:     Documentation only changes
#   style:    Changes that do not affect the meaning of the code
#   refactor: A code change that neither fixes a bug nor adds a feature
#   test:     Adding missing tests or correcting existing tests
#   chore:    Changes to the build process or auxiliary tools
# 
# Example:
#   feat: add login functionality
# 
#   - Implement OAuth2 authentication
#   - Add user session management
#   - Create login form UI
"""
        print(template)
    
    def view_remotes(self):
        """View and manage remotes"""
        while True:
            self.clear_screen()
            info = self.get_repo_info()
            self.print_header("Remote Configuration")
            
            if not info['is_git']:
                print("Not a git repository. Initialize first.")
                print()
                print("Options:")
                print("  [1] Initialize repository")
                print("  [2] Back")
                print()
                
                choice = self.get_input("Select option: ")
                if choice == "1":
                    self.init_repo()
                elif choice == "2":
                    break
                continue
            
            if info['remotes']:
                print("Current remotes:")
                print()
                for i, remote in enumerate(info['remotes'], 1):
                    if remote['type'] == 'fetch':
                        print(f"  Remote: {remote['name']}")
                        print(f"  URL:    {remote['url']}")
                        print()
            else:
                print("No remotes configured.")
                print()
            
            print("Options:")
            print("  [1] Add GitHub remote")
            print("  [2] Add custom remote")
            if info['remotes']:
                print("  [3] Modify remote URL")
                print("  [4] Delete remote")
                print("  [5] Test connection")
                print("  [6] Back")
            else:
                print("  [3] Back")
            print()
            
            choice = self.get_input("Select option: ")
            
            if choice == "1":
                self.add_github_remote()
            elif choice == "2":
                self.add_custom_remote()
            elif choice == "3" and info['remotes']:
                self.modify_remote(info['remotes'])
            elif choice == "4" and info['remotes']:
                self.delete_remote(info['remotes'])
            elif choice == "5" and info['remotes']:
                self.test_remote(info['remotes'])
            elif choice in ["3", "6"]:
                break
    
    def add_github_remote(self):
        """Add GitHub remote with username"""
        self.clear_screen()
        self.print_header("Add GitHub Remote")
        
        # Get GitHub username
        username = self.config.get('github_username', '')
        if not username:
            username = self.get_input("GitHub username: ")
            if username:
                self.config['github_username'] = username
                self.save_config()
        
        # Get repository name - clean any URL parts
        default_repo = os.path.basename(self.project_dir).replace(' ', '_').lower()
        repo_input = self.get_input(f"Repository name [{default_repo}]: ") or default_repo
        
        # Clean the input - extract just the repo name
        repo_name = repo_input
        if 'github.com/' in repo_input:
            # Extract after the last github.com/
            repo_name = repo_input.split('github.com/')[-1]
        if '/' in repo_name:
            # Take just the last part after any slash
            repo_name = repo_name.split('/')[-1]
        # Remove .git extension if present
        repo_name = repo_name.replace('.git', '')
        
        # Choose protocol
        print("\nProtocol:")
        print("  1. HTTPS (with token)")
        print("  2. SSH (with key)")
        print()
        proto_choice = self.get_input("Choose [1/2]: ")
        
        use_ssh = (proto_choice == "2")
        
        # Get remote name
        remote_name = self.get_input(f"Remote name [origin]: ") or "origin"
        
        # Clean username and repo
        clean_username = username.split('/')[-1] if '/' in username else username
        clean_repo = repo_name.split('/')[-1] if '/' in repo_name else repo_name
        clean_repo = clean_repo.replace('.git', '')
        
        # Construct URL
        if use_ssh:
            remote_url = f"git@github.com:{clean_username}/{clean_repo}.git"
            print(f"\nRemote URL (SSH): {remote_url}")
        else:
            remote_url = f"https://github.com/{clean_username}/{clean_repo}.git"
            print(f"\nRemote URL (HTTPS): {remote_url}")
        
        confirm = self.get_input("Add this remote? [y/N]: ").lower()
        if confirm != 'y':
            return
        
        # Check if remote exists
        result = self.run_git_command(f"git remote get-url {remote_name} 2>/dev/null")
        if result['success']:
            overwrite = self.get_input(f"Remote '{remote_name}' exists. Overwrite? [y/N]: ").lower()
            if overwrite == 'y':
                self.run_git_command(f"git remote remove {remote_name}")
            else:
                return
        
        # Add remote
        result = self.run_git_command(f"git remote add {remote_name} {remote_url}")
        if result['success']:
            print(f"✓ Remote '{remote_name}' added successfully")
            
            # Ask about token for HTTPS
            if not use_ssh:
                if not self.get_token():
                    print("\nHTTPS remote requires token for authentication.")
                    add_token = self.get_input("Add token now? [y/N]: ").lower()
                    if add_token == 'y':
                        self.prompt_for_token()
        else:
            print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        
        input("\nPress Enter to continue...")
    
    def push_to_remote(self):
        """Push changes to remote with timeout and non-interactive mode"""
        self.clear_screen()
        self.print_header("Push to Remote")
    
        # Check if there are changes to push
        status = self.run_git_command("git status -s")
        if status['success'] and status['stdout'].strip():
            print("Uncommitted changes detected:")
            print(status['stdout'])
            print("\nPlease commit changes before pushing.")
            self.get_input("Press Enter to continue...")
            return
    
        # Check if remote exists
        remote_check = self.run_git_command("git remote -v")
        if not remote_check['success'] or not remote_check['stdout'].strip():
            print("No remote configured. Please add a remote first.")
            self.get_input("Press Enter to continue...")
            return
    
        # Get current branch
        branch_result = self.run_git_command("git branch --show-current")
        current_branch = branch_result['stdout'].strip() if branch_result['success'] else "main"
    
        # Get remote URL
        remote_url_result = self.run_git_command("git remote get-url origin")
        if not remote_url_result['success']:
            print("Could not get remote URL")
            self.get_input("Press Enter to continue...")
            return
    
        remote_url = remote_url_result['stdout'].strip()
    
        # Check if it's a GitHub URL and we have a token
        token = self.get_token()
        username = self.config.get('github_username', '')
    
        push_url = remote_url
        if token and username and 'github.com' in remote_url:
            # Inject token into URL for authentication
            push_url = remote_url.replace('https://', f'https://{username}:{token}@')
            print(f"Pushing to: {remote_url.replace('https://', 'https://' + username + ':********@')}")
        else:
            print(f"Pushing to: {remote_url}")
    
        print()
    
        # Check what would be pushed
        ahead_result = self.run_git_command(f"git rev-list --count HEAD --not --remotes")
        if ahead_result['success'] and ahead_result['stdout'].strip():
            commits_ahead = int(ahead_result['stdout'].strip())
            if commits_ahead == 0:
                print("No commits to push.")
                self.get_input("Press Enter to continue...")
                return
            print(f"Commits to push: {commits_ahead}")
        else:
            print("Could not determine commits ahead")
    
        print("\nPushing...")
    
        # Use subprocess with timeout and non-interactive mode
        import subprocess
        import select
        import sys
    
        try:
            # Set up the push command with non-interactive flags
            cmd = [
                "git", 
                "push",
                "-u", 
                "origin", 
                current_branch,
                "--quiet"  # Suppress progress output that might cause hanging
            ]
        
            # Use environment to prevent git from asking for credentials
            env = os.environ.copy()
            env.update({
                'GIT_ASKPASS': 'echo',  # Non-interactive
                'GIT_TERMINAL_PROMPT': '0'  # Disable terminal prompt
            })
        
            # Use subprocess with timeout and pipe output
            process = subprocess.Popen(
                cmd,
                cwd=self.project_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        
            # Wait for process with timeout
            timeout = 60  # 60 seconds timeout
            start_time = time.time()
        
            stdout_data = []
            stderr_data = []
        
            while True:
                # Check if process has ended
                return_code = process.poll()
                if return_code is not None:
                    # Process finished
                    stdout, stderr = process.communicate()
                    if stdout:
                        stdout_data.append(stdout)
                    if stderr:
                        stderr_data.append(stderr)
                    break
            
                # Check timeout
                if time.time() - start_time > timeout:
                    process.kill()
                    print(f"\n✗ Push timed out after {timeout} seconds")
                    self.get_input("Press Enter to continue...")
                    return
            
                # Small sleep to prevent CPU spinning
                time.sleep(0.1)
        
            # Check result
            stdout = ''.join(stdout_data)
            stderr = ''.join(stderr_data)
        
            if return_code == 0:
                print("\n✓ Push successful!")
                # Update last push time in config
                self.config['last_sync'] = datetime.now().isoformat()
                self.save_config()
            else:
                print("\n✗ Push failed:")
                if stderr:
                    print(stderr)
                else:
                    print("Unknown error")
                
        except Exception as e:
            print(f"\n✗ Push error: {e}")
    
        self.get_input("Press Enter to continue...")
    
    def add_custom_remote(self):
        """Add custom remote"""
        self.clear_screen()
        self.print_header("Add Custom Remote")
        
        name = self.get_input("Remote name [origin]: ") or "origin"
        url = self.get_input("Remote URL: ")
        
        if not url:
            print("URL cannot be empty.")
            input("\nPress Enter to continue...")
            return
        
        # Check if remote exists
        result = self.run_git_command(f"git remote get-url {name} 2>/dev/null")
        if result['success']:
            overwrite = self.get_input(f"Remote '{name}' exists. Overwrite? [y/N]: ").lower()
            if overwrite == 'y':
                self.run_git_command(f"git remote remove {name}")
            else:
                return
        
        result = self.run_git_command(f"git remote add {name} {url}")
        if result['success']:
            print(f"✓ Remote '{name}' added successfully")
        else:
            print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        
        input("\nPress Enter to continue...")
    
    def modify_remote(self, remotes):
        """Modify remote URL"""
        self.clear_screen()
        self.print_header("Modify Remote")
        
        # Get unique remote names
        remote_names = list(set([r['name'] for r in remotes]))
        
        print("Select remote to modify:")
        for i, name in enumerate(remote_names, 1):
            print(f"  [{i}] {name}")
        
        print()
        choice = self.get_input("Enter number: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(remote_names):
                name = remote_names[idx]
                
                # Get current URL
                result = self.run_git_command(f"git remote get-url {name}")
                if result['success']:
                    current_url = result['stdout'].strip()
                    print(f"\nCurrent URL: {current_url}")
                    
                    new_url = self.get_input("New URL: ")
                    if new_url:
                        result = self.run_git_command(f"git remote set-url {name} {new_url}")
                        if result['success']:
                            print(f"✓ Remote URL updated")
                        else:
                            print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        except:
            pass
        
        input("\nPress Enter to continue...")
    
    def delete_remote(self, remotes):
        """Delete remote"""
        self.clear_screen()
        self.print_header("Delete Remote")
        
        # Get unique remote names
        remote_names = list(set([r['name'] for r in remotes]))
        
        print("Select remote to delete:")
        for i, name in enumerate(remote_names, 1):
            print(f"  [{i}] {name}")
        
        print()
        choice = self.get_input("Enter number: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(remote_names):
                name = remote_names[idx]
                confirm = self.get_input(f"Delete remote '{name}'? [y/N]: ").lower()
                if confirm == 'y':
                    result = self.run_git_command(f"git remote remove {name}")
                    if result['success']:
                        print(f"✓ Remote '{name}' deleted")
                    else:
                        print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        except:
            pass
        
        input("\nPress Enter to continue...")
        
    def test_remote(self, remotes):
        """Test connection to remote using stored token"""
        self.clear_screen()
        self.print_header("Test Remote Connection")
        
        # Get unique remote names
        remote_names = list(set([r['name'] for r in remotes]))
        
        print("Select remote to test:")
        for i, name in enumerate(remote_names, 1):
            print(f"  [{i}] {name}")
        
        print()
        choice = self.get_input("Enter number: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(remote_names):
                name = remote_names[idx]
                
                # Get remote URL
                url_result = self.run_git_command(f"git remote get-url {name}")
                if not url_result['success']:
                    print("Could not get remote URL")
                    input("\nPress Enter to continue...")
                    return
                
                remote_url = url_result['stdout'].strip()
                print(f"\nRemote URL: {remote_url}")
                
                # Get username from config
                username = self.config.get('github_username', '')
                if not username:
                    print("\nNo GitHub username configured.")
                    print("Please set up username in Settings first.")
                    input("\nPress Enter to continue...")
                    return
                
                # Get token from Crypto
                token = self.get_token()
                if not token:
                    print("\nNo valid token found.")
                    print("Please set up token in Settings → Manage tokens first.")
                    input("\nPress Enter to continue...")
                    return
                
                print(f"\nTesting connection to '{name}'...")
                
                # Handle HTTPS with token
                if 'https://' in remote_url:
                    if 'github.com/' in remote_url:
                        # Extract repo path correctly
                        repo_path = remote_url.split('github.com/')[-1]
                        repo_path = repo_path.strip('/')
                        repo_path = repo_path.replace('.git', '')
                        
                        print(f"Repository path: {repo_path}")
                        
                        # Test with GitHub API
                        import subprocess
                        import json
                        
                        print("\nTesting via GitHub API...")
                        api_cmd = f"curl -s -H 'Authorization: token {token}' https://api.github.com/repos/{repo_path}"
                        api_result = subprocess.run(api_cmd, shell=True, capture_output=True, text=True)
                        
                        if api_result.returncode == 0:
                            try:
                                data = json.loads(api_result.stdout)
                                if 'id' in data:
                                    print(f"✓ API connection successful")
                                    print(f"  Repository: {data.get('full_name')}")
                                    print(f"  Private: {data.get('private')}")
                                    print(f"  Default branch: {data.get('default_branch')}")
                                    
                                    # Check permissions
                                    if 'permissions' in data:
                                        perms = data['permissions']
                                        print(f"  Push access: {'✅' if perms.get('push') else '❌'}")
                                        if not perms.get('push'):
                                            print("\n⚠ Token does NOT have push access to this repository.")
                                            print("   To push, you need a token with:")
                                            print("   - 'repo' scope for private repos")
                                            print("   - 'public_repo' scope for public repos")
                                    else:
                                        print("  Push access: Unknown (API didn't return permissions)")
                                elif 'message' in data:
                                    if data['message'] == 'Not Found':
                                        print(f"✗ Repository not found: {repo_path}")
                                        print("\nPossible causes:")
                                        print(f"1. Repository doesn't exist at: https://github.com/{repo_path}")
                                        print("2. Token doesn't have access to this repository")
                                        print("3. Repository is private and token lacks 'repo' scope")
                                    else:
                                        print(f"✗ API error: {data['message']}")
                            except:
                                print("✗ Could not parse API response")
                        else:
                            print("✗ API request failed")
                        
                        # Try git ls-remote with auth (read-only test)
                        print("\nTesting git ls-remote (read-only)...")
                        auth_url = f"https://{username}:{token}@github.com/{repo_path}.git"
                        git_cmd = f"git ls-remote {auth_url} HEAD"
                        git_result = self.run_git_command(git_cmd)
                        
                        if git_result['success']:
                            print("✓ Git read access successful")
                            if git_result['stdout']:
                                print(f"  HEAD: {git_result['stdout'][:40]}...")
                            
                            # Try a real push test (optional)
                            print("\nTesting git push (write access)...")
                            test_cmd = f"git push --dry-run {auth_url} HEAD"
                            push_result = self.run_git_command(test_cmd)
                            
                            if push_result['success']:
                                print("✓ Git write access successful")
                            else:
                                error = push_result.get('stderr', '')
                                if '403' in error:
                                    print("✗ Git write access failed - token lacks push permissions")
                                    print("\n🔧 To fix: Generate new token with:")
                                    print("   - 'repo' scope (for private repos)")
                                    print("   - 'public_repo' scope (for public repos)")
                                else:
                                    print(f"✗ Git write access failed: {error[:200]}")
                        else:
                            print("✗ Git read access failed")
                            error = git_result.get('stderr', '')
                            if '403' in error:
                                print("\n🔧 Token lacks access. Generate new token with:")
                                print("   - 'repo' scope for private repos")
                                print("   - 'public_repo' scope for public repos")
                            elif '404' in error:
                                print(f"\n🔧 Repository '{repo_path}' not found")
                    else:
                        print("Not a GitHub URL, cannot test with token")
                        git_result = self.run_git_command(f"git ls-remote {name} HEAD")
                        if git_result['success']:
                            print("✓ Connection successful")
                        else:
                            print("✗ Connection failed")
                else:
                    # SSH - test normally
                    print("Testing SSH connection...")
                    git_result = self.run_git_command(f"git ls-remote {name} HEAD")
                    if git_result['success']:
                        print("✓ Connection successful")
                    else:
                        print("✗ Connection failed:")
                        print(git_result.get('stderr', 'Unknown error'))
                        
        except Exception as e:
            print(f"Error: {e}")
        
        input("\nPress Enter to continue...")
    def manage_branches(self):
        """View and manage branches"""
        while True:
            self.clear_screen()
            info = self.get_repo_info()
            self.print_header("Branch Management")
            
            if not info['is_git']:
                print("Not a git repository. Initialize first.")
                print()
                print("Options:")
                print("  [1] Initialize repository")
                print("  [2] Back")
                print()
                
                choice = self.get_input("Select option: ")
                if choice == "1":
                    self.init_repo()
                elif choice == "2":
                    break
                continue
            
            print(f"Current branch: {info['current_branch']}")
            if info['ahead'] > 0 or info['behind'] > 0:
                print(f"Sync: {info['ahead']} ahead, {info['behind']} behind")
            print()
            
            if info['branches']:
                print("Local branches:")
                for i, branch in enumerate(info['branches'], 1):
                    marker = '*' if branch['current'] else ' '
                    print(f"  [{i}] {marker} {branch['name']}")
            else:
                print("No branches found.")
            
            print()
            print("Options:")
            print("  [1] Switch branch")
            print("  [2] Create branch")
            print("  [3] Delete branch")
            print("  [4] Merge branch")
            print("  [5] Pull from remote")
            print("  [6] Push to remote")
            print("  [7] Back")
            print()
            
            choice = self.get_input("Select option: ")
            
            if choice == "1":
                self.switch_branch(info['branches'])
            elif choice == "2":
                self.create_branch()
            elif choice == "3":
                self.delete_branch(info['branches'])
            elif choice == "4":
                self.merge_branch(info['branches'])
            elif choice == "5":
                self.pull_branch(info)
            elif choice == "6":
                self.push_branch(info)
            elif choice == "7":
                break
    
    def switch_branch(self, branches):
        """Switch to a different branch"""
        self.clear_screen()
        self.print_header("Switch Branch")
        
        local_branches = [b for b in branches if b['local']]
        if not local_branches:
            print("No local branches available.")
            input("\nPress Enter to continue...")
            return
        
        print("Select branch to switch to:")
        for i, branch in enumerate(local_branches, 1):
            print(f"  [{i}] {branch['name']}")
        
        print()
        choice = self.get_input("Enter number: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(local_branches):
                branch = local_branches[idx]['name']
                
                # Check for uncommitted changes
                info = self.get_repo_info()
                if info['uncommitted']:
                    print("\nUncommitted changes detected:")
                    print(info['status'])
                    proceed = self.get_input("Switch anyway? [y/N]: ").lower()
                    if proceed != 'y':
                        return
                
                result = self.run_git_command(f"git checkout {branch}")
                if result['success']:
                    print(f"✓ Switched to '{branch}'")
                else:
                    print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        except:
            pass
        
        input("\nPress Enter to continue...")
    
    def create_branch(self):
        """Create a new branch"""
        self.clear_screen()
        self.print_header("Create Branch")
        
        name = self.get_input("New branch name: ")
        if not name:
            return
        
        # Check if branch exists
        result = self.run_git_command(f"git show-ref --verify refs/heads/{name}")
        if result['success']:
            print(f"Branch '{name}' already exists.")
            input("\nPress Enter to continue...")
            return
        
        result = self.run_git_command(f"git branch {name}")
        if result['success']:
            print(f"✓ Branch '{name}' created")
            
            switch = self.get_input("Switch to new branch? [y/N]: ").lower()
            if switch == 'y':
                self.run_git_command(f"git checkout {name}")
        else:
            print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        
        input("\nPress Enter to continue...")
    
    def delete_branch(self, branches):
        """Delete a branch"""
        self.clear_screen()
        self.print_header("Delete Branch")
        
        local_branches = [b for b in branches if b['local'] and not b['current']]
        if not local_branches:
            print("No deletable branches (cannot delete current branch).")
            input("\nPress Enter to continue...")
            return
        
        print("Select branch to delete:")
        for i, branch in enumerate(local_branches, 1):
            print(f"  [{i}] {branch['name']}")
        
        print()
        choice = self.get_input("Enter number: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(local_branches):
                branch = local_branches[idx]['name']
                
                # Check if merged
                result = self.run_git_command(f"git branch --merged | grep {branch}")
                is_merged = result['success']
                
                if is_merged:
                    result = self.run_git_command(f"git branch -d {branch}")
                else:
                    print(f"Warning: Branch '{branch}' is not fully merged")
                    force = self.get_input("Delete anyway? [y/N]: ").lower()
                    if force != 'y':
                        return
                    result = self.run_git_command(f"git branch -D {branch}")
                
                if result['success']:
                    print(f"✓ Branch '{branch}' deleted")
                else:
                    print(f"✗ Failed: {result.get('stderr', 'Unknown error')}")
        except:
            pass
        
        input("\nPress Enter to continue...")
    
    def merge_branch(self, branches):
        """Merge a branch into current with optional version tagging"""
        self.clear_screen()
        self.print_header("Merge Branch")
    
        info = self.get_repo_info()
        other_branches = [b for b in branches if b['local'] and b['name'] != info['current_branch']]
    
        if not other_branches:
            print("No other branches to merge.")
            self.get_input("Press Enter to continue...")
            return
    
        print(f"Current branch: {info['current_branch']}")
        print("\nSelect branch to merge:")
        for i, branch in enumerate(other_branches, 1):
            print(f"  [{i}] {branch['name']}")
    
        print()
        choice = self.get_input("Enter number: ")
    
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(other_branches):
                branch = other_branches[idx]['name']
            
                # Check if merging into master
                is_merging_into_master = info['current_branch'] == 'master' or info['current_branch'] == 'main'
            
                if info['uncommitted']:
                    print("\nUncommitted changes detected:")
                    print(info['status'])
                    proceed = self.get_input("Merge anyway? [y/N]: ").lower()
                    if proceed != 'y':
                        return
            
                # Perform the merge
                print(f"\nMerging {branch} into {info['current_branch']}...")
                result = self.run_git_command(f"git merge {branch}")
            
                if result['success']:
                    print(f"✓ Merged '{branch}' into '{info['current_branch']}'")
                
                    # 🟢 Version tagging for master/main merges
                    if is_merging_into_master:
                        self._handle_version_tagging(branch)
                
                else:
                    print(f"✗ Merge failed: {result.get('stderr', 'Unknown error')}")
                
                    if 'conflict' in result.get('stderr', '').lower():
                        print("\nMerge conflicts detected. Resolve conflicts and commit.")
        except:
            pass
    
        self.get_input("Press Enter to continue...")

    def _handle_version_tagging(self, merged_branch):
        """Handle version tagging after merge into master"""
        print("\n" + "="*50)
        print("Version Tagging")
        print("="*50)

        # Get all tags and find the latest version
        tags_result = self.run_git_command("git tag -l")
        latest_tag = "v0.0.0"
        existing_tags = []
    
        if tags_result['success'] and tags_result['stdout'].strip():
            all_tags = tags_result['stdout'].strip().split('\n')
            # Filter for valid semver tags
            valid_tags = []
            for tag in all_tags:
                tag = tag.strip()
                if tag and re.match(r'^v\d+\.\d+\.\d+$', tag):
                    valid_tags.append(tag)
        
            if valid_tags:
                # Sort by version number (convert to tuples for proper comparison)
                def version_key(t):
                    match = re.search(r'v(\d+)\.(\d+)\.(\d+)', t)
                    if match:
                        return tuple(map(int, match.groups()))
                    return (0, 0, 0)
            
                valid_tags.sort(key=version_key, reverse=True)
                latest_tag = valid_tags[0]
                existing_tags = valid_tags

        print(f"Latest version: {latest_tag}")
        print("\nSelect version increment:")
        print("  [1] Patch (v1.0.0 → v1.0.1) - bug fixes")
        print("  [2] Minor (v1.0.0 → v1.1.0) - new features")
        print("  [3] Major (v1.0.0 → v2.0.0) - breaking changes")
        print("  [4] Custom version")
        print("  [5] Skip tagging")
        print()

        choice = self.get_input("Choose [1-5]: ").strip()

        if choice == "5":
            print("Skipping version tag.")
            return

        # Parse current version
        import re
        version_match = re.search(r'v(\d+)\.(\d+)\.(\d+)', latest_tag)
        if version_match:
            major, minor, patch = map(int, version_match.groups())
        else:
            major, minor, patch = 0, 0, 0

        new_version = latest_tag

        if choice == "1":
            patch += 1
            new_version = f"v{major}.{minor}.{patch}"
        elif choice == "2":
            minor += 1
            patch = 0
            new_version = f"v{major}.{minor}.{patch}"
        elif choice == "3":
            major += 1
            minor = 0
            patch = 0
            new_version = f"v{major}.{minor}.{patch}"
        elif choice == "4":
            new_version = self.get_input("Enter custom version (e.g., v2.5.0): ").strip()
            if not new_version:
                print("No version entered. Skipping tag.")
                return
            if not new_version.startswith('v'):
                new_version = 'v' + new_version

        # Check if tag already exists and suggest next version
        if new_version in existing_tags:
            print(f"\n⚠ Tag '{new_version}' already exists!")
        
            # Parse the attempted version
            version_match = re.search(r'v(\d+)\.(\d+)\.(\d+)', new_version)
            if version_match:
                major, minor, patch = map(int, version_match.groups())
            
                print("\nSuggested next versions:")
                suggestions = []
            
                # Try each increment until we find one that doesn't exist
                for inc in range(1, 10):  # Try up to 9 increments
                    test_patch = f"v{major}.{minor}.{patch + inc}"
                    if test_patch not in existing_tags:
                        suggestions.append(f"  [p{inc}] Patch: {test_patch}")
                        break
            
                test_minor = f"v{major}.{minor + 1}.0"
                if test_minor not in existing_tags:
                    suggestions.append(f"  [m] Minor: {test_minor}")
            
                test_major = f"v{major + 1}.0.0"
                if test_major not in existing_tags:
                    suggestions.append(f"  [M] Major: {test_major}")
            
                for s in suggestions:
                    print(s)
                print("  [c] Enter custom version")
                print()
            
                suggest_choice = self.get_input("Choose [p1/p2/m/M/c]: ").lower().strip()
            
                if suggest_choice.startswith('p'):
                    try:
                        inc = int(suggest_choice[1:]) if len(suggest_choice) > 1 else 1
                        new_version = f"v{major}.{minor}.{patch + inc}"
                    except:
                        new_version = f"v{major}.{minor}.{patch + 1}"
                elif suggest_choice == 'm':
                    new_version = f"v{major}.{minor + 1}.0"
                elif suggest_choice == 'M':
                    new_version = f"v{major + 1}.0.0"
                elif suggest_choice == 'c':
                    new_version = self.get_input("Enter custom version: ").strip()
                    if not new_version.startswith('v'):
                        new_version = 'v' + new_version
                else:
                    print("Invalid choice. Skipping tag.")
                    return

        print(f"New version: {new_version}")

        # Create annotated tag
        tag_message = f"Release {new_version}\n\nMerged from branch: {merged_branch}"

        import subprocess
        tag_result = subprocess.run(
            ['git', 'tag', '-a', new_version, '-m', tag_message],
            cwd=self.project_dir,
            capture_output=True,
            text=True
        )

        if tag_result.returncode == 0:
            print(f"✓ Created tag: {new_version} (local only)")
            print("  Use normal push operation to push tags later")
        else:
            if "already exists" in tag_result.stderr:
                print(f"✗ Tag '{new_version}' already exists.")
            else:
                print(f"✗ Failed to create tag: {tag_result.stderr}")
    
    def check_remote_connectivity(self, remote='origin'):
        """Check if remote is reachable using stored credentials"""
        import socket
        import subprocess
    
        # Get authenticated URL
        auth_url, public_url = self.get_authenticated_remote_url(remote)
        if not auth_url:
            return {'success': False, 'error': 'Could not get remote URL'}
    
        # Extract hostname
        from urllib.parse import urlparse
        try:
            parsed = urlparse(auth_url if 'https://' in auth_url else public_url)
            host = parsed.hostname or 'github.com'
        except:
            host = 'github.com'
    
        # Test DNS resolution
        try:
            socket.gethostbyname(host)
        except socket.gaierror:
            return {'success': False, 'error': f'Could not resolve {host}'}
    
        # Test connectivity with git ls-remote using authenticated URL
        try:
            if auth_url != public_url:
                # Use authenticated URL for testing
                cmd = ['git', 'ls-remote', '--heads', auth_url]
            else:
                cmd = ['git', 'ls-remote', '--heads', remote]
        
            result = subprocess.run(
                cmd,
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return {'success': True}
            else:
                return {'success': False, 'error': result.stderr[:100]}
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Connection timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_authenticated_remote_url(self, remote='origin'):
        """Get remote URL with authentication token injected"""
        # Get remote URL
        url_result = self.run_git_command(f"git remote get-url {remote}")
        if not url_result['success']:
            return None, None
    
        remote_url = url_result['stdout'].strip()
    
        # Get token from config
        token = self.get_token()
        username = self.config.get('github_username', '')
    
        # Inject token if it's a GitHub URL
        if token and username and 'github.com' in remote_url:
            auth_url = remote_url.replace('https://', f'https://{username}:{token}@')
            return auth_url, remote_url
        else:
            return remote_url, remote_url
    
    def pull_branch(self, info):
        """Pull from remote using stored token automatically"""
        self.clear_screen()
        self.print_header("Pull from Remote")
        
        if not info['remotes']:
            print("No remotes configured.")
            input("\nPress Enter to continue...")
            return
        
        # Get remote names
        remote_names = list(set([r['name'] for r in info['remotes']]))
        
        if len(remote_names) > 1:
            print("Select remote:")
            for i, name in enumerate(remote_names, 1):
                print(f"  [{i}] {name}")
            print()
            remote_choice = self.get_input("Enter number: ")
            
            try:
                idx = int(remote_choice) - 1
                remote = remote_names[idx] if 0 <= idx < len(remote_names) else remote_names[0]
            except:
                remote = remote_names[0]
        else:
            remote = remote_names[0]
        
        # Get current remote URL
        remote_url_result = self.run_git_command(f"git remote get-url {remote}")
        remote_url = remote_url_result['stdout'].strip() if remote_url_result['success'] else ""
        
        # Get username and token
        username = self.config.get('github_username', '')
        token = None
        
        # Try to get token from encrypted storage
        if self.get_token():
            from crypto import Crypto
            try:
                token_file = os.path.join(self.project_dir, ".github_token.enc")
                with open(token_file, 'rb') as f:
                    encrypted = f.read()
                
                crypto = Crypto(self.project_dir, "github_token")
                token = crypto.decrypt(encrypted)
            except:
                print("⚠ Could not auto-decrypt token")
                input("\nPress Enter to continue...")
                return
        
        # Check for uncommitted changes
        if info['uncommitted']:
            print("\nUncommitted changes detected:")
            print(info['status'])
            print("\nOptions:")
            print("  1. Stash changes and pull")
            print("  2. Commit changes first")
            print("  3. Cancel")
            print()
            
            choice = self.get_input("Choose [1-3]: ")
            
            if choice == "1":
                stash_result = self.run_git_command("git stash")
                if stash_result['success']:
                    print("Changes stashed")
                else:
                    print("Failed to stash changes")
                    return
            elif choice == "2":
                print("\nPlease commit changes manually and try again")
                return
            else:
                return
        
        pull_cmd = f"git pull {remote} {info['current_branch']}"
        
        # If using token, inject it into the command
        if token and username and 'https://' in remote_url:
            if 'github.com/' in remote_url:
                repo_path = remote_url.split('github.com/')[-1]
                auth_url = f"https://{username}:{token}@github.com/{repo_path}"
                pull_cmd = f"git pull {auth_url} {info['current_branch']}"
                print("🔑 Using stored credentials")
        
        print(f"\nPulling from {remote}...")
        result = self.run_git_command(pull_cmd)
        
        if result['success']:
            print("✓ Pull successful")
            if result['stdout']:
                print(result['stdout'])
        else:
            print("✗ Pull failed:")
            print(result.get('stderr', 'Unknown error'))
        
        # Pop stash if we stashed
        if 'choice' in locals() and choice == "1":
            pop_result = self.run_git_command("git stash pop")
            if pop_result['success']:
                print("Stashed changes restored")
        
        input("\nPress Enter to continue...")
    
    def test_remote(self, remotes):
        """Test connection to remote using stored token"""
        self.clear_screen()
        self.print_header("Test Remote Connection")
        
        # Get unique remote names
        remote_names = list(set([r['name'] for r in remotes]))
        
        print("Select remote to test:")
        for i, name in enumerate(remote_names, 1):
            print(f"  [{i}] {name}")
        
        print()
        choice = self.get_input("Enter number: ")
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(remote_names):
                name = remote_names[idx]
                
                # Get remote URL
                url_result = self.run_git_command(f"git remote get-url {name}")
                if not url_result['success']:
                    print("Could not get remote URL")
                    input("\nPress Enter to continue...")
                    return
                
                remote_url = url_result['stdout'].strip()
                
                # Get username from config
                username = self.config.get('github_username', '')
                if not username:
                    print("\nNo GitHub username configured.")
                    print("Please set up username in Settings first.")
                    input("\nPress Enter to continue...")
                    return
                
                # Get token from Crypto
                token = self.get_token()
                if not token:
                    print("\nNo valid token found.")
                    print("Please set up token in Settings → Manage tokens first.")
                    input("\nPress Enter to continue...")
                    return
                
                print(f"\nTesting connection to '{name}'...")
                
                # Handle HTTPS with token
                if 'https://' in remote_url:
                    if 'github.com/' in remote_url:
                        # Extract repo path
                        repo_path = remote_url.split('github.com/')[-1].replace('.git', '')
                        
                        # Test with GitHub API first (more reliable)
                        import subprocess
                        print("Testing via GitHub API...")
                        api_cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: token {token}' https://api.github.com/repos/{username}/{repo_path}"
                        api_result = subprocess.run(api_cmd, shell=True, capture_output=True, text=True)
                        
                        if api_result.stdout.strip() == '200':
                            print("✓ API connection successful")
                            
                            # Also test git ls-remote
                            auth_url = f"https://{username}:{token}@github.com/{repo_path}.git"
                            git_cmd = f"git ls-remote {auth_url} HEAD"
                            git_result = self.run_git_command(git_cmd)
                            
                            if git_result['success']:
                                print("✓ Git connection successful")
                                if git_result['stdout']:
                                    print(f"  HEAD: {git_result['stdout'][:40]}...")
                            else:
                                print("✗ Git connection failed")
                        else:
                            print(f"✗ API connection failed (HTTP {api_result.stdout})")
                            
                            # Try git directly as fallback
                            print("\nTrying direct git connection...")
                            auth_url = f"https://{username}:{token}@github.com/{repo_path}.git"
                            git_cmd = f"git ls-remote {auth_url} HEAD"
                            git_result = self.run_git_command(git_cmd)
                            
                            if git_result['success']:
                                print("✓ Git connection successful")
                            else:
                                print("✗ Git connection failed")
                                print(git_result.get('stderr', 'Unknown error'))
                    else:
                        print("Not a GitHub URL, cannot test with token")
                else:
                    # SSH - test normally
                    print("Testing SSH connection...")
                    result = self.run_git_command(f"git ls-remote {name} HEAD")
                    if result['success']:
                        print("✓ Connection successful")
                    else:
                        print("✗ Connection failed:")
                        print(result.get('stderr', 'Unknown error'))
                        
        except Exception as e:
            print(f"Error: {e}")
        
        input("\nPress Enter to continue...")
    
    def push_branch(self, info):
        """Push to remote using stored token from Crypto"""
        self.clear_screen()
        self.print_header("Push to Remote")
        
        if not info['remotes']:
            print("No remotes configured.")
            input("\nPress Enter to continue...")
            return
        
        if info['uncommitted']:
            print("Uncommitted changes detected:")
            print(info['status'])
            print("\nPlease commit changes before pushing.")
            input("\nPress Enter to continue...")
            return
        
        # Get remote names
        remote_names = list(set([r['name'] for r in info['remotes']]))
        
        if len(remote_names) > 1:
            print("Select remote:")
            for i, name in enumerate(remote_names, 1):
                print(f"  [{i}] {name}")
            print()
            remote_choice = self.get_input("Enter number: ")
            
            try:
                idx = int(remote_choice) - 1
                remote = remote_names[idx] if 0 <= idx < len(remote_names) else remote_names[0]
            except:
                remote = remote_names[0]
        else:
            remote = remote_names[0]
        
        # Get current remote URL
        remote_url_result = self.run_git_command(f"git remote get-url {remote}")
        if not remote_url_result['success']:
            print("Could not get remote URL")
            input("\nPress Enter to continue...")
            return
        
        remote_url = remote_url_result['stdout'].strip()
        
        # Check if upstream is set
        upstream_result = self.run_git_command("git rev-parse --abbrev-ref --symbolic-full-name @{u}")
        has_upstream = upstream_result['success']
        
        # Get username from config
        username = self.config.get('github_username', '')
        if not username:
            print("\nNo GitHub username configured.")
            print("Please set up username in Settings first.")
            input("\nPress Enter to continue...")
            return
        
        # Get token from Crypto
        token = self.get_token()
        if not token:
            print("\nNo valid token found.")
            print("Please set up token in Settings → Manage tokens first.")
            input("\nPress Enter to continue...")
            return
        
        if has_upstream:
            push_cmd = f"git push {remote}"
        else:
            push_cmd = f"git push -u {remote} {info['current_branch']}"
        
        if info['ahead'] > 0:
            print(f"Commits to push: {info['ahead']}")
        else:
            print("No commits to push.")
            if not has_upstream:
                # Still need to set upstream
                pass
            else:
                input("\nPress Enter to continue...")
                return
        
        # Handle HTTPS with token
        if 'https://' in remote_url:
            # Extract repo path
            if 'github.com/' in remote_url:
                repo_path = remote_url.split('github.com/')[-1].replace('.git', '')
                
                # Create authenticated URL
                auth_url = f"https://{username}:{token}@github.com/{repo_path}.git"
                
                # Mask token for display
                masked_url = auth_url.replace(token, '********')
                print(f"\nPushing to: {masked_url}")
                
                # Use authenticated URL
                if has_upstream:
                    result = self.run_git_command(f"git push {auth_url} {info['current_branch']}")
                else:
                    result = self.run_git_command(f"git push -u {auth_url} {info['current_branch']}")
            else:
                print("Not a GitHub URL, using normal push")
                result = self.run_git_command(push_cmd)
        else:
            # SSH - use normal push
            print(f"\nPushing to {remote}...")
            result = self.run_git_command(push_cmd)
        
        if result['success']:
            print("✓ Push successful")
        else:
            print("✗ Push failed:")
            print(result.get('stderr', 'Unknown error'))
            
            # Troubleshooting
            if '403' in result.get('stderr', '') or 'authentication' in result.get('stderr', '').lower():
                print("\n🔧 Troubleshooting:")
                print("1. Token may be expired - generate a new one")
                print("2. Ensure token has 'repo' scope")
                print("3. Update token in Settings → Manage tokens")
        
        input("\nPress Enter to continue...")
    
    def view_status(self):
        """View repository status"""
        self.clear_screen()
        info = self.get_repo_info()
        self.print_header("Repository Status")
        
        if not info['is_git']:
            print("Not a git repository.")
            print()
            print("Options:")
            print("  [1] Initialize repository")
            print("  [2] Back")
            print()
            
            choice = self.get_input("Select option: ")
            if choice == "1":
                self.init_repo()
            return
        
        print(f"Project: {os.path.basename(self.project_dir)}")
        print(f"Path: {self.project_dir}")
        print(f"Git: Yes")
        print(f"Current branch: {info['current_branch']}")
        print()
        
        if info['remotes']:
            print("Remotes:")
            for remote in info['remotes']:
                if remote['type'] == 'fetch':
                    print(f"  {remote['name']}: {remote['url']}")
            print()
        
        if info['ahead'] > 0 or info['behind'] > 0:
            print(f"Sync status: {info['ahead']} ahead, {info['behind']} behind")
            print()
        
        if info['status']:
            print("Uncommitted changes:")
            print(info['status'])
        else:
            print("Working tree clean.")
        
        print()
        
        if info['branches']:
            print("Local branches:")
    
            # Get current branch
            current_branch = info.get('current_branch', '')
    
            # Get list of merged branches
            merged_result = self.run_git_command("git branch --merged")
            merged_branches = []
            if merged_result['success'] and merged_result['stdout']:
                merged_branches = [line.strip().replace('* ', '') for line in merged_result['stdout'].split('\n') if line.strip()]
    
            for i, branch in enumerate(info['branches'], 1):
                marker = '*' if branch['current'] else ' '
                branch_name = branch['name']
        
                # Determine status
                if branch['current']:
                    status = "[current]"
                elif branch_name in merged_branches:
                    status = "[merged]"
                else:
                    status = "[unmerged]"
        
                print(f"  [{i}] {marker} {branch_name} {status}")
        
        input("\nPress Enter to continue...")
    
    def configure_settings(self):
        """Configure Git settings"""
        self.clear_screen()
        self.print_header("Git Configuration")
        
        # Check token status using get_token()
        token = self.get_token()
        token_exists = token is not None

        print(f"GitHub username: {self.config.get('github_username', 'Not set')}")
        print(f"Default remote: {self.config.get('default_remote', 'origin')}")
        print(f"Default branch: {self.config.get('default_branch', 'main')}")
        print(f"Token stored: {'Yes' if token_exists else 'No'}")
        if token_exists and token:
            masked = token[:4] + '*' * (len(token)-8) + token[-4:] if len(token) > 8 else '***'
            print(f"Token preview: {masked}")
        print()
        print(f"Excluded folders:")
        for folder in self.config.get('excluded_folders', []):
            print(f"  - {folder}")
        print()

        print("Options:")
        print("  1. Set GitHub username")
        print("  2. Set default remote name")
        print("  3. Set default branch")
        print("  4. Manage GitHub token")
        print("  5. View/Edit .gitignore")
        print("  6. Back")
        print()

        choice = self.get_input("Select option: ")

        if choice == "1":
            username = self.get_input("GitHub username: ")
            if username:
                self.config['github_username'] = username
                self.save_config()
                print("✓ Username saved")

        elif choice == "2":
            remote = self.get_input("Default remote name [origin]: ") or "origin"
            self.config['default_remote'] = remote
            self.save_config()
            print("✓ Default remote saved")

        elif choice == "3":
            branch = self.get_input("Default branch [main]: ") or "main"
            self.config['default_branch'] = branch
            self.save_config()
            print("✓ Default branch saved")

        elif choice == "4":
            self.manage_token()
            # After managing token, refresh the screen
            self.configure_settings()
            return

        elif choice == "5":
            self.view_gitignore()

        if choice in ["1", "2", "3", "5"]:
            input("\nPress Enter to continue...")
    
    def manage_token(self):
        """Manage GitHub token"""
        self.clear_screen()
        self.print_header("GitHub Token Management")

        # Use get_token() directly to check if token exists
        token = self.get_token()
        token_exists = token is not None
        
        print(f"Token status: {'✅ Stored' if token_exists else '❌ Not set'}")
        
        if token_exists:
            # Show masked token
            masked = token[:4] + '*' * (len(token)-8) + token[-4:] if len(token) > 8 else '***'
            print(f"  Token: {masked}")

        print()
        print("Options:")
        print("  1. Set new token")
        if token_exists:
            print("  2. Clear token")
            print("  3. Test token")
        print("  4. Back")
        print()

        choice = self.get_input("Select option: ")

        if choice == "1":
            token = self.get_password("Enter GitHub Personal Access Token: ")
            if token:
                if self.save_token(token):
                    print("✓ Token saved")
                else:
                    print("✗ Failed to save token")
        
        elif choice == "2" and token_exists:
            if self.delete_token():
                print("✓ Token cleared")
            else:
                print("✗ Failed to clear token")
        
        elif choice == "3" and token_exists:
            self.test_saved_token()
        
        if choice in ["1", "2"]:
            input("\nPress Enter to continue...")
    
    def view_gitignore(self):
        """View and edit .gitignore"""
        self.clear_screen()
        self.print_header(".gitignore Management")
        
        gitignore_path = os.path.join(self.project_dir, '.gitignore')
        
        if os.path.exists(gitignore_path):
            print("Current .gitignore:")
            print()
            with open(gitignore_path, 'r') as f:
                print(f.read())
        else:
            print("No .gitignore file found.")
        
        print()
        print("Options:")
        print("  1. Create/Recreate .gitignore (with notebooks_root excluded)")
        print("  2. Edit manually")
        print("  3. Back")
        print()
        
        choice = self.get_input("Select option: ")
        
        if choice == "1":
            self.create_gitignore()
            print("✓ .gitignore created/updated")
        elif choice == "2":
            if os.path.exists(gitignore_path):
                editor = os.environ.get('EDITOR', 'nano')
                os.system(f"{editor} {gitignore_path}")
            else:
                print("No .gitignore to edit.")
        
        if choice in ["1", "2"]:
            input("\nPress Enter to continue...")
    
    def run(self):
        """Main loop"""
        while True:
            self.clear_screen()
            self.print_header("Terminal Notes Project Git Manager")
            self.print_separator()
            print("  Focused on project repository only")
            print("  Excludes: notebooks_root/")
            self.print_separator()
            print()
            
            print("1. View Repository Status")
            print("2. Configure Remotes")
            print("3. Manage Branches")
            print("4. Commit Changes")  # New option
            print("5. Configure Settings")
            print("6. Initialize Repository (if needed)")
            print("7. Exit")
            print()
            
            choice = self.get_input("Select option [1-7]: ")
            
            if choice == "1":
                self.view_status()
            elif choice == "2":
                self.view_remotes()
            elif choice == "3":
                self.manage_branches()
            elif choice == "4":
                self.commit_changes()
            elif choice == "5":
                self.configure_settings()
            elif choice == "6":
                self.init_repo()
                self.view_status()
            elif choice == "7":
                print("\nGoodbye!")
                break

if __name__ == "__main__":
    manager = ProjectGitManager()
    manager.run()