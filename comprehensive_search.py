#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
from datetime import datetime, timezone
import os
import re
import shutil
from datetime import timezone
import json

def _ensure_utc(dt):
    """Convert datetime to UTC-aware if naive, ensure UTC if aware"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
from query_parser import QueryParser

class ComprehensiveSearch:
    def __init__(self, note_manager, ui_methods=None):
        self.manager = note_manager
        self.ui = ui_methods
        from search_system import SimpleSearch
        from git_resurrection import GitHistoryMiner
        from timeline_engine import TimelineEngine
        self.simple_search = SimpleSearch(note_manager, ui_methods)
        self.history_miner = GitHistoryMiner(note_manager)
        self.timeline_engine = TimelineEngine(note_manager)
        self._current_crypto = None
    
    def process(self, query, context=None, crypto=None, mode='search'):
        """
        Universal search processor.
        """
        self._current_crypto = crypto
        self._current_context = context  # 🟢 ADD THIS
        self._is_global_search = False    # 🟢 ADD THIS
    
        # Load all unlocked notebooks FIRST
        if hasattr(self.manager, 'load_for_search'):
            self.manager.load_for_search()
    
        # Step 1: Parse query
        in_home = (context is None or context == 'home')
        parsed = QueryParser.parse(query, in_home=in_home)
    
        # 🟢 Set global flag from parsed query
        self._is_global_search = parsed['is_global']
        
        # Step 2: Load notebooks for search
        if hasattr(self.manager, 'load_for_search'):
            self.manager.load_for_search()
        
        # Step 3: Route based on mode
        results = []  # 🟢 FIX: Initialize as empty list

        if mode == 'timeline':
            results = self._get_timeline_items(context, crypto) or []
        elif mode == 'activity':
            results = self._get_activity_items(context, parsed, crypto) or []
        else:
            # Normal search mode
            results = self._get_search_items(parsed, context, crypto) or []
        
        # Step 4: Apply filters
        if parsed['actions'] or parsed['type'] or parsed['date_range']:
            results = self._apply_filters(results, parsed)
        
        # Step 5: Deduplicate by UUID
        results = self._deduplicate(results)
        
        # Step 6: Sort by date
        # Step 6: Sort by date - handle both naive and aware datetimes
        def get_sort_date(item):
            date = item.get('date')
            if date is None:
                return datetime.min.replace(tzinfo=timezone.utc)
            if date.tzinfo is None:
                return date.replace(tzinfo=timezone.utc)
            return date

        results.sort(key=get_sort_date, reverse=True)
        
        return {
            'results': results[:50],  # Limit
            'total': len(results),
            'query_parsed': parsed,
            'context': context,
            'mode': mode
        }
    
    def _get_search_items(self, parsed, context, crypto):
        """Collect items for normal search"""
        target_notebooks = self._resolve_notebooks(parsed, context)
        
        results = []
        seen_uuids = set()

        # Define action groups
        CURRENT_ACTIONS = ['CREATED', 'UPDATED', 'EDITED']
        HISTORICAL_ACTIONS = ['DELETED', 'RENAMED', 'RESTORED', 'ERASED']

        # Get actions to process (all if none specified)
        actions = parsed['actions'] if parsed['actions'] else CURRENT_ACTIONS + HISTORICAL_ACTIONS

        # BLANK QUERY - show ALL items of specified action types
        if not parsed['text']:
            for action in actions:
                # CURRENT ITEMS (created/updated/edited)
                if action in CURRENT_ACTIONS:
                    for notebook in target_notebooks:
                        # Add notebook itself - ONLY if type matches
                        if not notebook.parent_id and (not parsed['type'] or parsed['type'] == 'notebook'):
                            enhanced = self._enhance_notebook_result({}, notebook, crypto)
                            if enhanced and enhanced.get('uuid') not in seen_uuids:
                                seen_uuids.add(enhanced['uuid'])
                                results.append(enhanced)
                        
                        # Add all notes and subnotebooks recursively
                        def add_all_items(nb):
                            # Add notes - ONLY if type matches (note or file)
                            if not parsed['type'] or parsed['type'] == 'note' or parsed['type'] == 'file':
                                for note in nb.notes:
                                    # Skip if type doesn't match
                                    if parsed['type'] == 'file' and not note.is_file_note:
                                        continue
                                    if parsed['type'] == 'note' and note.is_file_note:
                                        continue
                                    if note.id in seen_uuids:
                                        continue
                                    
                                    # For UPDATED/EDITED, only include if modified
                                    if action in ['UPDATED', 'EDITED']:
                                        if note.updated > note.created:
                                            seen_uuids.add(note.id)
                                            result = self._create_note_result(note, nb, crypto)
                                            # Get the last commit message for this note
                                            root = self.manager._find_root_notebook(nb)
                                            if root and hasattr(root, 'custom_path') and root.custom_path:
                                                import subprocess
                                                cmd = ["git", "log", "-1", "--grep", note.id, "--pretty=format:%B", "--all"]
                                                git_result = subprocess.run(cmd, cwd=root.custom_path, capture_output=True, text=True)
                                                if git_result.returncode == 0 and git_result.stdout:
                                                    result['commit_message'] = git_result.stdout
                                            results.append(result)
                                    
                                    # For CREATED, include all - get FIRST commit (creation)
                                    elif action == 'CREATED':
                                        seen_uuids.add(note.id)
                                        result = self._create_note_result(note, nb, crypto)
                                        # Get the FIRST commit message for this note (creation)
                                        root = self.manager._find_root_notebook(nb)
                                        if root and hasattr(root, 'custom_path') and root.custom_path:
                                            import subprocess
                                            # 🟢 FIX: Use --reverse to get the first commit
                                            cmd = ["git", "log", "--reverse", "--grep", note.id, "--pretty=format:%B", "--all"]
                                            git_result = subprocess.run(cmd, cwd=root.custom_path, capture_output=True, text=True)
                                            if git_result.returncode == 0 and git_result.stdout:
                                                # Take the first commit message (creation)
                                                first_commit = git_result.stdout.split('\n')[0]
                                                result['commit_message'] = first_commit
                                        results.append(result)
                            
                            # Add subnotebooks - ONLY if type matches 'sub'
                            if not parsed['type'] or parsed['type'] == 'sub':
                                for sub in nb.subnotebooks:
                                    if sub.id not in seen_uuids:
                                        seen_uuids.add(sub.id)
                                        results.append(self._create_notebook_result(sub, crypto))
                                    add_all_items(sub)

                        add_all_items(notebook)
                
                # HISTORICAL ITEMS
                elif action in HISTORICAL_ACTIONS:
                    # Skip if type filter doesn't match
                    if parsed['type'] and parsed['type'] not in ['note', 'file', 'notebook', 'sub']:
                        continue
                
                    items = []
                    if action == 'DELETED':
                        items = self.history_miner.find_deleted_items("", quiet=True)
                    elif action == 'RENAMED':
                        items = self.history_miner.find_renamed_items("", quiet=True)
                    elif action == 'RESTORED':
                        items = self.history_miner.find_restored_items("", quiet=True)
                    elif action == 'ERASED':
                        items = self.history_miner.find_erased_items("", quiet=True)
                
                    for item in items:
                        # Filter by type
                        if parsed['type']:
                            item_type = 'notebook' if item.get('is_subnotebook') else ('file' if item.get('is_file_note') else 'note')
                            if parsed['type'] != item_type:
                                continue
                    
                        if item.get('uuid') not in seen_uuids:
                            # Determine if item should be included based on scope
                            include_item = False
                            
                            if parsed['is_global']:
                                include_item = True
                            elif parsed['scope']:
                                include_item = self._belongs_to_notebooks(item, target_notebooks)
                            elif context is not None:
                                include_item = self._belongs_to_notebooks(item, target_notebooks)
                            else:
                                include_item = True
                            
                            if include_item:
                                seen_uuids.add(item['uuid'])
                                # Set appropriate flags
                                if action == 'DELETED':
                                    item['is_deleted'] = True
                                    item['is_renamed'] = False
                                    item['is_erased'] = False
                                elif action == 'RENAMED':
                                    item['is_renamed'] = True
                                    item['is_deleted'] = False
                                    item['is_erased'] = False
                                elif action == 'ERASED':
                                    item['is_erased'] = True
                                    item['is_deleted'] = False
                                    item['is_renamed'] = False
                                elif action == 'RESTORED':
                                    item['is_restored'] = True
                                results.append(item)

        # WITH TEXT - filter items by text AND action
        else:
            # Current items (if UPDATED/EDITED in actions)
            if any(a in CURRENT_ACTIONS for a in actions):
                current = self.simple_search.search(parsed['text'])
                for item in current:
                    if item['type'] == 'current_note':
                        note, nb = self.manager.find_note_by_id(item['notebook_id'], item['note_id'])
                        if note and nb:
                            # File type filtering
                            if parsed['type'] == 'file' and not note.is_file_note:
                                continue
                            if parsed['type'] == 'note' and note.is_file_note:
                                continue
                            
                            # Check if this note belongs to the target hierarchy
                            belongs = False
                            
                            if parsed['is_global']:
                                belongs = True
                            elif parsed['scope']:
                                root = self.manager._find_root_notebook(nb)
                                for target_nb in target_notebooks:
                                    if nb.id == target_nb.id or root.id == target_nb.id:
                                        belongs = True
                                        break
                            elif context is not None:
                                root = self.manager._find_root_notebook(nb)
                                for target_nb in target_notebooks:
                                    if nb.id == target_nb.id or root.id == target_nb.id:
                                        belongs = True
                                        break
                            else:
                                belongs = True
                            
                            if belongs:
                                # For UPDATED/EDITED, only include if modified
                                if 'UPDATED' in actions or 'EDITED' in actions:
                                    if note.updated > note.created:
                                        if note.id not in seen_uuids:
                                            seen_uuids.add(note.id)
                                            results.append(self._create_note_result(note, nb, crypto))
                                # For CREATED, include all - get FIRST commit
                                elif 'CREATED' in actions:
                                    if note.id not in seen_uuids:
                                        seen_uuids.add(note.id)
                                        result = self._create_note_result(note, nb, crypto)
                                        # Get the FIRST commit message (creation)
                                        root = self.manager._find_root_notebook(nb)
                                        if root and hasattr(root, 'custom_path') and root.custom_path:
                                            import subprocess
                                            cmd = ["git", "log", "--reverse", "--grep", note.id, "--pretty=format:%B", "--all"]
                                            git_result = subprocess.run(cmd, cwd=root.custom_path, capture_output=True, text=True)
                                            if git_result.returncode == 0 and git_result.stdout:
                                                first_commit = git_result.stdout.split('\n')[0]
                                                result['commit_message'] = first_commit
                                        results.append(result)
                    
                    elif item['type'] == 'current_notebook':
                        nb = self.manager.find_notebook_by_id(item['notebook_id'])
                        if nb:
                            belongs = False
                            
                            if parsed['is_global']:
                                belongs = True
                            elif parsed['scope']:
                                root = self.manager._find_root_notebook(nb)
                                for target_nb in target_notebooks:
                                    if nb.id == target_nb.id or root.id == target_nb.id:
                                        belongs = True
                                        break
                            elif context is not None:
                                root = self.manager._find_root_notebook(nb)
                                for target_nb in target_notebooks:
                                    if nb.id == target_nb.id or root.id == target_nb.id:
                                        belongs = True
                                        break
                            else:
                                belongs = True
                            
                            if belongs and nb.id not in seen_uuids:
                                seen_uuids.add(nb.id)
                                results.append(self._create_notebook_result(nb, crypto))
            
            # Historical items - include if action matches
            if parsed['text'] or parsed['type']:
                for action in HISTORICAL_ACTIONS:
                    # Skip if actions are specified and this action isn't requested
                    if parsed['actions'] and action not in parsed['actions']:
                        continue
                    
                    items = []
                    search_text = parsed['text'] if parsed['text'] else ""
                    
                    if action == 'DELETED':
                        items = self.history_miner.find_deleted_items(search_text, quiet=True)
                    elif action == 'RENAMED':
                        items = self.history_miner.find_renamed_items(search_text, quiet=True)
                    elif action == 'RESTORED':
                        items = self.history_miner.find_restored_items(search_text, quiet=True)
                    elif action == 'ERASED':
                        items = self.history_miner.find_erased_items(search_text, quiet=True)
                    
                    for item in items:
                        # Filter by type if specified
                        if parsed['type']:
                            item_type = 'notebook' if item.get('is_subnotebook') else ('file' if item.get('is_file_note') else 'note')
                            if parsed['type'] != item_type:
                                continue
                        
                        if item.get('uuid') not in seen_uuids:
                            # Determine if item should be included based on scope
                            include_item = False
                            
                            if parsed['is_global']:
                                include_item = True
                            elif parsed['scope']:
                                include_item = self._belongs_to_notebooks(item, target_notebooks)
                            elif context is not None:
                                include_item = self._belongs_to_notebooks(item, target_notebooks)
                            else:
                                include_item = True
                            
                            if include_item:
                                seen_uuids.add(item['uuid'])
                                # Set appropriate flags
                                if action == 'DELETED':
                                    item['is_deleted'] = True
                                    item['is_renamed'] = False
                                    item['is_erased'] = False
                                elif action == 'RENAMED':
                                    item['is_renamed'] = True
                                    item['is_deleted'] = False
                                    item['is_erased'] = False
                                elif action == 'ERASED':
                                    item['is_erased'] = True
                                    item['is_deleted'] = False
                                    item['is_renamed'] = False
                                elif action == 'RESTORED':
                                    item['is_restored'] = True
                                results.append(item)
        
        return results

    def _create_note_result(self, note, notebook, crypto):
        result = {
            'type': 'current_note',
            'uuid': note.id,
            'title': note.title,
            'is_file_note': note.is_file_note,
            'file_extension': getattr(note, 'file_extension', None),
            'date': note.updated,
            'notebook_id': notebook.id,
            'notebook_name': notebook.name,
            '_crypto': crypto,
            '_current_context': self._current_context,
            '_is_global': self._is_global_search
        }
        return result

    def _create_notebook_result(self, notebook, crypto):
        """Helper to create notebook result dict"""
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        metadata = ops.get_notebook_metadata(notebook.id) or {}
    
        return {
            'type': 'current_notebook',
            'uuid': notebook.id,
            'title': notebook.name,
            'name': notebook.name,
            'is_subnotebook': notebook.parent_id is not None and notebook.parent_id != notebook.id,
            'parent_id': notebook.parent_id,
            'date': datetime.now(timezone.utc),
            'notebook_id': notebook.id,
            'note_count': metadata.get('note_count', 0),
            'file_count': metadata.get('file_count', 0),
            'sub_count': metadata.get('sub_count', 0),
            '_crypto': crypto,
            '_current_context': self._current_context,  # 🟢 ADD THIS
            '_is_global': self._is_global_search         # 🟢 ADD THIS for g* support
        }
    
    def _get_timeline_items(self, note_id, crypto):
        """Get timeline versions for a note"""
        results = []
        note, notebook = self.manager.find_note_by_id(None, note_id)
        if not note or not notebook:
            return results
        
        versions = self.timeline_engine.get_item_timeline(note_id, notebook.id, crypto=crypto)
        for version in versions:
            results.append({
                'type': 'timeline_version',
                'uuid': version.get('uuid'),
                'title': version.get('title'),
                'date': version.get('date'),
                'message': version.get('commit_message'),
                'commit_hash': version.get('commit_hash'),
                'temp_dir': version.get('temp_dir'),
                '_crypto': crypto
            })
        
        return results
    
    def _get_activity_items(self, notebook_id, parsed, crypto):
        """Get activity items for a notebook"""
        from activity_view import ActivityView
        activity = ActivityView(self.manager, self.ui)
        activity.fetch_activity(50, notebook_id)
        
        results = []
        for commit in activity.commits:
            results.append({
                'type': 'activity',
                'uuid': commit.get('uuid'),
                'title': commit.get('subject'),
                'date': commit.get('date'),
                'action': commit.get('action'),
                'notebook_name': commit.get('item_notebook_name'),
                'full_path': commit.get('full_path'),
                'hash': commit.get('hash'),
                '_crypto': crypto
            })
        
        return results
    
    def _resolve_notebooks(self, parsed, context):
        notebooks = []

        # If in* scope exists, find that notebook
        if parsed['scope']:
            target_name = parsed['scope']['notebook']
            
            # If global is set, search across all roots for that notebook
            if parsed['is_global']:
                for nb in self.manager.notebooks:
                    clean = nb.name.replace('🔐 ', '').replace('🔒 ', '')
                    if target_name.lower() in clean.lower():
                        return [nb] + self._get_all_subnotebooks(nb)
                return []
            
            # If not global, search within current context
            if context and isinstance(context, str) and len(context) > 10:
                root = self.manager.find_notebook_by_id(context)
                if root:
                    def find_in_hierarchy(notebook):
                        clean = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
                        if target_name.lower() in clean.lower():
                            return notebook
                        for sub in notebook.subnotebooks:
                            found = find_in_hierarchy(sub)
                            if found:
                                return found
                        return None
                    found = find_in_hierarchy(root)
                    if found:
                        return [found] + self._get_all_subnotebooks(found)
            else:
                # Home screen with in* - search ALL notebooks (including subnotebooks) recursively
                def find_notebook_recursive(notebook_list, target_name):
                    for nb in notebook_list:
                        clean = nb.name.replace('🔐 ', '').replace('🔒 ', '')
                        if target_name.lower() in clean.lower():
                            return nb
                        # Recursively search subnotebooks
                        found = find_notebook_recursive(nb.subnotebooks, target_name)
                        if found:
                            return found
                    return None
                
                found = find_notebook_recursive(self.manager.notebooks, target_name)
                if found:
                    return [found] + self._get_all_subnotebooks(found)
                else:
                    return []

        # No in* scope
        if parsed['is_global']:
            for nb in self.manager.notebooks:
                notebooks.append(nb)
                notebooks.extend(self._get_all_subnotebooks(nb))
            return notebooks

        if context and isinstance(context, str) and len(context) > 10:
            nb = self.manager.find_notebook_by_id(context)
            if nb:
                notebooks = [nb] + self._get_all_subnotebooks(nb)
            return notebooks

        for nb in self.manager.notebooks:
            notebooks.append(nb)
            notebooks.extend(self._get_all_subnotebooks(nb))

        return notebooks

    def _get_all_subnotebooks(self, notebook):
        """Recursively get all subnotebooks"""
        subs = []
        for sub in notebook.subnotebooks:
            subs.append(sub)
            subs.extend(self._get_all_subnotebooks(sub))
        return subs
        
    def _in_target_notebooks(self, notebook_id, target_notebooks):
        """Check if notebook_id is in target list"""
        return any(nb.id == notebook_id for nb in target_notebooks)
    
    def _belongs_to_notebooks(self, item, target_notebooks):
        """Check if historical item belongs to any target notebook"""
        if not target_notebooks:
            return True
        
        # Get the parent_id from the item
        parent_id = item.get('parent_id')
        if not parent_id:
            return False
        
        # Convert to string for safe comparison
        parent_id_str = str(parent_id)
        
        # Check if parent_id matches any target notebook
        for nb in target_notebooks:
            # Handle both notebook objects and string IDs
            if hasattr(nb, 'id'):
                nb_id = str(nb.id)
            else:
                nb_id = str(nb)
            
            if nb_id == parent_id_str:
                return True
        
        return False
    
    def _enhance_note_result(self, result, note, notebook, crypto):
        """Enhance note result with metadata"""
        result['uuid'] = note.id
        result['title'] = note.title
        result['is_file_note'] = note.is_file_note
        result['file_extension'] = getattr(note, 'file_extension', None)
        result['date'] = note.updated
        result['notebook_name'] = notebook.name
        result['notebook_id'] = notebook.id
        result['_crypto'] = crypto or getattr(note, '_crypto', None)
        return result
    
    def _enhance_notebook_result(self, result, notebook, crypto):
        """Enhance notebook result with metadata"""
        result['type'] = 'current_notebook'
        result['uuid'] = notebook.id
        result['title'] = notebook.name        # 🟢 Add this
        result['name'] = notebook.name          # 🟢 Add this
        result['is_subnotebook'] = notebook.parent_id is not None and notebook.parent_id != notebook.id
        result['date'] = datetime.now(timezone.utc)
        result['notebook_id'] = notebook.id
        result['_crypto'] = crypto or getattr(notebook, '_crypto', None)
    
        # Add counts
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        metadata = ops.get_notebook_metadata(notebook.id) or {}
        result['note_count'] = metadata.get('note_count', 0)
        result['file_count'] = metadata.get('file_count', 0)
        result['sub_count'] = metadata.get('sub_count', 0)
    
        return result
    
    def _apply_filters(self, results, parsed):
        """Apply action, type, and date filters"""
        if not results:
            return []
        
        filtered = []
        
        # Check if we're filtering for 'created*'
        for_created = parsed['actions'] and 'CREATED' in parsed['actions']
        
        for r in results:
            # Skip if result is None
            if not r:
                continue
            
            # Action filter
            if parsed['actions']:
                action = self._get_action(r, for_created=for_created)
                
                # Check if this item's action matches ANY requested action
                action_match = False
                for req_action in parsed['actions']:
                    # Handle UPDATED/EDITED as synonyms
                    if req_action in ['UPDATED', 'EDITED'] and action in ['UPDATED', 'EDITED']:
                        action_match = True
                        break
                    elif action == req_action:
                        action_match = True
                        break
                
                if not action_match:
                    continue
            
            # Type filter
            if parsed['type']:
                item_type = self._get_type(r)
                
                if parsed['type'] == 'note' and item_type != 'note':
                    continue
                if parsed['type'] == 'file' and not r.get('is_file_note'):
                    continue
                if parsed['type'] == 'sub' and not r.get('is_subnotebook') and r.get('type') != 'current_notebook':
                    continue
            
            # Date filter
            if parsed['date_range']:
                d = r.get('date')
                if not d:
                    continue
                start, end = parsed['date_range']
                d = _ensure_utc(d)
                start = _ensure_utc(start)
                end = _ensure_utc(end)
                
                if not (start <= d <= end):
                    continue
            
            filtered.append(r)
        
        return filtered

    
    def _get_action(self, result, for_created=False):
        """Determine action from result - safely handle missing fields"""
        if not result:
            return 'UNKNOWN'
        
        # Check commit message first (strongest signal)
        if result.get('commit_message'):
            msg = result['commit_message'].upper()
            if 'CREATED' in msg:
                return 'CREATED'
            elif 'UPDATED' in msg or 'EDITED' in msg:
                return 'UPDATED'
            elif 'DELETED' in msg:
                return 'DELETED'
            elif 'RENAMED' in msg:
                return 'RENAMED'
            elif 'RESTORED' in msg:
                return 'RESTORED'
            elif 'ERASED' in msg:
                return 'ERASED'
        
        # For current items
        result_type = result.get('type', '')
        
        if result_type == 'current_note':
            note_id = result.get('uuid') or result.get('note_id')
            notebook_id = result.get('notebook_id')
            if note_id and notebook_id:
                note, _ = self.manager.find_note_by_id(notebook_id, note_id)
                if note:
                    if for_created:
                        return 'CREATED'
                    if note.updated > note.created:
                        return 'UPDATED'
                    return 'CREATED'
            return 'CREATED'
        
        elif result_type == 'current_notebook':
            return 'CREATED'
        
        # For historical items
        elif result.get('is_erased'):
            return 'ERASED'
        elif result.get('is_renamed'):
            return 'RENAMED'
        elif 'RESTORED' in str(result.get('commit_message', '')):
            return 'RESTORED'
        elif 'DELETED' in str(result.get('commit_message', '')):
            return 'DELETED'
        
        return 'UNKNOWN'

    
    def _get_type(self, result):
        """Determine type from result - safely handle missing fields"""
        if not result:
            return 'unknown'
    
        # Get type from result dict
        result_type = result.get('type', '')
    
        if result_type == 'current_note':
            return 'file' if result.get('is_file_note') else 'note'
        elif result_type == 'current_notebook':
            # 🟢 FIX: Check if parent_id equals id (root) or different (sub)
            if result.get('parent_id') == result.get('uuid') or result.get('parent_id') == result.get('id'):
                return 'notebook'  # Root notebook
            else:
                return 'sub'  # Subnotebook
        elif result.get('is_subnotebook'):
            return 'sub'
        elif result.get('is_file_note'):
            return 'file'
        elif result.get('title'):
            return 'note'
        return 'unknown'
    
    def _deduplicate(self, results):
        """Remove duplicates by UUID"""
        seen = set()
        unique = []
        for r in results:
            uid = r.get('uuid')
            if uid and uid not in seen:
                seen.add(uid)
                unique.append(r)
        return unique
    
    # Keep compatibility methods for existing calls
    def search(self, query):
        """Compatibility wrapper for old search calls"""
        data = self.process(query, mode='search')
        self.results = data['results']
        self.query = query
        self.current_page = 0
        return self.results
    
    def search_in_notebook(self, query, notebook_id):
        """Compatibility wrapper for old notebook search calls"""
        data = self.process(query, context=notebook_id, mode='search')
        self.results = data['results']
        self.query = query
        self.current_page = 0
        return self.results
    
    def show_note_timeline(self, note_id, notebook_id, crypto=None):
        """Show timeline for a note"""
        # Find the notebook
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            print("❌ Notebook not found")
            return
    
        # Get the ROOT notebook (where the git repo actually is)
        root = self.manager._find_root_notebook(notebook)
        if not root:
            print("❌ Root notebook not found")
            return
    
        # Get the actual path
        if hasattr(root, 'custom_path') and root.custom_path:
            notebook_path = root.custom_path
        else:
            # Try to construct from name and ID
            folder_name = f"{root.name}-{root.id}"
            notebook_path = os.path.join(self.manager.notebooks_root, folder_name)
    
        # If crypto not provided, try to get it
        if not crypto and root.id in self.manager.encrypted_notebooks:
            crypto = self.manager.session_keys.get(root.id)
            if not crypto:
                from crypto import Crypto
                folder_name = f"{root.name}-{root.id}"
                crypto = Crypto.retrieve_for_folder(folder_name)
                if crypto:
                    self.manager.session_keys[root.id] = crypto
    
        # Create timeline engine and pass the ROOT notebook ID
        from timeline_engine import TimelineEngine
        engine = TimelineEngine(self.manager)
        versions = engine.get_item_timeline(note_id, root.id, crypto=crypto)
    
        # Convert to expected format
        data = {'results': versions}
        from cs_ui import show_timeline
        return show_timeline(data, self.ui, self)
    
    def _show_timeline_version_screen(self, version_data):
        """
        Show a specific timeline version.
        """
        import shutil
        import os
        import json
        from datetime import datetime

        # If temp_dir is missing, try to reconstruct it now
        if 'temp_dir' not in version_data or not version_data.get('temp_dir'):
            from timeline_engine import TimelineEngine
            engine = TimelineEngine(self.manager)
    
            crypto = version_data.get('_crypto')
        
            # 🟢 FIX: Check if this is a DELETED commit
            commit_hash = version_data['commit_hash']
            target_hash = commit_hash
        
            if 'DELETED' in version_data.get('message', ''):
                # Get the commit before deletion
                import subprocess
                cmd = ["git", "rev-parse", f"{commit_hash}^"]
                result = subprocess.run(cmd, cwd=version_data['notebook_path'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    target_hash = result.stdout.strip()
                    print(f"🔍 DELETED commit, using parent: {target_hash[:8]}")
        
            version = engine.create_version_at_commit(
                version_data['uuid'],
                version_data['notebook_path'],
                target_hash,  # ← Use target_hash instead of commit_hash
                version_data.get('message', ''),
                crypto=crypto
            )
        
            if version and 'temp_dir' in version:
                version_data = version
            else:
                print("Error: Cannot load this version")
                input("Press Enter to continue...")
                return
    
        # Now display the version...
    
        # Now display the version
        temp_dir = version_data.get('temp_dir')
        if not temp_dir or not os.path.exists(temp_dir):
            print("Error: Cannot load this version")
            input("Press Enter to continue...")
            return
    
        item_type = version_data.get('item_type', 'note')

        if item_type in ['notebook', 'subnotebook']:
            self._show_timeline_notebook(version_data)
        else:
            self._show_timeline_note(version_data)
    

    def _show_search_notebook_view(self, notebook_id, page=0):
        """Show notebook view within comprehensive search context - WITH CRYPTO SUPPORT"""
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return "continue"

        # Handle encryption if needed
        if notebook_id in self.manager.encrypted_notebooks:
            crypto = self.manager.get_crypto(notebook_id)
            if not crypto:
                return "continue"
            notebook = self.manager.find_notebook_by_id(notebook_id)
            if not notebook:
                return "continue"

        while True:
            # Get terminal dimensions
            terminal_width, terminal_height = shutil.get_terminal_size()
            self.ui.clear_screen()

            # 🟢 CHECK ACTIVITY - MUST BE HERE BEFORE ANY FOOTER USAGE
            has_activity = False
            try:
                root = self.manager._find_root_notebook(notebook)
                if root and hasattr(root, 'custom_path') and root.custom_path:
                    repo_path = root.custom_path
                    if os.path.exists(os.path.join(repo_path, ".git")):
                        import subprocess
                        cmd = ["git", "rev-list", "--count", "HEAD"]
                        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
                        if result.returncode == 0:
                            total_commits = int(result.stdout.strip())
                            has_activity = total_commits > 1
            except:
                pass

            # DYNAMIC PAGINATION
            try:
                _, terminal_height = shutil.get_terminal_size()
                fixed_lines = 3 + 1 + 2 + 3

                if notebook.subnotebooks:
                    fixed_lines += 2
                    available_for_notes = terminal_height - fixed_lines
                    items_per_page = int(available_for_notes * 0.9)
                else:
                    available_for_notes = terminal_height - fixed_lines
                    items_per_page = int(available_for_notes * 0.95)

                items_per_page = max(1, items_per_page)

            except:
                items_per_page = 10

            # Calculate pagination
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(notebook.notes))
            paginated_notes = notebook.notes[start_idx:end_idx]
            total_pages = (len(notebook.notes) + items_per_page - 1) // items_per_page if notebook.notes else 1
            current_page = page + 1

            # Build smart header
            notebook_path = self.manager.get_notebook_hierarchy(notebook.id)
            if notebook_path:
                path_names = [nb.name for nb in notebook_path]
                full_path = "/".join(path_names) + "/"
                reserved = len(" (search)") + 4
                available_width = terminal_width - reserved

                if len(full_path) <= available_width:
                    display_path = full_path
                else:
                    display_segments = []
                    for segment in reversed(path_names):
                        test_segments = [segment] + display_segments
                        test_path = ".../" + "/".join(test_segments) + "/"
                        if len(test_path) <= available_width:
                            display_segments.insert(0, segment)
                        else:
                            break

                    if display_segments:
                        display_path = ".../" + "/".join(display_segments) + "/"
                    else:
                        last = path_names[-1]
                        max_len = available_width - len("...//") - 3
                        if max_len > 5:
                            display_path = ".../" + last[:max_len-3] + ".../"
                        else:
                            display_path = ".../"
            else:
                display_path = notebook.name

            self.ui.print_header(f"{display_path} (search)")

            # Show notes
            if notebook.notes:
                print("Notes & Files:")
                for i, note in enumerate(paginated_notes, 1):
                    updated = note.updated.strftime("%b %d %H:%M")
                    timestamp_text = f"[Updated: {updated}]"
                    available_for_title = terminal_width - len(str(i)) - len(timestamp_text) - 6

                    title_display = note.title
                    if len(title_display) > available_for_title:
                        title_display = title_display[:available_for_title-3] + "..."

                    padding = available_for_title - len(title_display)
                    print(f"[{i}] {title_display}{' ' * padding}{timestamp_text}")

                # Page indicator
                if total_pages > 1:
                    page_text = f"Page {current_page} of {total_pages}"
                    centered_text = page_text.center(terminal_width)
                    text_start = (terminal_width - len(page_text)) // 2
                    text_end = text_start + len(page_text)
                    line_chars = list(centered_text)

                    if current_page > 1:
                        left_pos = text_start - 4 - 2
                        if left_pos >= 0:
                            line_chars[left_pos:left_pos+2] = list("<<")

                    if current_page < total_pages:
                        right_pos = text_end + 4
                        if right_pos + 2 <= terminal_width:
                            line_chars[right_pos:right_pos+2] = list(">>")

                    print()
                    print("".join(line_chars))

            # Show subnotebooks
            if notebook.subnotebooks:
                if len(paginated_notes) > 0:
                    print()
                next_number = len(paginated_notes) + 1
                sub_count = len(notebook.subnotebooks)
                if sub_count == 1:
                    print(f"Sub-notebook: ({sub_count} sub)")
                    print(f"[{next_number}] View Sub-notebook =>")
                else:
                    print(f"Sub-notebooks: ({sub_count} subs)")
                    print(f"[{next_number}] View Sub-notebooks =>")

            # Empty state
            if not notebook.notes and not notebook.subnotebooks:
                print("This notebook is empty.")
                print()

            # Footer
            # Footer
            # Footer
            # Footer
            footer_options = ["[C]reate", "[B]ack", "[Q]uit"]
            if notebook.notes or notebook.subnotebooks:
                footer_options.insert(1, "[V]iew")
                if notebook.notes:
                    footer_options.insert(2, "[D]elete")
            if has_activity:
                insert_pos = 2 if notebook.notes else 1
                footer_options.insert(insert_pos, "[A]ctivity")
            if total_pages > 1:
                if current_page < total_pages:
                    footer_options.append("[N]ext")
                if current_page > 1:
                    footer_options.append("[P]rev")

            self.ui.print_footer("  ".join(footer_options))

            # Handle input
            cmd = self.ui.get_input("> ").strip().lower()

            if cmd == "b":
                return "continue"
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    self.ui.clear_screen()
                    import sys
                    sys.exit(0)
                else:
                    confirm = self.ui.get_input("Quit Terminal Notes? [y/N]: ")
                    if confirm.lower() == "y":
                        self.ui.clear_screen()
                        import sys
                        sys.exit(0)
                    else:
                        continue

            elif cmd == "c":
                choice = self.ui.show_create_choice_screen(notebook)
                if choice == "1":
                    self.ui.create_note(notebook)
                    notebook = self.manager.find_notebook_by_id(notebook.id)
                    page = 0
                elif choice == "2":
                    self.ui.create_file_note(notebook)
                    notebook = self.manager.find_notebook_by_id(notebook.id)
                    page = 0
                elif choice == "3":
                    self.ui.create_subnotebook(notebook)
                    notebook = self.manager.find_notebook_by_id(notebook.id)
                    page = 0
            
            elif cmd == "a" and has_activity:
                from activity_view import ActivityView
                av = ActivityView(self.manager, self.ui)
                av.show(notebook.id)
                # After returning, refresh notebook
                notebook = self.manager.find_notebook_by_id(notebook.id)
                page = 0
                continue
            
            elif cmd.startswith("v"):
                if cmd == "v":
                    try:
                        user_input = self.ui.get_input("Enter item number: ")
                        if not user_input:
                            continue
                        display_num = int(user_input)
                    except ValueError:
                        continue
                else:
                    try:
                        display_num = int(cmd[1:])
                    except ValueError:
                        continue

                if display_num <= len(paginated_notes):
                    idx = display_num - 1
                    if 0 <= idx < len(paginated_notes):
                        note = paginated_notes[idx]
                        crypto = notebook._crypto if hasattr(notebook, '_crypto') else None
                        self._show_search_note_with_timeline(note.id, 0, crypto)
                        notebook = self.manager.find_notebook_by_id(notebook.id)
                elif display_num == len(paginated_notes) + 1 and notebook.subnotebooks:
                    self._show_subnotebooks_list(notebook.id, 0)
            elif cmd.startswith("d") and notebook.notes:
                if cmd == "d":
                    try:
                        display_num = int(self.ui.get_input("Enter note number to delete: "))
                    except ValueError:
                        continue
                else:
                    try:
                        display_num = int(cmd[1:])
                    except ValueError:
                        continue

                if 1 <= display_num <= len(paginated_notes):
                    note = paginated_notes[display_num - 1]
                    print(f"Delete note '{note.title}':")
                    print("  1. Forget (keep in history)")
                    print("  2. Erase (remove completely)")
                    choice = self.ui.get_input("Choose [1/2] or Enter to cancel: ")

                    if choice == "1":
                        from eraser import Eraser
                        Eraser(self.manager, self.ui).delete_item(note.id, 'forget', note.title)
                        print("Note forgotten")
                    elif choice == "2":
                        confirm = self.ui.get_input("Type 'erase' to confirm: ")
                        if confirm.lower() == "erase":
                            from eraser import Eraser
                            Eraser(self.manager, self.ui).delete_item(note.id, 'erase', note.title)
                            print("Note completely erased!")
                        else:
                            continue
                    else:
                        continue

                    self.manager.save_data()
                    notebook = self.manager.find_notebook_by_id(notebook.id)
                    total_pages = (len(notebook.notes) + items_per_page - 1) // items_per_page if notebook.notes else 1
                    if page >= total_pages and total_pages > 0:
                        page = total_pages - 1
            elif cmd == "n" and page < total_pages - 1:
                page += 1
            elif cmd == "p" and page > 0:
                page -= 1

    def _show_subnotebooks_list(self, notebook_id, page=0):
        """Show list of subnotebooks for a notebook (gateway screen)"""
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return

        while True:
            self.ui.clear_screen()
            terminal_width, terminal_height = shutil.get_terminal_size()

            # Header - matching main app style
            separator = "" * terminal_width
            print(separator)
            
            # Get smart path like main app
            hierarchy = self.manager.get_notebook_hierarchy(notebook.id)
            if hierarchy:
                path_names = [nb.name for nb in hierarchy]
                full_path = "/".join(path_names)
                if len(full_path) > terminal_width - 20:
                    if len(path_names) > 2:
                        display_path = ".../" + "/".join(path_names[-2:])
                    else:
                        display_path = full_path
                else:
                    display_path = full_path
                header_title = f"{display_path} =>"
            else:
                header_title = f"{notebook.name} =>"
            
            print(f"{header_title:^{terminal_width}}")
            print(separator)

            # Pagination calculation - same as main app
            fixed_ui_lines = 8
            available = terminal_height - fixed_ui_lines
            items_per_page = int(available * 0.9)
            items_per_page = max(1, items_per_page)

            total_items = len(notebook.subnotebooks)
            total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1

            if page >= total_pages:
                page = max(0, total_pages - 1)

            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            paginated_items = notebook.subnotebooks[start_idx:end_idx]
            current_page = page + 1

            # Title line - matching main app
            # Title line - matching main app
            if total_items == 1:
                print(f"Sub-notebook of '{notebook.name}' ({total_items} sub):")
            else:
                print(f"Sub-notebooks of '{notebook.name}' ({total_items} subs):")

            # Display items with counts - matching main app style
            if paginated_items:
                for i, sub_nb in enumerate(paginated_items, 1):
                    note_count = sub_nb.get_total_note_count()
                    sub_count = sub_nb.get_total_subnotebook_count()
                    file_count = sub_nb.get_file_note_count()
                    regular_note_count = note_count - file_count

                    parts = []
                    if regular_note_count > 0:
                        parts.append(f"{regular_note_count} note{'s' if regular_note_count != 1 else ''}")
                    if file_count > 0:
                        parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
                    if sub_count > 0:
                        parts.append(f"{sub_count} sub{'s' if sub_count != 1 else ''}")

                    count_display = f" ({', '.join(parts)})" if parts else ""
                    print(f"[{i}] {sub_nb.name}{count_display}")
            else:
                print("No subnotebooks yet.")
                print()

            # Page indicator with arrows - matching main app
            if total_pages > 1:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(terminal_width)
                text_start = (terminal_width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)

                if current_page > 1:
                    left_pos = text_start - 4 - 2
                    if left_pos >= 0:
                        line_chars[left_pos:left_pos+2] = list("<<")

                if current_page < total_pages:
                    right_pos = text_end + 4
                    if right_pos + 2 <= terminal_width:
                        line_chars[right_pos:right_pos+2] = list(">>")

                print()
                print("".join(line_chars))
                print()
            else:
                print()

            # Footer - matching main app
            # Footer - matching main app
            print("" * terminal_width)
            footer = ["[V]iew", "[B]ack", "[Q]uit"]

            if total_pages > 1:
                if current_page < total_pages:
                    footer.append("[N]ext")
                if current_page > 1:
                    footer.append("[P]rev")

            print("  ".join(footer))
            print()

            cmd = self.ui.get_input("> ").strip().lower()

            if cmd == "b":
                break
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    self.ui.clear_screen()
                    import sys
                    sys.exit(0)
                else:
                    confirm = self.ui.get_input("Quit Terminal Notes? [y/N]: ")
                    if confirm.lower() == "y":
                        self.ui.clear_screen()
                        import sys
                        sys.exit(0)
            elif cmd == "n" and current_page < total_pages:
                page += 1
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd.startswith("v"):
                if cmd == "v":
                    try:
                        idx = int(self.ui.get_input(f"Enter number [1-{len(paginated_items)}]: ")) - 1
                    except ValueError:
                        continue
                else:
                    try:
                        idx = int(cmd[1:]) - 1
                    except ValueError:
                        continue

                if 0 <= idx < len(paginated_items):
                    sub_nb = paginated_items[idx]
                    self._show_search_notebook_view(sub_nb.id, 0)
            
    def _show_search_note_with_timeline(self, note_id, page=0, crypto=None):
        """Show current note with identical layout to normal notes + timeline"""
        # 🟢 FIX: Ensure page is integer
        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 0
        note, notebook = self.manager.find_note_by_id(None, note_id)
        if not note or not notebook:
            return "continue"

        # 🟢 FIX: Ensure content is loaded for encrypted notes
        if hasattr(self, 'ops'):
            content = self.ops.get_note_content(note.id, notebook.id)
            if content is not None:
                note.content = content
        elif notebook.id in self.manager.encrypted_notebooks:
            # Try to load content for encrypted notes
            crypto = self.manager.session_keys.get(notebook.id)
            if crypto:
                from notebook_operations import read_json
                folder_path = notebook.custom_path
                if folder_path:
                    content_file = "files.json" if note.is_file_note else "notes.json"
                    content_path = os.path.join(folder_path, content_file)
                    content_map = read_json(content_path, crypto) or {}
                    if note.id in content_map:
                        note.content = content_map[note.id]

        # Store crypto in the note object
        if crypto:
            note._crypto = crypto
        elif notebook.id in self.manager.encrypted_notebooks:
            # Try to get crypto if not provided
            crypto = self.manager.session_keys.get(notebook.id)
            if not crypto:
                from crypto import Crypto
                folder_name = f"{notebook.name}-{notebook.id}"
                crypto = Crypto.retrieve_for_folder(folder_name)
                if crypto:
                    self.manager.session_keys[notebook.id] = crypto
            note._crypto = crypto

        while True:
            # Get terminal size
            terminal_width, terminal_height = shutil.get_terminal_size()
            self.ui.clear_screen()
            # 🟢 Check if there's any activity (more than just the initial commit)
            has_activity = False
            try:
                root = self.manager._find_root_notebook(notebook)
                if root and hasattr(root, 'custom_path') and root.custom_path:
                    repo_path = root.custom_path
                    if os.path.exists(os.path.join(repo_path, ".git")):
                        import subprocess
                        cmd = ["git", "rev-list", "--count", "HEAD"]
                        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
                        if result.returncode == 0:
                            total_commits = int(result.stdout.strip())
                            has_activity = total_commits > 1
            except:
                pass

            # HEADER - 3 LINES (no empty line after)
            # HEADER - Just the note title
            # HEADER - Smart path + note title (like main navigation)
            # HEADER - Smart path + note title (like main navigation)
            separator = "" * terminal_width
            print(separator)

            # Get the smart path without numbers
            try:
                # Get the root notebook for proper hierarchy
                root = self.manager._find_root_notebook(notebook)
                hierarchy = self.manager.get_notebook_hierarchy(root.id)
    
                if hierarchy and len(hierarchy) > 0:
                    # Get all notebook names in the path
                    path_names = []
                    for nb in hierarchy:
                        clean_name = nb.name.replace('🔐 ', '').replace('🔒 ', '')
                        path_names.append(clean_name)
        
                    # Add the current notebook if it's not the root
                    if notebook.id != root.id and notebook.name not in path_names:
                        clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
                        path_names.append(clean_name)
        
                    # Smart truncation
                    full_path = '/'.join(path_names)
                    max_path_width = terminal_width - len(note.title) - 5  # Reserve space for title + ": "
        
                    if len(full_path) <= max_path_width:
                        display_path = full_path
                    else:
                        # Show last few segments with ellipsis
                        if len(path_names) > 3:
                            display_path = '.../' + '/'.join(path_names[-3:])
                        else:
                            display_path = '.../' + '/'.join(path_names[-2:])
        
                    header_text = f"{display_path}: {note.title}"
                else:
                    # Fallback to just notebook name
                    clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
                    header_text = f"{clean_name}: {note.title}"
            except Exception as e:
                # If anything fails, just show the note title
                header_text = note.title

            print(f"{header_text:^{terminal_width}}")
            print(separator)

            # NOTE INFO - 2 LINES
            if note.is_file_note:
                print(f"File Name: {note.title} [.{note.file_extension} file]")
            else:
                print(f"Note Title: {note.title}")

            timestamp = note.updated.strftime("%b %d %H:%M")
            created = note.created.strftime("%b %d")
            print(f"Created: {created}  Updated: {timestamp}")

            # SEPARATOR - 1 LINE
            print("" * terminal_width)

            # Calculate pagination using UI's helper
            pagination_info = self.ui.calculate_note_pagination(note.content, terminal_height)
            wrapped_lines = pagination_info['wrapped_lines']
            available_content_lines = pagination_info['available_content_lines']
            needs_pagination = pagination_info['needs_pagination']
            total_pages = pagination_info['total_pages']

            # Use available_content_lines directly
            max_content_lines = max(1, available_content_lines)

            if needs_pagination:
                # Ensure we don't go beyond the last page
                if page >= total_pages:
                    page = total_pages - 1

                start_idx = page * max_content_lines
                end_idx = start_idx + max_content_lines
                paginated_lines = wrapped_lines[start_idx:end_idx]
                current_page = page + 1
            else:
                # If content fits on one page, always show page 0
                if page > 0:
                    page = 0
                paginated_lines = wrapped_lines
                current_page = 1
                total_pages = 1

            # Display content lines
            for line in paginated_lines:
                print(line)

            # Page indicator with arrows
            if needs_pagination:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(terminal_width)
                text_start = (terminal_width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)

                if current_page > 1:
                    left_arrow_pos = text_start - 4 - 2
                    if left_arrow_pos >= 0:
                        line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")

                if current_page < total_pages:
                    right_arrow_pos = text_end + 4
                    if right_arrow_pos + 2 <= terminal_width:
                        line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")

                print()
                print("".join(line_chars))
                print()
            else:
                print()  # Blank line when no pagination

            # Footer options
            footer_options = ["[E]dit", "[V]iew"]

            if note.is_file_note:
                footer_options.append("[X]port")

            footer_options.append("[T]imeline")
            footer_options.append("[R]ename")
            footer_options.append("[B]ack")

            if needs_pagination:
                if current_page < total_pages:
                    footer_options.append("[N]ext")
                if current_page > 1:
                    footer_options.append("[P]rev")

            if self.ui.should_show_jump():
                footer_options.append("[J]ump")

            footer_options.append("[Q]uit")

            print("  ".join(footer_options))
            print()

            cmd = self.ui.get_input("> ").strip().lower()

            if cmd == "b":
                break
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd == "n" and current_page < total_pages:
                page += 1
            elif cmd == "e":
                # Edit note
                original_content = note.content
                if note.is_file_note:
                    new_content = self.ui.external_editor(
                        note.content, 
                        file_extension=note.file_extension
                    )
                else:
                    new_content = self.ui.external_editor(note.content)

                if new_content is not None and new_content != original_content:
                    from notebook_operations import NotebookOperations
                    ops = NotebookOperations(self.manager)
                    ops.edit_note(note, notebook, new_content)
                    print("Note updated!")
                    self.ui.get_input("Press Enter to continue...")
                    # Refresh content
                    note.content = new_content
            elif cmd == "v":
                if note.is_file_note:
                    self.ui.external_editor(
                        note.content, 
                        read_only=True, 
                        file_extension=note.file_extension
                    )
                else:
                    self.ui.external_editor(note.content, read_only=True)
            elif cmd == "r":
                self.ui.rename_note(note)
                # Refresh after rename
                note, notebook = self.manager.find_note_by_id(None, note.id)
            elif cmd == "x" and note.is_file_note:
                self.ui.export_file_note(note)
            elif cmd == "t":
                result = self.show_note_timeline(
                    note.id, 
                    notebook.id, 
                    crypto=note._crypto if hasattr(note, '_crypto') else None
                )
                if result == "exit":
                    return "exit"
            elif cmd == "q":
                confirm = self.ui.get_input("Quit? [y/N]: ")
                if confirm.lower() == "y":
                    self.ui.clear_screen()
                    return "exit"

        return "continue"
    
    def _handle_result_view(self, result):
        """Handle viewing any type of result"""
    
        if result['type'] == 'resurrected_note':
            from git_resurrection import GitHistoryMiner
            miner = GitHistoryMiner(self.manager)
        
            if result.get('is_subnotebook') is True:
                # 🟢 USE GIT RESURRECTION FOR SUBNOTEBOOKS
                miner.display_resurrected_item(result, self.ui)
                return "navigate"
            else:
                miner.display_resurrected_item(result, self.ui)
                return "navigate"
            
        elif result['type'] == 'timeline_version':
            self._show_timeline_version_screen(result['timeline_data'])
            return "continue"
    
        elif result['type'] == 'current_note':
            result_val = self._show_search_note_with_timeline(result['note_id'], 0)
            if result_val == "exit":
                return "exit"
            return "navigate"
    
        elif result['type'] == 'current_notebook':
            notebook_id = result['notebook_id']
            page = 0
            self.search_nav_push('current_notebook', {
                'notebook_id': notebook_id,
                'page': page,
                'from_search': True
            })
            self._show_search_notebook_view(notebook_id, page)
            return "navigate"
    
        return "continue"

    def _show_timeline_note(self, version_data):
        """Display a timeline note version using note view pagination."""
        import shutil
        import json
        import os
        from datetime import datetime

        temp_dir = version_data['temp_dir']

        # Determine if it's a file or note
        is_file = version_data.get('item_type') == 'file'
        content_file = "files.json" if is_file else "notes.json"

        # Load the content
        content_path = os.path.join(temp_dir, content_file)
        if not os.path.exists(content_path):
            print("Error: Content file not found")
            input("Press Enter to continue...")
            return

        with open(content_path, 'r') as f:
            content_map = json.load(f)

        content = content_map.get(version_data['uuid'], "")
        title = version_data.get('title', 'Unknown')
        file_ext = version_data.get('file_extension')

        page = 0
        while True:
            # Get terminal size
            terminal_width, terminal_height = shutil.get_terminal_size()
            
            # ========== USE NOTE VIEW'S PAGINATION ==========
            # Same calculation as show_note_view_screen
            pagination_info = self.ui.calculate_note_pagination(content, terminal_height)
            wrapped_lines = pagination_info['wrapped_lines']
            available_content_lines = pagination_info['available_content_lines']
            needs_pagination = pagination_info['needs_pagination']
            total_pages = pagination_info['total_pages']
            
            max_content_lines = max(1, available_content_lines)
            
            if needs_pagination:
                if page >= total_pages:
                    page = total_pages - 1
                start_idx = page * max_content_lines
                end_idx = start_idx + max_content_lines
                paginated_lines = wrapped_lines[start_idx:end_idx]
                current_page = page + 1
            else:
                if page > 0:
                    page = 0
                paginated_lines = wrapped_lines
                current_page = 1
                total_pages = 1
            # ========== END ==========
            
            self.ui.clear_screen()
            
            # Header (same as note view)
            print("" * terminal_width)
            header = f"Timeline: {title} [{'FILE' if is_file else 'NOTE'}]"
            print(f"{header:^{terminal_width}}")
            print("" * terminal_width)
            
            # Note info (same as note view)
            if is_file:
                print(f"File Name: {title} [.{file_ext} file]")
            else:
                print(f"Note Title: {title}")
            
            # Date info
            date_str = ""
            if 'date' in version_data:
                date = version_data['date']
                if hasattr(date, 'strftime'):
                    date_str = date.strftime("%Y-%m-%d %H:%M")
            timestamp = date_str if date_str else "Unknown"
            print(f"Created: {timestamp}  Updated: {timestamp}")
            
            # Separator
            print("" * terminal_width)
            
            # Display content
            for line in paginated_lines:
                print(line)
            
            # Page indicator with arrows (same as note view)
            if needs_pagination:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(terminal_width)
                text_start = (terminal_width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)
                
                if current_page > 1:
                    left_arrow_pos = text_start - 4 - 2
                    if left_arrow_pos >= 0:
                        line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")
                
                if current_page < total_pages:
                    right_arrow_pos = text_end + 4
                    if right_arrow_pos + 2 <= terminal_width:
                        line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")
                
                print()
                print("".join(line_chars))
            else:
                print()
            
            # Footer (same as note view but without Edit)
            print("" * terminal_width)
            footer = ["[V]iew"]
            
            if needs_pagination:
                if current_page > 1:
                    footer.append("[P]rev")
                if current_page < total_pages:
                    footer.append("[N]ext")
            
            footer.append("[B]ack")
            footer.append("[Q]uit")
            
            print("  ".join(footer))
            print()
            
            cmd = self.ui.get_input("> ").lower()
            
            if cmd == "b":
                break
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    self.ui.clear_screen()
                    import sys
                    sys.exit(0)
                else:
                    confirm = self.ui.get_input("Quit Terminal Notes? [y/N]: ")
                    if confirm.lower() == "y":
                        self.ui.clear_screen()
                        import sys
                        sys.exit(0)
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd == "n" and needs_pagination and page < total_pages - 1:
                page += 1
            elif cmd == "v":
                if is_file and file_ext:
                    self.ui.external_editor(content, read_only=True, file_extension=file_ext)
                else:
                    self.ui.external_editor(content, read_only=True)

    def _show_timeline_notebook(self, version_data):
        """Display a timeline notebook version."""
        temp_dir = version_data['temp_dir']
    
        # Create temp manager and display
        from activity_view import ActivityView
        av = ActivityView(self.manager, self.ui)
        av._show_resurrected_notebook_screen(temp_dir)

    def _get_action_from_message(self, message):
        """Extract action from commit message using type: prefix"""
        if message.startswith('type: CREATED'):
            return "CREATED"
        elif message.startswith('type: UPDATED') or message.startswith('type: EDITED'):
            return "UPDATED"
        elif message.startswith('type: DELETED'):
            return "DELETED"
        elif message.startswith('type: RENAMED'):
            return "RENAMED"
        elif message.startswith('type: RESTORED'):
            return "RESTORED"
        elif message.startswith('type: ERASED'):
            return "ERASED"
        return "UNKNOWN"