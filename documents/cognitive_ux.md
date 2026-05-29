# The Cognitive Architecture of Terminal Notes

## How the Interface Respects Human Memory

---

## Preface

This document describes the cognitive principles embedded in the Terminal Notes interface. The system does not ask the user to remember. It externalizes memory. It shows what is possible. It forgives mistakes.

The design was not derived from textbooks. It emerged from the constraints of building for a single user who could not afford to forget – the author himself. Only later was the alignment with cognitive science discovered.

This document describes what exists. The reader may evaluate the principles for themselves.

---

## The Core Problem: Software Forces You to Remember

Conventional software assumes the user will remember:

- Where settings are hidden
- What keyboard shortcuts do
- Where they are in the navigation hierarchy
- What they were doing before they switched contexts
- How to recover from mistakes

This is not user error. It is design error. The software externalizes its own complexity onto the user's limited working memory.

Terminal Notes inverts this relationship. The software remembers. The user writes.

---

## Principle 1: Recognition, Not Recall

**The problem:** Settings screens, keyboard shortcut cheatsheets, and hidden menus require the user to recall information that is not currently visible.

**The solution:** Every possible action is visible on the current screen. The footer shows exactly what commands are available.

**Implementation:**

```
[C]reate  [V]iew  [S]earch  [D]elete  [L]ock  [M]anage  [Q]uit
```

**What the user experiences:** They never ask "how do I delete?" The `[D]elete` button is always visible when deletion is possible. They never need to recall a shortcut. They recognize the letter and press it.

**Cognitive principle:** Recognition requires less cognitive load than recall (Norman, 1988). The interface does not test memory. It presents choices.

---

## Principle 2: Spatial Memory, Not Path Memorization

**The problem:** File paths and breadcrumbs require the user to remember or parse abstract strings. `home/user/projects/web/src/components/Header.js` is not how humans navigate space.

**The solution:** The system shows the current location as numbered segments. The user navigates by relative position, not absolute path.

**Screenshot:**

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

**What the user experiences:** They do not need to remember that they are five levels deep. The path is displayed. They do not need to type `cd ../../..`. They press `j3` to jump to "projects". They press `jb` to return to where they were.

**Cognitive principle:** Human spatial memory operates by relative position, not absolute coordinates (Tversky, 1992). You know you are three rooms from the entrance. You do not recite GPS coordinates.

---

## Principle 3: Working Memory Offload (The Jump Back)

**The problem:** When exploring deeply, users forget where they came from. The forward/back buttons in browsers are temporal, but they do not remember the user's cognitive context.

**The solution:** The system maintains a jump history. `jb` returns to the exact previous location – same notebook, same page, same scroll position.

**Screenshot:**

```
[1]home/[2]user/[3]projects/
... (user jumps to level 3, works there, then presses jb)
[1]home/[2]user/[3]projects/   ← returned to original context
```

**What the user experiences:** They explore without fear. They know they can always return. The system remembers where they were so they do not have to.

**Cognitive principle:** Working memory has limited capacity (Miller, 1956). Offloading location tracking to the environment frees cognitive resources for the task at hand.

---

## Principle 4: Numbered Items (Affordance)

**The problem:** Selecting items requires the user to know the item's name or use a mouse. Both are slow. Both require attention.

**The solution:** Every displayed item has a number. The number is not a label. It is a command.

**Screenshot:**

```
[1] Meeting Notes
[2] Project Plan
[3] Ideas
```

**What the user experiences:** They do not think "I want to view the first item." They think "I want to view that one." Their finger presses `1`. The action is immediate. The interface does not insert itself between intention and action.

**Cognitive principle:** Affordance (Gibson, 1979) means the object's properties suggest its use. A numbered item affords pressing that number. No instruction is needed.

---

## Principle 5: Pagination with Visible Boundaries

**The problem:** Long lists overwhelm working memory. Users lose track of where they are.

**The solution:** The system paginates lists and shows a centered page indicator with arrows.

**Screenshot:**

```
<<                            Page 2 of 5                            >>
```

**What the user experiences:** They always know which page they are on. They know if there is a previous or next page. The arrows are not hidden. The page number is not buried in a status bar.

**Cognitive principle:** Maintaining orientation reduces cognitive load. The user does not need to infer context. The context is displayed.

---

## Principle 6: The Lock Button as Memory Flush

**The problem:** Unlocked notebooks keep keys and structure in memory. The user may not need them anymore, but the system does not know.

**The solution:** The lock button (`[L]ock`) is not just a security feature. It is an explicit memory manager.

**Screenshot:**

```
[1] 🔐 my-notes    ← unlocked (key in memory)
[2] 🔒 work        ← locked (key cleared, structure unloaded)
```

**What the user experiences:** When they finish working on a notebook, they lock it. The system clears encryption keys and unloads the notebook structure. Memory is freed. The cognitive context is closed. They do not wonder "is this still open?" The lock symbol tells them.

**Cognitive principle:** The user controls what stays in working memory. The system does not guess. This respects the user's cognitive boundary.

---

## Principle 7: Soft Delete as Forgiveness

**The problem:** Accidental deletion is permanent in many systems. Users live in fear of pressing the wrong key.

**The solution:** Soft delete (`[D]elete` → `forget`) removes the item from view but keeps it in Git history. Deleted items are searchable (`deleted*`) and restorable (`[R]estore`).

**Screenshot:**

```
Search: 'deleted*' (2 matches)

[1] deleted: old-notes                                        [archive]
[2] deleted: temp-file                                           [scratch]

[S]earch  [V]iew  [R]estore  [B]ack  [Q]uit
```

**What the user experiences:** They delete without fear. They know the item is not gone. They can restore it later. The system remembers what they chose to forget.

**Cognitive principle:** Forgetting is often retrieval inhibition, not deletion. The memory trace remains. Soft delete models this biological reality.

---

## Principle 8: Hard Delete as Conscious Erasure

**The problem:** Some data must be truly erased. Soft delete is not enough for sensitive information.

**The solution:** Hard delete (`[D]elete` → `erase`) requires the user to type `erase` to confirm. The system then removes the item from Git history entirely.

**Screenshot:**

```
Delete note 'secret-password':
  1. Forget (keep in history)
  2. Erase (remove completely)

Choose [1/2] or Enter to cancel: 2
Type 'erase' to confirm permanent removal: erase
```

**What the user experiences:** They cannot accidentally erase. The confirmation requires deliberate action. When they confirm, the erasure is permanent. The system does not second-guess. It obeys.

**Cognitive principle:** Permanent deletion requires conscious, deliberate action. The system does not make this decision for the user.

---

## Principle 9: The Disappearing Interface

**The problem:** Most interfaces demand attention. Toolbars, menus, notifications, animations – all compete for cognitive resources.

**The solution:** The terminal shows only what is necessary. No toolbar. No menu bar. No animations. No notifications. The footer shows commands. The rest of the screen is content.

**Screenshot:**

```
[1]terminal-notes/

Note Title: The Disappearing Interface
Created: May 21  Updated: May 21 21:42

The interface should not be noticed. It should serve the user's intent,
then step aside. This is not minimalism. This is cognitive hygiene.

                                 Page 1 of 1

[E]dit  [V]iew  [T]imeline  [R]ename  [B]ack  [Q]uit
```

**What the user experiences:** They write. They do not think about the software. The software does not interrupt. It waits. It serves. It disappears.

**Cognitive principle:** Flow state (Csikszentmihalyi, 1990) requires uninterrupted attention. The interface must not compete with the task. It must vanish.

---

## Principle 10: Verbs, Not Nouns

**The problem:** Menus and buttons are often labelled with nouns ("File", "Edit", "View"). The user must translate their intention into a category.

**The solution:** Every command is a verb. `[C]reate`, `[V]iew`, `[E]dit`, `[D]elete`, `[S]earch`, `[S]ync`, `[L]ock`, `[M]anage`.

**What the user experiences:** They think "I want to create." Their finger presses `c`. The mapping from intention to action is direct. There is no intermediate category selection.

**Cognitive principle:** Action verbs map directly to intentions. Nouns require an extra cognitive step. The interface should speak the language of action.

---

## Summary: What the User Never Needs to Remember

| The user never needs to remember | Because |
|--------------------------------|---------|
| Keyboard shortcuts | All commands are visible in the footer |
| Where they are in the hierarchy | The path is displayed with numbers |
| Where they came from | `jb` returns to previous context |
| How to delete | `[D]elete` is always visible |
| How to search | `[S]earch` is always visible |
| Which commands are available | The footer shows only relevant commands |
| That file notes can be exported | `[X]port` appears only for file notes |
| Pagination state | Page indicator shows current position |
| Whether a notebook is unlocked | Lock symbol (🔐/🔒) is always visible |
| How to recover from mistakes | Soft delete keeps history; restore is one key |

**The system remembers. The user writes.**

---

## The Accidental Discovery

These principles were not researched. They were not borrowed from textbooks. They emerged from building for a single user who could not afford to forget – the author himself.

The alignment with cognitive science (Miller, Norman, Tversky, Gibson, Csikszentmihalyi) was discovered after the fact. The system existed before the explanation.

This is not a claim of design genius. It is an observation of emergence. The constraints forced simplicity. Simplicity revealed patterns. Patterns matched the brain.

**The interface disappears because it was built by a mind that needed it to disappear.**

---

## Conclusion

Terminal Notes does not ask the user to remember. It shows what is possible. It externalizes location. It forgives mistakes. It obeys deliberate commands. It disappears when not needed.

The user does not need to learn the interface. The interface learns the user. Not through AI. Through alignment.

**The user writes. The system remembers. Nothing else.**

---

**End of Document**

---
