# git_manager.py
import os
import subprocess
import uuid
import re
from datetime import datetime
from pathlib import Path


class GitManager:
    def __init__(self, notebook_path):
        self.notebook_path = Path(notebook_path)
        self.repo_initialized = False
        self.current_branch = "master"
        self._check_git_installation()

    def _check_git_installation(self):
        """Check if Git is installed and available"""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
                cwd=self.notebook_path,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fail silently - Git is optional
            pass

    def _run_git_command(self, command, capture_output=True):
        """Run Git command silently"""
        try:
            result = subprocess.run(
                command,
                cwd=self.notebook_path,
                capture_output=capture_output,
                text=True,
                check=True,
            )
            return result
        except subprocess.CalledProcessError:
            return None

    def init_repo(self, notebook_name=None, custom_path=None):
        """Initialize Git repository - ONLY initialize, don't commit"""
        git_dir = self.notebook_path / ".git"
        if not git_dir.exists():
            self._run_git_command(["git", "init"])
            # DON'T add files here
            # DON'T commit here
            self.repo_initialized = True
        self.repo_initialized = True

    def commit_silently(self, message, files=None):
        """Commit with atomic writes guaranteed"""
        if not self.repo_initialized:
            self.init_repo()

        if files is None:
            files = ["structure.json", "notes.json", "files.json"]
        elif isinstance(files, str):
            files = [files]
    
        # Stage files
        for file in files:
            self._run_git_command(["git", "add", file])
    
        # Commit if changes exist
        status = self._run_git_command(["git", "status", "--porcelain"])
        if status and status.stdout:
            result = self._run_git_command(["git", "commit", "-m", message])
            return result is not None
        return True
    
    def generate_commit_message(self, action, content_type, title, context="", description="", tags="", item_uuid="", parent_uuid="", root_uuid=""):
        """Generate structured commit messages with parent and root UUIDs"""
    
        # Build main message with type: prefix
        message = f"type: {action} {content_type}: {title}"
        if context:
            message += f" | {context}"
    
        # Add description if provided
        if description:
            message += f"\n\n{description}"
    
        # Build metadata with ALL UUIDs
        metadata_parts = []
        if tags:
            metadata_parts.append(tags)
    
        # Always include UUIDs when available - join with | directly
        uuid_parts = []
        if item_uuid:
            uuid_parts.append(f"uuid:{item_uuid}")
        if parent_uuid:
            uuid_parts.append(f"parent:{parent_uuid}")
        if root_uuid:
            uuid_parts.append(f"root:{root_uuid}")
    
        if uuid_parts:
            metadata_parts.append(" | ".join(uuid_parts))
    
        # Add metadata to message
        if metadata_parts:
            message += f"\n\nMetadata: {' | '.join(metadata_parts)}"
    
        return message

    def detect_note_type(self, note_content, editor_type):
        """Detect if note is quick capture or detailed"""
        word_count = len(note_content.split())
        
        if editor_type == "internal":
            if word_count < 50:
                return "Quick note"
            else:
                return "Text note"
        else:  # vim editor
            if word_count > 200:
                return "Detailed notes"
            else:
                return "Formatted note"

    def detect_file_purpose(self, filename, extension, content):
        """Detect file purpose based on extension and content"""
        purposes = {
            # Web Core
            "html": "HTML webpage", "js": "JavaScript", "css": "Stylesheet", 
            "ts": "TypeScript", "scss": "Sass styles", "vue": "Vue component",
            "jsx": "React component", "svelte": "Svelte component", "astro": "Astro page",
            "mdx": "MDX documentation", "graphql": "GraphQL schema",

            # Backend & Systems
            "py": "Python script", "php": "PHP script", "rb": "Ruby script",
            "java": "Java code", "c": "C code", "cpp": "C++ code", "go": "Go code",
            "rs": "Rust code", "pl": "Perl script", "lua": "Lua script", "r": "R script",
            "jl": "Julia code",
        
            # Mobile & Platforms
            "swift": "Swift code", "kt": "Kotlin code",
        
            # DevOps & Automation
            "sh": "Shell script", "yml": "YAML config", "yaml": "YAML config",
            "toml": "TOML config", "ini": "INI config", "cfg": "Config file",
            "hcl": "HCL config", "tf": "Terraform config", "justfile": "Just tasks",
            "nix": "Nix expression",
        
            # Data & APIs
            "json": "JSON data", "xml": "XML data", "sql": "SQL queries",
            "proto": "Protocol Buffer",
        
            # Documentation
            "bib": "Bibliography", "tex": "LaTeX document", "md": "Markdown doc",
            "txt": "Text file", "sty": "LaTeX style", "cls": "LaTeX class",
            "org": "Org mode doc", "adoc": "AsciiDoc", "rst": "reStructuredText",
            "typ": "Typst document",
        
            # Shell Configs
            "bashrc": "Bash config", "zshrc": "Zsh config", "profile": "Profile config",
            "aliases": "Shell aliases", "bash_profile": "Bash profile",
            "zprofile": "Zsh profile",
        
            # Editor Configs
            "vimrc": "Vim config", "editorconfig": "EditorConfig",

            # Git Configs
            "gitconfig": "Git config", "gitignore": "Git ignore", "gitattributes": "Git attributes",
        
            # Language/Runtime
            "npmrc": "npm config", "yarnrc": "Yarn config", "gemrc": "RubyGems config",
            "Rprofile": "R profile", "irbrc": "IRB config",
        
            # Application Configs
            "tmux.conf": "Tmux config", "inputrc": "Readline config",
            "Xresources": "X resources", "ssh/config": "SSH config",
        
            # Container/CI
            "Dockerfile": "Dockerfile", "Jenkinsfile": "Jenkins pipeline",
            "service": "Systemd service", "timer": "Systemd timer"
        }
    
        return purposes.get(extension, f"{extension.upper()} file")

    def get_content_metrics(self, content):
        """Calculate word count and line count"""
        words = len(content.split())
        lines = len(content.splitlines())
        return words, lines
    # 🎯 8 COMMIT OPERATIONS

    def commit_notebook_creation(self, notebook_uuid, notebook_name, note_count=0, file_count=0, custom_path=None):
        """Commit: CREATE_NOTEBOOK - WITH PROPER UUIDs"""
        if custom_path:
            context = "custom location"
        else:
            context = "default location"

        message = self.generate_commit_message(
            action="CREATED",
            content_type="NOTEBOOK", 
            title=notebook_name,
            context=context,
            tags=f"notebook created {notebook_name.lower()}",
            item_uuid=notebook_uuid,
            parent_uuid="",
            root_uuid=notebook_uuid
        )

        return self.commit_silently(message, ["structure.json", "notes.json", "files.json"])

    def commit_subnotebook_creation(self, subnotebook_uuid, subnotebook_name, parent_notebook, note_count=0, root_uuid=""):
        """Commit: CREATE_SUBNOTEBOOK"""
    
        # Get parent UUID
        parent_uuid = ""
        if hasattr(parent_notebook, 'id'):
            parent_uuid = parent_notebook.id
        elif isinstance(parent_notebook, str):
            # Try to find notebook by name
            for nb in self.manager.notebooks:
                if nb.name == parent_notebook:
                    parent_uuid = nb.id
                    break
    
        # Get parent name for context
        parent_name = parent_notebook.name if hasattr(parent_notebook, 'name') else parent_notebook
    
        message = self.generate_commit_message(
            action="CREATED",
            content_type="SUBNOTEBOOK",
            title=subnotebook_name,
            context=f"in {parent_name}",
            tags=f"subnotebook created {subnotebook_name.lower()}",
            item_uuid=subnotebook_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        return self.commit_silently(message, ["structure.json"])

    def commit_note_creation(self, note_uuid, note_title, notebook_name, editor_type, content="", parent_uuid="", root_uuid=""):
        """Commit: CREATE_NOTE - with format: change: 11(+) totalc:11"""
        note_type = self.detect_note_type(content, editor_type)
        char_count = len(content)
    
        changes = f"change: {char_count}(+) totalc:{char_count}"  # ← change: for creation
    
        message = self.generate_commit_message(
            action="CREATED",
            content_type="NOTE",
            title=note_title,
            context=f"in {notebook_name} | Editor: {editor_type}, Type: {note_type}",
            description=changes,
            tags=f"note created {note_title.lower()} {notebook_name.lower()} {editor_type} chars:{char_count}",
            item_uuid=note_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        return self.commit_silently(message, ["structure.json", "notes.json"])

    def commit_file_creation(self, note_uuid, filename, notebook_name, extension, content="", parent_uuid="", root_uuid=""):
        """Commit: CREATE_FILE - with format: change: 11(+) totalc:11"""
        purpose = self.detect_file_purpose(filename, extension, content)
        char_count = len(content)
    
        changes = f"change: {char_count}(+) totalc:{char_count}"  # ← change: for creation
    
        message = self.generate_commit_message(
            action="CREATED", 
            content_type="FILE",
            title=filename,
            context=f"in {notebook_name} | {purpose} | .{extension}",
            description=changes,
            tags=f"file created {filename} {extension} {notebook_name.lower()} chars:{char_count}",
            item_uuid=note_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        return self.commit_silently(message, ["structure.json", "files.json"])

    def commit_note_edit(self, note_uuid, note_title, notebook_name, old_content, new_content, is_file_note=False, parent_uuid="", root_uuid=""):
        """Commit: EDIT_CONTENT - with format: change: 12(+) 5(-) totalc:17"""
        
        added, removed = self._count_char_changes(old_content, new_content)
        new_chars = len(new_content)
        changes = f"change: {added}(+) {removed}(-) totalc:{new_chars}"
        
        # Determine content type and files to commit
        if is_file_note:
            content_type = "FILE"
            files_to_commit = ["structure.json", "files.json"]
        else:
            content_type = "NOTE"
            files_to_commit = ["structure.json", "notes.json"]
        
        message = self.generate_commit_message(
            action="UPDATED",
            content_type=content_type,
            title=note_title,
            context=f"in {notebook_name}",
            description=changes,
            tags=f"note edited {note_title.lower()} {notebook_name.lower()} chars:{new_chars}",
            item_uuid=note_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        
        return self.commit_silently(message, files_to_commit)

    def commit_note_rename(self, note_uuid, old_title, new_title, notebook_name, is_file_note=False, parent_uuid="", root_uuid=""):
        """Commit: RENAME_NOTE"""
        content_type = "FILE" if is_file_note else "NOTE"
    
        message = self.generate_commit_message(
            action="RENAMED",
            content_type=content_type,
            title=f"{old_title} → {new_title}",
            context=f"in {notebook_name}",
            tags=f"renamed {old_title.lower()} {new_title.lower()} {notebook_name.lower()}",
            item_uuid=note_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        return self.commit_silently(message, "structure.json")

    def commit_note_deletion(self, note_uuid, note_title, notebook_name, is_file_note=False, parent_uuid="", root_uuid=""):
        """Commit: DELETE_NOTE - ALWAYS include parent UUID"""
        content_type = "FILE" if is_file_note else "NOTE"
    
        # 🟢 Ensure parent_uuid is set
        if not parent_uuid and root_uuid:
            parent_uuid = root_uuid
    
        message = self.generate_commit_message(
            action="DELETED",
            content_type=content_type,
            title=note_title,
            context=f"from {notebook_name}",
            tags=f"deleted {note_title.lower()} {notebook_name.lower()}",
            item_uuid=note_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        if is_file_note:
            return self.commit_silently(message, ["structure.json", "files.json"])
        else:
            return self.commit_silently(message, ["structure.json", "notes.json"])

    def commit_subnotebook_deletion(self, subnotebook_uuid, subnotebook_name, parent_notebook, root_uuid=""):
        """Commit: DELETE_SUBNOTEBOOK - ALWAYS include parent UUID"""
    
        # 🟢 Get parent UUID from the parent_notebook object
        parent_uuid = ""
        if hasattr(parent_notebook, 'id'):
            parent_uuid = parent_notebook.id
        elif isinstance(parent_notebook, str):
            # If it's a string, use it as the parent name and root as fallback
            parent_uuid = root_uuid
    
        # 🟢 Generate message with parent_uuid
        message = self.generate_commit_message(
            action="DELETED",
            content_type="SUBNOTEBOOK",
            title=subnotebook_name,
            context=f"from {parent_notebook}",
            tags=f"subnotebook deleted {subnotebook_name.lower()} {str(parent_notebook).lower()}",
            item_uuid=subnotebook_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        return self.commit_silently(message, "structure.json")
    
    def commit_restoration(self, item_uuid, item_title, notebook_name, item_type, 
                      original_commit=None, parent_uuid="", root_uuid="", context=""):
        """Commit: RESTORE item"""
    
        if context:
            full_context = context
        else:
            full_context = f"to {notebook_name}"
    
        description = ""
        if original_commit:
            description = f"Restored from commit {original_commit[:8]}"
    
        message = self.generate_commit_message(
            action="RESTORED",
            content_type=item_type,
            title=item_title,
            context=full_context,
            description=description,
            tags=f"restored {item_title.lower()} {notebook_name.lower()}",
            item_uuid=item_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
    
        if item_type == 'FILE':
            files = ["structure.json", "files.json"]
        elif item_type == 'NOTE':
            files = ["structure.json", "notes.json"]
        else:  # SUBNOTEBOOK
            files = ["structure.json", "notes.json", "files.json"]
    
        return self.commit_silently(message, files)
    
    def commit_subnotebook_rename(self, subnotebook_uuid, old_name, new_name, notebook_name, parent_uuid="", root_uuid=""):
        """Commit: RENAME_SUBNOTEBOOK - ONLY structure.json"""
    
        message = self.generate_commit_message(
            action="RENAMED",
            content_type="SUBNOTEBOOK",
            title=f"{old_name} → {new_name}",
            context=f"in {notebook_name}",
            tags=f"renamed subnotebook {old_name.lower()} {new_name.lower()} {notebook_name.lower()}",
            item_uuid=subnotebook_uuid,
            parent_uuid=parent_uuid,
            root_uuid=root_uuid
        )
        return self.commit_silently(message, ["structure.json"])  # ONLY structure.json
    
    def _count_char_changes(self, old_text, new_text):
        """Count actual character additions and removals between two strings."""
        if old_text == new_text:
            return 0, 0
    
        from collections import Counter
    
        old_counter = Counter(old_text)
        new_counter = Counter(new_text)
    
        # Characters that remain (common)
        common = old_counter & new_counter
    
        # Added = characters in new but not in common
        added = sum((new_counter - common).values())
    
        # Removed = characters in old but not in common
        removed = sum((old_counter - common).values())
    
        return added, removed