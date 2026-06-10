#!/usr/bin/env python3
import sys
sys.dont_write_bytecode = True
import sys
import os

# Force add the source directory to path
source_dir = '/app/source'
if os.path.exists(source_dir):
    sys.path.insert(0, source_dir)
else:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subprocess
import tempfile
import shutil
import traceback
import json
import signal
import threading  # 🆕 ADD THIS IMPORT

# Disable Ctrl+Z (SIGTSTP)
signal.signal(signal.SIGTSTP, signal.SIG_IGN)

from datetime import datetime
from terminal_notes_core import Note, Notebook, NoteManager, SimpleNav
from notebook_manager import NotebookManager
from notebook_operations import NotebookOperations
from search_system import SimpleSearch
from comprehensive_search import ComprehensiveSearch  # 🆕 ADD THIS IMPORT
from notebook_importer import NotebookImporter  # 🆕 ADD THIS
from recovery_system import RecoverySystem
from activity_view import ActivityView
from eraser import Eraser
from editor_config import EditorConfig
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import sys
import os

class TerminalNotes:
    def __init__(self):
        # Get correct app directory for PyInstaller
        if getattr(sys, 'frozen', False):
            self.app_dir = os.path.dirname(sys.executable)
            self.assets_dir = os.path.join(os.path.dirname(__file__), 'assets')
        else:
            self.app_dir = os.path.dirname(os.path.abspath(__file__))
            self.assets_dir = os.path.join(self.app_dir, 'assets')

        self.config_dir = os.path.join(self.app_dir, 'config')

        # Add assets to Python path for crypto imports
        if os.path.exists(self.assets_dir):
            sys.path.insert(0, self.assets_dir)

        self.manager = NoteManager()
        self.nav = SimpleNav()
        self.nav.push("home")
        self.importer = NotebookImporter(self.manager, self)
        self.activity_view = None

        from notebook_operations import NotebookOperations
        self.ops = NotebookOperations(self.manager)

        try:
            columns, _ = shutil.get_terminal_size()
            self.terminal_width = max(60, columns)
        except:
            self.terminal_width = 80
        self.terminal_height = 24

        self.search_manager = SimpleSearch(self.manager, self)
        self.load_editor_config()

        self.allowed_extensions = {
            "html", "js", "css", "ts", "scss", "vue", "jsx", "svelte", "astro", "mdx", "graphql",
            "py", "php", "rb", "java", "c", "cpp", "go", "rs", "pl", "lua", "r", "jl",
            "swift", "kt", "sh", "yml", "yaml", "toml", "ini", "cfg", "hcl", "tf", "justfile", "nix",
            "json", "xml", "sql", "proto", "bib", "tex", "md", "txt", "sty", "cls", "org", "adoc", "rst", "typ",
            "bashrc", "zshrc", "profile", "aliases", "bash_profile", "zprofile",
            "vimrc", "lua", "editorconfig", "gitconfig", "gitignore", "gitattributes",
            "npmrc", "yarnrc", "gemrc", "Rprofile", "irbrc",
            "tmux.conf", "inputrc", "Xresources", "ssh/config",
            "Dockerfile", "Jenkinsfile", "service", "timer"
        }
        self.search_results = []
        self.search_query = ""
        self.export_history = []
        self.export_history_limit = 3
        self.comprehensive_search = ComprehensiveSearch(self.manager, self)
        self.recovery_system = RecoverySystem(self.manager, self.app_dir)
        self.nvim_autosave_commands = [
            "set autowriteall",
            "set updatetime=30000",
            "autocmd CursorHold * silent! write",
            "autocmd CursorHoldI * silent! write",
            "autocmd FocusLost * silent! write",
            "echo 'NeoVim autosave enabled - saving every 30 seconds'"
        ]
        self.activity_view = None
        # In __init__ of TerminalNotes
        self.notebook_manager = NotebookManager(manager=self.manager, ui=self, nav=self.nav, app_dir=self.app_dir)
        self.jump_histories = {}  # notebook_id -> list of stacks
    
    def load_editor_config(self):
        """Load or create editor config - always use app_dir"""
        config_path = os.path.join(self.app_dir, "config.json")
        config = EditorConfig.load_config(config_path)
    
        self.edit_editor = config["edit"]
        self.view_editor = config["view"]
    
        if not os.path.exists(config_path):
            default_config = {
                "edit": self.edit_editor,
                "view": self.view_editor,
            }
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)

    def get_terminal_width(self):
            try:
                columns, _ = shutil.get_terminal_size()
                return max(60, columns)
            except:
                return 80

    def get_smart_header_path(self, notebook_id):
        hierarchy = self.manager.get_notebook_hierarchy(notebook_id)
        if not hierarchy:
            return "Home"

        # 🟢 Remove lock icons from all names in the path
        full_path = [nb.name.replace('🔐 ', '') for nb in hierarchy]
    
        available_width = self.terminal_width - 4

        # Try full numbered path first
        numbered_full_path = ""
        for idx, segment in enumerate(full_path, 1):
            numbered_full_path += f"[{idx}]{segment}/"

        if len(numbered_full_path) <= available_width:
            return numbered_full_path

        # Smart truncation with RELATIVE numbering
        current_index = len(full_path) - 1
        left_index = current_index
        right_index = current_index

        while True:
            display_parts = []
            if left_index > 0:
                display_parts.append("...")

            segment_number = 1
            for i in range(left_index, right_index + 1):
                display_parts.append(f"[{segment_number}]{full_path[i]}")
                segment_number += 1

            if right_index < len(full_path) - 1:
                display_parts.append("...")

            display_string = "/".join(display_parts) + "/"

            if len(display_string) <= available_width:
                if left_index > 0:
                    new_left = left_index - 1
                    new_parts = ["..."] if new_left > 0 else []
                    new_segment_number = 1
                    for i in range(new_left, right_index + 1):
                        new_parts.append(f"[{new_segment_number}]{full_path[i]}")
                        new_segment_number += 1
                    if right_index < len(full_path) - 1:
                        new_parts.append("...")
                    new_string = "/".join(new_parts) + "/"
                    if len(new_string) <= available_width:
                        left_index = new_left
                        continue

                if right_index < len(full_path) - 1:
                    new_right = right_index + 1
                    new_parts = ["..."] if left_index > 0 else []
                    new_segment_number = 1
                    for i in range(left_index, new_right + 1):
                        new_parts.append(f"[{new_segment_number}]{full_path[i]}")
                        new_segment_number += 1
                    if new_right < len(full_path) - 1:
                        new_parts.append("...")
                    new_string = "/".join(new_parts) + "/"
                    if len(new_string) <= available_width:
                        right_index = new_right
                        continue
                break
            else:
                if left_index < current_index:
                    left_index += 1
                elif right_index > current_index:
                    right_index -= 1
                else:
                    break

        display_parts = []
        if left_index > 0:
            display_parts.append("...")

        segment_number = 1
        for i in range(left_index, right_index + 1):
            display_parts.append(f"[{segment_number}]{full_path[i]}")
            segment_number += 1

        if right_index < len(full_path) - 1:
            display_parts.append("...")

        final_path = "/".join(display_parts) + "/"
        return final_path

    def get_numbered_path_info(self, notebook_id):
        hierarchy = self.manager.get_notebook_hierarchy(notebook_id)
        if not hierarchy:
            return {}

        full_path = [nb for nb in hierarchy]
        available_width = self.terminal_width - 4

        current_index = len(full_path) - 1
        left_index = current_index
        right_index = current_index

        while True:
            display_parts = []
            if left_index > 0:
                display_parts.append("...")

            segment_number = 1
            for i in range(left_index, right_index + 1):
                display_parts.append(f"[{segment_number}]{full_path[i].name}")
                segment_number += 1

            if right_index < len(full_path) - 1:
                display_parts.append("...")

            display_string = "/".join(display_parts) + "/"

            if len(display_string) <= available_width:
                if left_index > 0:
                    new_left = left_index - 1
                    new_parts = ["..."] if new_left > 0 else []
                    new_segment_number = 1
                    for i in range(new_left, right_index + 1):
                        new_parts.append(f"[{new_segment_number}]{full_path[i].name}")
                        new_segment_number += 1
                    if right_index < len(full_path) - 1:
                        new_parts.append("...")
                    new_string = "/".join(new_parts) + "/"
                    if len(new_string) <= available_width:
                        left_index = new_left
                        continue

                if right_index < len(full_path) - 1:
                    new_right = right_index + 1
                    new_parts = ["..."] if left_index > 0 else []
                    new_segment_number = 1
                    for i in range(left_index, new_right + 1):
                        new_parts.append(f"[{new_segment_number}]{full_path[i].name}")
                        new_segment_number += 1
                    if new_right < len(full_path) - 1:
                        new_parts.append("...")
                    new_string = "/".join(new_parts) + "/"
                    if len(new_string) <= available_width:
                        right_index = new_right
                        continue
                break
            else:
                if left_index < current_index:
                    left_index += 1
                elif right_index > current_index:
                    right_index -= 1
                else:
                    break

        number_map = {}
        display_number = 1
        for i in range(left_index, right_index + 1):
            number_map[display_number] = full_path[i]
            display_number += 1

        return number_map

    def update_terminal_size(self):
        try:
            columns, rows = shutil.get_terminal_size()
            self.terminal_width = max(60, columns)
            self.terminal_height = rows  # ← ADD THIS LINE
            return columns, rows  # ← ADD THIS LINE
        except:
            self.terminal_width = 80
            self.terminal_height = 24
            return 80, 24

    def clear_screen(self):
        os.system("clear")

    def print_header(self, title):
        self.update_terminal_size()
        separator = "" * self.terminal_width
        print(separator)
        print(f"{title:^{self.terminal_width}}")
        print(separator)

    def print_footer(self, options):
        print("" * self.terminal_width)
        print(options)
        print()

    def wrap_text(self, text, width=None):
        if width is None:
            width = self.terminal_width - 4

        lines = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                lines.append("")
                continue
            words = paragraph.split()
            current_line = []
            current_length = 0

            for word in words:
                if current_length + len(word) + len(current_line) <= width:
                    current_line.append(word)
                    current_length += len(word)
                else:
                    if current_line:
                        lines.append(" ".join(current_line))
                    current_line = [word]
                    current_length = len(word)

            if current_line:
                lines.append(" ".join(current_line))

        return lines
    
    def get_input(self, prompt, preserve_case=False):
        """Get input - optionally preserve case"""
        import readline
        readline.set_completer_delims(' \t\n;')
        readline.parse_and_bind('set completion-ignore-case off')
        try:
            result = input(prompt).strip()
            return result if preserve_case else result.lower()
        except (EOFError, KeyboardInterrupt):
            return ""
        
    def get_raw_input(self, prompt):
        """Get input WITHOUT stripping or lowercasing"""
        import sys
        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            return sys.stdin.readline().strip()  # Only strip newline, keep case/spaces
        except (EOFError, KeyboardInterrupt):
            return ""
    
    def get_path_input(self, prompt):
        """Get path input without readline interference"""
        import sys
        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            return sys.stdin.readline().strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def get_dynamic_page_size(self):
        try:
            _, terminal_height = shutil.get_terminal_size()
            available_lines = terminal_height - 10
            return max(5, min(20, available_lines))
        except:
            return 20

    def get_paginated_items(self, items, page=0):
        items_per_page = self.get_dynamic_page_size()
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        total_pages = (len(items) + items_per_page - 1) // items_per_page

        paginated_items = items[start_idx:end_idx]
        return paginated_items, total_pages, page + 1, items_per_page

    def get_paginated_content(self, content, page=0, lines_per_page=None):
        """Get paginated content with optional custom page size"""
        wrapped_lines = self.wrap_text(content)
    
        # 🆕 USE PROVIDED PAGE SIZE OR DEFAULT
        if lines_per_page is None:
            lines_per_page = self.get_dynamic_page_size()
    
        start_idx = page * lines_per_page
        end_idx = start_idx + lines_per_page
        total_pages = (len(wrapped_lines) + lines_per_page - 1) // lines_per_page

        paginated_lines = wrapped_lines[start_idx:end_idx]
        return paginated_lines, total_pages, page + 1, lines_per_page

    def internal_editor(self, initial_content=""):
        self.clear_screen()    
        print("Enter your note. Press Ctrl+D on empty line when finished:")
        print("" * (self.terminal_width // 2))
        if initial_content:
            print("Current content (append below):")
            wrapped_content = self.wrap_text(initial_content, self.terminal_width - 4)
            for line in wrapped_content:
                print(f"  {line}")
            print("" * (self.terminal_width // 2))
        print(end="")

        lines = []
        try:
            while True:
                line = input()
                lines.append(line)
        except EOFError:
            pass

        if initial_content and lines:
            return initial_content + "\n" + "\n".join(lines)
        elif initial_content:
            return initial_content
        else:
            return "\n".join(lines)

    def external_editor(self, initial_content="", read_only=False, file_extension=None):
        suffix = f".{file_extension}" if file_extension else ".txt"

        with tempfile.NamedTemporaryFile(mode="w+", suffix=suffix, delete=False, encoding="utf-8") as f:
            if initial_content:
                f.write(initial_content)
            f.flush()
            temp_path = f.name

        try:
            editor_cmd = self.view_editor if read_only else self.edit_editor
            config_path = os.path.join(self.app_dir, "config.json")
            cmd = EditorConfig.get_launch_command(editor_cmd, temp_path, read_only, config_path)
            subprocess.run(cmd, shell=True)

            with open(temp_path, "r", encoding="utf-8") as f:
                return f.read()
        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    # UPDATED: Better jump detection
    def should_show_jump(self):
        current = self.nav.current()
        if not current or not current["id"]:
            return False

        notebook_id = current["id"]
        number_map = self.get_numbered_path_info(notebook_id)

        if len(number_map) > 1:
            return True

        root_id = self._get_root_notebook_id(notebook_id)
        if root_id in self.jump_histories and len(self.jump_histories[root_id]) >= 1:
            return True

        return False

    def process_command(self, command):
        cmd = command.lower().strip()
        if cmd == "":  # Empty input
            return "continue"  # Just redraw current screen
        # 🟢 UNIVERSAL SEARCH - CHECK FIRST, WORKS EVERYWHERE
        if cmd.startswith("s"):
            return self.handle_search(cmd)
        current = self.nav.current()

        if not current:
            return "exit"

        # Handle BACK command - SIMPLE ONE-STACK VERSION
        if cmd == "b":
            current = self.nav.current()
        
            # 🆕 DISABLE BACK ON HOME SCREEN
            if current and current["screen"] == "home":
                # Silent ignore - user must use [Q]uit
                return "continue"
        
            # Regular back for other screens
            if len(self.nav.stack) > 1:
                self.nav.pop()
                return "navigate"
            else:
                return "exit"

        # 🟢 MOVE LOCK BUTTON HANDLING HERE - BEFORE JUMP COMMANDS
        if cmd.startswith('l') and current and current["screen"] == "home":
            return self.process_home_command(cmd)

        # ========== FIX: Notebook-specific jump history helper ==========
        # Helper function to check jump history
        def has_jump_history():
            return (
                hasattr(self.nav, "jump_history")
                and self.nav.jump_history is not None
                and len(self.nav.jump_history) > 0
            )

        # ========== END FIX ==========

        # Handle JUMP BACK command (jb)
        # Handle JUMP BACK command (jb)
        if cmd == "jb":
            if self.jump_back():
                return "navigate"
            else:
                print("No previous jump location to return to")
                self.get_input("Press Enter to continue...")
                return "continue"

        # Handle JUMP command (J1, J2, J3, etc.)
        if len(cmd) > 1 and cmd[0] == "j":
            try:
                jump_number = int(cmd[1:])
                return self.process_jump_command(jump_number)
            except ValueError:
                print("Invalid jump format. Use: J1, J2, J3, or JB")
                self.get_input("Press Enter to continue...")
                return "continue"

        # UPDATED: Handle single letter JUMP command with context-aware prompts
        if cmd == "j":
            # Check if we're in root notebook with ONLY jump-back available
            current = self.nav.current()
            
            # ========== FIX: Use notebook-specific history check ==========
            current_notebook_id = None
            if current and current.get("id"):
                current_notebook_id = self._get_root_notebook_id(current["id"])
            
            is_root_with_only_jumpback = (
                current
                and current["screen"] == "notebook"
                and current_notebook_id
                and len(self.get_numbered_path_info(current["id"])) <= 1
                and len(self.jump_histories.get(current_notebook_id, [])) > 0
            )

            # Proper jump history check (notebook-specific)
            has_jump_history = (
                current_notebook_id
                and len(self.jump_histories.get(current_notebook_id, [])) > 0
            )
            # ========== END FIX ==========

            if is_root_with_only_jumpback:
                print("Jump back to previous location:")
                prompt_text = "Enter 'b': "
            elif has_jump_history:
                # STATIC + DYNAMIC prompt
                print("Jump to position j1, j2, j3, etc or 'b' to jump back:")
                prompt_text = "Enter number or 'b': "
            else:
                # STATIC prompt only
                print("Jump to position j1, j2, j3, etc:")
                prompt_text = "Enter number: "

            choice = self.get_input(prompt_text).lower().strip()

            # Process the choice
            if choice == "b":
                if has_jump_history:
                    if self.jump_back():
                        return "navigate"
                    else:
                        print("No previous jump location to return to")
                        self.get_input("Press Enter to continue...")
                        return "continue"
                else:
                    print("No jump back history available")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            elif choice.startswith("j") and len(choice) > 1:
                try:
                    jump_number = int(choice[1:])
                    return self.process_jump_command(jump_number)
                except ValueError:
                    # DYNAMIC error message
                    if has_jump_history:
                        print("Invalid command. Use: number, j1, j2, j3, or b")
                    else:
                        print("Invalid command. Use: number, j1, j2, j3")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            elif choice.isdigit():
                try:
                    jump_number = int(choice)
                    return self.process_jump_command(jump_number)
                except ValueError:
                    # DYNAMIC error message
                    if has_jump_history:
                        print("Invalid command. Use: number, j1, j2, j3, or b")
                    else:
                        print("Invalid command. Use: number, j1, j2, j3")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                # DYNAMIC error message
                if has_jump_history:
                    print("Invalid command. Use: number, j1, j2, j3, or b")
                else:
                    print("Invalid command. Use: number, j1, j2, j3")
                self.get_input("Press Enter to continue...")
                return "continue"

        # Route to appropriate command processor based on current screen
        current_screen = current["screen"]
        if current_screen == "home":
            return self.process_home_command(cmd)
        elif current_screen == "list":
            return self.process_notebook_list_command(cmd)
        elif current_screen == "notebook":
            return self.process_notebook_view_command(cmd)
        elif current_screen == "subnotebooks":
            return self.process_subnotebooks_view_command(cmd)
        elif current_screen == "note":
            return self.process_note_view_command(cmd)

        return "continue"

    def process_jump_command(self, jump_number):
        """Process jump by finding existing position OR building correct path"""
        # Save current position BEFORE jumping
        self.save_jump_position()

        current = self.nav.current()
        if not current or current["screen"] not in ["notebook", "subnotebooks"]:
            print("Jump only available in notebook views")
            self.get_input("Press Enter to continue...")
            return "continue"

        notebook_id = current["id"]
        if not notebook_id:
            print("Jump only available in notebook views")
            self.get_input("Press Enter to continue...")
            return "continue"

        number_map = self.get_numbered_path_info(notebook_id)

        if not number_map:
            print("No jump targets available")
            self.get_input("Press Enter to continue...")
            return "continue"

        if jump_number not in number_map:
            valid_numbers = list(number_map.keys())
            print(f"Invalid jump number. Available: {valid_numbers}")
            self.get_input("Press Enter to continue...")
            return "continue"

        target_notebook = number_map[jump_number]

        # CHECK IF TARGET NOTEBOOK IS ALREADY IN OUR NAVIGATION STACK
        target_position = None
        for i, nav_item in enumerate(self.nav.stack):
            if (
                nav_item["id"] == target_notebook.id
                and nav_item["screen"] == "notebook"
            ):
                target_position = i
                break

        if target_position is not None:
            # TARGET EXISTS IN STACK - JUST TRUNCATE TO THAT POSITION
            self.nav.stack = self.nav.stack[: target_position + 1]
            self.nav.replace_page(0)  # Reset to first page
        else:
            # TARGET NOT IN STACK - BUILD CORRECT PATH
            hierarchy = self.manager.get_notebook_hierarchy(target_notebook.id)

            if not hierarchy:
                print("Error: Could not determine notebook path")
                self.get_input("Press Enter to continue...")
                return "continue"

            # CLEAR the current navigation stack
            self.nav.clear()

            # REBUILD the navigation stack with the ACTUAL TREE PATH
            # Start with home
            self.nav.push("home")

            # Add notebook list
            self.nav.push("list", None, 0)

            # Add each notebook in the hierarchy (except the last one which is the target)
            for notebook in hierarchy[:-1]:
                self.nav.push("notebook", notebook.id, 0)

            # Finally add the target notebook
            self.nav.push("notebook", target_notebook.id, 0)

        return "navigate"
    
    def save_jump_position(self):
        current = self.nav.current()
        if not current or not current["id"]:
            return
        root_id = self._get_root_notebook_id(current["id"])
        if not root_id:
            return
        if root_id not in self.jump_histories:
            self.jump_histories[root_id] = []
        stack_copy = self.nav.stack.copy()
        if self.jump_histories[root_id] and self.jump_histories[root_id][-1] == stack_copy:
            return
        self.jump_histories[root_id].append(stack_copy)
        if len(self.jump_histories[root_id]) > 20:
            self.jump_histories[root_id].pop(0)


    def jump_back(self):
        current = self.nav.current()
        if not current or not current["id"]:
            return None
        root_id = self._get_root_notebook_id(current["id"])
        if not root_id or root_id not in self.jump_histories:
            return None
        if len(self.jump_histories[root_id]) == 0:
            return None
        previous = self.jump_histories[root_id][-1]
        self.jump_histories[root_id] = []
        self.nav.stack = previous
        self.nav.replace_page(0)
        return self.nav.current()


    def _get_root_notebook_id(self, notebook_id):
        """Get root notebook ID from any notebook ID"""
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            return notebook_id
        root = self.manager._find_root_notebook(notebook)
        return root.id if root else notebook_id

    def process_home_command(self, cmd):
        if cmd == "s" and not self.manager.notebooks:
            # No notebooks, silently ignore
            return "continue"

        terminal_width, terminal_height = shutil.get_terminal_size()

        # Get current page for pagination
        current = self.nav.current()
        page = current["page"] if current and "page" in current else 0

        # Calculate pagination EXACTLY like display
        terminal_width, terminal_height = shutil.get_terminal_size()
    
        # Count fixed UI elements exactly as they appear
        fixed_lines = 3  # Header
        fixed_lines += 1  # Page indicator line
        fixed_lines += 3  # Footer
        # Total fixed lines = 7
    
        available_for_items = terminal_height - fixed_lines
        items_per_page = int(available_for_items * 0.9)
        items_per_page = max(1, items_per_page)
    
        total_pages = (len(self.manager.notebooks) + items_per_page - 1) // items_per_page
    
        if page >= total_pages:
            page = max(0, total_pages - 1)
            self.nav.replace_page(page)
    
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(self.manager.notebooks))
        paginated_items = self.manager.notebooks[start_idx:end_idx]
        current_page = page + 1

        # PAGE NAVIGATION
        if cmd == "n" and page < total_pages:
            self.nav.replace_page(page + 1)
            return "navigate"
        elif cmd == "p" and page > 0:
            self.nav.replace_page(page - 1)
            return "navigate"
    
        # VIEW NOTEBOOK (supports v and v#)
        elif cmd.startswith("v"):
            if not self.manager.notebooks:
                return "continue"
            
            if cmd == "v":
                try:
                    idx = int(self.get_input("Enter notebook number to view: ")) - 1
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    idx = int(cmd[1:]) - 1
                except ValueError:
                    print("Invalid format. Use v1, v2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            if 0 <= idx < len(paginated_items):
                notebook = paginated_items[idx]
                
                # Get fresh notebook
                fresh_notebook = self.manager.find_notebook_by_id(notebook.id)
                if fresh_notebook:
                    notebook = fresh_notebook
                
                # Check if encrypted
                if notebook.id in self.manager.encrypted_notebooks:
                    # Read lock state directly from master registry
                    fp_hash = self.manager._compute_fp_hash()
                    registry = self.manager.load_registry(force_reload=True)
                    notebook_data = registry.get("notebooks", {}).get(notebook.id, {})
                    system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
                    is_locked = system_entry.get("locked", True)
                    
                    if is_locked:
                        # Direct unlock - password prompt only (no extra message)
                        crypto = self.manager.get_crypto(notebook.id)
                        if crypto:
                            # Update registry to unlocked
                            system_entry["locked"] = False
                            self.manager.save_registry(registry)
                            
                            # Update notebook object
                            notebook.locked = False
                            notebook._crypto = crypto
                            
                            # Update the manager's list
                            for i, nb in enumerate(self.manager.notebooks):
                                if nb.id == notebook.id:
                                    self.manager.notebooks[i] = notebook
                                    break
                            
                            # Proceed to notebook view
                            self.nav.push("notebook", notebook.id, 0)
                            return "navigate"
                        else:
                            # Unlock failed (wrong password or cancelled)
                            return "continue"
                    else:
                        # Notebook is unlocked – verify vault exists
                        vault_name = system_entry.get("vault", "default")
                        vault_path = self.manager.vault_manager.get_vault_path(vault_name)
                        
                        if not vault_path or not os.path.exists(vault_path):
                            # Vault missing - recovery flow
                            retry_count = 0
                            max_retries = 3
                            
                            while retry_count < max_retries:
                                print(f"\n  ❌ Cannot open '{notebook.name}'")
                                if vault_name == "default":
                                    print(f"     Default vault not found at: {vault_path}")
                                else:
                                    print(f"     Vault '{vault_name}' not found at: {vault_path}")
                                print("     Please insert the USB drive or locate the vault file.")
                                print()
                                print("  Options:")
                                print("    1) Retry (I've inserted the USB drive)")
                                print("    2) Locate vault file manually")
                                print("    3) Cancel")
                                print()
                                
                                choice = self.get_input("  Choose [1-3]: ").strip()
                                
                                if choice == "1":
                                    retry_count += 1
                                    vault_path = self.manager.vault_manager.get_vault_path(vault_name)
                                    if vault_path and os.path.exists(vault_path):
                                        print("\n  ✓ Vault found! Opening notebook...")
                                        self.nav.push("notebook", notebook.id, 0)
                                        return "navigate"
                                    else:
                                        remaining = max_retries - retry_count
                                        if remaining > 0:
                                            print(f"\n  ⚠️ Vault still not found. {remaining} attempt(s) remaining.")
                                        continue
                                
                                elif choice == "2":
                                    new_location = self.get_input("  Enter vault file path: ").strip()
                                    if new_location and os.path.exists(new_location):
                                        self.manager.vault_manager.set_vault_path(vault_name, new_location)
                                        self.manager._update_system_entry(notebook.id, {
                                            "path": system_entry.get("path"),
                                            "vault": vault_name,
                                            "entry": system_entry.get("entry"),
                                            "locked": False
                                        })
                                        print("  ✓ Vault location updated. Opening notebook...")
                                        self.nav.push("notebook", notebook.id, 0)
                                        return "navigate"
                                    else:
                                        print("  ✗ Invalid vault path.")
                                        continue
                                
                                else:
                                    return "continue"
                            
                            print("\n  Too many retries. Please try again later.")
                            self.get_input("\nPress Enter to continue...")
                            return "continue"
                
                # If we get here, notebook is unencrypted or unlocked and vault is available
                self.nav.push("notebook", notebook.id, 0)
                return "navigate"
            else:
                print("Invalid notebook number.")
                self.get_input("Press Enter to continue...")
                return "continue"

        # CREATE
        # In process_home_command, after handling 'c' command:
        elif cmd == "c":
            result = self.show_create_import_menu()
            if result == "navigate":
                # Force reload notebooks after creation
                self.manager.load_all_notebooks(quiet=True)
                return "navigate"
            return "continue"
        
        # DELETE (ADD THIS SECTION)
        elif cmd.startswith('d'):
            if not self.manager.notebooks:
                return "continue"
            
            if cmd == 'd':
                try:
                    display_num = int(self.get_input("Enter notebook number to delete: "))
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    display_num = int(cmd[1:])
                except ValueError:
                    print("Invalid format. Use d1, d2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            if 1 <= display_num <= len(paginated_items):
                notebook = paginated_items[display_num - 1]
                
                # Check if notebook is locked
                if notebook.id in self.manager.encrypted_notebooks:
                    if not hasattr(notebook, 'custom_path') or not notebook.custom_path:
                        print(f"\nCannot delete locked notebook '{notebook.name}'")
                        print("Unlock it first using [L]ock button")
                        self.get_input("Press Enter to continue...")
                        return "continue"
                
                print(f"\nDelete notebook '{notebook.name}':")
                print("  1. Remove from registry only (keep files)")
                print("  2. Standard delete (remove folder)")
                print("  3. Secure erase (remove completely)")
                print("  Enter - Cancel")
                print()
                
                choice = self.get_input("Choose [1-3]: ").strip()
                
                if choice == "1":
                    # Remove from registry only
                    self.manager.unregister_notebook(notebook.id)
                    self.manager.notebooks.remove(notebook)
                    print(f"✓ '{notebook.name}' removed from registry.")
                    if hasattr(notebook, 'custom_path') and notebook.custom_path:
                        print(f"  Files kept at: {notebook.custom_path}")
                        
                elif choice == "2":
                    # Standard delete
                    from eraser import Eraser
                    eraser = Eraser(self.manager, self)
                    eraser.standard_delete_notebook(notebook.id)
                    self.manager.load_all_notebooks()
                    
                elif choice == "3":
                    # Secure erase
                    confirm = self.get_input("Type 'erase' to confirm permanent removal: ")
                    if confirm.lower() == "erase":
                        from eraser import Eraser
                        eraser = Eraser(self.manager, self)
                        eraser.secure_erase_notebook(notebook)
                        self.manager.load_all_notebooks()
                    else:
                        print("Erase cancelled")
                        return "continue"
                else:
                    print("Deletion cancelled")
                    return "continue"
                
                self.nav.replace_page(0)
                return "navigate"
            else:
                print(f"Invalid notebook number. Please use 1-{len(paginated_items)}")
                self.get_input("Press Enter to continue...")
                return "continue"

        # SEARCH
        elif cmd.startswith("s"):
            if len(cmd) > 1 and cmd[1] == " ":
                query = cmd[2:].strip()
            elif len(cmd) > 1:
                query = cmd[1:].strip()
            else:
                query = self.get_input("Search query: ")
                if not query:
                    return "continue"
    
            result = self.comprehensive_search.show_search_simple(query)
            if result == "exit":
                return "exit"
            elif result == "navigate":
                return "navigate"
            return "continue"
                # MANAGE - open notebook manager
                # MANAGE - open notebook manager
                # MANAGE - open notebook manager
        # In the main_loop method, find where you handle the notebook manager return
# Around line where you have:
        # Manage - opens notebook manager
        # Manage - opens notebook manager
        # Manage - opens notebook manager
        elif cmd.startswith('m'):
            # Check for 'mf' to open full manager (always works)
            if cmd == 'mf':
                from notebook_manager import NotebookManager
                nb_manager = NotebookManager(manager=self.manager, ui=self, nav=self.nav)
                nb_manager.load_notebooks()
                nb_manager.load_accounts()
                result = nb_manager.run()
                if result == "exit_app":
                    return "exit"
                if not hasattr(self.manager, '_skip_next_reload'):
                    self.manager.load_all_notebooks(quiet=False)
                else:
                    delattr(self.manager, '_skip_next_reload')
                self.nav.replace_page(0)
                return "navigate"
            
            # If no notebooks, go directly to full manager (no prompt)
            if not self.manager.notebooks:
                from notebook_manager import NotebookManager
                nb_manager = NotebookManager(manager=self.manager, ui=self, nav=self.nav)
                nb_manager.load_notebooks()
                nb_manager.load_accounts()
                result = nb_manager.run()
                if result == "exit_app":
                    return "exit"
                if not hasattr(self.manager, '_skip_next_reload'):
                    self.manager.load_all_notebooks(quiet=False)
                else:
                    delattr(self.manager, '_skip_next_reload')
                self.nav.replace_page(0)
                return "navigate"
            
            # Handle single 'm' command (notebooks exist)
            if cmd == 'm':
                choice = self.get_input("Number or f: ").strip().lower()
                if not choice:
                    return "continue"
                if choice == 'f':
                    from notebook_manager import NotebookManager
                    nb_manager = NotebookManager(manager=self.manager, ui=self, nav=self.nav)
                    nb_manager.load_notebooks()
                    nb_manager.load_accounts()
                    result = nb_manager.run()
                    if result == "exit_app":
                        return "exit"
                    if not hasattr(self.manager, '_skip_next_reload'):
                        self.manager.load_all_notebooks(quiet=False)
                    else:
                        delattr(self.manager, '_skip_next_reload')
                    self.nav.replace_page(0)
                    return "navigate"
                try:
                    rel_num = int(choice)
                except ValueError:
                    print("Invalid input.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    rel_num = int(cmd[1:])
                except ValueError:
                    print("Invalid format. Use m, m#, or mf")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(self.manager.notebooks))
            items_on_page = end_idx - start_idx
            
            if 1 <= rel_num <= items_on_page:
                absolute_index = start_idx + (rel_num - 1)
                notebook_obj = self.manager.notebooks[absolute_index]
                
                notebook_dict = {
                    "id": notebook_obj.id,
                    "name": notebook_obj.name,
                    "path": notebook_obj.custom_path if hasattr(notebook_obj, 'custom_path') else None,
                    "encrypted": notebook_obj.id in self.manager.encrypted_notebooks,
                    "locked": notebook_obj.locked,
                    "note_count": notebook_obj.get_total_note_count(),
                    "file_count": notebook_obj.get_file_note_count(),
                    "sub_count": notebook_obj.get_total_subnotebook_count(),
                    "git_config": None,
                    "account": None
                }
                
                if hasattr(self, 'notebook_manager') and self.notebook_manager:
                    git_config = self.notebook_manager.get_notebook_config(notebook_obj.id)
                    if git_config:
                        notebook_dict["git_config"] = git_config
                    account = self.notebook_manager.get_account_for_notebook(notebook_obj.id)
                    if account:
                        notebook_dict["account"] = account
                
                from notebook_manager import NotebookManager
                nb_manager = NotebookManager(manager=self.manager, ui=self, nav=self.nav)
                nb_manager.load_notebooks()
                nb_manager.load_accounts()
                
                result = nb_manager.show_notebook_view(notebook_dict)
                if result == "exit_app":
                    return "exit"
                
                if not hasattr(self.manager, '_skip_next_reload'):
                    self.manager.load_all_notebooks(quiet=False)
                else:
                    delattr(self.manager, '_skip_next_reload')
                
                self.nav.replace_page(0)
                return "navigate"
            else:
                print(f"Invalid number. Use 1-{items_on_page}")
                self.get_input("Press Enter to continue...")
                return "continue"

        # In process_home_command, find the deletion section and update it:

        elif cmd.startswith('l'):
            if not self.manager.notebooks:
                return "continue"
            
            if cmd == 'l':
                try:
                    relative_num = int(self.get_input("Enter notebook number: "))
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    relative_num = int(cmd[1:])
                except ValueError:
                    print("Invalid format. Use l1, l2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            absolute_index = (page * items_per_page) + (relative_num - 1)
            full_notebooks = self.manager.notebooks

            if 0 <= absolute_index < len(full_notebooks):
                notebook = full_notebooks[absolute_index]

                # Only encrypted notebooks can be locked/unlocked
                if notebook.id not in self.manager.encrypted_notebooks:
                    print("Notebook is not encrypted.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

                # Get current system entry from master registry
                fp_hash = self.manager._compute_fp_hash()
                registry = self.manager.load_registry()
                notebook_data = registry.get("notebooks", {}).get(notebook.id, {})
                system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
                
                current_locked_state = system_entry.get("locked", True)

                if current_locked_state:
                    # CASE 1: Notebook is LOCKED → UNLOCK
                    self.manager._skip_next_reload = True
                    crypto = self.manager.get_crypto(notebook.id)
                    if crypto:
                        # Update registry to unlocked
                        system_entry["locked"] = False
                        #notebook_data["autolock"] = False  # Disable autolock temporarily
                        self.manager.save_registry(registry)

                        notebook.locked = False
                        notebook._crypto = crypto
                        if hasattr(self, 'notebook_manager') and self.notebook_manager:
                            self.notebook_manager.load_notebooks()
                        self.nav.replace_page(page)
                        return "navigate"
                    return "continue"
                else:
                    # CASE 2: Notebook is UNLOCKED → LOCK
                    self.manager._skip_next_reload = True
                    
                    # Update registry to locked
                    system_entry["locked"] = True
                    self.manager.save_registry(registry)
                    
                    # Clear all cached crypto
                    self.manager.unload_notebook(notebook.id)
                    
                    # Remove in‑memory access
                    notebook.custom_path = None
                    if notebook.id in self.manager.session_keys:
                        del self.manager.session_keys[notebook.id]
                    notebook.locked = True
                    if hasattr(notebook, '_crypto'):
                        delattr(notebook, '_crypto')
                    
                    # Clear SessionKeyVault cache
                    if hasattr(self.manager.session_keys, 'clear_cache'):
                        self.manager.session_keys.clear_cache(notebook.id)
                    
                    # Clear from ops caches
                    if hasattr(self.manager, 'ops') and hasattr(self.manager.ops, '_crypto_cache'):
                        self.manager.ops._crypto_cache.pop(notebook.id, None)
                    
                    if hasattr(self.manager, 'ops') and hasattr(self.manager.ops.crypto, '_key_cache'):
                        self.manager.ops.crypto._key_cache.pop(notebook.id, None)
                    
                    # Update in-memory notebook in manager's list
                    for i, nb in enumerate(self.manager.notebooks):
                        if nb.id == notebook.id:
                            nb.locked = True
                            nb.custom_path = None
                            if hasattr(nb, '_crypto'):
                                delattr(nb, '_crypto')
                            self.manager.notebooks[i] = nb
                            break

                    self.nav.replace_page(page)
                    return "navigate"
            else:
                print(f"Invalid notebook number.")
                self.get_input("Press Enter to continue...")
                return "continue"
        # QUIT
        # QUIT - support both 'q' (with confirmation) and 'qy' (auto-confirm)
        elif cmd == "q" or cmd == "qy":
            if cmd == "qy":
                # Auto-confirm quit
                self.clear_screen()
                return "exit"
            else:
                # Regular q with confirmation
                confirm = self.get_input("Quit Terminal Notes? [y/N]: ")
                if confirm.lower() == "y":
                    self.clear_screen()
                    return "exit"
                else:
                    return "continue"
    
    def refresh_search_if_needed(self):
        """Refresh search results if we're currently in a search view"""
        if hasattr(self, '_last_search_query') and self._last_search_query:
            from comprehensive_search import ComprehensiveSearch
            cs = ComprehensiveSearch(self.manager, self)
        
            # Determine context based on where we are
            current = self.nav.current()
            context = None
            if current and current['screen'] in ['notebook', 'subnotebooks']:
                notebook = self.manager.find_notebook_by_id(current['id'])
                if notebook:
                    root = self.manager._find_root_notebook(notebook)
                    context = root.id
        
            # Re-run the search
            results_data = cs.process(self._last_search_query, context=context)
            self._search_results = results_data['results']
            self._search_parsed = results_data['query_parsed']
        
            # 🟢 If we're in search screen, stay there with refreshed results
            if current and current['screen'] == 'search':
                return "refresh"
            return True
        return False

    def show_search_options(self):
        """Search options without Deleted Items Only"""
        while True:
            self.clear_screen()
            self.print_header("Search Notes")
    
            print("1. Quick Search (fast)")
            print("2. Comprehensive Search") 
            print("3. Back")  # 🆕 REMOVED "Deleted Items Only"
    
            print()
            self.print_footer("")
    
            choice = self.get_input("Choose [1-3]: ").strip()
    
            # 🆕 FIX: Silent filtering like home screen - only 1,2,3 work
            if choice == "1":
                result = self.search_manager.show_search_simple()
                if result == "exit":
                    return "exit"
                else:
                    continue
            elif choice == "2":
                result = self.comprehensive_search.show_search_simple()
                if result == "exit":
                    return "exit"
                elif result == "navigate":
                    return "navigate"  # 🆕 ADD: Handle navigation
                else:
                    continue
            elif choice == "3":
                return "continue"
            else:
                # 🆕 SILENTLY ignore any other input (like home screen)
                continue
            
    def handle_search(self, cmd):
        """Universal search - works from any screen with context"""
    
        # Parse the command
        if cmd == "s":
            query = self.get_input("Search query: ")
        else:
            query = cmd[1:].strip()
    
        if not query:
            return "continue"
        # 🟢 Store the query for refresh
        self._last_search_query = query
    
        # Save where we came from
        current = self.nav.current()
        self._search_return_to = {
            'screen': current['screen'] if current else 'home',
            'id': current.get('id') if current else None,
            'page': current.get('page', 0) if current else 0
        }
    
        # Determine context based on current screen and query
        words = query.split()
        has_global = any(word in ['g*', 'global*'] for word in words)
    
        # Remove global flag from query if present
        if has_global:
            clean_words = [w for w in words if w not in ['g*', 'global*']]
            clean_query = ' '.join(clean_words)
        else:
            clean_query = query
    
        # Determine context
        context = None
        if not has_global:
            # If we're in a notebook view, use the ROOT notebook as context
            if current and current.get('id') and current['screen'] in ['notebook', 'subnotebooks']:
                notebook = self.manager.find_notebook_by_id(current['id'])
                if notebook:
                    root = self.manager._find_root_notebook(notebook)
                    if root:
                        context = root.id  # ← Use ROOT notebook ID
            # If we're in a note view, use its ROOT notebook
            elif current and current['screen'] == 'note':
                note, notebook = self.manager.find_note_by_id(None, current['id'])
                if notebook:
                    root = self.manager._find_root_notebook(notebook)
                    if root:
                        context = root.id  # ← Use ROOT notebook ID
    
        # Process search with context
        results_data = self.comprehensive_search.process(clean_query, context=context)
    
        # Show results
        from cs_ui import show_search
        result = show_search(results_data, self, self.nav)
    
        if result == "exit":
            return "exit"
        elif result == "navigate":
            return "navigate"
        else:
            return "continue"

    def process_notebook_view_command(self, cmd):
        current = self.nav.current()
        if not current:
            return "continue"

        notebook_id = current["id"]
        page = current["page"]
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            print("Error: Notebook not found")
            self.get_input("Press Enter to continue...")
            return "continue"

        # CALCULATE PAGINATION - Same as display method
        # CALCULATE PAGINATION - EXACT COPY FROM DISPLAY
        try:
            _, terminal_height = shutil.get_terminal_size()

            # Count fixed UI elements
            fixed_lines = 3  # Header
            fixed_lines += 1  # "Notes & Files" header
            fixed_lines += 2  # Page indicator (blank line + indicator)
            fixed_lines += 3  # Footer

            if notebook.subnotebooks:
                fixed_lines += 2  # Subnotebook section

            available_for_notes = terminal_height - fixed_lines
            items_per_page = int(available_for_notes * 0.9)
            items_per_page = max(1, items_per_page)

        except:
            items_per_page = 10

        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(notebook.notes))
        paginated_notes = notebook.notes[start_idx:end_idx]
        total_pages = (len(notebook.notes) + items_per_page - 1) // items_per_page
        displayed_notes_count = len(paginated_notes)
        has_subnotebooks = len(notebook.subnotebooks) > 0
    
        # Page navigation
        if cmd == "n":
            if page < total_pages - 1:
                self.nav.replace_page(page + 1)
                return "navigate"
            else:
                print("Already on the last page.")
                self.get_input("Press Enter to continue...")
                return "continue"
        elif cmd == "p" and page > 0:
            self.nav.replace_page(page - 1)
            return "navigate"

        # CREATE
        elif cmd == "c":
            choice = self.show_create_choice_screen(notebook)
            if choice == "1":
                self.create_note(notebook)
                self.nav.replace_page(0)
                return "navigate"
            elif choice == "2":
                self.create_file_note(notebook)
                self.nav.replace_page(0)
                return "navigate"
            elif choice == "3":
                self.nav.push("subnotebooks", notebook_id, 0)
                return "navigate"
            else:
                print("Invalid choice.")
                self.get_input("Press Enter to continue...")
                return "continue"
        # In process_notebook_view_command, after other command handlers
        # 🟢 HANDLE INLINE SEARCH - OPENS SEARCH RESULTS SCREEN
        if cmd.startswith("s"):
            # Extract query
            if cmd == "s":
                query = self.get_input("Search query: ")
            else:
                query = cmd[1:].strip()
    
            if query:
                # 🟢 Store the query for refresh
                self._last_search_query = query
                # Set context to current notebook
                self.comprehensive_search._search_notebook_context = notebook.id
                # Perform search
                self.comprehensive_search.search_in_notebook(query, notebook.id)
                # 🟢 PUSH TO SEARCH RESULTS SCREEN (like home)
                self.nav.push("search", None, 0)
                return "navigate"
            return "continue"
            
        # In process_notebook_view_command, update the 'a' command handler:
        # In process_notebook_view_command, update the 'a' command handler:
        elif cmd == "a":
            # Check if there's ANY activity beyond root creation
            notebook_has_activity = False
            try:
                root = self.manager._find_root_notebook(notebook)
                if hasattr(root, 'custom_path') and root.custom_path:
                    repo_path = root.custom_path
                    if os.path.exists(os.path.join(repo_path, ".git")):
                        git_cmd = ["git", "rev-list", "--count", "HEAD"]
                        result = subprocess.run(git_cmd, cwd=repo_path, capture_output=True, text=True)
                        if result.returncode == 0:
                            notebook_has_activity = int(result.stdout.strip()) > 1
            except:
                notebook_has_activity = self.has_descendant_activity(notebook)

            if notebook_has_activity:
                from activity_view import ActivityView
                if not hasattr(self, 'activity_view') or self.activity_view is None:
                    self.activity_view = ActivityView(self.manager, self)
                self.activity_view.show(notebook.id)
                return "navigate"
            else:
                # Silent ignore - button wouldn't be shown
                return "continue"

        # VIEW: supports v and v# and sub-notebook quick view if last slot
        elif cmd.startswith("v"):
            # If plain 'v', ask for number
            if cmd == "v":
                try:
                    idx = int(self.get_input("Enter item number to view: ")) - 1
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    idx = int(cmd[1:]) - 1
                except ValueError:
                    print("Invalid format. Use v1, v2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            # 🟢 CRITICAL FIX - Get FRESH notebook from manager
            fresh_notebook = self.manager.find_notebook_by_id(notebook_id)
            if not fresh_notebook:
                print("Error: Notebook not found")
                return "continue"
    
            # Recalculate pagination with fresh notebook
            start_idx = page * items_per_page
            end_idx = min(start_idx + items_per_page, len(fresh_notebook.notes))
            current_page_notes = fresh_notebook.notes[start_idx:end_idx]
        
            if 0 <= idx < len(current_page_notes):
                note = current_page_notes[idx]
                self.nav.push("note", note.id, 0)
                return "navigate"
            elif idx == len(current_page_notes) and fresh_notebook.subnotebooks:
                self.nav.push("subnotebooks", notebook_id, 0)
                return "navigate"
            else:
                print(f"Invalid item number. Use 1-{len(current_page_notes)}")
                self.get_input("Press Enter to continue...")
                return "continue"

        elif cmd.startswith("d"):
            if cmd == "d":
                try:
                    display_num = int(self.get_input("Enter item number to delete: "))
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    display_num = int(cmd[1:])
                except ValueError:
                    print("Invalid format. Use d1, d2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            if 1 <= display_num <= len(paginated_notes):
                note = paginated_notes[display_num - 1]
        
                print(f"\nDelete note '{note.title}':")
                print("  1. Forget (keep in history)")
                print("  2. Erase (remove completely)")
                print("  Enter - Cancel")
                print()
        
                choice = self.get_input("Choose [1/2] or Enter to cancel: ")

                if choice == "1":
                    from eraser import Eraser
                    Eraser(self.manager, self).delete_item(note.id, 'forget', note.title)
                    print("✓ Note forgotten")
            
                elif choice == "2":
                    confirm = self.get_input("Type 'erase' to confirm permanent removal: ")
                    if confirm.lower() == "erase":
                        from eraser import Eraser
                        Eraser(self.manager, self).delete_item(note.id, 'erase', note.title)
                        print("✓ Note completely erased!")
                    else:
                        print("Erase cancelled")
                        return "continue"
                else:
                    print("Deletion cancelled")
                    return "continue"
            
                self.nav.replace_page(0)
                return "navigate"
            else:
                print(f"Invalid item number. Please use 1-{len(paginated_notes)}")
                self.get_input("Press Enter to continue...")
                return "continue"

        # RENAME (r or r#)
        elif cmd.startswith("r"):
            if cmd == "r":
                try:
                    idx = int(self.get_input("Enter note number to rename: ")) - 1
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    idx = int(cmd[1:]) - 1
                except ValueError:
                    print("Invalid format. Use r1, r2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            if 0 <= idx < displayed_notes_count:
                self.rename_note(paginated_notes[idx])
                self.nav.replace_page(0)
                return "navigate"
            else:
                print("Invalid note number.")
                self.get_input("Press Enter to continue...")
                return "continue"
                # QUIT
        elif cmd == "q" or cmd == "qy":
            if cmd == "qy":
                self.clear_screen()
                return "exit"
            else:
                confirm = self.get_input("Quit Terminal Notes? [y/N]: ")
                if confirm.lower() == "y":
                    self.clear_screen()
                    return "exit"

    def process_subnotebooks_view_command(self, cmd):
        terminal_width, terminal_height = shutil.get_terminal_size()

        current = self.nav.current()
        if not current:
            return "continue"

        parent_notebook_id = current["id"]
        page = current["page"]

        parent_notebook = self.manager.find_notebook_by_id(parent_notebook_id)
        if not parent_notebook:
            print("Error: Parent notebook not found")
            self.get_input("Press Enter to continue...")
            return "continue"

        numbered_list = parent_notebook.subnotebooks
    
        # 🟢 FIX: EXACTLY MATCH the calculation from show_subnotebooks_view_screen
        fixed_ui_lines = 8  # Same as in show_subnotebooks_view_screen
        available = terminal_height - fixed_ui_lines
        items_per_page = int(available * 0.9)
        items_per_page = max(1, items_per_page)

        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        paginated_items = numbered_list[start_idx:end_idx]
        total_pages = (len(numbered_list) + items_per_page - 1) // items_per_page
        displayed_count = len(paginated_items)

        # Page navigation
        if cmd == "n" and page < total_pages - 1:
            self.nav.replace_page(page + 1)
            return "navigate"
        elif cmd == "p" and page > 0:
            self.nav.replace_page(page - 1)
            return "navigate"

        # CREATE subnotebook
        # CREATE subnotebook
        elif cmd == "c":
            result = self.create_subnotebook(parent_notebook)
            if result == "navigate":
                return "navigate"
            return "continue"

        # VIEW subnotebook (v and v#)
        elif cmd.startswith("v"):
            if not paginated_items:
                print("No subnotebooks available.")
                self.get_input("Press Enter to continue...")
                return "continue"

            if cmd == "v":
                try:
                    idx = int(self.get_input("Enter subnotebook number to view: ")) - 1
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    idx = int(cmd[1:]) - 1
                except ValueError:
                    print("Invalid format. Use v1, v2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            if 0 <= idx < displayed_count:
                notebook = paginated_items[idx]
                self.nav.push("notebook", notebook.id, 0)
                return "navigate"
            else:
                print(f"Invalid subnotebook number. Please use 1-{displayed_count}")
                self.get_input("Press Enter to continue...")
                return "continue"
        # In process_subnotebooks_view_command, add this after delete handling:

        elif cmd.startswith("r"):
            if cmd == "r":
                try:
                    display_num = int(self.get_input("Enter subnotebook number to rename: "))
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    display_num = int(cmd[1:])
                except ValueError:
                    print("Invalid format. Use r1, r2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            # Check if within current page
            if 1 <= display_num <= displayed_count:
                item = paginated_items[display_num - 1]
                self.rename_subnotebook(item, parent_notebook)
                return "navigate"
            else:
                print(f"Invalid subnotebook number. Please use 1-{displayed_count}")
                self.get_input("Press Enter to continue...")
                return "continue"

        # DELETE subnotebook
        # DELETE subnotebook
        elif cmd.startswith("d"):
            if cmd == "d":
                try:
                    display_num = int(self.get_input("Enter subnotebook number to delete: "))
                except ValueError:
                    print("Please enter a valid number.")
                    self.get_input("Press Enter to continue...")
                    return "continue"
            else:
                try:
                    display_num = int(cmd[1:])
                except ValueError:
                    print("Invalid format. Use d1, d2, etc.")
                    self.get_input("Press Enter to continue...")
                    return "continue"

            if 1 <= display_num <= displayed_count:
                item = paginated_items[display_num - 1]
        
                self.clear_screen()
                self.print_header(f"Delete Subnotebook")
        
                print(f"Delete subnotebook '{item.name}':")
                print("  1. Forget (keep in history)")
                print("  2. Erase (remove completely)")
                choice = self.get_input("Choose [1/2] or Enter to cancel: ")

                if choice == "1":
                    from eraser import Eraser
                    Eraser(self.manager, self).delete_item(item.id, 'forget')
                    print("\n✓ Subnotebook forgotten")
                    self.get_input("Press Enter to continue...")
                    # 🟢 CRITICAL: Force immediate refresh
                    return "navigate"
                
                elif choice == "2":
                    confirm = self.get_input("Type 'erase' to confirm: ")
                    if confirm.lower() == "erase":
                        from eraser import Eraser
                        Eraser(self.manager, self).delete_item(item.id, 'erase', item.name)
                    else:
                        print("Erase cancelled")
                        self.get_input("Press Enter to continue...")
                        return "continue"
                else:
                    print("Deletion cancelled")
                    self.get_input("Press Enter to continue...")
                    return "continue"
        
                # 🟢 CRITICAL: Force refresh and return to subnotebook view
                return "navigate"
            else:
                print(f"Invalid subnotebook number. Please use 1-{displayed_count}")
                self.get_input("Press Enter to continue...")
                return "continue"
    
                # QUIT
        elif cmd == "q" or cmd == "qy":
            if cmd == "qy":
                self.clear_screen()
                return "exit"
            else:
                confirm = self.get_input("Quit Terminal Notes? [y/N]: ")
                if confirm.lower() == "y":
                    self.clear_screen()
                    return "exit"
        
    def process_note_view_command(self, cmd):
        current = self.nav.current()
        if not current:
            return "continue"

        note_id = current["id"]
        page = current["page"]

        # Find the note and its notebook
        note_found, notebook_found = self.manager.find_note_by_id(None, note_id)

        if not note_found or not notebook_found:
            print("Error: Note not found")
            self.get_input("Press Enter to continue...")
            return "continue"

        note = note_found
        notebook = notebook_found

        # Use the same helper method for consistent calculation
        terminal_width, terminal_height = shutil.get_terminal_size()
        pagination_info = self.calculate_note_pagination(note.content, terminal_height)
        needs_pagination = pagination_info['needs_pagination']
        total_pages = pagination_info['total_pages']

        # Page navigation
        if cmd == "p" and page > 0:
            self.nav.replace_page(page - 1)
            return "navigate"
        elif cmd == "n":
            if needs_pagination and page < total_pages - 1:
                self.nav.replace_page(page + 1)
                return "navigate"
            else:
                print("Already on the last page.")
                self.get_input("Press Enter to continue...")
                return "continue"
    
        # 🟢 EDIT - Using ops
        elif cmd == "e":
            self.clear_screen()

            original_content = note.content
            if note.is_file_note:
                new_content = self.external_editor_with_recovery(
                    note.content, 
                    file_extension=note.file_extension,
                    note_uuid=note.id,
                    parent_notebook_uuid=notebook.id,
                    note_title=note.title
                )
            elif note.created_with == "internal":
                new_content = self.internal_editor(note.content)
            else:
                new_content = self.external_editor_with_recovery(
                    note.content,
                    note_uuid=note.id,
                    parent_notebook_uuid=notebook.id,
                    note_title=note.title
                )

            if new_content is not None and new_content != original_content:
                from notebook_operations import NotebookOperations
                ops = NotebookOperations(self.manager)
                ops.edit_note(note, notebook, new_content)
                print("Note updated successfully!")
                self.get_input("Press Enter to continue...")
                return "continue"
            elif new_content == original_content:
                print("No changes made.")
                self.get_input("Press Enter to continue...")
                return "continue"
    
        # 🟢 EXPORT - Using ops
        elif cmd == "x" and note.is_file_note:
            self.export_file_note(note)
            return "continue"
    
        # 🟢 VIEW - Using ops (read-only)
        elif cmd == "v":
            if note.is_file_note:
                self.external_editor(note.content, read_only=True, file_extension=note.file_extension)
            else:
                self.external_editor(note.content, read_only=True)
            return "continue"
    
        # 🟢 RENAME - Using ops
        elif cmd == "r":
            self.rename_note(note)
            # 🟢 Return "refresh" to update search if needed
            current = self.nav.current()
            if current and current['screen'] == 'search':
                return "refresh"
            return "continue"
    
        # 🟢 TIMELINE - Using ops
        elif cmd == "t":
            result = self.comprehensive_search.show_note_timeline(note.id, notebook.id)
            if result == "exit":
                return "exit"
            return "continue"
    
        # 🟢 DELETE - Using ops via eraser
        elif cmd == "d":
            print(f"\nDelete note '{note.title}':")
            print("  1. Forget (keep in history)")
            print("  2. Erase (remove completely)")
            print("  Enter - Cancel")
            print()
        
            choice = self.get_input("Choose [1/2] or Enter to cancel: ")

            if choice == "1":
                from eraser import Eraser
                Eraser(self.manager, self).delete_item(note.id, 'forget', note.title)
                print("Note forgotten")
                self.nav.pop()
                return "navigate"
            
            elif choice == "2":
                confirm = self.get_input("Type 'erase' to confirm permanent removal: ")
                if confirm.lower() == "erase":
                    from eraser import Eraser
                    Eraser(self.manager, self).delete_item(note.id, 'erase', note.title)
                    print("Note completely erased!")
                    self.nav.pop()
                    return "navigate"
                else:
                    print("Erase cancelled")
                    return "continue"
            else:
                print("Deletion cancelled")
                return "continue"
    
                # QUIT
        elif cmd == "q" or cmd == "qy":
            if cmd == "qy":
                self.clear_screen()
                return "exit"
            else:
                confirm = self.get_input("Quit Terminal Notes? [y/N]: ")
                if confirm.lower() == "y":
                    self.clear_screen()
                    return "exit"

    # 🟢 ADD THIS METHOD INSIDE THE CLASS
    def terminal_supports_emoji(self):
        """Check if terminal can display emoji/lock symbols"""
        # Check encoding
        if sys.stdout.encoding and 'UTF-8' in sys.stdout.encoding.upper():
            return True
        
        # Check platform (Windows 10+ supports emoji)
        if sys.platform == 'win32':
            import platform
            if int(platform.release()) >= 10:
                return True
        
        # Check terminal program
        term_program = os.environ.get('TERM_PROGRAM', '')
        if term_program in ['iTerm.app', 'Apple_Terminal', 'vscode', 'Hyper']:
            return True
        
        # Assume older terminals don't support emoji
        return False
    
    def ensure_vault_present(self, notebook_id):
        """Check if vault is still present, lock if missing"""
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if notebook and not notebook.locked:
            vault_path = self.manager._get_vault_path(notebook_id)
            if not vault_path or not os.path.exists(vault_path):
                # Vault missing - force lock
                notebook.locked = True
                notebook.custom_path = None
                if notebook_id in self.manager.session_keys:
                    del self.manager.session_keys[notebook_id]
                if hasattr(notebook, '_crypto'):
                    delattr(notebook, '_crypto')
                return False
        return True
    
    
    def show_home_screen(self):
        term_width, term_height = shutil.get_terminal_size()

        if not hasattr(self, '_just_created'):
            self._just_created = False

        current = self.nav.current()
        page = current["page"] if current and "page" in current else 0

        self.clear_screen()

        terminal_width, terminal_height = shutil.get_terminal_size()

        fixed_ui_lines = 7
        available_for_items = terminal_height - fixed_ui_lines
        items_per_page = int(available_for_items * 0.9)
        items_per_page = max(1, items_per_page)

        numbered_list = self.manager.notebooks
        total_items = len(numbered_list)
        total_pages = (total_items + items_per_page - 1) // items_per_page if total_items > 0 else 1

        if self._just_created and total_items > 0:
            page = total_pages - 1
            self._just_created = False
            if current:
                current['page'] = page

        if page >= total_pages:
            page = max(0, total_pages - 1)
            if current:
                current['page'] = page

        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, total_items)
        paginated_items = numbered_list[start_idx:end_idx]
        current_page = page + 1

        # Count display for each notebook
        for notebook in paginated_items:
            is_encrypted = notebook.id in self.manager.encrypted_notebooks
            is_locked = notebook.locked if is_encrypted else False
            
            # For unlocked encrypted notebooks, try to get counts
            if is_encrypted and not is_locked and hasattr(notebook, 'custom_path') and notebook.custom_path:
                folder_path = notebook.custom_path
                struct_file = os.path.join(folder_path, "structure.json")
                if os.path.exists(struct_file):
                    try:
                        crypto = self.manager.session_keys.get(notebook.id)
                        from notebook_operations import read_json
                        struct_data = read_json(struct_file, crypto)
                        if struct_data:
                            def count_items(nb_data):
                                note_count = 0
                                file_count = 0
                                for note in nb_data.get('notes', []):
                                    if note.get('file_extension'):
                                        file_count += 1
                                    else:
                                        note_count += 1
                                sub_count = len(nb_data.get('subnotebooks', []))
                                for sub in nb_data.get('subnotebooks', []):
                                    sub_note_count, sub_file_count, sub_sub_count = count_items(sub)
                                    note_count += sub_note_count
                                    file_count += sub_file_count
                                    sub_count += sub_sub_count
                                return note_count, file_count, sub_count
                            
                            if "notebooks" in struct_data:
                                note_count = 0
                                file_count = 0
                                sub_count = 0
                                for nb in struct_data["notebooks"]:
                                    n, f, s = count_items(nb)
                                    note_count += n
                                    file_count += f
                                    sub_count += s
                            else:
                                note_count, file_count, sub_count = count_items(struct_data)
                            
                            notebook._display_file_count = file_count
                            notebook._display_note_count = note_count
                            notebook._display_sub_count = sub_count
                            continue
                    except:
                        pass
            
            # Fallback counts
            file_count = sum(1 for note in notebook.notes if note.is_file_note)
            regular_note_count = len(notebook.notes) - file_count
            sub_count = len(notebook.subnotebooks)
            
            notebook._display_file_count = file_count
            notebook._display_note_count = regular_note_count
            notebook._display_sub_count = sub_count

        # HEADER
        separator = "" * terminal_width
        print(separator)
        header_text = "Root Notebooks" if total_items != 1 else "Root Notebook"
        print(f"{header_text:^{terminal_width}}")
        print(separator)

        # DISPLAY NOTEBOOKS
        if not paginated_items:
            print("No notebooks yet.")
            print()
            print("Create your first notebook to get started!")
            print()
            print("or")
            print()
            print("Press [M] to import existing from remote")
        else:
            for i, notebook in enumerate(paginated_items, 1):
                is_encrypted = notebook.id in self.manager.encrypted_notebooks
                is_locked = notebook.locked if is_encrypted else False
                
                file_count = getattr(notebook, '_display_file_count', 0)
                regular_note_count = getattr(notebook, '_display_note_count', 0)
                sub_count = getattr(notebook, '_display_sub_count', 0)

                parts = []
                if regular_note_count > 0:
                    parts.append(f"{regular_note_count} note{'s' if regular_note_count != 1 else ''}")
                if file_count > 0:
                    parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
                if sub_count > 0:
                    parts.append(f"{sub_count} sub{'s' if sub_count != 1 else ''}")

                count_display = f" ({', '.join(parts)})" if parts else ""
                
                # Determine display name with lock symbols
                use_emoji = self.terminal_supports_emoji()
                
                # ========== DEBUG: Print what we're detecting ==========
                #print(f"[DEBUG] Notebook: {notebook.name}, is_encrypted={is_encrypted}, is_locked={is_locked}")
                # ========== END DEBUG ==========
                
                if is_encrypted:
                    if not is_locked:
                        if use_emoji:
                            display_name = f"🔐 {notebook.name}"
                        else:
                            display_name = f"[U] {notebook.name}"
                    else:
                        if use_emoji:
                            display_name = f"🔒 {notebook.name}"
                        else:
                            display_name = f"[L] {notebook.name}"
                        count_display = ""
                else:
                    display_name = notebook.name

                print(f"[{i}] {display_name}{count_display}")

        # Page indicator
        if total_pages > 1:
            page_text = f"Page {current_page} of {total_pages}"
            text_width = len(page_text)
            available_space = term_width - text_width
            left_space = available_space // 2
            right_space = available_space - left_space

            left_part = " " * left_space
            right_part = " " * right_space

            if current_page > 1 and left_space >= 6:
                left_part = " " * (left_space - 6) + "<<" + " " * 4
            if current_page < total_pages and right_space >= 6:
                right_part = " " * 4 + ">>" + " " * (right_space - 6)

            print()
            print(left_part + page_text + right_part)
            print()
        else:
            print()

        footer_options = ["[C]reate"]
        if self.manager.notebooks:
            footer_options.append("[V]iew")
            footer_options.append("[S]earch")
            footer_options.append("[D]elete")
            footer_options.append("[L]ock")
        footer_options.append("[M]anage")
        if total_pages > 1:
            if current_page < total_pages:
                footer_options.append("[N]ext")
            if current_page > 1:
                footer_options.append("[P]rev")
        footer_options.append("[Q]uit")

        #print("" * terminal_width)
        print("  ".join(footer_options))
        print()

    def show_notebook_list_screen(self):
        term_width, term_height = shutil.get_terminal_size()  # ← ADD THIS

        current = self.nav.current()
        if not current:
            return

        self.clear_screen()

        page = current["page"] if current else 0

        numbered_list = self.manager.notebooks
        total_items = len(numbered_list)

        # Get terminal size
        terminal_width, terminal_height = shutil.get_terminal_size()

        # MANUAL HEADER - FIRST THING AFTER CLEAR_SCREEN
        separator = "" * terminal_width
        print(separator)
    
        notebook_count = len(self.manager.notebooks)
        if notebook_count == 1:
            header_base = "Root Notebook"
        else:
            header_base = "Root Notebooks"

        # ADJUSTED CALCULATION - 90% instead of 80%
        fixed_ui_lines = 9  # Header(4) + Page indicator(2) + Footer(3)
        available_for_items = terminal_height - fixed_ui_lines
        items_per_page = int(available_for_items * 0.9)  # ← CHANGED TO 90%
        items_per_page = max(1, items_per_page)

        total_pages = (total_items + items_per_page - 1) // items_per_page
        current_page = page + 1

        notebook_count = len(self.manager.notebooks)
        if notebook_count == 1:
            header_base = "Root Notebook"
        else:
            header_base = "Root Notebooks"

        header_text = header_base  # No page count
                
        print(f"{header_text:^{terminal_width}}")
        print(separator)
        print()  # Empty line after header

        # Get paginated items
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        paginated_items = numbered_list[start_idx:end_idx]

        if not paginated_items:
            print("No notebooks yet.")
            print()
        else:
            # DISPLAY LIMITED ITEMS - safety check
            for i, notebook in enumerate(paginated_items, 1):
                if i > items_per_page:  # SAFETY CHECK
                    break
                
                note_count = notebook.get_total_note_count()
                sub_count = notebook.get_total_subnotebook_count()
                file_count = notebook.get_file_note_count()
                regular_note_count = note_count - file_count

                parts = []
                if regular_note_count > 0:
                    parts.append(
                        f"{regular_note_count} note{'s' if regular_note_count != 1 else ''}"
                    )
                if file_count > 0:
                    parts.append(f"{file_count} file{'s' if file_count != 1 else ''}")
                if sub_count > 0:
                    parts.append(f"{sub_count} sub{'s' if sub_count != 1 else ''}")

                count_display = f" ({', '.join(parts)})" if parts else ""
                print(f"[{i}] {notebook.name}{count_display}")

        # Page indicator with arrows exactly 4 spaces from centered counter
            if total_pages > 1:
                # Create page counter text
                page_text = f"Page {current_page} of {total_pages}"
                
                # Center the page counter in the available width
                centered_text = page_text.center(terminal_width)
                
                # Find where the centered text actually starts
                text_start = (terminal_width - len(page_text)) // 2
                text_end = text_start + len(page_text)
                
                # Convert centered_text to list for manipulation
                line_chars = list(centered_text)
                
                # Add left arrow 4 spaces before the text if needed
                if current_page > 1:
                    left_arrow_pos = text_start - 4 - 2  # 4 spaces + arrow width
                    if left_arrow_pos >= 0:
                        line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")
                
                # Add right arrow 4 spaces after the text if needed
                if current_page < total_pages:
                    right_arrow_pos = text_end + 4  # 4 spaces after text
                    if right_arrow_pos + 2 <= terminal_width:
                        line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")
                
                # Convert back to string
                line = "".join(line_chars)
                
                print()
                print(line)

        footer_options = ["[C]reate", "[B]ack"]  # ← Remove Quit
        if self.manager.notebooks:
            footer_options.insert(1, "[V]iew")
            footer_options.append("[D]elete")
        if total_pages > 1:
            if current_page < total_pages:
                footer_options.insert(0, "[N]ext")
            if current_page > 1:
                footer_options.insert(0, "[P]rev")
        footer_options.append("[Q]uit")  # ← Add at end

        # MANUAL FOOTER
        print("" * terminal_width)
        print("  ".join(footer_options))
        print()  # Empty line for input

    def show_notebook_view_screen(self):
        terminal_width, terminal_height = shutil.get_terminal_size()

        current = self.nav.current()
        if not current:
            return

        notebook_id = current["id"]
        page = current.get("page", 0)

        # First, get the notebook from memory
        notebook = self.manager.find_notebook_by_id(notebook_id)
        if not notebook:
            print("Error: Notebook not found")
            self.get_input("Press Enter to continue...")
            self.nav.pop()
            return

        # ========== READ LOCK STATE DIRECTLY FROM MASTER REGISTRY ==========
        is_locked = True
        if notebook.id in self.manager.encrypted_notebooks:
            fp_hash = self.manager._compute_fp_hash()
            registry = self.manager.load_registry(force_reload=True)
            notebook_data = registry.get("notebooks", {}).get(notebook.id, {})
            system_entry = notebook_data.get("systems", {}).get(fp_hash, {})
            is_locked = system_entry.get("locked", True)
        # ========== END REGISTRY READ ==========

        # Handle encryption based on lock state
        if notebook_id in self.manager.encrypted_notebooks:
            if is_locked:
                # Notebook is locked – need to unlock (will prompt for password)
                crypto = self.manager.get_crypto(notebook_id)
                if not crypto:
                    self.nav.pop()
                    return
            else:
                # Notebook is unlocked – get crypto from cache (no password prompt)
                crypto = self.manager.session_keys._cache.get(notebook_id)
                if not crypto:
                    # Fallback: try get_crypto (should just return cached keys)
                    crypto = self.manager.get_crypto(notebook_id)
                    if not crypto:
                        self.nav.pop()
                        return
            
            # Refresh notebook after decryption
            notebook = self.manager.find_notebook_by_id(notebook_id)
            if not notebook:
                print("❌ Failed to load notebook after decryption")
                self.nav.pop()
                return
            
            # Ensure crypto is attached
            self.manager.ensure_crypto(notebook)
        else:
            # For unencrypted notebooks
            self.manager.ensure_crypto(notebook)

        # Check if we just created something
        if hasattr(self, '_just_created') and self._just_created:
            fixed_lines = 3 + 1 + 2 + 3
            if notebook.subnotebooks:
                fixed_lines += 2

            available = terminal_height - fixed_lines
            items_per_page = int(available * 0.9)
            items_per_page = max(1, items_per_page)

            total_items = len(notebook.notes)
            last_page = (total_items - 1) // items_per_page if total_items > 0 else 0

            page = last_page
            self._just_created = False

            # Update navigation
            current['page'] = last_page
        else:
            page = current.get("page", 0)

        self.clear_screen()

        # SILENT RECOVERY - Check for any unsaved work
        try:
            recovered_count = self.recovery_system.recover_notebook_content(notebook)
            if recovered_count > 0:
                print(f"🔄 Recovered {recovered_count} items")
        except:
            pass

        # Custom header without extra blank line
        smart_path = self.get_smart_header_path(notebook.id)
        print("" * terminal_width)
        print(f"{smart_path:^{terminal_width}}")
        print("" * terminal_width)      

        # ... rest of your method (pagination, notes display, footer) ...   

        # DYNAMIC PAGINATION
        try:
            _, terminal_height = shutil.get_terminal_size()

            fixed_lines = 3  # Header (empty line + path + separator)
            fixed_lines += 1  # "Notes & Files" header
            fixed_lines += 2  # Page indicator section (blank line + page text)
            fixed_lines += 3  # Footer (separator + options + input line)

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

        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        total_pages = (len(notebook.notes) + items_per_page - 1) // items_per_page if notebook.notes else 1
        paginated_notes = notebook.notes[start_idx:end_idx] if notebook.notes else []
        
        notes_current_page = page + 1
        notes_total_pages = max(1, total_pages)

        if paginated_notes:
            # Calculate note/file counts
            if notebook.parent_id is not None:
                total_notes = notebook.get_total_note_count()
                total_files = notebook.get_file_note_count()  
                regular_note_count = total_notes - total_files
                file_count = total_files
            else:
                file_count = sum(1 for note in notebook.notes if note.is_file_note)
                regular_note_count = len(notebook.notes) - file_count

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
        
            for i, note in enumerate(paginated_notes, 1):
                updated = note.updated.strftime("%b %d %H:%M")
                timestamp_text = f"[Updated: {updated}]"
                
                # Calculate available space for title (use full terminal width)
                number_str = f"[{i}] "
                timestamp_width = len(timestamp_text)
                
                # Reserve space for number and timestamp
                reserved_space = len(number_str) + timestamp_width
                max_title_width = self.terminal_width - reserved_space - 2  # -2 for safety margin
                
                title_display = note.title
                if len(title_display) > max_title_width:
                    title_display = title_display[:max_title_width - 3] + "..."
                
                # Calculate padding to push timestamp to the right edge
                used_space = len(number_str) + len(title_display)
                padding = self.terminal_width - used_space - timestamp_width - 1
                
                print(f"{number_str}{title_display}{' ' * padding}{timestamp_text}")

        # Activity check
        notebook_has_activity = False
        try:
            root = self.manager._find_root_notebook(notebook)
            if root and hasattr(root, 'custom_path') and root.custom_path:
                repo_path = root.custom_path
                if repo_path and os.path.exists(os.path.join(repo_path, ".git")):
                    cmd = ["git", "rev-list", "--count", "HEAD"]
                    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
                    if result.returncode == 0:
                        total_commits = int(result.stdout.strip())
                        notebook_has_activity = total_commits > 1
        except:
            notebook_has_activity = self.has_descendant_activity(notebook)
        print()

        # Show subnotebooks section
        if notebook.subnotebooks:
            #if len(paginated_notes) == 0 or notes_total_pages <= 1:
            #   print()
        
            next_number = len(paginated_notes) + 1
            sub_count = len(notebook.subnotebooks)

            if sub_count == 1:
                print(f"Sub-notebook: ({sub_count} sub)")
                print(f"[{next_number}] View Sub-notebook =>")
            else:
                print(f"Sub-notebooks: ({sub_count} subs)")
                print(f"[{next_number}] View Sub-notebooks =>")
        
        # 🟢 MOVED PAGINATION HERE (after subnotebooks)
        if notes_total_pages > 1:
            page_text = f"Page {notes_current_page} of {notes_total_pages}"
            centered_text = page_text.center(terminal_width)
            text_start = (terminal_width - len(page_text)) // 2
            text_end = text_start + len(page_text)
            line_chars = list(centered_text)
            if notes_current_page > 1:
                left_arrow_pos = text_start - 4 - 2
                if left_arrow_pos >= 0:
                    line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")
            if notes_current_page < notes_total_pages:
                right_arrow_pos = text_end + 4
                if right_arrow_pos + 2 <= terminal_width:
                    line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")
            line = "".join(line_chars)
            print()
            print(line)
        
        if not paginated_notes and not notebook.subnotebooks:
            print()
            print("This notebook is empty.")
            print("Create note, file or sub-notebook to get started!")
            print()
        
        current_page = page + 1
        
        # Build footer options
        footer_options = ["[C]reate"]

        if notebook.notes or notebook.subnotebooks:
            footer_options.append("[V]iew")

        if notebook.notes:
            footer_options.append("[D]elete")

        if notebook_has_activity:
            footer_options.append("[A]ctivity")

        footer_options.append("[B]ack")

        if total_pages > 1:
            if current_page < total_pages:
                footer_options.append("[N]ext")
            if current_page > 1:
                footer_options.append("[P]rev")

        if self.should_show_jump():
            footer_options.append("[J]ump")

        footer_options.append("[Q]uit")

        self.print_footer("  ".join(footer_options))
        
        
    def show_subnotebooks_view_screen(self):
        terminal_width, term_height = shutil.get_terminal_size()
    
        # 🟢 ADD THESE LINES
        if not hasattr(self, '_just_created'):
            self._just_created = False
    
        current = self.nav.current()
        if not current:
            return
    
        page = current.get("page", 0)
        parent_notebook_id = current["id"]
    
        # 🟢 FIX: Get fresh parent_notebook for both pagination and display
        parent_notebook = self.manager.find_notebook_by_id(parent_notebook_id)
        if not parent_notebook:
            print("Error: Parent notebook not found")
            self.get_input("Press Enter to continue...")
            return
    
        # If we just created a subnotebook, go to last page
        if self._just_created:
            # Use same pagination calculation as the view
            fixed_ui_lines = 8
            available = term_height - fixed_ui_lines
            items_per_page = int(available * 0.9)
            items_per_page = max(1, items_per_page)
        
            total_items = len(parent_notebook.subnotebooks)
            last_page = (total_items - 1) // items_per_page if total_items > 0 else 0
        
            page = last_page
            # Update navigation
            if current:
                current['page'] = last_page
        
            self._just_created = False
    
        # Get fresh parent_notebook for display
        parent_notebook = self.manager.find_notebook_by_id(parent_notebook_id)
        if not parent_notebook:
            print("Error: Parent notebook not found")
            self.get_input("Press Enter to continue...")
            return

        # 🆕 MOVE RECOVERY HERE - before any screen rendering
        recovered_count = self.recovery_system.recover_notebook_content(parent_notebook)

        # 🆕 NOW clear and render ONCE
        self.clear_screen()

    # ... rest of your display code continues here ...

        # Get terminal size for this screen
        terminal_width, terminal_height = shutil.get_terminal_size()

        # HEADER - 4 LINES (with empty line after)
        separator = "" * terminal_width
        print(separator)
        smart_path = self.get_smart_header_path(parent_notebook.id)
        header_title = f"{smart_path} =>"
        print(f"{header_title:^{terminal_width}}")
        print(separator)

        numbered_list = parent_notebook.subnotebooks
        total_items = len(numbered_list)

        fixed_ui_lines = 0
        fixed_ui_lines += 1  # Header line
        fixed_ui_lines += 1  # Blank line after header
        fixed_ui_lines += 1  # Title line
        fixed_ui_lines += 1  # Blank line before items? (if any)
        fixed_ui_lines += 1  # Blank line after items (before page indicator)
        fixed_ui_lines += 1  # Page indicator line
        # NO blank line after page indicator
        fixed_ui_lines += 1  # Footer line
        fixed_ui_lines += 1  # Input line
        # Total = 8
        
        available = terminal_height - fixed_ui_lines  # 24 - 8 = 16
        items_per_page = int(available * 0.9)  # 16 * 0.9 = 14.4 → 14 items
        # Total fixed = 7
        
        items_per_page = max(1, items_per_page)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        needs_pagination = total_pages > 1

        # Get paginated items for current page
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        paginated_items = numbered_list[start_idx:end_idx]
        current_page = page + 1

        if not paginated_items:
            print("No subnotebooks yet.")
            print()
        else:
            total_sub_count = len(parent_notebook.subnotebooks)
            parent_name = parent_notebook.name

            notebook_plural = "Sub-notebook" if total_sub_count == 1 else "Sub-notebooks"
            count_plural = "sub" if total_sub_count == 1 else "subs"
            count_display = f"{total_sub_count} {count_plural}"

            print(f"{notebook_plural} of '{parent_name}' ({count_display}):")

            # Display items
            for i, notebook in enumerate(paginated_items, 1):
                if i > items_per_page:
                    break
                
                # ========== SURGICAL FIX: Count notes AND files separately ==========
                # Get note counts (regular notes + file notes)
                total_notes = notebook.get_total_note_count()
                total_files = notebook.get_file_note_count()
                regular_notes = total_notes - total_files
                sub_count = notebook.get_total_subnotebook_count()
                
                # Build parts with correct categorization
                parts = []
                if regular_notes > 0:
                    parts.append(f"{regular_notes} note{'s' if regular_notes != 1 else ''}")
                if total_files > 0:
                    parts.append(f"{total_files} file{'s' if total_files != 1 else ''}")
                if sub_count > 0:
                    parts.append(f"{sub_count} sub{'s' if sub_count != 1 else ''}")
                
                count_display = f" ({', '.join(parts)})" if parts else ""
                print(f"[{i}] {notebook.name}{count_display}")

        # Page indicator with arrows exactly 4 spaces from centered counter
        if needs_pagination:
            # Create page counter text
            current_page_num = page + 1
            page_text = f"Page {current_page_num} of {total_pages}"
            
            # Center the page counter in the available width
            centered_text = page_text.center(terminal_width)
            
            # Find where the centered text actually starts
            text_start = (terminal_width - len(page_text)) // 2
            text_end = text_start + len(page_text)
            
            # Convert centered_text to list for manipulation
            line_chars = list(centered_text)
            
            # Add left arrow 4 spaces before the text if needed
            if current_page_num > 1:
                left_arrow_pos = text_start - 4 - 2
                if left_arrow_pos >= 0:
                    line_chars[left_arrow_pos:left_arrow_pos+2] = list("<<")
            
            # Add right arrow 4 spaces after the text if needed
            if current_page_num < total_pages:
                right_arrow_pos = text_end + 4
                if right_arrow_pos + 2 <= terminal_width:
                    line_chars[right_arrow_pos:right_arrow_pos+2] = list(">>")
            
            # Convert back to string
            line = "".join(line_chars)
            
            print()
            print(line)
        else:
            print()  # 🆕 ADD EMPTY LINE WHEN NO PAGINATION
        

        # Find this section
        footer_options = ["[C]reate"]

        if parent_notebook.subnotebooks:
            footer_options.append("[V]iew")
            footer_options.append("[D]elete")

        footer_options.append("[B]ack")

        # 🟢 ADD RENAME BUTTON IF THERE ARE SUBNOTEBOOKS
        if parent_notebook.subnotebooks:
            footer_options.insert(2, "[R]ename")  # After View, before Delete

        if total_pages > 1:
            if current_page < total_pages:
                footer_options.append("[N]ext")
            if current_page > 1:
                footer_options.append("[P]rev")

        if self.should_show_jump():
            footer_options.append("[J]ump")

        footer_options.append("[Q]uit")

        # Footer
        print("" * terminal_width)
        print("  ".join(footer_options))
        print()  # Empty line for input
        
    def calculate_note_pagination(self, note_content, terminal_height):
        # Fixed lines: Header(4) + NoteInfo(2) + Separator(1) + Footer(3) = 10
        # Wait, let's count exactly:
        # - Header separator line (1)
        # - Header title line (1)  
        # - Header separator line (1)
        # - Empty line after header? (1) = 4
        # - Note info line 1 (1)
        # - Note info line 2 (1) = 2
        # - Separator line (1) = 1
        # - Page indicator (1) + empty line (1) = 2
        # - Footer separator line (1)
        # - Footer options line (1)
        # - Empty line for input (1) = 3
        # Total = 4 + 2 + 1 + 2 + 3 = 12
    
        fixed_lines = 12
        available_content_lines = terminal_height - fixed_lines
        available_content_lines = max(5, available_content_lines)  # At least 5 lines of content

        wrapped_lines = self.wrap_text(note_content)
    
        if len(wrapped_lines) == 0:
            return {
                'wrapped_lines': [''],
                'available_content_lines': available_content_lines,
                'needs_pagination': False,
                'total_pages': 1
            }
    
        needs_pagination = len(wrapped_lines) > available_content_lines
    
        if needs_pagination:
            total_pages = (len(wrapped_lines) + available_content_lines - 1) // available_content_lines
        else:
            total_pages = 1
    
        return {
            'wrapped_lines': wrapped_lines,
            'available_content_lines': available_content_lines,
            'needs_pagination': needs_pagination,
            'total_pages': total_pages
        }

    def show_note_view_screen(self):
        term_width, term_height = shutil.get_terminal_size()
        current = self.nav.current()
        if not current:
            return

        # Get terminal size ONCE and use it consistently
        terminal_width, terminal_height = shutil.get_terminal_size()
        self.clear_screen()

        note_id = current["id"]
        page = current["page"]

        # Find the note
        note_found, notebook_found = self.manager.find_note_by_id(None, note_id)
        if not note_found or not notebook_found:
            print("Error: Note not found")
            self.get_input("Press Enter to continue...")
            return

        note = note_found
        notebook = notebook_found

        # 🟢 ENSURE CONTENT IS PROPERLY LOADED (handles decryption)
        # The note object already has content, but we can verify/refresh if needed
        if hasattr(self, 'ops'):
            content = self.ops.get_note_content(note.id, notebook.id)
            if content is not None:
                note.content = content

        # HEADER - 3 LINES (no empty line after)
        separator = "" * terminal_width
        print(separator)
        smart_path = self.get_smart_header_path(notebook.id)
        print(f"{smart_path:^{terminal_width}}")
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

        # Use the helper method for consistent calculation
        pagination_info = self.calculate_note_pagination(note.content, terminal_height)
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
                self.nav.replace_page(page)

            start_idx = page * max_content_lines
            end_idx = start_idx + max_content_lines
            paginated_lines = wrapped_lines[start_idx:end_idx]
            current_page = page + 1
        else:
            # If content fits on one page, always show page 0
            if page > 0:
                page = 0
                self.nav.replace_page(0)
            paginated_lines = wrapped_lines
            current_page = 1
            total_pages = 1

        # Display content lines
        for i, line in enumerate(paginated_lines):
            if i >= max_content_lines:
                break
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

        if self.should_show_jump():
            footer_options.append("[J]ump")

        footer_options.append("[Q]uit")

        print("  ".join(footer_options))
        print()
        
    def external_editor_with_recovery(self, initial_content="", read_only=False, 
                                    file_extension=None, note_uuid=None, 
                                    parent_notebook_uuid=None, note_title=""):
        """External editor with autosave recovery - returns None if no changes made"""
        suffix = f".{file_extension}" if file_extension else ".txt"
        with tempfile.NamedTemporaryFile(mode="w+", suffix=suffix, delete=False, encoding="utf-8") as f:
            if initial_content:
                f.write(initial_content)
            f.flush()
            temp_path = f.name

        autosave_thread = None
        if not read_only and note_uuid:
            autosave_thread = threading.Thread(
                target=self._simple_autosave_loop,
                args=(temp_path, note_uuid, parent_notebook_uuid, note_title, bool(file_extension), file_extension),
                daemon=True
            )
            autosave_thread.start()

        try:
            used_editor = None
            config_path = os.path.join(self.app_dir, "config.json")
            mode = "view" if read_only else "edit"
            editors = EditorConfig.get_editor_list(mode, read_only, config_path)
        
            for editor in editors:
                try:
                    editor_name = editor.split()[0]
                    if subprocess.run(f"command -v {editor_name}", shell=True, capture_output=True).returncode == 0:
                        used_editor = editor
                        cmd = EditorConfig.get_launch_command(editor, temp_path, read_only, config_path)
                        subprocess.run(cmd, shell=True)
                        break
                except Exception:
                    continue

            if not used_editor:
                print("No suitable editor found. Please install micro, nvim, vim, or nano.")
                return initial_content

            with open(temp_path, "r", encoding="utf-8") as f:
                final_content = f.read()
        
            # ========== NORMALIZATION AND CHANGE DETECTION ==========
            def normalize(s):
                """Normalize string for comparison: strip whitespace, normalize line endings"""
                if s is None:
                    return ""
                # Normalize line endings (Windows CRLF -> LF, old Mac CR -> LF)
                normalized = s.replace('\r\n', '\n').replace('\r', '\n')
                # Strip leading/trailing whitespace (including newlines)
                return normalized.strip()
            
            if not read_only and note_uuid:
                initial_norm = normalize(initial_content)
                final_norm = normalize(final_content)
                
                # Check if content is EMPTY
                if not final_norm:
                    print("No content provided. File not saved.")
                    input("Press Enter to continue...")
                    # Clean up any existing recovery file
                    recovery_filename = self.recovery_system.get_recovery_filename(
                        note_uuid, note_title, bool(file_extension), file_extension
                    )
                    recovery_path = self.recovery_system.recovery_dir / recovery_filename
                    if recovery_path.exists():
                        recovery_path.unlink()
                    return None
                
                # Check if content is IDENTICAL to initial (no changes made)
                if initial_norm == final_norm:
                    print("No changes made. File not saved.")
                    input("Press Enter to continue...")
                    # Clean up any existing recovery file
                    recovery_filename = self.recovery_system.get_recovery_filename(
                        note_uuid, note_title, bool(file_extension), file_extension
                    )
                    recovery_path = self.recovery_system.recovery_dir / recovery_filename
                    if recovery_path.exists():
                        recovery_path.unlink()
                    return None
                
                # Changes detected - save recovery file and proceed
                self.recovery_system.save_recovery_file(
                    note_uuid, parent_notebook_uuid, final_content, note_title,
                    bool(file_extension), file_extension
                )
                recovery_filename = self.recovery_system.get_recovery_filename(
                    note_uuid, note_title, bool(file_extension), file_extension
                )
                recovery_path = self.recovery_system.recovery_dir / recovery_filename
                if recovery_path.exists():
                    recovery_path.unlink()
        
            return final_content

        finally:
            try:
                os.unlink(temp_path)
            except:
                pass

    def _simple_autosave_loop(self, temp_path, note_uuid, parent_notebook_uuid, note_title, is_file_note, file_extension):
        """Simple autosave that copies temp file to recovery every 30 seconds"""
        import time
        import os
    
        last_content = ""
        empty_saves = 0
    
        while True:
            try:
                # Check if temp file still exists
                if not os.path.exists(temp_path):
                    break
            
                # Read current content
                with open(temp_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            
                # 🟢 Only save if content has ACTUAL text (not just whitespace)
                if content and content.strip():
                    self.recovery_system.save_recovery_file(
                        note_uuid, parent_notebook_uuid, content, note_title,
                        is_file_note, file_extension
                    )
                    last_content = content
                    empty_saves = 0
                else:
                    empty_saves += 1
                    # If we've had 3 empty saves in a row, assume the file is intentionally empty
                    if empty_saves > 3:
                        # Remove any existing recovery file
                        recovery_filename = self.recovery_system.get_recovery_filename(
                            note_uuid, note_title, is_file_note, file_extension
                        )
                        recovery_path = self.recovery_system.recovery_dir / recovery_filename
                        if recovery_path.exists():
                            recovery_path.unlink()
            
                # Wait 30 seconds
                time.sleep(30)
            
            except:
                break
            
    def _start_autosave_thread(self, file_path, note_uuid, parent_notebook_uuid, 
                              note_title, is_file_note, file_extension):
        """Start background thread for autosaving to recovery"""
        import threading
        import time

        class AutosaveThread(threading.Thread):
            def __init__(self, recovery_system, file_path, note_uuid, parent_notebook_uuid,
                        note_title, is_file_note, file_extension):
                super().__init__(daemon=True)
                self.recovery_system = recovery_system
                self.file_path = file_path
                self.note_uuid = note_uuid
                self.parent_notebook_uuid = parent_notebook_uuid
                self.note_title = note_title
                self.is_file_note = is_file_note
                self.file_extension = file_extension
                self._stop_event = threading.Event()
                self.last_content = ""
                self._log(f"AUTOSAVE THREAD STARTED for {note_title}")
        
            def _log(self, message):
                """Log to file instead of screen"""
                with open("/tmp/terminal_notes_debug.log", "a") as f:
                    f.write(f"{datetime.now().isoformat()}: {message}\n")
        
            def run(self):
                self._log(f"AUTOSAVE: Monitoring {self.file_path}")
                while not self._stop_event.is_set():
                    try:
                        # Read current content from temp file
                        with open(self.file_path, 'r', encoding='utf-8') as f:
                            current_content = f.read()
                    
                        # Only save if content changed
                        if current_content != self.last_content:
                            self._log(f"AUTOSAVE: Content changed, saving recovery...")
                            success = self.recovery_system.save_recovery_file(
                                self.note_uuid, self.parent_notebook_uuid,
                                current_content, self.note_title,
                                self.is_file_note, self.file_extension
                            )
                            if success:
                                self._log("AUTOSAVE: Recovery file saved successfully")
                            else:
                                self._log("AUTOSAVE: Failed to save recovery file")
                            self.last_content = current_content
                    
                        # Wait before next autosave
                        self._log("AUTOSAVE: Waiting 30 seconds...")
                        self._stop_event.wait(30)
                    
                    except Exception as e:
                        self._log(f"AUTOSAVE ERROR: {e}")
                        # If we can't read the file, editor might be closed
                        break
        
            def stop(self):
                self._log("AUTOSAVE THREAD STOPPED")
                self._stop_event.set()

        thread = AutosaveThread(
            self.recovery_system, file_path, note_uuid, parent_notebook_uuid,
            note_title, is_file_note, file_extension
        )
        thread.start()
        return thread
    
    def has_descendant_activity(self, notebook):
        """Check if any descendant notebook has more than 1 commit"""
    
        # Check all subnotebooks recursively
        for sub in notebook.subnotebooks:
            try:
                root = self.manager._find_root_notebook(sub)
                if hasattr(root, 'custom_path') and root.custom_path:
                    repo_path = root.custom_path
                    if os.path.exists(os.path.join(repo_path, ".git")):
                        cmd = ["git", "rev-list", "--count", "HEAD"]
                        result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)
                        if result.returncode == 0 and int(result.stdout.strip()) > 1:
                            return True
            except:
                continue
    
        return False
            
    def create_note(self, notebook):
        self.clear_screen()
    
        # Get the full path for the notebook
        hierarchy = self.manager.get_notebook_hierarchy(notebook.id)
        if hierarchy and len(hierarchy) > 1:
            path_names = [nb.name for nb in hierarchy]
            if len(path_names) <= 3:
                display_path = "/".join(path_names)
            else:
                display_path = ".../" + "/".join(path_names[-3:])
        else:
            display_path = notebook.name

        self.print_header(f"Create New Note in: {display_path}")

        title = self.get_input("Note title: ")
        if not title:
            return

        # Clean title
        title = title.replace('\n', ' ').replace('\r', ' ').strip()
        if not title:
            print("Error: Title cannot be empty")
            self.get_input("Press Enter to continue...")
            return

        print()

        # Get current editor from config
        current_editor = getattr(self, 'edit_editor', 'micro')

        print("Choose editor (this choice is permanent for this note):")
        print()
        print("1. Internal editor")
        print("   • quick editing in terminal")
        print("   • Ctrl+D on empty line to save")
        print("   • no syntax highlighting")
        print()
        print("2. External editor")
        print(f"   • current editor: {current_editor}")
        print("   • full syntax highlighting for all file types")
        print("   • auto-saved every 30 seconds")
        print("   • change default editor in config.json")
        print()
        print("" * self.terminal_width)

        choice = self.get_input("Choose [1-2]: ")

        if choice == "1":
            self.clear_screen()
            content = self.internal_editor()
    
            if not content or not content.strip():
                print("\nNote creation cancelled - no content provided.")
                self.get_input("Press Enter to continue...")
                return "continue"
    
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
    
            # 🟢 FIX: create_note already adds the note to notebook.notes
            # We don't need to add it again
            note = ops.create_note(notebook, title, content.strip(), "internal")
    
            file_count = sum(1 for n in notebook.notes if n.is_file_note)
            regular_count = len(notebook.notes) - file_count
            
    
            # Find root notebook for saving
            root = self.manager._find_root_notebook(notebook)
    
            # Update the notebook in the manager's notebook list
            # Also force update the manager's list entry
            for i, nb in enumerate(self.manager.notebooks):
                if nb.id == notebook.id:
                    print(f"[DEBUG] Before update: manager.notebooks[{i}] id={id(nb)}, locked={nb.locked}")
                    nb.locked = notebook.locked
                    print(f"[DEBUG] After update: manager.notebooks[{i}] id={id(nb)}, locked={nb.locked}")
                    break
    
            # If this is a subnotebook, also update it in its parent's structure
            if notebook.id != root.id:
                # Find and update the notebook in the manager's hierarchy
                for i, root_nb in enumerate(self.manager.notebooks):
                    if root_nb.id == root.id:
                        # Recursively update the notebook in the hierarchy
                        updated_root = self._update_notebook_in_hierarchy(root_nb, notebook.id, notebook)
                        if updated_root:
                            self.manager.notebooks[i] = updated_root
                            break
    
            print(f"\n✓ Note '{title}' created successfully")
    
            # 🟢 Force refresh the manager's in-memory state
            self.manager.load_all_notebooks(quiet=True)  # Force reload from disk
    
            # Find the updated notebook in the manager
            updated_notebook = self.manager.find_notebook_by_id(notebook.id)
            if updated_notebook:
                file_count = sum(1 for n in updated_notebook.notes if n.is_file_note)
                regular_count = len(updated_notebook.notes) - file_count
                
            
                # Update the current navigation's notebook reference
                current = self.nav.current()
                if current and current['screen'] == 'notebook' and current['id'] == notebook.id:
                    # We're still in the same notebook, so refresh the page
                    terminal_width, terminal_height = shutil.get_terminal_size()
                
                    # Get fresh counts
                    fresh_file_count = sum(1 for note in updated_notebook.notes if note.is_file_note)
                    fresh_total = len(updated_notebook.notes)
                
                    # Calculate total pages
                    fixed_lines = 3 + 1 + 2 + 3
                    if updated_notebook.subnotebooks:
                        fixed_lines += 2
                    available = terminal_height - fixed_lines
                    items_per_page = int(available * 0.9)
                    items_per_page = max(1, items_per_page)
                
                    total_pages = (fresh_total + items_per_page - 1) // items_per_page if fresh_total > 0 else 1
                
                    if total_pages > 0:
                        self.nav.replace_page(total_pages - 1)  # Go to last page where new note appears
                    else:
                        self.nav.replace_page(0)
    
            self._just_created = True
            return "navigate"

        elif choice == "2":
            self.clear_screen()
            print("Opening external editor...")
    
            # 🟢 STEP 1: Create TEMPORARY note object for recovery (NOT saved to disk)
            from terminal_notes_core import Note
            temp_note = Note(title, "", created_with="external")
    
            # 🟢 STEP 2: Edit with recovery using temp UUID
            content = self.external_editor_with_recovery(
                initial_content="",
                read_only=False,
                file_extension=None,
                note_uuid=temp_note.id,  # ← Pass temp UUID for recovery
                parent_notebook_uuid=notebook.id,
                note_title=title
            )

            # 🟢 STEP 3: Check if content was added
            if not content or not content.strip():
                print("\nNo content provided. Note creation cancelled.")
                # Clean up any recovery file
                recovery_filename = self.recovery_system.get_recovery_filename(
                    temp_note.id, title, False, None
                )
                recovery_path = self.recovery_system.recovery_dir / recovery_filename
                if recovery_path.exists():
                    recovery_path.unlink()
                return "continue"
    
            # 🟢 STEP 4: Create REAL note with content (SINGLE COMMIT)
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
            note = ops.create_note(notebook, title, content.strip(), "external")
    
            # 🟢 STEP 5: Clean up recovery file now that note is saved
            recovery_filename = self.recovery_system.get_recovery_filename(
                temp_note.id, title, False, None
            )
            recovery_path = self.recovery_system.recovery_dir / recovery_filename
            if recovery_path.exists():
                recovery_path.unlink()
    
            # Find root notebook for saving
            root = self.manager._find_root_notebook(notebook)
    
            # Update the notebook in the manager's notebook list
            for i, nb in enumerate(self.manager.notebooks):
                if nb.id == root.id:
                    self.manager.notebooks[i] = root
                    break
    
            # If this is a subnotebook, also update it in its parent's structure
            if notebook.id != root.id:
                for i, root_nb in enumerate(self.manager.notebooks):
                    if root_nb.id == root.id:
                        updated_root = self._update_notebook_in_hierarchy(root_nb, notebook.id, notebook)
                        if updated_root:
                            self.manager.notebooks[i] = updated_root
                            break
    
            print(f"\n✓ Note '{title}' created successfully")
    
            # Force refresh
            self.manager.load_all_notebooks(quiet=True)
    
            # Update navigation
            updated_notebook = self.manager.find_notebook_by_id(notebook.id)
            if updated_notebook:
                current = self.nav.current()
                if current and current['screen'] == 'notebook' and current['id'] == notebook.id:
                    terminal_width, terminal_height = shutil.get_terminal_size()
            
                    fresh_total = len(updated_notebook.notes)
                    fixed_lines = 3 + 1 + 2 + 3
                    if updated_notebook.subnotebooks:
                        fixed_lines += 2
                    available = terminal_height - fixed_lines
                    items_per_page = int(available * 0.9)
                    items_per_page = max(1, items_per_page)
            
                    total_pages = (fresh_total + items_per_page - 1) // items_per_page if fresh_total > 0 else 1
            
                    if total_pages > 0:
                        self.nav.replace_page(total_pages - 1)
                    else:
                        self.nav.replace_page(0)
    
            self._just_created = True
            return "navigate"

        else:
            return "continue"
        
    def edit_note(self, note, notebook):
        """Edit a note using ops - only modifies notes.json and structure.json"""
        self.clear_screen()
        
        original_content = note.content
        
        if note.is_file_note:
            new_content = self.external_editor_with_recovery(
                note.content,
                file_extension=note.file_extension,
                note_uuid=note.id,
                parent_notebook_uuid=notebook.id,
                note_title=note.title
            )
        elif note.created_with == "internal":
            new_content = self.internal_editor(note.content)
        else:
            new_content = self.external_editor_with_recovery(
                note.content,
                note_uuid=note.id,
                parent_notebook_uuid=notebook.id,
                note_title=note.title
            )

        if new_content is None:
            return "continue"
            
        if new_content == original_content:
            print("\nNo changes made.")
            self.get_input("Press Enter to continue...")
            return "continue"

        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        
        # OPS HANDLES EVERYTHING:
        # - Updates note content
        # - Updates timestamp
        # - Saves only structure.json and appropriate content file
        # - Git commit with correct files
        # - Crypto if needed
        ops.edit_note(note, notebook, new_content)
        
        print("\n✓ Note updated successfully")
        self.get_input("Press Enter to continue...")
        return "navigate"
    
    def rename_note(self, note):
        """Rename a note using ops"""
        # 🟢 Store that we're coming from search if needed
        from_search = False
        current = self.nav.current()
        if current and current['screen'] == 'search':
            from_search = True
            self._rename_from_search = True
        self.clear_screen()
        self.print_header("Rename Note")

        old_title = note.title
        print(f"Current name: {note.title}")

        if note.is_file_note:
            if "." in note.title:
                name_parts = note.title.rsplit(".", 1)
                current_filename = name_parts[0]
                current_extension = name_parts[1]
                print(f"File extension: .{current_extension} (will be kept)")
                new_filename = self.get_input("New filename (without extension): ")

                if new_filename and new_filename.strip():
                    new_title = f"{new_filename.strip()}.{current_extension}"
                    
                    from notebook_operations import NotebookOperations
                    ops = NotebookOperations(self.manager)
                    
                    # Find notebook
                    _, notebook = self.manager.find_note_by_id(None, note.id)
                    if notebook:
                        ops.rename_note(note, notebook, new_title)
                        print(f"\n✓ Renamed to: {new_title}")
                    else:
                        print("Error: Could not find parent notebook")
                else:
                    print("Filename cannot be empty.")
            else:
                new_title = self.get_input("New name: ")
                if new_title and new_title.strip():
                    from notebook_operations import NotebookOperations
                    ops = NotebookOperations(self.manager)
                    
                    _, notebook = self.manager.find_note_by_id(None, note.id)
                    if notebook:
                        ops.rename_note(note, notebook, new_title.strip())
                        print("\n✓ Note renamed!")
                    else:
                        print("Error: Could not find parent notebook")
                else:
                    print("Name cannot be empty.")
        else:
            new_title = self.get_input("New title: ")
            if new_title and new_title.strip():
                from notebook_operations import NotebookOperations
                ops = NotebookOperations(self.manager)
                
                _, notebook = self.manager.find_note_by_id(None, note.id)
                if notebook:
                    ops.rename_note(note, notebook, new_title.strip())
                    print("\n✓ Note renamed!")
                else:
                    print("Error: Could not find parent notebook")
            else:
                print("Title cannot be empty.")
            # 🟢 APPEND START - Refresh search if needed
        if from_search:
            self.refresh_search_if_needed()
        # 🟢 APPEND END

        self.get_input("Press Enter to continue...")
    
    def create_external_notebook(self, name, external_path, encrypt=False, phrase=None):
        """
        Create notebook at external location (USB, network drive, etc.)
        Delegates to create_notebook with custom_path parameter
        """
        # Simply delegate to create_notebook with custom_path
        return self.manager.create_notebook(name, custom_path=external_path, encrypt=encrypt, phrase=phrase)
        
    def show_create_import_menu(self):
        """Unified menu for create (default/other) and import - Enter to cancel anywhere"""
        if not hasattr(self, 'path_history'):
            self.path_history = []
        
        while True:
            self.clear_screen()
            self.print_header("Create / Import Notebook")

            print("1. Default location (notebooks_root/)")
            print("   → Quick creation in app's default directory")
            print()
            print("2. External location (USB/Network drive) 🔒 MORE SECURE")
            print("   → Choose any folder on your system")
            print("   → Perfect for encrypted notebooks on USB drives")
            print("   → Easy to backup, sync with cloud, or store on encrypted drive")
            print()
            print("3. Import existing notebook")
            print("   → Load an existing Terminal Notes notebook from local path")
            print("   → Must contain structure.json and Git history")
            print()
            print("4. Import from Git URL")
            print("   → Clone and import a notebook from GitHub/GitLab/Bitbucket")
            print("   → Enter repository URL (must end with .git)")
            print("   → Will prompt for account credentials if needed")
            print()
            print()
        
            choice = self.get_input("Choose [1-4] or Enter to cancel: ")

            if not choice:
                return "continue"

            if choice == "1":
                # Default location
                self.clear_screen()
                self.print_header("Create Notebook - Default Location")
        
                name = self.get_input("Notebook name (Enter to cancel): ")
                if not name:
                    continue
        
                print()
                print("  [1] Encrypted notebook (password protected)")
                print("  [2] Unencrypted notebook")
                print()
                encrypt_choice = self.get_input("  Choose [1/2] or press Enter to cancel: ").strip()

                if not encrypt_choice:
                    print("\n  Notebook creation cancelled.")
                    self.get_input("Press Enter to continue...")
                    continue

                if encrypt_choice == "1":
                    encrypt = True
                elif encrypt_choice == "2":
                    encrypt = False
                else:
                    print("\n  Invalid choice. Please enter 1 or 2.")
                    self.get_input("Press Enter to continue...")
                    continue
        
                self.clear_screen()
        
                try:
                    notebook = self.manager.create_notebook(name, encrypt=encrypt)
                    if notebook:
                        self._just_created = True
                        print(f"\nPress Enter to continue...", end="")
                        input()
                        return "navigate"
                except ValueError as e:
                    print(f"\n✗ Error: {e}")
                    self.get_input("Press Enter to continue...")
                continue
            
            elif choice == "2":
                # External location
                self.clear_screen()
                self.print_header("Create External Notebook")
        
                print("Enter the DIRECTORY where you want to create the notebook:")
                print("  • The notebook will be created in its own subfolder")
                print("  • Example: /mnt/usb/ → creates /mnt/usb/notebook-name/")
                print("  • Perfect for encrypted notebooks on removable drives")
                print()
        
                if self.path_history:
                    print("Recent paths:")
                    for i, path in enumerate(self.path_history, 1):
                        print(f"  [{i}] {path}")
                    print()
                    prompt = f"External path [1-{len(self.path_history)} or new path] (Enter to cancel): "
                else:
                    prompt = "External path (Enter to cancel): "
        
                path_input = self.get_path_input(prompt)
                if not path_input:
                    continue
        
                if path_input.isdigit() and self.path_history:
                    idx = int(path_input) - 1
                    if 0 <= idx < len(self.path_history):
                        external_path = self.path_history[idx]
                        print(f"Using: {external_path}")
                    else:
                        print("Invalid history number.")
                        self.get_input("Press Enter to continue...")
                        continue
                else:
                    external_path = path_input
        
                external_path = os.path.expanduser(external_path)
                if not os.path.exists(external_path):
                    print(f"\n  Directory does not exist. Create it? [y/N]: ", end='')
                    if input().strip().lower() == 'y':
                        os.makedirs(external_path, exist_ok=True)
                    else:
                        print("  Cancelled.")
                        self.get_input("Press Enter to continue...")
                        continue
        
                name = self.get_input("Notebook name (Enter to cancel): ")
                if not name:
                    continue
        
                print()
                print("  [1] Encrypted notebook (password protected)")
                print("  [2] Unencrypted notebook")
                print()
                encrypt_choice = self.get_input("  Choose [1/2] or press Enter to cancel: ").strip()

                if not encrypt_choice:
                    print("\n  Notebook creation cancelled.")
                    self.get_input("Press Enter to continue...")
                    continue

                if encrypt_choice == "1":
                    encrypt = True
                elif encrypt_choice == "2":
                    encrypt = False
                else:
                    print("\n  Invalid choice. Please enter 1 or 2.")
                    self.get_input("Press Enter to continue...")
                    continue
        
                self.clear_screen()
        
                try:
                    notebook = self.manager.create_notebook(name, custom_path=external_path, encrypt=encrypt)
                    if notebook:
                        if external_path not in self.path_history:
                            self.path_history.insert(0, external_path)
                            self.path_history = self.path_history[:3]
                        self._just_created = True
                        print(f"\nPress Enter to continue...", end="")
                        input()
                        return "navigate"
                except ValueError as e:
                    print(f"\n✗ Error: {e}")
                    self.get_input("Press Enter to continue...")
                continue
            
            elif choice == "3":
                # Import existing notebook
                self.clear_screen()
                self.print_header("Import Existing Notebook")
        
                print("Enter the path to an existing Terminal Notes notebook folder:")
                print("  • Must contain structure.json, notes.json, files.json")
                print("  • Should be a Git repository for full functionality")
                print()
        
                if self.path_history:
                    print("Recent paths:")
                    for i, path in enumerate(self.path_history, 1):
                        print(f"  [{i}] {path}")
                    print()
                    prompt = f"Notebook path [1-{len(self.path_history)} or new path] (Enter to cancel): "
                else:
                    prompt = "Notebook path (Enter to cancel): "
        
                path_input = self.get_path_input(prompt)
                if not path_input:
                    continue
        
                if path_input.isdigit() and self.path_history:
                    idx = int(path_input) - 1
                    if 0 <= idx < len(self.path_history):
                        path = self.path_history[idx]
                        print(f"Using: {path}")
                    else:
                        print("Invalid history number.")
                        self.get_input("Press Enter to continue...")
                        continue
                else:
                    path = path_input
        
                result = self.importer.import_notebook_flow_with_path(path)
        
                if result == "success" or result is True:
                    if path not in self.path_history:
                        self.path_history.insert(0, path)
                        self.path_history = self.path_history[:3]
                    return "navigate"
                continue
            
            elif choice == "4":
                # Import from Git URL
                self.clear_screen()
                self.print_header("Import from Git URL")
        
                print("Enter Git repository URL (must end with .git):")
                print()
                print("Examples:")
                print("  https://github.com/user/repo.git")
                print("  git@github.com:user/repo.git")
                print("  https://gitlab.com/user/project.git")
                print("  file:///home/user/backups/notebook.git")
                print()
        
                url = self.get_input("URL (Enter to cancel): ")
                if not url:
                    continue
        
                if not url.endswith('.git'):
                    print("\nURL must end with .git")
                    self.get_input("Press Enter to continue...")
                    continue
        
                from notebook_manager import NotebookManager
                nb_manager = NotebookManager(manager=self.manager, ui=self, nav=self.nav)
                nb_manager.load_accounts()
                nb_manager.import_from_url(url)
                
                self.manager.load_all_notebooks(quiet=True)
                return "navigate"
            
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
                self.get_input("Press Enter to continue...")
                continue

    def show_create_choice_screen(self, notebook):
        self.clear_screen()
        term_width = self.terminal_width
    
        # Header
        print("" * term_width)
        header = f"Create in: {notebook.name}"
        print(f"{header:^{term_width}}")
        print("" * term_width)
        print()
    
        # Static menu - no dynamic config
        print("1 - Regular Note")
        print("    • internal editor (quick, Ctrl+D to save)")
        print("    • external editor (micro/nvim/vim)")
        print("    • auto-saved every 30 seconds")
        print()
    
        print("2 - Specialized File")
        print("    • 80+ supported formats (.py, .html, .sh, .md)")
        print("    • full syntax highlighting")
        print("    • file extension determines purpose")
        print()
    
        print("3 - Sub-notebook")
        print("    • nested container for organization")
        print("    • holds unlimited notes, files, and sub-notebooks")
        print("    • perfect for projects and hierarchies")
        print()
    
        print("" * term_width)
    
        return self.get_input("Choose [1-3]: ")

    def create_file_note(self, notebook):
        """Create a specialized file note - direct filename input or category selection"""
        
        # ========== DATA STRUCTURE ==========
        categories_data = {
            "Web": [
                "astro", "css", "graphql", "html", "js", "jsx", "mdx", 
                "pug", "scss", "svelte", "ts", "vue", "wasm"
            ],
            "Backend": [
                "c", "cpp", "crystal", "d", "go", "java", "jl", "lua", 
                "nim", "php", "pl", "py", "r", "rb", "rs", "zig"
            ],
            "Mobile": [
                "kt", "swift"
            ],
            "DevOps": [
                "cfg", "dockerignore", "env", "hcl", "ini", "justfile", 
                "nix", "sh", "tf", "toml", "yaml", "yml"
            ],
            "Data": [
                "hjson", "json", "proto", "ron", "sql", "xml"
            ],
            "Documentation": [
                "adoc", "bib", "cls", "md", "org", "rst", "sty", "tex", "txt", "typ", "wiki"
            ],
            "Config Files": [
                "aliases", "bash_profile", "bashrc", "curlrc", "editorconfig", "fish",
                "gitmessage", "inputrc", "irbrc", "lua", "mailmap", "profile", 
                "screenrc", "vimrc", "wgetrc", "Xresources", "zprofile", "zshrc"
            ],
            "Git": [
                "gitattributes", "gitconfig", "gitignore"
            ],
            "Runtime": [
                "gemrc", "npmrc", "Rprofile", "yarnrc"
            ],
            "App Configs": [
                "tmux.conf"
            ],
            "CI/CD": [
                "bat", "cmake", "Dockerfile", "gitlab-ci.yml", "Jenkinsfile", "ps1", "service", "timer"
            ],
        }
        
        # Special files with their exact filenames
        special_files = {
            "bashrc": ".bashrc",
            "zshrc": ".zshrc",
            "profile": ".profile",
            "aliases": ".aliases",
            "bash_profile": ".bash_profile",
            "zprofile": ".zprofile",
            "vimrc": ".vimrc",
            "lua": "init.lua",
            "editorconfig": ".editorconfig",
            "screenrc": ".screenrc",
            "wgetrc": ".wgetrc",
            "curlrc": ".curlrc",
            "fish": "config.fish",
            "gitmessage": ".gitmessage",
            "mailmap": ".mailmap",
            "gitconfig": ".gitconfig",
            "gitignore": ".gitignore",
            "gitattributes": ".gitattributes",
            "npmrc": ".npmrc",
            "yarnrc": ".yarnrc",
            "gemrc": ".gemrc",
            "Rprofile": ".Rprofile",
            "irbrc": ".irbrc",
            "tmux.conf": ".tmux.conf",
            "inputrc": ".inputrc",
            "Xresources": ".Xresources",
            "justfile": "justfile",
            "dockerignore": ".dockerignore",
            "env": ".env",
            "Dockerfile": "Dockerfile",
            "Jenkinsfile": "Jenkinsfile",
            "gitlab-ci.yml": ".gitlab-ci.yml",
            "cmake": "CMakeLists.txt",
        }
        
        # Build categories list dynamically
        categories = []
        for cat_name, extensions in categories_data.items():
            extensions.sort()
            ext_list = []
            for ext in extensions:
                ext_list.append({
                    "ext": ext,
                    "special": ext in special_files,
                    "filename": special_files.get(ext, None)
                })
            categories.append({
                "name": cat_name,
                "extensions": ext_list
            })
        
        # Build all extensions set for validation
        all_extensions = set()
        for cat in categories:
            for ext in cat['extensions']:
                all_extensions.add(ext['ext'])
        
        # Helper function to create file from extension and filename
        def create_file_from_ext(extension, filename):
            """Create file from extension and filename (internal helper)"""
            # Find extension info
            ext_info = None
            for cat in categories:
                for ext in cat['extensions']:
                    if ext['ext'] == extension:
                        ext_info = ext
                        break
                if ext_info:
                    break
            
            if not ext_info:
                return False, f"Unsupported extension: {extension}"
            
            # Get initial content
            initial_content = self.get_initial_content_for_extension(extension)
            
            # Create temp note for recovery
            from terminal_notes_core import Note
            temp_note = Note(filename, "", created_with="external")
            temp_note.file_extension = extension
            
            print(f"\n  Opening external editor for '{filename}'...")
            
            # Edit with recovery - this already shows message and pauses if no changes
            content = self.external_editor_with_recovery(
                initial_content=initial_content,
                read_only=False,
                file_extension=extension,
                note_uuid=temp_note.id,
                parent_notebook_uuid=notebook.id,
                note_title=filename
            )
            
            # If None returned, message already shown
            if content is None:
                return False, None
            
            # Save the file note
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
            ops.create_file(notebook, filename, content.strip(), extension)
            
            # Clean up recovery file
            recovery_filename = self.recovery_system.get_recovery_filename(
                temp_note.id, filename, True, extension
            )
            recovery_path = self.recovery_system.recovery_dir / recovery_filename
            if recovery_path.exists():
                recovery_path.unlink()
            
            return True, filename
        
        while True:
            self.clear_screen()
            
            # Get display path
            hierarchy = self.manager.get_notebook_hierarchy(notebook.id)
            if hierarchy and len(hierarchy) > 1:
                path_names = [nb.name for nb in hierarchy]
                if len(path_names) <= 3:
                    display_path = "/".join(path_names)
                else:
                    display_path = ".../" + "/".join(path_names[-3:])
            else:
                display_path = notebook.name

            self.print_header(f"Create Specialized File in: {display_path}")

            # Display categories
            print("Select file category or type filename directly:\n")

            # Calculate available width for extensions
            term_width = self.terminal_width
            cat_name_max = max(len(cat['name']) for cat in categories) + 2
            available_width = term_width - cat_name_max - 6

            for idx, cat in enumerate(categories, 1):
                extensions_list = [ext['ext'] for ext in cat['extensions']]
                extensions_str = ", ".join(extensions_list)
                
                if len(extensions_str) > available_width:
                    truncated = extensions_str[:available_width - 3]
                    last_comma = truncated.rfind(',')
                    if last_comma > 0:
                        truncated = truncated[:last_comma]
                    extensions_str = truncated + "..."
                
                print(f"{idx}. {cat['name']:<{cat_name_max-2}} {extensions_str}")

            print()
            print("• Enter category number or type filename directly (e.g., index.html, .bashrc)")
            print()

            user_input = self.get_input("> ", preserve_case=True).strip()
            
            if not user_input:
                return "continue"
            
            # ========== HANDLE CATEGORY NUMBER SELECTION ==========
            if user_input.isdigit():
                cat_idx = int(user_input) - 1
                if cat_idx < 0 or cat_idx >= len(categories):
                    print("Invalid category number.")
                    self.get_input("Press Enter to continue...")
                    continue
                
                category = categories[cat_idx]
                
                # Show extensions in selected category (multi-column)
                while True:
                    self.clear_screen()
                    self.print_header(f"Create Specialized File in: {display_path}")
                    print(f"Category: {category['name']}\n")
                    
                    extensions = category['extensions']
                    total_items = len(extensions)
                    
                    if total_items == 0:
                        print("  No extensions in this category.")
                        self.get_input("Press Enter to continue...")
                        break
                    
                    # Calculate multi-column layout
                    term_width = self.terminal_width
                    max_ext_len = max(len(ext['ext']) for ext in extensions)
                    col_width = max_ext_len + 6
                    cols = max(1, term_width // col_width)
                    rows = (total_items + cols - 1) // cols
                    
                    # Build grid
                    grid = []
                    for r in range(rows):
                        row = []
                        for c in range(cols):
                            idx = r + c * rows
                            if idx < total_items:
                                ext_info = extensions[idx]
                                row.append((idx + 1, ext_info['ext']))
                            else:
                                row.append(None)
                        grid.append(row)
                    
                    # Print grid
                    for row in grid:
                        line = ""
                        for item in row:
                            if item:
                                num, ext = item
                                line += f"{num:>3}. {ext:<{max_ext_len}}  "
                            else:
                                line += " " * (max_ext_len + 6)
                        print(line.rstrip())
                    
                    print()
                    print("  • Enter number to select extension, or type filename directly (e.g., index.html, .bashrc)")
                    print()

                    ext_choice = self.get_input(f"Choose [1-{total_items}] or type filename: ")
                    if not ext_choice:
                        break

                    # Check if input is a number (extension selection)
                    if ext_choice.isdigit():
                        try:
                            ext_idx = int(ext_choice) - 1
                            if ext_idx < 0 or ext_idx >= total_items:
                                raise ValueError
                        except ValueError:
                            print("Invalid choice.")
                            self.get_input("Press Enter to continue...")
                            continue
                        
                        ext_info = extensions[ext_idx]
                        extension = ext_info['ext']
                        special = ext_info['special']
                        fixed_filename = ext_info['filename']
                        
                        # Determine filename
                        if special and fixed_filename:
                            filename = fixed_filename
                            self.clear_screen()
                            self.print_header(f"Create: {extension}")
                            print(f"\n  📄 This file will be saved as: {filename}")
                            print(f"     (filename is fixed for this file type)")
                            print()
                            self.get_input("  Press Enter to continue")
                        else:
                            self.clear_screen()
                            self.print_header(f"Create: {extension}")
                            print(f"\n  Enter filename (without .{extension} extension):")
                            print(f"  Example: my_script → my_script.{extension}")
                            print()
                            name_input = self.get_input("  Filename (Enter to cancel): ")
                            if not name_input:
                                continue
                            name_input = name_input.strip().replace(' ', '_').replace('/', '_')
                            if not name_input:
                                print("  Invalid filename.")
                                self.get_input("Press Enter to continue...")
                                continue
                            filename = f"{name_input}.{extension}"
                        
                        # Create the file
                        success, result = create_file_from_ext(extension, filename)
                        
                        if success:
                            print(f"\n  ✓ File '{filename}' created successfully")
                            
                            # Refresh navigation
                            self.manager.load_all_notebooks(quiet=True)
                            updated_notebook = self.manager.find_notebook_by_id(notebook.id)
                            if updated_notebook:
                                current = self.nav.current()
                                if current and current['screen'] == 'notebook' and current['id'] == notebook.id:
                                    terminal_width, terminal_height = shutil.get_terminal_size()
                                    fresh_total = len(updated_notebook.notes)
                                    fixed_lines = 3 + 1 + 2 + 3
                                    if updated_notebook.subnotebooks:
                                        fixed_lines += 2
                                    available = terminal_height - fixed_lines
                                    items_per_page = int(available * 0.9)
                                    items_per_page = max(1, items_per_page)
                                    total_pages = (fresh_total + items_per_page - 1) // items_per_page if fresh_total > 0 else 1
                                    if total_pages > 0:
                                        self.nav.replace_page(total_pages - 1)
                                    else:
                                        self.nav.replace_page(0)
                            
                            self._just_created = True
                            self.get_input("\nPress Enter to continue...")
                            return "navigate"
                        else:
                            if result is None:
                                break
                            else:
                                print(f"\n  ✗ {result}")
                                self.get_input("Press Enter to continue...")
                                break

                    else:
                        # ========== DIRECT FILENAME INPUT FROM CATEGORY SUBMENU ==========
                        filename = ext_choice.strip()
                        
                        if '.' in filename:
                            parts = filename.rsplit('.', 1)
                            name_part = parts[0]
                            extension = parts[1].lower()
                            
                            if not name_part:
                                print("\n  ✗ Invalid: Filename must have a name before the extension")
                                self.get_input("Press Enter to continue...")
                                continue
                            
                            if extension not in all_extensions:
                                print(f"\n  ✗ Unsupported extension: .{extension}")
                                self.get_input("Press Enter to continue...")
                                continue
                            
                            success, result = create_file_from_ext(extension, filename)
                            
                            if success:
                                print(f"\n  ✓ File '{filename}' created successfully")
                                self.manager.load_all_notebooks(quiet=True)
                                self._just_created = True
                                self.get_input("\nPress Enter to continue...")
                                return "navigate"
                            else:
                                if result is None:
                                    break
                                else:
                                    print(f"\n  ✗ {result}")
                                    self.get_input("Press Enter to continue...")
                                    break
                        else:
                            if filename in special_files:
                                extension = filename
                                fixed_filename = special_files[filename]
                                
                                success, result = create_file_from_ext(extension, fixed_filename)
                                
                                if success:
                                    print(f"\n  ✓ File '{fixed_filename}' created successfully")
                                    self.manager.load_all_notebooks(quiet=True)
                                    self._just_created = True
                                    self.get_input("\nPress Enter to continue...")
                                    return "navigate"
                                else:
                                    if result is None:
                                        break
                                    else:
                                        print(f"\n  ✗ {result}")
                                        self.get_input("Press Enter to continue...")
                                        break
                            else:
                                print(f"\n  ✗ Invalid: '{filename}' is not a valid filename")
                                print("     Regular files: name.extension (e.g., index.html)")
                                print("     Special files: .bashrc or Dockerfile")
                                self.get_input("Press Enter to continue...")
                                continue
                
                continue
            
            # ========== DIRECT FILENAME INPUT AT MAIN MENU LEVEL ==========
            else:
                filename = user_input.strip()
                
                if '.' in filename:
                    parts = filename.rsplit('.', 1)
                    name_part = parts[0]
                    extension = parts[1].lower()
                    
                    if not name_part:
                        print("\n  ✗ Invalid: Filename must have a name before the extension")
                        print("     Example: my_script.py")
                        self.get_input("Press Enter to continue...")
                        continue
                    
                    if extension not in all_extensions:
                        print(f"\n  ✗ Unsupported extension: .{extension}")
                        print("     Use category menu to see supported extensions")
                        self.get_input("Press Enter to continue...")
                        continue
                    
                    success, result = create_file_from_ext(extension, filename)
                    
                    if success:
                        print(f"\n  ✓ File '{filename}' created successfully")
                        self.manager.load_all_notebooks(quiet=True)
                        self._just_created = True
                        self.get_input("\nPress Enter to continue...")
                        return "navigate"
                    else:
                        if result is None:
                            continue
                        else:
                            print(f"\n  ✗ {result}")
                            self.get_input("Press Enter to continue...")
                            continue
                else:
                    if filename in special_files:
                        extension = filename
                        fixed_filename = special_files[filename]
                        
                        success, result = create_file_from_ext(extension, fixed_filename)
                        
                        if success:
                            print(f"\n  ✓ File '{fixed_filename}' created successfully")
                            self.manager.load_all_notebooks(quiet=True)
                            self._just_created = True
                            self.get_input("\nPress Enter to continue...")
                            return "navigate"
                        else:
                            if result is None:
                                continue
                            else:
                                print(f"\n  ✗ {result}")
                                self.get_input("Press Enter to continue...")
                                continue
                    else:
                        print(f"\n  ✗ Invalid: '{filename}' is not a valid filename")
                        print("     Regular files: name.extension (e.g., index.html)")
                        print("     Special files: .bashrc or Dockerfile")
                        self.get_input("Press Enter to continue...")
                        continue
        
        return "continue"
    
    def get_initial_content_for_extension(self, extension):
        """Provide initial content hints based on file type"""
        hints = {
            # Web Core (existing)
            "html": "<!DOCTYPE html>\n<html>\n<head>\n    <title>Document</title>\n</head>\n<body>\n    \n</body>\n</html>",
            "js": "// JavaScript file\n\n",
            "css": "/* CSS file */\n\n",
            "ts": "// TypeScript file\n\n",
            "scss": "// SCSS file\n\n",
            "vue": "<template>\n  <div>\n    \n  </div>\n</template>\n\n<script>\nexport default {\n  \n}\n</script>\n\n<style>\n\n</style>",
            "jsx": "import React from 'react';\n\nconst Component = () => {\n  return (\n    <div>\n      \n    </div>\n  );\n};\n\nexport default Component;",
            "svelte": "<script>\n  // Svelte component\n</script>\n\n<div>\n  \n</div>\n\n<style>\n  \n</style>",
            "astro": "---\n// Astro component props/scripts\n---\n\n<div>\n  \n</div>\n\n<style>\n  \n</style>",
            "mdx": "# MDX Document\n\nimport Component from './component'\n\n<Component>\n  Content here\n</Component>\n\n## Section\n\nRegular markdown content...",
            "graphql": "# GraphQL Schema\n\ntype Query {\n  user(id: ID!): User\n}\n\ntype User {\n  id: ID!\n  name: String!\n  email: String!\n}",
            # 🆕 NEW WEB EXTENSIONS
            "wasm": ";; WebAssembly Text Format\n(module\n  (func (export \"add\") (param $a i32) (param $b i32) (result i32)\n    local.get $a\n    local.get $b\n    i32.add))\n",
            "pug": "//- Pug template\ndoctype html\nhtml\n  head\n    title Document\n  body\n    block content\n",

            # Backend & Systems (existing)
            "py": "# Python file\n\n",
            "php": "<?php\n\n",
            "rb": "# Ruby file\n\n",
            "java": "// Java file\n\n",
            "c": "// C file\n\n",
            "cpp": "// C++ file\n\n",
            "go": "// Go file\n\npackage main\n\nfunc main() {\n    \n}",
            "rs": "// Rust file\n\nfn main() {\n    \n}",
            "pl": "# Perl file\n\n",
            "lua": "-- Lua file\n\n",
            "r": "# R script\n\nlibrary(tidyverse)\n\ndata <- read.csv('file.csv')\nsummary(data)",
            "jl": "# Julia file\n\nusing DataFrames\n\nfunction main()\n    println(\"Hello, Julia!\")\nend",
            # 🆕 NEW BACKEND EXTENSIONS
            "zig": "// Zig file\n\nconst std = @import(\"std\");\n\npub fn main() !void {\n    std.debug.print(\"Hello, world!\\n\", .{});\n}\n",
            "nim": "# Nim file\n\nimport std/strutils\n\necho \"Hello, world!\"\n",
            "crystal": "# Crystal file\n\nputs \"Hello, world!\"\n",
            "d": "// D file\n\nimport std.stdio;\n\nvoid main()\n{\n    writeln(\"Hello, world!\");\n}\n",

            # Mobile & Platforms (existing)
            "swift": "// Swift file\n\n",
            "kt": "// Kotlin file\n\n",

            # DevOps & Automation (existing)
            "sh": "#!/bin/bash\n\n",
            "yml": "---\n# YAML file\n",
            "yaml": "---\n# YAML file\n",
            "toml": "# TOML file\n\n",
            "ini": "; INI file\n\n",
            "cfg": "# Config file\n\n",
            "hcl": "# Terraform/HCL configuration\n\nresource \"aws_instance\" \"example\" {\n  ami           = \"ami-123456\"\n  instance_type = \"t2.micro\"\n  \n  tags = {\n    Name = \"example-instance\"\n  }\n}",
            "tf": "# Terraform configuration\n\nprovider \"aws\" {\n  region = \"us-west-2\"\n}\n\nresource \"aws_s3_bucket\" \"example\" {\n  bucket = \"my-bucket-name\"\n  acl    = \"private\"\n}",
            "justfile": "# Just command runner\n\n# Available commands\nlist:\n    just --list\n\nbuild:\n    cargo build\n\nrun: build\n    ./target/debug/app\n\ntest:\n    cargo test\n\n# Variables\nversion := \"1.0.0\"\n\n# Default command\ndefault:\n    @just --list",
            "nix": "# Nix expression\n\n{ pkgs ? import <nixpkgs> {} }:\n\npkgs.stdenv.mkDerivation {\n  name = \"my-package\";\n  \n  src = ./.;\n  \n  buildInputs = with pkgs; [\n    gcc\n    make\n  ];\n  \n  installPhase = ''\n    mkdir -p $out/bin\n    cp my-program $out/bin/\n  '';\n}",
            # 🆕 NEW DEVOPS EXTENSIONS
            "dockerignore": "# Docker ignore file\n\n# Dependencies\nnode_modules/\n__pycache__/\n*.pyc\n\n# Logs\n*.log\n\n# Environment\n.env\n.env.local\n",
            "env": "# Environment variables\n\n# Database\nDB_HOST=localhost\nDB_PORT=5432\nDB_NAME=mydb\n\n# API\nAPI_KEY=your-api-key-here\nAPI_SECRET=your-secret-here\n",

            # Data & APIs (existing)
            "json": "{\n  \n}",
            "xml": "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n\n",
            "sql": "-- SQL file\n\n",
            "proto": "syntax = \"proto3\";\n\npackage example;\n\nservice UserService {\n  rpc GetUser (GetUserRequest) returns (User) {}\n}\n\nmessage User {\n  string id = 1;\n  string name = 2;\n  string email = 3;\n}\n\nmessage GetUserRequest {\n  string id = 1;\n}",
            # 🆕 NEW DATA EXTENSIONS
            "hjson": "# HJSON (Human JSON)\n\n{\n  # Comments are allowed\n  name: \"example\"\n  count: 42\n  enabled: true\n  items: [\n    \"apple\"\n    \"banana\"\n  ]\n}\n",
            "ron": "// RON (Rusty Object Notation)\n\n(\n    name: \"example\",\n    count: 42,\n    enabled: true,\n    items: [\"apple\", \"banana\"],\n)\n",

            # Documentation (existing)
            "bib": "@article{,\n  \n}",
            "tex": "\\documentclass{article}\n\\begin{document}\n\n\n\\end{document}",
            "md": "# Markdown file\n\n",
            "txt": "",
            "sty": "\\NeedsTeXFormat{LaTeX2e}\n\\ProvidesPackage{}\n\n",
            "cls": "\\NeedsTeXFormat{LaTeX2e}\n\\ProvidesClass{}\n\n",
            "org": "#+TITLE: Org Mode Document\n#+AUTHOR: Your Name\n#+DATE: <2024-01-01>\n\n* Section 1\n  Content here...\n\n** Subsection\n   - List item 1\n   - List item 2\n\n* Section 2\n  More content...",
            "adoc": "= AsciiDoc Document\nAuthor Name\n:doctype: article\n\n== Section 1\n\nContent here...\n\n* List item\n* Another item\n\n== Section 2\n\nMore content...",
            "rst": "===============\nDocument Title\n===============\n\n:Author: Your Name\n:Date: 2024-01-01\n\nSection 1\n=========\n\nContent here...\n\n- List item 1\n- List item 2\n\nSection 2\n=========\n\nMore content...",
            "typ": "#set page(width: auto, height: auto)\n#set text(font: \"Times New Roman\", size: 11pt)\n\n= Document Title\n\n== Section 1\n\nContent here...\n\n- List item 1\n- List item 2\n\n== Section 2\n\nMore content...\n\n```\nCode block\n```",
            # 🆕 NEW DOCUMENTATION EXTENSIONS
            "wiki": "= Wiki Page =\n\n== Section 1 ==\nContent here...\n\n=== Subsection ===\nMore content...\n\n* Bullet point 1\n* Bullet point 2\n",

            # Shell Configs (existing)
            "bashrc": "# ~/.bashrc\n\n# Aliases\nalias ll='ls -la'\nalias gs='git status'\n\n# PATH\nexport PATH=$PATH:$HOME/.local/bin\n\n# Prompt\nPS1='\\[\\e[32m\\]\\u@\\h\\[\\e[0m\\]:\\[\\e[34m\\]\\w\\[\\e[0m\\]\\$ '",
            "zshrc": "# ~/.zshrc\n\n# Oh My Zsh\nplugins=(git docker kubectl)\n\n# Aliases\nalias ll='ls -la'\n\n# Theme\nZSH_THEME=\"robbyrussell\"",
            "profile": "# ~/.profile\n\n# PATH\nexport PATH=\"$HOME/.local/bin:$PATH\"\n\n# Default editor\nexport EDITOR=vim",
            "aliases": "# Custom aliases\n\nalias ll='ls -la'\nalias la='ls -A'\nalias l='ls -CF'\n\n# Git aliases\nalias gs='git status'\nalias ga='git add'\nalias gc='git commit'",
            "bash_profile": "# ~/.bash_profile\n\n# Source .bashrc if it exists\nif [ -f ~/.bashrc ]; then\n    source ~/.bashrc\nfi\n\n# PATH\nexport PATH=\"$HOME/bin:$PATH\"",
            "zprofile": "# ~/.zprofile\n\n# Environment variables for Zsh login shells\n\nexport EDITOR=vim\nexport VISUAL=vim",
            # 🆕 NEW SHELL CONFIGS
            "screenrc": "# ~/.screenrc\n\n# Startup message\nstartup_message off\n\n# Hardstatus\ndefhardstatus alwayslastline\nhardstatus string '%{= kG}%-w%{= kW}%n %t%{-}%+w %= %{= kW}%Y-%m-%d %c'\n\n# Key bindings\nbindkey -k k1 screen 1\nbindkey -k k2 screen 2\n",
            "wgetrc": "# ~/.wgetrc\n\n# Set default timeout\ntimeout = 30\n\n# Don't check certificate\ncheck_certificate = off\n\n# Set user agent\nuser_agent = \"Mozilla/5.0\"\n",
            "curlrc": "# ~/.curlrc\n\n# Default options\n--progress-bar\n--remote-time\n--retry 3\n--retry-delay 1\n--connect-timeout 30\n--max-time 300\n",
            "fish": "# config.fish\n\n# Aliases\nalias ll='ls -la'\nalias gs='git status'\n\n# PATH\nset -gx PATH $HOME/.local/bin $PATH\n\n# Prompt\nfunction fish_prompt\n    echo -n (whoami)@(hostname) (pwd) '> '\nend\n",

            # Editor Configs (existing)
            "vimrc": "\" ~/.vimrc\n\nset number\nset relativenumber\nset tabstop=4\nset shiftwidth=4\nset expandtab\nsyntax on\n\n\" Mappings\nnnoremap <C-s> :w<CR>\n\n\" Plugins (if using vim-plug)\ncall plug#begin()\n\" Plug 'preservim/nerdtree'\ncall plug#end()",
            "lua": "-- init.lua for Neovim\n\n-- Options\nvim.opt.number = true\nvim.opt.relativenumber = true\nvim.opt.tabstop = 4\nvim.opt.shiftwidth = 4\nvim.opt.expandtab = true\n\n-- Keymaps\nvim.keymap.set('n', '<C-s>', ':w<CR>')",
            "editorconfig": "# EditorConfig is awesome: https://EditorConfig.org\n\nroot = true\n\n[*]\nindent_style = space\nindent_size = 4\nend_of_line = lf\ncharset = utf-8\ntrim_trailing_whitespace = true\ninsert_final_newline = true\n\n[*.{js,py}]\nindent_size = 4",

            # Git Configs (existing)
            "gitconfig": "[user]\n\tname = Your Name\n\temail = email@example.com\n\n[alias]\n\tco = checkout\n\tbr = branch\n\tci = commit\n\tst = status\n\n[core]\n\teditor = vim\n\n[color]\n\tui = auto",
            "gitignore": "# OS files\n.DS_Store\nThumbs.db\n*.swp\n*.swo\n*~\n\n# IDE\n.vscode/\n.idea/\n\n# Dependencies\nnode_modules/\n__pycache__/\n*.pyc\n\n# Environment\n.env\n.env.local\n\n# Build outputs\ndist/\nbuild/\n*.log",
            "gitattributes": "# Auto detect text files\n* text=auto\n\n# Source code\n*.js text eol=lf\n*.py text eol=lf\n*.md text eol=lf\n\n# Binaries\n*.png binary\n*.jpg binary\n*.gz binary",
            # 🆕 NEW GIT CONFIGS
            "gitmessage": "# Commit message template\n\n# <type>(<scope>): <subject>\n# Example: feat(api): add user authentication\n\n\n# Body (optional): detailed explanation\n\n\n# Footer (optional): issue references\n# Closes #123\n",
            "mailmap": "# .mailmap file\n\n# Format: Proper Name <proper@email> <commit-name> <commit-email>\n# Example:\n# John Doe <john@example.com> <johndoe> <johndoe@old.com>\n",

            # Language/Runtime (existing)
            "npmrc": "# npm config file\nregistry=https://registry.npmjs.org/\nsave-exact=true\ninit-author-name=Your Name\ninit-license=MIT",
            "yarnrc": "# Yarn config file\n# https://yarnpkg.com/configuration/yarnrc\n\nnpmRegistryServer: \"https://registry.npmjs.org\"\n\nyarnPath: .yarn/releases/yarn-berry.cjs",
            "gemrc": "---\n:verbose: true\n:update_sources: true\n:backtrace: false\n:bulk_threshold: 1000\ninstall: --no-rdoc --no-ri --env-shebang\nupdate: --no-rdoc --no-ri --env-shebang",
            "Rprofile": ".First <- function() {\n  cat(\"\\nWelcome to R!\\n\")\n  options(repos = c(CRAN = \"https://cloud.r-project.org\"))\n}\n\n.Last <- function() {\n  cat(\"\\nGoodbye!\\n\")\n}",
            "irbrc": "# ~/.irbrc\n\nrequire 'irb/completion'\n\nIRB.conf[:AUTO_INDENT] = true\nIRB.conf[:USE_READLINE] = true\nIRB.conf[:SAVE_HISTORY] = 1000\nIRB.conf[:HISTORY_FILE] = \"~/.irb_history\"\n\n# Prompt\nIRB.conf[:PROMPT][:CUSTOM] = {\n  :PROMPT_I => \"> \",\n  :PROMPT_S => \"%l> \",\n  :PROMPT_C => \"?> \",\n  :RETURN => \"=> %s\\n\"\n}\nIRB.conf[:PROMPT_MODE] = :CUSTOM",

            # Application Configs (existing)
            "tmux.conf": "# ~/.tmux.conf\n\n# Use C-a as prefix\nset -g prefix C-a\nunbind C-b\nbind C-a send-prefix\n\n# Split panes\nbind | split-window -h\nbind - split-window -v\n\n# Reload config\nbind r source-file ~/.tmux.conf\n\n# Mouse mode\nset -g mouse on\n\n# Colors\nset -g default-terminal \"screen-256color\"",
            "inputrc": "# ~/.inputrc\n\n# Case-insensitive tab completion\nset completion-ignore-case on\n\n# Show all matches at once\nset show-all-if-ambiguous on\n\n# Vi mode\nset editing-mode vi\n\n# History\nset history-size 1000",
            "Xresources": "! ~/.Xresources\n\nXft.dpi: 96\nXft.antialias: true\nXft.hinting: true\nXft.hintstyle: hintslight\nXft.rgba: rgb\n\n! Urxvt settings\nURxvt*font: xft:Monospace:pixelsize=12\nURxvt*scrollBar: false\nURxvt*transparent: false",

            # Container/CI (existing)
            "Dockerfile": "# Dockerfile\nFROM ubuntu:22.04\n\nRUN apt-get update && apt-get install -y \\\n    python3 \\\n    python3-pip \\\n    && rm -rf /var/lib/apt/lists/*\n\nWORKDIR /app\n\nCOPY requirements.txt .\nRUN pip3 install -r requirements.txt\n\nCOPY . .\n\nCMD [\"python3\", \"app.py\"]",
            "Jenkinsfile": "pipeline {\n    agent any\n    \n    environment {\n        APP_NAME = 'my-app'\n    }\n    \n    stages {\n        stage('Checkout') {\n            steps {\n                checkout scm\n            }\n        }\n        stage('Build') {\n            steps {\n                echo \"Building ${APP_NAME}...\"\n                sh 'make build'\n            }\n        }\n        stage('Test') {\n            steps {\n                sh 'make test'\n            }\n        }\n        stage('Deploy') {\n            steps {\n                echo \"Deploying ${APP_NAME}...\"\n                sh 'make deploy'\n            }\n        }\n    }\n    \n    post {\n        always {\n            cleanWs()\n        }\n    }\n}",
            "service": "[Unit]\nDescription=My Custom Service\nAfter=network.target\n\n[Service]\nType=simple\nUser=myuser\nGroup=mygroup\nWorkingDirectory=/opt/myapp\nExecStart=/usr/bin/python3 /opt/myapp/main.py\nRestart=on-failure\nRestartSec=10\n\n[Install]\nWantedBy=multi-user.target",
            "timer": "[Unit]\nDescription=Run my service daily\nRequires=myapp.service\n\n[Timer]\nOnCalendar=daily\nPersistent=true\n\n[Install]\nWantedBy=timers.target",
            # 🆕 NEW CI/CD EXTENSIONS
            "gitlab-ci.yml": "# .gitlab-ci.yml\n\nstages:\n  - build\n  - test\n  - deploy\n\nvariables:\n  APP_NAME: myapp\n\nbefore_script:\n  - apt-get update -qq\n\nbuild:\n  stage: build\n  script:\n    - make build\n  artifacts:\n    paths:\n      - dist/\n\ntest:\n  stage: test\n  script:\n    - make test\n\ndeploy:\n  stage: deploy\n  script:\n    - make deploy\n  only:\n    - main\n",
            "ps1": "# PowerShell script\n\nWrite-Host \"Hello, World!\"\n\n# Variables\n$name = \"World\"\nWrite-Host \"Hello, $name!\"\n\n# Function\nfunction Get-Greeting {\n    param([string]$Name)\n    return \"Hello, $Name!\"\n}\n\n# Condition\nif ($true) {\n    Write-Host \"Condition is true\"\n}\n\n# Loop\nforeach ($i in 1..5) {\n    Write-Host \"Number: $i\"\n}\n",
            "bat": "@echo off\nREM Batch file\n\necho Hello, World!\n\nREM Variables\nset NAME=World\necho Hello, %NAME%!\n\nREM Condition\nif \"%NAME%\"==\"World\" (\n    echo Condition is true\n)\n\nREM Loop\nfor /l %%i in (1,1,5) do (\n    echo Number: %%i\n)\n",
            "cmake": "# CMakeLists.txt\n\ncmake_minimum_required(VERSION 3.10)\nproject(MyProject)\n\n# Set C++ standard\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\n\n# Add executable\nadd_executable(myapp main.cpp)\n\n# Find packages\nfind_package(OpenCV REQUIRED)\n\n# Link libraries\ntarget_link_libraries(myapp ${OpenCV_LIBS})\n\n# Set output directory\nset_target_properties(myapp PROPERTIES\n    RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin\n)\n",
        }
        return hints.get(extension, "")

    def _update_notebook_in_hierarchy(self, root_notebook, target_id, updated_notebook):
        """Recursively find and update a notebook in the hierarchy"""
        if root_notebook.id == target_id:
            return updated_notebook
    
        for i, sub in enumerate(root_notebook.subnotebooks):
            if sub.id == target_id:
                root_notebook.subnotebooks[i] = updated_notebook
                return root_notebook
        
            # Recursively search deeper
            result = self._update_notebook_in_hierarchy(sub, target_id, updated_notebook)
            if result:
                return root_notebook
    
        return None
    
    def create_subnotebook(self, parent_notebook):
        self.clear_screen()
        self.print_header(f"Create Sub-notebook in: {parent_notebook.name}")

        name = self.get_input("Sub-notebook name: ")
        if not name:
            return

        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)

        # Create subnotebook
        subnotebook = ops.create_subnotebook(parent_notebook, name)

        # 🟢 FIX: Ensure parent_notebook is updated in memory
        # Find the root notebook
        root = self.manager._find_root_notebook(parent_notebook)
    
        # Update the root in manager's notebook list
        for i, nb in enumerate(self.manager.notebooks):
            if nb.id == root.id:
                self.manager.notebooks[i] = root
                break
    
        # Also update the parent notebook if it's not the root
        if parent_notebook.id != root.id:
            # Find and update parent in the hierarchy
            for i, root_nb in enumerate(self.manager.notebooks):
                if root_nb.id == root.id:
                    # Recursively update the parent in the hierarchy
                    updated_root = self._update_notebook_in_hierarchy(root_nb, parent_notebook.id, parent_notebook)
                    if updated_root:
                        self.manager.notebooks[i] = updated_root
                        break

        print(f"\n✓ Sub-notebook '{name}' created successfully")
        self._just_created = True
        return "navigate"
    
    def rename_subnotebook(self, subnotebook, parent_notebook):
        """Rename a subnotebook"""
        self.clear_screen()
        self.print_header("Rename Sub-notebook")

        old_name = subnotebook.name
        print(f"Current name: {old_name}")
        print()
    
        new_name = self.get_input("New name: ")
        if not new_name or not new_name.strip():
            print("Name cannot be empty.")
            self.get_input("Press Enter to continue...")
            return
    
        new_name = new_name.strip()
        
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        ops.rename_subnotebook(subnotebook, parent_notebook, new_name)
    
        print(f"\n✓ Subnotebook renamed to '{new_name}'")
        self._just_created = True
        self.get_input("Press Enter to continue...")
    
    def count_total_files(self):
        """Count total file notes across all notebooks"""
        file_count = 0

        def count_files_in_notebook(notebook):
            nonlocal file_count
            for note in notebook.notes:
                if note.is_file_note:
                    file_count += 1
            for sub_nb in notebook.subnotebooks:
                count_files_in_notebook(sub_nb)

        for notebook in self.manager.notebooks:
            count_files_in_notebook(notebook)

        return file_count

    def export_file_note(self, note):
        """Export file note - using ops"""
        if not note.is_file_note:
            print("This is not a file note.")
            self.get_input("Press Enter to continue...")
            return

        while True:
            self.clear_screen()
            self.print_header(f"Export File: {note.title}")

            print("Enter export DIRECTORY (filename will be automatic):")
            print("Examples:")
            print("  /home/user/projects/")
            print("  ./exports/")
            print("  ../backup/")

            if self.export_history:
                print("\nRecent export paths:")
                for i, path in enumerate(self.export_history, 1):
                    print(f"[{i}] {path}")
            print()

            print(f"File will be saved as: {note.title}")
            print()

            if self.export_history:
                prompt = "Enter directory or number [1-3]: "
            else:
                prompt = "Export directory: "

            export_dir = self.get_input(prompt)

            if not export_dir:
                return

            # Handle number selection from history
            if export_dir.isdigit() and self.export_history:
                idx = int(export_dir) - 1
                if 0 <= idx < len(self.export_history):
                    export_dir = self.export_history[idx]
                    print(f"Using: {export_dir}")
                else:
                    print("Invalid history number.")
                    self.get_input("Press Enter to continue...")
                    continue

            # 🟢 Use ops to export
            from notebook_operations import NotebookOperations
            ops = NotebookOperations(self.manager)
            success = ops.export_file(note, export_dir)

            if success:
                print(f"File exported successfully!")
                self._update_export_history(export_dir)
            else:
                print(f"Export failed")

            self.get_input("Press Enter to continue...")
            break

    def _update_export_history(self, export_dir):
        """Update export history with new directory"""
        # Remove if already exists (to avoid duplicates)
        if export_dir in self.export_history:
            self.export_history.remove(export_dir)

        # Add to front (most recent)
        self.export_history.insert(0, export_dir)

        # Trim to limit
        if len(self.export_history) > self.export_history_limit:
            self.export_history = self.export_history[: self.export_history_limit]
    
                                                    
    def main_loop(self):
        # Initialize terminal size tracking
        self.clear_screen()

        self.update_terminal_size()
        last_terminal_size = (self.terminal_width, self.terminal_height)

        while True:
            # Check if terminal was resized
            current_width, current_height = self.update_terminal_size()
            if (current_width, current_height) != last_terminal_size:
                last_terminal_size = (current_width, current_height)

            current = self.nav.current()
            current_screen = current["screen"]
    
            if current_screen == "home":
                # 🟢 CLEAR SEARCH CONTEXT WHEN GOING HOME
                self.clear_screen()
                self.comprehensive_search._search_notebook_context = None
                self.show_home_screen()
                prompt = "> "
            elif current_screen == "list":
                self.show_notebook_list_screen()
                prompt = "> "
            elif current_screen == "notebook":
                self.show_notebook_view_screen()
                prompt = "> "
            elif current_screen == "subnotebooks":
                self.show_subnotebooks_view_screen()
                prompt = "> "
            elif current_screen == "note":
                self.show_note_view_screen()
                prompt = "> "
            # 🟢 SEARCH SCREEN CASE
            # In main_loop, where you handle search screen
            elif current_screen == "search":
                # This should no longer happen - search now uses its own UI
                # But keep for backward compatibility
                self.nav.pop()
                continue

    
            command = self.get_input(prompt)
            try:
                result = self.process_command(command)
            except Exception:
                print("An unexpected error occurred:")
                traceback.print_exc()
                self.get_input("Press Enter to continue...")
                continue
    
            if result == "exit":
                self.clear_screen()
                break
            elif result == "navigate":
                # 🟢 FIX: Check if we should skip reload
                if hasattr(self.manager, '_skip_next_reload'):
                    # Clear the flag without reloading
                    delattr(self.manager, '_skip_next_reload')
                elif current_screen == "home":
                    # Only reload if we're going home and no flag is set
                    self.manager.load_all_notebooks()
                continue
            
if __name__ == "__main__":
    import traceback

    try:
        app = TerminalNotes()
        app.main_loop()
    except Exception:
        print("\n--- An unexpected error occurred ---")
        traceback.print_exc()
        input("\nPress Enter to exit...")