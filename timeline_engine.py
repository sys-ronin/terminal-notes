# timeline_engine.py
#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True

import os
import json
import tempfile
import subprocess
from datetime import datetime
from pathlib import Path

class TimelineEngine:
    """
    Clean, focused timeline engine.
    Only does two things:
    1. Gets list of commits for an item
    2. Reconstructs item at a specific commit
    """
    
    def __init__(self, note_manager):
        self.manager = note_manager
        self.temp_dirs = []
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def get_item_timeline(self, item_uuid, notebook_id, crypto=None):
        """
        Get all historical versions of an item.
        Returns list of version data (minimal, just metadata).
        """
        timeline_versions = []
    
        # Find the notebook and its path
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return timeline_versions
    
        root = self.manager._find_root_notebook(notebook)
        notebook_path = self._get_notebook_path(root)
        if not notebook_path or not os.path.exists(notebook_path):
            return timeline_versions
    
        # Use provided crypto or try to get it
        if not crypto and root.id in self.manager.encrypted_notebooks:
            crypto = self.manager.session_keys.get(root.id)
            if not crypto:
                from crypto import Crypto
                folder_name = f"{root.name}-{root.id}"
                crypto = Crypto.retrieve_for_folder(folder_name)
                if crypto:
                    self.manager.session_keys[root.id] = crypto
    
        # Get all commits mentioning this UUID
        cmd = [
            "git", "log", "--all", 
            "--pretty=format:%H|%ai|%BENDOFCOMMIT",
            "--grep", item_uuid
        ]
    
        try:
            result = subprocess.run(cmd, cwd=notebook_path, capture_output=True, text=True)
        
            if result.returncode == 0 and result.stdout.strip():
                commits = result.stdout.strip().split('ENDOFCOMMIT')
            
                for commit in commits:
                    if not commit.strip():
                        continue
                
                    lines = commit.strip().splitlines()
                    if len(lines) < 2:
                        continue
                
                    # Parse commit
                    first_line = lines[0]
                    rest = '\n'.join(lines[1:])
                    parts = first_line.split('|', 2)
                
                    if len(parts) < 3:
                        continue
                
                    commit_hash, date_str, subject = parts
                    full_message = subject + '\n' + rest
                
                    # 🟢 FIX: If this is a DELETED commit, get the commit before
                    target_hash = commit_hash
                    if 'DELETED' in subject:
                        # Get the commit before deletion
                        cmd_before = ["git", "rev-parse", f"{commit_hash}^"]
                        before_result = subprocess.run(cmd_before, cwd=notebook_path, capture_output=True, text=True)
                        if before_result.returncode == 0 and before_result.stdout.strip():
                            target_hash = before_result.stdout.strip()
                            print(f"🔍 DELETED commit detected, using parent: {target_hash[:8]}")
                
                    # Parse date
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
                    except ValueError:
                        date_obj = datetime.now()
                
                    # Store minimal version data with the correct target hash
                    timeline_versions.append({
                        'commit_hash': commit_hash,
                        'target_hash': target_hash,  # 🟢 Store both
                        'date': date_obj,
                        'message': full_message.strip(),
                        'uuid': item_uuid,
                        'notebook_path': notebook_path,
                        '_crypto': crypto,
                        'notebook_id': root.id
                    })
    
        except Exception as e:
            print(f"Timeline error: {e}")
    
        return sorted(timeline_versions, key=lambda x: x['date'], reverse=True)
    
    def create_version_at_commit(self, item_uuid, notebook_path, commit_hash, 
                                    commit_message="", crypto=None, target_hash=None):
        """
        Reconstruct an item at a specific commit.
        target_hash: Optional hash to use for reconstruction (for DELETED commits)
        """
        try:
            # Get structure.json at this commit
            structure_data = self._get_file_at_commit(notebook_path, commit_hash, "structure.json", crypto)
            if not structure_data:
                return None

            # Find the item in the structure
            item_info = self._find_item_in_structure(structure_data, item_uuid)
            if not item_info:
                return None

            # Determine item type
            item_type = self._determine_type(item_info)

            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix=f"timeline_{item_uuid[:8]}_")
            self.temp_dirs.append(temp_dir)

            # Reconstruct based on type
            if item_type in ['note', 'file']:
                version = self._reconstruct_note(
                    item_uuid, item_info, notebook_path, commit_hash,
                    commit_message, item_type, crypto, temp_dir
                )
            elif item_type in ['notebook', 'subnotebook']:
                version = self._reconstruct_notebook(
                    item_uuid, item_info, notebook_path, commit_hash,
                    commit_message, structure_data, crypto, temp_dir
                )
            else:
                return None

            if version:
                version['_crypto'] = crypto
                version['notebook_id'] = self._extract_id_from_path(notebook_path)
                return version
            return None

        except Exception:
            return None
    
    def cleanup(self):
        """Remove all temporary directories."""
        import shutil
        for temp_dir in self.temp_dirs:
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
        self.temp_dirs = []
    
    # =========================================================================
    # RECONSTRUCTORS
    # =========================================================================
    
    def _reconstruct_note(self, item_uuid, item_info, notebook_path, commit_hash,
                        commit_message, item_type, crypto, temp_dir):
        """Reconstruct a note or file at a specific commit."""

        # Get content
        content_file = "files.json" if item_type == 'file' else "notes.json"
        content_data = self._get_file_at_commit(notebook_path, commit_hash, content_file, crypto) or {}
        content = content_data.get(item_uuid, "")

        # Extract parent_id and root_id from commit_message
        import re
        parent_match = re.search(r'parent[:\s]*([a-f0-9-]+)', commit_message, re.IGNORECASE)
        root_match = re.search(r'root[:\s]*([a-f0-9-]+)', commit_message, re.IGNORECASE)

        parent_id = parent_match.group(1) if parent_match else None
        root_id = root_match.group(1) if root_match else None

        # Build minimal structure
        structure = {
            'notebooks': [{
                'id': 'timeline_viewer',
                'name': 'Historical View',
                'parent_id': None,
                'notes': [item_info] if item_type == 'note' else [],
                'subnotebooks': []
            }]
        }

        # Save structure
        with open(os.path.join(temp_dir, "structure.json"), "w") as f:
            json.dump(structure, f, indent=2)

        # Save content
        content_map = {item_uuid: content}
        with open(os.path.join(temp_dir, content_file), "w") as f:
            json.dump(content_map, f, indent=2)

        # Empty counterpart
        other_file = "notes.json" if item_type == 'file' else "files.json"
        with open(os.path.join(temp_dir, other_file), "w") as f:
            json.dump({}, f, indent=2)

        return {
            'type': 'timeline_version',
            'item_type': item_type,
            'title': item_info.get('title', 'Unknown'),
            'content': content,
            'file_extension': item_info.get('file_extension'),
            'uuid': item_uuid,
            'notebook_path': notebook_path,
            'temp_dir': temp_dir,
            'commit_hash': commit_hash,
            'commit_message': commit_message,
            'item_info': item_info,
            'date': self._get_commit_date(notebook_path, commit_hash),
            'parent_id': parent_id,
            'root_id': root_id
        }
    
    def _reconstruct_notebook(self, item_uuid, item_info, notebook_path, commit_hash,
                            commit_message, structure_data, crypto, temp_dir):
        """Reconstruct a notebook or subnotebook at a specific commit."""
    
        # Find the notebook in the full structure
        notebook_data = self._find_item_in_structure(structure_data, item_uuid)
        if not notebook_data:
            print(f"  ❌ Notebook {item_uuid[:8]} not found in structure")
            return None
    
        # Create minimal structure containing just this notebook
        minimal_structure = {
            'notebooks': [notebook_data]
        }
    
        # Save structure.json
        with open(os.path.join(temp_dir, "structure.json"), "w") as f:
            json.dump(minimal_structure, f, indent=2)
    
        # Collect all UUIDs in this notebook (notes and subnotebooks)
        all_uuids = set()
        self._collect_uuids_from_notebook(notebook_data, all_uuids)
    
        # Get notes.json and files.json from the commit
        notes_data = self._get_file_at_commit(notebook_path, commit_hash, "notes.json", crypto) or {}
        files_data = self._get_file_at_commit(notebook_path, commit_hash, "files.json", crypto) or {}
    
        # Filter to only UUIDs in this notebook
        filtered_notes = {uuid: notes_data[uuid] for uuid in all_uuids if uuid in notes_data}
        filtered_files = {uuid: files_data[uuid] for uuid in all_uuids if uuid in files_data}
    
        # Save filtered content
        with open(os.path.join(temp_dir, "notes.json"), "w") as f:
            json.dump(filtered_notes, f, indent=2)
    
        with open(os.path.join(temp_dir, "files.json"), "w") as f:
            json.dump(filtered_files, f, indent=2)
    
        # Extract parent_id and root_id from commit_message
        import re
        parent_match = re.search(r'parent[:\s]*([a-f0-9-]+)', commit_message, re.IGNORECASE)
        root_match = re.search(r'root[:\s]*([a-f0-9-]+)', commit_message, re.IGNORECASE)
    
        parent_id = parent_match.group(1) if parent_match else None
        root_id = root_match.group(1) if root_match else None
    
        return {
            'type': 'timeline_version',
            'item_type': 'subnotebook' if notebook_data.get('parent_id') else 'notebook',
            'title': notebook_data.get('name', 'Unknown'),
            'uuid': item_uuid,
            'notebook_path': notebook_path,
            'temp_dir': temp_dir,
            'commit_hash': commit_hash,
            'commit_message': commit_message,
            'item_info': notebook_data,
            'date': self._get_commit_date(notebook_path, commit_hash),
            'parent_id': parent_id,
            'root_id': root_id
        }

    def _collect_uuids_from_notebook(self, notebook_data, uuid_set):
        """Recursively collect all UUIDs from a notebook structure."""
        if 'id' in notebook_data:
            uuid_set.add(notebook_data['id'])
    
        for note in notebook_data.get('notes', []):
            if 'id' in note:
                uuid_set.add(note['id'])
    
        for sub in notebook_data.get('subnotebooks', []):
            self._collect_uuids_from_notebook(sub, uuid_set)
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _get_notebook_path(self, notebook):
        """Get filesystem path for a notebook."""
        if hasattr(notebook, 'custom_path') and notebook.custom_path:
            return notebook.custom_path
        
        folder_name = f"{notebook.name}-{notebook.id}"
        return os.path.join(self.manager.notebooks_root, folder_name)
    
    def _get_file_at_commit(self, repo_path, commit_hash, filename, crypto=None):
        """Get a file's content at a specific commit."""
        try:
            cmd = ["git", "show", f"{commit_hash}:{filename}"]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True)
            
            if result.returncode != 0 or not result.stdout:
                return None
            
            # Try JSON decode (for unencrypted)
            try:
                return json.loads(result.stdout.decode('utf-8'))
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Probably encrypted - return raw bytes
                if crypto:
                    try:
                        json_str = crypto.decrypt(result.stdout)
                        return json.loads(json_str)
                    except:
                        return result.stdout
                return result.stdout
                
        except Exception:
            return None
    
    def _get_commit_date(self, repo_path, commit_hash):
        """Get date of a commit."""
        try:
            cmd = ["git", "show", "-s", "--format=%ai", commit_hash]
            result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return datetime.strptime(result.stdout.strip(), "%Y-%m-%d %H:%M:%S %z")
        except:
            pass
        return datetime.now()
    
    def _find_item_in_structure(self, data, target_uuid):
        """Find any item by UUID in nested structure."""
        if isinstance(data, dict):
            if data.get('id') == target_uuid:
                return data
            
            for note in data.get('notes', []):
                if note.get('id') == target_uuid:
                    return note
            
            for sub in data.get('subnotebooks', []):
                result = self._find_item_in_structure(sub, target_uuid)
                if result:
                    return result
        
        elif isinstance(data, list):
            for item in data:
                result = self._find_item_in_structure(item, target_uuid)
                if result:
                    return result
        
        return None
    
    def _extract_subtree(self, full_structure, root_uuid):
        """Extract a notebook and all its descendants from full structure."""
        def find_and_copy(data):
            if isinstance(data, dict):
                if data.get('id') == root_uuid:
                    # Deep copy the notebook and all contents
                    return json.loads(json.dumps(data))
                
                for sub in data.get('subnotebooks', []):
                    result = find_and_copy(sub)
                    if result:
                        return result
            return None
        
        notebook = find_and_copy(full_structure)
        if notebook:
            return {'notebooks': [notebook]}
        return None
    
    def _collect_uuids(self, structure):
        """Collect all UUIDs in a notebook hierarchy."""
        uuids = set()
        
        def walk(data):
            if isinstance(data, dict):
                if 'id' in data:
                    uuids.add(data['id'])
                
                for note in data.get('notes', []):
                    if 'id' in note:
                        uuids.add(note['id'])
                
                for sub in data.get('subnotebooks', []):
                    walk(sub)
            elif isinstance(data, list):
                for item in data:
                    walk(item)
        
        walk(structure)
        return uuids
    
    def _determine_type(self, item_info):
        """Determine what type of item this is."""
        if 'file_extension' in item_info and item_info['file_extension'] is not None:
            return 'file'
        elif 'title' in item_info:
            return 'note'
        elif 'subnotebooks' in item_info or 'notes' in item_info:
            if 'parent_id' in item_info and item_info['parent_id'] is not None:
                return 'subnotebook'
            else:
                return 'notebook'
        return 'unknown'
    
    def _extract_id_from_path(self, notebook_path):
        """Extract notebook ID from path."""
        folder = os.path.basename(notebook_path)
        if '-' in folder:
            return folder.split('-')[-1]
        return None