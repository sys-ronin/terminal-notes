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

VAULT_VERSION = 2

class SecureSessionStorage:
    """
    Zero-trust binary vault for storing notebook keys.
    No outer encryption. Fingerprints never stored.
    Each notebook has its own list of entries (one per machine).
    Active flag indicates current machine's entry.
    """
    
    def __init__(self, app_dir: Optional[str] = None, vault_path: Optional[str] = None):
        if app_dir is None:
            if getattr(sys, 'frozen', False):
                app_dir = os.path.dirname(sys.executable)
            else:
                app_dir = os.path.dirname(os.path.abspath(__file__))
        
        self.app_dir = app_dir
        self.config_dir = os.path.join(app_dir, "config")
        os.makedirs(self.config_dir, exist_ok=True)
        
        # Use custom vault path if provided, otherwise default (relative to app)
        if vault_path:
            self.vault_path = vault_path
        else:
            # DEFAULT VAULT - relative to app directory
            self.vault_path = os.path.join(self.config_dir, "session.vault")
        
        self._system_fingerprint = None
        self._vault_cache = None
    
    def get_vault_id(self) -> str:
        """Extract vault ID from vault filename"""
        basename = os.path.basename(self.vault_path)
        if basename == "session.vault":
            return "default"
        if basename.endswith(".vault"):
            return basename[:-6]
        return "unknown"
    
    # ========================================================================
    # Public API
    # ========================================================================
    
    def add_entry(self, entry_uuid: str, notebook_id: str, encrypted_keys: bytes, 
                  nonce: bytes = None, timestamp: int = None) -> bool:
        """Add or update an entry in the vault"""
        import time
        
        vault = self._read_vault()
        
        if "entries" not in vault:
            vault["entries"] = {}
        
        vault["entries"][entry_uuid] = {
            "notebook_id": notebook_id,
            "timestamp": timestamp or time.time_ns(),
            "nonce": nonce or os.urandom(12),
            "encrypted_keys": encrypted_keys
        }
        
        self._write_vault(vault)
        return True
    
    
    def store_keys(self, notebook_id: str, password_key: bytes, phrase_key: bytes) -> str:
        """
        Store keys in vault and return the generated entry UUID.
        This replaces the old store_keys behavior.
        """
        import uuid
        from crypto import Crypto
        
        fingerprint = self._get_system_fingerprint()
        
        # Ensure keys are 32 bytes
        if len(password_key) != 32:
            import hashlib
            password_key = hashlib.sha256(password_key).digest()
        if len(phrase_key) != 32:
            import hashlib
            phrase_key = hashlib.sha256(phrase_key).digest()
        
        # Combine keys
        combined = password_key + phrase_key
        
        # Generate nonce and encrypt
        nonce = os.urandom(12)
        aesgcm = AESGCM(fingerprint)
        encrypted_keys = aesgcm.encrypt(nonce, combined, None)
        
        # Generate entry UUID
        entry_uuid = str(uuid.uuid4())
        
        # Add to vault
        self.add_entry(entry_uuid, notebook_id, encrypted_keys, nonce)
        
        return entry_uuid
    
    def get_keys(self, entry_uuid: str) -> Optional[tuple]:
        """
        Retrieve and decrypt keys by entry UUID.
        Returns (password_key, phrase_key) or None.
        """
        fingerprint = self._get_system_fingerprint()
        
        entry = self.get_entry(entry_uuid)
        if not entry:
            return None
        
        try:
            aesgcm = AESGCM(fingerprint)
            decrypted = aesgcm.decrypt(entry["nonce"], entry["encrypted_keys"], None)
            
            # Split into password_key and phrase_key (both 32 bytes)
            password_key = decrypted[:32]
            phrase_key = decrypted[32:64]
            
            return password_key, phrase_key
        except Exception:
            return None
    
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
    
    def reload(self):
        """Force reload vault from disk, invalidating cache"""
        self._vault_cache = None


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
    
    def _read_vault(self) -> Dict[str, List[Dict]]:
        """Read entire binary vault file - NEW FORMAT (version 2)"""
        if self._vault_cache is not None:
            return self._vault_cache
        
        if not os.path.exists(self.vault_path):
            self._vault_cache = {"version": VAULT_VERSION, "entries": {}}
            return self._vault_cache
        
        try:
            with open(self.vault_path, 'rb') as f:
                version_data = f.read(4)
                if len(version_data) < 4:
                    self._vault_cache = {"version": VAULT_VERSION, "entries": {}}
                    return self._vault_cache
                
                version = struct.unpack('>I', version_data)[0]
                
                # Handle old format (version 4/5) - treat as empty for migration
                if version < VAULT_VERSION:
                    print(f"⚠️ Old vault format detected (v{version}). Creating new vault.")
                    self._vault_cache = {"version": VAULT_VERSION, "entries": {}}
                    return self._vault_cache
                
                # Read new format
                result = {"version": version, "entries": {}}
                
                # Read number of entries
                num_entries_data = f.read(4)
                if len(num_entries_data) < 4:
                    self._vault_cache = result
                    return self._vault_cache
                num_entries = struct.unpack('>I', num_entries_data)[0]
                
                for _ in range(num_entries):
                    # Read entry UUID
                    uuid_len_data = f.read(4)
                    if len(uuid_len_data) < 4:
                        break
                    uuid_len = struct.unpack('>I', uuid_len_data)[0]
                    uuid_bytes = f.read(uuid_len)
                    if len(uuid_bytes) < uuid_len:
                        break
                    entry_uuid = uuid_bytes.decode('utf-8')
                    
                    # Read notebook_id
                    nb_len_data = f.read(4)
                    if len(nb_len_data) < 4:
                        break
                    nb_len = struct.unpack('>I', nb_len_data)[0]
                    nb_bytes = f.read(nb_len)
                    if len(nb_bytes) < nb_len:
                        break
                    notebook_id = nb_bytes.decode('utf-8')
                    
                    # Read timestamp
                    ts_data = f.read(8)
                    if len(ts_data) < 8:
                        break
                    timestamp = struct.unpack('>Q', ts_data)[0]
                    
                    # Read nonce
                    nonce = f.read(12)
                    if len(nonce) < 12:
                        break
                    
                    # Read encrypted_keys length
                    len_data = f.read(4)
                    if len(len_data) < 4:
                        break
                    blob_len = struct.unpack('>I', len_data)[0]
                    
                    # Read encrypted_keys
                    encrypted_keys = f.read(blob_len)
                    if len(encrypted_keys) < blob_len:
                        break
                    
                    result["entries"][entry_uuid] = {
                        "notebook_id": notebook_id,
                        "timestamp": timestamp,
                        "nonce": nonce,
                        "encrypted_keys": encrypted_keys
                    }
                
                self._vault_cache = result
                return self._vault_cache
                
        except Exception as e:
            print(f"Error reading vault: {e}")
            self._vault_cache = {"version": VAULT_VERSION, "entries": {}}
            return self._vault_cache
    
    def _write_vault(self, vault: Dict) -> None:
        """Write entire binary vault file - NEW FORMAT (version 2)"""
        temp_path = self.vault_path + '.tmp'
        
        try:
            with open(temp_path, 'wb') as f:
                # Write version
                f.write(struct.pack('>I', VAULT_VERSION))
                
                entries = vault.get("entries", {})
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
                    
                    # Write nonce
                    f.write(entry_data["nonce"])
                    
                    # Write encrypted_keys length and data
                    encrypted_keys = entry_data["encrypted_keys"]
                    f.write(struct.pack('>I', len(encrypted_keys)))
                    f.write(encrypted_keys)
            
            os.rename(temp_path, self.vault_path)
            self._vault_cache = vault
            
        except Exception as e:
            print(f"Error writing vault: {e}")
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    
    def get_entry(self, entry_uuid: str) -> Optional[Dict]:
        """Get a single entry by UUID"""
        vault = self._read_vault()
        return vault.get("entries", {}).get(entry_uuid)
    
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

    def remove_entry(self, entry_uuid: str) -> bool:
        """Remove an entry by UUID"""
        vault = self._read_vault()
        if "entries" in vault and entry_uuid in vault["entries"]:
            del vault["entries"][entry_uuid]
            self._write_vault(vault)
            return True
        return False