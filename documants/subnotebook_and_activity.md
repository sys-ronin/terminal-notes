# Subnotebook Hierarchy and Activity

## 1. What a Subnotebook Is

A subnotebook is a notebook inside another notebook.

There is no limit to how deep you can go. A subnotebook can contain notes, files, and more subnotebooks. Each level is a full notebook with its own structure, content, and Git history.

In the code, a subnotebook is just a `Notebook` object stored in the `subnotebooks` list of its parent notebook. It has all the same fields: `id`, `name`, `notes`, `subnotebooks`, `parent_id`. The `parent_id` points to the notebook that contains it.

When you create a subnotebook, only `structure.json` is saved. The content files (`notes.json`, `files.json`) are created empty. Git commits record the creation with `type: CREATED SUBNOTEBOOK`.

---

## 2. How the System Knows Where You Are

The UI keeps a navigation stack: `self.nav.push("notebook", notebook_id, page)`. Each entry stores the screen type, the notebook ID, and the current page number.

When you move into a subnotebook, a new entry is added. When you go back, the stack is popped. This is how the system knows which notebook you are viewing at any moment.

Jump commands (`j1`, `j2`, `jb`) work by walking the hierarchy and rebuilding the stack to the target notebook.

---

## 3. Activity View for a Subnotebook

Activity view shows changes in the notebook you are viewing **and all notebooks inside it**.

When you press `[A]ctivity` on a notebook, the system:

1. Finds the root notebook (the one that contains the Git repository). All notebooks in a hierarchy share the same root.
2. Collects every UUID from that notebook and all its descendants. This includes the notebook itself, every note, every file, and every subnotebook at any depth.
3. Builds a Git grep pattern by joining those UUIDs with `|`.
4. Runs `git log --grep "uuid1|uuid2|..." --all` and returns the most recent 50 commits.

Because UUIDs are permanent, a change in a deeply nested subnotebook will be captured by the activity view of any ancestor notebook that contains it.

---

## 4. Displaying the Path in Activity View

When a commit is shown in activity view, the system needs to tell you where the changed item lives relative to the notebook you are viewing.

The path is built from the notebook hierarchy stored in `uuid_to_path`. This is a map from each UUID to the list of notebook names that lead to it (starting from the root).

Example: If you have notebooks `Work` → `Projects` → `ClientX`, and a note `Meeting Notes` inside `ClientX`, the path list is `["Work", "Projects", "ClientX"]`.

When viewing activity from `Projects`:

- If the item is `Projects` itself → `[Projects]`.
- If the item is `ClientX` → `[ClientX]` (direct child).
- If the item is `Meeting Notes` → `[ClientX]` (shows the immediate parent name, not the full path).
- If the item is `Work` (ancestor) → `[Work]` (shows the parent name).

If the depth is greater than two levels, the path is truncated: `[.../last/two]`. This keeps the display clean while still providing context.

---

## 5. Timeline for a Subnotebook

Timeline works for subnotebooks exactly as it does for notes. The system finds every commit that mentions the subnotebook’s UUID and lets you view the state of the subnotebook at that point in time.

When you view a historical version of a subnotebook, the system reconstructs:

- The subnotebook’s structure (which notes and sub‑subnotebooks existed at that commit).
- The content of those notes and files (filtered to only those belonging to the subnotebook).

The reconstruction is on‑demand: it happens only when you select a version.

---

## 6. Searching Within a Subnotebook

When you search from a notebook view (including subnotebooks), the context is set to that notebook’s root. The search includes that notebook and all its descendants.

If the query contains `global*`, the search ignores the notebook context and searches all unlocked notebooks. This is controlled by the `is_global` flag in the parsed query.

The search system does not pre‑index. Current items are found by walking the in‑memory tree. Historical items are found by querying Git.

---

## 7. Memory Usage

Only unlocked notebooks are kept in memory. Each notebook stores its entire structure (names, IDs, parent relationships) but not the content of its notes.

Locked subnotebooks are not loaded at all. Their only footprint is the registry entry (a few bytes).

When you unlock a notebook, its entire structure is loaded, but notes are loaded only when viewed.

This means you can have thousands of subnotebooks without affecting performance, as long as most remain locked.

---

## 8. Git Repository Location

All notebooks in a hierarchy share the same Git repository, which is located at the root notebook’s `custom_path`. The root is found by walking the `parent_id` chain until no parent exists.

Subnotebooks do not have their own repositories. This is important: commits for subnotebooks are recorded in the root repository. The root’s `structure.json` contains the entire hierarchy, and the root’s `notes.json` and `files.json` store content for all notes and files in the tree.

When you view activity for a subnotebook, the system runs Git commands in the root repository. This works because the root repository contains all the commits that affect any part of the hierarchy.

---

## 9. Deleting a Subnotebook

Forgetting a subnotebook removes it from the parent’s `subnotebooks` list and commits the change with `type: DELETED SUBNOTEBOOK`. The folder on disk remains; only the reference is removed.

Erasing a subnotebook runs the same `git-filter-repo` process as for a note, removing every commit that mentions any UUID in that subnotebook’s subtree. After erasure, a tombstone commit with `type: ERASED` is added.

The folder is not deleted immediately; only the Git history is rewritten. The user can later delete the folder manually if desired.

---

## 10. Why This Design Works

- **Hierarchy is stored in one place** – `structure.json` at the root. This keeps Git operations simple.
- **UUIDs are stable** – renaming or moving a subnotebook does not break references to its content.
- **Activity is recursive** – viewing a parent notebook shows changes anywhere below it, which matches how you think about a project or domain.
- **Memory is explicit** – unlocking a notebook loads its structure; locking it clears that structure. No background processes.
- **History is complete** – every change, whether at the root or ten levels deep, is recorded in the same repository and can be found by UUID.

This is not a file system. It is a semantic tree where every node is a first‑class object, and the system knows how to show you what changed anywhere in that tree.
