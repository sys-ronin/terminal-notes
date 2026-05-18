#!/usr/bin/env python3
"""
Session Key Vault - Transparent vault-backed dictionary for crypto keys
"""

import os
import sys
from typing import Optional


class SessionKeyVault(dict):
    def __init__(self, manager):
        self.manager = manager
        self._cache = {}  # RAM cache for unlocked notebooks
        super().__init__()
    
    def clear_cache(self, notebook_id=None):
        """Clear cache for a specific notebook or all"""
        if notebook_id:
            if notebook_id in self._cache:
                del self._cache[notebook_id]
        else:
            self._cache.clear()
    
    def __getitem__(self, notebook_id):
        # Check RAM cache first (unlocked notebooks)
        if notebook_id in self._cache:
            # Verify vault still exists (cache validation)
            vault_path = self.manager._get_vault_path(notebook_id)
            if vault_path and os.path.exists(vault_path):
                return self._cache[notebook_id]
            else:
                # Vault missing - invalidate cache
                del self._cache[notebook_id]
        
        # Not in cache or cache invalidated - read from vault (unlock)
        crypto = self.manager._get_crypto_from_vault(notebook_id)
        if crypto:
            # Store in RAM cache for future access
            self._cache[notebook_id] = crypto
            return crypto
        
        raise KeyError(notebook_id)
    
    def __setitem__(self, notebook_id, crypto):
        # Store in RAM cache
        self._cache[notebook_id] = crypto
        # Write to vault (replaces existing entry, same UUID)
        self.manager._write_crypto_to_vault(notebook_id, crypto)
    
    def __contains__(self, notebook_id):
        # Check if keys exist in vault (locked but has keys)
        return self.manager._vault_has_keys(notebook_id)
    
    def get(self, notebook_id, default=None):
        try:
            return self[notebook_id]
        except KeyError:
            return default
    
    def __delitem__(self, notebook_id):
        # Remove from RAM cache (lock the notebook)
        if notebook_id in self._cache:
            del self._cache[notebook_id]
        # DO NOT delete from vault - keys remain for future unlocks
    
    def pop(self, notebook_id, default=None):
        """Remove from cache only (lock), return cached value if exists"""
        result = self._cache.pop(notebook_id, default)
        # DO NOT delete from vault
        return result
    
    def clear(self):
        """Clear RAM cache only (lock all notebooks)"""
        self._cache.clear()
        # DO NOT clear vault
    
    def keys(self):
        """Return notebook IDs that are currently unlocked (in RAM cache)"""
        return self._cache.keys()
    
    def values(self):
        """Return crypto objects for unlocked notebooks"""
        return self._cache.values()
    
    def items(self):
        """Return (notebook_id, crypto) for unlocked notebooks"""
        return self._cache.items()
    
    def is_unlocked(self, notebook_id):
        """Check if notebook is currently unlocked (in RAM)"""
        return notebook_id in self._cache
    
    def lock(self, notebook_id):
        """Lock a notebook (remove from RAM cache, update registry)"""
        if notebook_id in self._cache:
            del self._cache[notebook_id]
        # Registry update is handled by caller

    def unlock(self, notebook_id, crypto):
        """Unlock a notebook (store in RAM cache)"""
        self._cache[notebook_id] = crypto