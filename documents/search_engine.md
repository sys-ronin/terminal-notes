# Search Engine Architecture

## Overview

The search system provides a unified interface to find items regardless of their state—current, deleted, renamed, restored, or erased. It operates from any screen, with context automatically applied unless overridden. The query language is order‑free, designed to match how users naturally think about what they are looking for.

This document describes the search engine's design, how it interprets queries, and how results are presented. It does not advertise features. It explains how the system works.

---

## 1. Where Search Can Be Accessed

Search is available from every screen where the user might need to find something.

- **Home screen** – searches all unlocked notebooks globally.
- **Notebook view** – searches the current notebook and all its subnotebooks (the entire hierarchy).
- **Subnotebooks view** – same as notebook view (searches the parent notebook and its descendants).
- **Note view** – searches from the notebook containing the note (context preserved).

The context is automatically set to the notebook the user is currently viewing. This means a search from a subnotebook will include that subnotebook and all its descendants, but not siblings or ancestors.

---

## 2. Query Structure

A search query is a space‑separated list of tokens. The parser processes tokens in any order except for the `in*` token, which must appear at the end. Tokens are recognized by their pattern; unrecognized tokens become the text search.

### 2.1 Action Wildcards

Action wildcards filter by the type of change recorded in Git history. They are always written with an asterisk:

- `created*` – items that were created.
- `deleted*` – items that were deleted (soft delete).
- `updated*` or `edited*` – items that were modified.
- `renamed*` – items whose title or filename changed.
- `restored*` – items that were restored from deletion.
- `erased*` – items that were permanently erased (tombstones).

When an action wildcard is present, search results show the item title without an action prefix. When no action wildcard is present, results show the action prefix (`created note:`, `updated file:`, etc.) to provide context.

### 2.2 Type Wildcards

Type wildcards filter by the kind of item:

- `note*` – only regular notes.
- `file*` – only file notes (with extensions).
- `sub*` – only subnotebooks.
- `notebook*` – only root notebooks.

These can be combined with action wildcards. For example, `created* file*` finds only created files.

### 2.3 Time Filters

Time filters restrict results to items that were created, updated, or deleted within a specific timeframe.

- `date* DD-MM-YYYY` – items from a specific date.
- `date* DD-MM-YYYY DD-MM-YYYY` – items within a date range.
- `today*` – items from the current calendar day.
- `yesterday*` – items from the previous calendar day.
- `thisweek*` – items from Monday to Sunday of the current week.
- `lastweek*` – items from the previous week.

Time filters are applied to the commit date, not the content date.

### 2.4 Scope

- `in* notebook_name` – restricts search to a specific notebook and its descendants. This token must appear at the end of the query.
- `g*` or `global*` – overrides any context or `in*` scope and searches all unlocked notebooks. Can appear anywhere in the query.

When no scope is specified, the current context (the notebook being viewed) is used. On the home screen, the default scope is global.

### 2.5 Text Search

Any token not recognized as a wildcard becomes text to be matched. Text search is case‑insensitive and uses substring matching on titles and content (for current notes) or on commit messages (for historical items). Multiple text tokens are combined with AND logic.

---

## 3. Query Examples by User Need

Different users have different ways of finding what they need. The search system accommodates simple, intermediate, and complex queries without requiring memorization.

### 3.1 Simple Queries

**A student wants to find notes about a specific topic.**

- `s machine learning`

**A developer wants to find a specific file.**

- `s Dockerfile`

**A writer wants to find all notes containing a phrase.**

- `s "project timeline"`

**A researcher wants to see what they created last week.**

- `s created* thisweek*`

**A sysadmin wants to find a deleted configuration.**

- `s deleted* nginx.conf`

**A project manager wants to find all meeting notes in the work notebook.**

- `s meeting in* work`

### 3.2 Intermediate Queries

**A scientist wants to see what they changed in a specific project last month.**

- `s updated* date* 01-02-2026 28-02-2026 in* experiment`

**A legal professional needs to find deleted case files from a specific date.**

- `s deleted* date* 15-03-2026 in* case-2024`

**A developer wants to find all Python files they created, not just any files.**

- `s created* file* .py`

**A writer needs to find all versions of a chapter that were renamed.**

- `s renamed* chapter* in* book`

**A sysadmin wants to see what was erased from a server configuration.**

- `s erased* server*`

**A student needs to find notes from yesterday that contain "exam".**

- `s yesterday* exam`

### 3.3 Complex Queries

**A researcher wants to find files created in the last week about a specific subject, but only in a specific notebook.**

- `s created* file* thisweek* data in* experiments`

**A legal professional needs to find deleted documents from last month that contained "contract", regardless of which notebook they were in.**

- `s g* deleted* lastweek* contract`

**A developer wants to find all changes (created, updated, deleted) to a specific file across the entire system.**

- `s g* config.yaml`

**A project manager wants to see everything related to a client in the last three months, including deleted items.**

- `s deleted* date* 01-12-2025 01-03-2026 acme in* client-projects`

**A writer needs to find all versions of a chapter that were renamed, but only those that existed in a specific notebook.**

- `s renamed* chapter* in* book-draft`

**A sysadmin wants to find all erased items from a specific server notebook, across any time.**

- `s erased* in* webserver`

### 3.4 Combining Filters

Filters can be combined in any order, making complex queries natural.

- `s file* deleted* yesterday* report in* work` – finds deleted files from yesterday with "report" in the work notebook.
- `s g* created* thisweek* meeting` – finds created meetings from this week, globally.
- `s updated* today* config in* server` – finds configurations updated today in the server notebook.
- `s deleted* file* lastweek* backup in* archive` – finds backup files deleted last week in the archive notebook.

The parser removes recognised tokens regardless of position, so users do not need to remember a specific sequence.

---

## 4. How Results Are Collected

The search engine collects items from two sources.

### 4.1 Current Items

Current items (notes, files, notebooks that exist in the active structure) are collected by walking the in‑memory notebook tree. The walk includes all unlocked notebooks (or only the current context if specified). For each note, the title and content are matched against the text query. For each notebook or subnotebook, the name is matched.

### 4.2 Historical Items

Historical items (deleted, renamed, restored, erased) are collected by querying Git. The resurrection engine is used to find commits matching the action wildcard and text query. For each match, the item is reconstructed from the commit before the action (for deleted items) or from the commit itself (for restored items). Erased items return only a tombstone.

Results from both sources are deduplicated by UUID, filtered by type and date range, sorted by date (newest first), and limited to 50.

---

## 5. Result Presentation

### 5.1 Action Prefix

- If the query contains an action wildcard, results show only the title (and change statistics if available). The action is implied by the search.
- If the query does not contain an action wildcard, results show the action prefix (`created`, `updated`, `deleted`, etc.) and change statistics.

### 5.2 Location

Each result shows its location relative to the search context:

- On the home screen, locations show the full path from the root notebook, truncated with ellipsis when deep.
- In a notebook view, locations show the path relative to that notebook.
- For items outside the context, the full path from the root is shown.

### 5.3 Deleted Items

Deleted items are marked with `(deleted)` in the result line. When viewed, they show the content as it existed before deletion, with a restore button.

---

## 6. Context and Overrides

The search engine automatically sets the context to the current screen. From a notebook view, the context is that notebook and all its subnotebooks. From the home screen, the context is global.

The `g*` token overrides the context, forcing a global search regardless of where it is invoked.

The `in*` token overrides the context for that search only, restricting results to the named notebook and its descendants.

---

## 7. Performance

- Current items are searched in memory. The walk is O(n) on the number of items in unlocked notebooks, which is typically small.
- Historical items are queried using Git. `git log` with `--grep` uses Git's internal index and is efficient.
- Results are limited to 50 to keep the interface responsive.
- No background indexing is performed. All searches are on‑demand.

---

## 8. Design Principles

- **Order‑free.** Users should not have to remember a specific order. They type what they mean.
- **Intent‑based.** The system uses wildcards to understand whether the user is looking for created items, deleted items, etc.
- **Context‑aware.** A search from a notebook should search that notebook, unless the user explicitly overrides.
- **Consistent.** The same search syntax works from any screen, with the same result formatting.

---

## 9. Summary

The search engine is a unified interface to the entire knowledge base, current and historical. It understands action, type, time, and scope, and presents results in a way that matches the user's intent. The query language is designed to be discovered through use, not memorized. The system does not require training; it responds to what the user types.
