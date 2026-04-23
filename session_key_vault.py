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
        self._cache = {}  # Session performance cache
        super().__init__()
    
    def clear_cache(self, notebook_id=None):
        """Clear cache for a specific notebook or all"""
        if notebook_id:
            if notebook_id in self._cache:
                del self._cache[notebook_id]
        else:
            self._cache.clear()
    
    def __getitem__(self, notebook_id):
        # Check cache only for performance, but ALWAYS validate
        if notebook_id in self._cache:
            # Verify cached crypto still valid (vault still exists)
            vault_path = self.manager._get_vault_path(notebook_id)
            if vault_path and os.path.exists(vault_path):
                return self._cache[notebook_id]
            else:
                # Vault missing - invalidate cache
                del self._cache[notebook_id]
        
        # Cache miss - read from vault
        crypto = self.manager._get_crypto_from_vault(notebook_id)
        if crypto:
            self._cache[notebook_id] = crypto
            return crypto
        
        raise KeyError(notebook_id)
    
    def __setitem__(self, notebook_id, crypto):
        self._cache[notebook_id] = crypto
        self.manager._write_crypto_to_vault(notebook_id, crypto)
    
    def __contains__(self, notebook_id):
        return notebook_id in self._cache or self.manager._vault_has_keys(notebook_id)
    
    def get(self, notebook_id, default=None):
        """Called when code does: session_keys.get(notebook_id)"""
        try:
            return self[notebook_id]
        except KeyError:
            return default
    
    def __delitem__(self, notebook_id):
        if notebook_id in self._cache:
            del self._cache[notebook_id]
        self.manager._delete_from_vault(notebook_id)
    
    def pop(self, notebook_id, default=None):
        """Called when code does: session_keys.pop(notebook_id)"""
        result = self.get(notebook_id, default)
        self.manager._delete_from_vault(notebook_id)
        return result
    
    def clear(self):
        """Called when code does: session_keys.clear()"""
        # Can't clear vault without knowing which notebooks
        # This is a limitation - individual del must be used
        pass
    
    def keys(self):
        """Return keys that have entries in vault"""
        # This is expensive - would need to scan all possible notebooks
        # Return empty for now
        return []
    
    def values(self):
        """Return values from vault"""
        return []
    
    def items(self):
        """Return items from vault"""
        return []