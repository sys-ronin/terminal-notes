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
        import subprocess
        import shlex
        
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
                cmd_parts = ["git", "commit", "-m", commit_msg]
                for line in commit_desc.split('\n'):
                    if line.strip():
                        cmd_parts.extend(["-m", line])
                print(f"\nRunning: git commit with {len(cmd_parts)-2} message parts")
                result = subprocess.run(cmd_parts, cwd=self.project_dir, capture_output=True, text=True)
            else:
                cmd_parts = ["git", "commit", "-m", commit_msg]
                result = subprocess.run(cmd_parts, cwd=self.project_dir, capture_output=True, text=True)
        
            if result.returncode == 0:
                print("\n✓ Commit successful!")
                if result.stdout:
                    print(result.stdout)
                
                # Ask about version tagging
                print("\n" + "="*50)
                create_tag = self.get_input("Create a version tag for this commit? [y/N]: ").lower()
                if create_tag == 'y':
                    # Get current branch name
                    branch_result = self.run_git_command("git branch --show-current")
                    current_branch = branch_result['stdout'].strip() if branch_result['success'] else "unknown"
                    
                    # Reuse the version tagging method (this has its own input pause)
                    self._handle_version_tagging(source="commit", source_name=current_branch)
                else:
                    print("\n✓ Skipping version tag.")
                    input("\nPress Enter to continue...")  # Only pause here if not tagging
            else:
                print("\n✗ Commit failed:")
                print(result.stderr)
                input("\nPress Enter to continue...")  # Pause on error

        else:
            print("Commit cancelled")
            input("\nPress Enter to continue...")  # Pause on cancel
    
    
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
        """Push changes to remote with timeout and non-interactive mode, including tag sync"""
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

        # Check tag synchronization status
        print("\n" + "="*50)
        print("📌 Checking tags...")
        
        tags_result = self.run_git_command("git tag -l")
        local_tags = []
        if tags_result['success'] and tags_result['stdout'].strip():
            local_tags = [tag.strip() for tag in tags_result['stdout'].strip().split('\n') if tag.strip()]
            print(f"   Local tags found: {len(local_tags)}")
            if local_tags:
                for tag in local_tags[:3]:
                    print(f"     • {tag}")
                if len(local_tags) > 3:
                    print(f"     ... and {len(local_tags)-3} more")
        else:
            print("   No local tags found")
        
        # Get remote tags
        remote_tags = []
        if local_tags:  # Only check remote if we have local tags
            print("   Checking remote tags...")
            remote_tags_result = self.run_git_command("git ls-remote --tags origin")
            if remote_tags_result['success'] and remote_tags_result['stdout'].strip():
                for line in remote_tags_result['stdout'].strip().split('\n'):
                    if 'refs/tags/' in line:
                        tag = line.split('refs/tags/')[-1].replace('^{}', '')
                        if tag and tag not in remote_tags:
                            remote_tags.append(tag)
                print(f"   Remote tags found: {len(remote_tags)}")
                if remote_tags:
                    for tag in remote_tags[:3]:
                        print(f"     • {tag}")
                    if len(remote_tags) > 3:
                        print(f"     ... and {len(remote_tags)-3} more")
            else:
                print("   No remote tags found or cannot access remote")
        else:
            remote_tags = []
        
        # Determine tag differences
        tags_to_push = [tag for tag in local_tags if tag not in remote_tags]
        tags_to_delete = [tag for tag in remote_tags if tag not in local_tags]
        
        print(f"\n   Tags to push: {len(tags_to_push)}")
        print(f"   Tags to delete: {len(tags_to_delete)}")
        
        # Show tag sync status if there are any tag operations
        if tags_to_push or tags_to_delete:
            print("\n" + "="*50)
            print("📌 Tag Synchronization Required:")
            print("-" * 50)
            
            if tags_to_push:
                print(f"\n🔼 Tags to PUSH to remote ({len(tags_to_push)}):")
                for tag in tags_to_push[:5]:
                    print(f"   • {tag}")
                if len(tags_to_push) > 5:
                    print(f"   ... and {len(tags_to_push)-5} more")
            
            if tags_to_delete:
                print(f"\n🔽 Tags to DELETE from remote ({len(tags_to_delete)}):")
                for tag in tags_to_delete[:5]:
                    print(f"   • {tag}")
                if len(tags_to_delete) > 5:
                    print(f"   ... and {len(tags_to_delete)-5} more")
        else:
            print("\n✅ Local and remote tags are in sync")

        # Check if token is needed for HTTPS
        token = self.get_token()
        username = self.config.get('github_username', '')

        push_url = remote_url
        if token and username and 'github.com' in remote_url:
            # Inject token into URL for authentication
            push_url = remote_url.replace('https://', f'https://{username}:{token}@')
            print(f"\n🔐 Pushing with authentication")
            print(f"   Remote: {remote_url.replace('https://', 'https://' + username + ':********@')}")
        else:
            print(f"\n📡 Pushing to: {remote_url}")

        # Check what would be pushed
        ahead_result = self.run_git_command(f"git rev-list --count HEAD --not --remotes")
        commits_to_push = 0
        if ahead_result['success'] and ahead_result['stdout'].strip():
            commits_to_push = int(ahead_result['stdout'].strip())
            if commits_to_push == 0 and not tags_to_push and not tags_to_delete:
                print("\n📭 No commits or tags to sync.")
                self.get_input("Press Enter to continue...")
                return
            if commits_to_push > 0:
                print(f"\n📝 Commits to push: {commits_to_push}")
        else:
            print("\n⚠️ Could not determine commits ahead")

        # ALWAYS ask about tag synchronization if there are tag operations
        sync_tags = False
        tag_action = None
        
        if tags_to_push or tags_to_delete:
            print("\n" + "="*50)
            print("🏷️  Tag Sync Options:")
            print("-" * 50)
            print("  [1] Push new tags only (keep existing remote tags)")
            if tags_to_delete:
                print("  [2] Full sync (push new AND delete removed tags from remote)")
            else:
                print("  [2] Push all tags (--tags)")
            print("  [3] Skip tag operations, push commits only")
            print()
            
            tag_choice = self.get_input("Choose [1-3]: ").strip()
            
            if tag_choice == "1":
                sync_tags = True
                tag_action = "push_only"
                print("\n✅ Will push new tags only")
            elif tag_choice == "2":
                sync_tags = True
                if tags_to_delete:
                    tag_action = "full_sync"
                    print(f"\n✅ Will perform FULL sync: push {len(tags_to_push)} new + delete {len(tags_to_delete)} removed tags")
                else:
                    tag_action = "push_all"
                    print(f"\n✅ Will push all {len(local_tags)} tags")
            else:
                print("\n⏭️  Skipping tag operations, pushing commits only")
        else:
            print("\n✅ No tag operations needed")

        print("\n" + "="*50)
        print("📤 Pushing to remote...")
        print("-" * 50)

        # Use subprocess with timeout and non-interactive mode
        import subprocess
        import time

        try:
            success = True
            
            # Step 1: Delete tags from remote if doing full sync
            if sync_tags and tag_action == "full_sync" and tags_to_delete:
                print("\n🗑️  Deleting removed tags from remote...")
                for tag in tags_to_delete:
                    delete_cmd = ["git", "push", "origin", f":refs/tags/{tag}"]
                    
                    # Use authenticated URL if needed
                    if token and username and 'github.com' in remote_url and push_url != remote_url:
                        delete_cmd = ["git", "push", push_url, f":refs/tags/{tag}"]
                    
                    delete_result = subprocess.run(
                        delete_cmd,
                        cwd=self.project_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if delete_result.returncode == 0:
                        print(f"   ✓ Deleted: {tag}")
                    else:
                        print(f"   ✗ Failed to delete: {tag}")
                        if delete_result.stderr:
                            print(f"     Error: {delete_result.stderr[:100]}")
                        success = False
            
            # Step 2: Push commits and tags
            need_to_push = commits_to_push > 0 or (sync_tags and (tags_to_push or tag_action == "push_all"))
            
            if need_to_push:
                # Set up the push command
                cmd = ["git", "push", "-u", "origin", current_branch]
                
                # Add tags based on sync type
                if sync_tags:
                    if tag_action == "push_only" and tags_to_push:
                        cmd.append("--tags")
                        print("\n🏷️  Pushing new tags...")
                    elif tag_action == "push_all":
                        cmd.append("--tags")
                        print(f"\n🏷️  Pushing all {len(local_tags)} tags...")
                    elif tag_action == "full_sync":
                        cmd.append("--follow-tags")
                        print("\n🏷️  Pushing commits and associated tags...")
                
                if commits_to_push > 0:
                    print(f"📝 Pushing {commits_to_push} commit(s)...")
                
                # Use environment to prevent git from asking for credentials
                env = os.environ.copy()
                env.update({
                    'GIT_ASKPASS': 'echo',
                    'GIT_TERMINAL_PROMPT': '0'
                })
                
                # If using authentication, set up the URL with credentials
                actual_cmd = cmd[:]
                if token and username and 'github.com' in remote_url and push_url != remote_url:
                    # Replace 'origin' with authenticated URL
                    for i, arg in enumerate(actual_cmd):
                        if arg == 'origin':
                            actual_cmd[i] = push_url
                            break
                
                # Run push command
                process = subprocess.Popen(
                    actual_cmd,
                    cwd=self.project_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for process with timeout
                timeout = 60
                try:
                    stdout, stderr = process.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    process.kill()
                    print(f"\n✗ Push timed out after {timeout} seconds")
                    self.get_input("Press Enter to continue...")
                    return
                
                if process.returncode != 0:
                    success = False
                    print("\n✗ Push failed:")
                    if stderr:
                        print(stderr)
                    if stdout:
                        print(stdout)
                else:
                    if stdout:
                        print(stdout)
            
            # Step 3: Report results
            if success:
                print("\n" + "="*50)
                print("✅ Push Successful!")
                print("-" * 50)
                
                if sync_tags:
                    if tags_to_push and tag_action == "push_only":
                        print(f"✓ Pushed {len(tags_to_push)} new tag(s)")
                    elif tag_action == "push_all" and local_tags:
                        print(f"✓ Pushed all {len(local_tags)} tag(s)")
                    elif tag_action == "full_sync":
                        if tags_to_push:
                            print(f"✓ Pushed {len(tags_to_push)} new tag(s)")
                        if tags_to_delete:
                            print(f"✓ Deleted {len(tags_to_delete)} tag(s) from remote")
                
                if commits_to_push > 0:
                    print(f"✓ Pushed {commits_to_push} commit(s)")
                
                # Show pushed tags
                if sync_tags and tags_to_push and tag_action != "push_all":
                    print("\n📌 Tags pushed:")
                    for tag in tags_to_push[:5]:
                        print(f"   • {tag}")
                    if len(tags_to_push) > 5:
                        print(f"   ... and {len(tags_to_push)-5} more")
                elif sync_tags and tag_action == "push_all" and local_tags:
                    print("\n📌 Tags pushed:")
                    for tag in local_tags[:5]:
                        print(f"   • {tag}")
                    if len(local_tags) > 5:
                        print(f"   ... and {len(local_tags)-5} more")
                
                # Update last push time in config
                self.config['last_sync'] = datetime.now().isoformat()
                self.save_config()
            else:
                print("\n" + "="*50)
                print("❌ Push completed with errors")
                print("-" * 50)
                
        except Exception as e:
            print(f"\n❌ Push error: {e}")
            import traceback
            traceback.print_exc()

        self.get_input("\nPress Enter to continue...")
    
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
            
                # Check if merging into master/main
                is_merging_into_master = info['current_branch'] in ['master', 'main']
            
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
                
                    # ONLY ask for version tagging when merging into master/main
                    if is_merging_into_master:
                        print("\n" + "="*50)
                        ask_version = self.get_input("Would you like to create a version tag? [y/N]: ").lower()
                        if ask_version == 'y':
                            self._handle_version_tagging(source="merge", source_name=branch)
                        else:
                            print("✓ Skipping version tag.")
                            input("\nPress Enter to continue...")
                    else:
                        print(f"\nℹ️  Not merging into master/main - no version tag needed.")
                        input("\nPress Enter to continue...")
                else:
                    print(f"✗ Merge failed: {result.get('stderr', 'Unknown error')}")
                    input("\nPress Enter to continue...")
                
                    if 'conflict' in result.get('stderr', '').lower():
                        print("\n❌ Merge conflicts detected. Resolve conflicts and commit manually.")
                        print("   Then run: git merge --continue")
        except Exception as e:
            print(f"Error: {e}")
            input("\nPress Enter to continue...")

    def _handle_version_tagging(self, source="merge", source_name=None):
        """Handle version tagging for merges or commits with proper existing tag detection
        
        Args:
            source: Where the tag is being created from ('merge' or 'commit')
            source_name: Branch name or commit reference (optional)
        """
        print("\n" + "="*50)
        print("Version Tagging")
        print("="*50)
        
        # If source_name not provided, use appropriate default
        if source_name is None:
            if source == "merge":
                source_name = "merged branch"
            else:
                source_name = "commit"
        
        # Get ALL existing tags
        tags_result = self.run_git_command("git tag -l")
        existing_tags = []
        
        if tags_result['success'] and tags_result['stdout'].strip():
            existing_tags = [tag.strip() for tag in tags_result['stdout'].strip().split('\n') if tag.strip()]
            
            # Sort tags by version number, not string
            import re
            def version_key(tag):
                match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', tag)
                if match:
                    return tuple(map(int, match.groups()))
                return (0, 0, 0)
            
            existing_tags.sort(key=version_key)
        
        # Display existing tags if any
        if existing_tags:
            print(f"\n📌 Existing tags ({len(existing_tags)} total):")
            # Show last 5 tags
            for tag in existing_tags[-5:]:
                print(f"   • {tag}")
            if len(existing_tags) > 5:
                print(f"   ... and {len(existing_tags)-5} more")
            print(f"\n🏷️  Latest tag: {existing_tags[-1] if existing_tags else 'None'}")
        else:
            print("\n📌 No existing tags found. This will be the first version tag.")
        
        print("\n" + "-"*50)
        print("Version Options:")
        
        # Always ask for version (optional)
        print("\nEnter version manually, or choose an option:")
        print("  [1] Auto-increment version (based on latest tag)")
        print("  [2] Enter custom version")
        print("  [3] Skip tagging (no version tag)")
        print()
        
        choice = self.get_input("Choose [1-3]: ").strip()
        
        new_version = None
        
        if choice == "3":
            print("\n✓ Skipping version tag.")
            return
        
        elif choice == "1":
            if existing_tags:
                latest_tag = existing_tags[-1]
                
                # Parse the latest tag to get current numbers
                import re
                version_match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', latest_tag)
                
                if version_match:
                    current_major, current_minor, current_patch = map(int, version_match.groups())
                    
                    # Calculate suggested increments based on current tag
                    patch_version = f"v{current_major}.{current_minor}.{current_patch + 1}"
                    minor_version = f"v{current_major}.{current_minor + 1}.0"
                    major_version = f"v{current_major + 1}.0.0"
                    
                    print(f"\n📐 Latest tag: {latest_tag}")
                    print("\nSelect increment type:")
                    print(f"  [1] Patch (bug fixes)      - {latest_tag} → {patch_version}")
                    print(f"  [2] Minor (new features)   - {latest_tag} → {minor_version}")
                    print(f"  [3] Major (breaking)       - {latest_tag} → {major_version}")
                    print("  [4] Custom increment")
                    print()
                    
                    inc_choice = self.get_input("Choose [1-4]: ").strip()
                    
                    if inc_choice == "1":
                        new_version = patch_version
                    elif inc_choice == "2":
                        new_version = minor_version
                    elif inc_choice == "3":
                        new_version = major_version
                    elif inc_choice == "4":
                        custom = self.get_input(f"Enter custom version (e.g., {patch_version}, {minor_version}, etc.): ").strip()
                        if custom:
                            if not custom.startswith('v') and custom[0].isdigit():
                                custom = 'v' + custom
                            new_version = custom
                    else:
                        print("Invalid choice. Please enter custom version.")
                        new_version = self.get_input("Enter version: ").strip()
                else:
                    print(f"⚠️ Could not parse version format: {latest_tag}")
                    print("\nSelect increment type (generic):")
                    print("  [1] Patch (bug fixes)      - v1.0.0 → v1.0.1")
                    print("  [2] Minor (new features)   - v1.0.0 → v1.1.0")
                    print("  [3] Major (breaking)       - v1.0.0 → v2.0.0")
                    print("  [4] Custom increment")
                    print()
                    
                    inc_choice = self.get_input("Choose [1-4]: ").strip()
                    
                    if inc_choice == "1":
                        new_version = "v1.0.1"
                    elif inc_choice == "2":
                        new_version = "v1.1.0"
                    elif inc_choice == "3":
                        new_version = "v2.0.0"
                    elif inc_choice == "4":
                        new_version = self.get_input("Enter custom version: ").strip()
                    else:
                        new_version = self.get_input("Enter version: ").strip()
                    
                    if new_version and not new_version.startswith('v') and new_version[0].isdigit():
                        new_version = 'v' + new_version
            else:
                # No existing tags, suggest starting version
                print("\nNo existing tags. Suggested starting versions:")
                print("  [1] v1.0.0 (semantic version)")
                print("  [2] v0.1.0 (development version)")
                print("  [3] Enter custom version")
                print()
                
                start_choice = self.get_input("Choose [1-3]: ").strip()
                
                if start_choice == "1":
                    new_version = "v1.0.0"
                elif start_choice == "2":
                    new_version = "v0.1.0"
                else:
                    new_version = self.get_input("Enter version: ").strip()
                    if new_version and not new_version.startswith('v') and new_version[0].isdigit():
                        new_version = 'v' + new_version
        
        elif choice == "2":
            # Manual version entry
            if existing_tags:
                latest_tag = existing_tags[-1]
                print(f"\nLatest tag: {latest_tag}")
                print("Enter version tag (e.g., v1.2.3, v1.0, 2.0.0, or any format)")
            else:
                print("\nEnter version tag (e.g., v1.2.3, v1.0, 2.0.0, or any format)")
            print("  Leave empty to skip tagging")
            print()
            new_version = self.get_input("Version: ").strip()
            
            if not new_version:
                print("\n✓ Skipping version tag.")
                return
            
            # Auto-add 'v' prefix if missing and tag looks like a version number
            if not new_version.startswith('v') and new_version and new_version[0].isdigit():
                add_prefix = self.get_input(f"Add 'v' prefix to '{new_version}'? [Y/n]: ").strip().lower()
                if add_prefix != 'n':
                    new_version = 'v' + new_version
        
        # Create the tag if we have a version
        if new_version:
            # Check if tag already exists
            if new_version in existing_tags:
                print(f"\n⚠️ Tag '{new_version}' already exists!")
                overwrite = self.get_input("Create anyway? Git will reject duplicates. [y/N]: ").lower()
                if overwrite != 'y':
                    print("✓ Tag creation cancelled.")
                    input("\nPress Enter to continue...")
                    return
            
            # Create annotated tag (message differs based on source)
            if source == "merge":
                tag_message = f"Release {new_version}\n\nMerged from branch: {source_name}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            else:
                tag_message = f"Release {new_version}\n\nCommitted on branch: {source_name}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            import subprocess
            print(f"\n📝 Creating tag: {new_version}")
            
            tag_result = subprocess.run(
                ['git', 'tag', '-a', new_version, '-m', tag_message],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            
            if tag_result.returncode == 0:
                # Verify tag was created
                verify_result = subprocess.run(
                    ['git', 'tag', '-l', new_version],
                    cwd=self.project_dir,
                    capture_output=True,
                    text=True
                )
                
                if verify_result.returncode == 0 and verify_result.stdout.strip() == new_version:
                    print(f"\n✅ SUCCESS: Created tag '{new_version}'")
                    print(f"   Message: {tag_message.split(chr(10))[0]}")
                    print("\n📌 To push tags to remote:")
                    print("   - Push single tag: git push origin " + new_version)
                    print("   - Push all tags:   git push --tags")
                    print("\n   Or use 'Push to Remote' from the main menu.")
                else:
                    print(f"\n⚠️ Tag may not have been created properly. Verify with: git tag -l")
            else:
                print(f"\n❌ Failed to create tag: {tag_result.stderr}")
                if "already exists" in tag_result.stderr.lower():
                    print("   Tag already exists in repository.")
                elif "not allow" in tag_result.stderr.lower():
                    print("   Git configuration may not allow tag creation.")
        else:
            print("\n✓ No version tag created.")
        
        # Show current tags after creation
        print("\n" + "-"*50)
        show_tags = self.get_input("Show all tags? [y/N]: ").strip().lower()
        if show_tags == 'y':
            list_result = subprocess.run(
                ['git', 'tag', '-l', '--sort=-version:refname'],
                cwd=self.project_dir,
                capture_output=True,
                text=True
            )
            if list_result.returncode == 0 and list_result.stdout.strip():
                print("\n📋 All tags:")
                for tag in list_result.stdout.strip().split('\n')[:10]:  # Show first 10
                    print(f"   • {tag}")
                tag_count = len(list_result.stdout.strip().split('\n'))
                if tag_count > 10:
                    print(f"   ... and {tag_count - 10} more")
        
        input("\nPress Enter to continue...")
    
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
                
                # Handle HTTPS with token #
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
    
    def get_commits_between_tags(self, current_tag, previous_tag=None):
        """Get FULL commit messages (title + body) between two tags"""
        # If previous_tag is provided (from release checking), use it directly
        if previous_tag:
            # Remove the outer quotes from format - use %B without quotes
            log_result = self.run_git_command(f"git log {previous_tag}..{current_tag} --pretty=format:%B --reverse")
        else:
            # No previous tag provided, try to find the previous tag automatically
            import re
            
            # Get all tags and sort them properly
            tags_result = self.run_git_command("git tag -l")
            all_tags = []
            if tags_result['success'] and tags_result['stdout'].strip():
                all_tags = [tag.strip() for tag in tags_result['stdout'].strip().split('\n') if tag.strip()]
                
                # Sort tags by version number
                def version_key(tag):
                    match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', tag)
                    if match:
                        return tuple(map(int, match.groups()))
                    return (0, 0, 0)
                
                all_tags.sort(key=version_key)
                
                # Find the current tag index
                if current_tag in all_tags:
                    current_index = all_tags.index(current_tag)
                    if current_index > 0:
                        previous_tag = all_tags[current_index - 1]
            
            if previous_tag:
                # Remove the outer quotes from format
                log_result = self.run_git_command(f"git log {previous_tag}..{current_tag} --pretty=format:%B --reverse")
            else:
                # No previous tag found, ask user for range
                print(f"\n  No previous tag found before {current_tag}")
                print("  Options:")
                print("    [1] Get all commits since beginning")
                print("    [2] Enter specific start tag/commit")
                print("    [3] Skip (use minimal release notes)")
                
                range_choice = self.get_input("  Choose [1-3]: ").strip()
                
                if range_choice == "1":
                    log_result = self.run_git_command(f"git log {current_tag} --pretty=format:%B --reverse")
                elif range_choice == "2":
                    start_ref = self.get_input("  Enter start tag or commit hash: ").strip()
                    if start_ref:
                        log_result = self.run_git_command(f"git log {start_ref}..{current_tag} --pretty=format:%B --reverse")
                    else:
                        log_result = {'success': False, 'stdout': ''}
                else:
                    log_result = {'success': False, 'stdout': ''}
        
        # Parse the commit messages
        commits = []
        if log_result.get('success') and log_result.get('stdout', '').strip():
            # Commits are separated by two newlines when using %B format
            raw_output = log_result['stdout']
            
            # Split by double newline to separate commits
            raw_commits = raw_output.split('\n\n')
            
            for commit in raw_commits:
                if commit.strip():
                    # Clean up the commit message
                    commit = commit.strip()
                    
                    # No need to remove quotes anymore since we're not using them
                    if commit:
                        commits.append(commit)
        
        return commits, previous_tag

    def generate_release_notes(self, tag_name, commits, previous_tag):
        """Generate release notes from commit messages without grouping"""
        notes = []
        notes.append(f"## {tag_name}")
        notes.append(f"\n**Release Date:** {datetime.now().strftime('%Y-%m-%d')}")
        
        if previous_tag:
            notes.append(f"\n**Changes since {previous_tag}:**")
        else:
            notes.append("\n**Initial Release:**")
        
        # Just list all commits as-is, preserving their original format
        notes.append("")
        
        # Clean and count actual commits
        clean_commits = []
        for commit in commits:
            # Skip empty commits
            if not commit or not commit.strip():
                continue
                
            # Clean up the commit message - remove surrounding quotes
            commit = commit.strip()
            
            # Remove single quotes from start and end
            if commit.startswith("'") and commit.endswith("'"):
                commit = commit[1:-1]
            # Remove double quotes from start and end
            if commit.startswith('"') and commit.endswith('"'):
                commit = commit[1:-1]
            commit = commit.strip()
            
            # Skip if empty after cleaning
            if not commit:
                continue
                
            # Decode escaped newlines
            commit = commit.replace('\\n', '\n')
            
            # Clean up any remaining quote artifacts at line boundaries
            lines = commit.split('\n')
            cleaned_lines = []
            for line in lines:
                line = line.strip()
                if line:
                    # Remove single quotes from line boundaries
                    if line.startswith("'") and line.endswith("'"):
                        line = line[1:-1]
                    if line.startswith('"') and line.endswith('"'):
                        line = line[1:-1]
                    cleaned_lines.append(line)
            
            if cleaned_lines:
                clean_commits.append('\n'.join(cleaned_lines))
        
        # Add cleaned commits to notes
        for i, commit in enumerate(clean_commits):
            # Split into lines and add each line
            lines = commit.split('\n')
            for j, line in enumerate(lines):
                if j == 0:
                    notes.append(f"{line}")
                else:
                    notes.append(f"  {line}")
            # Add blank line between commits (except after last commit)
            if i < len(clean_commits) - 1:
                notes.append("")
        
        # Remove the total commits line entirely
        # Don't add the commit count
        
        return '\n'.join(notes)

    def _create_github_release(self, repo_path, tag_name, title, description, is_prerelease, token):
        """Create release on GitHub"""
        import urllib.request
        import urllib.error
        import json
        
        url = f"https://api.github.com/repos/{repo_path}/releases"
        
        data = {
            "tag_name": tag_name,
            "name": title,
            "body": description,
            "draft": False,
            "prerelease": is_prerelease,
            "generate_release_notes": False
        }
        
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
            'User-Agent': 'Terminal-Notes/1.0'
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                print(f"\n  Release created successfully!")
                print(f"  URL: {result.get('html_url', 'N/A')}")
                return True
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ''
            print(f"\n  Failed to create release: HTTP {e.code}")
            if 'already_exists' in error_body:
                print("  A release for this tag already exists")
            elif e.code == 401:
                print("  Authentication failed - token may be invalid")
            elif e.code == 404:
                print("  Repository not found - check permissions")
            return False
        except Exception as e:
            print(f"\n  Failed to create release: {str(e)[:100]}")
            return False

    def _create_gitlab_release(self, repo_path, tag_name, title, description, is_prerelease, token):
        """Create release on GitLab"""
        import urllib.request
        import urllib.error
        import json
        
        # GitLab uses project ID or URL-encoded path
        project_path = repo_path.replace('/', '%2F')
        url = f"https://gitlab.com/api/v4/projects/{project_path}/releases"
        
        data = {
            "name": title,
            "tag_name": tag_name,
            "description": description
        }
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        try:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode())
                print(f"\n  Release created successfully!")
                print(f"  URL: {result.get('_links', {}).get('self', 'N/A')}")
                return True
        except urllib.error.HTTPError as e:
            error_body = e.read().decode() if e.fp else ''
            print(f"\n  Failed to create release: HTTP {e.code}")
            if 'already exists' in error_body.lower():
                print("  A release for this tag already exists")
            return False
        except Exception as e:
            print(f"\n  Failed to create release: {str(e)[:100]}")
            return False
    
    def create_release_from_tag(self, tag_name):
        """Create a release on GitHub/GitLab from an existing tag, checking online for existing releases"""
        token = self.get_token()
        username = self.config.get('github_username', '')
        
        if not token or not username:
            print("  Cannot create release: Missing authentication")
            return False
        
        # Get remote URL to determine platform
        remote_url_result = self.run_git_command("git remote get-url origin")
        if not remote_url_result['success']:
            print("  Cannot create release: No remote URL found")
            return False
        
        remote_url = remote_url_result['stdout'].strip()
        
        # Determine platform and extract repo path
        platform = None
        repo_path = None
        
        if 'github.com' in remote_url:
            platform = 'github'
            if 'github.com/' in remote_url:
                repo_path = remote_url.split('github.com/')[-1].replace('.git', '')
        elif 'gitlab.com' in remote_url:
            platform = 'gitlab'
            if 'gitlab.com/' in remote_url:
                repo_path = remote_url.split('gitlab.com/')[-1].replace('.git', '')
        else:
            print(f"  Release creation not supported for: {remote_url}")
            return False
        
        # Check if release already exists online
        print(f"\n  Checking if release already exists for {tag_name}...")
        release_exists = False
        existing_release_url = None
        
        if platform == 'github':
            import urllib.request
            import urllib.error
            import json
            
            url = f"https://api.github.com/repos/{repo_path}/releases/tags/{tag_name}"
            headers = {
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json',
                'User-Agent': 'Terminal-Notes/1.0'
            }
            
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as response:
                    if response.status == 200:
                        release_data = json.loads(response.read().decode())
                        release_exists = True
                        existing_release_url = release_data.get('html_url', '')
                        print(f"  Release already exists: {existing_release_url}")
                        return False
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    print(f"  No existing release found for {tag_name}, creating new release...")
                else:
                    print(f"  Error checking release: HTTP {e.code}")
                    return False
        
        # Find the last tag that HAS a release (not just any tag)
        print(f"\n  Finding last released tag before {tag_name}...")
        
        # Get all tags with their release status
        tags_result = self.run_git_command("git tag -l")
        all_tags = []
        if tags_result['success'] and tags_result['stdout'].strip():
            all_tags = [tag.strip() for tag in tags_result['stdout'].strip().split('\n') if tag.strip()]
            
            # Sort tags by version number
            import re
            def version_key(tag):
                match = re.search(r'v?(\d+)\.(\d+)\.(\d+)', tag)
                if match:
                    return tuple(map(int, match.groups()))
                return (0, 0, 0)
            
            all_tags.sort(key=version_key)
        
        # Find the last tag that has a release (check each tag from newest to oldest)
        last_released_tag = None
        for tag in reversed(all_tags):
            if tag == tag_name:
                continue
            
            # Check if this tag has a release
            if platform == 'github':
                url = f"https://api.github.com/repos/{repo_path}/releases/tags/{tag}"
                headers = {
                    'Authorization': f'token {token}',
                    'Accept': 'application/vnd.github.v3+json',
                    'User-Agent': 'Terminal-Notes/1.0'
                }
                
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as response:
                        if response.status == 200:
                            last_released_tag = tag
                            print(f"  Found last released tag: {last_released_tag}")
                            break
                except urllib.error.HTTPError:
                    continue
                except Exception:
                    continue
        
        # Get commits between the last released tag and current tag
        if last_released_tag:
            print(f"\n  Getting commits from {last_released_tag} to {tag_name}...")
            commits, _ = self.get_commits_between_tags(tag_name, last_released_tag)
        else:
            print(f"\n  No previous releases found. Getting all commits for {tag_name}...")
            commits, _ = self.get_commits_between_tags(tag_name, None)
        
        if commits:
            print(f"  Found {len(commits)} commits since {last_released_tag if last_released_tag else 'beginning'}")
            
            # Show commits preview
            print("\n  Commits to include:")
            for i, commit in enumerate(commits[:10], 1):
                first_line = commit.split('\n')[0]
                print(f"    {i}. {first_line[:80]}")
                if len(first_line) > 80:
                    print(f"       {first_line[80:]}")
            if len(commits) > 10:
                print(f"    ... and {len(commits)-10} more")
            
            generated_notes = self.generate_release_notes(tag_name, commits, last_released_tag)
        else:
            print("  No commits found")
            generated_notes = f"Release {tag_name}"
        
        # Show generated notes and ask for confirmation
        print("\n  " + "-" * 40)
        print("  Generated Release Notes:")
        print("  " + "-" * 40)
        note_lines = generated_notes.split('\n')
        for line in note_lines[:20]:
            print(f"  {line}")
        if len(note_lines) > 20:
            print(f"  ... and {len(note_lines)-20} more lines")
        print("  " + "-" * 40)
        
        use_auto = input("\n  Use auto-generated release notes? [Y/n/e to edit]: ").strip().lower()
        
        release_description = generated_notes
        if use_auto == 'n':
            print("\n  Enter release description (enter 'done' when finished):")
            description_lines = []
            while True:
                line = input("    ")
                if line.lower() == 'done':
                    break
                description_lines.append(line)
            release_description = '\n'.join(description_lines) if description_lines else generated_notes
        elif use_auto == 'e':
            # Open editor for manual editing
            import tempfile
            import subprocess
            
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.md', delete=False) as f:
                f.write(generated_notes)
                f.flush()
                temp_path = f.name
            
            editor = os.environ.get('EDITOR', 'micro')
            subprocess.call(f"{editor} {temp_path}", shell=True)
            
            with open(temp_path, 'r') as f:
                release_description = f.read()
            
            os.unlink(temp_path)
        
        # Release details
        print("\n  Release Information:")
        release_title = input(f"  Release title [{tag_name}]: ").strip()
        if not release_title:
            release_title = tag_name
        
        # Determine if pre-release
        is_prerelease = False
        if any(x in tag_name.lower() for x in ['alpha', 'beta', 'rc', 'pre']):
            prerelease_choice = input(f"  Tag '{tag_name}' looks like a pre-release. Mark as pre-release? [Y/n]: ").strip().lower()
            is_prerelease = prerelease_choice != 'n'
        else:
            prerelease_choice = input("  Is this a pre-release? [y/N]: ").strip().lower()
            is_prerelease = prerelease_choice == 'y'
        
        print("\n  " + "-" * 40)
        print("  Release Summary:")
        print(f"    Tag: {tag_name}")
        print(f"    Title: {release_title}")
        print(f"    Pre-release: {is_prerelease}")
        print(f"    Commits: {len(commits)}")
        if last_released_tag:
            print(f"    Since last release: {last_released_tag}")
        print("  " + "-" * 40)
        
        confirm = input("\n  Create release? [y/N]: ").strip().lower()
        if confirm != 'y':
            print("  Release creation cancelled")
            return False
        
        # Create release based on platform
        import urllib.request
        import urllib.error
        import json
        
        if platform == 'github':
            return self._create_github_release(repo_path, tag_name, release_title, release_description, is_prerelease, token)
        elif platform == 'gitlab':
            return self._create_gitlab_release(repo_path, tag_name, release_title, release_description, is_prerelease, token)
        else:
            print(f"  Release creation not implemented for {platform}")
            return False

    def manage_releases(self):
        """Manage releases for tags"""
        self.clear_screen()
        self.print_header("Release Management")
        
        # Get all tags
        tags_result = self.run_git_command("git tag -l")
        if not tags_result['success'] or not tags_result['stdout'].strip():
            print("No tags found. Create tags first using version tagging.")
            input("\nPress Enter to continue...")
            return
        
        tags = [tag.strip() for tag in tags_result['stdout'].strip().split('\n') if tag.strip()]
        
        print("Available tags:")
        for i, tag in enumerate(tags, 1):
            # Show tag info
            tag_date_result = self.run_git_command(f"git log -1 --format=%ai {tag}")
            tag_date = tag_date_result['stdout'].strip()[:10] if tag_date_result['success'] else "unknown"
            print(f"  [{i}] {tag} ({tag_date})")
        print("  [0] Back")
        print()
        
        choice = self.get_input("Select tag to create release: ")
        
        if choice == "0":
            return
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(tags):
                tag = tags[idx]
                self.create_release_from_tag(tag)
            else:
                print("Invalid choice")
        except ValueError:
            print("Invalid input")
        
        input("\nPress Enter to continue...")
    
    def push_branch(self, info):
        """Push to remote using stored token from Crypto with tag sync"""
        self.clear_screen()
        self.print_header("Push to Remote")
        
        if not info['remotes']:
            print("No remote configured. Please add a remote first.")
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
            print("  [0] Cancel")
            print()
            remote_choice = self.get_input("Enter number: ")
            
            if remote_choice == "0":
                print("\nOperation cancelled.")
                input("\nPress Enter to continue...")
                return
            
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
            print("Please set up token in Settings -> Manage tokens first.")
            input("\nPress Enter to continue...")
            return
        
        # Create authenticated URL for all operations
        auth_url = remote_url
        if 'https://' in remote_url:
            from urllib.parse import urlparse
            parsed = urlparse(remote_url)
            host = parsed.netloc
            path = parsed.path
            auth_url = f"https://{username}:{token}@{host}{path}"
        
        # Check tag synchronization
        print("\n" + "-" * 50)
        print("Checking tags...")
        
        tags_result = self.run_git_command("git tag -l")
        local_tags = []
        if tags_result['success'] and tags_result['stdout'].strip():
            local_tags = [tag.strip() for tag in tags_result['stdout'].strip().split('\n') if tag.strip()]
            print(f"Local tags: {len(local_tags)}")
        else:
            print("No local tags found")
        
        # Get remote tags using authenticated URL
        remote_tags = []
        if local_tags:
            print("Checking remote tags...")
            remote_tags_result = self.run_git_command(f"git ls-remote --tags {auth_url}")
            if remote_tags_result['success'] and remote_tags_result['stdout'].strip():
                for line in remote_tags_result['stdout'].strip().split('\n'):
                    if 'refs/tags/' in line:
                        tag = line.split('refs/tags/')[-1].replace('^{}', '')
                        if tag and tag not in remote_tags:
                            remote_tags.append(tag)
                print(f"Remote tags: {len(remote_tags)}")
            else:
                print("No remote tags found")
        
        # Determine tag differences
        tags_to_push = [tag for tag in local_tags if tag not in remote_tags]
        tags_to_delete = [tag for tag in remote_tags if tag not in local_tags]
        
        # Show tag differences
        if tags_to_push:
            print(f"\nTags to push: {len(tags_to_push)}")
            for tag in tags_to_push[:5]:
                print(f"  - {tag}")
            if len(tags_to_push) > 5:
                print(f"  ... and {len(tags_to_push)-5} more")
        
        if tags_to_delete:
            print(f"\nTags to delete from remote: {len(tags_to_delete)}")
            for tag in tags_to_delete[:5]:
                print(f"  - {tag}")
            if len(tags_to_delete) > 5:
                print(f"  ... and {len(tags_to_delete)-5} more")
        
        # Check commits ahead by comparing with remote directly
        print("\nChecking commits...")

        import subprocess
        import re

        # Define env for all git operations
        env = os.environ.copy()
        env.update({
            'GIT_ASKPASS': 'echo',
            'GIT_TERMINAL_PROMPT': '0'
        })

        # First, check if remote branch exists
        remote_branch_exists = False
        remote_commit_hash = None

        check_remote_cmd = ["git", "ls-remote", "--heads", auth_url, info['current_branch']]
        check_result = subprocess.run(
            check_remote_cmd,
            cwd=self.project_dir,
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )

        if check_result.returncode == 0 and check_result.stdout.strip():
            remote_branch_exists = True
            # Extract the remote commit hash from ls-remote output
            remote_commit_hash = check_result.stdout.strip().split()[0]
            print(f"  Remote branch exists at commit: {remote_commit_hash[:8]}")
            
            # Get local commit hash
            local_hash_result = self.run_git_command(f"git rev-parse {info['current_branch']}")
            local_commit_hash = local_hash_result['stdout'].strip() if local_hash_result['success'] else ""
            
            if local_commit_hash:
                print(f"  Local branch at commit: {local_commit_hash[:8]}")
                
                if remote_commit_hash == local_commit_hash:
                    commits_ahead = 0
                    print("  Local and remote are in sync")
                else:
                    # Try to find merge base
                    merge_base_result = self.run_git_command(f"git merge-base {info['current_branch']} {remote_commit_hash} 2>/dev/null")
                    if merge_base_result['success'] and merge_base_result['stdout'].strip():
                        merge_base = merge_base_result['stdout'].strip()
                        # Count commits from merge base to local HEAD
                        ahead_result = self.run_git_command(f"git rev-list --count {merge_base}..{info['current_branch']}")
                        if ahead_result['success'] and ahead_result['stdout'].strip():
                            commits_ahead = int(ahead_result['stdout'].strip())
                            print(f"  Local commits ahead of remote: {commits_ahead}")
                        else:
                            commits_ahead = 0
                    else:
                        # No common ancestor - check if remote has any commits
                        # Get total commits in remote
                        remote_total_result = self.run_git_command(f"git rev-list --count {remote_commit_hash}")
                        remote_total = int(remote_total_result['stdout'].strip()) if remote_total_result['success'] and remote_total_result['stdout'].strip() else 0
                        
                        if remote_total == 0:
                            # Remote has no commits - first real push
                            total_result = self.run_git_command(f"git rev-list --count HEAD")
                            if total_result['success'] and total_result['stdout'].strip():
                                commits_ahead = int(total_result['stdout'].strip())
                                print(f"  Remote has no commits, pushing all: {commits_ahead}")
                            else:
                                commits_ahead = 0
                        else:
                            # Different histories - count local commits not in remote
                            # Use git log with --not to exclude remote commits
                            not_in_remote = self.run_git_command(f"git rev-list --count HEAD --not {remote_commit_hash}")
                            if not_in_remote['success'] and not_in_remote['stdout'].strip():
                                commits_ahead = int(not_in_remote['stdout'].strip())
                                print(f"  Local commits not in remote: {commits_ahead}")
                            else:
                                # Fallback to asking user
                                print("  Branches have diverged with no common ancestor")
                                print("  This may happen if repositories have different histories")
                                choice = self.get_input("  Force push all local commits? [y/N]: ")
                                if choice.lower() == 'y':
                                    total_result = self.run_git_command(f"git rev-list --count HEAD")
                                    commits_ahead = int(total_result['stdout'].strip()) if total_result['success'] and total_result['stdout'].strip() else 0
                                else:
                                    commits_ahead = 0
        else:
            # Remote branch doesn't exist - this is a first push
            print("  Remote branch does not exist - first push")
            total_commits_result = self.run_git_command("git rev-list --count HEAD")
            if total_commits_result['success'] and total_commits_result['stdout'].strip():
                commits_ahead = int(total_commits_result['stdout'].strip())
                print(f"  First push: {commits_ahead} commit(s) to push")
            else:
                commits_ahead = info['ahead']

        # Double-check with git status for accuracy
        if commits_ahead == 0:
            status_result = self.run_git_command(f"git status -sb")
            if status_result['success'] and status_result['stdout']:
                # Look for "ahead X" pattern
                ahead_match = re.search(r'ahead[^\d]*(\d+)', status_result['stdout'])
                if ahead_match:
                    status_ahead = int(ahead_match.group(1))
                    if status_ahead > 0:
                        print(f"  Git status shows {status_ahead} commits ahead - correcting")
                        commits_ahead = status_ahead

        has_commits = commits_ahead > 0

        if has_commits:
            print(f"\nCommits to push: {commits_ahead}")
            # Show recent commits that need to be pushed
            if remote_branch_exists and remote_commit_hash:
                log_result = self.run_git_command(f"git log --oneline {remote_commit_hash}..{info['current_branch']} -{min(5, commits_ahead)}")
            else:
                log_result = self.run_git_command(f"git log --oneline -{min(5, commits_ahead)}")
            
            if log_result['success'] and log_result['stdout']:
                print("\nCommits to push:")
                for line in log_result['stdout'].strip().split('\n')[:5]:
                    print(f"  {line[:80]}")
        else:
            print("No commits to push")

        # Restore the original remote URL (without token) after checking
        restore_cmd = ["git", "remote", "set-url", remote, remote_url]
        subprocess.run(restore_cmd, cwd=self.project_dir, capture_output=True, text=True)
        
        # Ask about tag synchronization
        sync_tags = False
        tag_action = None
        
        if tags_to_push or tags_to_delete:
            print("\n" + "-" * 50)
            print("Tag Options:")
            print("  [1] Push new tags only")
            if tags_to_delete:
                print("  [2] Full sync (push new + delete removed tags)")
            else:
                print("  [2] Push new tags (only tags not on remote)")
            print("  [3] Skip tags, push commits only")
            print("  [0] Cancel entire operation")
            print()
            
            tag_choice = self.get_input("Choose [0-3]: ").strip()
            
            if tag_choice == "0":
                print("\nOperation cancelled.")
                input("\nPress Enter to continue...")
                return
            elif tag_choice == "1":
                sync_tags = True
                tag_action = "push_only"
                print("\nWill push new tags only")
            elif tag_choice == "2":
                sync_tags = True
                if tags_to_delete:
                    tag_action = "full_sync"
                    print(f"\nWill perform full sync: push {len(tags_to_push)} new + delete {len(tags_to_delete)} tags")
                else:
                    tag_action = "push_only"
                    print(f"\nWill push {len(tags_to_push)} new tag(s)")
            else:
                print("\nSkipping tag operations, pushing commits only")
        else:
            if not has_commits:
                print("\nNo commits or tags to sync")
                input("\nPress Enter to continue...")
                return
            else:
                print("\nNo tag operations needed, pushing commits only")
        
        # Confirm before pushing
        print("\n" + "-" * 50)
        if not has_commits and sync_tags and tags_to_push:
            confirm = input("Push tags only? [y/N]: ").strip().lower()
        elif has_commits and not sync_tags:
            confirm = input("Push commits only? [y/N]: ").strip().lower()
        else:
            confirm = input("Proceed with push? [y/N]: ").strip().lower()
        
        if confirm != 'y':
            print("\nOperation cancelled.")
            input("\nPress Enter to continue...")
            return
        
        print("\nPushing to remote...")
        
        import subprocess
        
        try:
            success = True
            
            # Delete tags from remote if doing full sync
            if sync_tags and tag_action == "full_sync" and tags_to_delete:
                print("\nDeleting removed tags from remote...")
                for tag in tags_to_delete:
                    delete_cmd = ["git", "push", auth_url, f":refs/tags/{tag}"]
                    
                    delete_result = subprocess.run(
                        delete_cmd,
                        cwd=self.project_dir,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if delete_result.returncode == 0:
                        print(f"  Deleted: {tag}")
                    else:
                        print(f"  Failed to delete: {tag}")
                        success = False
            
            # Push commits and tags
            need_to_push = has_commits or (sync_tags and tags_to_push)

            # Define env for all git operations
            env = os.environ.copy()
            env.update({
                'GIT_ASKPASS': 'echo',
                'GIT_TERMINAL_PROMPT': '0'
            })

            if need_to_push:
                # Build push command
                if has_upstream:
                    cmd = ["git", "push", auth_url, info['current_branch']]
                else:
                    cmd = ["git", "push", "-u", auth_url, info['current_branch']]
                
                # Add tags only if we have new tags to push
                if sync_tags and tags_to_push:
                    # Push commits first, then tags separately
                    if has_commits:
                        print(f"Pushing {commits_ahead} commit(s)...")
                        result = subprocess.run(
                            cmd,
                            cwd=self.project_dir,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.returncode != 0:
                            success = False
                            print(f"\nPush failed: {result.stderr[:500]}")
                        else:
                            print("Commits pushed successfully")
                    
                    # Push new tags one by one
                    if tags_to_push:
                        print(f"\nPushing {len(tags_to_push)} new tag(s)...")
                        for tag in tags_to_push:
                            tag_cmd = ["git", "push", auth_url, tag]
                            tag_result = subprocess.run(
                                tag_cmd,
                                cwd=self.project_dir,
                                env=env,
                                capture_output=True,
                                text=True,
                                timeout=30
                            )
                            if tag_result.returncode == 0:
                                print(f"  Pushed tag: {tag}")
                            else:
                                if "already exists" in tag_result.stderr:
                                    print(f"  Tag already exists on remote: {tag}")
                                else:
                                    print(f"  Failed to push tag: {tag}")
                                    success = False
                else:
                    # Just push commits (no tags)
                    if has_commits:
                        print(f"Pushing {commits_ahead} commit(s)...")
                        result = subprocess.run(
                            cmd,
                            cwd=self.project_dir,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=60
                        )
                        if result.returncode != 0:
                            success = False
                            print(f"\nPush failed: {result.stderr[:500]}")
                        else:
                            print("\nPush successful")
            
            # Report results
            if success:
                if sync_tags and tags_to_push:
                    print(f"\nPushed {len(tags_to_push)} new tag(s)")
                
                if has_commits:
                    print(f"Pushed {commits_ahead} commit(s)")
                
                # Update last push time
                self.config['last_sync'] = datetime.now().isoformat()
                self.save_config()
                
                # Ask about creating releases for newly pushed tags
                if tags_to_push and sync_tags:
                    print("\n" + "-" * 50)
                    create_releases = input("Create releases for new tags? [y/N]: ").strip().lower()
                    if create_releases == 'y':
                        print("\nWhich tags to create releases for?")
                        print("  [1] All new tags")
                        print("  [2] Select specific tags")
                        print("  [3] Cancel")
                        
                        tag_choice = input("\nChoose [1-3]: ").strip()
                        
                        if tag_choice == "1":
                            tags_for_release = tags_to_push
                        elif tag_choice == "2":
                            print("\nSelect tags (comma-separated numbers):")
                            for i, tag in enumerate(tags_to_push, 1):
                                print(f"  [{i}] {tag}")
                            
                            selection = input("\nEnter numbers: ").strip()
                            try:
                                indices = [int(x.strip()) - 1 for x in selection.split(',')]
                                tags_for_release = [tags_to_push[i] for i in indices if 0 <= i < len(tags_to_push)]
                            except:
                                print("  Invalid selection")
                                tags_for_release = []
                        else:
                            tags_for_release = []
                        
                        if tags_for_release:
                            print(f"\nCreating releases for {len(tags_for_release)} tag(s)...")
                            for tag in tags_for_release:
                                print(f"\n  Processing tag: {tag}")
                                self.create_release_from_tag(tag)
                                
                                if tag != tags_for_release[-1]:
                                    continue_choice = input("\n  Continue to next tag? [Y/n]: ").strip().lower()
                                    if continue_choice == 'n':
                                        print("  Stopping release creation")
                                        break
                        else:
                            print("\nNo tags selected for release creation")
                    else:
                        print("\nSkipping release creation")
            
        except subprocess.TimeoutExpired:
            print("\nPush timed out after 60 seconds")
            success = False
        except Exception as e:
            print(f"\nPush error: {str(e)[:200]}")
            success = False
        
        if not success:
            print("\nPush completed with errors")
        
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
            print("4. Commit Changes")
            print("5. Configure Settings")
            print("6. Initialize Repository (if needed)")
            print("7. Exit")  # <-- CHANGE THIS FROM 7 to 8
            print()
            
            choice = self.get_input("Select option [1-8]: ")  # <-- CHANGE THIS FROM 1-7 to 1-8
            
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