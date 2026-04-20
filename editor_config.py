#!/usr/bin/env python3
"""
Centralized editor configuration with forced autosave settings.
No external config files needed - everything is defined here.
"""
import sys
sys.dont_write_bytecode = True
import os
import json

class EditorConfig:
    """Central repository for all editor configurations"""
    
    # NeoVim autosave commands
    NVIM_AUTOSAVE = [
        "set autowriteall",
        "set updatetime=30000",
        "autocmd CursorHold * silent! write",
        "autocmd CursorHoldI * silent! write",
        "autocmd FocusLost * silent! write",
        "echo 'NeoVim autosave enabled - saving every 30 seconds'"
    ]
    
    # Vim autosave commands
    VIM_AUTOSAVE = [
        "set autowriteall",
        "autocmd CursorHold * silent! write",
        "autocmd FocusLost * silent! write",
        "echo 'Vim autosave enabled'"
    ]
    
    # Emacs autosave commands
    EMACS_AUTOSAVE = [
        "(setq auto-save-visited-mode t)",
        "(auto-save-visited-mode 1)",
        "(setq auto-save-interval 300)",
        "(setq auto-save-visited-interval 30)",
        "(message \"Emacs autosave enabled - saving every 30 seconds\")"
    ]
    
    # Micro forced autosave (creates ~/.config/micro/settings.json if needed)
    MICRO_AUTOSAVE = """
{
    "autosave": true,
    "autosaveinterval": 30,
    "rmtrailingws": true,
    "savecursor": true,
    "saveundo": true
}
"""
    
    # Helix forced autosave (creates ~/.config/helix/config.toml if needed)
    HELIX_AUTOSAVE = """
# Helix forced autosave configuration
# This will be written to ~/.config/helix/config.toml if needed
theme = "default"

[editor]
line-number = "relative"
mouse = false
auto-save = true
auto-save.focus-lost = true
auto-save.after-delay = { secs = 30, nanos = 0 }

[editor.statusline]
left = ["mode", "spinner", "file-name"]
right = ["diagnostics", "selections", "position", "file-encoding"]
"""
    
    # Kate (KDE Advanced Text Editor) autosave
    KATE_AUTOSAVE = """
# Kate autosave configuration
# Written to ~/.config/katerc
[General]
Auto Save Interval=30
Auto Save on Focus Out=true
Backup on Save=local
"""
    
    # Geany forced autosave
    GEANY_AUTOSAVE = """
# Geany autosave configuration
# Written to ~/.config/geany/geany.conf
[geany]
autosave=30
autosave_interval=30
beep_on_errors=false
tab_order_ltr=true
"""
    
    # Leafpad forced autosave (simple GTK editor)
    LEAFPAD_AUTOSAVE = """
# Leafpad is simple - we'll rely on recovery thread
# No configuration needed - just launch normally
"""
    
    # Mousepad forced autosave (XFCE editor)
    MOUSEPAD_AUTOSAVE = """
# Mousepad autosave configuration
# Written to ~/.config/mousepad/accels.scm
# We'll rely on recovery thread for autosave
"""
    
    # Pluma (MATE editor) forced autosave
    PLUMA_AUTOSAVE = """
# Pluma autosave configuration
# Written to ~/.config/pluma/pluma.conf
[Document]
Auto Save=1
Auto Save Interval=30
Create Backup=0
"""
    
    # Gedit forced autosave
    GEDIT_AUTOSAVE = """
# Gedit autosave configuration
# Written to ~/.config/gedit/gedit.conf
[gedit]
auto-save=true
auto-save-interval=30
create-backup-copy=false
"""
    
    # Nano forced autosave (via .nanorc)
    NANO_AUTOSAVE = """
# Nano autosave configuration
# Written to ~/.nanorc
set autoindent
set backup
set backupdir "~/.nano/backups"
set historylog
set positionlog
set zap
bind ^S savefile main
"""
    
    # JOE forced autosave
    JOE_AUTOSAVE = """
# JOE autosave configuration
# Written to ~/.joerc
-auto-save
-auto-save-interval 30
"""
    
    # JED forced autosave
    JED_AUTOSAVE = """
# JED autosave configuration
# Written to ~/.jedrc
() = evalkeb("set autosave 30");
() = evalkeb("set autosavefocus");
"""
    
    # MG forced autosave (micro GNU emacs)
    MG_AUTOSAVE = """
# MG autosave configuration
# Written to ~/.mg
(setq auto-save-interval 300)
(setq auto-save-timeout 30)
(setq backup-by-copying t)
"""
    # Default editor preferences (fallback if config.json not found)
    DEFAULT_EDITORS = {
        "edit": "micro",  # default editor for editing
        "view": "micro"   # default editor for viewing
    }
    
    @classmethod
    def load_config(cls, config_path=None):
        """Load editor preferences from config.json"""
        import sys
        import os
    
        if config_path is None:
            # Fallback: use app_dir
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(app_dir, "config.json")
    
        config = {
            "edit": cls.DEFAULT_EDITORS["edit"],
            "view": cls.DEFAULT_EDITORS["view"]
        }
    
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                    config["edit"] = user_config.get("edit", config["edit"])
                    config["view"] = user_config.get("view", config["view"])
            except:
                pass
    
        return config
    
    @classmethod
    def get_editor_list(cls, mode="edit", read_only=False, config_path=None):
        """
        Get the list of editors to try in order.
        """
        import sys
        import os
        import subprocess

        # If config_path is None, get it from app_dir
        if config_path is None:
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(app_dir, "config.json")

        # Load user preferences
        config = cls.load_config(config_path)
        preferred_editor = config.get(mode, config.get("edit", "micro"))

        # 🟢 Check for bundled editors first (when running as executable)
        bundled_editors = {}
        if getattr(sys, 'frozen', False):
            # Check for bundled micro
            micro_path = os.path.join(os.path.dirname(sys.executable), 'editors', 'micro.exe')
            if os.path.exists(micro_path):
                bundled_editors['micro'] = [micro_path, f"{micro_path} -readonly"]
        
            # Check for bundled nvim
            nvim_path = os.path.join(os.path.dirname(sys.executable), 'editors', 'nvim.exe')
            if os.path.exists(nvim_path):
                bundled_editors['nvim'] = [nvim_path, f"{nvim_path} -R"]

        # Define all available editors (check bundled first)
        all_editors = {
            "micro": [bundled_editors.get('micro', ['micro', 'micro'])[0],
                      bundled_editors.get('micro', ['micro', 'micro'])[1]],
            "nvim": [bundled_editors.get('nvim', ['nvim', 'nvim -R'])[0],
                     bundled_editors.get('nvim', ['nvim', 'nvim -R'])[1]],
            "vim": ["vim", "vim -R"],
            "helix": ["helix", "helix"],
            "hx": ["hx", "hx"],
            "emacs": ["emacs -nw", "emacs -nw --eval '(view-mode)'"],
            "nano": ["nano", "nano -v"],
            "kate": ["kate", "kate"],
            "geany": ["geany", "geany"],
            "gedit": ["gedit", "gedit"],
            "pluma": ["pluma", "pluma"],
            "mousepad": ["mousepad", "mousepad"],
            "leafpad": ["leafpad", "leafpad"],
            "mg": ["mg", "mg -R"],
            "jed": ["jed", "jed -view"],
            "joe": ["joe", "joe -rdonly"]
        }

        # Build the ordered list
        editor_list = []

        # 1. Put preferred editor first
        if preferred_editor in all_editors:
            cmd = all_editors[preferred_editor][1 if read_only else 0]
            editor_list.append(cmd)

        # 2. Add all other editors
        for editor, commands in all_editors.items():
            if editor != preferred_editor:
                cmd = commands[1 if read_only else 0]
                if cmd not in editor_list:
                    editor_list.append(cmd)

        return editor_list
    
    @classmethod
    def get_launch_command(cls, editor, temp_path, read_only=False, config_path=None):
        """Get the full launch command for an editor"""
        import sys
        import os

        editor_base = editor.split()[0]

        # If config_path not provided, get it from app_dir
        if config_path is None:
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(app_dir, "config.json")

        # Load config to check if this is the preferred editor
        config = cls.load_config(config_path)
        preferred_edit = config.get("edit", "micro")
        preferred_view = config.get("view", "micro")

        # Get editor list with config_path
        editors = cls.get_editor_list(mode="edit" if not read_only else "view", 
                                    read_only=read_only, 
                                    config_path=config_path)

        # Handle editors with built-in autosave
        if editor_base in ["micro", "helix", "hx", "kate", "geany", "gedit", "pluma", "mousepad", "leafpad"]:
            if (not read_only and editor_base == preferred_edit) or \
            (read_only and editor_base == preferred_view):
                cls._ensure_autosave_config(editor_base)
            return f"{editor} {temp_path}"

        # Handle editors with command-line autosave
        elif editor_base == "nvim":
            if not read_only:
                cmd_string = " -c \"" + "\" -c \"".join(cls.NVIM_AUTOSAVE) + "\""
                return f"nvim{cmd_string} {temp_path}"
            return f"nvim -R {temp_path}"

        elif editor_base == "vim":
            if not read_only:
                cmd_string = " -c \"" + "\" -c \"".join(cls.VIM_AUTOSAVE) + "\""
                return f"vim{cmd_string} {temp_path}"
            return f"vim -R {temp_path}"

        elif editor_base == "emacs":
            if read_only:
                return f"emacs -nw --eval '(view-mode)' {temp_path}"
            else:
                cmd_string = " --eval \"" + "\" --eval \"".join(cls.EMACS_AUTOSAVE) + "\""
                return f"emacs -nw{cmd_string} {temp_path}"

        elif editor_base == "nano":
            if not read_only:
                cls._ensure_nanorc_autosave()
            return f"{editor} {temp_path}"

        elif editor_base == "joe":
            if not read_only:
                cls._ensure_joe_autosave()
            return f"{editor} {temp_path}"

        elif editor_base == "jed":
            if not read_only:
                cls._ensure_jed_autosave()
            return f"{editor} {temp_path}"

        elif editor_base == "mg":
            if not read_only:
                cls._ensure_mg_autosave()
            return f"{editor} {temp_path}"

        # Default - just launch
        return f"{editor} {temp_path}"
    
    @classmethod
    def _ensure_autosave_config(cls, editor):
        """Create config files to force autosave for various editors"""
        import os
        import json
    
        home = os.path.expanduser("~")
    
        if editor == "micro":
            config_dir = os.path.join(home, ".config", "micro")
            config_file = os.path.join(config_dir, "settings.json")
            os.makedirs(config_dir, exist_ok=True)
        
            # Only write if file doesn't exist OR if it's empty/corrupted
            should_write = False
            if not os.path.exists(config_file):
                should_write = True
            else:
                # Check if file is valid JSON
                try:
                    with open(config_file, 'r') as f:
                        json.load(f)
                except:
                    should_write = True  # Corrupted, overwrite
        
            if should_write:
                try:
                    # Parse the JSON string to validate it
                    config_data = json.loads(cls.MICRO_AUTOSAVE)
                    with open(config_file, 'w') as f:
                        json.dump(config_data, f, indent=2)
                except Exception:
                    pass  # Fail silently
    
        elif editor == "helix" or editor == "hx":
            config_dir = os.path.join(home, ".config", "helix")
            config_file = os.path.join(config_dir, "config.toml")
            os.makedirs(config_dir, exist_ok=True)
        
            if not os.path.exists(config_file):
                try:
                    with open(config_file, 'w') as f:
                        f.write(cls.HELIX_AUTOSAVE.strip())
                except:
                    pass
        
        elif editor == "kate":
            config_file = os.path.join(home, ".config", "katerc")
            if not os.path.exists(config_file):
                try:
                    with open(config_file, 'w') as f:
                        f.write(cls.KATE_AUTOSAVE.strip())
                except:
                    pass
        
        elif editor == "geany":
            config_dir = os.path.join(home, ".config", "geany")
            config_file = os.path.join(config_dir, "geany.conf")
            os.makedirs(config_dir, exist_ok=True)
            
            if not os.path.exists(config_file):
                try:
                    with open(config_file, 'w') as f:
                        f.write(cls.GEANY_AUTOSAVE.strip())
                except:
                    pass
        
        elif editor == "gedit":
            config_dir = os.path.join(home, ".config", "gedit")
            config_file = os.path.join(config_dir, "gedit.conf")
            os.makedirs(config_dir, exist_ok=True)
            
            if not os.path.exists(config_file):
                try:
                    with open(config_file, 'w') as f:
                        f.write(cls.GEDIT_AUTOSAVE.strip())
                except:
                    pass
        
        elif editor == "pluma":
            config_dir = os.path.join(home, ".config", "pluma")
            config_file = os.path.join(config_dir, "pluma.conf")
            os.makedirs(config_dir, exist_ok=True)
            
            if not os.path.exists(config_file):
                try:
                    with open(config_file, 'w') as f:
                        f.write(cls.PLUMA_AUTOSAVE.strip())
                except:
                    pass
    
    @classmethod
    def _ensure_nanoroc_autosave(cls):
        """Create .nanorc with autosave settings"""
        import os
        home = os.path.expanduser("~")
        nanorc = os.path.join(home, ".nanorc")
        
        if not os.path.exists(nanorc):
            try:
                with open(nanorc, 'w') as f:
                    f.write(cls.NANO_AUTOSAVE.strip())
            except:
                pass
    
    @classmethod
    def _ensure_joe_autosave(cls):
        """Create .joerc with autosave settings"""
        import os
        home = os.path.expanduser("~")
        joerc = os.path.join(home, ".joerc")
        
        if not os.path.exists(joerc):
            try:
                with open(joerc, 'w') as f:
                    f.write(cls.JOE_AUTOSAVE.strip())
            except:
                pass
    
    @classmethod
    def _ensure_jed_autosave(cls):
        """Create .jedrc with autosave settings"""
        import os
        home = os.path.expanduser("~")
        jedrc = os.path.join(home, ".jedrc")
        
        if not os.path.exists(jedrc):
            try:
                with open(jedrc, 'w') as f:
                    f.write(cls.JED_AUTOSAVE.strip())
            except:
                pass
    
    @classmethod
    def _ensure_mg_autosave(cls):
        """Create .mg with autosave settings"""
        import os
        home = os.path.expanduser("~")
        mgrc = os.path.join(home, ".mg")
        
        if not os.path.exists(mgrc):
            try:
                with open(mgrc, 'w') as f:
                    f.write(cls.MG_AUTOSAVE.strip())
            except:
                pass