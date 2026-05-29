# Prior Art Disclosure: Folder Name as Cryptographic Salt and Secret

**Date of Disclosure:** April 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  

---

## What This Document Describes

This document describes a key derivation method where the cryptographic salt is not a random value stored separately, but is derived from the folder name containing the encrypted data. The folder name is a human‑readable identifier concatenated with a globally unique identifier (UUID). Changing any character of the folder name changes the derived key, rendering the encrypted data permanently inaccessible.

This method eliminates the need for a separate salt file. It also introduces a novel security property: the folder name itself becomes a secret that the user can control. If the user keeps the folder name private, even an attacker who obtains the password cannot decrypt the data.

---

## The Core Mechanism

### Key Derivation

The encryption key for a notebook is derived as:

```python
key = SHA256(password + b':' + folder_name)
```

Where `folder_name` is the name of the directory containing the encrypted JSON files. The folder name is not random; it is constructed as:

```
folder_name = f"{notebook_name}-{notebook_uuid}"
```

Example: `my-notes-20260401123456`

The `notebook_name` is chosen by the user. The `notebook_uuid` is a timestamp‑based or random identifier.

### No Separate Salt File

Conventional encryption systems generate a random salt and store it alongside the ciphertext (often prepended). This system does not. The salt is the folder name itself. The folder name is already present in the filesystem. No extra file is created, stored, or managed.

### The Salt Is Not a Secret (By Default)

In standard cryptographic practice, the salt does not need to be secret. Its purpose is to ensure uniqueness. This system follows that principle: the folder name is visible in the filesystem. An attacker who knows the folder name still cannot derive the key without the password.

---

## The Novel Security Property: Folder Name as a User‑Controlled Secret

Because the folder name is part of the key derivation, the user can **change** the folder name to any arbitrary string. If the user renames the folder to a secret name known only to them, the following consequences apply:

- The original folder name is no longer present.
- An attacker who discovers the encrypted folder (e.g., on a backup drive, cloud storage, or stolen device) sees only a folder with an unknown, arbitrary name.
- Without the correct folder name, even the correct password will derive a different key, and decryption will fail.
- The data becomes unrecoverable unless the user remembers the secret name.

Thus, the folder name acts as a **second factor** of authentication: something the user knows (the secret name) in addition to the password.

### Practical Implementation

The user can rename the encrypted notebook folder at any time. For example:

```
# Original folder name (derived from notebook name and UUID)
my-notes-20260401123456

# User renames to a secret name
secret_vault_xyz789
```

From that point on, the correct key derivation requires:

1. The password (or recovery phrase)
2. The exact secret folder name

An attacker who obtains the encrypted files but does not know the secret name cannot decrypt them, even with the password.

To recover the data, the user must rename the folder back to its original name (or to the same secret name used during encryption). The system does not store the folder name anywhere else; it must be remembered or recorded by the user.

### Security Level

The folder name can be any UTF‑8 string of arbitrary length. The entropy of the folder name is chosen by the user. A long, random secret name provides security comparable to a cryptographic key. Combined with a strong password, the system achieves a two‑factor security level that is resistant to brute‑force attacks even if one factor is compromised.

---

## Why Changing a Single Letter Makes Decryption Impossible

The key derivation uses SHA256, a cryptographic hash function. SHA256 has the avalanche property: a change of a single bit in the input produces a completely different output, indistinguishable from random.

If the folder name is changed by even one character:

```python
folder_name1 = "my-notes-20260401123456"
folder_name2 = "my-notes-20260401123457"  # last digit changed

key1 = SHA256(password + b':' + folder_name1)
key2 = SHA256(password + b':' + folder_name2)
```

`key1` and `key2` share no relation. Decryption with the wrong folder name fails with the same probability as guessing a random 256‑bit key.

Thus, the data is permanently locked if the folder name is lost or altered. There is no backdoor, no recovery mechanism, and no master key.

---

## Relation to the Recovery Phrase

The system also uses a recovery phrase to derive a separate key (`Ks`). The phrase key is used to encrypt the password key (`Kp`). The folder name is used in the derivation of both `Kp` and `Ks`:

```python
Kp = SHA256(password + b':' + folder_name)
Ks = SHA256(phrase + b':' + folder_name)
```

Therefore, the folder name is an integral part of both the daily password and the recovery mechanism. Changing the folder name invalidates both.

This means that the user must keep a record of the folder name if they wish to recover the data using the phrase. Without the correct folder name, the phrase alone cannot derive the correct `Ks`.

---

## Prior Art Assertion

The concept of using the folder name as the cryptographic salt, without separate salt storage, and the property that the folder name can serve as a user‑controlled secret factor, was made public in timestamped GitHub repositories and prior art disclosures starting in February 2026.

No prior art describes a system where:

- The salt is derived from the human‑readable folder name concatenated with a UUID.
- The folder name is not stored elsewhere; it is the filesystem path itself.
- Changing the folder name irreversibly locks the data, even with the correct password.
- The folder name can be used as a second authentication factor.

These concepts constitute prior art under 35 U.S.C. § 102(a)(1) and Article 54(2) EPC. No party may obtain valid patent claims covering these concepts.

---

## Conclusion

The folder name is not merely a label. It is an active component of the encryption key. By controlling the folder name, the user gains an additional layer of security: the ability to lock the data behind a secret name that only they know.

If the folder name is lost or changed, the data becomes permanently inaccessible. This is not a design flaw; it is a feature that gives the user absolute control over their encrypted data.

The system does not rely on external key escrow, cloud backup, or administrative override. The security is mathematical and final.

```
