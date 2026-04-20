#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True

import os
import subprocess
import shutil
from datetime import datetime

class ActivityView:
    def __init__(self, manager, ui):
        self.manager = manager
        self.ui = ui
        self.commits = []
        self.current_page = 0
        self.notebook_id = None
    
    def fetch_activity(self, limit=50, notebook_id=None):
        """Gather latest commits - globally or for specific notebook hierarchy"""
        all_commits = []
        self.current_notebook_id = notebook_id

        if notebook_id:
            notebook = self.manager.find_notebook_by_id(notebook_id)
            if not notebook:
                return

            root = self.manager._find_root_notebook(notebook)
            if not hasattr(root, 'custom_path') or not root.custom_path:
                return
        
            repo_path = root.custom_path
            self.notebook_name = notebook.name

            # Collect UUIDs with their full hierarchical paths
            def collect_uuids_with_path(nb, uuid_to_path, current_path=None):
                if current_path is None:
                    current_path = [nb.name]
                else:
                    current_path = current_path + [nb.name]
    
                # Store this notebook's UUID
                uuid_to_path[nb.id] = current_path.copy()
    
                # Store all notes in this notebook
                for note in nb.notes:
                    uuid_to_path[note.id] = current_path.copy()
    
                # Process subnotebooks recursively
                for sub in nb.subnotebooks:
                    collect_uuids_with_path(sub, uuid_to_path, current_path)

            uuid_to_path = {}
            collect_uuids_with_path(notebook, uuid_to_path)

            # Build UUID list for grep
            uuid_list = list(uuid_to_path.keys())
            if not uuid_list:
                self.commits = []
                return

            # Get commits that mention these UUIDs
            uuid_pattern = "\\|".join(uuid_list[:50])
            cmd = [
                "git", "log", f"-n{limit}", "--all",
                "--grep", uuid_pattern,
                "--pretty=format:%H|%ai|%s|%b%n---END---"
            ]

            try:
                result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
                if result.returncode == 0 and result.stdout:
                    commits = result.stdout.split('---END---')
                
                    for commit in commits:
                        if not commit.strip():
                            continue
                    
                        lines = commit.strip().split('\n')
                        if not lines:
                            continue
                    
                        first_line = lines[0]
                        parts = first_line.split('|', 3)
                        if len(parts) < 4:
                            continue
                    
                        hash_, date_str, subject, body = parts
                        rest = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                        full_body = body + "\n" + rest
                    
                        uuid = self._extract_uuid(subject, full_body)
                    
                        try:
                            date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
                        except ValueError:
                            date = datetime.now()
                    
                        action = self._determine_action(subject)
                    
                        # Get the path info for this UUID
                        path_parts = uuid_to_path.get(uuid, [notebook.name])

                        # Calculate relative path from the viewing notebook
                        viewing_notebook_name = notebook.name
                        viewing_index = -1

                        # Find where the viewing notebook appears in the path
                        for i, part in enumerate(path_parts):
                            if part == viewing_notebook_name:
                                viewing_index = i
                                break
                        
                        

                        if viewing_index != -1:
                            # Item is at or below viewing notebook
                            # Build path RELATIVE to viewing notebook (viewing notebook becomes root)
                            relative_parts = path_parts[viewing_index:]
    
                            if len(relative_parts) == 1:
                                # Item is the viewing notebook itself
                                display_name = f"[{viewing_notebook_name}]"
                            elif len(relative_parts) == 2:
                                # Direct child
                                display_name = f"[{relative_parts[1]}]"
                            elif len(relative_parts) == 3:
                                # Two levels deep
                                display_name = f"[{relative_parts[1]}/{relative_parts[2]}]"
                            else:
                                # Three or more levels deep - show last two with ellipsis
                                display_name = f"[.../{relative_parts[-2]}/{relative_parts[-1]}]"
                        else:
                            # Item is above viewing notebook - show from viewing notebook's parent perspective
                            # Find the closest ancestor path
                            if viewing_index == -1:
                                # Item is completely outside - show last segment
                                if len(path_parts) == 1:
                                    display_name = f"[{path_parts[0]}]"
                                else:
                                    display_name = f"[.../{path_parts[-2]}/{path_parts[-1]}]"

                        crypto = None
                        if hasattr(notebook, '_crypto'):
                            crypto = notebook._crypto

                        all_commits.append({
                            'hash': hash_,
                            'date': date,
                            'subject': subject,
                            'body': full_body,
                            'uuid': uuid,
                            'action': action,
                            'notebook_path': repo_path,
                            'notebook_name': notebook.name,
                            'item_notebook_name': display_name,
                            'full_path': ' → '.join(path_parts),
                            '_crypto': crypto
                        })
            except Exception:
                pass
    
        else:
            # Global mode - scan all root notebooks
            for nb in self.manager.notebooks:
                if not hasattr(nb, 'custom_path') or not nb.custom_path:
                    continue
            
                path = nb.custom_path
                try:    
                    cmd = [
                        "git", "log", f"-n{limit}", "--all",
                        "--pretty=format:%H|%ai|%s|%b%n---END---"
                    ]
                    result = subprocess.run(cmd, cwd=path, capture_output=True, text=True)
                    if result.returncode == 0 and result.stdout:
                        commits = result.stdout.split('---END---')
                        for commit in commits:
                            if commit.strip():
                                lines = commit.strip().split('\n')
                                if lines:
                                    first_line = lines[0]
                                    parts = first_line.split('|', 3)
                                    if len(parts) >= 4:
                                        hash_, date_str, subject, body = parts
                                        rest_of_body = '\n'.join(lines[1:]) if len(lines) > 1 else ""
                                        full_body = body + "\n" + rest_of_body
                                        uuid = self._extract_uuid(subject, full_body)
                                        try:
                                            date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S %z")
                                        except ValueError:
                                            date = datetime.now()
                            
                                        action = self._determine_action(subject)
                            
                                        all_commits.append({
                                            'hash': hash_,
                                            'date': date,
                                            'subject': subject,
                                            'body': full_body,
                                            'uuid': uuid,
                                            'action': action,
                                            'notebook_path': path,
                                            'notebook_name': nb.name,
                                            'item_notebook_name': nb.name
                                        })
                except Exception:
                    continue

        all_commits.sort(key=lambda x: x['date'], reverse=True)
        self.commits = all_commits[:limit]
    
    def _determine_action(self, subject):
        """Determine action type from commit subject with type: prefix"""
        if subject.startswith('type: CREATED'):
            return "CREATED"
        elif subject.startswith('type: UPDATED') or subject.startswith('type: EDITED'):
            return "UPDATED"
        elif subject.startswith('type: DELETED'):
            return "DELETED"
        elif subject.startswith('type: RENAMED'):
            return "RENAMED"
        elif subject.startswith('type: RESTORED'):
            return "RESTORED"
        elif subject.startswith('type: ERASED'):
            return "ERASED"
        else:
            return "UNKNOWN"
    
    def _extract_uuid(self, subject, body):
        """Extract UUID from commit message - reused from git_resurrection"""
        from git_resurrection import GitHistoryMiner
        # Use the existing method by creating a temporary miner
        miner = GitHistoryMiner(self.manager)
        full = subject + "\n" + (body or "")
        return miner._extract_uuid_from_message(full)
    
    def show(self, notebook_id=None):
        """Main loop for activity screen.
        notebook_id=None: global mode (all notebooks)
        notebook_id=xyz: show activity for that notebook AND all its descendants
        """
    
        self.current_notebook_id = notebook_id
        self._in_search = False
        self.fetch_activity(50, notebook_id)

        while True:
            if self._in_search:
                result = self._search_cs._show_search_results_simple()
                if result == "exit_search":
                    self._in_search = False
                    if hasattr(self, '_search_return_to'):
                        ret = self._search_return_to
                        self.current_page = ret.get('page', 0)
                        self.fetch_activity(50, self.current_notebook_id)
                    continue
                elif result == "exit":
                    return "exit"
                continue

            self.ui.clear_screen()
            term_width, term_height = shutil.get_terminal_size()

            # Dynamic header based on depth
            if notebook_id:
                notebook = self.manager.find_notebook_by_id(notebook_id)
                if notebook:
                    hierarchy = self.manager.get_notebook_hierarchy(notebook_id)
                    if hierarchy and len(hierarchy) > 1:
                        # Show full path for deep navigation
                        path_names = [nb.name.replace('🔐 ', '').replace('🔒 ', '') for nb in hierarchy]
                    
                        # Smart truncation if path too long
                        full_path = '/'.join(path_names)
                        if len(full_path) > term_width - 20:
                            # Show last 3 segments with ellipsis
                            if len(path_names) > 3:
                                display_path = '.../' + '/'.join(path_names[-3:])
                            else:
                                display_path = '.../' + '/'.join(path_names[-2:])
                        else:
                            display_path = full_path
                    
                        header = f"Activity: {display_path}"
                    else:
                        # Root notebook level
                        clean_name = notebook.name.replace('🔐 ', '').replace('🔒 ', '')
                        header = f"Activity: {clean_name} and subnotebooks"
                else:
                    header = "Activity: recent changes (last 50)"
            else:
                header = "Activity: recent changes (last 50)"

            # Print header
            separator = "" * term_width
            print(separator)
            print(f"{header:^{term_width}}")
            print(separator)

            # Pagination calculation
            fixed_after_commits = 6
            available_for_commits = term_height - 3 - fixed_after_commits
            self.items_per_page = available_for_commits
            self.items_per_page = max(1, self.items_per_page)

            total_pages = (len(self.commits) + self.items_per_page - 1) // self.items_per_page

            # Ensure current page is valid
            if self.current_page >= total_pages:
                self.current_page = max(0, total_pages - 1)

            start = self.current_page * self.items_per_page
            end = start + self.items_per_page
            page_commits = self.commits[start:end]

            # Display commits using shared formatter
            from cs_ui import ResultFormatter
            formatter = ResultFormatter(self.manager, term_width)
        
            for i, c in enumerate(page_commits, 1):
                line = formatter._format_activity(c, i)
                print(line)

            # Page indicator
            if total_pages > 1:
                current_page_num = self.current_page + 1
                page_text = f"Page {current_page_num} of {total_pages}"
                centered_text = page_text.center(term_width)
                text_start = (term_width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)
            
                if current_page_num > 1:
                    left_arrow_pos = text_start - 4 - 2
                    if left_arrow_pos >= 0:
                        line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")
            
                if current_page_num < total_pages:
                    right_arrow_pos = text_end + 4
                    if right_arrow_pos + 2 <= term_width:
                        line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")
            
                line = "".join(line_chars)
                print()
                print(line)
            else:
                print()

            # Footer
            print("" * term_width)

            footer_options = []
            if page_commits:
                footer_options.append("[V]iew")
            footer_options.append("[B]ack")

            if total_pages > 1:
                if self.current_page > 0:
                    footer_options.append("[P]rev")
                if self.current_page < total_pages - 1:
                    footer_options.append("[N]ext")

            footer_options.append("[Q]uit")

            print("  ".join(footer_options))
            print()

            cmd = self.ui.get_input("> ")

            # Search handler
            if cmd.startswith("s"):
                self.handle_search(cmd)
                continue
            elif cmd == "b":
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
            elif cmd == "n" and self.current_page < total_pages - 1:
                self.current_page += 1
            elif cmd == "p" and self.current_page > 0:
                self.current_page -= 1
            elif cmd.startswith("v") and page_commits:
                if cmd == "v":
                    try:
                        idx = int(self.ui.get_input("Enter number: ")) - 1
                    except ValueError:
                        continue
                else:
                    try:
                        idx = int(cmd[1:]) - 1
                    except ValueError:
                        continue
            
                if 0 <= idx < len(page_commits):
                    self._view_commit(page_commits[idx])
    
    def _view_commit(self, commit):
        """View a commit using TimelineEngine and GitHistoryMiner"""
        from timeline_engine import TimelineEngine
        from git_resurrection import GitHistoryMiner

        # Handle ERASED tombstone commits
        if commit['subject'].startswith('ERASED') or commit['subject'].startswith('type: ERASED'):
            self.ui.clear_screen()
            term_width = self.ui.terminal_width
            
            # ========== SURGICAL FIX: Extract title correctly ==========
            subject = commit['subject']
            
            # Remove "type: ERASED " prefix
            if subject.startswith('type: ERASED '):
                rest = subject[12:]  # Remove "type: ERASED "
            elif subject.startswith('ERASED '):
                rest = subject[7:]   # Remove "ERASED "
            else:
                rest = subject
            
            # Now rest looks like: "NOTE: rr | in 12"
            # Extract title - everything before " | "
            if ' | ' in rest:
                title_part = rest.split(' | ')[0]
                # Remove "NOTE: " or "FILE: " or "SUBNOTEBOOK: "
                if title_part.startswith('NOTE: '):
                    title = title_part[6:]
                elif title_part.startswith('FILE: '):
                    title = title_part[6:]
                elif title_part.startswith('SUBNOTEBOOK: '):
                    title = title_part[13:]
                else:
                    title = title_part
            else:
                title = rest
            # ========== END FIX ==========
            
            # Get path from commit data
            path_display = "[root]"
            parent_id = commit.get('parent_id')
            notebook_path = commit.get('notebook_path')
            
            if parent_id:
                parent_notebook = self.manager.find_notebook_by_id(parent_id)
                if parent_notebook:
                    hierarchy = self.manager.get_notebook_hierarchy(parent_notebook.id)
                    if hierarchy:
                        from cs_ui import ResultFormatter
                        term_width, _ = shutil.get_terminal_size()
                        formatter = ResultFormatter(self.manager, term_width)
                        path_display = formatter._format_path(hierarchy, None, False, max_length=40)
            elif notebook_path:
                folder_name = os.path.basename(notebook_path)
                if '-' in folder_name:
                    display_name = folder_name.split('-')[0]
                    path_display = f"[{display_name}]"
            
            # Clean display with path
            separator = "" * term_width
            print(separator)
            print(f"{path_display:^{term_width}}")
            print(separator)
            print()
            print("  PERMANENTLY ERASED ITEM".center(term_width))
            print()
            print(f"This item was permanently erased from history.")
            print(f"Item: {title}")
            print()
            print("No content remains - this is a tombstone record only.")
            print()
            print(separator)
            print()
            self.ui.get_input("Press Enter to continue...")
            return
        
        # ... rest of method unchanged ...
        
        # For DELETED items, get commit before
        target_hash = commit['hash']
        if commit['action'] == "DELETED":
            try:
                cmd = ["git", "rev-parse", f"{commit['hash']}^"]
                result = subprocess.run(cmd, cwd=commit['notebook_path'], capture_output=True, text=True)
                if result.returncode == 0:
                    target_hash = result.stdout.strip()
            except:
                pass
        
        # Get FULL commit message from subject AND body
        subject = commit.get('subject', '')
        body = commit.get('body', '')
        full_message = subject
        if body:
            full_message = subject + '\n\n' + body
        
        # Create version using TimelineEngine with FULL message
        engine = TimelineEngine(self.manager)
        version = engine.create_version_at_commit(
            commit['uuid'],
            commit['notebook_path'],
            target_hash,
            full_message,
            crypto=commit.get('_crypto')
        )
        
        if not version:
            print("Could not reconstruct item from this commit.")
            self.ui.get_input("Press Enter to continue...")
            return       
        
        # Convert to format expected by GitHistoryMiner
        result_data = {
            'type': 'resurrected_note',
            'title': version.get('title', 'Unknown'),
            'content': version.get('content', ''),
            'file_extension': version.get('file_extension'),
            'uuid': version.get('uuid'),
            'temp_dir': version.get('temp_dir'),
            'is_file_note': version.get('item_type') == 'file',
            'is_subnotebook': version.get('item_type') in ['notebook', 'subnotebook'],
            'date': commit.get('date'),
            'item_info': version.get('item_info', {}),
            'notebook_path': commit.get('notebook_path'),
            'commit_message': version.get('commit_message', commit.get('subject')),
            'action': commit.get('action'),
            '_crypto': version.get('_crypto'),
            'parent_id': version.get('parent_id'),
            'root_id': version.get('root_id'),
            'is_deleted': commit.get('action') == 'DELETED',
        }
        
        # Delegate to GitHistoryMiner for display
        miner = GitHistoryMiner(self.manager)
        
        # Check if it's a notebook/subnotebook
        if result_data['is_subnotebook']:
            self._show_resurrected_notebook(result_data)
        else:
            miner.display_resurrected_item(result_data, self.ui)
            
            if commit.get('action') == 'DELETED' and hasattr(self, '_handle_activity_restore'):
                self._current_restore_version = version
    
    def _show_resurrected_notebook(self, result_data):
        """Show resurrected notebook using git_resurrection"""
        from git_resurrection import GitHistoryMiner
        miner = GitHistoryMiner(self.manager)
        miner.display_resurrected_item(result_data, self.ui)
    
    def handle_search(self, cmd):
        """Search from activity view - uses same universal search as notebook view"""
    
        # Just pass through to UI's universal search handler
        # It already knows how to handle context based on current screen
        result = self.ui.handle_search(cmd)
    
        # If returning from search, restore activity view
        if result == "exit_search":
            if hasattr(self, '_search_return_to'):
                ret = self._search_return_to
                self.current_page = ret.get('page', 0)
                self.fetch_activity(50, self.notebook_id)
        elif result == "exit":
            return "exit"