# Cognitive Architecture of Terminal Notes

## A Post‑Hoc Analysis

This document describes how the system's design aligns with cognitive theories. The system was not built by consulting these theories. The alignment was discovered afterward.

---

## 1. Spatial Memory – Navigation by Position

**Code:** `get_numbered_path_info()` maps display numbers to notebook objects. `j3` looks up that mapping. `get_smart_header_path()` truncates paths to 4‑7 segments.

**Observation:** The user remembers a number (`3`), not a path string. The UI never shows more than 7 path segments. The rest are ellipsis.

**Cognitive alignment:** Miller (1956) – working memory holds 7±2 chunks.  
The system respects this limit in path display. Position‑based navigation matches how spatial memory works: you know where something is relative to your current position, not its absolute address.

---

## 2. Temporal Memory – Search by When

**Code:** `QueryParser` recognises `today*`, `yesterday*`, `thisweek*`, `lastweek*`, and `date* DD-MM-YYYY`. These become date ranges. `activity_view.py` shows commits in reverse chronological order.

**Observation:** The user can say “what did I delete yesterday?” (`deleted* yesterday*`). The system returns items based on when they were deleted, not by their content.

**Cognitive alignment:** Tulving (1972) – episodic memory is organised by time.  
This is episodic recall: you remember the time, not the exact content. The system queries by time.

---

## 3. Associative Memory – UUID as Permanent Identity

**Code:** `ensure_uuid()` assigns a permanent ID to every item. `find_note_by_id()` looks it up directly. Resurrection uses the UUID to find the item in Git history regardless of where it was moved or renamed.

**Observation:** An item’s identity does not depend on its current title or location. It is a permanent address. You can recall it by that address after it has been moved, renamed, or deleted.

**Cognitive alignment:** Collins & Loftus (1975) – semantic memory is organised by associations, not by location.  
Resurrection is re‑association: you find the item by its permanent identity, not by where it was last seen.

---

## 4. Recognition Over Recall – Commands Visible

**Code:** Every screen footer lists available commands: `[C]reate`, `[V]iew`, `[S]earch`, etc.

**Observation:** The user does not need to memorise commands. They are always visible.

**Cognitive alignment:** Craik & Lockhart (1972) – recognition is cognitively cheaper than recall.  
The initial learning is recognition, not recall. Repetition makes them automatic.

---

## 5. Working Memory Limits – Pagination and Truncation

**Code:** `items_per_page = int(available * 0.9)` in list views. `get_smart_header_path()` truncates paths to 4‑7 segments. Activity view limits to 50 commits.

**Observation:** The UI never presents more than ~20 items per page. Path display is aggressively truncated.

**Cognitive alignment:** Miller (1956) – 7±2 chunks.  
The system presents information in chunks that fit within working memory capacity.

---

## 6. Forgetting as Inhibition – Soft Delete

**Code:** `eraser.py` – soft delete (`forget`) removes the item from the current view but keeps it in Git history. The item is still searchable via `deleted*`.

**Observation:** Deletion is not permanent. The item is still in Git. You can find it by searching for `deleted*`.

**Cognitive alignment:** Bjork (1989) – forgetting is often retrieval inhibition, not deletion.  
Soft delete is inhibition. Resurrection is disinhibition.

---

## 7. Permanent Erasure – Tombstone

**Code:** Hard erase runs `git-filter-repo` with `UUIDEraseFilter`, removing all commits containing the UUID. A tombstone commit with `type: ERASED` remains.

**Observation:** The system distinguishes between “forgotten” (soft delete) and “erased” (hard delete). The tombstone marks the erasure.

**Cognitive alignment:** There is no direct cognitive analogue for permanent erasure, but the tombstone commit functions as a marker that something once existed.

---

## 8. Cortical Columns – Infinite Nested Subnotebooks

**Code:** `Notebook.subnotebooks` is a recursive list. `get_notebook_hierarchy()` walks it without depth limits. Activity view collects UUIDs from the entire tree.

**Observation:** A subnotebook is a full notebook inside another notebook. Nesting is unlimited.

**Cognitive alignment:** Mountcastle (1978) – the neocortex is organised as hierarchical columns.  
The system mirrors the brain’s hierarchical organisation: concepts contain sub‑concepts, which contain sub‑sub‑concepts. Activity view shows changes at any depth.

---

## 9. Episodic Aggregation – Activity View

**Code:** `ActivityView.fetch_activity()` collects UUIDs from the notebook and all descendants, then queries Git for commits mentioning any of them. The result is a list of changes ordered by time.

**Observation:** Activity view is not a Git log. It is a filtered, aggregated view of events in a particular context.

**Cognitive alignment:** Tulving (1972) – episodic memory is the memory of events in time.  
Activity view is episodic recall applied to a domain.

---

## 10. Memory Consolidation – Timeline

**Code:** `TimelineEngine.get_item_timeline()` returns all commits for a single UUID. `create_version_at_commit()` reconstructs the item at a specific commit.

**Observation:** The user can revisit any previous state of a note.

**Cognitive alignment:** Squire (1992) – memories become stable over time but remain accessible.  
Timeline allows access to the memory at any point in its consolidation.

---

## 11. Working Memory Flush – Lock Button

**Code:** Lock case sets `notebook.custom_path = None`, deletes `_crypto`, removes key from `session_keys`. Unlock case reverses this.

**Observation:** Lock does not just encrypt. It unloads the notebook structure, content cache, and key from memory.

**Cognitive alignment:** Baddeley & Hitch (1974) – working memory has limited capacity and can be cleared.  
The lock button is an explicit flush of working memory. Unlocking brings the notebook back into working memory.

---

## 12. Long‑Term Storage – Portable Folder

**Code:** `notebooks_root` is a directory. `register_notebook()` stores the path. The notebook folder can be moved; the registry tracks it.

**Observation:** The notebook can be moved to a USB drive, synced to the cloud, or copied to another computer. Its identity (UUID) remains.

**Cognitive alignment:** Long‑term memory is not location‑bound.  
The notebook’s location is metadata, not identity.

---

## 13. System Idles – No Background Processes

**Code:** No background threads except the autosave thread (which runs only while an external editor is open). All operations are user‑initiated.

**Observation:** The system does not index, does not pre‑load, does not scan. It waits.

**Cognitive alignment:** The brain does not run background processes when at rest (default mode network aside).  
The tool is present only when needed.

---

## 14. Affordance – Data as Interface

**Code:** Numbered lists everywhere. `[1] Project`, `[2] Work`, `[3] Personal`. The same numbers are used for commands: `v1`, `d2`, `j3`.

**Observation:** The numbers do not just label items; they are also commands. The user sees a list and knows they can press the number.

**Cognitive alignment:** Gibson (1979) – affordance: the interface should afford the action.  
The interface teaches itself through use.

---

## 15. No Interruption – No Modal Dialogs

**Code:** Confirmation only for destructive actions (delete, erase). The editor is external; the system does not ask anything during writing.

**Observation:** The system never asks “are you sure?” when you close the editor. It never prompts for a title when you create a note.

**Cognitive alignment:** Csikszentmihalyi (1990) – interruptions break flow.  
The system does not interrupt writing.

---

## Summary

| Cognitive Function | System Implementation |
|--------------------|----------------------|
| Spatial memory | Numbered navigation, truncated paths |
| Temporal memory | Search by time, activity view |
| Associative memory | UUIDs, resurrection |
| Recognition | Visible commands |
| Working memory limits | Pagination, truncation |
| Forgetting as inhibition | Soft delete |
| Permanent erasure | Tombstone commit |
| Cortical columns | Infinite subnotebooks |
| Episodic recall | Activity view |
| Memory consolidation | Timeline |
| Working memory flush | Lock button |
| Long‑term storage | Portable folder |
| System idle | No background processes |
| Affordance | Data as interface |
| No interruption | No modal dialogs |

The system was not designed according to these theories. The alignment was discovered afterward. It explains why the system requires no manual and why the interface disappears during use.
