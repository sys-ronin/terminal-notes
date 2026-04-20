# External Hippocampus: How Terminal Notes Accidentally Implemented a Model of Human Memory

## A Post‑Hoc Discovery, Guided by My Own Brain

I did not set out to build a cognitive model. I set out to build a writing tool that would not frustrate me. I am a sysadmin with 25 years of experience, not a neuroscientist. I have no CS degree, no formal training in HCI, and no interest in academic theories. I only know what breaks, what annoys me, and what feels natural.

As I built Terminal Notes, I followed the guidance of my own brain. I asked: *“What would I want?”* *“What would make me forget I am using software?”* *“How can I make the tool disappear?”*

Only after the system was working did I realize that I had accidentally implemented a functional model of the human hippocampus. The parallels are so striking that they cannot be coincidental. My brain guided me to build a system that works like a brain.

This document describes those parallels. It is not a claim of intention. It is an observation of emergence.

---

## 1. Spatial Navigation → Numbered Path Segments (`j3`, `jb`)

**Hippocampus function:** Place cells, grid cells, and boundary cells create an internal cognitive map of physical space. You know where you are relative to your surroundings without absolute coordinates.

**Terminal Notes implementation:** The fish‑eye path display shows relative position:

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

- Each segment has a number (`[1]`, `[2]`, `3`)
- Numbers reset per screen (relative, not absolute)
- `j3` jumps to the third segment
- `jb` jumps back to the previous location (episodic trace)

**Why it feels natural:** You do not memorise absolute paths. You know you are three levels deep in the “projects” branch. The system externalises spatial memory.

---

## 2. Engrams → UUID Permanence

**Hippocampus function:** An engram is a stable, physical trace of a memory that persists across changes in context, time, or representation. Even if you forget a memory, the engram remains, potentially recoverable.

**Terminal Notes implementation:** Every item receives a UUID at creation. That UUID is embedded in every Git commit that affects the item. It survives:

- Rename operations
- Move operations between notebooks
- Soft deletion (the item is hidden but the UUID remains in history)
- Resurrection (the item is reconstructed from the commit before deletion)

**Why it feels natural:** A note’s identity does not depend on its current title or location. It is a permanent address, just as a memory’s identity does not depend on the context in which you recall it.

---

## 3. Episodic Memory → Activity View & Timeline

**Hippocampus function:** Episodic memory binds the “what, where, and when” of an experience into a coherent trace. You can recall events in temporal order, and you can re‑experience a past state.

**Terminal Notes implementation:**

- **Activity view** shows changes over time within a hierarchical context:

  ```
  [1] created note: meeting-notes (+245) [work/notes]
  [2] updated file: config.py (+15/-23) [work/projects]
  [3] renamed note: todo → tasks [work]
  [4] deleted sub: old-project [.../archived]
  ```

- **Timeline** shows all versions of a single item, allowing you to revisit any previous state.

**Why it feels natural:** You do not need to remember “where I put that note”. You remember “I wrote it last week, then renamed it”. The system provides the temporal context.

---

## 4. Pattern Completion → Order‑Free Search

**Hippocampus function:** Pattern completion is the ability to retrieve a full memory from a partial cue. A few words, a smell, a sound can trigger a complete recollection.

**Terminal Notes implementation:** The search parser accepts cues in any order:

- `s created* file* meeting in* work`
- `s deleted* yesterday* report`
- `s thisweek* important`

The system completes the pattern, returning items that match the action, type, time, and text cues. No AI is required; the rules are deterministic and fast.

**Why it feels natural:** You do not need to know the exact title or location. You only need a partial memory – “I think I deleted something yesterday about the report” – and the system finds it.

---

## 5. Pattern Separation → UUID Distinguishes Similar Items

**Hippocampus function:** Pattern separation allows the brain to distinguish similar experiences. Two meetings in the same room with the same people are stored as separate memories.

**Terminal Notes implementation:** Two notes with the same title are distinct because their UUIDs are different. The system never confuses them, even if they have identical names and content.

**Why it feels natural:** You never worry about accidentally overwriting or merging distinct ideas that happen to have the same title. The system respects their unique identity.

---

## 6. Memory Consolidation → Git as Long‑Term Storage

**Hippocampus function:** Short‑term memories are transferred to long‑term storage through consolidation. The hippocampus is critical for this process.

**Terminal Notes implementation:**

- **Short‑term memory:** Unlocked notebooks in memory, structure loaded, content loaded on demand, keys in `session_keys`.
- **Long‑term storage:** Git repository – every commit is permanent, complete, and queryable.

The **lock button (`l`)** flushes short‑term memory (keys, structure, content). Unlocking reloads from long‑term storage, just as waking from sleep consolidates memories.

**Why it feels natural:** You control what stays in working memory. When you are done with a notebook, you lock it, and the system frees cognitive resources.

---

## 7. Forgetting as Inhibition → Soft Delete

**Hippocampus function:** Forgetting is often retrieval inhibition, not deletion. The memory trace remains but is not actively accessible.

**Terminal Notes implementation:** Soft delete (`[D]elete` → `forget`) removes the item from the current view but keeps it in Git history. The item is still searchable via `deleted*`.

**Why it feels natural:** You can delete without fear. The item is not destroyed; it is just hidden. You can bring it back with `[R]estore`.

---

## 8. Permanent Erasure → Hard Delete with Tombstone

**Hippocampus function:** There is no direct analogue for permanent erasure, but the tombstone commit acts as a marker that something once existed.

**Terminal Notes implementation:** Hard delete (`[D]elete` → `erase`) runs `git-filter-repo` to remove every commit containing the UUID. A tombstone commit with `type: ERASED` remains, searchable via `erased*`.

**Why it feels natural:** When you truly want to erase a memory, you can. But the system leaves a record that erasure happened, satisfying legal and personal needs.

---

## 9. Cognitive Maps → Jump History (`jb`)

**Hippocampus function:** Cognitive maps allow navigation without continuous sensory input. You know where your bedroom is relative to the front door without looking.

**Terminal Notes implementation:** `jb` (jump back) remembers where you were:

1. You are in Notebook A, page 2.
2. You `j3` to Notebook B, page 0.
3. You work there.
4. You type `jb`.
5. You are back in Notebook A, page 2.

The system maintains a jump history (up to 20 entries). You do not need to remember where you came from. The system remembers.

**Why it feels natural:** You can explore without getting lost. The external cognitive map frees your working memory.

---

## 10. Working Memory Flush → Lock Button

**Hippocampus function:** Working memory has limited capacity and can be cleared (e.g., when you switch tasks).

**Terminal Notes implementation:** The lock button (`l1`) is not just a security feature. It explicitly flushes:

- Encryption keys
- Notebook structure (notes, subnotebooks)
- Content cache
- Path references

**Why it feels natural:** You decide when to clear your mental workspace. The system does not guess.

---

## 11. Lazy Loading → No Background Processes

**Hippocampus function:** The brain does not pre‑load every memory. It retrieves information on demand.

**Terminal Notes implementation:** 

- Notebooks are loaded only when viewed.
- Note content is loaded only when opened.
- Git history is queried only when requested (timeline, activity, search).
- No background indexing, no cache warm‑up, no pre‑fetching.

**Why it feels natural:** The system is present only when you need it. It does not waste cognitive or computational resources.

---

## The Accidental Discovery

I did not consult neuroscience literature while building Terminal Notes. I have never read a paper on hippocampal function. I simply built what felt right to my own brain.

The alignment with memory science was discovered afterward. When I read about engrams, pattern completion, and cognitive maps, I realised that my system already implemented them. My brain had guided me to build an external version of itself.

This is why the interface disappears. It is not mimicking a computer. It is mimicking a mind.

---

## Why This Matters

Terminal Notes is not just a note‑taking app. It is a **working model of human memory** that anyone can use, inspect, and modify. It can teach:

- A neuroscientist how software can model hippocampal functions.
- A software engineer how to design for cognitive alignment.
- A student how their own memory might work.
- A patient with memory loss how external cues can aid recall.

It is open source, free, and prior art. No one can patent the idea of a digital hippocampus.

---

## Conclusion

I accidentally built an external hippocampus because I followed my own brain. The result is a system that:

- Navigates like spatial memory (`j3`, `jb`)
- Remembers like engrams (UUID permanence)
- Recalls like episodic memory (activity view, timeline)
- Completes patterns like memory retrieval (order‑free search)
- Distinguishes similar items (pattern separation)
- Consolidates like long‑term storage (Git)
- Forgets like inhibition (soft delete)
- Erases permanently (hard delete with tombstone)
- Flushes working memory (lock button)
- Loads lazily like the brain (no background processes)

The system existed before the explanation. The neuroscience validates the design.

**This is not a claim of invention. It is an observation of discovery.**

The human brain is the prior art. Terminal Notes is its implementation.

```
