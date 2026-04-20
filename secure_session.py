#!/usr/bin/env python3
"""
Secure Session Storage - Zero-Trust Binary Vault
No fingerprints stored. Active flag for O(1) lookup.
Stores notebook IDs as strings (supports timestamp IDs and UUIDs).
"""
import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import os
import sys
import socket
import time
import struct
import hashlib
from typing import Optional, Tuple, Dict, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SecureSessionStorage:
    """
    Zero-trust binary vault for storing notebook keys.
    No outer encryption. Fingerprints never stored.
    Each notebook has its own list of entries (one per machine).
    Active flag indicates current machine's entry.
    """
    
    def __init__(self, app_dir: Optional[str] = None):
        """Initialize secure session storage"""
        if app_dir is None:
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.config_dir = os.path.join(app_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        self.vault_path = os.path.join(self.config_dir, "session.vault")
        
        self._system_fingerprint = None
        self._vault_cache = None
    
    # ========================================================================
    # Public API
    # ========================================================================
    
    def store_keys(self, notebook_id: str, password_key: bytes, phrase_key: bytes) -> bool:
        try:
            import hashlib
            
            # Ensure keys are 32 bytes (AES-256 requirement)
            if len(password_key) != 32:
                password_key = hashlib.sha256(password_key).digest()
            if len(phrase_key) != 32:
                phrase_key = hashlib.sha256(phrase_key).digest()
            
            fingerprint = self._get_system_fingerprint()
            vault = self._read_vault()
            system_name = socket.gethostname()  # ← ADD THIS
            
            entries = vault.get(notebook_id, [])
            
            # Find existing entry for this machine (by successful decryption)
            found_index = -1
            for i, entry in enumerate(entries):
                try:
                    key = self._derive_entry_key(entry["timestamp"], fingerprint)
                    self._decrypt(entry["encrypted_keys"], key, entry["nonce"])
                    found_index = i
                    break
                except Exception:
                    continue
            
            # Create new entry with new timestamp
            timestamp = time.time_ns()
            key = self._derive_entry_key(timestamp, fingerprint)
            nonce = os.urandom(12)
            
            plaintext = password_key + b":" + phrase_key
            encrypted_keys = self._encrypt(plaintext, key, nonce)
            
            new_entry = {
                "timestamp": timestamp,
                "nonce": nonce,
                "encrypted_keys": encrypted_keys,
                "active": True,
                "created": timestamp,
                "system_name": system_name  # ← ADD THIS
            }
            
            if found_index >= 0:
                # Replace existing entry for this machine
                entries[found_index] = new_entry
            else:
                # New machine - add entry
                entries.append(new_entry)
            
            vault[notebook_id] = entries
            self._write_vault(vault)
            return True
            
        except Exception as e:
            print(f"[DEBUG] store_keys error: {e}")
            return False
    
    def get_keys(self, notebook_id: str) -> Tuple[Optional[bytes], Optional[bytes]]:
        try:
            fingerprint = self._get_system_fingerprint()
            vault = self._read_vault()
            entries = vault.get(notebook_id, [])
            
            if not entries:
                return None, None
            
            for entry in entries:
                if entry.get("active"):
                    try:
                        key = self._derive_entry_key(entry["timestamp"], fingerprint)
                        encrypted_data = entry.get("encrypted_keys")
                        plaintext = self._decrypt(encrypted_data, key, entry["nonce"])
                        password_key, phrase_key = self._parse_keys(plaintext)
                        return password_key, phrase_key
                    except Exception:
                        entry["active"] = False
                        self._write_vault(vault)
                        break
            
            for entry in entries:
                try:
                    key = self._derive_entry_key(entry["timestamp"], fingerprint)
                    encrypted_data = entry.get("encrypted_keys")
                    plaintext = self._decrypt(encrypted_data, key, entry["nonce"])
                    password_key, phrase_key = self._parse_keys(plaintext)
                    entry["active"] = True
                    self._write_vault(vault)
                    return password_key, phrase_key
                except Exception:
                    continue
            
            return None, None
            
        except Exception:
            return None, None
    
    def get_active_entry(self, notebook_id: str) -> Optional[Dict]:
        """Get the active entry for a notebook"""
        vault = self._read_vault()
        entries = vault.get(notebook_id, [])
        
        for entry in entries:
            if entry.get("active"):
                return entry
        return None
    
    def get_keys_with_verification(self, notebook_id: str, folder_path: str, folder_name: str):
        from crypto import derive_key
        from getpass import getpass
        import hashlib
        
        password_key, phrase_key = self.get_keys(notebook_id)
        
        if password_key is not None and phrase_key is not None:
            attempts = 0
            max_attempts = 3
            
            while attempts < max_attempts:
                remaining = max_attempts - attempts
                password = getpass(f"Password ({remaining} attempts remaining): ")
                derived_key = derive_key(password, folder_name)
                
                if derived_key == password_key:
                    combined_key = hashlib.sha256(password_key + phrase_key).digest()
                    password_file = os.path.join(folder_path, ".tn_password")
                    
                    if os.path.exists(password_file):
                        try:
                            with open(password_file, 'rb') as f:
                                password_data = f.read()
                            
                            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                            aesgcm = AESGCM(combined_key)
                            nonce = password_data[:12]
                            ciphertext = password_data[12:]
                            aesgcm.decrypt(nonce, ciphertext, None)
                            return password_key, phrase_key
                        except Exception:
                            print("\n⚠ Password changed on another machine.")
                            print("   Please enter your recovery phrase to update this machine.\n")
                            return self._recover_with_phrase(notebook_id, folder_path, folder_name)
                    else:
                        return password_key, phrase_key
                
                attempts += 1
                if attempts < max_attempts:
                    print("Wrong password. Try again.")
            
            print("Too many failed attempts.")
            return None, None
        
        print("\n" + "=" * 50)
        print("This notebook has not been used on this machine before.")
        print("Please enter your RECOVERY PHRASE to unlock it.")
        print("=" * 50)
        
        return self._recover_with_phrase(notebook_id, folder_path, folder_name)


    def _recover_with_phrase(self, notebook_id: str, folder_path: str, folder_name: str):
        from crypto import Crypto, derive_key
        import json
        import os
        import hashlib
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        
        phrase = input("Recovery phrase: ")
        
        if not phrase:
            print("❌ No phrase entered.")
            return None, None
        
        phrase_key = derive_key(phrase, folder_name)
        
        # Ensure phrase_key is 32 bytes
        if len(phrase_key) != 32:
            phrase_key = hashlib.sha256(phrase_key).digest()
        
        # Verify .tn_test
        test_file = os.path.join(folder_path, ".tn_test")
        
        if not os.path.exists(test_file):
            print("❌ Notebook missing .tn_test. Cannot verify.")
            return None, None
        
        try:
            with open(test_file, 'rb') as f:
                test_data = f.read()
            
            temp_crypto = Crypto(None, phrase_key, folder_name)
            temp_crypto.decrypt(test_data)
            print("✓ Recovery phrase verified.")
        except Exception:
            print("❌ Wrong recovery phrase.")
            return None, None
        
        # Decrypt .tn_recovery
        recovery_file = os.path.join(folder_path, ".tn_recovery")
        
        if not os.path.exists(recovery_file):
            print("❌ Notebook missing .tn_recovery. Cannot recover.")
            return None, None
        
        try:
            with open(recovery_file, 'rb') as f:
                recovery_data = f.read()
            
            temp_crypto = Crypto(None, phrase_key, folder_name)
            json_str = temp_crypto.decrypt(recovery_data)
            recovery_info = json.loads(json_str)
            password_key = bytes.fromhex(recovery_info["password_key"])
            
            # Ensure password_key is 32 bytes
            if len(password_key) != 32:
                password_key = hashlib.sha256(password_key).digest()
            
            print("✓ Password key recovered from .tn_recovery.")
        except Exception:
            print("❌ Failed to decrypt .tn_recovery.")
            return None, None
        
        # Verify .tn_password
        password_file = os.path.join(folder_path, ".tn_password")
        
        if not os.path.exists(password_file):
            print("⚠ No .tn_password file. Skipping verification.")
        else:
            try:
                combined_key = hashlib.sha256(password_key + phrase_key).digest()
                with open(password_file, 'rb') as f:
                    password_data = f.read()
                
                aesgcm = AESGCM(combined_key)
                nonce = password_data[:12]
                ciphertext = password_data[12:]
                aesgcm.decrypt(nonce, ciphertext, None)
                print("✓ Two-factor verification passed.")
            except Exception:
                print("❌ Verification failed. Keys do not match .tn_password.")
                return None, None
        
        # Store keys
        self.store_keys(notebook_id, password_key, phrase_key)
        
        print("\n✓ This machine is now trusted.")
        print("  Future unlocks will require only your password.\n")
        
        return password_key, phrase_key
    
    def remove_session_key(self, notebook_id: str) -> bool:
        """Remove all entries for this notebook"""
        try:
            vault = self._read_vault()
            if notebook_id in vault:
                del vault[notebook_id]
                self._write_vault(vault)
            return True
        except Exception:
            return False
    
    def list_stored_notebooks(self) -> Dict[str, Dict]:
        """List all notebooks with stored entries"""
        result = {}
        vault = self._read_vault()
        
        for notebook_id, entries in vault.items():
            result[notebook_id] = {
                "entry_count": len(entries),
                "has_active": any(e.get("active") for e in entries)
            }
        
        return result
    
    def clear_all(self) -> None:
        """Clear all stored session data"""
        if os.path.exists(self.vault_path):
            os.remove(self.vault_path)
        self._vault_cache = None
    
    # ========================================================================
    # Internal Methods
    # ========================================================================
    
    def _get_system_fingerprint(self) -> bytes:
        """Generate system fingerprint at runtime. Never stored to disk."""
        if self._system_fingerprint is None:
            self._system_fingerprint = self._generate_system_fingerprint()
        return self._system_fingerprint
    
    def _generate_system_fingerprint(self) -> bytes:
        """Generate 32-byte fingerprint from hardware identifiers"""
        import platform
        import subprocess
        
        components = []
        
        if sys.platform.startswith('linux'):
            try:
                with open('/etc/machine-id', 'r') as f:
                    components.append(f.read().strip())
            except:
                pass
            try:
                with open('/sys/class/dmi/id/product_uuid', 'r') as f:
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
    
    def _derive_entry_key(self, timestamp: int, fingerprint: bytes) -> bytes:
        """Derive key from timestamp + fingerprint (no storage of either)"""
        key_material = str(timestamp).encode() + fingerprint
        return hashlib.sha256(key_material).digest()
    
    def _derive_key(self, timestamp: int, fingerprint: bytes) -> bytes:
        """Derive key from timestamp + fingerprint"""
        key_material = str(timestamp).encode() + fingerprint
        return hashlib.sha256(key_material).digest()
    
    def _encrypt(self, plaintext: bytes, key: bytes, nonce: bytes) -> bytes:
        """AES-GCM encryption"""
        aesgcm = AESGCM(key)
        return aesgcm.encrypt(nonce, plaintext, None)
    
    def _decrypt(self, ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    
    def _parse_keys(self, plaintext: bytes) -> Tuple[bytes, bytes]:
        """Parse plaintext into password_key and phrase_key (ensure 32 bytes each)"""
        import hashlib
        
        parts = plaintext.split(b':', 1)
        pw_key = parts[0]
        ph_key = parts[1] if len(parts) > 1 else parts[0]
        
        # Ensure keys are 32 bytes (AES-256 requirement)
        if len(pw_key) != 32:
            pw_key = hashlib.sha256(pw_key).digest()
        if len(ph_key) != 32:
            ph_key = hashlib.sha256(ph_key).digest()
        
        return pw_key, ph_key
    
    def set_custom_vault_path(self, vault_path):
        """Set a custom vault file path for this instance"""
        self.custom_vault_path = vault_path
        self.vault_path = vault_path
        self._vault_cache = None  # Clear cache

    def get_vault_path(self):
        """Get the current vault path"""
        return self.vault_path
    
    def _read_vault(self) -> Dict[str, List[Dict]]:
        """Read entire binary vault file"""
        if self._vault_cache is not None:
            return self._vault_cache
        
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
                # Allow both version 4 and 5
                if version not in [4, 5]:
                    self._vault_cache = {}
                    return self._vault_cache
                
                result = {}
                
                while True:
                    # Read notebook ID length
                    id_len_data = f.read(4)
                    if len(id_len_data) < 4:
                        break
                    id_len = struct.unpack('>I', id_len_data)[0]
                    
                    # Read notebook ID string
                    notebook_id_bytes = f.read(id_len)
                    if len(notebook_id_bytes) < id_len:
                        break
                    notebook_id = notebook_id_bytes.decode('utf-8')
                    
                    # Read number of entries
                    num_entries_data = f.read(4)
                    if len(num_entries_data) < 4:
                        break
                    num_entries = struct.unpack('>I', num_entries_data)[0]
                    
                    entries = []
                    for _ in range(num_entries):
                        # Read timestamp (8 bytes)
                        timestamp_data = f.read(8)
                        if len(timestamp_data) < 8:
                            break
                        timestamp = struct.unpack('>Q', timestamp_data)[0]
                        
                        # Read nonce (12 bytes)
                        nonce = f.read(12)
                        if len(nonce) < 12:
                            break
                        
                        # Read encrypted_keys length
                        length_data = f.read(4)
                        if len(length_data) < 4:
                            break
                        length = struct.unpack('>I', length_data)[0]
                        
                        # Read encrypted_keys
                        encrypted_keys = f.read(length)
                        if len(encrypted_keys) < length:
                            break
                        
                        # Read active flag (1 byte)
                        active_data = f.read(1)
                        active = bool(active_data[0]) if active_data else False
                        
                        # Read created timestamp (8 bytes) - exists in version 4 and 5
                        created_data = f.read(8)
                        if len(created_data) == 8:
                            created = struct.unpack('>Q', created_data)[0]
                        else:
                            created = timestamp
                        
                        # Read system_name (string length + data) - version 5 only
                        system_name = "unknown (legacy)"
                        if version >= 5:
                            sysname_len_data = f.read(4)
                            if len(sysname_len_data) == 4:
                                sysname_len = struct.unpack('>I', sysname_len_data)[0]
                                sysname_bytes = f.read(sysname_len)
                                if len(sysname_bytes) == sysname_len:
                                    system_name = sysname_bytes.decode('utf-8')
                        
                        entries.append({
                            "timestamp": timestamp,
                            "nonce": nonce,
                            "encrypted_keys": encrypted_keys,
                            "active": active,
                            "created": created,
                            "system_name": system_name
                        })
                    
                    result[notebook_id] = entries
                
                self._vault_cache = result
                return self._vault_cache
                
        except Exception as e:
            print(f"Error reading vault: {e}")
            self._vault_cache = {}
            return self._vault_cache
    
    def _write_vault(self, vault: Dict[str, List[Dict]]) -> None:
        """Write entire binary vault file atomically"""
        temp_path = self.vault_path + '.tmp'
        
        try:
            with open(temp_path, 'wb') as f:
                # Write version (bump to 5 for system_name support)
                f.write(struct.pack('>I', 5))
                
                for notebook_id, entries in vault.items():
                    # Write notebook ID length and string
                    id_bytes = notebook_id.encode('utf-8')
                    f.write(struct.pack('>I', len(id_bytes)))
                    f.write(id_bytes)
                    
                    # Write number of entries
                    f.write(struct.pack('>I', len(entries)))
                    
                    for entry in entries:
                        # Write timestamp (8 bytes)
                        f.write(struct.pack('>Q', entry["timestamp"]))
                        
                        # Write nonce (12 bytes)
                        f.write(entry["nonce"])
                        
                        # Write encrypted_keys length
                        f.write(struct.pack('>I', len(entry["encrypted_keys"])))
                        
                        # Write encrypted_keys
                        f.write(entry["encrypted_keys"])
                        
                        # Write active flag (1 byte)
                        f.write(struct.pack('>B', 1 if entry.get("active") else 0))
                        
                        # Write created timestamp (8 bytes)
                        f.write(struct.pack('>Q', entry.get("created", entry["timestamp"])))
                        
                        # Write system_name
                        sysname = entry.get("system_name", "unknown").encode('utf-8')
                        f.write(struct.pack('>I', len(sysname)))
                        f.write(sysname)
            
            # Atomic rename
            os.rename(temp_path, self.vault_path)
            self._vault_cache = vault
            
        except Exception as e:
            print(f"Error writing vault: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def list_entries(self, notebook_id: str) -> List[Dict]:
        """List all entries for a notebook (for trusted devices UI)"""
        vault = self._read_vault()
        entries = vault.get(notebook_id, [])
        
        result = []
        for entry in entries:
            result.append({
                "timestamp": entry.get("timestamp"),
                "created": entry.get("created", entry.get("timestamp")),
                "system_name": entry.get("system_name", "unknown"),
                "active": entry.get("active", False)
            })
        return result

    def remove_entry(self, notebook_id: str, timestamp: int) -> bool:
        """Remove a specific entry by timestamp (revoke trusted device)"""
        try:
            vault = self._read_vault()
            if notebook_id not in vault:
                return False
            
            entries = vault[notebook_id]
            # Filter out the entry with matching timestamp
            new_entries = [e for e in entries if e.get("timestamp") != timestamp]
            
            if len(new_entries) == len(entries):
                return False  # No entry removed
            
            if new_entries:
                vault[notebook_id] = new_entries
            else:
                del vault[notebook_id]
            
            self._write_vault(vault)
            return True
        except Exception:
            return False