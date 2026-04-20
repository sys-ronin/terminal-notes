#!/usr/bin/env python3
"""
Resurrected UI - Display and interaction for resurrected items
Completely separate from git_resurrection.py (data layer)
"""
import sys
sys.dont_write_bytecode = True
import os
import json
import shutil
from terminal_notes_core import Notebook
from datetime import datetime

class ResurrectedUI:
    def __init__(self, manager, ui):
        self.manager = manager
        self.ui = ui
        self._current_crypto = None
    
    def display_item(self, result_data, ui):
        """Display a resurrected item - main entry point"""
        # 🟢 FIX: Handle erased items specially
        if result_data.get('is_erased', False):
            self._display_erased_item(result_data, ui)
            return
        temp_dir = result_data.get('temp_dir')
        if not temp_dir or not os.path.exists(temp_dir):
            print("Error: Cannot display resurrected item")
            ui.get_input("Press Enter to continue...")
            return

        if result_data.get('is_subnotebook'):
            self._display_notebook(result_data, ui)
        else:
            self._display_note(result_data, ui)
    
    # =========================================================================
    # NOTE DISPLAY
    # =========================================================================
    
    def _display_note(self, result_data, ui):
        """Display a resurrected note with full temporal-spatial layout"""
        temp_dir = result_data['temp_dir']

        # Load content
        is_file = result_data.get('is_file_note', False)
        content_file = "files.json" if is_file else "notes.json"
        content_path = os.path.join(temp_dir, content_file)

        content = ""
        if os.path.exists(content_path):
            with open(content_path, 'r') as f:
                content_map = json.load(f)
            content = content_map.get(result_data.get('uuid'), result_data.get('content', ''))

        title = result_data.get('title', 'Unknown')
        file_ext = result_data.get('file_extension')

        # ========== GET PATH FOR HEADER ==========
        path_display = "[root]"
        parent_id = result_data.get('parent_id')
        notebook_path = result_data.get('notebook_path')
        
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
        
        # ========== GET DATES AND ACTION ==========
        commit_msg = result_data.get('commit_message', '')
        
        item_info = result_data.get('item_info', {})
        created_date = None
        if 'created' in item_info:
            try:
                if isinstance(item_info['created'], str):
                    created_date = datetime.fromisoformat(item_info['created'])
                else:
                    created_date = item_info['created']
            except:
                pass
        
        if not created_date:
            created_date = result_data.get('date')
        
        action_date = result_data.get('date')
        
        action = None
        if 'ERASED' in commit_msg:
            action = "erased"
        elif 'RENAMED' in commit_msg:
            action = "renamed"
        elif 'RESTORED' in commit_msg:
            action = "restored"
        elif 'DELETED' in commit_msg:
            action = "deleted"
        elif 'CREATED' in commit_msg:
            action = "created"
        elif 'UPDATED' in commit_msg or 'EDITED' in commit_msg:
            action = "updated"
        
        old_name = result_data.get('old_name', '')
        new_name = result_data.get('new_name', '')

        page = 0
        while True:
            ui.clear_screen()
            width, height = shutil.get_terminal_size()
        
            # ========== HEADER: PATH ONLY ==========
            print("" * width)
            print(f"{path_display:^{width}}")
            print("" * width)
            # ========== END HEADER ==========
        
            # ========== NOTE INFO: TITLE AND TYPE ==========
            if is_file:
                print(f"File Name: {title} [.{file_ext} file]")
            else:
                if action == 'renamed' and old_name and new_name:
                    print(f"Note Title: {old_name} → {new_name}")
                else:
                    print(f"Note Title: {title}")
            # ========== END NOTE INFO ==========
        
            # ========== TIMELINE: CREATED → ACTION ==========
            timeline_parts = []
            
            if created_date:
                if hasattr(created_date, 'strftime'):
                    created_str = created_date.strftime("%b %d %H:%M")
                else:
                    created_str = str(created_date)
                timeline_parts.append(f"Created: {created_str}")
            
            if action_date and action:
                if hasattr(action_date, 'strftime'):
                    action_str = action_date.strftime("%b %d %H:%M")
                else:
                    action_str = str(action_date)
                
                # Surgical fix: Remove rename details from timeline (already shown in title)
                if action == 'renamed':
                    timeline_parts.append(f"{action}: {action_str}")
                else:
                    timeline_parts.append(f"{action}: {action_str}")
            
            print("  ".join(timeline_parts))
            # ========== END TIMELINE ==========
        
            # ========== SEPARATOR ==========
            print("" * width)
            # ========== END SEPARATOR ==========
        
            # ========== PAGINATED CONTENT (USING UI'S CALCULATION) ==========
            # Use the same calculation as note view screen
            pagination_info = ui.calculate_note_pagination(content, height)
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
            # ========== END CONTENT ==========
        
            # ========== PAGE INDICATOR ==========
            if needs_pagination:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(width)
                text_start = (width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)
                
                if current_page > 1:
                    left_arrow_pos = text_start - 4 - 2
                    if left_arrow_pos >= 0:
                        line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")
                
                if current_page < total_pages:
                    right_arrow_pos = text_end + 4
                    if right_arrow_pos + 2 <= width:
                        line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")
                
                print()
                print("".join(line_chars))
            else:
                print()
            # ========== END PAGE INDICATOR ==========
        
            # ========== FOOTER ==========
            print("" * width)
            footer = []
            
            footer.append("[V]iew")
            footer.append("[T]imeline")
            
            if result_data.get('is_deleted', False) or action == 'deleted':
                footer.append("[R]estore")
            
            if is_file:
                footer.append("[X]port")
            
            if needs_pagination:
                if current_page > 1:
                    footer.append("[P]rev")
                if current_page < total_pages:
                    footer.append("[N]ext")
            
            footer.append("[B]ack")
            footer.append("[Q]uit")
            
            print("  ".join(footer))
            print()
            # ========== END FOOTER ==========
        
            cmd = ui.get_input("> ").lower()
        
            if cmd == "b":
                break
            elif cmd == "q" or cmd == "qy":
                if cmd == "qy":
                    ui.clear_screen()
                    import sys
                    sys.exit(0)
                else:
                    confirm = ui.get_input("Quit Terminal Notes? [y/N]: ")
                    if confirm.lower() == "y":
                        ui.clear_screen()
                        import sys
                        sys.exit(0)
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd == "n" and needs_pagination and page < total_pages - 1:
                page += 1
            elif cmd == "v":
                if is_file and file_ext:
                    ui.external_editor(content, read_only=True, file_extension=file_ext)
                else:
                    ui.external_editor(content, read_only=True)
            elif cmd == "t":
                note_uuid = result_data.get('uuid')
                notebook_id = result_data.get('notebook_id')
                
                if not notebook_id:
                    parent_id = result_data.get('parent_id')
                    if parent_id:
                        notebook = self.manager.find_notebook_by_id(parent_id)
                        if notebook:
                            root = self.manager._find_root_notebook(notebook)
                            if root:
                                notebook_id = root.id
                
                if note_uuid and notebook_id:
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(self.manager, ui)
                    cs.show_note_timeline(note_uuid, notebook_id, crypto=result_data.get('_crypto'))
                else:
                    print("Cannot show timeline: missing note or notebook information")
                    ui.get_input("Press Enter to continue...")
            elif cmd == "e" and not result_data.get('is_deleted') and action != 'deleted':
                note_uuid = result_data.get('uuid')
                note, notebook = self.manager.find_note_by_id(None, note_uuid)
                if note and notebook:
                    from terminal_notes_ui import TerminalNotes
                    tn = TerminalNotes()
                    tn.edit_note(note, notebook)
                    ui.get_input("Press Enter to continue...")
                else:
                    print("Cannot edit: note no longer exists in current structure")
                    ui.get_input("Press Enter to continue...")
            elif cmd == "r" and (result_data.get('is_deleted') or action == 'deleted'):
                print("\n" + "=" * 50)
                confirm = ui.get_input(f"Restore '{title}' to its original location? [y/N]: ")
                if confirm.lower() == 'y':
                    result = self._trigger_restore(result_data, ui)
                    if result == "navigate":
                        return "navigate"
                else:
                    print("Restore cancelled.")
                    ui.get_input("Press Enter to continue...")
                    continue
            elif cmd == "x" and is_file:
                self._export_file(content, title, ui)
    
    def _display_erased_item(self, result_data, ui):
        """Display a permanently erased item (tombstone)"""
        import shutil

        ui.clear_screen()
        width, height = shutil.get_terminal_size()

        title = result_data.get('title', 'Unknown')
        
        # ========== SURGICAL FIX: Get path for erased item ==========
        path_display = "[root]"
        parent_id = result_data.get('parent_id')
        notebook_path = result_data.get('notebook_path')
        
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
        # ========== END FIX ==========

        # Header
        separator = "" * width
        print(separator)
        
        # ========== SURGICAL FIX: Show path in header ==========
        print(f"{path_display:^{width}}")
        print(separator)
        # ========== END FIX ==========
        
        # Message
        print("  PERMANENTLY ERASED ITEM".center(width))
        print()
        print(f"This item was permanently erased from history.")
        print(f"Item: {title}")
        print()
        print("No content remains - this is a tombstone record only.")
        print()
        
        # Footer
        print(separator)
        print()
        ui.get_input("Press Enter to continue...")
        
    # =========================================================================
    # NOTEBOOK DISPLAY
    # =========================================================================
    
    def _display_notebook(self, result_data, ui):
        """Display resurrected notebook with full functionality"""
        import json
        import shutil
        import os
    
        temp_dir = result_data['temp_dir']
        if not temp_dir or not os.path.exists(temp_dir):
            print("Error: Resurrected notebook data not available")
            ui.get_input("Press Enter to continue...")
            return

        # Create temp manager and load notebooks
        temp_manager = self._create_temp_manager(temp_dir)
        if not temp_manager:
            print("Error: Could not load resurrected notebook")
            ui.get_input("Press Enter to continue...")
            return

        temp_notebooks = temp_manager.load_all_notebooks()
        if not temp_notebooks:
            print("Error: No resurrected notebook found")
            ui.get_input("Press Enter to continue...")
            return

        notebook = temp_notebooks[0]
    
        # Get parent notebook and crypto
        parent_notebook = result_data.get('parent_notebook')
        crypto = result_data.get('_crypto')
    
        # Decrypt notebook contents if crypto is available
        if crypto:
            def decrypt_notebook_contents(nb):
                for note in nb.notes:
                    if hasattr(note, 'content') and note.content and isinstance(note.content, bytes):
                        try:
                            note.content = crypto.decrypt(note.content)
                        except Exception:
                            pass
                for sub in nb.subnotebooks:
                    decrypt_notebook_contents(sub)
            decrypt_notebook_contents(notebook)
    
        page = 0
        while True:
            ui.clear_screen()
            term_width, term_height = shutil.get_terminal_size()
        
            # Build smart path for header
            path_parts = self._build_notebook_path(notebook, parent_notebook, temp_dir)
        
            # Convert to string with slashes
            full_path = '/'.join(path_parts)
        
            # Smart truncation
            available_width = term_width - len(" [RESURRECTED]") - 4
            display_path = self._truncate_path(full_path, path_parts, available_width)
        
            # Header
            header_title = f"{display_path} [RESURRECTED]"
            print("" * term_width)
            print(f"{header_title:^{term_width}}")
            print("" * term_width)
            print()
        
            # Calculate pagination
            items_per_page, total_pages = self._calculate_pagination(notebook, term_height)
        
            if page >= total_pages and total_pages > 0:
                page = total_pages - 1
        
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(notebook.notes))
            paginated_notes = notebook.notes[start_idx:end_idx]
            current_page = page + 1
        
            # Show notes
            if notebook.notes:
                self._display_notes_section(notebook, paginated_notes, term_width, current_page, total_pages)
            else:
                print("No notes in this notebook.")
                print()
        
            # Show subnotebooks section
            if notebook.subnotebooks:
                self._display_subnotebooks_gateway(notebook, len(paginated_notes), total_pages)
        
            # Footer
            print("" * term_width)
            footer_options = self._build_footer(result_data, total_pages, current_page)
            print("  ".join(footer_options))
            print()
        
            # Handle input
            cmd = ui.get_input("> ").lower().strip()
            
            if self._handle_quit(cmd, ui):
                continue
                
            if cmd == "b":
                break
            elif cmd == "n" and current_page < total_pages:
                page += 1
                continue
            elif cmd == "p" and page > 0:
                page -= 1
                continue
            elif cmd == "r":
                self._trigger_restore(result_data, ui)
                return
            elif cmd.startswith("v") and (notebook.notes or notebook.subnotebooks):
                self._handle_notebook_view(cmd, paginated_notes, notebook, result_data, ui, 
                                         temp_dir, parent_notebook, crypto, page, items_per_page)
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _build_notebook_path(self, notebook, parent_notebook, temp_dir):
        """Build full path for notebook header"""
        import json
        import os
        
        path_parts = []
        current = notebook
        path_parts.append(current.name)
        
        if parent_notebook:
            path_parts.insert(0, parent_notebook.name)
            
            if temp_dir:
                struct_path = os.path.join(temp_dir, "structure.json")
                if os.path.exists(struct_path):
                    with open(struct_path, 'r') as f:
                        struct_data_full = json.load(f)
                    
                    def find_notebook_by_id(nb_data, target_id):
                        if nb_data.get('id') == target_id:
                            return nb_data
                        for sub in nb_data.get('subnotebooks', []):
                            found = find_notebook_by_id(sub, target_id)
                            if found:
                                return found
                        return None
                    
                    if hasattr(parent_notebook, 'parent_id') and parent_notebook.parent_id:
                        for nb_data in struct_data_full.get('notebooks', []):
                            parent_parent = find_notebook_by_id(nb_data, parent_notebook.parent_id)
                            if parent_parent:
                                path_parts.insert(0, parent_parent.get('name', '...'))
                                break
        return path_parts
    
    def _truncate_path(self, full_path, path_parts, available_width):
        """Smart path truncation"""
        if len(full_path) <= available_width:
            return full_path
        else:
            segments = path_parts
            test_parts = []
            
            for i in range(len(segments) - 1, -1, -1):
                new_test = segments[i] + ('/' + '/'.join(test_parts) if test_parts else '')
                if i > 0:
                    new_test = '.../' + new_test
                
                if len(new_test) <= available_width:
                    test_parts.insert(0, segments[i])
                else:
                    break
            
            if test_parts:
                display_path = '/'.join(test_parts)
                if len(segments) > len(test_parts):
                    display_path = '.../' + display_path
                return display_path
            else:
                return segments[-1][:available_width-4] + "..."
    
    def _calculate_pagination(self, notebook, term_height):
        """Calculate items per page and total pages"""
        try:
            fixed_lines = 3 + 1 + 2 + 3
            if notebook.subnotebooks:
                fixed_lines += 2
                available_for_notes = term_height - fixed_lines
                items_per_page = int(available_for_notes * 0.9)
            else:
                available_for_notes = term_height - fixed_lines
                items_per_page = int(available_for_notes * 0.95)
            items_per_page = max(1, items_per_page)
        except:
            items_per_page = 10
        
        total_pages = (len(notebook.notes) + items_per_page - 1) // items_per_page
        return items_per_page, total_pages
    
    def _display_notes_section(self, notebook, paginated_notes, term_width, current_page, total_pages):
        """Display notes section with pagination"""
        file_count = sum(1 for note in notebook.notes if hasattr(note, 'file_extension') and note.file_extension)
        regular_note_count = len(notebook.notes) - file_count
        
        # Header text
        if regular_note_count == 1 and file_count == 0:
            header_text = "Note:"
        elif regular_note_count == 0 and file_count == 1:
            header_text = "File:"
        elif regular_note_count > 0 and file_count > 0:
            header_text = "Notes & Files:"
        elif regular_note_count > 0:
            header_text = "Notes:"
        elif file_count > 0:
            header_text = "Files:"
        else:
            header_text = "Notes & Files:"
        
        counter_parts = []
        if regular_note_count > 0:
            counter_parts.append(f"{regular_note_count} note{'s' if regular_note_count != 1 else ''}")
        if file_count > 0:
            counter_parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
        
        counter_string = f" ({', '.join(counter_parts)})" if counter_parts else ""
        print(f"{header_text}{counter_string}")
        
        # Display notes
        for i, note in enumerate(paginated_notes, 1):
            timestamp = note.updated.strftime("%b %d %H:%M") if hasattr(note, 'updated') else "Unknown"
            timestamp_text = f"[Updated: {timestamp}]"
            
            has_content = hasattr(note, 'content') and note.content is not None
            if not has_content:
                timestamp_text += " [EMPTY]"
            
            available_for_title = term_width - len(str(i)) - len(timestamp_text) - 6
            title_display = note.title
            if len(title_display) > available_for_title:
                title_display = title_display[:available_for_title-3] + "..."
            
            padding = available_for_title - len(title_display)
            print(f"[{i}] {title_display}{' ' * padding}{timestamp_text}")
        
        # Page indicator
        if total_pages > 1:
            page_text = f"Page {current_page} of {total_pages}"
            centered_text = page_text.center(term_width)
            text_start = (term_width - len(page_text)) // 2
            text_end = text_start + len(page_text)
            line_chars = list(centered_text)
            
            if current_page > 1:
                left_pos = text_start - 4 - 2
                if left_pos >= 0:
                    line_chars[left_pos:left_pos+2] = list("<<")
            
            if current_page < total_pages:
                right_pos = text_end + 4
                if right_pos + 2 <= term_width:
                    line_chars[right_pos:right_pos+2] = list(">>")
            
            print()
            print("".join(line_chars))
            if notebook.subnotebooks:
                print()
    
    def _display_subnotebooks_gateway(self, notebook, notes_count, total_pages):
        """Display subnotebooks gateway section"""
        if notes_count == 0 or total_pages <= 1:
            print()
        
        next_number = notes_count + 1
        sub_count = len(notebook.subnotebooks)
        
        if sub_count == 1:
            print(f"Sub-notebook: ({sub_count} sub)")
            print(f"[{next_number}] View Sub-notebook =>")
        else:
            print(f"Sub-notebooks: ({sub_count} subs)")
            print(f"[{next_number}] View Sub-notebooks =>")
    
    def _build_footer(self, result_data, total_pages, current_page):
        """Build footer options"""
        footer = ["[V]iew", "[B]ack"]
        
        if result_data.get('is_deleted'):
            footer.insert(1, "[R]estore")
        
        if total_pages > 1:
            if current_page < total_pages:
                footer.append("[N]ext")
            if current_page > 1:
                footer.append("[P]rev")
        
        footer.append("[Q]uit")
        return footer
    
    def _handle_quit(self, cmd, ui):
        """Handle quit commands"""
        if cmd == "q" or cmd == "qy":
            if cmd == "qy":
                ui.clear_screen()
                import sys
                sys.exit(0)
            else:
                confirm = ui.get_input("Quit Terminal Notes? [y/N]: ")
                if confirm.lower() == "y":
                    ui.clear_screen()
                    import sys
                    sys.exit(0)
                return True
        return False
    
    def _handle_notebook_view(self, cmd, paginated_notes, notebook, result_data, ui, 
                            temp_dir, parent_notebook, crypto, page, items_per_page):
        """Handle view command in notebook"""
        displayed_notes_count = len(paginated_notes)
        total_displayed_items = displayed_notes_count + 1
        
        if cmd == "v":
            try:
                user_input = ui.get_input(f"Enter item number [1-{total_displayed_items}]: ")
                if not user_input:
                    return
                display_num = int(user_input)
            except ValueError:
                return
        else:
            try:
                display_num = int(cmd[1:])
            except ValueError:
                return
        
        idx = display_num - 1
        
        if 0 <= idx < total_displayed_items:
            if idx < displayed_notes_count:
                # Show note
                note = paginated_notes[idx]
                self._display_note_from_notebook(note, result_data, ui)
            elif idx == displayed_notes_count:
                # Show subnotebooks list
                self._display_subnotebooks_list(notebook, ui, temp_dir, parent_notebook, crypto)
    
    def _display_note_from_notebook(self, note, result_data, ui):
        """Display a resurrected note from within a notebook"""
        import shutil

        content = note.content if hasattr(note, 'content') and note.content else ""
        title = note.title
        is_file = hasattr(note, 'file_extension') and note.file_extension is not None
        file_ext = note.file_extension if is_file else None

        page = 0
        while True:
            ui.clear_screen()
            width, height = shutil.get_terminal_size()
        
            # Header
            print("" * width)
            header = f"{title} [HISTORICAL]"
            print(f"{header:^{width}}")
            print("" * width)
        
            # Note info
            if is_file:
                print(f"File Name: {title} [.{file_ext} file]")
            else:
                print(f"Note Title: {title}")
        
            # Show historical info
            if 'date' in result_data:
                date = result_data['date']
                date_str = date.strftime("%Y-%m-%d %H:%M") if hasattr(date, 'strftime') else str(date)
                print(f"Version from: {date_str}")
        
            print("" * width)
        
            # Paginated content
            wrapped = ui.wrap_text(content)
            fixed_lines = 6
            available = height - fixed_lines
            lines_per_page = max(1, available)
        
            total_pages = (len(wrapped) + lines_per_page - 1) // lines_per_page if wrapped else 1
        
            if page >= total_pages:
                page = max(0, total_pages - 1)
        
            start = page * lines_per_page
            end = start + lines_per_page
        
            for line in wrapped[start:end]:
                print(line)
        
            # Page indicator
            if total_pages > 1:
                current = page + 1
                page_text = f"Page {current} of {total_pages}"
                print()
                print(f"{page_text:^{width}}")
        
            # Footer
            print("" * width)
            footer = ["[V]iew"]
            
            # 🟢 ADD TIMELINE BUTTON HERE
            footer.append("[T]imeline")
        
            if total_pages > 1:
                if page > 0:
                    footer.append("[P]rev")
                if page < total_pages - 1:
                    footer.append("[N]ext")
        
            if is_file:
                footer.append("[X]port")
        
            footer.append("[B]ack")
        
            print("  ".join(footer))
            print()
        
            cmd = ui.get_input("> ").lower()
        
            if cmd == "b":
                break
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd == "n" and page < total_pages - 1:
                page += 1
            elif cmd == "v":
                if is_file and file_ext:
                    ui.external_editor(content, read_only=True, file_extension=file_ext)
                else:
                    ui.external_editor(content, read_only=True)
            # 🟢 ADD TIMELINE HANDLER
            elif cmd == "t":
                # Get note UUID and notebook ID
                note_uuid = note.id
                notebook_id = result_data.get('notebook_id')
                
                # If notebook_id not available, try to get from parent notebook
                if not notebook_id:
                    parent_id = result_data.get('parent_id')
                    if parent_id:
                        parent_nb = self.manager.find_notebook_by_id(parent_id)
                        if parent_nb:
                            root = self.manager._find_root_notebook(parent_nb)
                            if root:
                                notebook_id = root.id
                
                if note_uuid and notebook_id:
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(self.manager, ui)
                    cs.show_note_timeline(note_uuid, notebook_id, crypto=result_data.get('_crypto'))
                else:
                    print("Cannot show timeline: missing note or notebook information")
                    ui.get_input("Press Enter to continue...")
            elif cmd == "x" and is_file:
                self._export_file(content, title, ui)
    
    def _display_subnotebooks_list(self, parent_notebook, ui, temp_dir=None, parent_notebook_obj=None, crypto=None):
        """Display list of subnotebooks (gateway screen)"""
        import shutil
        import json
        import os
    
        page = 0
        while True:
            ui.clear_screen()
            term_width, term_height = shutil.get_terminal_size()
        
            # Build path for header
            path_parts = []
            current = parent_notebook
            path_parts.append(current.name)
        
            # Build parent chain
            if temp_dir and hasattr(parent_notebook, 'parent_id') and parent_notebook.parent_id:
                struct_path = os.path.join(temp_dir, "structure.json")
                if os.path.exists(struct_path):
                    with open(struct_path, 'r') as f:
                        struct_data = json.load(f)
                
                    def find_notebook_by_id(nb_data, target_id):
                        if nb_data.get('id') == target_id:
                            return nb_data
                        for sub in nb_data.get('subnotebooks', []):
                            found = find_notebook_by_id(sub, target_id)
                            if found:
                                return found
                        return None
                
                    if parent_notebook.parent_id:
                        for nb_data in struct_data.get('notebooks', []):
                            parent = find_notebook_by_id(nb_data, parent_notebook.parent_id)
                            if parent:
                                path_parts.insert(0, parent.get('name', '...'))
                                break
        
            # Smart truncation
            full_path = '/'.join(path_parts)
            available_width = term_width - len(" [SUBNOTEBOOKS]") - 4
        
            if len(full_path) <= available_width:
                display_path = full_path
            else:
                segments = path_parts
                if len(segments) > 2:
                    display_path = '.../' + '/'.join(segments[-2:])
                else:
                    display_path = '.../' + segments[-1]
        
            # Header
            separator = "" * term_width
            print(separator)
            header_title = f"{display_path} => [SUBNOTEBOOKS]"
            print(f"{header_title:^{term_width}}")
            print(separator)
        
            # Pagination
            fixed_ui_lines = 8
            available = term_height - fixed_ui_lines
            items_per_page = int(available * 0.9)
            items_per_page = max(1, items_per_page)
        
            total_items = len(parent_notebook.subnotebooks)
            total_pages = (total_items + items_per_page - 1) // items_per_page
        
            if page >= total_pages and total_pages > 0:
                page = total_pages - 1
        
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, total_items)
            paginated_items = parent_notebook.subnotebooks[start_idx:end_idx]
            current_page = page + 1
        
            # Title
            if total_items == 1:
                print(f"Sub-notebook: ({total_items} sub)")
            else:
                print(f"Sub-notebooks: ({total_items} subs)")
        
            # Display items
            if paginated_items:
                for i, sub_nb in enumerate(paginated_items, 1):
                    note_count = sub_nb.get_total_note_count()
                    sub_count = sub_nb.get_total_subnotebook_count()
                
                    parts = []
                    if note_count > 0:
                        parts.append(f"{note_count} note{'s' if note_count != 1 else ''}")
                    if sub_count > 0:
                        parts.append(f"{sub_count} sub{'s' if sub_count != 1 else ''}")
                
                    count_display = f" ({', '.join(parts)})" if parts else ""
                    print(f"[{i}] {sub_nb.name}{count_display}")
            else:
                print("No subnotebooks yet.")
                print()
        
            # Page indicator
            if total_pages > 1:
                page_text = f"Page {current_page} of {total_pages}"
                centered_text = page_text.center(term_width)
                text_start = (term_width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                line_chars = list(centered_text)
            
                if current_page > 1:
                    left_pos = text_start - 4 - 2
                    if left_pos >= 0:
                        line_chars[left_pos:left_pos+2] = list("<<")
            
                if current_page < total_pages:
                    right_pos = text_end + 4
                    if right_pos + 2 <= term_width:
                        line_chars[right_pos:right_pos+2] = list(">>")
            
                print()
                print("".join(line_chars))
                print()
            else:
                print()
        
            # Footer
            print("" * term_width)
            footer = ["[V]iew", "[B]ack"]
        
            if total_pages > 1:
                if current_page < total_pages:
                    footer.append("[N]ext")
                if current_page > 1:
                    footer.append("[P]rev")
        
            print("  ".join(footer))
            print()
        
            cmd = ui.get_input("> ").strip().lower()
        
            if cmd == "b":
                break
            elif cmd == "n" and current_page < total_pages:
                page += 1
            elif cmd == "p" and page > 0:
                page -= 1
            elif cmd.startswith("v"):
                if cmd == "v":
                    try:
                        idx = int(ui.get_input(f"Enter number [1-{len(paginated_items)}]: ")) - 1
                    except ValueError:
                        continue
                else:
                    try:
                        idx = int(cmd[1:]) - 1
                    except ValueError:
                        continue
            
                if 0 <= idx < len(paginated_items):
                    sub_nb = paginated_items[idx]
                    # Navigate into the selected subnotebook
                    sub_result = {
                        'temp_dir': temp_dir,
                        'parent_notebook': parent_notebook_obj,
                        '_crypto': crypto
                    }
                    self._display_notebook_direct(sub_nb, 0, temp_dir, parent_notebook_obj, crypto)
    
    def _display_notebook_direct(self, notebook, page, temp_dir, parent_notebook, crypto):
        """Display a subnotebook directly (recursive navigation)"""
        # Create result data and call _display_notebook
        result_data = {
            'temp_dir': temp_dir,
            'parent_notebook': parent_notebook,
            '_crypto': crypto,
            'is_subnotebook': True
        }
        # We need to set notebook as the current one
        # This is a bit tricky - for now, just call _display_notebook with modified result_data
        # But _display_notebook loads from temp_dir again, which is inefficient
        # For simplicity, we'll just create a new instance with the same temp_dir
        self._display_notebook(result_data, self.ui)
    
    # =========================================================================
    # TEMP MANAGER
    # =========================================================================
    
    def _create_temp_manager(self, temp_dir):
        """Create temporary manager for resurrected data"""
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
                        if isinstance(nb_data, dict) and ('subnotebooks' in nb_data or 'notes' in nb_data):
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
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _trigger_restore(self, result_data, ui):
        """Trigger restore operation - calls back to git_resurrection"""
        from git_resurrection import GitHistoryMiner
        miner = GitHistoryMiner(self.manager)
        success = miner._restore_item(result_data, ui)
    
        if success:
            # 🟢 Refresh search results from ANY source
            if hasattr(ui, 'refresh_search_if_needed'):
                ui.refresh_search_if_needed()
            return "navigate"
        return "continue"
    
    def _export_file(self, content, filename, ui):
        """Export a file"""
        ui.clear_screen()
        ui.print_header(f"Export: {filename}")
        
        export_dir = ui.get_input("Export directory: ")
        if not export_dir:
            return
        
        export_dir = os.path.expanduser(export_dir)
        export_path = os.path.join(export_dir, filename)
        
        try:
            os.makedirs(os.path.dirname(export_path), exist_ok=True)
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Exported to: {export_path}")
        except Exception as e:
            print(f"Export failed: {e}")
        
        ui.get_input("Press Enter to continue...")