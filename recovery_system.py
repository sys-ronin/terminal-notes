# recovery_system.py
import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from terminal_notes_core import Note  # 🆕 ADD THIS IMPORT

class RecoverySystem:
    def __init__(self, manager, app_dir=None):
        self.manager = manager
        if app_dir:
            self.app_dir = app_dir
        elif hasattr(manager, 'app_dir'):
            self.app_dir = manager.app_dir
        else:
            self.app_dir = Path(__file__).parent
    
        self.recovery_dir = Path(self.app_dir) / ".recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
    
    def get_recovery_filename(self, note_uuid, note_title, is_file_note=False, file_extension=None):
        """Generate recovery filename using last 6 chars of UUID"""
        uuid_part = str(note_uuid)[-6:]
        safe_title = "".join(c for c in note_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        safe_title = safe_title.replace(' ', '_')[:30]
    
        if is_file_note and file_extension:
            return f"{safe_title}_{uuid_part}.{file_extension}"
        else:
            return f"{safe_title}_{uuid_part}"
    
    def save_recovery_file(self, note_uuid, parent_notebook_uuid, content, note_title, 
                        is_file_note=False, file_extension=None):
        """Save autosave recovery file"""
    
        filename = self.get_recovery_filename(note_uuid, note_title, is_file_note, file_extension)
        recovery_path = self.recovery_dir / filename
    
        recovery_data = {
            "note_uuid": str(note_uuid),
            "parent_notebook_uuid": str(parent_notebook_uuid),
            "content": content,
            "is_file_note": is_file_note,
            "file_extension": file_extension,
            "note_title": note_title,
            "last_updated": datetime.now().isoformat()
        }
    
        try:
            # Atomic write - write to temp then rename
            temp_path = recovery_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(recovery_data, f, indent=2)
            temp_path.rename(recovery_path)
            return True
        except Exception:
            return False
    
    def get_recovery_files_for_notebook(self, notebook_uuid):
        """Get all recovery files for a specific notebook"""
        notebook_recoveries = []
    
        for recovery_file in self.recovery_dir.glob('*'):
            if recovery_file.is_file() and not recovery_file.name.endswith('.tmp'):
                try:
                    with open(recovery_file, 'r', encoding='utf-8') as f:
                        recovery_data = json.load(f)
                
                    file_uuid = recovery_data.get('parent_notebook_uuid')
                
                    if file_uuid == str(notebook_uuid):
                        notebook_recoveries.append((recovery_file, recovery_data))
                except Exception as e:
                    continue
    
        return notebook_recoveries
    
    def recover_notebook_content(self, notebook):
        """Recover any unsaved content for this notebook"""
        recovered_count = 0
        recovery_files = self.get_recovery_files_for_notebook(notebook.id)
    
        for recovery_file, recovery_data in recovery_files:
            try:
                note_uuid = recovery_data['note_uuid']
                content = recovery_data['content']
                note_title = recovery_data['note_title']
                is_file_note = recovery_data['is_file_note']
                file_extension = recovery_data['file_extension']
            
                # Find if note already exists
                existing_note, existing_notebook = self.manager.find_note_by_id(None, note_uuid)
            
                # CASE 1: Note already exists
                if existing_note:
                    if not content or not content.strip():
                        from notebook_operations import NotebookOperations
                        ops = NotebookOperations(self.manager)
                        ops.delete_note(existing_note, existing_notebook, 'forget')
                    elif content != existing_note.content:
                        from notebook_operations import NotebookOperations
                        ops = NotebookOperations(self.manager)
                        ops.edit_note(existing_note, existing_notebook, content)
                        recovered_count += 1

                # CASE 2: Note does NOT exist
                else:
                    if content and content.strip():
                        from notebook_operations import NotebookOperations
                        ops = NotebookOperations(self.manager)
                    
                        new_note = ops.create_note(
                            notebook, 
                            note_title, 
                            content, 
                            "vim"
                        )   
                    
                        if is_file_note and file_extension:
                            new_note.file_extension = file_extension
                            ops.save_notebook(notebook, save_notes=False, save_files=True)
                    
                        recovered_count += 1

                # Always remove the recovery file after processing
                recovery_file.unlink()

            except Exception:
                continue

        return recovered_count
    
    def _save_notebook_silently(self, notebook):
        """Save notebook without triggering navigation events"""
        # 🟢 FIX THIS - use custom_path instead
        if hasattr(notebook, 'custom_path') and notebook.custom_path:
            folder_path = notebook.custom_path
        else:
            print(f"⚠ No custom_path for notebook {notebook.name}, cannot save silently")
            return False
    
        # 🟢 FIX: Get file paths using folder_path directly
        structure_file = os.path.join(folder_path, "structure.json")
        notes_file = os.path.join(folder_path, "notes.json")
        files_file = os.path.join(folder_path, "files.json")

        # Save structure (metadata only)
        structure_data = notebook.to_dict()
        with open(structure_file, "w") as f:
            json.dump(structure_data, f, indent=2)

        # Save content files directly
        notes_map = {}
        files_map = {}
    
        # 🟢 FIX: Use ops to extract content if available
        from notebook_operations import NotebookOperations
        ops = NotebookOperations(self.manager)
        ops._extract_file_content_from_notebook(notebook, notes_map, files_map)

        with open(notes_file, "w") as f:
            json.dump(notes_map, f, indent=2)

        with open(files_file, "w") as f:
            json.dump(files_map, f, indent=2)
    
        return True
    
    def cleanup_stale_recovery_files(self, older_than_hours=24):
        """Clean up old recovery files"""
        cutoff_time = datetime.now().timestamp() - (older_than_hours * 3600)
        
        for recovery_file in self.recovery_dir.glob('*'):
            if recovery_file.is_file():
                if recovery_file.stat().st_mtime < cutoff_time:
                    recovery_file.unlink()