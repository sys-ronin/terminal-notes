# How Lack of Formal Education Shaped an Unconventional Architecture

## A Personal Account of Problem‑Solving Without Textbooks

---

## Preface

This document is not a claim of superiority. It is not a rejection of formal education. It is an honest reflection on how my particular background—25 years of system experience, 12 years of professional experience in IT administration, networking, security, cloud, and supporting users of all skill levels, yet **without any formal college education**—forced me to solve problems in ways that I later discovered are highly unusual.

I did not set out to create a “new architecture.” I set out to make a writing tool that worked for me. The constraints I worked under (no funding, no team, no prior coding experience) were severe, but the most influential constraint was my ignorance of what “should” be done. I had no textbooks, no best‑practice guides, no mentors telling me how to design a secure, portable, offline‑first application. I only had problems and a need to solve them.

The result is a system that works, but that is very hard to describe using conventional terminology. This document explains why.

---

## 1. My Background: What I Knew and What I Did Not Know

| **What I had** | **What I did not have** |
|----------------|--------------------------|
| 25 years of system‑level experience (hardware, OS, networks, storage) | A formal computer science degree |
| 12 years of professional experience as IT admin, IT manager, handling security, cloud, and users of every technical level | Any formal training in software development |
| Deep understanding of real‑world constraints: hardware fails, users make mistakes, electricity goes dark | Knowledge of design patterns, architectural layers, or “best practices” |
| Practical experience with Git (as a user, not as a developer) | Experience with databases, ORMs, or web frameworks |
| No social media following, no influencer bias – only my own reasoning | Exposure to the hype cycles of “modern” software engineering |

I knew how systems behave in production. I knew how users break things. I knew that the cloud is just someone else’s computer, and that computers fail. But I did not know that you are “supposed” to use a database, a transaction manager, a TPM, or a key derivation function with thousands of iterations.

**This ignorance became my advantage.**

---

## 2. How Lack of Formal Education Forced Different Solutions

Because I did not know what the “correct” solution was, I solved each problem with the simplest tool I understood.

| **Problem** | **Textbook “Best Practice” (I learned later)** | **What I actually did** |
|-------------|------------------------------------------------|--------------------------|
| Storing notebook metadata and content | Use a relational database (SQLite, PostgreSQL) | Use three JSON files (`structure.json`, `notes.json`, `files.json`) and atomic writes. |
| Coordinating writes to multiple files | Use a transaction manager or two‑phase commit | Call the write functions in sequence; if one fails, stop. No rollback, no coordinator. |
| Binding encryption keys to a specific machine | Use a TPM or Secure Enclave | Derive a hardware fingerprint at runtime from machine IDs; never store it. Encrypt keys with that fingerprint. |
| Deriving keys from a password | Use PBKDF2, bcrypt, or Argon2 with thousands of iterations | Use a single SHA256 pass. The password is not the encryption key anyway. |
| Finding a notebook’s keys across different storage locations | Use a centralized key management service (KMS) or a database lookup | Use a small JSON registry that maps a vault name to a URL; download the vault file when needed. |
| Recovering deleted items from Git | Manually check out old revisions and copy files | Store the item UUID in the commit message; find the deletion commit; use its parent commit to reconstruct the item. |
| Ensuring consistency between registries and files | Use a database with foreign keys and transactions | Write files atomically (`.tmp` → `rename`). The registry is just another file. |

In every case, I chose the approach that required the **least new knowledge**. I used what I already understood: files, dictionaries, Git, hardware identifiers. I never asked “what is the best practice?” I asked “what will work?”

---

## 3. The Emergence of an Unusual Architecture

Because each solution was chosen in isolation, without reference to a grand design, the interactions between these solutions created **emergent properties** that I did not anticipate. Only after the system was complete did I notice:

- The application no longer held state; the files did. The application became a **stateless visitor** rather than a stateful container.
- The “coordination” between components happened through **data dependencies** (UUID pointers in JSON files) rather than through a central controller.
- The system could be split across multiple storage locations (local disk, USB, S3, WebDAV) without changing the code, because every artifact was addressed by a path or URL.
- The total complexity of a lookup remained **O(1)** regardless of how many notebooks or items existed, because every resolution was a dictionary lookup.

I did not design these properties. They **emerged** from solving small problems in the simplest possible way. Later, when I tried to explain the system to others, I realised that it did not fit any known architectural pattern. It was not a “microservice” architecture (no network). It was not a “client‑server” architecture (no server). It was not a “database‑centric” architecture (no database). It was something else.

---

## 4. Why This Was Difficult to Explain (Even to Myself)

Because the architecture emerged from constraint rather than from design, I could not name it using standard terminology. Every time I tried to describe it, I had to invent new phrases: “data visitation,” “UUID chain,” “ephemeral convergence,” “artifact‑driven orchestration.” Each of these phrases describes a behavior that is not covered in textbooks because textbooks assume that applications are built from known patterns.

**The system is not complex because it has many parts.** It is complex because the interactions between its few parts are subtle and not described elsewhere. The learning curve is not in the code (the code is small) but in the **mental model** required to understand why it works.

This is, I believe, a direct consequence of my lack of formal education. I did not know that these problems were supposed to be hard, so I solved them with simple tools. And because I used simple tools in ways that are not standard, the resulting system does not look like anything a trained software engineer would produce.

---

## 5. What I Learned (and What I Still Do Not Know)

I learned that **constraints are creative**. Having no choice but to build with what I had forced me to find solutions that are not in any textbook.

I learned that **ignorance of “best practices” can be a gift** when those practices are not actually required for the problem at hand. Many best practices exist to manage scale, concurrency, or team size that I did not have.

I still do not know most of what a computer science graduate knows. I cannot design a complex algorithm or write a compiler. But I know how to solve the problems that matter to me, and I have learned that simple solutions are often the most powerful.

---

## 6. A Humble Request to the Reader

If you are a trained software engineer, you may find this system confusing or even wrong. I ask you to set aside your assumptions for a moment. Do not ask “why didn’t they use a database?” Ask “does this file‑based approach work?” Do not ask “is this secure without a TPM?” Ask “is the hardware fingerprint bound at runtime?” The code is open. The behavior is observable. The system works.

I am not arguing that formal education is bad. I am documenting that my lack of it led me to a different path. That path produced a system that is, by many measures, rare and possibly unique. I share it not to say “this is how you should build software,” but to say “this is how one person built software under extreme constraints, and it worked.”

---

## 7. Conclusion

The architecture documented in the accompanying files is not the result of following best practices. It is the result of solving real problems with the tools I had and the knowledge I possessed. The lack of formal education forced me to ignore many assumptions that trained engineers take for granted. Those assumptions turned out to be **optional** for this particular problem domain.

The system works. It is secure, portable, offline‑first, and recoverable. It contradicts many textbook teachings, but it does not contradict reality. Reality is the only test that matters.

I offer this as a case study – not a blueprint, but an example of what can happen when you are free from the burden of knowing what you are “supposed” to do.

The code is open. The documents are public. The reader may judge for themselves.

---

**sys_ronin**  
May 2026
