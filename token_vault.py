#!/usr/bin/env python3
"""
Token Vault - Zero-Trust Binary Storage for GitHub Tokens
"""

import os
import sys
import time
import struct
import hashlib
from typing import Optional, Dict, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class TokenVault:
    def __init__(self, app_dir: Optional[str] = None):
        if app_dir is None:
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.config_dir = os.path.join(app_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.vault_path = os.path.join(self.config_dir, "token.vault")
        self._system_fingerprint = None
        self._vault_cache = None
    
    def _get_system_fingerprint(self) -> bytes:
        if self._system_fingerprint is None:
            self._system_fingerprint = self._generate_system_fingerprint()
        return self._system_fingerprint
    
    def _generate_system_fingerprint(self) -> bytes:
        import platform
        import subprocess
        
        components = []
        
        if sys.platform.startswith('linux'):
            try:
                with open('/etc/machine-id', 'r') as f:
                    components.append(f.read().strip())
            except:
                pass
        elif sys.platform == 'darwin':
            try:
                result = subprocess.run(
                    ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'IOPlatformUUID' in line:
                        components.append(line.split('=')[1].strip().strip('"'))
                        break
            except:
                pass
        elif sys.platform == 'win32':
            try:
                result = subprocess.run(
                    ['reg', 'query', 'HKLM\\SOFTWARE\\Microsoft\\Cryptography', '/v', 'MachineGuid'],
                    capture_output=True, text=True
                )
                for line in result.stdout.split('\n'):
                    if 'MachineGuid' in line:
                        components.append(line.split()[-1])
                        break
            except:
                pass
        
        components.extend([
            platform.node(),
            platform.processor(),
            str(os.getuid()) if hasattr(os, 'getuid') else '0',
            platform.system(),
            platform.release(),
        ])
        
        combined = '|'.join(str(c) for c in components if c)
        return hashlib.sha256(combined.encode('utf-8')).digest()
    
    def _derive_key(self, timestamp: int, fingerprint: bytes) -> bytes:
        key_material = str(timestamp).encode() + fingerprint
        return hashlib.sha256(key_material).digest()
    
    def _encrypt(self, plaintext: bytes, key: bytes, nonce: bytes) -> bytes:
        aesgcm = AESGCM(key)
        return aesgcm.encrypt(nonce, plaintext, None)
    
    def _decrypt(self, ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def store_token(self, account_id: str, username: str, platform: str, host: str,
                    api_url: str, token: str, linked_notebooks: list = None) -> bool:
        """Store full account data for current machine"""
        try:
            fingerprint = self._get_system_fingerprint()
            
            # Read existing vault (will create empty if doesn't exist)
            vault = self._read_vault()
            entries = vault.get(account_id, [])
            
            # Remove existing active entry
            entries = [e for e in entries if not e.get("active")]
            
            timestamp = time.time_ns()
            created = timestamp
            
            # Build encrypted data blob
            data = self._build_encrypted_data(username, platform, host, api_url, token, linked_notebooks or [])
            
            key = self._derive_key(timestamp, fingerprint)
            nonce = os.urandom(12)
            encrypted_blob = self._encrypt(data, key, nonce)
            
            entries.append({
                "timestamp": timestamp,
                "nonce": nonce,
                "encrypted_blob": encrypted_blob,
                "active": True,
                "created": created
            })
            
            vault[account_id] = entries
            self._write_vault(vault)
            return True
            
        except Exception as e:
            print(f"TokenVault store error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _build_encrypted_data(self, username: str, platform: str, host: str,
                               api_url: str, token: str, linked_notebooks: list) -> bytes:
        """Build binary blob from account data"""
        data = b""
        
        # username
        b = username.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        # platform
        b = platform.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        # host
        b = host.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        # api_url
        b = api_url.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        # token
        b = token.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        # linked notebooks
        data += struct.pack('>I', len(linked_notebooks))
        for nb_id in linked_notebooks:
            b = nb_id.encode('utf-8')
            data += struct.pack('>I', len(b))
            data += b
        
        return data
    
    def _parse_encrypted_data(self, data: bytes) -> dict:
        """Parse binary blob back to account data"""
        offset = 0
        
        # username
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        username = data[offset:offset+length].decode('utf-8')
        offset += length
        
        # platform
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        platform = data[offset:offset+length].decode('utf-8')
        offset += length
        
        # host
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        host = data[offset:offset+length].decode('utf-8')
        offset += length
        
        # api_url
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        api_url = data[offset:offset+length].decode('utf-8')
        offset += length
        
        # token
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        token = data[offset:offset+length].decode('utf-8')
        offset += length
        
        # linked notebooks
        num = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        linked_notebooks = []
        for _ in range(num):
            length = struct.unpack('>I', data[offset:offset+4])[0]
            offset += 4
            nb_id = data[offset:offset+length].decode('utf-8')
            offset += length
            linked_notebooks.append(nb_id)
        
        return {
            "username": username,
            "platform": platform,
            "host": host,
            "api_url": api_url,
            "token": token,
            "linked_notebooks": linked_notebooks
        }
    
    def get_full_account(self, account_id: str) -> Optional[dict]:
        """Retrieve full account data for current machine"""
        try:
            fingerprint = self._get_system_fingerprint()
            vault = self._read_vault()
            entries = vault.get(account_id, [])
            
            if not entries:
                return None
            
            # Try active entry
            for entry in entries:
                if entry.get("active"):
                    try:
                        key = self._derive_key(entry["timestamp"], fingerprint)
                        decrypted = self._decrypt(entry["encrypted_blob"], key, entry["nonce"])
                        result = self._parse_encrypted_data(decrypted)
                        result["created"] = entry.get("created", entry["timestamp"])
                        return result
                    except Exception:
                        entry["active"] = False
                        self._write_vault(vault)
                        break
            
            # Try all entries
            for entry in entries:
                try:
                    key = self._derive_key(entry["timestamp"], fingerprint)
                    decrypted = self._decrypt(entry["encrypted_blob"], key, entry["nonce"])
                    result = self._parse_encrypted_data(decrypted)
                    result["created"] = entry.get("created", entry["timestamp"])
                    entry["active"] = True
                    self._write_vault(vault)
                    return result
                except Exception:
                    continue
            
            return None
            
        except Exception as e:
            print(f"TokenVault get error: {e}")
            return None
    
    def get_token(self, account_id: str) -> Optional[str]:
        """Retrieve only the token (backward compatibility)"""
        result = self.get_full_account(account_id)
        return result["token"] if result else None
    
    def list_accounts(self) -> List[str]:
        """List all account IDs in the vault"""
        vault = self._read_vault()
        return list(vault.keys())
    
    def remove_token(self, account_id: str) -> bool:
        """Remove all entries for this account"""
        try:
            vault = self._read_vault()
            if account_id in vault:
                del vault[account_id]
                self._write_vault(vault)
            return True
        except Exception:
            return False
    
    def _read_vault(self) -> Dict[str, List[Dict]]:
        """Read entire binary vault file - creates new if doesn't exist"""
        if self._vault_cache is not None:
            return self._vault_cache
        
        # If file doesn't exist, return empty dict (will create on first write)
        if not os.path.exists(self.vault_path):
            self._vault_cache = {}
            return self._vault_cache
        
        try:
            with open(self.vault_path, 'rb') as f:
                # Read version
                version_data = f.read(4)
                if len(version_data) < 4:
                    self._vault_cache = {}
                    return self._vault_cache
                
                version = struct.unpack('>I', version_data)[0]
                if version != 4:
                    # Wrong version, start fresh
                    self._vault_cache = {}
                    return self._vault_cache
                
                result = {}
                
                while True:
                    # Read account ID length
                    id_len_data = f.read(4)
                    if len(id_len_data) < 4:
                        break
                    id_len = struct.unpack('>I', id_len_data)[0]
                    
                    # Read account ID
                    account_id_bytes = f.read(id_len)
                    if len(account_id_bytes) < id_len:
                        break
                    account_id = account_id_bytes.decode('utf-8')
                    
                    # Read number of entries
                    num_entries_data = f.read(4)
                    if len(num_entries_data) < 4:
                        break
                    num_entries = struct.unpack('>I', num_entries_data)[0]
                    
                    entries = []
                    for _ in range(num_entries):
                        # Timestamp (8 bytes)
                        ts_data = f.read(8)
                        if len(ts_data) < 8:
                            break
                        timestamp = struct.unpack('>Q', ts_data)[0]
                        
                        # Nonce (12 bytes)
                        nonce = f.read(12)
                        if len(nonce) < 12:
                            break
                        
                        # Encrypted blob length (4 bytes)
                        len_data = f.read(4)
                        if len(len_data) < 4:
                            break
                        blob_len = struct.unpack('>I', len_data)[0]
                        
                        # Encrypted blob
                        encrypted_blob = f.read(blob_len)
                        if len(encrypted_blob) < blob_len:
                            break
                        
                        # Active flag (1 byte)
                        active_byte = f.read(1)
                        active = bool(active_byte[0]) if active_byte else False
                        
                        # Created timestamp (8 bytes) - may not exist in older files
                        created_data = f.read(8)
                        if len(created_data) == 8:
                            created = struct.unpack('>Q', created_data)[0]
                        else:
                            created = timestamp
                        
                        entries.append({
                            "timestamp": timestamp,
                            "nonce": nonce,
                            "encrypted_blob": encrypted_blob,
                            "active": active,
                            "created": created
                        })
                    
                    result[account_id] = entries
                
                self._vault_cache = result
                return self._vault_cache
                
        except Exception as e:
            print(f"TokenVault read error: {e}")
            # On error, start fresh
            self._vault_cache = {}
            return self._vault_cache
    
    def _write_vault(self, vault: Dict[str, List[Dict]]) -> None:
        """Write entire binary vault file"""
        temp_path = self.vault_path + '.tmp'
        
        try:
            with open(temp_path, 'wb') as f:
                # Version (4 bytes)
                f.write(struct.pack('>I', 4))
                
                for account_id, entries in vault.items():
                    # Account ID
                    id_bytes = account_id.encode('utf-8')
                    f.write(struct.pack('>I', len(id_bytes)))
                    f.write(id_bytes)
                    
                    # Number of entries
                    f.write(struct.pack('>I', len(entries)))
                    
                    for entry in entries:
                        # Timestamp
                        f.write(struct.pack('>Q', entry["timestamp"]))
                        # Nonce
                        f.write(entry["nonce"])
                        # Encrypted blob length and data
                        f.write(struct.pack('>I', len(entry["encrypted_blob"])))
                        f.write(entry["encrypted_blob"])
                        # Active flag
                        f.write(struct.pack('>B', 1 if entry.get("active") else 0))
                        # Created timestamp
                        f.write(struct.pack('>Q', entry.get("created", entry["timestamp"])))
            
            # Atomic rename
            os.rename(temp_path, self.vault_path)
            self._vault_cache = vault
            
        except Exception as e:
            print(f"TokenVault write error: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    def link_notebook(self, account_id: str, notebook_id: str) -> bool:
        """Link a notebook to an account"""
        try:
            # Get current account data
            account_data = self.get_full_account(account_id)
            if not account_data:
                return False
            
            # Get current linked notebooks
            linked = account_data.get("linked_notebooks", [])
            
            # Add if not already there
            if notebook_id not in linked:
                linked.append(notebook_id)
            
            # Re-store the account with updated linked notebooks
            return self.store_token(
                account_id,
                account_data["username"],
                account_data["platform"],
                account_data["host"],
                account_data["api_url"],
                account_data["token"],
                linked
            )
            
        except Exception as e:
            print(f"TokenVault link_notebook error: {e}")
            return False


    def unlink_notebook(self, account_id: str, notebook_id: str) -> bool:
        """Unlink a notebook from an account"""
        try:
            # Get current account data
            account_data = self.get_full_account(account_id)
            if not account_data:
                return False
            
            # Get current linked notebooks
            linked = account_data.get("linked_notebooks", [])
            
            # Remove if present
            if notebook_id in linked:
                linked.remove(notebook_id)
            
            # Re-store the account with updated linked notebooks
            return self.store_token(
                account_id,
                account_data["username"],
                account_data["platform"],
                account_data["host"],
                account_data["api_url"],
                account_data["token"],
                linked
            )
            
        except Exception as e:
            print(f"TokenVault unlink_notebook error: {e}")
            return False


    def get_linked_notebooks(self, account_id: str) -> List[str]:
        """Get all notebook IDs linked to an account"""
        account_data = self.get_full_account(account_id)
        if account_data:
            return account_data.get("linked_notebooks", [])
        return []