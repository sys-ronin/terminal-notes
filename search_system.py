#!/usr/bin/env python3
from datetime import datetime
import shutil


class SimpleSearch:
    def __init__(self, note_manager, ui_methods):
        self.manager = note_manager
        self.ui = ui_methods  # Reference to main UI methods
        self.results = []
        self.query = ""
        self.current_page = 0
        self.search_nav_stack = []  # Format: {'screen': 'results/notebook/note', 'data': {}}
    
    def search(self, query, include_historical=False):
        self.query = query
        self.results = []
        self.current_page = 0

        # If query is empty, return ALL items (but skip locked notebooks)
        if not query or not query.strip():
            for notebook in self.manager.notebooks:
                # Skip locked notebooks entirely
                if notebook.id in self.manager.encrypted_notebooks and not hasattr(notebook, 'custom_path'):
                    continue
            
                # Add the notebook itself (root notebooks only)
                if not notebook.parent_id:
                    self.results.append({
                        'type': 'current_notebook',
                        'notebook_id': notebook.id,
                        'parent_id': None,
                        'item_type': 'root_notebook',
                        'name': notebook.name
                    })
            
                # Add all notes and subnotebooks recursively
                def add_items_recursive(nb):
                    # Add notes in this notebook
                    for note in nb.notes:
                        self.results.append({
                            'type': 'current_note',
                            'note_id': note.id,
                            'notebook_id': nb.id,
                            'item_type': 'file' if note.is_file_note else 'note',
                            'title': note.title
                        })
                
                    # Add subnotebooks themselves
                    for sub_nb in nb.subnotebooks:
                        # Check if subnotebook is locked
                        if sub_nb.id in self.manager.encrypted_notebooks and not hasattr(sub_nb, 'custom_path'):
                            continue
                    
                        # Add the subnotebook itself
                        self.results.append({
                            'type': 'current_notebook',
                            'notebook_id': sub_nb.id,
                            'parent_id': sub_nb.parent_id,
                            'item_type': 'subnotebook',
                            'name': sub_nb.name
                        })
                        # Recursively add its contents
                        add_items_recursive(sub_nb)
            
                add_items_recursive(notebook)

            return self.results

        # Search with query
        def search_recursive(notebook):
            # Skip locked notebooks entirely
            if notebook.id in self.manager.encrypted_notebooks and not hasattr(notebook, 'custom_path'):
                return
    
            # 🟢 FIX: Search notebook name itself
            if query.lower() in notebook.name.lower():
                self.results.append({
                    'type': 'current_notebook',
                    'notebook_id': notebook.id,
                    'parent_id': notebook.parent_id,
                    'item_type': 'subnotebook' if notebook.parent_id else 'root_notebook',
                    'name': notebook.name
                })
    
            # Search notes/files in this notebook
            for note in notebook.notes:
                title_match = query.lower() in note.title.lower()
                content_match = False
                if hasattr(note, 'content') and note.content:
                    content_match = query.lower() in note.content.lower()
    
                if title_match or content_match:
                    self.results.append({
                        'type': 'current_note',
                        'note_id': note.id,
                        'notebook_id': notebook.id,
                        'item_type': 'file' if note.is_file_note else 'note',
                        'title': note.title
                    })

            # 🟢 FIX: Search subnotebook names AND recurse into them
            for sub_nb in notebook.subnotebooks:
                # Skip locked subnotebooks
                if sub_nb.id in self.manager.encrypted_notebooks and not hasattr(sub_nb, 'custom_path'):
                    continue
            
                # Search subnotebook name
                if query.lower() in sub_nb.name.lower():
                    self.results.append({
                        'type': 'current_notebook',
                        'notebook_id': sub_nb.id,
                        'parent_id': notebook.id,
                        'item_type': 'subnotebook',
                        'name': sub_nb.name
                    })
            
                # 🟢 CRITICAL: Recursively search inside subnotebook
                search_recursive(sub_nb)

        # Start recursive search from all root notebooks
        for notebook in self.manager.notebooks:
            search_recursive(notebook)

        return self.results
    
    def get_search_page_size(self):
        """Use the exact same calculation as notebook views"""
        try:
            _, terminal_height = shutil.get_terminal_size()
        
            # EXACT SAME as your working notebook view calculation
            fixed_lines = 4    # Header
            fixed_lines += 2   # Results header (equivalent to "Notes & Files") 
            fixed_lines += 2   # Page indicator (when needed)
            fixed_lines += 3   # Footer
        
            available_lines = terminal_height - fixed_lines
            items_per_page = available_lines  # NO BUFFER - fill all available lines
        
            return items_per_page
        
        except:
            return self.get_dynamic_page_size()  # Fallback to existing method
    
    def clear(self):
        self.results = []
        self.query = ""
        self.current_page = 0
    
    
    