# Navigation as Stack Manipulation: A Technical Description

## What This Document Is

This document describes the navigation system of Terminal Notes. It does not compare itself to other software. It does not advertise. It simply explains what exists, why it exists, and how it works.

The system was built for personal use. The design emerged from constraints and from observing what felt natural. Only later did I realise that it aligns with several cognitive principles. Those principles are mentioned here to explain *why* it feels natural, not to claim any academic achievement.

---

## 1. The Core Insight: Navigation Is Just Stack Manipulation

Most software separates navigation from data. There is a UI layer that manages screens, a router that parses URLs, and a history stack that tracks where the user has been.

In Terminal Notes, there is no separate navigation layer. The navigation state **is** a single Python list: `self.stack = []`. Each entry in the list is a dictionary containing:

- `screen` – the type of view (e.g., `"home"`, `"notebook"`, `"note"`)
- `id` – the UUID of the notebook or note being viewed
- `page` – the current page number for paginated lists

That is the entire navigation system.

### Operations

- **`push(screen, id, page)`** – append a new state to the stack. Used when the user opens a notebook or a note.
- **`pop()`** – remove the last state and return to the previous one. This is the `b` (back) command.
- **`replace_page(page)`** – update the page number of the current state without changing the stack depth.

There is no `forward` operation. There is no separate history manager. There is no URL router. The stack is the source of truth.

---

## 2. The Back Command (`b`)

When the user presses `b`, the system calls `pop()`. If the stack has more than one entry, the last entry is removed. The screen is then redrawn using the new current state.

This is not a “back” button in the browser sense. It is a **stack pop**. The user always returns to the exact previous state (same screen, same notebook, same page). There is no ambiguity.

Because the stack is transparent, the user never wonders “where will back take me?”. The answer is always “to the place you just came from”.

---

## 3. The Jump Command (`j3`, `j4`, etc.)

The path display shows the current hierarchy as numbered segments:

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

The numbers are not labels. They are commands.

Pressing `j3` does the following:

1. Look up the notebook corresponding to segment 3 (in this example, `projects`).
2. Clear the current stack and rebuild it from scratch:
   - `push("home")`
   - `push("list")`
   - `push("notebook", home_id)`
   - `push("notebook", user_id)`
   - `push("notebook", projects_id)`
   - `replace_page(0)`
3. Redraw the screen.

This is a **direct jump**. The user does not need to press back multiple times or click through intermediate levels. The target is visible on the screen, and the jump is instantaneous.

The path is truncated to a maximum of 7 segments (typically 4–7). This is not an arbitrary limit; it respects the average capacity of human working memory. The truncation uses ellipsis (`...`) to indicate omitted ancestors.

---

## 4. The Jump Back Command (`jb`)

`jb` is not the same as `b`. While `b` pops the navigation stack, `jb` returns to a **previous cognitive context** saved before a jump.

Whenever the user performs a `j3` jump, the current stack is saved into a separate `jump_history` list (maximum 20 entries). Pressing `jb` restores the most recently saved stack.

This allows the user to:

- Jump deep into a hierarchy to perform a task
- Work there for a while
- Press `jb` to return to exactly where they were before the jump

The system remembers the context. The user does not need to.

`jb` is a **temporal navigation** command. It does not rely on the linear stack order; it relies on explicit save points created by deliberate jumps.

---

## 5. Why There Is No Forward Button

Most software that has a back button also has a forward button. Terminal Notes does not.

The reason is simple: **forward is never needed**.

- The stack is fully visible through the path display. The user always knows where they are and how they got there.
- Jumps (`j3`) are direct and intentional. The user never “accidentally” lands somewhere.
- The only way to move forward is to perform an explicit action: open a notebook, view a note, or jump to a path segment.
- There is no “redo” operation because every action is either a deliberate move forward or a return to a known state.

A forward button would imply that the user might want to go to a place they have not explicitly chosen. That is not how the system is designed. The forward button is a workaround for navigation models that are not transparent. Here, it is unnecessary.

---

## 6. Cognitive Alignment (Observed, Not Designed)

The following observations were made after the system was built. They are offered as explanations for why the navigation feels natural, not as claims of intentional design.

| Principle | How It Manifests |
|-----------|------------------|
| **Miller’s Law** (7±2 chunks) | The path is truncated to 4–7 segments. The user never sees more than that. |
| **Hick’s Law** (decision time) | The number of visible commands is small (`v1`, `d2`, `j3`). The user does not need to choose from many options. |
| **Recognition over recall** | All actions and navigable items are visible. The user never needs to remember a hidden command. |
| **Spatial memory** | The numbered path creates a stable spatial map. The user learns the position of items, not just their names. |
| **Tesler’s Law** (complexity is conserved) | The navigation interface is simple. All complexity is moved into the stack implementation. |
| **Progressive disclosure** | Advanced commands (`j3`, `jb`) are only shown when the path has enough depth to make them useful. |

Again, these principles were not consulted during development. They are cited here to explain why the system feels effortless. The design came from personal experience, not from textbooks.

---

## 7. Performance Characteristics

- **`b` (back)** – O(1). A single list pop and a redraw.
- **`j3` (jump)** – O(d) where d is the depth of the target (typically ≤ 10). The stack is rebuilt by walking the parent chain.
- **`jb` (jump back)** – O(1). Restores a previously saved stack from the history list.
- **Memory** – The stack and jump history store only screen names, UUIDs, and page numbers. No UI state is duplicated.

There are no background processes. The navigation system only runs when the user presses a key.

---

## 8. Why This Matters (Without Hype)

This navigation system was built because other navigation models felt frustrating. The stack approach turned out to be simpler, faster, and more predictable than anything I had used before.

The fact that it aligns with cognitive principles is a useful observation, but not the goal. The goal was to build something that does not get in the way. The stack, the direct jumps, and the absence of a forward button are all consequences of that goal.

The system is open source. The code is available. Anyone can study it, use it, or modify it.

---

## 9. Conclusion

Terminal Notes navigates by manipulating a single stack. The user moves with `b` (back), `j3` (jump to path segment), and `jb` (jump back to a saved context). There is no forward button because it is never needed. The path is truncated to respect working memory limits. The interface is transparent because the stack is the interface.

This is not a claim of superiority. It is a description of what works.

```
