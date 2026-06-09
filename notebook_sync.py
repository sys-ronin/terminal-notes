#!/usr/bin/env python3
"""
Notebook Sync - Linear History Reconstruction with Per-UUID Conflict Resolution

DESIGN PRINCIPLES:
1. Each commit changes exactly ONE UUID (note, file, or subnotebook)
2. Commits are complete snapshots of notes.json, files.json, structure.json (raw encrypted blobs)
3. Sync collects all commits from local and remote, groups by UUID
4. For each UUID, keep the chain whose last commit is newer (discard the other chain)
5. Merge all winning commits, sort by timestamp, replay on orphan branch
6. Replace original branch with linear history, force push
7. No JSON parsing, no decryption conflicts, no merge commits

PLATFORM SUPPORT:
- Linux, macOS, Windows (cross-platform)
- GitHub, GitLab, Bitbucket, Gitea (self-hosted)
"""

import os
import sys
import json
import subprocess
import time
import re
import base64
import socket
from datetime import datetime
from typing import Dict, List, Optional, Set
from collections import defaultdict


class NotebookSync:
    """Linear history reconstruction with per-UUID conflict resolution"""

    def __init__(self, manager, accounts, app_dir, ui_callback=None, confirm_callback=None):
        self.manager = manager
        self.accounts = accounts
        self.app_dir = app_dir
        self.ui = ui_callback or print
        self.confirm = confirm_callback or self._default_confirm

    def _default_confirm(self, prompt):
        return input(prompt).strip().lower() == 'y'

    def _log(self, message, end="\n"):
        if self.ui:
            self.ui(message, end=end)

    def _ask_confirmation(self, description: str) -> bool:
        self._log(description)
        self._log("")
        confirm = input("  Proceed? [y/N]: ").strip().lower()
        return confirm == 'y'

    # ------------------------------------------------------------------------
    # Public Entry Point
    # ------------------------------------------------------------------------
    def execute(self, notebook):
        return self.sync_notebook(notebook)

    def sync_notebook(self, notebook):
        """Main sync orchestrator with sequential progress updates"""
        self.clear_screen()
        
        # ========== SIMPLE SEQUENTIAL PROGRESS ==========
        print()
        print(" " * 60)
        print("  Syncing your notebook...")
        print(" " * 60)
        print()
        
        # Step 1
        print("  → Checking your connection")
        if not self._has_internet():
            self._log("  No internet connection.")
            self._log("  Press Enter to continue...")
            input()
            return False
        print("  ✓ Connection confirmed")
        
        # Step 2
        print("  → Verifying your account")
        git_config = notebook.get("git_config")
        account = notebook.get("account")
        if not git_config or not account:
            self._log("  Not configured with a remote repository.")
            self._log("  Press Enter to continue...")
            input()
            return False
        
        token = self._decrypt_token(account.get('token_enc', ''))
        if not token:
            self._log("  Could not decrypt account token.")
            self._log("  Press Enter to continue...")
            input()
            return False
        
        if not self._check_token_valid(account, token):
            self._log("  Account token is invalid or expired.")
            self._log("  Press Enter to continue...")
            input()
            return False
        print("  ✓ Account verified")
        
        # Step 3
        print("  → Looking for updates")
        print()
        print("  Connecting to the cloud...")
        print()
        
        # Continue with the rest of sync
        path = notebook.get('path')
        if not path or not os.path.exists(path):
            self._log("  Notebook path not found.")
            self._log("  Press Enter to continue...")
            input()
            return False

        repo_name = os.path.basename(path).replace('.git', '')
        
        # Git init if needed
        git_dir = os.path.join(path, ".git")
        if not os.path.exists(git_dir):
            subprocess.run(["git", "init"], cwd=path, capture_output=True)

        # Setup remote
        auth_url = self._build_repo_url(account, repo_name).replace(
            "https://", f"https://{account['username']}:{token}@"
        )
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"], cwd=path, capture_output=True
        )
        if remote_result.returncode != 0:
            subprocess.run(["git", "remote", "add", "origin", auth_url], cwd=path)

        # Check if remote repo exists
        repo_exists = self._repo_exists(account, repo_name, token)
        if not repo_exists:
            result = self._create_and_push(notebook, account, repo_name, token, path, git_config)
            self._log("  Press Enter to continue...")
            input()
            return result

        # Fetch latest remote
        self._log("  Fetching remote changes...", end="")
        subprocess.run(["git", "fetch", "origin"], cwd=path)
        self._log(" Done")
        
        print()
        print("  ✓ Looking for updates - complete")
        print()

        # ========== STEP 2: COLLECT NORMAL COMMITS (existing code) ==========
        local_commits = self._get_commits_with_uuids(path, "HEAD")
        remote_commits = self._get_commits_with_uuids(path, "origin/master")
        
        # ========== STEP 3: COLLECT SECURITY COMMITS (NEW) ==========
        local_security = self._get_security_commits(path, "HEAD")
        remote_security = self._get_security_commits(path, "origin/master")
        
        # ========== MERGE ALL COMMITS FOR HASH COMPARISON (NEW) ==========
        all_local = local_commits + local_security
        all_remote = remote_commits + remote_security
        
        local_hashes = {c['hash'] for c in all_local}
        remote_hashes = {c['hash'] for c in all_remote}
        
        hashes_only_local = local_hashes - remote_hashes
        hashes_only_remote = remote_hashes - local_hashes
        
        # ========== DETECT SECURITY COMMITS IN THE DIFFERENCE (NEW) ==========
        local_security_hashes = {c['hash'] for c in local_security}
        remote_security_hashes = {c['hash'] for c in remote_security}
        
        has_security_local = bool(local_security_hashes & hashes_only_local)
        has_security_remote = bool(remote_security_hashes & hashes_only_remote)
        # ========== END NEW ==========

        result = True
        
        # Case 1: Already in sync
        if len(hashes_only_local) == 0 and len(hashes_only_remote) == 0:
            self._log("  Your notebook is already up to date.")
            self._log("  Press Enter to continue...")
            input()
            return True

        # Case 2: Only local has new commits
        if len(hashes_only_local) > 0 and len(hashes_only_remote) == 0:
            self.clear_screen()
            
            # ========== ADD SECURITY COMMIT MESSAGE (NEW) ==========
            if has_security_local:
                print("  You have a password change ready to share.")
                print()
                print("  What will happen:")
                print("  • Your new password will be saved to the cloud")
                print("  • Your notebook will stay unlocked on this machine")
                print()
            else:
                desc = f"  Your local notebook has {len(hashes_only_local)} update(s) ready to share.\n\n  What will happen:\n  • Your changes will be saved to the cloud"
            # ========== END NEW ==========
            
            if self._ask_confirmation(desc if not has_security_local else None):
                result = self._simple_push(path, len(hashes_only_local))
            else:
                result = False

        # Case 3: Only remote has new commits
        elif len(hashes_only_remote) > 0 and len(hashes_only_local) == 0:
            self.clear_screen()
            
            # ========== ADD SECURITY COMMIT MESSAGE (NEW) ==========
            if has_security_remote:
                print("  The cloud has a password change ready for you.")
                print()
                print("  What will happen:")
                print("  • Your password will be updated")
                print("  • Your notebook will be locked after sync")
                print("  • Use your new password to unlock")
                print()
            else:
                desc = f"  The cloud has {len(hashes_only_remote)} update(s) ready for you.\n\n  What will happen:\n  • Your notebook will be updated with the latest content"
            # ========== END NEW ==========
            
            if self._ask_confirmation(desc if not has_security_remote else None):
                result = self._simple_pull(path, len(hashes_only_remote))
                # ========== IF SECURITY COMMIT WAS PULLED, UPDATE VAULT (NEW) ==========
                if result and has_security_remote:
                    # Get the newest security commit from remote
                    remote_security_sorted = sorted(remote_security, key=lambda c: c['timestamp'])
                    newest_security = remote_security_sorted[-1] if remote_security_sorted else None
                    if newest_security:
                        self._update_vault_for_security_commit(path, notebook, newest_security)
                        notebook['locked'] = True
                        print()
                        print("  Your password has been updated from the cloud.")
                        print("  Your notebook is now locked. Use your new password to unlock.")
                # ========== END NEW ==========
            else:
                result = False

        # Case 4: Both sides have unique commits - reconstruct
        else:
            # ========== PASS SECURITY COMMITS TO HANDLER (NEW) ==========
            result = self._handle_diverged_history(
                path, notebook, account, 
                local_commits, remote_commits,
                local_security, remote_security
            )
            # ========== END NEW ==========
        
        # ========== FORCE RELOAD NOTEBOOK DATA AFTER SYNC ==========
        if result:
            # Refresh the notebook object with latest data
            fresh_notebook = self.manager.find_notebook_by_id(notebook.get('id'))
            if fresh_notebook:
                # Update counts
                total_notes = fresh_notebook.get_total_note_count()
                total_files = fresh_notebook.get_file_note_count()
                notebook['note_count'] = total_notes - total_files
                notebook['file_count'] = total_files
                notebook['sub_count'] = fresh_notebook.get_total_subnotebook_count()
                notebook['locked'] = fresh_notebook.locked
                notebook['path'] = fresh_notebook.custom_path
        # ========== END RELOAD ==========
        
        # Wait for user acknowledgment before returning
        self._log("")
        self._log("  Press Enter to continue...")
        input()
        
        return result

    def _handle_diverged_history(self, path, notebook, account, local_commits, remote_commits,
                                    local_security=None, remote_security=None):
        """Handle diverged histories with reconstruction (normal + security commits)"""
        
        if local_security is None:
            local_security = []
        if remote_security is None:
            remote_security = []
        
        # Check for common ancestor (filter-repo case)
        has_common = self._has_common_ancestor(path)

        if not has_common:
            return self._handle_no_common_ancestor(path, notebook, account)

        # Build chains from NORMAL commits only (security commits excluded)
        local_chains = self._build_uuid_chains(local_commits)
        remote_chains = self._build_uuid_chains(remote_commits)
        
        # Resolve conflicts for normal commits only
        winning_normal = self._resolve_and_merge_chains(local_chains, remote_chains)
        
        # ========== HANDLE SECURITY COMMITS SEPARATELY ==========
        # ALL security commits from both sides, keep ALL of them
        all_security = local_security + remote_security
        all_security.sort(key=lambda c: c['timestamp'])
        
        # Determine if remote has a newer security commit than local
        remote_has_newer = False
        
        if remote_security and local_security:
            remote_newest = sorted(remote_security, key=lambda c: c['timestamp'])[-1]
            local_newest = sorted(local_security, key=lambda c: c['timestamp'])[-1]
            if remote_newest['timestamp'] > local_newest['timestamp']:
                remote_has_newer = True
        elif remote_security and not local_security:
            remote_has_newer = True
        
        # Combine: winning normal commits + ALL security commits
        winning_commits = winning_normal + all_security
        winning_commits.sort(key=lambda c: c['timestamp'])
        
        if not winning_commits:
            self._log("  No commits to replay.")
            return True

        # Show description and confirm
        description = self._build_reconstruction_description(local_chains, remote_chains, winning_commits)
        if not self._ask_confirmation(description):
            self._log("  Sync cancelled.")
            return False

        # Reconstruct linear history (pass security commits)
        success = self._reconstruct_linear_history(
            path, local_commits, remote_commits, winning_commits,
            has_security=len(all_security) > 0, all_security=all_security
        )
        
        if success:
            # ========== POST-RECONSTRUCTION VAULT UPDATE ==========
            if all_security:
                all_security_sorted = sorted(all_security, key=lambda c: c['timestamp'])
                newest_security = all_security_sorted[-1]
                
                if remote_has_newer:
                    self._update_vault_for_security_commit(path, notebook, newest_security)
                    notebook['locked'] = True
                    print()
                    print("  Your password has been updated from the cloud.")
                    print("  Your notebook is now locked. Use your new password to unlock.")
                else:
                    # Count how many normal changes were also synced
                    normal_changes_count = len(winning_normal)
                    if normal_changes_count > 0 and local_security:
                        print()
                        print("  Your password change and updates have been saved to the cloud.")
                    elif local_security:
                        print()
                        print("  Your password change has been saved to the cloud.")
            
            self._update_last_push(notebook, account)
            self._log("")
            self._log("  Sync complete! Linear history reconstructed.")
        else:
            self._log("")
            self._log("  Sync failed!")

        return success

    def _handle_no_common_ancestor(self, path, notebook, account):
        """Handle case where local and remote have no common ancestor"""
        self.clear_screen()
        
        local_last_ts = self._get_branch_timestamp(path, "HEAD")
        remote_last_ts = self._get_branch_timestamp(path, "origin/master")
        local_commit_count = self._get_branch_commit_count(path, "HEAD")
        remote_commit_count = self._get_branch_commit_count(path, "origin/master")

        # Case 1: Remote has newer changes (by timestamp)
        if remote_last_ts > local_last_ts:
            return self._show_sync_decision(
                path, notebook, account,
                title="Update Available",
                message="The online version has newer changes than your local copy.",
                primary="Your notebook will be updated with the latest changes",
                secondary="Your local changes will be replaced"
            )
        # Case 2: Local has newer changes (by timestamp)
        elif local_last_ts > remote_last_ts:
            return self._show_sync_decision(
                path, notebook, account,
                title="Share Your Changes",
                message="Your local copy has newer changes than the online version.",
                primary="Your changes will become the main version",
                secondary="The online version will be updated to match you"
            )
        # Case 3: Timestamps are equal - compare commit counts to determine which has "more"
        else:
            if remote_commit_count > local_commit_count:
                # Remote has more commits (not necessarily "newer", just more)
                return self._show_sync_decision(
                    path, notebook, account,
                    title="Update Available",
                    message="The online version has additional changes that you don't have.",
                    primary="Your notebook will be updated with the missing changes",
                    secondary="Your existing changes will stay as they are"
                )
            elif local_commit_count > remote_commit_count:
                # Local has more commits
                return self._show_sync_decision(
                    path, notebook, account,
                    title="Share Your Changes",
                    message="Your local copy has additional changes that are not online yet.",
                    primary="Your missing changes will be saved to the cloud",
                    secondary="The online version will be updated to match you"
                )
            else:
                # Equal commit counts but different content - BOTH SIDES HAVE UNIQUE CHANGES
                return self._show_sync_decision(
                    path, notebook, account,
                    title="Sync Your Notebook",
                    message="Your local notebook and the online version both have new changes.",
                    primary="Changes from both sides will be combined",
                    secondary="Your complete notebook will be saved in both places"
                )

    def _show_sync_decision(self, path, notebook, account, title, message, primary, secondary):
        """Show a clean sync decision screen - fully left corner aligned"""
        self.clear_screen()
        
        print(f"{title}")
        print()
        print(f"{message}")
        print()
        print("What will happen:")
        print()
        print(f"  {primary}")
        print(f"  {secondary}")
        print()
        print("Do you want to proceed?")
        print()
        
        confirm = input("Yes or No [y/N]: ").strip().lower()
        
        if confirm == 'y':
            self.clear_screen()
            if "online version has newer" in message or "updated with the latest" in primary:
                result = self._sync_from_remote(path, notebook, account)
            else:
                result = self._sync_to_remote(path, notebook, account)
            
            # Show final result without any intermediate output
            self.clear_screen()
            if result:
                print(f"{title}")
                print()
                print("Done.")
            return result
        return False

    def _sync_from_remote(self, path, notebook, account):
        """Apply remote changes to local - silent operation"""
        result = subprocess.run(
            ["git", "reset", "--hard", "origin/master"],
            cwd=path, capture_output=True, text=True
        )
        if result.returncode != 0:
            return False
        
        try:
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
            metadata = ops.get_notebook_metadata(notebook.get('id'))
            if metadata:
                notebook['note_count'] = metadata.get('note_count', 0)
                notebook['file_count'] = metadata.get('file_count', 0)
                notebook['sub_count'] = metadata.get('sub_count', 0)
        except:
            pass
        
        self._update_last_push(notebook, account)
        return True

    def _sync_to_remote(self, path, notebook, account):
        """Upload local changes to remote - silent operation"""
        branch = self._get_current_branch(path)
        result = subprocess.run(
            ["git", "push", "--force", "origin", branch],
            cwd=path, capture_output=True, text=True
        )
        if result.returncode != 0:
            return False
        self._update_last_push(notebook, account)
        return True

    def clear_screen(self):
        """Clear terminal screen"""
        os.system('cls' if os.name == 'nt' else 'clear')

    # ------------------------------------------------------------------------
    # Helper Methods
    # ------------------------------------------------------------------------
    def _get_parent_commit(self, repo_path: str, commit_hash: str) -> Optional[str]:
        try:
            cmd = ["git", "rev-parse", f"{commit_hash}^"]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        return None

    def _has_common_ancestor(self, repo_path: str) -> bool:
        try:
            cmd = ["git", "merge-base", "HEAD", "origin/master"]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            return result.returncode == 0 and bool(result.stdout.strip())
        except:
            return False

    def _get_branch_timestamp(self, repo_path: str, branch: str) -> int:
        try:
            cmd = ["git", "log", "-1", "--format=%ct", branch]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except:
            pass
        return 0

    def _get_branch_commit_count(self, repo_path: str, branch: str) -> int:
        try:
            cmd = ["git", "rev-list", "--count", branch]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except:
            pass
        return 0

    def _get_current_branch(self, path: str) -> str:
        try:
            res = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=path, capture_output=True, text=True
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except:
            pass
        return "master"

    def _get_raw_blob(self, repo_path: str, commit_hash: str, filename: str) -> Optional[bytes]:
        cmd = ["git", "show", f"{commit_hash}:{filename}"]
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True)
        if result.returncode == 0 and result.stdout:
            return result.stdout
        return None

    def _write_raw_file(self, repo_path: str, filename: str, content: Optional[bytes]):
        filepath = os.path.join(repo_path, filename)
        if content is None:
            if os.path.exists(filepath):
                os.unlink(filepath)
        else:
            with open(filepath, 'wb') as f:
                f.write(content)

    def _write_json_encrypted(self, repo_path: str, filename: str, data: Dict, crypto) -> None:
        import json
        filepath = os.path.join(repo_path, filename)
        json_str = json.dumps(data, indent=2, ensure_ascii=False)
        encrypted = crypto.encrypt(json_str)
        with open(filepath, 'wb') as f:
            f.write(encrypted)

    # ------------------------------------------------------------------------
    # Commit Collection and UUID Extraction
    # ------------------------------------------------------------------------
    def _get_commits_with_uuids(self, repo_path: str, ref: str) -> List[Dict]:
        """Get normal commits (NOT security commits)"""
        commits = []
        cmd = ["git", "rev-list", "--no-merges", "--grep", "--not", "--grep", "SECURITY:", ref]
        # OR simpler: get all commits, filter later
        cmd = ["git", "rev-list", "--no-merges", ref]
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout:
            return commits

        hashes = [h.strip() for h in result.stdout.strip().split('\n') if h.strip()]
        for commit_hash in hashes:
            fmt_cmd = ["git", "log", "-1", "--format=%an|%ae|%ct|%B", commit_hash]
            fmt_res = subprocess.run(fmt_cmd, cwd=repo_path, capture_output=True, text=True)
            if fmt_res.returncode != 0:
                continue
            parts = fmt_res.stdout.strip().split('|', 3)
            if len(parts) < 4:
                continue
            author_name, author_email, ts_str, message = parts
            timestamp = int(ts_str)

            # SKIP security commits in normal collection
            if "SECURITY:" in message:
                continue

            uuid = self._extract_uuid_from_message(message)
            if not uuid:
                continue

            commits.append({
                'hash': commit_hash,
                'uuid': uuid,
                'timestamp': timestamp,
                'author_name': author_name,
                'author_email': author_email,
                'message': message,
                'notes_raw': self._get_raw_blob(repo_path, commit_hash, "notes.json"),
                'files_raw': self._get_raw_blob(repo_path, commit_hash, "files.json"),
                'struct_raw': self._get_raw_blob(repo_path, commit_hash, "structure.json")
            })

        commits.sort(key=lambda c: c['timestamp'])
        return commits


    def _extract_uuid_from_message(self, message: str) -> Optional[str]:
        patterns = [
            r'uuid:([a-f0-9-]+)',
            r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}',
            r'\b(\d{14})\b'
        ]
        for pattern in patterns:
            m = re.search(pattern, message, re.IGNORECASE)
            if m:
                return m.group(1) if '(' in pattern else m.group(0)
        return None

    # ------------------------------------------------------------------------
    # Per-UUID Chain Building and Conflict Resolution
    # ------------------------------------------------------------------------
    def _build_uuid_chains(self, commits: List[Dict]) -> Dict[str, List[Dict]]:
        """Build UUID chains - EXCLUDES security commits (they are handled separately)"""
        chains = defaultdict(list)
        for c in commits:
            # Skip security commits - they don't belong to any UUID chain
            if c.get('uuid') == 'SECURITY' or c.get('is_security'):
                continue
            chains[c['uuid']].append(c)
        return dict(chains)

    def _resolve_and_merge_chains(self, local_chains: Dict, remote_chains: Dict) -> List[Dict]:
        all_uuids = set(local_chains.keys()) | set(remote_chains.keys())
        winning = []

        for uuid in all_uuids:
            local = local_chains.get(uuid, [])
            remote = remote_chains.get(uuid, [])

            if local and not remote:
                winning.extend(local)
            elif remote and not local:
                winning.extend(remote)
            else:
                local_last_ts = local[-1]['timestamp']
                remote_last_ts = remote[-1]['timestamp']
                if remote_last_ts > local_last_ts:
                    winning.extend(remote)
                else:
                    winning.extend(local)

        winning.sort(key=lambda c: c['timestamp'])
        return winning

    # ------------------------------------------------------------------------
    # Linear History Reconstruction
    # ------------------------------------------------------------------------
    def _reconstruct_linear_history(self, repo_path: str, local_commits: List[Dict],
                                        remote_commits: List[Dict], winning_commits: List[Dict],
                                        has_security: bool = False, all_security: List[Dict] = None) -> bool:
        """Reconstruct linear history with full subnotebook hierarchy and security commit support"""
        
        self._log("  Reconstructing linear history from all commits...")

        # Get crypto key
        crypto = self._get_crypto_for_path(repo_path)
        if not crypto:
            self._log("  ERROR: Cannot decrypt without crypto key")
            return False

        from notebook_operations import read_bytes

        # Backup TN files (only if no security commit will be applied)
        marker_backups = {}
        if not has_security:
            marker_files = ['.tn_test', '.tn_recovery', '.tn_password']
            for marker in marker_files:
                marker_path = os.path.join(repo_path, marker)
                if os.path.exists(marker_path):
                    with open(marker_path, 'rb') as f:
                        marker_backups[marker] = f.read()

        # Get notebook ID and name from repo path
        folder_name = os.path.basename(repo_path)
        if '-' in folder_name:
            notebook_name = folder_name.split('-')[0]
            notebook_id = folder_name.split('-')[-1]
        else:
            notebook_name = folder_name
            notebook_id = folder_name

        # Save current branch
        current_branch = self._get_current_branch(repo_path)

        # Create orphan branch
        temp_branch = "temp-linear-reconstruction"
        subprocess.run(["git", "checkout", "--orphan", temp_branch], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "rm", "-rf", "."], cwd=repo_path, capture_output=True)

        # Restore marker files from backup (only if no security commit)
        if not has_security and marker_backups:
            for marker, content in marker_backups.items():
                with open(os.path.join(repo_path, marker), 'wb') as f:
                    f.write(content)
                subprocess.run(["git", "add", marker], cwd=repo_path, capture_output=True)

        # Initialize state
        current_notes = {}
        current_files = {}
        current_struct = {
            "id": notebook_id,
            "name": notebook_name,
            "parent_id": None,
            "notes": [],
            "files": [],
            "subnotebooks": []
        }

        # Get common ancestor
        common_hash = None
        try:
            cmd = ["git", "merge-base", "HEAD", "origin/master"]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                common_hash = result.stdout.strip()
        except:
            pass

        # Apply common ancestor state if exists
        if common_hash:
            common_notes_raw = self._get_raw_blob(repo_path, common_hash, "notes.json")
            common_files_raw = self._get_raw_blob(repo_path, common_hash, "files.json")
            common_struct_raw = self._get_raw_blob(repo_path, common_hash, "structure.json")

            if common_notes_raw:
                notes_data = read_bytes(common_notes_raw, crypto)
                if notes_data:
                    current_notes = notes_data
            if common_struct_raw:
                struct_data = read_bytes(common_struct_raw, crypto)
                if struct_data:
                    current_struct = struct_data

            self._write_json_encrypted(repo_path, "notes.json", current_notes, crypto)
            self._write_json_encrypted(repo_path, "files.json", current_files, crypto)
            self._write_json_encrypted(repo_path, "structure.json", current_struct, crypto)
            subprocess.run(["git", "add", "notes.json", "files.json", "structure.json"], cwd=repo_path, capture_output=True)

            # Commit common ancestor
            cmd = ["git", "log", "-1", "--format=%an|%ae|%ct|%B", common_hash]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            if result.returncode == 0:
                parts = result.stdout.strip().split('|', 3)
                if len(parts) >= 4:
                    author_name, author_email, ts_str, msg = parts
                    timestamp = int(ts_str)
                    env = os.environ.copy()
                    env['GIT_AUTHOR_NAME'] = author_name
                    env['GIT_AUTHOR_EMAIL'] = author_email
                    env['GIT_AUTHOR_DATE'] = f"@{timestamp}"
                    env['GIT_COMMITTER_NAME'] = author_name
                    env['GIT_COMMITTER_EMAIL'] = author_email
                    env['GIT_COMMITTER_DATE'] = f"@{timestamp}"
                    subprocess.run(["git", "commit", "-m", msg], cwd=repo_path, env=env, capture_output=True)
        else:
            self._write_json_encrypted(repo_path, "notes.json", current_notes, crypto)
            self._write_json_encrypted(repo_path, "files.json", current_files, crypto)
            self._write_json_encrypted(repo_path, "structure.json", current_struct, crypto)
            subprocess.run(["git", "add", "notes.json", "files.json", "structure.json"], cwd=repo_path, capture_output=True)
            subprocess.run(["git", "commit", "-m", "Initial state"], cwd=repo_path, capture_output=True)

        # Track subnotebook content recursively
        def collect_all_note_ids_from_subnotebooks(struct, target_set):
            for sub in struct.get('subnotebooks', []):
                for note in sub.get('notes', []):
                    if note.get('id'):
                        target_set.add(note['id'])
                for file_item in sub.get('files', []):
                    if file_item.get('id'):
                        target_set.add(file_item['id'])
                collect_all_note_ids_from_subnotebooks(sub, target_set)
        
        def merge_subnotebooks_recursively(target_struct, source_struct):
            target_subs = {sub.get('id'): sub for sub in target_struct.get('subnotebooks', [])}
            source_subs = {sub.get('id'): sub for sub in source_struct.get('subnotebooks', [])}
            for sub_id, source_sub in source_subs.items():
                if sub_id not in target_subs:
                    target_struct.setdefault('subnotebooks', []).append(source_sub.copy())
                else:
                    target_sub = target_subs[sub_id]
                    merge_subnotebooks_recursively(target_sub, source_sub)

        # Replay commits in timestamp order
        for commit in winning_commits:
            is_security = commit.get('is_security', False) or commit.get('uuid') == 'SECURITY'
            changed = False

            # Handle NORMAL commits
            if not is_security and commit.get('notes_raw'):
                notes_data = read_bytes(commit['notes_raw'], crypto)
                if notes_data:
                    for uuid, content in notes_data.items():
                        if uuid not in current_notes:
                            current_notes[uuid] = content
                            changed = True
                        elif content != current_notes[uuid]:
                            current_notes[uuid] = content
                            changed = True

            if not is_security and commit.get('files_raw'):
                files_data = read_bytes(commit['files_raw'], crypto)
                if files_data:
                    for uuid, content in files_data.items():
                        if uuid not in current_files:
                            current_files[uuid] = content
                            changed = True

            if not is_security and commit.get('struct_raw'):
                struct_data = read_bytes(commit['struct_raw'], crypto)
                if struct_data:
                    for note in struct_data.get('notes', []):
                        note_id = note.get('id')
                        if note_id:
                            existing = next((n for n in current_struct.get('notes', []) if n.get('id') == note_id), None)
                            if existing:
                                existing['title'] = note.get('title', existing.get('title', 'Untitled'))
                                existing['updated'] = note.get('updated', existing.get('updated', 0))
                            else:
                                current_struct.setdefault('notes', []).append(note.copy())
                            changed = True
                    
                    for file_item in struct_data.get('files', []):
                        file_id = file_item.get('id')
                        if file_id:
                            existing = next((f for f in current_struct.get('files', []) if f.get('id') == file_id), None)
                            if not existing:
                                current_struct.setdefault('files', []).append(file_item.copy())
                                changed = True
                    
                    merge_subnotebooks_recursively(current_struct, struct_data)
                    changed = True

            # Handle SECURITY commits
            if is_security:
                if commit.get('tn_recovery_raw'):
                    self._write_raw_file(repo_path, ".tn_recovery", commit['tn_recovery_raw'])
                    changed = True
                if commit.get('tn_password_raw'):
                    self._write_raw_file(repo_path, ".tn_password", commit['tn_password_raw'])
                    changed = True
                if commit.get('tn_test_raw'):
                    self._write_raw_file(repo_path, ".tn_test", commit['tn_test_raw'])
                    changed = True

            if changed:
                # Ensure all notes are in structure (for normal commits)
                if not is_security:
                    all_note_ids_in_struct = set()
                    for note in current_struct.get('notes', []):
                        if note.get('id'):
                            all_note_ids_in_struct.add(note['id'])
                    collect_all_note_ids_from_subnotebooks(current_struct, all_note_ids_in_struct)
                    
                    for uuid in current_notes.keys():
                        if uuid not in all_note_ids_in_struct:
                            current_struct['notes'].append({
                                'id': uuid,
                                'title': 'Untitled',
                                'created': datetime.fromtimestamp(commit['timestamp']).isoformat(),
                                'updated': datetime.fromtimestamp(commit['timestamp']).isoformat()
                            })

                # Write JSON files (for normal commits)
                if not is_security:
                    self._write_json_encrypted(repo_path, "notes.json", current_notes, crypto)
                    self._write_json_encrypted(repo_path, "files.json", current_files, crypto)
                    self._write_json_encrypted(repo_path, "structure.json", current_struct, crypto)

                # Stage all files
                subprocess.run(["git", "add", "notes.json", "files.json", "structure.json"], cwd=repo_path, capture_output=True)
                
                # Stage any TN files that exist
                for marker in ['.tn_test', '.tn_recovery', '.tn_password']:
                    marker_path = os.path.join(repo_path, marker)
                    if os.path.exists(marker_path):
                        subprocess.run(["git", "add", marker], cwd=repo_path, capture_output=True)

                # Commit with original metadata
                env = os.environ.copy()
                env['GIT_AUTHOR_NAME'] = commit['author_name']
                env['GIT_AUTHOR_EMAIL'] = commit['author_email']
                env['GIT_AUTHOR_DATE'] = f"@{commit['timestamp']}"
                env['GIT_COMMITTER_NAME'] = commit['author_name']
                env['GIT_COMMITTER_EMAIL'] = commit['author_email']
                env['GIT_COMMITTER_DATE'] = f"@{commit['timestamp']}"
                subprocess.run(["git", "commit", "-m", commit['message']], cwd=repo_path, env=env, capture_output=True)

        # Replace branch and force push
        subprocess.run(["git", "checkout", current_branch], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "reset", "--hard", temp_branch], cwd=repo_path, capture_output=True)
        subprocess.run(["git", "branch", "-D", temp_branch], cwd=repo_path, capture_output=True)

        self._log("  Pushing reconstructed history...", end="")
        push_res = subprocess.run(
            ["git", "push", "--force", "origin", current_branch],
            cwd=repo_path, capture_output=True, text=True
        )
        if push_res.returncode != 0:
            self._log(" FAILED")
            self._log(f"  Push failed: {push_res.stderr[:200]}")
            return False
        self._log(" OK")

        return True

    def _get_crypto_for_path(self, repo_path: str):
        """Get crypto key for notebook at given path"""
        folder_name = os.path.basename(repo_path)
        notebook_id = folder_name.split('-')[-1] if '-' in folder_name else folder_name
        if hasattr(self.manager, 'session_keys'):
            return self.manager.session_keys.get(notebook_id)
        return None

    # ------------------------------------------------------------------------
    # Simple Push/Pull
    # ------------------------------------------------------------------------
    def _simple_push(self, path: str, ahead: int) -> bool:
        self._log(f"  Pushing {ahead} commit(s)...", end="")
        subprocess.run(["git", "add", ".tn_test", ".tn_recovery", ".tn_password"], cwd=path, capture_output=True)
        branch = self._get_current_branch(path)
        result = subprocess.run(["git", "push", "origin", branch], cwd=path, capture_output=True, text=True)
        if result.returncode != 0:
            self._log(" FAILED")
            self._log(f"  Push failed: {result.stderr[:200]}")
            return False
        self._log(" OK")
        return True

    def _simple_pull(self, path: str, behind: int) -> bool:
        self._log(f"  Pulling {behind} commit(s)...", end="")
        result = subprocess.run(["git", "pull", "--rebase", "origin", "master"], cwd=path, capture_output=True, text=True)
        if result.returncode != 0:
            self._log(" FAILED")
            self._log(f"  Pull failed: {result.stderr[:200]}")
            return False
        self._log(" OK")
        return True

    # ------------------------------------------------------------------------
    # Description Builders
    # ------------------------------------------------------------------------
    def _build_reconstruction_description(self, local_chains, remote_chains, winning_commits) -> str:
        all_uuids = set(local_chains.keys()) | set(remote_chains.keys())
        local_only = []
        remote_only = []
        conflicts = []

        for uuid in all_uuids:
            local = local_chains.get(uuid, [])
            remote = remote_chains.get(uuid, [])
            if local and not remote:
                local_only.append(uuid)
            elif remote and not local:
                remote_only.append(uuid)
            else:
                conflicts.append(uuid)

        lines = [
            "  Status: Local and remote have diverged history.",
            ""
        ]
        if local_only:
            lines.append(f"  • Commits only in local: {len(local_only)}")
        if remote_only:
            lines.append(f"  • Commits only in remote: {len(remote_only)}")
        if conflicts:
            lines.append(f"  • Conflicting UUIDs (newer chain wins): {len(conflicts)}")
        lines.extend([
            "",
            "  What will happen:",
            f"  • Reconstruct linear history from {len(winning_commits)} commits",
            "  • Commits ordered by original timestamps",
            "  • Newer chain kept for conflicting UUIDs",
            "  • All commits preserved, linear timeline",
            "  • Remote history will be replaced (force push)"
        ])
        return "\n".join(lines)

    # ------------------------------------------------------------------------
    # First Push (Create Remote Repo)
    # ------------------------------------------------------------------------
    def _create_and_push(self, notebook, account, repo_name, token, path, git_config) -> bool:
        total_commits = self._get_total_commits(path)
        visibility = git_config.get('visibility', 'private') if git_config else 'private'
        desc = f"  Status: No remote repository found.\n\n  What will happen:\n  • Create new {visibility} repository\n    Name: {repo_name}\n  • Push all {total_commits} commit(s) to remote"
        if not self._ask_confirmation(desc):
            return False

        self._log("  Creating repository...", end="")
        if not self._create_repo(account, repo_name, token, visibility):
            self._log(" FAILED")
            return False
        self._log(" OK")

        self._log("  Pushing commits...", end="")
        branch = self._get_current_branch(path)
        res = subprocess.run(["git", "push", "-u", "origin", branch], cwd=path, capture_output=True, text=True)
        if res.returncode != 0:
            self._log(" FAILED")
            self._log(f"  Push failed: {res.stderr[:200]}")
            return False
        self._log(" OK")
        return True

    # ------------------------------------------------------------------------
    # Platform Helpers
    # ------------------------------------------------------------------------
    def _has_internet(self) -> bool:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def _decrypt_token(self, token_enc: str) -> Optional[str]:
        if not token_enc or not token_enc.startswith("acc_"):
            return token_enc
        from token_vault import TokenVault
        return TokenVault(self.app_dir).get_token(token_enc)

    def _check_token_valid(self, account, token) -> bool:
        platform = account.get('platform', 'github')
        try:
            if platform == 'github':
                cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: token {token}' https://api.github.com/user"
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                return res.stdout.strip() == "200"
            elif platform == 'gitlab':
                cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: Bearer {token}' https://gitlab.com/api/v4/user"
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                return res.stdout.strip() == "200"
            elif platform == 'bitbucket':
                auth = base64.b64encode(f"{account['username']}:{token}".encode()).decode()
                cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: Basic {auth}' https://api.bitbucket.org/2.0/user"
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                return res.stdout.strip() == "200"
        except:
            pass
        return False

    def _repo_exists(self, account, repo_name, token) -> bool:
        platform = account.get('platform', 'github')
        try:
            if platform == 'github':
                cmd = f"curl -s -o /dev/null -w '%{{http_code}}' -H 'Authorization: token {token}' https://api.github.com/repos/{account['username']}/{repo_name}"
                res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
                return res.stdout.strip() == "200"
        except:
            pass
        return False

    def _create_repo(self, account, repo_name, token, visibility="private") -> bool:
        import json
        private_flag = "true" if visibility == "private" else "false"
        cmd = f'''curl -s -X POST -H "Authorization: token {token}" -H "Accept: application/vnd.github.v3+json" https://api.github.com/user/repos -d '{{"name":"{repo_name}","private":{private_flag},"auto_init":false}}' '''
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout:
                data = json.loads(res.stdout)
                return "id" in data
        except:
            pass
        return False

    def _build_repo_url(self, account, repo_name) -> str:
        username = account.get('username', '')
        platform = account.get('platform', 'github')
        if platform == "github":
            return f"https://github.com/{username}/{repo_name}.git"
        elif platform == "gitlab":
            return f"https://gitlab.com/{username}/{repo_name}.git"
        elif platform == "bitbucket":
            return f"https://bitbucket.org/{username}/{repo_name}.git"
        else:
            return f"https://{account.get('host', 'github.com')}/{username}/{repo_name}.git"
    
    # ------------------------------------------------------------------------
    # Security Commits management
    # ------------------------------------------------------------------------

    def _get_security_commits(self, repo_path: str, ref: str) -> List[Dict]:
        """Get security commits (password changes) from a ref"""
        commits = []
        
        # Get all commits with SECURITY: in message
        cmd = ["git", "rev-list", "--no-merges", "--grep", "SECURITY:", ref]
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        
        if result.returncode != 0 or not result.stdout:
            return commits
        
        for commit_hash in result.stdout.strip().split('\n'):
            if not commit_hash:
                continue
            
            # Get metadata
            fmt_cmd = ["git", "log", "-1", "--format=%an|%ae|%ct|%B", commit_hash]
            fmt_res = subprocess.run(fmt_cmd, cwd=repo_path, capture_output=True, text=True)
            if fmt_res.returncode != 0:
                continue
            
            parts = fmt_res.stdout.strip().split('|', 3)
            if len(parts) < 4:
                continue
            
            author_name, author_email, ts_str, message = parts
            timestamp = int(ts_str)
            
            # Get TN file blobs
            tn_test_raw = self._get_raw_blob(repo_path, commit_hash, ".tn_test")
            tn_recovery_raw = self._get_raw_blob(repo_path, commit_hash, ".tn_recovery")
            tn_password_raw = self._get_raw_blob(repo_path, commit_hash, ".tn_password")
            
            commits.append({
                'hash': commit_hash,
                'uuid': 'SECURITY',
                'timestamp': timestamp,
                'author_name': author_name,
                'author_email': author_email,
                'message': message,
                'tn_test_raw': tn_test_raw,
                'tn_recovery_raw': tn_recovery_raw,
                'tn_password_raw': tn_password_raw,
                'is_security': True
            })
        
        commits.sort(key=lambda c: c['timestamp'])
        return commits

    
    def _update_vault_for_security_commit(self, repo_path, notebook, security_commit):
        """Update vault entry with new password from security commit"""
        import time
        import json
        
        notebook_id = notebook.get('id')
        
        # Read the new .tn_recovery from the written file
        tn_recovery_path = os.path.join(repo_path, ".tn_recovery")
        
        if not os.path.exists(tn_recovery_path):
            return
        
        with open(tn_recovery_path, 'rb') as f:
            recovery_raw = f.read()
        
        # Get current crypto (has old phrase key - which never changes)
        crypto = self._get_crypto_for_path(repo_path)
        if not crypto:
            return
        
        # Decrypt .tn_recovery using phrase key
        from notebook_operations import read_bytes
        recovery_info = read_bytes(recovery_raw, crypto)
        
        if not recovery_info:
            return
        
        new_password_key_hex = recovery_info.get("password_key", "")
        if not new_password_key_hex:
            return
        
        new_password_key = bytes.fromhex(new_password_key_hex)
        
        # Get system entry from registry
        fp_hash = self.manager._compute_fp_hash()
        
        registry = self.manager.load_registry(force_reload=True)
        notebook_data = registry.get("notebooks", {}).get(notebook_id, {})
        
        systems = notebook_data.get("systems", {})
        
        system_entry = systems.get(fp_hash, {})
        
        entry_uuid = system_entry.get("entry")
        vault_name = system_entry.get("vault", "default")
        current_path = system_entry.get("path")
        
        if not entry_uuid:
            return
        
        # Get vault path
        vault_path = self.manager.vault_manager.get_vault_path(vault_name)
        
        if not vault_path or not os.path.exists(vault_path):
            return
        
        # Get existing entry to preserve structure
        existing_entry = self.manager.vault_manager.get_entry_from_vault(vault_path, entry_uuid)
        
        # Create new encrypted keys
        fingerprint = self.manager._get_system_fingerprint()
        
        combined_keys = new_password_key + crypto.phrase_key
        
        nonce = os.urandom(12)
        
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aesgcm = AESGCM(fingerprint)
        encrypted_keys = aesgcm.encrypt(nonce, combined_keys, None)
        
        # Replace vault entry (same UUID)
        success = self.manager.vault_manager.add_entry_to_vault(vault_path, entry_uuid, {
            "notebook_id": notebook_id,
            "timestamp": time.time_ns(),
            "nonce": nonce.hex(),
            "encrypted_keys": encrypted_keys.hex()
        })
        
        if success:
            # Update master registry to locked state
            self.manager._update_system_entry(notebook_id, {
                "path": current_path,
                "vault": vault_name,
                "entry": entry_uuid,
                "locked": True
            })
            
            # Clear session cache
            if hasattr(self.manager, 'session_keys'):
                if notebook_id in self.manager.session_keys._cache:
                    del self.manager.session_keys._cache[notebook_id]
    
    # ------------------------------------------------------------------------
    # Git Helpers
    # ------------------------------------------------------------------------
    def _get_ahead_count(self, path: str) -> int:
        try:
            res = subprocess.run(["git", "rev-list", "origin/master..master", "--count"], cwd=path, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip())
        except:
            pass
        return 0

    def _get_behind_count(self, path: str) -> int:
        try:
            res = subprocess.run(["git", "rev-list", "master..origin/master", "--count"], cwd=path, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip())
        except:
            pass
        return 0

    def _get_total_commits(self, path: str) -> int:
        try:
            res = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=path, capture_output=True, text=True)
            if res.returncode == 0 and res.stdout.strip():
                return int(res.stdout.strip())
        except:
            pass
        return 0

    def _update_last_push(self, notebook, account):
        for acc_id, acc in self.accounts.get("accounts", {}).items():
            if notebook['id'] in acc.get("notebooks", {}):
                acc["notebooks"][notebook['id']]["last_push"] = datetime.now().isoformat()
                break