#!/usr/bin/env python3
import os
import json
import time
import sys
import threading
import select
import subprocess
import re
import signal
import platform
from datetime import datetime
from pathlib import Path

class ClipboardManager:
    def __init__(self, data_file="clipboard_history.json"):
        # Get the directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Store data in the same directory as the script
        self.data_file = os.path.join(script_dir, data_file)
        
        self.last_content = ""
        self.monitoring = False
        self.history_update_flag = True
        self.should_quit = False
        self.history_length = 15
        self.expanded_item = None
        self.expanded_content = ""
        self.expanded_timestamp = ""
        self.monitor_thread = None
        self.pause_monitoring = False
        
        # Detect platform and set clipboard commands
        self.system = platform.system()
        self._setup_clipboard_commands()
        
        # Initialize data
        self.data = self._load_data()

    def _setup_clipboard_commands(self):
        """Setup clipboard commands based on operating system"""
        if self.system == "Linux":
            self.get_cmd = ['xclip', '-o', '-selection', 'clipboard']
            self.set_cmd = ['xclip', '-i', '-selection', 'clipboard']
        elif self.system == "Darwin":  # macOS
            self.get_cmd = ['pbpaste']
            self.set_cmd = ['pbcopy']
        elif self.system == "Windows":
            self.get_cmd = ['powershell', '-command', 'Get-Clipboard']
            self.set_cmd = ['powershell', '-command', 'Set-Clipboard']
        else:
            print(f"Unsupported system: {self.system}")
            sys.exit(1)

    def _handle_interrupt(self, signum, frame):
        """Handle Ctrl+C gracefully"""
        print()
        self.history_update_flag = True

    def get_clipboard(self):
        """Get clipboard content using system commands"""
        if self.should_quit:
            return ""
            
        try:
            result = subprocess.run(
                self.get_cmd,
                capture_output=True, 
                text=True,
                timeout=3
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except:
            return ""

    def set_clipboard(self, content):
        """Set clipboard content using system commands"""
        if self.should_quit or not content:
            return False
            
        try:
            self.pause_monitoring = True
            
            process = subprocess.Popen(
                self.set_cmd,
                stdin=subprocess.PIPE,
                text=True
            )
            process.communicate(input=content, timeout=2)
            process.wait(timeout=1)
            
            success = process.returncode == 0
            if success:
                self.last_content = content
                
            time.sleep(0.3)
            self.pause_monitoring = False
            
            return success
        except:
            self.pause_monitoring = False
            return False

    def _normalize_content(self, content):
        """Normalize content to avoid duplicates"""
        if not content:
            return content
        
        normalized = content.strip()
        normalized = normalized.replace('\r\n', '\n').replace('\r', '\n')
        normalized = re.sub(r'\n\s*\n', '\n\n', normalized)
        
        return normalized

    def _load_data(self):
        """Load data from JSON file"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"items": [], "next_id": 1}
        return {"items": [], "next_id": 1}

    def _save_data(self):
        """Save data to JSON file"""
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except:
            pass

    def save_to_history(self, content):
        """Save clipboard content to history"""
        if not content:
            return False

        normalized_content = self._normalize_content(content)
        
        if len(normalized_content.strip()) == 0:
            return False

        if len(content) > 100000:
            return False

        # Check for recent duplicates
        now = time.time()
        for item in self.data["items"]:
            if item["content"] == normalized_content:
                if now - item["timestamp"] < 30:
                    return False

        # Create new item
        new_item = {
            "id": self.data["next_id"],
            "content": normalized_content,
            "timestamp": now,
            "pinned": False,
            "length": len(normalized_content)
        }
        
        self.data["items"].append(new_item)
        self.data["next_id"] += 1
        self._save_data()
        self.history_update_flag = True
        
        return True

    def get_history(self, limit=None):
        """Retrieve clipboard history with pinned items on top"""
        if limit is None:
            limit = self.history_length

        # Sort: pinned items first (by timestamp desc), then unpinned (by timestamp desc)
        sorted_items = sorted(
            self.data["items"],
            key=lambda x: (not x["pinned"], -x["timestamp"])
        )
        
        # Return as list of tuples for compatibility
        result = []
        for item in sorted_items[:limit]:
            dt = datetime.fromtimestamp(item["timestamp"])
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            result.append((
                item["id"],
                item["content"],
                timestamp_str,
                item["length"]
            ))
        
        return result

    def clear_all(self):
        """Clear ALL clipboard history"""
        try:
            current_clipboard = self.get_clipboard()
            self.pause_monitoring = True
            time.sleep(0.5)

            self.monitoring = False
            if self.monitor_thread:
                self.monitor_thread.join(timeout=1)

            self.data["items"] = []
            self.data["next_id"] = 1
            self._save_data()

            self.last_content = current_clipboard
            self.history_update_flag = True
            self.expanded_item = None
            self.expanded_content = ""

            self.monitoring = True
            self.pause_monitoring = False
            self.monitor_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
            self.monitor_thread.start()

            return True
        except:
            self.monitoring = True
            self.pause_monitoring = False
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.monitor_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
                self.monitor_thread.start()
            return False

    def delete_entry(self, entry_id):
        """Delete a specific entry"""
        self.data["items"] = [item for item in self.data["items"] if item["id"] != entry_id]
        self._save_data()
        self.history_update_flag = True
        if self.expanded_item == entry_id:
            self.expanded_item = None
            self.expanded_content = ""

    def move_to_top(self, entry_id):
        """Move an entry to the top of history (update timestamp)"""
        for item in self.data["items"]:
            if item["id"] == entry_id:
                item["timestamp"] = time.time()
                break
        self._save_data()
        self.history_update_flag = True

    def toggle_pin(self, entry_id):
        """Toggle pin status of an entry"""
        for item in self.data["items"]:
            if item["id"] == entry_id:
                item["pinned"] = not item["pinned"]
                break
        self._save_data()
        self.history_update_flag = True

    def start_monitoring(self):
        """Start clipboard monitoring"""
        if not self.monitoring:
            self.monitoring = True
            self.last_content = self.get_clipboard()
            self.monitor_thread = threading.Thread(target=self._monitor_clipboard, daemon=True)
            self.monitor_thread.start()

    def _monitor_clipboard(self):
        """Background thread to monitor clipboard changes"""
        time.sleep(1)
        
        last_detected_time = 0
        debounce_delay = 0.8
        
        while self.monitoring and not self.should_quit:
            try:
                if not self.pause_monitoring:
                    current_time = time.time()
                    current_content = self.get_clipboard()
                    
                    if (current_content and 
                        current_content != self.last_content and
                        (current_time - last_detected_time) > debounce_delay):
                        
                        if self.save_to_history(current_content):
                            self.last_content = current_content
                            last_detected_time = current_time
                            
                time.sleep(0.5)
            except:
                time.sleep(1)

    def display_minimal_dashboard(self):
        """Minimal dashboard"""
        self.start_monitoring()
        self._render_minimal_dashboard()

        while not self.should_quit:
            if self.history_update_flag:
                self._render_minimal_dashboard()
                self.history_update_flag = False

            try:
                # Check for input with timeout
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    try:
                        command = sys.stdin.readline().strip().lower()
                        if command == 'q':
                            self.should_quit = True
                            break
                        elif command:
                            self._handle_command(command)
                    except (KeyboardInterrupt, EOFError):
                        print()
                        self.should_quit = True
                        break
            except:
                pass

        self._cleanup()

    def _cleanup(self):
        """Cleanup"""
        print("\nCleaning up...")
        self.monitoring = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1)
        print("Goodbye!")

    def _render_minimal_dashboard(self):
        """Render the minimal dashboard with width adaptation"""
        # Clear screen (works on all platforms)
        os.system('cls' if os.name == 'nt' else 'clear')
    
        # Get terminal width
        try:
            terminal_width = os.get_terminal_size().columns
        except:
            terminal_width = 80  # Default fallback
    
        # Adjust preview length based on terminal width (reserve space for numbers, indicators)
        preview_length = max(30, terminal_width - 20)  # Minimum 30 chars, adjust based on width

        if self.expanded_item:
            print("CLIPBOARD HISTORY - EXPANDED VIEW")
            print("-" * min(terminal_width, 40))
            print(f"[{self.expanded_timestamp}]")
            print()
        
            lines = self.expanded_content.split('\n')
            for i in range(min(4, len(lines))):
                line = lines[i]
                # Truncate long lines to terminal width
                if len(line) > terminal_width - 4:
                    line = line[:terminal_width - 7] + "..."
                print(f"  {line}")
        
            if len(lines) > 4:
                print(f"  ... and {len(lines) - 4} more lines")
        
            print()
            print("-" * min(terminal_width, 40))
            print("Commands: e close | c copy | q quit")
            print("> ", end='', flush=True)
        else:
            history = self.get_history()

            #print("CLIPBOARD HISTORY")
            #print("-" * min(terminal_width, 40))

            if not history:
                print("No clipboard history yet.")
                print("Copy some text to get started!")
            else:
                # Get full items to check pin status
                sorted_items = sorted(
                    self.data["items"],
                    key=lambda x: (not x["pinned"], -x["timestamp"])
                )[:self.history_length]
            
                for i, item in enumerate(sorted_items, 1):
                    content = item["content"]
                
                    # Clean preview: replace newlines with space for single line display
                    preview = content.replace('\n', ' ').replace('\r', ' ')
                    # Remove multiple spaces
                    preview = ' '.join(preview.split())
                
                    # Truncate based on terminal width
                    if len(preview) > preview_length:
                        preview = preview[:preview_length] + "..."
                
                    # Indicators
                    pin_indicator = "📌" if item["pinned"] else "  "
                    expand_indicator = "+" if len(content) > 80 or '\n' in content else " "
                
                    # Format with fixed width for alignment
                    print(f"{i:2d}. {preview:<{preview_length}} [{expand_indicator}]{pin_indicator}")

            print("-" * min(terminal_width, 40))
            cmd_text = "Commands: [1-{}] copy | d[1-{}] delete | p[1-{}] pin/unpin | e[1-{}] expand | c clear | l length | q quit".format(
                len(history), len(history), len(history), len(history))
        
            # Wrap command text if too long
            if len(cmd_text) > terminal_width:
                # Show abbreviated commands
                cmd_text = "[1-{}]cp d[1-{}]del p[1-{}]pin e[1-{}]exp c l q".format(
                    len(history), len(history), len(history), len(history))
        
            print(cmd_text)
            print("Showing: {}/{} items > ".format(len(history), self.history_length), end='', flush=True)

    def _handle_command(self, command):
        """Handle all commands"""
        command = command.strip().lower()

        if self.expanded_item:
            if command == 'e':
                self.expanded_item = None
                self.expanded_content = ""
                self.expanded_timestamp = ""
                self.history_update_flag = True
                return

            elif command == 'c':
                if self.set_clipboard(self.expanded_content):
                    print("Copied expanded content!")
                else:
                    print("Failed to copy!")
                time.sleep(0.5)
                self.history_update_flag = True
                return

        elif command == 'c':
            sorted_items = sorted(
                self.data["items"],
                key=lambda x: (not x["pinned"], -x["timestamp"])
            )[:self.history_length]
            
            if not sorted_items:
                print("Already empty!")
                time.sleep(0.5)
                self.history_update_flag = True
                return

            print("Clear ALL history? (y/N): ", end='', flush=True)
            try:
                response = input().strip().lower()
                if response == 'y':
                    if self.clear_all():
                        print("Cleared all history!")
                    else:
                        print("Failed to clear!")
                    time.sleep(0.5)
                self.history_update_flag = True
            except:
                print("\nClear cancelled!")
                time.sleep(0.5)
                self.history_update_flag = True

        elif command == 'l':
            print(f"Current history length: {self.history_length}")
            print("Set new length (5-50): ", end='', flush=True)
            try:
                new_length = input().strip()
                if new_length.isdigit():
                    new_length = int(new_length)
                    if 5 <= new_length <= 50:
                        self.history_length = new_length
                        print(f"History length set to {new_length}!")
                    else:
                        print("Please enter a number between 5 and 50")
                else:
                    print("Please enter a valid number")
                time.sleep(1)
                self.history_update_flag = True
            except:
                print("\nLength change cancelled!")
                time.sleep(0.5)
                self.history_update_flag = True

        elif command.startswith('p') and command[1:].isdigit() and not self.expanded_item:
            # Pin/unpin item
            idx = int(command[1:]) - 1
            sorted_items = sorted(
                self.data["items"],
                key=lambda x: (not x["pinned"], -x["timestamp"])
            )[:self.history_length]
            
            if 0 <= idx < len(sorted_items):
                item = sorted_items[idx]
                self.toggle_pin(item["id"])
                print(f"{'Pinned' if item['pinned'] else 'Unpinned'} item {command[1:]}!")
                time.sleep(0.5)
            else:
                print("Invalid number!")
                time.sleep(0.5)
            self.history_update_flag = True

        elif command.startswith('e') and command[1:].isdigit() and not self.expanded_item:
            # Expand item
            idx = int(command[1:]) - 1
            sorted_items = sorted(
                self.data["items"],
                key=lambda x: (not x["pinned"], -x["timestamp"])
            )[:self.history_length]
            
            if 0 <= idx < len(sorted_items):
                item = sorted_items[idx]
                self.expanded_item = item["id"]
                self.expanded_content = item["content"]
                dt = datetime.fromtimestamp(item["timestamp"])
                self.expanded_timestamp = dt.strftime('%H:%M:%S')
                print(f"Expanded item {command[1:]}")
                time.sleep(0.3)
            else:
                print("Invalid number!")
                time.sleep(0.5)
            self.history_update_flag = True

        elif command.isdigit():
            # Copy item and move to top
            idx = int(command) - 1
            sorted_items = sorted(
                self.data["items"],
                key=lambda x: (not x["pinned"], -x["timestamp"])
            )[:self.history_length]
            
            if 0 <= idx < len(sorted_items):
                item = sorted_items[idx]
                if self.set_clipboard(item["content"]):
                    # Only move to top if not pinned
                    if not item["pinned"]:
                        self.move_to_top(item["id"])
                    print(f"Copied item {command}!")
                else:
                    print(f"Failed to copy item {command}!")
                time.sleep(0.5)
            else:
                print("Invalid number!")
                time.sleep(0.5)
            self.history_update_flag = True

        elif command.startswith('d') and command[1:].isdigit():
            # Delete item
            idx = int(command[1:]) - 1
            sorted_items = sorted(
                self.data["items"],
                key=lambda x: (not x["pinned"], -x["timestamp"])
            )[:self.history_length]
            
            if 0 <= idx < len(sorted_items):
                self.delete_entry(sorted_items[idx]["id"])
                print(f"Deleted item {command[1:]}!")
                time.sleep(0.5)
            else:
                print("Invalid number!")
                time.sleep(0.5)
            self.history_update_flag = True

        else:
            print("Unknown command!")
            time.sleep(0.5)
            self.history_update_flag = True

def main():
    manager = ClipboardManager()

    print("Starting Clipboard Manager...")
    print(f"Data stored in: {manager.data_file}")
    print(f"System detected: {manager.system}")
    print("Pinned items (📌) stay at the top!")
    time.sleep(1)

    try:
        manager.display_minimal_dashboard()
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == "__main__":
    main()