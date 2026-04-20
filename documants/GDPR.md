# Terminal Notes: Architectural Compliance

## A Document of Observation

---

## Preface

This document describes what exists.

It does not claim achievement. It does not advertise features. It simply records what the code does and what follows from that.

The system described here was built for personal use, under constraints of no budget, no team, and no interest in user data. What emerged was compliance—not as a goal, but as a side effect of architecture.

This is not a marketing document. It is an architectural one.

---

## What the System Does

Terminal Notes is a local-first writing environment.

- It runs on the user's machine
- It stores data in files the user can see
- It does not have a network stack for data transmission
- It does not load third-party code
- It does not create accounts
- It does not collect metrics
- It does not phone home

These are not settings. They are constraints built into the code.

---

## Article-by-Article Mapping

### Article 5: Principles Relating to Processing of Personal Data

**1. Lawfulness, Fairness, Transparency**

Requirement: Users must know what happens to their data.

What the system does:
- No data processing occurs beyond local file operations
- Data lives in JSON files the user can open with any text editor
- Transparency is not a policy—it is the file system

**2. Purpose Limitation**

Requirement: Purpose must be clear and limited.

What the system does:
- Purpose: write text, save text
- No analytics, no telemetry, no improvement metrics
- There is no secondary purpose because there is no code for it

**3. Data Minimization**

Requirement: Only collect what is necessary.

What the system does:
- Data stored: user's text
- Metadata stored: timestamps, UUIDs (for internal linking)
- Nothing else exists in the codebase

**4. Accuracy**

Requirement: Data must be accurate.

What the system does:
- User controls all data directly
- Edit, rename, delete are immediate
- Accuracy is user capability, not system policy

**5. Storage Limitation**

Requirement: Data should not be kept indefinitely without reason.

What the system does:
- User decides retention
- Delete removes from current view
- Hard delete removes from Git history (eraser.py)
- No automatic retention policies

**6. Integrity and Confidentiality**

Requirement: Protect against unauthorized access.

What the system does:
- No transmission = no interception
- No cloud = no breach
- No central database = no mass exfiltration
- Security is the user's infrastructure choice

---

### Article 17: Right to Erasure ("Right to be Forgotten")

Requirement: Users can request deletion of their data.

What the system does:
- Standard delete: removes from current view
- Hard delete: removes from Git history using git-filter-repo
- No authority to request from—user executes deletion directly
- No waiting, no forms, no approval

Implementation:
```python
# eraser.py
def _hard_delete(self, uuid, item_type, context, item_title=None):
    self._purge_from_git(uuid, item_type, context)
    notebook.notes.remove(note)
    self.manager.save_data()
```

Result: Complete removal. Irreversible. User-controlled.

---

### Article 20: Right to Data Portability

Requirement: Users can receive their data in structured, common format.

What the system does:
- All data stored as JSON (RFC 8259)
- JSON is structured, machine-readable, human-readable
- Git history provides temporal data
- Copy the folder. It works anywhere.

Example structure.json:
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "name": "Projects",
  "notes": [
    {
      "id": "223e4567-e89b-12d3-a456-426614174001",
      "title": "API Design",
      "created": "2026-02-17T10:30:00"
    }
  ]
}
```

Portability:
- Copy directory to new machine
- Import in Terminal Notes (or read directly as JSON)
- All data, all history, all structure preserved
- No export/import required—the files are the data

---

### Article 32: Security of Processing

Requirement: Implement appropriate technical measures.

What the system does:
- No network stack in the application
- No third-party libraries (Python standard library only)
- Atomic writes prevent corruption (temp → rename)
- Git provides integrity checking (git fsck)
- Recovery system for editor crashes
- No single point of failure

Atomic write pattern:
```python
# Write to temp file first
with open(temp_path, 'w') as f:
    json.dump(data, f)
# Atomic rename (POSIX guarantee)
os.rename(temp_path, final_path)
```

Result: Data integrity even during crashes.

---

### Article 33: Breach Notification

Requirement: Notify authority within 72 hours of breach.

What the system does:
- No data to breach
- No servers to compromise
- No network to intercept
- No central database to exfiltrate
- Breach is impossible by architecture

Consequence: Not applicable.

---

### Article 35: Data Protection Impact Assessment

Requirement: Assess risk for high-risk processing.

What the system does:
- No processing = no risk
- No high-risk categories involved
- No automated decision-making
- No profiling
- No cross-border transfer
- DPIA not required

---

## Encryption Architecture

### Design Principle

Encryption in this system follows the same pattern as all other features: it exists to serve the user, not to be a feature in itself.

- Encryption is applied to JSON files
- Keys are derived from user password and folder name
- Keys are stored encrypted with machine hardware fingerprint
- No keys leave the user's machine
- No cloud key storage
- No key escrow

### What This Enables

- Notebooks can be encrypted at rest
- Encrypted notebooks show a lock symbol when locked, unlocked symbol when open
- Locking clears the key from memory
- Unlocking requires password (once per machine, stored in system-bound encrypted storage)
- Encrypted notebooks remain encrypted in Git history

### Compliance Implications

- Data at rest is protected by user-chosen keys
- Keys cannot be extracted to another machine (hardware binding)
- No third party can access encrypted notebooks
- Right to erasure applies to encrypted data as well

---

## Technical Decisions and Their Compliance Implications

| Decision | What It Does | Compliance Effect |
|----------|--------------|-------------------|
| No external dependencies | No third-party code loaded | No third-party data processing |
| Local file storage | Data never transmitted | No transmission, no interception |
| No accounts | No identifiers collected | No personal data to protect |
| No analytics | No metrics collected | No behavioral tracking |
| JSON format | Data is plain text structure | Portable by design |
| Git history | Every change recorded | Audit trail, right to erasure support |
| Atomic writes | temp → rename | Data integrity during crashes |
| Hard delete (git-filter-repo) | Removes from history | Complete right to erasure |
| Encryption with hardware binding | Keys tied to machine | Data cannot be decrypted elsewhere |

Each decision was made for personal necessity. Each created compliance as a side effect.

---

## Deployment Considerations

Terminal Notes itself is compliant by architecture. However, users may choose to:

- Place notebooks in cloud-synced folders (Dropbox, Nextcloud)
- Use third-party Git hosting (GitHub, GitLab)
- Share notebooks via email or USB

These choices introduce their own compliance considerations. Terminal Notes does not:
- Control the user's infrastructure choices
- Impose synchronization
- Require network access
- Validate where files are stored

The user's sovereignty includes the right to choose. The system does not restrict that choice, nor does it assume responsibility for those choices.

---

## Validation

The system has been used for daily writing since 2026.

Observations:
- No data has been collected (there is no code to collect)
- No data has been transmitted (there is no network code)
- No data has been sold (there is no business model)
- No data has been analyzed (there are no analytics)
- No data has been profiled (there is no profiling code)

Not because of policies. Because the architecture prevents it.

---

## Strategic Implications

### For Enterprise Deployment

Terminal Notes can be deployed in regulated environments:
- Healthcare (HIPAA)
- Finance (GLBA, SOX)
- Government (FedRAMP)
- Education (FERPA)
- EU (GDPR)

Why:
- No data leaves user control
- No third-party processing
- No cloud dependencies
- Audit trail via Git
- Complete deletion capability
- Portable data formats

No compliance review needed. The architecture is the compliance.

### For Personal Use

The user's data is the user's.
Always has been. Always will be.
No terms of service to change.
No privacy policy to update.
No company to be acquired.

The data outlives any organization.
The user outlasts any service.

### For the Industry

This demonstrates that compliance is not about policies.
Compliance is about architecture.

When software is built without:
- Data collection
- Third-party code
- Cloud dependencies
- User tracking

Then compliance is automatic. Not achieved. Not configured. Inherent.

---

## Limitations

This compliance applies only to Terminal Notes itself.

If the user:
- Places notebooks in cloud-synced folders
- Uses third-party Git hosting
- Shares notebooks via email or USB

Then those choices introduce their own compliance considerations.

Terminal Notes does not:
- Control the user's infrastructure choices
- Impose synchronization
- Require network access
- Validate where files are stored

The user's sovereignty includes the right to choose.
The system does not restrict that choice.
But the system also does not assume responsibility for those choices.

---

## Conclusion

Terminal Notes is compliant.

Not because it was designed to be.
Because it was designed to need nothing from the user.

The user's data is the user's.
Always has been. Always will be.
The architecture ensures it.

This is not a feature.
This is the absence of anti-features.

The system does not collect.
The system does not transmit.
The system does not process.
The system only saves what you write.

That is the entire compliance strategy.

---

## References

- Regulation (EU) 2016/679 (General Data Protection Regulation)
- https://gdpr-info.eu/

For questions about specific deployments:
- The answer is always: "The data is where you put it."
- There is no other answer.

---

**End of Document**
```
