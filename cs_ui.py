#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
import shutil
import os
import re
from datetime import datetime

class PaginationManager:
    """Reusable pagination for all list views"""
    
    @staticmethod
    def calculate(total_items, terminal_height, fixed_lines=7):
        """Calculate pagination parameters using 0.95 ratio for more items"""
        available = terminal_height - fixed_lines
        items_per_page = int(available * 0.95)  # ← Changed from 0.9 to 0.95
        items_per_page = max(1, items_per_page)
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1
        return items_per_page, total_pages
    
    @staticmethod
    def get_page_items(items, page, items_per_page):
        """Get items for current page"""
        start = page * items_per_page
        end = start + items_per_page
        return items[start:end]
    
    @staticmethod
    def show_indicator(current_page, total_pages, width):
        """Show page indicator with arrows"""
        if total_pages <= 1:
            return
        
        page_text = f"Page {current_page + 1} of {total_pages}"
        centered = page_text.center(width)
        text_start = (width - len(page_text)) // 2
        text_end = text_start + len(page_text)
        chars = list(centered)
        
        if current_page > 0:
            left = text_start - 6
            if left >= 0:
                chars[left:left+2] = list("<<")
        
        if current_page < total_pages - 1:
            right = text_end + 4
            if right + 2 <= width:
                chars[right:right+2] = list(">>")
        
        print()
        print(''.join(chars))
    
    # =============================================================================
    # PATH FORMATTER - Universal path formatting for all search UIs
    # =============================================================================

def format_path(notebook_hierarchy, terminal_width, title_length):
    """
    Format notebook path for display - universal formatter.
    
    Args:
        notebook_hierarchy: list of notebook objects from root to current
        terminal_width: current terminal width
        title_length: length of the item title being displayed
    
    Returns:
        formatted path string like "[root]", "[parent/child]", or "[.../gp/p]"
    """
    if not notebook_hierarchy:
        return "[root]"
    
    # Get clean names (remove lock icons)
    names = []
    for nb in notebook_hierarchy:
        if hasattr(nb, 'name'):
            clean = nb.name.replace('🔐 ', '').replace('🔒 ', '')
            names.append(clean)
        else:
            names.append(str(nb))
    
    # Case 1: Root level
    if len(names) == 1:
        return "[root]"
    
    # Case 2: Two levels
    if len(names) == 2:
        path = f"{names[0]}/{names[1]}"
    
    # Case 3: Three+ levels - always show last two with ellipsis
    else:
        path = f".../{names[-2]}/{names[-1]}"
    
    # Calculate available width for path
    # Reserve: [i] (4 chars) + title (variable) + spaces (2) = 6 + title_length
    available = terminal_width - (6 + title_length)
    
    # Truncate if needed
    if len(path) > available:
        if available > 10:  # Enough space for meaningful truncation
            path = path[:available-3] + "..."
        else:
            path = path[:available]  # Severe truncation
    
    return f"[{path}]"


class ResultFormatter:
    def __init__(self, manager, width):
        self.manager = manager
        self.width = width
    
    def _get_hierarchy(self, notebook_id):
        """Get notebook hierarchy for path formatting"""
        if not notebook_id:
            return None
        return self.manager.get_notebook_hierarchy(notebook_id)
    
    def _truncate(self, text, max_len):
        """Truncate text with ellipsis"""
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."
    
    def _format_path(self, hierarchy, current_context=None, is_global=False, max_length=30):
        """
        Format path with smart display based on context.
        """
        if not hierarchy:
            return "[root]"

        # Get clean names
        names = []
        notebook_ids = []
        for nb in hierarchy:
            if hasattr(nb, 'name'):
                clean = nb.name.replace('🔐 ', '').replace('🔒 ', '')
                names.append(clean)
                notebook_ids.append(nb.id)
            else:
                names.append(str(nb))
                notebook_ids.append(None)

        root_nb_id = notebook_ids[0] if notebook_ids else None
        root_name = names[0] if names else ""

        # 🟢 HOME SEARCH (no context) - show full path from root
        if current_context is None:
            if len(names) == 1:
                path_str = f"[{root_name}]"
            elif len(names) == 2:
                path_str = f"[{root_name}/{names[1]}]"
            else:
                # Show truncated full path
                last_two = f"{names[-2]}/{names[-1]}"
                if len(last_two) > max_length - len(root_name) - 7:
                    # Truncate the last part if needed
                    if len(names[-1]) > max_length - len(root_name) - 10:
                        truncated = names[-1][:max_length-len(root_name)-13] + "..."
                        path_str = f"[{root_name}/.../{names[-2]}/{truncated}]"
                    else:
                        path_str = f"[{root_name}/.../{last_two}]"
                else:
                    path_str = f"[{root_name}/.../{last_two}]"
            return path_str

        # 🟢 GLOBAL SEARCH (is_global=True) - same as home
        if is_global:
            if len(names) == 1:
                path_str = f"[{root_name}]"
            elif len(names) == 2:
                path_str = f"[{root_name}/{names[1]}]"
            else:
                last_two = f"{names[-2]}/{names[-1]}"
                if len(last_two) > max_length - len(root_name) - 7:
                    if len(names[-1]) > max_length - len(root_name) - 10:
                        truncated = names[-1][:max_length-len(root_name)-13] + "..."
                        path_str = f"[{root_name}/.../{names[-2]}/{truncated}]"
                    else:
                        path_str = f"[{root_name}/.../{last_two}]"
                else:
                    path_str = f"[{root_name}/.../{last_two}]"
            return path_str

        # 🟢 NOTEBOOK CONTEXT SEARCH - show relative to current notebook
        if root_nb_id == current_context:
            # Items from current notebook hierarchy
            if len(names) == 1:
                path_str = "[root]"
            elif len(names) == 2:
                path_str = f"[{names[1]}]"
            else:
                # Show at least last 2 segments
                last_two = f"{names[-2]}/{names[-1]}"
                if len(last_two) > max_length - 6:
                    if len(names[-1]) > max_length - 9:
                        truncated = names[-1][:max_length-12] + "..."
                        path_str = f"[.../{names[-2]}/{truncated}]"
                    else:
                        path_str = f"[.../{last_two}]"
                else:
                    path_str = f"[.../{last_two}]"
        else:
            # Items from other notebooks
            if len(names) == 1:
                path_str = f"[{root_name}]"
            elif len(names) == 2:
                path_str = f"[{root_name}/{names[1]}]"
            else:
                last_two = f"{names[-2]}/{names[-1]}"
                if len(last_two) > max_length - len(root_name) - 7:
                    if len(names[-1]) > max_length - len(root_name) - 10:
                        truncated = names[-1][:max_length-len(root_name)-13] + "..."
                        path_str = f"[{root_name}/.../{names[-2]}/{truncated}]"
                    else:
                        path_str = f"[{root_name}/.../{last_two}]"
                else:
                    path_str = f"[{root_name}/.../{last_two}]"

        return path_str
    
    def _build_line(self, title, path, idx=None):
        """
        Build a formatted line with title left-aligned and path right-aligned.
        Ensures the closing bracket stays at the edge.
        """
        import shutil
        
        # Get actual terminal width (recompute to be safe)
        try:
            current_width = shutil.get_terminal_size().columns
            self.width = current_width
        except:
            pass
        
        # Handle emoji display width (each emoji takes 2 columns)
        def get_display_width(s):
            """Calculate display width accounting for emojis (which take 2 columns)"""
            width = 0
            for ch in s:
                # Emoji range (rough check)
                if ord(ch) >= 0x1F000 and ord(ch) <= 0x1F9FF:
                    width += 2
                else:
                    width += 1
            return width
        
        # 🟢 FIX: Calculate actual width of index (e.g., "[1] " = 4, "[10] " = 5, "[100] " = 6)
        reserved = 0
        index_str = ""
        if idx is not None:
            index_str = f"[{idx}] "
            reserved = len(index_str)
        
        # Available width for content
        available = self.width - reserved
        
        # Extract path content (remove brackets)
        if path.startswith('[') and path.endswith(']'):
            path_content = path[1:-1]
        else:
            path_content = path
        
        # Calculate maximum title length (leave at least 25 chars for path)
        min_path_space = min(30, max(25, available // 4))
        max_title_len = available - min_path_space - 2
        
        # If title is too long, truncate it
        if len(title) > max_title_len - 3:  # Leave room for "..."
            title_display = title[:max_title_len - 6] + "..."
        else:
            title_display = title
        
        # Calculate actual title display width
        title_width = get_display_width(title_display)
        
        # Calculate remaining space for path
        remaining = available - title_width - 2  # -2 for space padding
        
        # Truncate path if needed
        if len(path_content) + 2 > remaining:
            # Leave room for "..."
            max_path_len = max(10, remaining - 5)
            if len(path_content) > max_path_len:
                # Truncate from the right side (keep beginning)
                truncated = path_content[:max_path_len - 3] + "..."
                path_display = f"[{truncated}]"
            else:
                path_display = f"[{path_content}]"
        else:
            path_display = f"[{path_content}]"
        
        # Calculate final padding
        final_title_width = get_display_width(title_display)
        final_path_width = get_display_width(path_display)
        padding = available - final_title_width - final_path_width - 1
        if padding < 1:
            padding = 1
        
        # Build the line
        if idx is not None:
            return f"{index_str}{title_display}{' ' * padding}{path_display}"
        else:
            return f"{title_display}{' ' * padding}{path_display}"
    
    def format(self, result, query_parsed):
        """Format a single result based on its type"""
        if not result:
            return "Invalid result"
        
        result_type = result.get('type', '')
        
        if result_type == 'current_note':
            return self._format_note(result)
        elif result_type == 'current_notebook':
            return self._format_notebook(result)
        elif result_type == 'resurrected_note' or result.get('is_erased') or result.get('is_renamed') or 'DELETED' in str(result.get('commit_message', '')):
            return self._format_historical(result)
        elif result_type == 'timeline_version':
            return self._format_timeline(result)
        elif result_type == 'activity':
            return self._format_activity(result)
        elif 'item_type' in result:
            if result['item_type'] in ['subnotebook', 'root_notebook']:
                return self._format_notebook(result)
        elif result.get('is_erased') or result.get('is_renamed'):
            return self._format_historical(result)
        elif result.get('title') and result.get('notebook_name'):
            return self._format_note(result)
        
        return f"Unknown: {result.get('title', result.get('name', ''))}"
    
    def _format_note(self, result, idx=None, show_action=True):
        """
        Format a note result.

        Args:
            result: The result dict
            idx: Optional index number
            show_action: If True, show action prefix (created/updated)
        """
        note, notebook = self.manager.find_note_by_id(result['notebook_id'], result['uuid'])
    
        # Fallback for historical items that can't be found in current structure
        if not note or not notebook:
            title = result.get('title', 'Unknown')
            stats = ""
            if 'commit_message' in result:
                from git_resurrection import parse_change_stats
                change_data = parse_change_stats(result['commit_message'])
                if change_data:
                    stats = f" {change_data['display']}"
            path = self._format_path(None, result.get('_current_context'), result.get('_is_global', False))
            return self._build_line(f"{title}{stats}", path, idx)
    
        # Get stats from commit message if available
        stats = ""
        if 'commit_message' in result:
            from git_resurrection import parse_change_stats
            change_data = parse_change_stats(result['commit_message'])
            if change_data:
                stats = f" {change_data['display']}"
    
        # Determine action prefix
        action_prefix = ""
        if show_action:
            if note.updated > note.created:
                action_prefix = "updated "
            else:
                action_prefix = "created "
    
        # Build display title
        display_title = f"{action_prefix}{note.title}{stats}"
    
        # Get path
        hierarchy = self._get_hierarchy(notebook.id)
        current_context = result.get('_current_context')
        is_global = result.get('_is_global', False)
        path = self._format_path(hierarchy, current_context, is_global)
    
        return self._build_line(display_title, path, idx)

    def _format_notebook(self, result, idx=None):
        """Format a regular notebook result WITH lock symbol"""
        title = result.get('title') or result.get('name', 'Unknown')
        notebook_id = result.get('notebook_id') or result.get('uuid')
        
        # Check lock status from master registry
        is_locked = True
        is_encrypted = False
        if notebook_id:
            # Get fresh lock state from master registry
            try:
                manager = self.manager
                fp_hash = manager._compute_fp_hash()
                registry = manager.load_registry(force_reload=True)
                notebook_data = registry.get("notebooks", {}).get(notebook_id, {})
                system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
                is_locked = system_entry.get("locked", True)
                is_encrypted = notebook_id in manager.encrypted_notebooks
            except:
                is_locked = True
                is_encrypted = False
        
        # Add lock symbol for encrypted notebooks
        if is_encrypted:
            if is_locked:
                display_title = f"🔒 {title}"
            else:
                display_title = f"🔐 {title}"
        else:
            display_title = title
        
        # Add counts
        note_count = result.get('note_count', 0)
        file_count = result.get('file_count', 0)
        sub_count = result.get('sub_count', 0)
        
        counts = []
        if note_count > 0:
            counts.append(f"{note_count}n")
        if file_count > 0:
            counts.append(f"{file_count}f")
        if sub_count > 0:
            counts.append(f"{sub_count}s")
        
        count_str = f" ({', '.join(counts)})" if counts else ""
        display_title = f"{display_title}{count_str}"
        
        # Get path
        hierarchy = self._get_hierarchy(notebook_id)
        path = self._format_path(hierarchy)
        
        return self._build_line(display_title, path, idx)
    
    def _format_historical(self, result, idx=None):
        """Format a deleted/renamed/restored result"""
        title = result.get('title', 'Unknown')
        commit_msg = str(result.get('commit_message', '')).upper()
        
        if result.get('is_erased') or 'ERASED' in commit_msg:
            action = "ERASED"
        elif result.get('is_renamed') or 'RENAMED' in commit_msg:
            action = "RENAMED"
        elif 'RESTORED' in commit_msg:
            action = "RESTORED"
        elif 'DELETED' in commit_msg:
            action = "DELETED"
        else:
            action = "DELETED"
        
        display_title = f"{action} {title}"
        
        # Get path
        hierarchy = None
        if result.get('notebook_path'):
            for nb in self.manager.notebooks:
                if hasattr(nb, 'custom_path') and nb.custom_path == result['notebook_path']:
                    hierarchy = self._get_hierarchy(nb.id)
                    break
        
        path = self._format_path(hierarchy)
        
        return self._build_line(display_title, path, idx)
    
    def _format_timeline(self, result, idx=None):
        """Format a timeline version"""
        from datetime import datetime
        date = result.get('date', datetime.now()).strftime("%Y-%m-%d %H:%M")
        msg = result.get('message', '')[:40]
        display_title = f"{date} {msg}"
        
        if idx is None:
            return display_title
        return self._build_line(display_title, "", idx)
    
    def _format_activity(self, result, idx=None):
        """Format an activity item WITH action prefix - for activity/timeline only"""
        subject = result.get('subject', result.get('title', ''))
        body = result.get('body', '')
    
        # Remove 'type: ' prefix for display
        if subject.startswith('type: '):
            subject = subject[6:]  # Remove 'type: '
    
        # Extract action from the cleaned subject
        action = "UNKNOWN"
        if subject.startswith('CREATED'):
            action = "created"
        elif subject.startswith('UPDATED') or subject.startswith('EDITED'):
            action = "updated"
        elif subject.startswith('DELETED'):
            action = "deleted"
        elif subject.startswith('RENAMED'):
            action = "renamed"
        elif subject.startswith('RESTORED'):
            action = "restored"
        elif subject.startswith('ERASED'):
            action = "erased"
    
        # Clean title (remove action words from the title itself)
        title = subject
        for word in ["CREATED", "UPDATED", "DELETED", "RENAMED", "RESTORED", "ERASED", "EDITED"]:
            if word in title:
                title = title.replace(word, "").strip()
                # Also remove the colon that follows
                if title.startswith(':'):
                    title = title[1:].strip()
                break
    
        for prefix in ["NOTE:", "FILE:", "SUBNOTEBOOK:", "NOTEBOOK:"]:
            if title.startswith(prefix):
                title = title.replace(prefix, "").strip()
                break
    
        # Add stats based on action type
        stats = ""
        from git_resurrection import parse_change_stats
        change_data = parse_change_stats(body)
        if change_data:
            stats = f" {change_data['display']}"
    
        if action == 'updated' or action == 'edited':
            # Look for edit stats (+123/-456)
            chars_match = re.search(r'Chars:.*?\(\+(\d+)/-(\d+)\)', body)
            if chars_match:
                added, removed = chars_match.groups()
                stats = f" (+{added}/-{removed})"
    
        elif action == 'created':
            # 🟢 Look for creation stats (+123)
            chars_match = re.search(r'Chars:\s*(\d+)\s*\(\+\)', body)
            if chars_match:
                chars = chars_match.group(1)
                stats = f" (+{chars})"
    
        # Determine item type from the original subject
        item_type = "note"
        if "FILE:" in subject:
            item_type = "file"
        elif "SUBNOTEBOOK:" in subject:
            item_type = "sub"
        elif "NOTEBOOK:" in subject:
            item_type = "notebook"
    
        # Build display WITH action prefix and stats
        display_title = f"{action} {item_type}: {title}{stats}"
    
        # Get path
        path = "[root]"
        if result.get('full_path'):
            path_parts = result['full_path'].replace(' → ', '/').split('/')
            if len(path_parts) == 1:
                path = "[root]"
            elif len(path_parts) == 2:
                path = f"[{path_parts[0]}/{path_parts[1]}]"
            else:
                path = f"[.../{path_parts[-2]}/{path_parts[-1]}]"
        elif result.get('item_notebook_name'):
            path = f"[{result['item_notebook_name']}]"
    
        return self._build_line(display_title, path, idx)

    def _format_notebook_with_action(self, result, idx=None):
        """Format a notebook result WITH action prefix"""
        action = "created"  # Notebooks are always "created"
        item_type = "sub" if result.get('is_subnotebook') else "notebook"
        title = result.get('title') or result.get('name', 'Unknown')
    
        # Get path
        notebook_id = result.get('notebook_id') or result.get('uuid')
        hierarchy = self._get_hierarchy(notebook_id)
        current_context = result.get('_current_context')
        is_global = result.get('_is_global', False)
        path = self._format_path(hierarchy, current_context, is_global)
    
        display_title = f"{action} {item_type}: {title}"
        return self._build_line(display_title, path, idx)
    
def show_search(results_data, ui, nav, title=None):
    """
    Display search results with full UI interaction.
    - With action wildcard (created*/deleted*): NO action prefix
    - Without action wildcard: SHOW action prefix
    """
    results = results_data['results']
    parsed = results_data['query_parsed']
    context = results_data['context']
    mode = results_data['mode']
    
    # Check if query had an action wildcard
    has_action_wildcard = parsed['actions'] is not None
    
    page = 0
    
    while True:
        ui.clear_screen()
        width, height = shutil.get_terminal_size()
        
        formatter = ResultFormatter(ui.manager, width)
        
        # Title
        if not title:
            if parsed['actions'] and not parsed['text']:
                action_display = '/'.join(parsed['actions']).lower().replace('*', '')
                display = f"{action_display}: ({len(results)} matches)"
            elif parsed['text']:
                filter_parts = []
                if parsed['actions']:
                    filter_parts.append('/'.join(parsed['actions']).lower().replace('*', ''))
                if parsed['type']:
                    filter_parts.append(parsed['type'])
                
                filter_text = ' '.join(filter_parts) if filter_parts else 'search'
                display = f"{filter_text}: '{parsed['text']}' ({len(results)} matches)"
            else:
                if parsed['type'] and not parsed['actions']:
                    display = f"{parsed['type']}: ({len(results)} matches)"
                else:
                    display = f"Search: ({len(results)} matches)"
        else:
            display = title
        
        ui.print_header(display)
        
        # Pagination
        items_per_page, total_pages = PaginationManager.calculate(
            len(results), height, fixed_lines=8
        )
        
        if page >= total_pages:
            page = max(0, total_pages - 1)
        
        page_items = PaginationManager.get_page_items(results, page, items_per_page)
        
        # Display results
        if not page_items:
            print("No matches found.")
        else:
            for i, result in enumerate(page_items, 1):                
                if result['type'] == 'current_note':
                    line = formatter._format_note(result, i, show_action=not has_action_wildcard)
        
                elif result['type'] == 'current_notebook':
                    line = formatter._format_notebook(result, i)  # Just format, don't navigate!
        
                elif result['type'] == 'resurrected_note' or result.get('is_erased') or result.get('is_renamed') or result.get('is_deleted'):
                    if has_action_wildcard:
                        line = _format_historical_no_action(result, formatter, i)
                    else:
                        line = _format_historical_with_action(result, formatter, i)
    
                elif result['type'] == 'timeline_version':
                    line = formatter._format_timeline(result, i)
                else:
                    line = formatter.format(result, parsed)
                    line = f"[{i}] {line}"
    
                print(line)
        
        # Page indicator
        PaginationManager.show_indicator(page, total_pages, width)
        
        # Footer
        footer = ["[S]earch"]
        if page_items:
            footer.append("[V]iew")
        footer.append("[B]ack")
        
        if page < total_pages - 1:
            footer.append("[N]ext")
        if page > 0:
            footer.append("[P]rev")
        footer.append("[Q]uit")
        
        ui.print_footer("  ".join(footer))
        
        # Command handling
        cmd = ui.get_input("> ").lower()
        
        if cmd == "b":
            return "exit_search"
        elif cmd == "q":
            confirm = ui.get_input("Quit? [y/N]: ")
            if confirm.lower() == "y":
                ui.clear_screen()
                return "exit"
        elif cmd == "qy":
            ui.clear_screen()
            return "exit"
        elif cmd == "n" and page < total_pages - 1:
            page += 1
        elif cmd == "p" and page > 0:
            page -= 1
        elif cmd.startswith("s"):
            if cmd == "s":
                new_query = ui.get_input("Search query: ")
            else:
                new_query = cmd[1:].strip()
            
            if new_query:
                from comprehensive_search import ComprehensiveSearch
                cs = ComprehensiveSearch(ui.manager, ui)
                
                words = new_query.split()
                has_global = any(word in ['g*', 'global*'] for word in words)
                new_context = None if has_global else context
                
                new_results = cs.process(new_query, context=new_context, mode=mode)
                results = new_results['results']
                parsed = new_results['query_parsed']
                # 🟢 Update for new search
                has_action_wildcard = parsed['actions'] is not None
                page = 0
                continue
        
        elif cmd.startswith("v") and page_items:
            if cmd == "v":
                try:
                    idx = int(ui.get_input("Enter number: ")) - 1
                except ValueError:
                    continue
            else:
                try:
                    idx = int(cmd[1:]) - 1
                except ValueError:
                    continue

            if 0 <= idx < len(page_items):
                item = page_items[idx]
                view_result = None
        
                if item['type'] == 'timeline_version':
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(ui.manager, ui)
                    cs._show_timeline_version_screen(item['timeline_data'])
                elif item['type'] == 'activity':
                    pass
                elif item['type'] == 'current_note':
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(ui.manager, ui)
                    view_result = cs._show_search_note_with_timeline(item['uuid'], 0)
                elif item['type'] == 'current_notebook':
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(ui.manager, ui)
                    result = cs._show_search_notebook_view(item['uuid'], 0)
                    # After returning from notebook view, refresh search results
                    if hasattr(ui, '_last_search_query') and ui._last_search_query:
                        from comprehensive_search import ComprehensiveSearch
                        cs = ComprehensiveSearch(ui.manager, ui)
                        context = results_data.get('context')
                        new_results = cs.process(ui._last_search_query, context=context)
                        results = new_results['results']
                        parsed = new_results['query_parsed']
                        page = 0
                        continue
                elif item['type'] == 'resurrected_note':
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(ui.manager, ui)
                    view_result = cs._handle_result_view(item)
        
                # 🟢 Refresh search results after restore or rename
                if view_result == "navigate" or view_result == "refresh":
                    if hasattr(ui, '_last_search_query') and ui._last_search_query:
                        from comprehensive_search import ComprehensiveSearch
                        cs = ComprehensiveSearch(ui.manager, ui)
                        context = results_data.get('context')
                        new_results = cs.process(ui._last_search_query, context=context)
                        results = new_results['results']
                        parsed = new_results['query_parsed']
                        page = 0
                        continue
                elif item['type'] == 'current_notebook':
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(ui.manager, ui)
                    view_result = cs._show_search_notebook_view(item['uuid'], 0)
                elif item['type'] == 'resurrected_note':
                    from comprehensive_search import ComprehensiveSearch
                    cs = ComprehensiveSearch(ui.manager, ui)
                    view_result = cs._handle_result_view(item)
                
                
        
                # 🟢 CRITICAL: Refresh search results after restore
                # 🟢 CRITICAL: Refresh search results after restore
                # 🟢 CRITICAL: Refresh search results after restore OR rename
                # 🟢 THIS GOES AFTER all the item type handling, NOT inside!
                
    
                if view_result == "navigate" or view_result == "refresh":
                    if hasattr(ui, '_last_search_query') and ui._last_search_query:
                        from comprehensive_search import ComprehensiveSearch
                        cs = ComprehensiveSearch(ui.manager, ui)
                        context = results_data.get('context')
                        new_results = cs.process(ui._last_search_query, context=context)
                        results = new_results['results']
                        parsed = new_results['query_parsed']
                        page = 0
                        continue
                
def _format_historical_with_action(result, formatter, idx=None):
    """Format historical items WITH action prefix"""
    title = result.get('title', 'Unknown')
    
    # Determine action
    if result.get('is_renamed'):
        action = "renamed"
    elif result.get('is_erased'):
        action = "erased"
    elif result.get('is_restored'):
        action = "restored"
    else:
        action = "deleted"
    
    # Get path from parent_id
    path = "[root]"
    parent_id = result.get('parent_id')
    if parent_id:
        parent_notebook = formatter.manager.find_notebook_by_id(parent_id)
        if parent_notebook:
            hierarchy = formatter.manager.get_notebook_hierarchy(parent_notebook.id)
            if hierarchy:
                path = formatter._format_path(hierarchy, None, False)
    elif result.get('notebook_path'):
        folder = os.path.basename(result['notebook_path'])
        if '-' in folder:
            path = f"[{folder.split('-')[0]}]"
        else:
            path = f"[{folder}]"
    
    display_title = f"{action}: {title}"
    if result.get('is_renamed') and result.get('old_name') and result.get('new_name'):
        display_title = f"{action}: {result['old_name']} → {result['new_name']}"
    
    return formatter._build_line(display_title, path, idx)

def _format_historical_no_action(result, formatter, idx=None):
    """Format historical items NO action prefix - for searches WITH action wildcard"""
    title = result.get('title', 'Unknown')
    
    # Get path from parent_id
    path = "[root]"
    parent_id = result.get('parent_id')
    if parent_id:
        parent_notebook = formatter.manager.find_notebook_by_id(parent_id)
        if parent_notebook:
            hierarchy = formatter.manager.get_notebook_hierarchy(parent_notebook.id)
            if hierarchy:
                path = formatter._format_path(hierarchy, None, False)
    elif result.get('notebook_path'):
        folder = os.path.basename(result['notebook_path'])
        if '-' in folder:
            path = f"[{folder.split('-')[0]}]"
        else:
            path = f"[{folder}]"
    
    if result.get('is_renamed'):
        old_name = result.get('old_name', '')
        new_name = result.get('new_name', '')
        if old_name and new_name:
            display_title = f"{old_name} → {new_name}"
        else:
            display_title = title
    else:
        display_title = title
    
    return formatter._build_line(display_title, path, idx)

        
def show_timeline(results_data, ui, cs_instance=None):
    """
    Display timeline versions for a note with proper action formatting.
    """
    results = results_data['results']
    page = 0
    
    while True:
        ui.clear_screen()
        width, height = shutil.get_terminal_size()
        
        ui.print_header(f"Timeline: {len(results)} versions")
        
        # Pagination
        items_per_page, total_pages = PaginationManager.calculate(
            len(results), height, fixed_lines=8
        )
        
        if page >= total_pages:
            page = max(0, total_pages - 1)
        
        page_items = PaginationManager.get_page_items(results, page, items_per_page)
        
        # Display versions
        if not page_items:
            print("No timeline versions found.")
        else:
            for i, version in enumerate(page_items, 1):
                from datetime import datetime
                
                # Get date
                date = version.get('date', datetime.now())
                if isinstance(date, str):
                    try:
                        date = datetime.fromisoformat(date)
                    except:
                        date = datetime.now()
                
                date_str = date.strftime("%Y-%m-%d %H:%M")
                
                # Get commit message
                msg = version.get('message', '') or version.get('commit_message', '')
                first_line = msg.split('\n')[0] if msg else ""
                
                # Remove 'type: ' prefix for display
                if first_line.startswith('type: '):
                    first_line = first_line[6:]
                
                # Parse change stats
                from git_resurrection import parse_change_stats
                change_data = parse_change_stats(msg)
                stats_display = f" {change_data['display']}" if change_data else ""
                
                # Determine action
                if "CREATED" in first_line:
                    display_text = f"[{i}] {date_str} [CREATED]{stats_display}"
                elif "UPDATED" in first_line or "EDITED" in first_line:
                    display_text = f"[{i}] {date_str} [UPDATED]{stats_display}"
                elif "DELETED" in first_line:
                    display_text = f"[{i}] {date_str} [DELETED]"
                elif "RENAMED" in first_line:
                    rename_match = re.search(r'RENAMED\s+\w+:\s*([^→]+)→\s*([^|]+)', first_line)
                    if rename_match:
                        old_name, new_name = rename_match.groups()
                        display_text = f"[{i}] {date_str} [RENAMED] {old_name} → {new_name}"
                    else:
                        display_text = f"[{i}] {date_str} [RENAMED]"
                elif "RESTORED" in first_line:
                    display_text = f"[{i}] {date_str} [RESTORED]"
                elif "ERASED" in first_line:
                    display_text = f"[{i}] {date_str} [ERASED]"
                else:
                    short_msg = first_line[:40] if first_line else ""
                    display_text = f"[{i}] {date_str} {short_msg}"
                
                # Truncate if needed
                if len(display_text) > width - 4:
                    display_text = display_text[:width-7] + "..."
                
                print(display_text)
        
        # Page indicator and footer...
        
        # Page indicator
        PaginationManager.show_indicator(page, total_pages, width)
        
        # Footer
        footer = ["[V]iew"]
        if page < total_pages - 1:
            footer.append("[N]ext")
        if page > 0:
            footer.append("[P]rev")
        footer.append("[B]ack")
        
        ui.print_footer("  ".join(footer))
        
        # Command handling
        cmd = ui.get_input("> ").lower()
        
        if cmd == "b":
            return
        elif cmd == "n" and page < total_pages - 1:
            page += 1
        elif cmd == "p" and page > 0:
            page -= 1
        elif cmd.startswith("v") and page_items:
            if cmd == "v":
                try:
                    idx = int(ui.get_input("Enter number: ")) - 1
                except ValueError:
                    continue
            else:
                try:
                    idx = int(cmd[1:]) - 1
                except ValueError:
                    continue
            
            if 0 <= idx < len(page_items):
                version = page_items[idx]
                if cs_instance:
                    cs_instance._show_timeline_version_screen(version)

def show_resurrected_note(result_data, ui, manager):
    """Display a resurrected note using the same UI as comprehensive_search"""
    from comprehensive_search import ComprehensiveSearch
    cs = ComprehensiveSearch(manager, ui)
    cs._show_resurrected_note_screen(result_data)
    
