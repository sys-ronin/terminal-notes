#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True

import os
import json
import shutil
from datetime import datetime

class Restore:
    def __init__(self, manager, ui):
        self.manager = manager
        self.ui = ui
        self.history_miner = None  # Will be set from outside
    
    def restore_item(self, uuid, target_notebook, source_data):
        """
        Restore an item from historical data to a notebook
        source_data: the data from _create_temp_json_for_item()
        """
        temp_dir = source_data.get('temp_dir')
        if not temp_dir or not os.path.exists(temp_dir):
            print("Error: Cannot find historical data")
            return False

        # Get crypto from source_data
        crypto = source_data.get('_crypto')
        if crypto:
            self._current_crypto = crypto

        # Determine item type
        is_subnotebook = source_data.get('is_subnotebook', False)
        is_file = source_data.get('is_file_note', False)
        item_title = source_data.get('title', 'Unknown')
        item_uuid = source_data.get('uuid')

        # Get root and its path using custom_path
        root = self.manager._find_root_notebook(target_notebook)
        if not root:
            print("Error: Cannot find root notebook")
            return False

        if hasattr(root, 'custom_path') and root.custom_path:
            live_path = root.custom_path
        else:
            print(f"Error: Root notebook {root.name} has no custom_path")
            return False

        # Get parent UUID (the target notebook is the parent)
        parent_uuid = target_notebook.id
        root_uuid = root.id

        # Paths to temp files
        temp_structure = os.path.join(temp_dir, "structure.json")
        temp_notes = os.path.join(temp_dir, "notes.json")
        temp_files = os.path.join(temp_dir, "files.json")

        # Paths to live files
        live_structure = os.path.join(live_path, "structure.json")
        live_notes = os.path.join(live_path, "notes.json")
        live_files = os.path.join(live_path, "files.json")

        # Create backups
        backups = {}
        try:
            for file in [live_structure, live_notes, live_files]:
                if os.path.exists(file):
                    backup_path = f"{file}.restore_backup"
                    shutil.copy2(file, backup_path)
                    backups[file] = backup_path
        except Exception as e:
            print(f"Failed to create backups: {e}")
            return False

        try:
            # Merge content files
            self._merge_json_files(temp_notes, live_notes)
            self._merge_json_files(temp_files, live_files)

            # Update structure.json
            self._update_structure(temp_structure, live_structure, uuid, target_notebook, is_subnotebook)

            # Update the in-memory notebook object directly
            if not is_subnotebook:
                temp_manager = self._create_temp_manager(temp_dir)
                if temp_manager:
                    temp_notebooks = temp_manager.load_all_notebooks()
                    if temp_notebooks and temp_notebooks[0].notes:
                        restored_note = temp_notebooks[0].notes[0]
                        target_notebook.notes.append(restored_note)

            # Save data
            self.manager.save_data()

            # Force refresh the manager's in-memory state
            self.manager.load_all_notebooks()

            # Git commit with full metadata
            try:
                git_manager = self.manager.get_git_manager(root)

                original_commit = source_data.get('commit_message', '')
                commit_hash = self._extract_commit_hash(original_commit)

                if is_subnotebook:
                    note_count = len(source_data.get('item_info', {}).get('notes', []))
                    sub_count = len(source_data.get('item_info', {}).get('subnotebooks', []))
                    file_count = self._count_files_in_subnotebook(source_data.get('item_info', {}))
                    context = f"to {target_notebook.name} ({note_count} notes, {file_count} files, {sub_count} subs)"
    
                    git_manager.commit_restoration(
                        item_uuid, item_title, target_notebook.name, 'SUBNOTEBOOK', 
                        original_commit=commit_hash, context=context,
                        parent_uuid=parent_uuid, root_uuid=root_uuid
                    )
                elif is_file:
                    git_manager.commit_restoration(
                        item_uuid, item_title, target_notebook.name, 'FILE',
                        original_commit=commit_hash,
                        parent_uuid=parent_uuid, root_uuid=root_uuid
                    )
                else:
                    git_manager.commit_restoration(
                        item_uuid, item_title, target_notebook.name, 'NOTE',
                        original_commit=commit_hash,
                        parent_uuid=parent_uuid, root_uuid=root_uuid
                    )
            except Exception as e:
                print(f"Git commit failed (optional): {e}")

            # Remove backups on success
            for backup in backups.values():
                if os.path.exists(backup):
                    os.unlink(backup)

            print(f"✓ {item_title} restored successfully!")
            return True

        except Exception as e:
            print(f"Restoration failed: {e}")
            print("Rolling back changes...")
        
            for original, backup in backups.items():
                if os.path.exists(backup):
                    try:
                        shutil.move(backup, original)
                    except Exception:
                        pass
        
            self.manager.load_all_notebooks()
            return False
    
    # 🆕 Add this helper method
    def _create_temp_manager(self, temp_dir):
        """Create a temporary manager to load data from temp_dir"""
        class TempNoteManager:
            def __init__(self, temp_dir):
                self.notebooks_root = temp_dir
                self.notebooks = []
                self._load_notebooks()
        
            def _load_notebooks(self):
                import json
                from terminal_notes_core import Notebook
            
                struct_file = os.path.join(self.notebooks_root, "structure.json")
                notes_file = os.path.join(self.notebooks_root, "notes.json")
                files_file = os.path.join(self.notebooks_root, "files.json")
            
                if os.path.exists(struct_file):
                    with open(struct_file, 'r') as f:
                        structure_data = json.load(f)
                
                    # Load content maps
                    notes_map = {}
                    files_map = {}
                
                    if os.path.exists(notes_file):
                        with open(notes_file, 'r') as f:
                            notes_map = json.load(f)
                
                    if os.path.exists(files_file):
                        with open(files_file, 'r') as f:
                            files_map = json.load(f)
                
                    # Create notebooks
                    if 'notebooks' in structure_data:
                        notebooks_data = structure_data['notebooks']
                    else:
                        notebooks_data = [structure_data]
                
                    for nb_data in notebooks_data:
                        notebook = Notebook.from_dict(nb_data)
                    
                        # Apply content
                        for note in notebook.notes:
                            note_id = note.id
                            if note.is_file_note and note_id in files_map:
                                note.content = files_map[note_id]
                            elif not note.is_file_note and note_id in notes_map:
                                note.content = notes_map[note_id]
                    
                        self.notebooks.append(notebook)
        
            def load_all_notebooks(self):
                return self.notebooks
    
        return TempNoteManager(temp_dir)
    
    def _merge_json_files(self, source_path, dest_path):
        """Merge source JSON into destination JSON (add/update keys) - WITH CRYPTO SUPPORT"""
        import json
        import os
        from notebook_operations import read_json, write_json
    
        # 🟢 FIX: Determine if destination is encrypted by checking parent notebook
        crypto = None
        # Try to get crypto from context (you'll need to pass this)
        if hasattr(self, '_current_crypto'):
            crypto = self._current_crypto
    
        # Load source (always plain JSON from temp)
        with open(source_path, 'r') as f:
            source_data = json.load(f)
    
        # Load or create destination with crypto support
        if os.path.exists(dest_path):
            # 🟢 Use read_json which handles decryption
            dest_data = read_json(dest_path, crypto)
            if dest_data is None:
                # Fallback to plain text if read_json fails
                try:
                    with open(dest_path, 'r') as f:
                        dest_data = json.load(f)
                except:
                    dest_data = {}
        else:
            dest_data = {}
    
        # Merge (source overwrites dest if same UUID)
        dest_data.update(source_data)
    
        # 🟢 Write back with crypto support
        temp_write_path = dest_path + '.tmp'
        success = write_json(temp_write_path, dest_data, crypto)
    
        if success:
            os.rename(temp_write_path, dest_path)
        else:
            # Fallback to plain write
            with open(temp_write_path, 'w') as f:
                json.dump(dest_data, f, indent=2)
            os.rename(temp_write_path, dest_path)
    
    def _update_structure(self, temp_structure, live_structure, uuid, target_notebook, is_subnotebook):
        """Update structure.json to include restored item - WITH CRYPTO SUPPORT"""
        import json
        import os
        from notebook_operations import read_json, write_json
    
        # 🟢 FIX: Get crypto from context
        crypto = getattr(self, '_current_crypto', None)
    
        # Load temp structure (always plain JSON)
        with open(temp_structure, 'r') as f:
            temp_data = json.load(f)
    
        # Load live structure with crypto support
        live_data = read_json(live_structure, crypto)
        if live_data is None:
            # Fallback to plain read
            try:
                with open(live_structure, 'r') as f:
                    live_data = json.load(f)
            except:
                live_data = {"notebooks": []}
    
        # Ensure live_data has the correct structure
        if 'notebooks' not in live_data:
            live_data = {"notebooks": [live_data] if live_data else []}
    
        # Find the target notebook in live data by walking the hierarchy
        def find_notebook_by_id(notebooks, target_id):
            for nb in notebooks:
                if nb.get('id') == target_id:
                    return nb
                # Search in subnotebooks
                found = find_notebook_by_id(nb.get('subnotebooks', []), target_id)
                if found:
                    return found
            return None
    
        target_nb_struct = find_notebook_by_id(live_data.get('notebooks', []), target_notebook.id)
    
        if not target_nb_struct:
            print(f"Warning: Target notebook {target_notebook.name} not found in structure.json")
            print("Creating entry for it...")
            # Create a basic structure for the target notebook
            target_nb_struct = {
                'id': target_notebook.id,
                'name': target_notebook.name,
                'parent_id': target_notebook.parent_id,
                'notes': [],
                'subnotebooks': []
            }
            # Make sure live_data has notebooks list
            if 'notebooks' not in live_data:
                live_data['notebooks'] = []
            live_data['notebooks'].append(target_nb_struct)
    
        if is_subnotebook:
            # Extract the subnotebook from temp structure
            historical_nb = None
            # Handle different possible structures in temp_data
            if 'notebooks' in temp_data:
                notebooks_to_search = temp_data['notebooks']
            else:
                notebooks_to_search = [temp_data]  # Assume temp_data itself is a notebook
    
            for nb in notebooks_to_search:
                historical_nb = self._find_notebook_by_uuid(nb, uuid)
                if historical_nb:
                    break
    
            if historical_nb:
                # Add to parent's subnotebooks
                if 'subnotebooks' not in target_nb_struct:
                    target_nb_struct['subnotebooks'] = []
                target_nb_struct['subnotebooks'].append(historical_nb)
                print(f"  Added subnotebook {historical_nb.get('name')} to {target_notebook.name}")
        else:
            # It's a note - extract from temp structure
            historical_note = None
            # Handle different possible structures in temp_data
            if 'notebooks' in temp_data:
                notebooks_to_search = temp_data['notebooks']
            else:
                notebooks_to_search = [temp_data]
    
            for nb in notebooks_to_search:
                historical_note = self._find_note_by_uuid(nb, uuid)
                if historical_note:
                    break
    
            if historical_note:
                # Add to target notebook's notes
                if 'notes' not in target_nb_struct:
                    target_nb_struct['notes'] = []
                target_nb_struct['notes'].append(historical_note)
                print(f"  Added note {historical_note.get('title')} to {target_notebook.name}")
    
        # 🟢 Save with crypto support
        temp_write_path = live_structure + '.tmp'
        success = write_json(temp_write_path, live_data, crypto)
    
        if success:
            os.rename(temp_write_path, live_structure)
        else:
            # Fallback to plain write
            with open(temp_write_path, 'w') as f:
                json.dump(live_data, f, indent=2)
            os.rename(temp_write_path, live_structure)
    
    def _find_notebook_by_uuid(self, notebook, uuid):
        """Recursively find notebook by UUID in structure"""
        if notebook.get('id') == uuid:
            return notebook
    
        for sub in notebook.get('subnotebooks', []):
            found = self._find_notebook_by_uuid(sub, uuid)
            if found:
                return found
        return None

    def _find_note_by_uuid(self, notebook, uuid):
        """Recursively find note by UUID in notebook structure"""
        for note in notebook.get('notes', []):
            if note.get('id') == uuid:
                return note
    
        for sub in notebook.get('subnotebooks', []):
            found = self._find_note_by_uuid(sub, uuid)
            if found:
                return found
        return None
    
    def _find_note_by_uuid(self, notebook, uuid):
        """Find note by UUID in notebook structure"""
        for note in notebook.get('notes', []):
            if note.get('id') == uuid:
                return note
        
        for sub in notebook.get('subnotebooks', []):
            found = self._find_note_by_uuid(sub, uuid)
            if found:
                return found
        return None
    
    def _count_files_in_subnotebook(self, notebook_info):
        """Count file notes in a subnotebook"""
        count = 0
        for note in notebook_info.get('notes', []):
            if note.get('file_extension'):
                count += 1
        
        for sub in notebook_info.get('subnotebooks', []):
            count += self._count_files_in_subnotebook(sub)
        
        return count
    
    def _extract_commit_hash(self, commit_message):
        """Extract commit hash from message if present"""
        import re
        match = re.search(r'[a-f0-9]{7,40}', commit_message)
        return match.group(0) if match else None
    
    def restore_subnotebook(self, uuid, target_notebook, source_data):
        """Restore entire subnotebook hierarchy - ATOMIC"""
        temp_dir = source_data.get('temp_dir')
        if not temp_dir:
            print("✗ No temp directory")
            return False

        # 🟢 APPEND: Get crypto from source_data
        crypto = source_data.get('_crypto')
        if crypto:
            self._current_crypto = crypto

        # Get root and its path using custom_path
        root = self.manager._find_root_notebook(target_notebook)
        if not root:
            print("Error: Cannot find root notebook")
            return False

        if hasattr(root, 'custom_path') and root.custom_path:
            live_path = root.custom_path
        else:
            print(f"Error: Root notebook {root.name} has no custom_path")
            return False

        live_struct = os.path.join(live_path, "structure.json")
        live_notes = os.path.join(live_path, "notes.json")
        live_files = os.path.join(live_path, "files.json")

        temp_struct = os.path.join(temp_dir, "structure.json")
        temp_notes = os.path.join(temp_dir, "notes.json")
        temp_files = os.path.join(temp_dir, "files.json")

        # Load and find subnotebook
        with open(temp_struct) as f:
            hist_struct = json.load(f)

        sub = self._find_notebook_by_uuid_recursive(
            hist_struct.get('notebooks', []), uuid
        )
        if not sub:
            print("✗ Subnotebook not found")
            return False

        # Collect all UUIDs and merge content
        all_uuids = set()
        self._collect_all_uuids(sub, all_uuids)

        # 🟢 APPEND: Create backups before any changes
        backups = {}
        try:
            for file in [live_struct, live_notes, live_files]:
                if os.path.exists(file):
                    backup_path = f"{file}.restore_backup"
                    shutil.copy2(file, backup_path)
                    backups[file] = backup_path
        except Exception as e:
            print(f"Failed to create backups: {e}")
            return False

        try:
            # Merge content
            self._atomic_filtered_merge(temp_notes, live_notes, all_uuids)
            self._atomic_filtered_merge(temp_files, live_files, all_uuids)

            # Update structure
            self._atomic_add_subnotebook_to_structure(
                live_struct, sub, target_notebook.id
            )
    
            # Refresh and commit
            self.manager.load_all_notebooks()

            try:
                git = self.manager.get_git_manager(root)
                note_cnt = len([u for u in all_uuids if self._is_note_uuid(u, temp_notes)])
                sub_cnt = len([u for u in all_uuids if self._is_subnotebook_uuid(u, temp_struct)]) - 1

                git.commit_restoration(
                    uuid, sub.get('name'), target_notebook.name, 'SUBNOTEBOOK',
                    context=f"{note_cnt} notes, {sub_cnt} subs",
                    parent_uuid=target_notebook.id,
                    root_uuid=root.id
                )
            except Exception as e:
                print(f"Git commit failed (optional): {e}")

            # 🟢 APPEND: Success - remove backups
            for backup in backups.values():
                if os.path.exists(backup):
                    os.unlink(backup)

            # Get parent notebook name instead of UUID
            parent_name = target_notebook.name

            # Get subnotebook name
            sub_name = sub.get('name', 'Unknown')

            # Smart path truncation
            terminal_width = shutil.get_terminal_size().columns

            if target_notebook.parent_id:
                hierarchy = self.manager.get_notebook_hierarchy(target_notebook.id)
                if hierarchy:
                    path_names = [nb.name for nb in hierarchy]
                    if len(path_names) > 2:
                        display_path = f".../{path_names[-2]}/{path_names[-1]}"
                    elif len(path_names) == 2:
                        display_path = f"{path_names[0]}/{path_names[1]}"
                    else:
                        display_path = path_names[0]
            else:
                display_path = target_notebook.name

            if len(display_path) > terminal_width - 30:
                display_path = display_path[:terminal_width-33] + "..."

            print(f"✓ Restored '{sub_name}' ({note_cnt} notes, {sub_cnt} subs) in {display_path}")
            return True

        except Exception as e:
            # 🟢 APPEND: Rollback - restore from backups
            print(f"Restoration failed: {e}")
            print("Rolling back changes...")
        
            for original, backup in backups.items():
                if os.path.exists(backup):
                    try:
                        shutil.move(backup, original)
                    except Exception as restore_error:
                        print(f"Failed to restore {original}: {restore_error}")
        
            # Reload original state
            self.manager.load_all_notebooks()
            return False

    def _atomic_filtered_merge(self, temp_path, live_path, allowed_uuids):
        """
        Atomically merge only entries with UUIDs in allowed_uuids - WITH CRYPTO SUPPORT
        """
        import json
        import os
        from notebook_operations import read_json, write_json
    
        if not os.path.exists(temp_path):
            return False
    
        # 🟢 FIX: Get crypto from context (already set in restore_subnotebook)
        crypto = getattr(self, '_current_crypto', None)
    
        # Read temp data (always plain JSON)
        with open(temp_path, 'r') as f:
            temp_data = json.load(f)

        # Filter to only allowed UUIDs
        filtered_data = {}
        for uuid, content in temp_data.items():
            if uuid in allowed_uuids:
                filtered_data[uuid] = content
    
        if not filtered_data:
            return False
    
        # Load or create live data with crypto support
        if os.path.exists(live_path):
            # Use read_json which handles decryption
            live_data = read_json(live_path, crypto)
            if live_data is None:
                # Fallback to plain text
                try:
                    with open(live_path, 'r') as f:
                        live_data = json.load(f)
                except:
                    live_data = {}
        else:
            live_data = {}
    
        # Merge
        live_data.update(filtered_data)
    
        # Write with crypto support
        temp_write_path = live_path + '.tmp'
        success = write_json(temp_write_path, live_data, crypto)
    
        if success:
            os.rename(temp_write_path, live_path)
            return True
        else:
            # Fallback to plain write
            with open(temp_write_path, 'w') as f:
                json.dump(live_data, f, indent=2)
            os.rename(temp_write_path, live_path)
            return True


    def _atomic_add_subnotebook_to_structure(self, live_structure, subnotebook_data, parent_id):
        """
        Atomically add the restored subnotebook to its parent - WITH CRYPTO SUPPORT
        """
        import json
        import os
        from notebook_operations import read_json, write_json
    
        # 🟢 FIX: Get crypto from context (already set in restore_subnotebook)
        crypto = getattr(self, '_current_crypto', None)
    
        # Use read_json which handles decryption
        live_data = read_json(live_structure, crypto)
        if live_data is None:
            # If read_json fails, try to read as plain text as fallback
            try:
                with open(live_structure, 'r') as f:
                    live_data = json.load(f)
            except:
                live_data = {}
    
        # Case 1: This is a root notebook (no "notebooks" wrapper)
        if 'id' in live_data and live_data.get('id') == parent_id:
            # This is the parent notebook itself
            if 'subnotebooks' not in live_data:
                live_data['subnotebooks'] = []
            live_data['subnotebooks'].append(subnotebook_data)
    
        # Case 2: This is a notebook collection (has "notebooks" wrapper)
        elif 'notebooks' in live_data:
            # Find the parent notebook in the collection
            def find_parent(notebooks, target_id):
                for nb in notebooks:
                    if nb.get('id') == target_id:
                        return nb
                    found = find_parent(nb.get('subnotebooks', []), target_id)
                    if found:
                        return found
                return None
    
            parent = find_parent(live_data.get('notebooks', []), parent_id)
    
            if parent:
                if 'subnotebooks' not in parent:
                    parent['subnotebooks'] = []
                parent['subnotebooks'].append(subnotebook_data)
            else:
                # Parent not found - add to root
                live_data['notebooks'].append(subnotebook_data)
    
        # Case 3: Something else - treat as root notebook
        else:
            live_data = {
                'id': live_data.get('id', parent_id),
                'name': live_data.get('name', 'Unknown'),
                'parent_id': None,
                'notes': live_data.get('notes', []),
                'subnotebooks': live_data.get('subnotebooks', []) + [subnotebook_data]
            }
    
        # Use write_json which handles encryption
        temp_write_path = live_structure + '.tmp'
        success = write_json(temp_write_path, live_data, crypto)
    
        if success:
            os.rename(temp_write_path, live_structure)
            return True
    
        return False


    def _find_notebook_by_uuid_recursive(self, notebooks, target_uuid):
        """Recursively find a notebook by UUID"""
        for notebook in notebooks:
            if notebook.get('id') == target_uuid:
                return notebook
            found = self._find_notebook_by_uuid_recursive(
                notebook.get('subnotebooks', []), 
                target_uuid
            )
            if found:
                return found
        return None


    def _collect_all_uuids(self, notebook_data, uuid_set):
        """Recursively collect all UUIDs in a notebook hierarchy"""
        if 'id' in notebook_data:
            uuid_set.add(notebook_data['id'])
    
        for note in notebook_data.get('notes', []):
            if 'id' in note:
                uuid_set.add(note['id'])
    
        for sub in notebook_data.get('subnotebooks', []):
            self._collect_all_uuids(sub, uuid_set)


    def _is_note_uuid(self, uuid, notes_path):
        """Check if UUID exists in notes.json - WITH CRYPTO SUPPORT"""
        if not os.path.exists(notes_path):
            return False
        from notebook_operations import read_json
        data = read_json(notes_path, getattr(self, '_current_crypto', None))
        return uuid in data if data else False


    def _is_file_uuid(self, uuid, files_path):
        """Check if UUID exists in files.json"""
        if not os.path.exists(files_path):
            return False
        with open(files_path, 'r') as f:
            return uuid in json.load(f)


    def _is_subnotebook_uuid(self, uuid, structure_path):
        """Check if UUID belongs to a subnotebook"""
        if not os.path.exists(structure_path):
            return False
        with open(structure_path, 'r') as f:
            struct_data = json.load(f)
    
        def check_notebook(notebooks):
            for nb in notebooks:
                if nb.get('id') == uuid:
                    return True
                if check_notebook(nb.get('subnotebooks', [])):
                    return True
            return False
    
        return check_notebook(struct_data.get('notebooks', []))