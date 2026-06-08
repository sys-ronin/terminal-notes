#!/usr/bin/env python3
FILTER_REPO_AVAILABLE = True  # FORCE DISABLE until fixed
import sys
sys.dont_write_bytecode = True

import os
import subprocess
import shutil
import importlib.util
import re
from datetime import datetime  # 🟢 ADD THIS LINE


# Manual loading of git_filter_repo
filter_repo_path = os.path.join(os.path.dirname(__file__), "git_filter_repo.py")
if os.path.exists(filter_repo_path):
    try:
        spec = importlib.util.spec_from_file_location("git_filter_repo", filter_repo_path)
        git_filter_repo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(git_filter_repo)
        FILTER_REPO_AVAILABLE = True
        #print("✓ git-filter-repo loaded manually")
    except Exception as e:
        FILTER_REPO_AVAILABLE = False
        #print(f"✗ Could not load git-filter-repo: {e}")
else:
    FILTER_REPO_AVAILABLE = False
    print("✗ git_filter_repo.py not found")
    input("  Press Enter to continue...")  # ← ADD THIS LINE
    
class Eraser:
    def __init__(self, manager, ui=None):  # ← Add ui parameter
        self.manager = manager
        self.ui = ui  # ← Now ui exists (from parameter)

    
    def delete_item(self, uuid, delete_type='forget', item_title=None):
        """Universal delete method - WITH GIT COMMIT"""
        item_info = self._identify_item(uuid)
        if not item_info:
            if self.ui:
                self.ui.clear_screen()
                print(f"✗ Could not find item with UUID: {uuid}")
                self.ui.get_input("Press Enter to continue...")
            return False
    
        item_type = item_info['type']
        context = item_info['context']
    
        # Get title for display
        if not item_title:
            if item_type in ['note', 'file']:
                item_title = context['note'].title
            elif item_type == 'subnotebook':
                item_title = context['subnotebook'].name
            elif item_type == 'notebook':
                item_title = context['notebook'].name
    
        if delete_type == 'forget':
            self._soft_delete(uuid, item_type, context, item_title)
        else:  # erase
            self._hard_delete(uuid, item_type, context, item_title)
    
        return True

    def _soft_delete(self, uuid, item_type, context, item_title=None):
        """Soft delete - keeps history, just removes from current - MUTED"""
        if item_type in ['note', 'file']:
            notebook = context['notebook']
            note = context['note']
            notebook.notes.remove(note)
            self.manager.save_data()
        
            # 🟢 USE GIT MANAGER FOR CONSISTENT COMMIT STRUCTURE
            root = self.manager._find_root_notebook(notebook)
            git_manager = self.manager.get_git_manager(root)
        
            git_manager.commit_note_deletion(
                note.id, 
                note.title, 
                notebook.name, 
                note.is_file_note,
                parent_uuid=notebook.id,
                root_uuid=root.id
            )
        
            print(f"  ✓ {item_title or note.title} forgotten")
        
        elif item_type == 'subnotebook':
            parent = context['parent_notebook']
            subnotebook = context['subnotebook']
            parent.subnotebooks.remove(subnotebook)
            self.manager.save_data()

            # Update manager's in-memory notebook list
            for i, nb in enumerate(self.manager.notebooks):
                if nb.id == parent.id:
                    self.manager.notebooks[i] = parent
                    break

            root = self.manager._find_root_notebook(parent)
            for i, nb in enumerate(self.manager.notebooks):
                if nb.id == root.id:
                    self.manager.notebooks[i] = root
                    break

            # 🟢 USE GIT MANAGER FOR SUBNOTEBOOK DELETION
            git_manager = self.manager.get_git_manager(root)
            git_manager.commit_subnotebook_deletion(
                subnotebook.id,
                subnotebook.name,
                parent.name,
                root_uuid=root.id
            )
            
        elif item_type == 'notebook':
            self.manager.delete_notebook(context['notebook'])
            print("  ✓ Notebook forgotten")

        if self.ui:
            self.ui.get_input("Press Enter to continue...")
    
    def _hard_delete(self, uuid, item_type, context, item_title=None):
        """Hard delete - removes from Git history completely with final tombstone commit"""

        if item_type in ['note', 'file', 'subnotebook']:
            # Get title for display
            display_title = item_title or uuid
        
            # Store ALL current crypto keys before purge
            saved_session_keys = {}
            if hasattr(self.manager, 'session_keys'):
                saved_session_keys = dict(self.manager.session_keys)
        
            # Temporarily disable auto-unlock
            self.manager._skip_auto_unlock = True
        
            if self.ui:
                display_title = item_title or uuid
                print(f"\nSECURELY ERASING {item_type.upper()}: {display_title}")

            # Get the notebook path before purge
            if item_type in ['note', 'file']:
                notebook = context['notebook']
            else:
                notebook = context['parent_notebook']

            root = self.manager._find_root_notebook(notebook)
            repo_path = root.custom_path if hasattr(root, 'custom_path') else None

            # ========== BACKUP ENCRYPTION FILES BEFORE PURGE ==========
            tn_test_backup = None
            tn_recovery_backup = None
            tn_password_backup = None
            
            if repo_path and os.path.exists(repo_path):
                tn_test_path = os.path.join(repo_path, ".tn_test")
                tn_recovery_path = os.path.join(repo_path, ".tn_recovery")
                tn_password_path = os.path.join(repo_path, ".tn_password")
                
                if os.path.exists(tn_test_path):
                    with open(tn_test_path, 'rb') as f:
                        tn_test_backup = f.read()
                if os.path.exists(tn_recovery_path):
                    with open(tn_recovery_path, 'rb') as f:
                        tn_recovery_backup = f.read()
                if os.path.exists(tn_password_path):
                    with open(tn_password_path, 'rb') as f:
                        tn_password_backup = f.read()
            # ========== END BACKUP ==========

            if self.ui:
                print("  Step 1: Purging from Git history...")

            # Perform the git purge
            self._purge_from_git(uuid, item_type, context)

            # ========== RESTORE ENCRYPTION FILES AFTER PURGE ==========
            if repo_path and os.path.exists(repo_path):
                tn_test_path = os.path.join(repo_path, ".tn_test")
                tn_recovery_path = os.path.join(repo_path, ".tn_recovery")
                tn_password_path = os.path.join(repo_path, ".tn_password")
                
                if tn_test_backup:
                    with open(tn_test_path, 'wb') as f:
                        f.write(tn_test_backup)
                if tn_recovery_backup:
                    with open(tn_recovery_path, 'wb') as f:
                        f.write(tn_recovery_backup)
                if tn_password_backup:
                    with open(tn_password_path, 'wb') as f:
                        f.write(tn_password_backup)
            # ========== END RESTORE ==========

            if self.ui:
                print("  Step 2: Removing from current view...")

            # Remove from current view
            if item_type in ['note', 'file']:
                notebook = context['notebook']
                note = context['note']
                notebook.notes.remove(note)
                self.manager.save_data()
                if self.ui:
                    print(f"    ✓ {display_title} removed from view")
            elif item_type == 'subnotebook':
                parent = context['parent_notebook']
                subnotebook = context['subnotebook']
                parent.subnotebooks.remove(subnotebook)
                self.manager.save_data()
                if self.ui:
                    print(f"    ✓ {display_title} removed from view")

            # ========== TOMBSTONE COMMIT - Stage ALL affected files ==========
            if repo_path and os.path.exists(repo_path):
                try:
                    # Get UUIDs for commit metadata
                    root_uuid = root.id
                    parent_uuid = ""

                    if item_type in ['note', 'file']:
                        notebook = context['notebook']
                        parent_uuid = notebook.id
                    elif item_type == 'subnotebook':
                        parent = context['parent_notebook']
                        parent_uuid = parent.id

                    # Create tombstone commit with type: ERASED prefix
                    tombstone_message = (
                        f"type: ERASED {item_type.upper()}: {display_title} | in {root.name}\n\n"
                        f"Metadata: uuid:{uuid} | parent:{parent_uuid} | root:{root_uuid}\n"
                        f"This item was permanently erased from history."
                    )

                    # Determine which files were affected
                    files_to_commit = ["structure.json", "notes.json", "files.json"]
                    
                    # Also include encryption files since they were restored
                    files_to_commit.extend([".tn_test", ".tn_recovery", ".tn_password"])

                    # Commit the tombstone
                    git_manager = self.manager.get_git_manager(root)
                    
                    # Stage all files explicitly
                    for file in files_to_commit:
                        git_manager._run_git_command(["git", "add", file])
                    
                    # Commit
                    git_manager.commit_silently(tombstone_message, files_to_commit)

                    if self.ui:
                        print(f"  Step 3: Creating tombstone commit...")
                        print(f"    ✓ Erasure recorded in git history")

                except Exception as e:
                    if self.ui:
                        print(f"  ⚠ Tombstone commit failed (optional): {e}")
            # ========== END TOMBSTONE COMMIT ==========

            # Restore ALL crypto keys
            if hasattr(self.manager, 'session_keys'):
                self.manager.session_keys.update(saved_session_keys)

            # Re-enable auto-unlock
            self.manager._skip_auto_unlock = False

            if self.ui:
                print("  ✓ Completely erased from history")
                print()
                self.ui.get_input("Press Enter to continue...")

        elif item_type == 'notebook':
            # Handled separately
            pass
    
    def _identify_item(self, uuid):
        """Find what type of item this UUID belongs to - WITH LOCK CHECK"""
        def search_recursive(notebooks):
            for notebook in notebooks:
                # 🟢 CRITICAL: Skip locked notebooks entirely
                if notebook.id in self.manager.encrypted_notebooks:
                    if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                        # Skip this entire notebook - it's locked
                        continue
            
                # Check notes in this notebook
                for note in notebook.notes:
                    if note.id == uuid:
                        return {
                            'type': 'file' if note.is_file_note else 'note',
                            'context': {
                                'notebook': notebook,
                                'note': note
                            }
                        }
            
                # Check subnotebooks in this notebook
                for sub in notebook.subnotebooks:
                    if sub.id == uuid:
                        return {
                            'type': 'subnotebook',
                            'context': {
                                'parent_notebook': notebook,
                                'subnotebook': sub
                            }
                        }
                    # Recursively search deeper subnotebooks
                    result = search_recursive([sub])
                    if result:
                        return result

            return None

        # Start search from root notebooks
        result = search_recursive(self.manager.notebooks)
        return result
    
    def _find_subnotebook(self, uuid, notebook, parent=None):
        """Recursively find subnotebook by UUID"""
        print(f"      Searching subnotebook: {notebook.name}")
        for sub in notebook.subnotebooks:
            print(f"        Checking sub: {sub.name} (ID: {sub.id[:8]}...)")
            if sub.id == uuid:
                print(f"          ✅ Found matching subnotebook!")
                return {'subnotebook': sub, 'parent': notebook}
            found = self._find_subnotebook(uuid, sub, notebook)
            if found:
                return found
        return None
    
    def _purge_from_git(self, uuid, item_type, context):
        """Remove all traces from Git history using filter-repo once"""
    
        if self.ui:
            print("    Starting Git history purge...")
    
        # Find Git repo path using notebook's custom_path
        if item_type in ['note', 'file']:
            notebook = context['notebook']
        else:  # subnotebook
            notebook = context['parent_notebook']
    
        root = self.manager._find_root_notebook(notebook)
        repo_path = root.custom_path if hasattr(root, 'custom_path') else None
    
        if not repo_path or not os.path.exists(repo_path):
            if self.ui:
                print("    └─ Repository folder not found, skipping")
            return
    
        # Files to purge - ALL files that might contain the UUID
        files_to_clean = ["structure.json", "notes.json", "files.json"]
    
        if self.ui:
            print(f"    ├─ Cleaning files: {', '.join(files_to_clean)}")
    
        # Run filter-repo ONCE with all files
        success = self._git_filter_all(repo_path, files_to_clean, uuid)
    
        if success and self.ui:
            print(f"    ├─ Running garbage collection...")
    
        # Silent garbage collection
        subprocess.run(["git", "gc", "--aggressive", "--prune=now"],
                    cwd=repo_path,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    
        if self.ui:
            print("    └─ Git history purge complete")
    
    def _git_filter_all(self, repo_path, files, uuid):
        """100% FILTER-REPO DELETION - Let filter-repo handle everything"""

        # 🚨 SAFETY CHECK 1 - Never run on project root
        project_root = os.path.dirname(os.path.abspath(__file__))
        try:
            if os.path.samefile(repo_path, project_root):
                if self.ui:
                    print(f"      ⚠ SAFETY: Cannot run filter-repo on project root: {repo_path}")
                return False
        except Exception:
            if os.path.abspath(repo_path) == os.path.abspath(project_root):
                if self.ui:
                    print(f"      ⚠ SAFETY: Cannot run filter-repo on project root: {repo_path}")
                return False

        # 🚨 SAFETY CHECK 2 - filter-repo must be available
        if not FILTER_REPO_AVAILABLE:
            if self.ui:
                print(f"      ⚠ filter-repo not available")
            return False

        # 🚨 SAFETY CHECK 3 - repo path must exist
        if not os.path.exists(repo_path):
            if self.ui:
                print(f"      ⚠ Repository path not found: {repo_path}")
            return False

        # 🚨 SAFETY CHECK 4 - must be a git repository
        git_path = os.path.join(repo_path, ".git")
        if not os.path.exists(git_path):
            if self.ui:
                print(f"      ⚠ Not a git repository: {repo_path}")
            return False

        original_dir = os.getcwd()
        try:
            os.chdir(repo_path)
        
            import git_filter_repo
        
            # ========== SURGICAL FIX: Clean filter-repo state ==========
            filter_repo_dir = os.path.join(repo_path, ".git", "filter-repo")
            already_ran_file = os.path.join(filter_repo_dir, "already_ran")
            
            if os.path.exists(already_ran_file):
                try:
                    os.unlink(already_ran_file)
                except:
                    pass
            # ========== END FIX ==========
        
            # Parse arguments for UUID erasure
            args = git_filter_repo.FilteringOptions.parse_args([
                "--force",           # Bypass already_ran prompt
                "--uuid-erase", uuid,
                "--prune-empty=always",
                "--path", "structure.json",
                "--path", "notes.json",
                "--path", "files.json"
            ], error_on_empty=False)
        
            # Use our specialized filter
            filter = git_filter_repo.UUIDEraseFilter(args, uuid)
            filter.run()
        
            return True
        
        except Exception as e:
            if self.ui:
                print(f"      ✗ Erasure failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            try:
                os.chdir(original_dir)
            except:
                pass
    
    def standard_delete_notebook(self, notebook_id):
        """Standard Delete - folder removed immediately (UPDATED for master registry)"""
        from getpass import getpass
        from crypto import derive_key
        
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return

        # ========== Get folder path from MASTER REGISTRY ==========
        master_registry = self.manager.load_registry(force_reload=True)
        notebook_data = master_registry.get("notebooks", {}).get(notebook_id, {})
        folder_path = None

        # Get path from first system entry (any system will do)
        for system_entry in notebook_data.get("systems", {}).values():
            path = system_entry.get("path")
            if path:
                if not os.path.isabs(path):
                    path = os.path.join(self.manager.notebooks_root, path)
                if os.path.exists(path):
                    folder_path = path
                    break

        if not folder_path:
            # Fallback to notebook.custom_path (old way)
            if hasattr(notebook, 'custom_path') and notebook.custom_path:
                folder_path = notebook.custom_path
            else:
                print(f"  ⚠ Cannot find folder for notebook {notebook_id}")
                return

        folder_name = os.path.basename(folder_path)

        # ========== PASSWORD VERIFICATION FOR ENCRYPTED NOTEBOOKS ==========
        if notebook.id in self.manager.encrypted_notebooks:
            # Get crypto key
            crypto = None
            if hasattr(notebook, '_crypto') and notebook._crypto:
                crypto = notebook._crypto
            else:
                crypto = self.manager.session_keys.get(notebook.id)
            
            if not crypto:
                print("  Cannot verify password - notebook not unlocked.")
                return
            
            stored_pw_key = crypto.password_key
            
            # Verify password (3 attempts)
            max_attempts = 3
            verified = False
            
            for attempt in range(max_attempts):
                remaining = max_attempts - attempt
                password = getpass(f"  Enter notebook password to confirm deletion ({remaining} attempts): ")
                
                derived_key = derive_key(password, folder_name)
                
                if derived_key == stored_pw_key:
                    verified = True
                    break
                else:
                    print("  Wrong password.\n")
            
            if not verified:
                print("\n  Password verification failed. Deletion cancelled.")
                return
        # ========== END PASSWORD VERIFICATION ==========

        # Clean up session keys
        if notebook.id in self.manager.encrypted_notebooks and folder_name:
            if notebook.id in self.manager.session_keys:
                del self.manager.session_keys[notebook.id]
            if self.manager.secure_storage:
                self.manager.secure_storage.remove_session_key(folder_name)

        # Unregister from master registry
        self.manager.unregister_notebook(notebook_id)

        # Delete folder
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

        # Remove key from permanent storage (if still present)
        if self.manager.secure_storage:
            self.manager.secure_storage.remove_session_key(folder_name)

        print(f"  ✓ Folder removed: {folder_path}")
        
    '''
    def secure_erase_notebook(self, notebook):
        """Secure Erase - completely remove notebook and ALL its commits from history"""
    
        # 🟢 FIX: If notebook is a string (ID), get the actual notebook object
        if isinstance(notebook, str):
            notebook = self.manager.find_notebook_by_id(notebook)
            if not notebook:
                if self.ui:
                    print(f"  ꘎ Notebook with ID {notebook} not found")
                    self.ui.get_input("Press Enter to continue...")
                return False
    
        if self.ui:
            self.ui.clear_screen()
            print(f"\n꘎ SECURELY ERASING ENTIRE NOTEBOOK: {notebook.name}")
            print("  This will DELETE ALL COMMITS and remove the folder permanently!")
            print()
    
        # Get the repo path
        if hasattr(notebook, 'custom_path') and notebook.custom_path:
            repo_path = notebook.custom_path
        else:
            print(f"  ⚠ No custom_path for notebook {notebook.name}")
            return
    
        if self.ui:
            print(f"  Repository: {repo_path}")
            print()
            confirm = self.ui.get_input(f"Type the notebook name '{notebook.name}' to confirm: ")
            if confirm != notebook.name:
                print("\n  ꘎ Confirmation failed. Erasure cancelled.")
                self.ui.get_input("Press Enter to continue...")
                return

        # ========== STEP 1: Get crypto key if notebook is encrypted ==========
        crypto = notebook._crypto if hasattr(notebook, '_crypto') else None
    
        if self.ui and crypto:
            print("    Using stored crypto key for decryption...")

        # ========== STEP 2: Get ALL UUIDs from Git history ==========
        if self.ui:
            print("\n  Step 1: Mining ALL UUIDs from Git history...")
    
        all_uuids = set()
        all_uuids.add(notebook.id)  # The notebook itself
    
        # Collect UUIDs from notebook structure
        def collect_uuids_from_notebook(nb):
            for note in nb.notes:
                all_uuids.add(note.id)
            for sub in nb.subnotebooks:
                all_uuids.add(sub.id)
                collect_uuids_from_notebook(sub)
    
        collect_uuids_from_notebook(notebook)
    
        if self.ui:
            print(f"    Found {len(all_uuids)} UUIDs from notebook structure")
    
        # ========== STEP 3: Find ALL commits containing these UUIDs ==========
        import subprocess
        import tempfile
    
        # Get ALL commit hashes
        cmd = ["git", "rev-list", "--all"]
        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        all_commit_hashes = result.stdout.strip().split('\n') if result.stdout else []
        # 🔇 Comment out the detailed commit scanning output
        """
        if self.ui:
            print(f"    Scanning {len(all_commit_hashes)} commits for UUID references...")
    
        commits_to_delete = set()
        commit_details = {}  # Store commit details for display
    
        for i, commit_hash in enumerate(all_commit_hashes):
            if not commit_hash:
                continue
        
            # Get commit message
            cmd = ["git", "log", "--format=%B", "-n", "1", commit_hash]
            msg_result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
        
            if msg_result.returncode == 0:
                msg = msg_result.stdout
                # Store first line for display
                first_line = msg.split('\n')[0][:50] if msg else "no message"
                commit_details[commit_hash] = first_line
            
                # Check if any UUID is in this commit message
                for uuid in all_uuids:
                    if uuid in msg:
                        commits_to_delete.add(commit_hash)
                        if self.ui:
                            print(f"        📍 Found UUID {uuid[:8]}... in commit {commit_hash[:8]}: {first_line[:30]}...")
                        break
        
            if self.ui and i % 5 == 0:
                print(f"      Progress: {i}/{len(all_commit_hashes)} commits", end='\r')
    
        if self.ui:
            print(f"      Progress: {len(all_commit_hashes)}/{len(all_commit_hashes)} commits")
            print(f"    Found {len(commits_to_delete)} commits to delete")
        
            # Show all commits that will be deleted
            if commits_to_delete:
                print("\n    Commits marked for deletion:")
                for ch in sorted(commits_to_delete):
                    print(f"      🔥 {ch[:8]}: {commit_details.get(ch, 'unknown')[:50]}")
        """
    
        # ========== STEP 4: Create temporary replace file with ALL UUIDs ==========
        temp_replace_file = None
        temp_callback_file = None
        original_dir = os.getcwd()
    
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for uuid in all_uuids:
                    f.write(f"literal:{uuid}==>\n")
                temp_replace_file = f.name
                if self.ui:
                    print(f"    Created replace file with {len(all_uuids)} UUID patterns")

            if self.ui:
                print("\n  Step 2: Running notebook erasure...")
                print("  " + "="*50)

            # Change to repo directory
            os.chdir(repo_path)
    
            # Import filter-repo
            import git_filter_repo
    
            # Format: notebook_uuid:uuid1,uuid2,uuid3,...
            uuid_list = ','.join(all_uuids)
            notebook_erase_arg = f"{notebook.id}:{uuid_list}"
    
            path_args = [
                "--path", "structure.json",
                "--path", "notes.json", 
                "--path", "files.json"
            ]
    
            # Parse arguments
            args = git_filter_repo.FilteringOptions.parse_args(
                [
                    "--force",
                    "--replace-text", temp_replace_file,
                    "--prune-empty=always",
                    "--notebook-erase", notebook_erase_arg,
                ] + path_args,
                error_on_empty=False
            )
    
            # Create and run the notebook erasure filter
            filter = git_filter_repo.NotebookEraseFilter(args, notebook.id, all_uuids)
            filter.run()
    
            # Return to original directory
            os.chdir(original_dir)

            if self.ui:
                print("  " + "="*50)
                print(f"    ✓ Notebook erasure completed")
                if hasattr(filter, 'commits_removed'):
                    print(f"    ✓ Removed {filter.commits_removed} commits")

            # ========== STEP 3: Verify deletion ==========
            if self.ui:
                print("\n  Step 3: Verifying deletion...")
    
            # Check if any commits remain
            cmd = ["git", "rev-list", "--all", "--count"]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            remaining = int(result.stdout.strip()) if result.stdout else 0
    
            if remaining == 0:
                if self.ui:
                    print(f"    ✓ All commits successfully deleted")
            else:
                if self.ui:
                    print(f"    ⚠ {remaining} commits remain - they may not belong to this notebook")
                    # Show remaining commits
                    cmd = ["git", "log", "--oneline"]
                    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
                    print(result.stdout)
    
            # ========== STEP 4: Clean up session keys ==========
            if self.ui:
                print("\n  Step 4: Cleaning up keys and registry...")
    
            folder_name = os.path.basename(repo_path)

            if notebook.id in self.manager.encrypted_notebooks:
                if notebook.id in self.manager.session_keys:
                    del self.manager.session_keys[notebook.id]
                if self.manager.secure_storage:
                    self.manager.secure_storage.remove_session_key(folder_name)
    
            self.manager.unregister_notebook(notebook.id)

            if self.ui:
                print("    ✓ Registry entry removed")
    
            # ========== STEP 5: Delete the folder ==========
            if self.ui:
                print("  Step 5: Deleting notebook folder...")
    
            if os.path.exists(repo_path):
                import shutil
                shutil.rmtree(repo_path)
                if self.ui:
                    print(f"    ✓ Folder deleted")
    
            if self.ui:
                print("\n  ✓ NOTEBOOK COMPLETELY ERASED FROM HISTORY!")
                if hasattr(filter, 'commits_removed'):
                    print(f"    Removed {filter.commits_removed} commits and {len(all_uuids)} UUIDs")
                self.ui.get_input("\nPress Enter to continue...")
    
            return True

        except Exception as e:
            if self.ui:
                print(f"      ✗ Erasure failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Clean up temp files
            if temp_replace_file and os.path.exists(temp_replace_file):
                os.unlink(temp_replace_file)
            # Return to original directory
            try:
                os.chdir(original_dir)
            except:
                pass

        '''
    def secure_erase_notebook(self, notebook):
        """
        Secure Erase - completely remove notebook and ALL its commits from history.
        Requires password verification for encrypted notebooks, name confirmation for unencrypted.
        """
        import shutil
        import subprocess
        import tempfile
        import os
        from getpass import getpass
        from crypto import derive_key

        # Resolve notebook object if ID was passed
        if isinstance(notebook, str):
            notebook = self.manager.find_notebook_by_id(notebook)
            if not notebook:
                if self.ui:
                    print(f"  Notebook with ID {notebook} not found")
                    self.ui.get_input("Press Enter to continue...")
                return False

        # Force unlock if notebook is locked (critical after password change)
        if notebook.locked or not notebook.custom_path:
            crypto = self.manager.get_crypto(notebook.id)
            if crypto:
                fresh = self.manager.find_notebook_by_id(notebook.id)
                if fresh and fresh.custom_path:
                    notebook = fresh
                else:
                    return False
            else:
                return False

        # Get folder path from master registry
        master_registry = self.manager.load_registry(force_reload=True)
        notebook_data = master_registry.get("notebooks", {}).get(notebook.id, {})
        system_entries = notebook_data.get("systems", {})
        folder_path = None

        for system_entry in system_entries.values():
            path = system_entry.get("path")
            if path:
                if not os.path.isabs(path):
                    path = os.path.join(self.manager.notebooks_root, path)
                if os.path.exists(path):
                    folder_path = path
                    break

        if not folder_path and hasattr(notebook, 'custom_path') and notebook.custom_path:
            folder_path = notebook.custom_path

        if not folder_path:
            if self.ui:
                print(f"  Cannot find folder for notebook {notebook.name}")
                self.ui.get_input("Press Enter to continue...")
            return False

        # ========== CONFIRMATION (Password for encrypted, Name for unencrypted) ==========
        if self.ui:
            self.ui.clear_screen()
            print(f"\n꘎ SECURELY ERASING ENTIRE NOTEBOOK: {notebook.name}")
            print("  This will DELETE ALL COMMITS and remove the folder permanently!")
            print()
            print(f"  Repository: {folder_path}")
            print()

            is_encrypted = notebook.id in self.manager.encrypted_notebooks

            if is_encrypted:
                # Get crypto key
                crypto = None
                if hasattr(notebook, '_crypto') and notebook._crypto:
                    crypto = notebook._crypto
                else:
                    crypto = self.manager.session_keys.get(notebook.id)

                if not crypto:
                    print("  Cannot verify password - notebook not unlocked.")
                    self.ui.get_input("Press Enter to continue...")
                    return False

                folder_name = os.path.basename(folder_path)
                stored_pw_key = crypto.password_key

                # Verify password (3 attempts)
                max_attempts = 3
                verified = False

                for attempt in range(max_attempts):
                    remaining = max_attempts - attempt
                    password = getpass(f"  Enter notebook password to confirm erasure ({remaining} attempts): ")

                    derived_key = derive_key(password, folder_name)

                    if derived_key == stored_pw_key:
                        verified = True
                        break
                    else:
                        print("  Wrong password.\n")

                if not verified:
                    print("\n  ꘎ Password verification failed. Erasure cancelled.")
                    self.ui.get_input("Press Enter to continue...")
                    return False
            else:
                # Unencrypted notebook - just confirm with notebook name
                print(f"  Type the notebook name '{notebook.name}' to confirm: ", end="")
                confirm = input().strip()
                if confirm != notebook.name:
                    print("\n  ꘎ Confirmation failed. Erasure cancelled.")
                    self.ui.get_input("Press Enter to continue...")
                    return False
        # ========== END CONFIRMATION ==========

        # Trusted device removal option
        remove_trusted = False
        if self.ui and len(system_entries) > 1:
            print("\n  This notebook has trusted devices on other systems.")
            print("  Options:")
            print("    1) Remove only this machine's trust (keep others)")
            print("    2) Remove ALL trusted devices (complete wipe)")
            print()
            choice = self.ui.get_input("  Choose [1/2]: ").strip()
            remove_trusted = (choice == "2")

        # Collect ALL UUIDs from notebook structure
        all_uuids = set()
        all_uuids.add(notebook.id)

        def collect_uuids_from_notebook(nb):
            for note in nb.notes:
                all_uuids.add(note.id)
            for sub in nb.subnotebooks:
                all_uuids.add(sub.id)
                collect_uuids_from_notebook(sub)

        collect_uuids_from_notebook(notebook)

        # Create replace file for filter-repo
        temp_replace_file = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                for uuid in all_uuids:
                    f.write(f"literal:{uuid}==>\n")
                temp_replace_file = f.name
        except Exception as e:
            if self.ui:
                print(f"  Failed to create replace file: {e}")
                self.ui.get_input("Press Enter to continue...")
            return False

        # Run git-filter-repo to erase all UUIDs
        original_dir = os.getcwd()
        try:
            os.chdir(folder_path)

            import git_filter_repo

            uuid_list = ','.join(all_uuids)
            notebook_erase_arg = f"{notebook.id}:{uuid_list}"

            path_args = [
                "--path", "structure.json",
                "--path", "notes.json",
                "--path", "files.json"
            ]

            filter_args = [
                "--force",
                "--replace-text", temp_replace_file,
                "--prune-empty=always",
                "--notebook-erase", notebook_erase_arg,
            ] + path_args

            args = git_filter_repo.FilteringOptions.parse_args(filter_args, error_on_empty=False)
            filter = git_filter_repo.NotebookEraseFilter(args, notebook.id, all_uuids)
            filter.run()

            os.chdir(original_dir)

        except Exception as e:
            if self.ui:
                print(f"  Erasure failed: {e}")
                self.ui.get_input("Press Enter to continue...")
            os.chdir(original_dir)
            return False
        finally:
            if temp_replace_file and os.path.exists(temp_replace_file):
                os.unlink(temp_replace_file)

        # Remove vault entries
        if remove_trusted:
            for system_entry in system_entries.values():
                vault_name = system_entry.get("vault", "default")
                entry_uuid = system_entry.get("entry")
                vault_path = self.manager.vault_manager.get_vault_path(vault_name)
                if vault_path and entry_uuid:
                    self.manager.vault_manager.remove_entry_from_vault(vault_path, entry_uuid)
        else:
            fp_hash = self.manager._compute_fp_hash()
            current_entry = system_entries.get(fp_hash)
            if current_entry:
                vault_name = current_entry.get("vault", "default")
                entry_uuid = current_entry.get("entry")
                vault_path = self.manager.vault_manager.get_vault_path(vault_name)
                if vault_path and entry_uuid:
                    self.manager.vault_manager.remove_entry_from_vault(vault_path, entry_uuid)

        # Clean up session keys and registry
        folder_name = os.path.basename(folder_path)
        if notebook.id in self.manager.encrypted_notebooks:
            if notebook.id in self.manager.session_keys:
                del self.manager.session_keys[notebook.id]
            if self.manager.secure_storage:
                self.manager.secure_storage.remove_session_key(folder_name)

        self.manager.unregister_notebook(notebook.id)

        # Delete the folder
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path)

        if self.ui:
            print("\n  ✓ NOTEBOOK COMPLETELY ERASED FROM HISTORY!")
            self.ui.get_input("\nPress Enter to continue...")

        return True