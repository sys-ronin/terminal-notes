#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
import subprocess
import json
import re
import tempfile
import os
from datetime import datetime
from crypto import Crypto
import shutil


class GitHistoryMiner:
    def __init__(self, note_manager):
        self.manager = note_manager
        self.temp_files = []
    
    # =========================================================================
    # PUBLIC METHODS - called by comprehensive_search
    # =========================================================================
    
    def find_renamed_items(self, query, quiet=False):
        """Find renamed items matching the query - using UUID tracking, not text matching"""
        renamed_items = []
        seen_ids = set()

        for notebook in self.manager.notebooks:
            if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                continue
        
            notebook_path = notebook.custom_path

            # Get crypto through ops for encrypted notebooks
            crypto = None
            if notebook.id in self.manager.encrypted_notebooks:
                from notebook_operations import NotebookOperations
                ops = NotebookOperations(self.manager)
                crypto = ops.get_crypto(notebook.id)
        
            # Get all commit hashes with RENAMED in message
            cmd = [
                "git", "log", "--all", 
                "--grep", "^type: RENAMED",
                "--pretty=format:%H|%s|%b"
            ]
        
            try:
                result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            
                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().split('\n')
                
                    for line in lines:
                        if not line or '|' not in line:
                            continue
                    
                        parts = line.split('|', 2)
                        if len(parts) < 2:
                            continue
                    
                        commit_hash = parts[0]
                        subject = parts[1] if len(parts) > 1 else ""
                        body = parts[2] if len(parts) > 2 else ""
                        full_message = subject + "\n" + body
                    
                        # Get the FULL commit message with decryption
                        full_message = self._get_commit_message(notebook_path, commit_hash, crypto)
                    
                        if not full_message:
                            continue
                    
                        # Extract UUID from metadata
                        item_id = self._extract_uuid_from_message(full_message)
                        if not item_id or item_id in seen_ids:
                            continue
                    
                        # Determine if it's a NOTE or FILE from the message
                        is_file = 'FILE:' in full_message
                    
                        # Only filter by query if query is provided
                        skip_item = False
                        if query and query.strip():
                            # Extract the title from the commit message
                            title_match = re.search(r'RENAMED\s+\w+:\s*([^→]+)→\s*([^|]+)', full_message)
                            if title_match:
                                old_name = title_match.group(1).strip()
                                new_name = title_match.group(2).strip()
                                # Check if query matches either old or new name
                                if (query.lower() not in old_name.lower() and 
                                    query.lower() not in new_name.lower()):
                                    skip_item = True
                            else:
                                # Fallback - check full message
                                if query.lower() not in full_message.lower():
                                    skip_item = True
                    
                        if skip_item:
                            continue
                    
                        seen_ids.add(item_id)
                    
                        # For rename, get commit BEFORE the rename
                        before_commit = self._get_commit_before(notebook_path, commit_hash)

                        if before_commit:
                            item_data = self._create_temp_json_for_item(
                                notebook_path, item_id, before_commit, full_message, crypto=crypto
                            )
                            if item_data:
                                item_data['is_renamed'] = True
                                item_data['is_file_note'] = is_file
                            
                                # Extract old and new names from commit message
                                name_match = re.search(r'RENAMED\s+\w+:\s*([^→]+)→\s*([^|]+)', full_message)
                                if name_match:
                                    item_data['old_name'] = name_match.group(1).strip()
                                    item_data['new_name'] = name_match.group(2).strip()
                            
                                # Set date to the rename commit date
                                item_data['date'] = self._get_commit_date(notebook_path, commit_hash)
                                renamed_items.append(item_data)
                            
            except Exception:
                continue
    
        return renamed_items
    
    def find_restored_items(self, query, quiet=False):
        """Find restored items matching the query"""
        restored_items = []
        seen_ids = set()

        for notebook in self.manager.notebooks:
            if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                continue
        
            notebook_path = notebook.custom_path
        
            # Get crypto for encrypted notebooks
            crypto = None
            if notebook.id in self.manager.encrypted_notebooks:
                from notebook_operations import NotebookOperations
                ops = NotebookOperations(self.manager)
                crypto = ops.get_crypto(notebook.id)
        
            # Get ALL restored commits
            cmd = [
                "git", "log", "--all", 
                "--grep", "^type: RESTORED",  # Now precise!
                "--pretty=format:%H|%s|%b"
            ]
        
            try:
                result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.splitlines():
                        if not line.strip():
                            continue
                    
                        parts = line.split('|', 2)
                        if len(parts) < 2:
                            continue
                    
                        commit_hash = parts[0]
                        subject = parts[1] if len(parts) > 1 else ""
                        body = parts[2] if len(parts) > 2 else ""
                        full_message = subject + "\n" + body
                    
                        # Extract UUID from metadata
                        item_id = self._extract_uuid_from_message(full_message)
                    
                        # If no UUID, try to find by name
                        if not item_id:
                            name_match = re.search(r'RESTORED\s+\w+:\s*([^|\n]+)', full_message)
                            if name_match:
                                item_name = name_match.group(1).strip()
                                item_id = self._find_id_by_name_in_commit(notebook_path, commit_hash, item_name, crypto)
                    
                        if not item_id or item_id in seen_ids:
                            continue
                    
                        # Get item name for filtering
                        name_match = re.search(r'RESTORED\s+\w+:\s*([^|\n]+)', full_message)
                        item_name = name_match.group(1).strip() if name_match else ""

                        # Filter by query if provided
                        if query and query.strip():
                            if (query.lower() not in full_message.lower() and 
                                query.lower() not in item_name.lower()):
                                continue

                        
                        # For restored items, use the commit itself
                        item_data = self._create_temp_json_for_item(
                            notebook_path, item_id, commit_hash, full_message, crypto=crypto
                        )
                    
                        if item_data:
                            seen_ids.add(item_id)
                            restored_items.append(item_data)
                            
            except Exception as e:
                if not quiet:
                    print(f"Error processing {notebook.name}: {e}")
                continue
    
        return restored_items
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _get_crypto_for_notebook(self, notebook):
        """Get crypto key for notebook using ops"""
        if notebook.id not in self.manager.encrypted_notebooks:
            return None
        
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        return ops.get_crypto(notebook.id)
    
    def _extract_uuid_from_message(self, message):
        """Extract UUID from commit message"""
        import re
    
        # Look for uuid: pattern first (most reliable)
        uuid_match = re.search(r'uuid:([a-f0-9-]+)', message, re.IGNORECASE)
        if uuid_match:
            return uuid_match.group(1)
    
        # Then try raw UUID pattern (full UUID, not truncated)
        uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', 
                              message, re.IGNORECASE)
        if uuid_match:
            return uuid_match.group(1)
    
        # Try timestamp IDs (14 digits exactly)
        ts_match = re.search(r'\b(\d{14})\b', message)
        if ts_match:
            return ts_match.group(1)
    
        return None
    
    def _get_commit_before(self, notebook_path, commit_hash):
        """Get the commit before the given commit"""
        try:
            cmd = ["git", "rev-parse", f"{commit_hash}^"]
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            
            # Fallback
            cmd = ["git", "log", "--before", commit_hash, "--pretty=format:%H", "-1"]
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except:
            pass
        return None
    
    def _get_commit_date(self, notebook_path, commit_hash):
        """Get the date of a commit"""
        try:
            cmd = ["git", "show", "-s", "--format=%ai", commit_hash]
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                date_str = result.stdout.strip()
                from datetime import datetime
                return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
        except Exception:
            pass
        
        # Fallback to epoch (1970-01-01) for commits that can't be found
        from datetime import datetime, timezone
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    
    def get_notebook_last_touched(self, notebook_id, root_notebook):
        """Get the last time this notebook was modified (created, renamed, or had content changes)"""
        if not hasattr(root_notebook, 'custom_path') or not root_notebook.custom_path:
            return None
        
        notebook_path = root_notebook.custom_path
        
        # Get crypto if needed
        crypto = None
        if root_notebook.id in self.manager.encrypted_notebooks:
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
            crypto = ops.get_crypto(root_notebook.id)
        
        # Search for ANY commit mentioning this notebook UUID
        cmd = [
            "git", "log", "--all",
            "--grep", notebook_id,
            "--pretty=format:%ai|%s",
            "-1"  # Only get the most recent
        ]
        
        try:
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            
            if result.returncode == 0 and result.stdout.strip():
                line = result.stdout.strip()
                parts = line.split('|', 1)
                
                if len(parts) >= 1:
                    date_str = parts[0]
                    from datetime import datetime
                    return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
        except Exception:
            pass
        
        return None
    
    def _get_commit_message(self, repo_path, commit_hash, crypto=None):
        """Get full commit message, decrypting if necessary"""
        try:
            cmd = ["git", "cat-file", "commit", commit_hash]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True)
    
            if result.returncode != 0:
                return None
    
            raw_data = result.stdout
    
            if crypto:
                try:
                    decrypted = crypto.decrypt(raw_data)
                    # Find the first blank line, take everything after
                    parts = decrypted.split('\n\n', 1)
                    if len(parts) > 1:
                        return parts[1]  # Everything after first blank line
                    return decrypted
                except:
                    pass
    
            try:
                text_data = raw_data.decode('utf-8')
                # Find the first blank line, take everything after
                parts = text_data.split('\n\n', 1)
                if len(parts) > 1:
                    return parts[1]  # Everything after first blank line
                return text_data
            except:
                return None
        
        except Exception as e:
            print(f"Error getting commit message: {e}")
            return None
        
    def find_deleted_items(self, query, quiet=False):
        """Find deleted items - including notes, files, AND SUBNOTEBOOKS"""
        
        deleted_items = []
        seen_ids = set()

        for notebook in self.manager.notebooks:
            if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                continue
        
            notebook_path = notebook.custom_path
        
            # Get crypto for encrypted notebooks
            crypto = None
            if notebook.id in self.manager.encrypted_notebooks:
                from notebook_operations import NotebookOperations
                ops = NotebookOperations(self.manager)
                crypto = ops.get_crypto(notebook.id)
        
            # Get commits with DELETED at the START of subject
            cmd = [
                "git", "log", "--all", 
                "--grep", "^type: DELETED",
                "--pretty=format:%H|%s|%b"
            ]
        
            try:
                result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.splitlines():
                        if not line.strip():
                            continue
                    
                        parts = line.split('|', 2)
                        if len(parts) < 2:
                            continue
                    
                        commit_hash = parts[0]
                        subject = parts[1] if len(parts) > 1 else ""
                        body = parts[2] if len(parts) > 2 else ""
                        full_message = subject + "\n\n" + body
                    
                        # Skip if this is actually a RENAMED commit
                        if 'RENAMED' in subject:
                            continue
                    
                        # 🟢 Check if it's a subnotebook deletion
                        is_subnotebook = 'SUBNOTEBOOK:' in subject
                    
                        # Extract UUID from metadata
                        item_id = self._extract_uuid_from_message(full_message)
                    
                        # If no UUID, try to find by name from the commit before deletion
                        before_commit = self._get_commit_before(notebook_path, commit_hash)
                        if not before_commit:
                            continue
                    
                        # Get the item name from the commit message
                        name_match = re.search(r'DELETED\s+(\w+):\s*([^|\n]+)', full_message)
                        if not name_match and not item_id:
                            continue
                    
                        item_type = name_match.group(1) if name_match else ""
                        item_name = name_match.group(2).strip() if name_match else ""
                    
                        # If we don't have UUID yet, try to find it by name in the before commit
                        if not item_id and item_name:
                            item_id = self._find_id_by_name_in_commit(notebook_path, before_commit, item_name, crypto)
                    
                        if not item_id or item_id in seen_ids:
                            continue
                         # 🟢 PASTE START - Check if this item already exists in current notebooks
                        item_exists = False
                        for nb in self.manager.notebooks:
                            # Search recursively for this UUID
                            if self._find_item_in_current_structure(nb, item_id):
                                item_exists = True
                                break
                    
                        if item_exists:
                            continue  # Skip this item - it's been restored
                        # 🟢 PASTE END
                        
                        # Get the full item data from before commit
                        item_data = self._create_temp_json_for_item(
                            notebook_path, item_id, before_commit, full_message, crypto=crypto
                        )
                    
                        if not item_data:
                            continue
                    
                        # 🟢 Set subnotebook flag if applicable
                        if is_subnotebook or item_type == 'SUBNOTEBOOK':
                            item_data['is_subnotebook'] = True
                    
                        # Filter by query if provided
                        if query and query.strip():
                            title = item_data.get('title', '').lower()
                            if (query.lower() not in title and 
                                query.lower() not in full_message.lower()):
                                continue
                    
                        seen_ids.add(item_id)
                        deleted_items.append(item_data)
                            
            except Exception as e:
                if not quiet:
                    print(f"Error processing {notebook.name}: {e}")
                continue
    
        return deleted_items
    
    def _find_item_in_current_structure(self, notebook, target_uuid):
        """Check if UUID exists in current notebook structure"""
        if notebook.id == target_uuid:
            return True
        for note in notebook.notes:
            if note.id == target_uuid:
                return True
        for sub in notebook.subnotebooks:
            if self._find_item_in_current_structure(sub, target_uuid):
                return True
        return False
    
    def find_erased_items(self, query, quiet=False):
        """Find permanently erased items (tombstone commits)"""
        erased_items = []
        seen_ids = set()

        for notebook in self.manager.notebooks:
            if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                continue
    
            notebook_path = notebook.custom_path
    
            # Get crypto for encrypted notebooks
            crypto = None
            if notebook.id in self.manager.encrypted_notebooks:
                from notebook_operations import NotebookOperations
                ops = NotebookOperations(self.manager)
                crypto = ops.get_crypto(notebook.id)
    
            # Get all commit hashes with ERASED in message
            cmd = [
                "git", "log", "--all", 
                "--grep", "^type: ERASED",
                "--pretty=format:%H|%s|%b"
            ]
    
            try:
                result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
        
                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if not line:
                            continue
                
                        parts = line.split('|', 2)
                        if len(parts) < 2:
                            continue
                
                        commit_hash = parts[0]
                        subject = parts[1] if len(parts) > 1 else ""
                        body = parts[2] if len(parts) > 2 else ""
                        full_message = subject + "\n" + body
                
                        # Filter by query if provided
                        if query and query.strip() and query.lower() not in full_message.lower():
                            continue
                
                        # Extract UUID
                        item_id = self._extract_uuid_from_message(full_message)
                        if not item_id or item_id in seen_ids:
                            continue
                
                        seen_ids.add(item_id)
                
                        # Extract parent_id from metadata
                        parent_id = None
                        parent_match = re.search(r'parent:([a-f0-9-]+)', full_message)
                        if parent_match:
                            parent_id = parent_match.group(1)
                
                        # Determine item type from message
                        is_file = 'FILE:' in full_message
                        is_subnotebook = 'SUBNOTEBOOK:' in full_message
                
                        # Extract title
                        title = self._extract_title_from_message(full_message)
                        
                
                        # Create result with parent_id for context filtering
                        erased_items.append({
                            'type': 'resurrected_note',
                            'title': title,
                            'uuid': item_id,
                            'parent_id': parent_id,
                            'notebook_path': notebook_path,
                            'commit_message': full_message,
                            'is_erased': True,
                            'is_file_note': is_file,
                            'is_subnotebook': is_subnotebook,
                            'date': self._get_commit_date(notebook_path, commit_hash)
                        })
            except Exception as e:
                if not quiet:
                    print(f"Error processing {notebook.name}: {e}")
                continue

        return erased_items

    def _extract_title_from_message(self, message):
        """Extract item title from ERASED commit message"""
        import re
    
        # Try new format: "type: ERASED NOTE: ttt | in a"
        match = re.search(r'ERASED\s+\w+:\s*([^|\n]+)', message)
        if match:
            return match.group(1).strip()
    
        # Try old format: "ERASED NOTE: ttt | in a"  
        match = re.search(r'ERASED\s+\w+:\s*([^|\n]+)', message)
        if match:
            return match.group(1).strip()
    
        # Fallback: extract after last colon or pipe
        if '|' in message:
            parts = message.split('|')
            first_part = parts[0]
            if ':' in first_part:
                return first_part.split(':')[-1].strip()
    
        return "Unknown"
    
    def _find_id_by_name_in_commit(self, notebook_path, commit_hash, item_name, crypto=None):
        """Find UUID by name in a specific commit - WITH CRYPTO SUPPORT"""
        try:
            # Get structure.json from that commit
            structure_data = self._get_historical_json(notebook_path, commit_hash, "structure.json", crypto)
            if not structure_data:
                return None
        
            def search_recursive(data, target_name):
                if isinstance(data, dict):
                    # Check notes
                    for note in data.get('notes', []):
                        if note.get('title', '').lower() == target_name.lower():
                            return note.get('id')
                
                    # Check subnotebooks
                    for sub_nb in data.get('subnotebooks', []):
                        if sub_nb.get('name', '').lower() == target_name.lower():
                            return sub_nb.get('id')
                        result = search_recursive(sub_nb, target_name)
                        if result:
                            return result
                        
                elif isinstance(data, list):
                    for item in data:
                        result = search_recursive(item, target_name)
                        if result:
                            return result
                return None
        
            return search_recursive(structure_data, item_name)
        
        except Exception as e:
            return None
    
    def _find_item_in_structure(self, structure_data, target_uuid):
        """Find any item by UUID in structure"""
        def search_recursive(data):
            if isinstance(data, dict):
                if data.get('id') == target_uuid:
                    return data
                
                for note in data.get('notes', []):
                    if note.get('id') == target_uuid:
                        return note
                
                for sub_nb in data.get('subnotebooks', []):
                    result = search_recursive(sub_nb)
                    if result:
                        return result
            
            elif isinstance(data, list):
                for item in data:
                    result = search_recursive(item)
                    if result:
                        return result
            
            return None
        
        return search_recursive(structure_data)
    
    def _get_historical_json(self, notebook_path, commit_hash, filename, crypto=None):
        """Get JSON file from git history with crypto support"""
        try:
            cmd = ["git", "show", f"{commit_hash}:{filename}"]
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True)
        
            if result.returncode != 0 or not result.stdout:
                return None
        
            # If we have crypto, try to decrypt
            if crypto:
                try:
                    json_str = crypto.decrypt(result.stdout)
                    return json.loads(json_str)
                except:
                    # Decryption failed, try as plain text
                    pass
        
            # Try as plain text
            try:
                return json.loads(result.stdout.decode('utf-8'))
            except UnicodeDecodeError:
                # Return raw bytes for encrypted data without key
                return result.stdout
            except json.JSONDecodeError:
                return None
            except Exception:
                return None
            
        except Exception:
            return None

    def _create_temp_json_for_item(self, notebook_path, item_id, target_commit, message="", crypto=None):
        """Create temp JSON for item - WITH CRYPTO SUPPORT - SILENT"""
        try:
            # Get structure data with crypto
            structure_data = self._get_historical_json(notebook_path, target_commit, "structure.json", crypto)
    
            if not structure_data:
                return None
    
            # Find the item in structure
            item_info = self._find_item_in_structure(structure_data, item_id)
    
            if not item_info:
                return None
    
            # Determine item type
            if 'name' in item_info:
                item_title = item_info['name']
                is_file_note = False
                is_subnotebook = True
            else:
                item_title = item_info.get('title', 'Unknown')
                is_file_note = 'file_extension' in item_info and item_info['file_extension'] is not None
                is_subnotebook = False

            temp_dir = tempfile.mkdtemp(prefix="resurrected_")
            self.temp_files.append(temp_dir)

            # Build structure
            temp_structure = self._create_minimal_structure(structure_data, item_id, item_info)
    
            # Save structure
            structure_path = os.path.join(temp_dir, "structure.json")
            with open(structure_path, "w") as f:
                json.dump(temp_structure, f, indent=2)

            # Handle content based on type
            if is_subnotebook:
                # For subnotebooks: load ALL content
                notes_data = self._get_historical_json(notebook_path, target_commit, "notes.json", crypto) or {}
                files_data = self._get_historical_json(notebook_path, target_commit, "files.json", crypto) or {}

                notebook_notes = {}
                notebook_files = {}
                self._collect_subnotebook_content(item_info, notes_data, files_data, notebook_notes, notebook_files)

                # Write files
                with open(os.path.join(temp_dir, "notes.json"), "w") as f:
                    json.dump(notebook_notes, f, indent=2)
                with open(os.path.join(temp_dir, "files.json"), "w") as f:
                    json.dump(notebook_files, f, indent=2)
            else:
                # For notes: load individual content
                content_file = "files.json" if is_file_note else "notes.json"
                content_data = self._get_historical_json(notebook_path, target_commit, content_file, crypto) or {}
                content = content_data.get(item_id, "") if content_data else ""
        
                temp_content = {item_id: content}
                content_filename = "files.json" if is_file_note else "notes.json"
                with open(os.path.join(temp_dir, content_filename), "w") as f:
                    json.dump(temp_content, f, indent=2)
        
                # Empty counterpart file
                counterpart_filename = "notes.json" if is_file_note else "files.json"
                with open(os.path.join(temp_dir, counterpart_filename), "w") as f:
                    json.dump({}, f, indent=2)
            
            # 🟢 EXTRACT parent_id DIRECTLY from commit message
            import re
            parent_match = re.search(r'parent[:\s]*([a-f0-9-]+)', message, re.IGNORECASE)
            extracted_parent_id = parent_match.group(1) if parent_match else None
        
            # Extract root_id as well (useful for later)
            root_match = re.search(r'root[:\s]*([a-f0-9-]+)', message, re.IGNORECASE)
            extracted_root_id = root_match.group(1) if root_match else None
        
            return {
                'type': 'resurrected_note',
                'title': item_title,
                'content': content if not is_subnotebook else "",
                'file_extension': item_info.get('file_extension'),
                'created_with': item_info.get('created_with', 'unknown'),
                'uuid': item_id,
                'parent_id': extracted_parent_id,  # ← FROM COMMIT MESSAGE, NOT item_info
                'root_id': extracted_root_id,
                'notebook_path': notebook_path,
                'temp_dir': temp_dir,
                'item_info': item_info,
                'commit_message': message,
                'is_file_note': is_file_note,
                'is_subnotebook': is_subnotebook,
                'date': self._get_commit_date(notebook_path, target_commit),
                '_crypto': crypto
            }
    
        except Exception:
            # Silently fail - no print
            return None
        
    def _collect_subnotebook_content(self, subnotebook, all_notes, all_files, collected_notes, collected_files):
        """Recursively collect all notes and files from a subnotebook hierarchy"""
        for note in subnotebook.get('notes', []):
            note_id = note.get('id')
            if note_id in all_notes:
                collected_notes[note_id] = all_notes[note_id]
            elif note_id in all_files:
                collected_files[note_id] = all_files[note_id]
    
        for child_subnotebook in subnotebook.get('subnotebooks', []):
            self._collect_subnotebook_content(child_subnotebook, all_notes, all_files, collected_notes, collected_files)
    
    def _create_minimal_structure(self, full_structure, target_uuid, target_item):
        """Create minimal structure.json containing the resurrected item"""
        def find_and_build_hierarchy(data, target_uuid, current_path):
            if isinstance(data, dict) and 'id' in data:
                if data.get('id') == target_uuid:
                    if 'subnotebooks' in data or 'notes' in data:
                        return data
                    else:
                        minimal_notebook = {
                            'id': current_path[-1]['id'] if current_path else data.get('id'),
                            'name': current_path[-1]['name'] if current_path else 'Resurrected',
                            'parent_id': None,
                            'notes': [target_item],
                            'subnotebooks': []
                        }
                        return minimal_notebook
            
                for note in data.get('notes', []):
                    if note.get('id') == target_uuid:
                        minimal_notebook = {
                            'id': data.get('id'),
                            'name': data.get('name'),
                            'parent_id': data.get('parent_id'),
                            'notes': [target_item],
                            'subnotebooks': []
                        }
                        return minimal_notebook
            
                for sub_nb in data.get('subnotebooks', []):
                    result = find_and_build_hierarchy(sub_nb, target_uuid, current_path + [data])
                    if result:
                        return result
        
            elif isinstance(data, list):
                for item in data:
                    result = find_and_build_hierarchy(item, target_uuid, current_path)
                    if result:
                        return result
        
            return None
    
        minimal_notebook = find_and_build_hierarchy(full_structure, target_uuid, [])
    
        if minimal_notebook:
            if 'subnotebooks' in minimal_notebook or 'notes' in minimal_notebook:
                return {
                    'notebooks': [minimal_notebook],
                    'resurrected': True,
                    'resurrected_at': datetime.now().isoformat()
                }
            else:
                return {
                    'notebooks': [minimal_notebook],
                    'resurrected': True,
                    'resurrected_at': datetime.now().isoformat()
                }
        else:
            if 'subnotebooks' in target_item or 'notes' in target_item:
                return {
                    'notebooks': [target_item],
                    'resurrected': True,
                    'resurrected_at': datetime.now().isoformat()
                }
            else:
                return {
                    'notebooks': [{
                        'id': 'resurrected_notebook',
                        'name': 'Resurrected Items',
                        'parent_id': None,
                        'notes': [target_item],
                        'subnotebooks': []
                    }],
                    'resurrected': True,
                    'resurrected_at': datetime.now().isoformat()
                }
    
    def get_note_timeline(self, note_id, notebook_id):
        """Get all historical versions of a specific note"""
        timeline_items = []

        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return timeline_items
    
        if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
            print(f"⚠ No custom_path for notebook {notebook.name}")
            return timeline_items
    
        notebook_path = notebook.custom_path

        # Get crypto key if needed
        crypto = self._get_crypto_for_notebook(notebook)

        # Get all commits mentioning this UUID
        cmd = [
            "git", "log", "--all", 
            "--pretty=format:%H|%ai|%BENDOFCOMMIT",
            "--grep", note_id
        ]

        try:
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                commits = result.stdout.strip().split('ENDOFCOMMIT')
                for commit in commits:
                    if commit.strip():
                        lines = commit.strip().splitlines()
                        if len(lines) >= 2:
                            first_line = lines[0]
                            rest_of_message = '\n'.join(lines[1:])
                    
                            parts = first_line.split('|', 2)
                            if len(parts) >= 3:
                                commit_hash, date_str, subject = parts
                                full_message = subject + '\n' + rest_of_message
                        
                                try:
                                    date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
                                    timeline_items.append({
                                        'commit_hash': commit_hash,
                                        'date': date_obj,
                                        'message': full_message.strip(),
                                        'note_id': note_id,
                                        'notebook_path': notebook_path
                                    })
                                except ValueError:
                                    timeline_items.append({
                                        'commit_hash': commit_hash,
                                        'date': datetime.now(),
                                        'message': full_message.strip(),
                                        'note_id': note_id,
                                        'notebook_path': notebook_path
                                    })
        except Exception as e:
            print(f"Timeline error: {e}")
    
        return sorted(timeline_items, key=lambda x: x['date'], reverse=True)
    
    def cleanup_temp_files(self):
        """Clean up all temporary files"""
        for temp_dir in self.temp_files:
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception:
                pass
        self.temp_files = []
        
        
    # Add these methods to GitHistoryMiner class

    def display_resurrected_item(self, result_data, ui):
        """Display a resurrected item - delegate to ResurrectedUI"""
        from res_ui import ResurrectedUI
        res_ui = ResurrectedUI(self.manager, ui)
        res_ui.display_item(result_data, ui)

    def _restore_item(self, result_data, ui):
        """Restore an item - delegates to restore.py"""
        from restore import Restore
    
        restorer = Restore(self.manager, ui)
    
        # Pass crypto if present
        if result_data.get('_crypto'):
            restorer._current_crypto = result_data['_crypto']
    
        # Find the target notebook from parent_id
        import re
        parent_id = None
    
        # Try to get parent_id from item_info first
        item_info = result_data.get('item_info', {})
        if isinstance(item_info, dict):
            parent_id = item_info.get('parent_id')
    
        # Fallback to commit message
        if not parent_id:
            commit_msg = result_data.get('commit_message', '')
            parent_match = re.search(r'parent[:\s]*([a-f0-9-]+)', commit_msg, re.IGNORECASE)
            parent_id = parent_match.group(1) if parent_match else None
    
        if not parent_id:
            print("❌ Error: Cannot determine parent location")
            ui.get_input("Press Enter to continue...")
            return False
    
        # Find the target notebook
        target_notebook = self.manager.find_notebook_by_id(parent_id)
    
        if not target_notebook:
            print(f"❌ Parent notebook not found (ID: {parent_id[:8]}...)")
            ui.get_input("Press Enter to continue...")
            return False
    
        # Perform restore
        if result_data.get('is_subnotebook'):
            success = restorer.restore_subnotebook(
                uuid=result_data['uuid'],
                target_notebook=target_notebook,
                source_data=result_data
            )
        else:
            success = restorer.restore_item(
                uuid=result_data['uuid'],
                target_notebook=target_notebook,
                source_data=result_data
            )
    
        # Mark as no longer deleted for UI
        if success:
            result_data['is_deleted'] = False
            print("\n✓ Item restored successfully!")
        else:
            print("\n✗ Restore failed.")
    
        ui.get_input("Press Enter to continue...")
        return success

####################################################################################################                    
####################################################################################################

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def parse_change_stats(commit_message):
    """
    Parse change stats from commit message.
    Returns dict with 'display' string (change stats only) and 'total' for future use.
    
    Format examples:
    - "change: 11(+) totalc:11" → display: "11(+)", total: "11"
    - "change: 12(+) 5(-) totalc:17" → display: "12(+) 5(-)", total: "17"
    """
    import re
    
    if not commit_message:
        return None
    
    # Look for change: pattern
    change_match = re.search(r'change:\s*(.+?)(?:\s+totalc:|$)', commit_message)
    if not change_match:
        return None
    
    change_str = change_match.group(1).strip()
    
    # Extract totalc for future use (not displayed yet)
    totalc_match = re.search(r'totalc:(\d+)', commit_message)
    totalc = totalc_match.group(1) if totalc_match else None
    
    return {
        'display': change_str,  # "11(+)" or "12(+) 5(-)" - what we show now
        'change': change_str,   # same as display for now
        'total': totalc         # stored for future use (not displayed)
    }