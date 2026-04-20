#!/usr/bin/env python3
"""
Dev Vault - Zero-Trust Binary Storage for dev_dashboard GitHub Token
"""

import os
import sys
import time
import struct
import hashlib
from typing import Optional, Dict, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DevVault:
    def __init__(self, app_dir: Optional[str] = None):
        if app_dir is None:
            app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.config_dir = os.path.join(app_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.vault_path = os.path.join(self.config_dir, "dev.vault")
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
    
    def store_token(self, token: str, username: str = "") -> bool:
        try:
            fingerprint = self._get_system_fingerprint()
            vault = self._read_vault()
            
            timestamp = time.time_ns()
            data = self._build_encrypted_data(token, username)
            key = self._derive_key(timestamp, fingerprint)
            nonce = os.urandom(12)
            encrypted_blob = self._encrypt(data, key, nonce)
            
            vault["dev_token"] = [{
                "timestamp": timestamp,
                "nonce": nonce,
                "encrypted_blob": encrypted_blob,
                "active": True,
                "created": timestamp
            }]
            
            self._write_vault(vault)
            return True
            
        except Exception:
            return False
    
    def _build_encrypted_data(self, token: str, username: str) -> bytes:
        data = b""
        
        b = username.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        b = token.encode('utf-8')
        data += struct.pack('>I', len(b))
        data += b
        
        return data
    
    def _parse_encrypted_data(self, data: bytes) -> dict:
        offset = 0
        
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        username = data[offset:offset+length].decode('utf-8')
        offset += length
        
        length = struct.unpack('>I', data[offset:offset+4])[0]
        offset += 4
        token = data[offset:offset+length].decode('utf-8')
        
        return {"username": username, "token": token}
    
    def get_token(self) -> Optional[str]:
        try:
            fingerprint = self._get_system_fingerprint()
            vault = self._read_vault()
            entries = vault.get("dev_token", [])
            
            if not entries:
                return None
            
            for entry in entries:
                if entry.get("active"):
                    try:
                        key = self._derive_key(entry["timestamp"], fingerprint)
                        decrypted = self._decrypt(entry["encrypted_blob"], key, entry["nonce"])
                        result = self._parse_encrypted_data(decrypted)
                        return result["token"]
                    except Exception:
                        entry["active"] = False
                        self._write_vault(vault)
                        break
            
            for entry in entries:
                try:
                    key = self._derive_key(entry["timestamp"], fingerprint)
                    decrypted = self._decrypt(entry["encrypted_blob"], key, entry["nonce"])
                    result = self._parse_encrypted_data(decrypted)
                    entry["active"] = True
                    self._write_vault(vault)
                    return result["token"]
                except Exception:
                    continue
            
            return None
            
        except Exception:
            return None
    
    def delete_token(self) -> bool:
        try:
            vault = self._read_vault()
            if "dev_token" in vault:
                del vault["dev_token"]
                self._write_vault(vault)
            return True
        except Exception:
            return False
    
    def _read_vault(self) -> Dict[str, List[Dict]]:
        if self._vault_cache is not None:
            return self._vault_cache
        
        if not os.path.exists(self.vault_path):
            self._vault_cache = {}
            return self._vault_cache
        
        try:
            with open(self.vault_path, 'rb') as f:
                version_data = f.read(4)
                if len(version_data) < 4:
                    self._vault_cache = {}
                    return self._vault_cache
                
                version = struct.unpack('>I', version_data)[0]
                if version != 4:
                    self._vault_cache = {}
                    return self._vault_cache
                
                result = {}
                
                while True:
                    key_len_data = f.read(4)
                    if len(key_len_data) < 4:
                        break
                    key_len = struct.unpack('>I', key_len_data)[0]
                    
                    key_bytes = f.read(key_len)
                    if len(key_bytes) < key_len:
                        break
                    key = key_bytes.decode('utf-8')
                    
                    num_entries_data = f.read(4)
                    if len(num_entries_data) < 4:
                        break
                    num_entries = struct.unpack('>I', num_entries_data)[0]
                    
                    entries = []
                    for _ in range(num_entries):
                        ts_data = f.read(8)
                        if len(ts_data) < 8:
                            break
                        timestamp = struct.unpack('>Q', ts_data)[0]
                        
                        nonce = f.read(12)
                        if len(nonce) < 12:
                            break
                        
                        len_data = f.read(4)
                        if len(len_data) < 4:
                            break
                        blob_len = struct.unpack('>I', len_data)[0]
                        
                        encrypted_blob = f.read(blob_len)
                        if len(encrypted_blob) < blob_len:
                            break
                        
                        active_byte = f.read(1)
                        active = bool(active_byte[0]) if active_byte else False
                        
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
                    
                    result[key] = entries
                
                self._vault_cache = result
                return self._vault_cache
                
        except Exception:
            self._vault_cache = {}
            return self._vault_cache
    
    def _write_vault(self, vault: Dict[str, List[Dict]]) -> None:
        temp_path = self.vault_path + '.tmp'
        
        try:
            with open(temp_path, 'wb') as f:
                f.write(struct.pack('>I', 4))
                
                for key, entries in vault.items():
                    key_bytes = key.encode('utf-8')
                    f.write(struct.pack('>I', len(key_bytes)))
                    f.write(key_bytes)
                    f.write(struct.pack('>I', len(entries)))
                    
                    for entry in entries:
                        f.write(struct.pack('>Q', entry["timestamp"]))
                        f.write(entry["nonce"])
                        f.write(struct.pack('>I', len(entry["encrypted_blob"])))
                        f.write(entry["encrypted_blob"])
                        f.write(struct.pack('>B', 1 if entry.get("active") else 0))
                        f.write(struct.pack('>Q', entry.get("created", entry["timestamp"])))
            
            os.rename(temp_path, self.vault_path)
            self._vault_cache = vault
            
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise