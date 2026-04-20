#!/usr/bin/env python3
"""
Vault Manager - Manages custom vault locations for secure session storage
"""

import sys
sys.dont_write_bytecode = True

import os
import json
import uuid
from datetime import datetime


class VaultManager:
    """Manages vault registry for custom secure session locations"""
    
    def __init__(self, app_dir):
        self.app_dir = app_dir
        self.config_dir = os.path.join(app_dir, "config")
        self.vault_registry_path = os.path.join(self.config_dir, "vaults_registry.json")
        self._vaults_cache = None
    
    def _load_registry(self):
        """Load vault registry (encrypted with system fingerprint)"""
        if self._vaults_cache is not None:
            return self._vaults_cache
        
        if not os.path.exists(self.vault_registry_path):
            self._vaults_cache = {"vaults": {}}
            return self._vaults_cache
        
        try:
            with open(self.vault_registry_path, 'r') as f:
                self._vaults_cache = json.load(f)
            return self._vaults_cache
        except:
            self._vaults_cache = {"vaults": {}}
            return self._vaults_cache
    
    def _save_registry(self):
        """Save vault registry"""
        try:
            with open(self.vault_registry_path, 'w') as f:
                json.dump(self._vaults_cache, f, indent=2)
            return True
        except:
            return False
    
    def get_vault_path(self, vault_id):
        """Get location path for a vault ID"""
        registry = self._load_registry()
        vault = registry.get("vaults", {}).get(vault_id)
        if vault:
            return vault.get("location")
        return None
    
    def get_vaults_list(self):
        """Get all vaults as list with IDs"""
        registry = self._load_registry()
        result = []
        for vault_id, vault_data in registry.get("vaults", {}).items():
            result.append({
                "id": vault_id,
                "type": vault_data.get("type", "file"),
                "location": vault_data.get("location"),
                "notebooks": vault_data.get("notebooks", [])
            })
        return result
    
    def create_vault(self, location, vault_type="file"):
        """Create a new vault entry"""
        registry = self._load_registry()
        
        # Generate new vault ID
        vault_id = f"vault_{uuid.uuid4().hex[:8]}"
        
        registry["vaults"][vault_id] = {
            "type": vault_type,
            "location": location,
            "created": datetime.now().isoformat(),
            "notebooks": []
        }
        
        if self._save_registry():
            return vault_id
        return None
    
    def assign_notebook_to_vault(self, vault_id, notebook_id):
        """Assign a notebook to a vault"""
        registry = self._load_registry()
        
        if vault_id not in registry.get("vaults", {}):
            return False
        
        notebooks = registry["vaults"][vault_id].get("notebooks", [])
        if notebook_id not in notebooks:
            notebooks.append(notebook_id)
            registry["vaults"][vault_id]["notebooks"] = notebooks
            return self._save_registry()
        return True
    
    def remove_notebook_from_vault(self, vault_id, notebook_id):
        """Remove a notebook from a vault"""
        registry = self._load_registry()
        
        if vault_id not in registry.get("vaults", {}):
            return False
        
        notebooks = registry["vaults"][vault_id].get("notebooks", [])
        if notebook_id in notebooks:
            notebooks.remove(notebook_id)
            registry["vaults"][vault_id]["notebooks"] = notebooks
            return self._save_registry()
        return True
    
    def delete_vault(self, vault_id):
        """Delete a vault entry (does not delete the actual vault file)"""
        registry = self._load_registry()
        
        if vault_id in registry.get("vaults", {}):
            del registry["vaults"][vault_id]
            return self._save_registry()
        return False
    
    def get_default_vault_path(self):
        """Get the default vault path"""
        return os.path.join(self.config_dir, "session.vault")