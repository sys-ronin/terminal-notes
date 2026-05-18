#!/usr/bin/env python3
"""
Vault Manager - Manages vault registry and .vault file I/O
"""

import os
import json
import uuid
import struct
from datetime import datetime
from typing import Optional, Dict, List
import sys
sys.dont_write_bytecode = True


class VaultManager:
    """Manages vault registry and .vault file operations"""
    
    VAULT_REGISTRY_VERSION = 1
    VAULT_FILE_VERSION = 2
    
    def __init__(self, app_dir: str):
        self.app_dir = app_dir
        self.registry_path = os.path.join(app_dir, "notebooks_root", "vaults_registry.json")
        self._registry_cache = None
    
    # ========================================================================
    # VAULT REGISTRY METHODS (per system, maps vault name → file path)
    # ========================================================================
    
    def load_vault_registry(self) -> Dict:
        """Load the vault registry from disk"""
        if self._registry_cache is not None:
            return self._registry_cache
        
        if not os.path.exists(self.registry_path):
            self._registry_cache = {
                "version": self.VAULT_REGISTRY_VERSION,
                "vaults": {}
            }
            return self._registry_cache
        
        try:
            with open(self.registry_path, 'r') as f:
                self._registry_cache = json.load(f)
                if "vaults" not in self._registry_cache:
                    self._registry_cache["vaults"] = {}
                return self._registry_cache
        except Exception as e:
            print(f"Error loading vault registry: {e}")
            self._registry_cache = {
                "version": self.VAULT_REGISTRY_VERSION,
                "vaults": {}
            }
            return self._registry_cache
    
    def save_vault_registry(self) -> None:
        """Save the vault registry to disk"""
        if self._registry_cache is None:
            return
        
        temp_path = self.registry_path + '.tmp'
        try:
            with open(temp_path, 'w') as f:
                json.dump(self._registry_cache, f, indent=2)
            os.rename(temp_path, self.registry_path)
        except Exception as e:
            print(f"Error saving vault registry: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def get_vault_id_from_file(self, vault_path: str) -> Optional[str]:
        """
        Extract vault ID from a vault file by reading its registry mapping.
        Returns the vault name (ID) if found, None otherwise.
        """
        import os
        
        # Check if this vault is registered in our registry
        registry = self.load_vault_registry()
        
        # Look for vault name that points to this path
        for vault_name, info in registry.get("vaults", {}).items():
            stored_path = info.get("path")
            if stored_path:
                # Handle relative paths (for default vault)
                if vault_name == "default" and not os.path.isabs(stored_path):
                    stored_path = os.path.join(self.app_dir, stored_path)
                
                # Compare normalized paths (handle Windows vs Linux paths)
                try:
                    if os.path.exists(stored_path) and os.path.samefile(stored_path, vault_path):
                        return vault_name
                except OSError:
                    # Fallback to string comparison if samefile fails
                    if os.path.normpath(stored_path) == os.path.normpath(vault_path):
                        return vault_name
        
        # Not found in registry - it's an unregistered vault file
        # Try to extract ID from filename (e.g., "vault_abc123.vault")
        basename = os.path.basename(vault_path)
        if basename.endswith('.vault') and basename != 'session.vault':
            # Extract the vault ID (remove .vault extension)
            # Example: "vault_abc123.vault" -> "vault_abc123"
            return basename[:-6]  # Remove '.vault'
        
        return None
    
    def get_vault_path(self, vault_name: str) -> Optional[str]:
        """Get absolute file path for a vault by name"""
        registry = self.load_vault_registry()
        
        # Special case: "default" always resolves to config/session.vault
        if vault_name == "default":
            default_path = os.path.join(self.app_dir, "config", "session.vault")
            return default_path
        
        vault = registry.get("vaults", {}).get(vault_name)
        if vault:
            return vault.get("path")
        return None
    
    def set_vault_path(self, vault_name: str, absolute_path: str) -> None:
        """Set or update the path for a vault"""
        registry = self.load_vault_registry()
        
        if "vaults" not in registry:
            registry["vaults"] = {}
        
        # For default vault, store relative path
        if vault_name == "default":
            # Convert to relative path from app_dir
            rel_path = os.path.relpath(absolute_path, self.app_dir)
            registry["vaults"][vault_name] = {
                "path": rel_path,
                "updated": datetime.now().isoformat()
            }
        else:
            registry["vaults"][vault_name] = {
                "path": absolute_path,
                "updated": datetime.now().isoformat()
            }
        
        self._registry_cache = registry
        self.save_vault_registry()
    
    def remove_vault(self, vault_name: str) -> bool:
        """Remove a vault from the registry (does not delete the file)"""
        registry = self.load_vault_registry()
        
        if vault_name == "default":
            print("Cannot remove default vault")
            return False
        
        if "vaults" in registry and vault_name in registry["vaults"]:
            del registry["vaults"][vault_name]
            self._registry_cache = registry
            self.save_vault_registry()
            return True
        return False
    
    def list_vaults(self) -> Dict[str, str]:
        """List all vaults with their paths"""
        registry = self.load_vault_registry()
        result = {}
        
        # Always include default vault (even if not in registry)
        default_path = os.path.join(self.app_dir, "config", "session.vault")
        result["default"] = default_path
        
        for name, info in registry.get("vaults", {}).items():
            result[name] = info.get("path")
        
        return result
    
    # ========================================================================
    # VAULT FILE I/O METHODS
    # ========================================================================
    
    def create_vault_file(self, vault_name: str, directory: str) -> str:
        """Create a new empty vault file and return its path"""
        # Ensure directory exists
        os.makedirs(directory, exist_ok=True)
        
        # Determine filename and path
        if vault_name == "default":
            filename = "session.vault"
            vault_path = os.path.join(directory, filename)
            # Store relative path in registry
            rel_path = os.path.relpath(vault_path, self.app_dir)
            self.set_vault_path(vault_name, rel_path)
        else:
            filename = f"{vault_name}.vault"
            vault_path = os.path.join(directory, filename)
            self.set_vault_path(vault_name, vault_path)
        
        # Create empty vault structure if it doesn't exist
        if not os.path.exists(vault_path):
            vault_data = {
                "version": 2,
                "entries": {}
            }
            with open(vault_path, 'w') as f:
                json.dump(vault_data, f)
        
        return vault_path
    
    import struct
    import os

    def read_vault_file(self, vault_path: str) -> Dict:
        """Read a binary vault file and return its data"""
        if not os.path.exists(vault_path):
            return {"version": 2, "entries": {}}
        
        try:
            with open(vault_path, 'rb') as f:
                # Read version
                version_data = f.read(4)
                if len(version_data) < 4:
                    return {"version": 2, "entries": {}}
                version = struct.unpack('>I', version_data)[0]
                
                if version != 2:
                    return {"version": 2, "entries": {}}
                
                result = {"version": version, "entries": {}}
                
                # Read number of entries
                num_entries_data = f.read(4)
                if len(num_entries_data) < 4:
                    return result
                num_entries = struct.unpack('>I', num_entries_data)[0]
                
                for _ in range(num_entries):
                    # Read entry UUID length
                    uuid_len_data = f.read(4)
                    if len(uuid_len_data) < 4:
                        break
                    uuid_len = struct.unpack('>I', uuid_len_data)[0]
                    
                    # Read entry UUID
                    uuid_bytes = f.read(uuid_len)
                    if len(uuid_bytes) < uuid_len:
                        break
                    entry_uuid = uuid_bytes.decode('utf-8')
                    
                    # Read notebook_id length
                    nb_len_data = f.read(4)
                    if len(nb_len_data) < 4:
                        break
                    nb_len = struct.unpack('>I', nb_len_data)[0]
                    
                    # Read notebook_id
                    nb_bytes = f.read(nb_len)
                    if len(nb_bytes) < nb_len:
                        break
                    notebook_id = nb_bytes.decode('utf-8')
                    
                    # Read timestamp
                    ts_data = f.read(8)
                    if len(ts_data) < 8:
                        break
                    timestamp = struct.unpack('>Q', ts_data)[0]
                    
                    # Read nonce length (should be 12)
                    nonce_len_data = f.read(4)
                    if len(nonce_len_data) < 4:
                        break
                    nonce_len = struct.unpack('>I', nonce_len_data)[0]
                    
                    # Read nonce
                    nonce = f.read(nonce_len)
                    if len(nonce) < nonce_len:
                        break
                    
                    # Read encrypted_keys length
                    key_len_data = f.read(4)
                    if len(key_len_data) < 4:
                        break
                    key_len = struct.unpack('>I', key_len_data)[0]
                    
                    # Read encrypted_keys
                    encrypted_keys = f.read(key_len)
                    if len(encrypted_keys) < key_len:
                        break
                    
                    result["entries"][entry_uuid] = {
                        "notebook_id": notebook_id,
                        "timestamp": timestamp,
                        "nonce": nonce.hex(),
                        "encrypted_keys": encrypted_keys.hex()
                    }
                
                return result
                
        except Exception as e:
            print(f"Error reading vault file {vault_path}: {e}")
            return {"version": 2, "entries": {}}

    def write_vault_file(self, vault_path: str, data: Dict) -> bool:
        """Write data to a binary vault file atomically"""
        temp_path = vault_path + '.tmp'
        
        try:
            with open(temp_path, 'wb') as f:
                # Write version
                f.write(struct.pack('>I', data.get("version", 2)))
                
                entries = data.get("entries", {})
                # Write number of entries
                f.write(struct.pack('>I', len(entries)))
                
                for entry_uuid, entry_data in entries.items():
                    # Write entry UUID
                    uuid_bytes = entry_uuid.encode('utf-8')
                    f.write(struct.pack('>I', len(uuid_bytes)))
                    f.write(uuid_bytes)
                    
                    # Write notebook_id
                    nb_bytes = entry_data["notebook_id"].encode('utf-8')
                    f.write(struct.pack('>I', len(nb_bytes)))
                    f.write(nb_bytes)
                    
                    # Write timestamp
                    f.write(struct.pack('>Q', entry_data["timestamp"]))
                    
                    # Write nonce (convert from hex to bytes)
                    nonce_bytes = bytes.fromhex(entry_data["nonce"])
                    f.write(struct.pack('>I', len(nonce_bytes)))
                    f.write(nonce_bytes)
                    
                    # Write encrypted_keys (convert from hex to bytes)
                    key_bytes = bytes.fromhex(entry_data["encrypted_keys"])
                    f.write(struct.pack('>I', len(key_bytes)))
                    f.write(key_bytes)
            
            os.rename(temp_path, vault_path)
            return True
            
        except Exception as e:
            print(f"Error writing vault file: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return False
    
    def add_entry_to_vault(self, vault_path: str, entry_uuid: str, entry_data: Dict) -> bool:
        """Add or update an entry in a vault file"""
        #
        #import traceback
        #print(f"\n🔴🔴🔴 [ADD_ENTRY_TO_VAULT] Called for UUID: {entry_uuid}")
        #print(f"   Stack trace:")
        #for frame in traceback.extract_stack()[-5:-1]:
        #    print(f"     {frame.filename}:{frame.lineno} in {frame.name}")
        #print(f"   Entry data notebook_id: {entry_data.get('notebook_id')}")
        
        vault_data = self.read_vault_file(vault_path)
    
        if "entries" not in vault_data:
            vault_data["entries"] = {}
        
        vault_data["entries"][entry_uuid] = entry_data
        return self.write_vault_file(vault_path, vault_data)
    
    def get_entry_from_vault(self, vault_path: str, entry_uuid: str) -> Optional[Dict]:
        """Get a single entry from a vault file by UUID"""
        vault_data = self.read_vault_file(vault_path)
        return vault_data.get("entries", {}).get(entry_uuid)
    
    def remove_entry_from_vault(self, vault_path: str, entry_uuid: str) -> bool:
        """Remove an entry from a vault file by UUID"""
        vault_data = self.read_vault_file(vault_path)
        
        if "entries" in vault_data and entry_uuid in vault_data["entries"]:
            del vault_data["entries"][entry_uuid]
            return self.write_vault_file(vault_path, vault_data)
        
        return False
    
    def copy_entry_to_vault(self, source_vault_path: str, dest_vault_path: str, 
                            entry_uuid: str) -> bool:
        """Copy an entry from one vault to another (preserves UUID and data)"""
        entry_data = self.get_entry_from_vault(source_vault_path, entry_uuid)
        if not entry_data:
            return False
        
        return self.add_entry_to_vault(dest_vault_path, entry_uuid, entry_data)
    
    def entry_exists_in_vault(self, vault_path: str, entry_uuid: str) -> bool:
        """Check if an entry exists in a vault"""
        return self.get_entry_from_vault(vault_path, entry_uuid) is not None
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def reload(self):
        """Force reload of vault registry cache"""
        self._registry_cache = None
    
    def ensure_default_vault(self) -> str:
        """Ensure default vault exists and return its path"""
        default_dir = os.path.join(self.app_dir, "config")
        os.makedirs(default_dir, exist_ok=True)
        
        default_path = os.path.join(default_dir, "session.vault")
        
        if not os.path.exists(default_path):
            self.create_vault_file("default", default_dir)
        
        return default_path