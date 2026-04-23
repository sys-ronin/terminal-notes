#!/usr/bin/env python3
"""
Vault Manager - Manages custom vault locations for notebooks
"""

import os
import json
import shutil
from datetime import datetime
from typing import Optional, Dict, List
import sys
sys.dont_write_bytecode = True


class VaultManager:
    def __init__(self, app_dir: str):
        self.app_dir = app_dir
        self.registry_path = os.path.join(app_dir, "notebooks_root", "vaults_registry.json")
        self.vaults = {}
        self._load()
    
    def _load(self):
        """Load vault registry from disk"""
        if os.path.exists(self.registry_path):
            try:
                with open(self.registry_path, 'r') as f:
                    self.vaults = json.load(f)
            except:
                self.vaults = {"vaults": {}}
        else:
            self.vaults = {"vaults": {}}
    
    def _save(self):
        """Save vault registry to disk"""
        try:
            with open(self.registry_path, 'w') as f:
                json.dump(self.vaults, f, indent=2)
        except Exception as e:
            print(f"Error saving vault registry: {e}")
    
    def get_vault_path(self, vault_id: str) -> Optional[str]:
        """Get location path for a vault ID"""
        vault = self.vaults.get("vaults", {}).get(vault_id)
        if vault:
            return vault.get("location")
        return None
    
    def get_vault_for_notebook(self, notebook_id: str) -> Optional[str]:
        """Find which vault contains this notebook"""
        for vault_id, vault in self.vaults.get("vaults", {}).items():
            if notebook_id in vault.get("notebooks", []):
                return vault_id
        return None
    
    def add_notebook_to_vault(self, vault_id: str, notebook_id: str):
        """Add notebook to vault's notebook list"""
        if vault_id not in self.vaults.get("vaults", {}):
            return False
        
        if "notebooks" not in self.vaults["vaults"][vault_id]:
            self.vaults["vaults"][vault_id]["notebooks"] = []
        
        if notebook_id not in self.vaults["vaults"][vault_id]["notebooks"]:
            self.vaults["vaults"][vault_id]["notebooks"].append(notebook_id)
            self._save()
        return True
    
    def remove_notebook_from_vault(self, vault_id: str, notebook_id: str):
        """Remove notebook from vault's notebook list"""
        if vault_id in self.vaults.get("vaults", {}):
            if "notebooks" in self.vaults["vaults"][vault_id]:
                if notebook_id in self.vaults["vaults"][vault_id]["notebooks"]:
                    self.vaults["vaults"][vault_id]["notebooks"].remove(notebook_id)
                    self._save()
    
    def create_vault(self, location: str, vault_id: str = None) -> str:
        """Create a new vault entry"""
        import uuid
        
        # If this is the default vault path, use "default" as ID
        if location.endswith("config/session.vault") or vault_id == "default":
            vault_id = "default"
        else:
            vault_id = f"vault_{uuid.uuid4().hex[:8]}"
        
        if "vaults" not in self.vaults:
            self.vaults["vaults"] = {}
        
        self.vaults["vaults"][vault_id] = {
            "type": "file",
            "location": location,
            "notebooks": [],
            "created": datetime.now().isoformat()
        }
        
        self._save()
        return vault_id
    
    def delete_vault(self, vault_id: str):
        """Delete a vault entry (does not delete the actual vault file)"""
        if vault_id in self.vaults.get("vaults", {}):
            del self.vaults["vaults"][vault_id]
            self._save()
    
    def list_vaults(self) -> Dict:
        """Return all vaults"""
        return self.vaults.get("vaults", {})
    
    def vault_exists(self, location: str) -> Optional[str]:
        """Check if a vault already exists at given location, return vault_id if found"""
        for vault_id, vault in self.vaults.get("vaults", {}).items():
            if vault.get("location") == location:
                return vault_id
        return None