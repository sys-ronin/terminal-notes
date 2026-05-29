# A Writing Environment That Disappears: Design for Focus, Not Features

## What This Document Is

This document describes how Terminal Notes is designed to be used without learning, without confusion, and without distraction. It does not compare itself to other software. It does not advertise. It simply explains the principles that make the interface fade into the background, leaving only the act of writing.

The design was not built for a specific audience. It was built for myself, a sysadmin who got frustrated by bloated software. Only later did I realise that the same principles work for people with no technical background, for older users, and even for those with memory loss. That realisation is documented here.

---

## 1. Zero Learning Curve: The Interface Teaches Itself

A user should never need to read a manual. The interface should show what is possible, right now, on the screen.

### Visible Commands

Every command is visible in the footer of the screen:

```
[C]reate  [V]iew  [S]earch  [D]elete  [B]ack  [Q]uit
```

The user sees the letter and presses it. There are no hidden menus. No right‑click context menus. No gestures to memorise.

### Numbers as Commands

When a list of items appears, each item has a number:

```
[1] Meeting Notes
[2] Project Plan
[3] Ideas
```

The number is not just a label. Pressing `1` views the first item. Pressing `2` views the second. The user learns this the first time they see a list. No explanation is needed.

### Contextual Buttons

Buttons appear only when they are useful. For example:

- `[A]ctivity` appears only when the current notebook has a Git history.
- `[T]imeline` appears only when viewing a note.
- `[J]ump` appears only when the path is deep enough to make jumping useful.

The interface never shows a disabled button. It never shows an option that cannot be used right now.

### No Settings Screen

There is no settings button. Configuration is either automatic (editors are detected, paths are created) or performed as an action on a specific object (e.g., changing a password is done from the notebook’s detail view, not from a global preferences panel).

The user never has to answer “how do I change the font?” because there is no font setting. The terminal provides the font. The app uses what the terminal gives.

**Result:** A first‑time user can create a notebook and start writing within seconds. No tutorial. No setup wizard. No “getting started” guide.

---

## 2. Noob‑Proof: Forgiveness Is Built In

A “noob” is not a beginner. A noob is anyone under pressure. Under stress, even experts make mistakes. The system should forgive those mistakes.

### Soft Delete (Forget)

When the user deletes an item, it is not destroyed. It is removed from the current view but remains in Git history. The user can search for `deleted*` and restore the item with a single key (`[R]estore`).

The user never loses work permanently by accident.

### Hard Delete (Erase) Requires Confirmation

If the user truly wants to erase an item forever, they must type `erase` to confirm. The system does not assume that a single key press means permanent destruction.

### Crash Recovery

If the external editor crashes or the power fails, the system saves recovery files every 30 seconds. When the user reopens the notebook, any unsaved content is automatically restored. The user never loses work to a crash.

### Clear Error Messages

When something goes wrong, the error message tells the user what happened and what to do next. It does not show a stack trace. It does not assume the user knows Git internals.

Example: If a notebook is encrypted and the user enters the wrong password, the system says “Wrong password.” It does not say “Decryption failed: invalid tag.”

**Result:** A user cannot accidentally destroy data. Mistakes are reversible. Crashes are recoverable.

---

## 3. Alzheimer‑Friendly: Designed for Memory Loss

The design principles that make the interface easy for a stressed expert also make it usable for someone with memory loss. This was not planned; it emerged from the same constraints.

### Recognition, Not Recall

All commands are visible. The user does not need to remember that “Ctrl+S saves”. They see `[S]earch` and press `s`. They see `[1] Meeting Notes` and press `1`.

### Spatial Memory

The path display shows the current location as numbered segments:

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

The user does not need to remember “I am in projects/web/src”. They see the numbers and know where they are. Pressing `j3` jumps back to `projects`. The path is a spatial map, not an abstract address.

### No Forward Button

There is no “forward” button. The user never accidentally lands in an unfamiliar screen. Every movement is either a deliberate jump to a visible target (`j3`) or a return to a known state (`b` or `jb`).

### Jump Back (`jb`) as External Memory

When the user jumps deep into a hierarchy, the system saves the previous location. Pressing `jb` returns to exactly where they were. The user does not need to remember the path back. The system remembers.

### Consistent Layout

Every screen has the same structure: a header with the current location, a list of items, a page indicator, and a footer with commands. The user never needs to relearn a new layout.

**Result:** A person with memory loss can navigate, write, and recover without frustration. The system does not rely on short‑term memory.

---

## 4. The Disappearing Interface: Writing, Not Clicking

An interface that disappears is one that the user does not notice. The user thinks about their writing, not about the tool.

### No Modal Dialogs

The system never interrupts the user with “Are you sure?” while they are writing. Confirmation is only required for destructive actions (erase). Editing, saving, and navigating happen instantly.

### No Toolbars

There are no toolbars, no ribbons, no status bars. The only persistent UI is the footer, which shows the available commands. The rest of the screen is dedicated to content.

### No Loading Spinners

All operations are instantaneous. Navigating, opening a note, searching, and saving happen in less than a second. There is no “loading…” message.

### The Lock Button as Memory Manager

When the user locks a notebook, the system removes the encryption keys and the notebook structure from memory. The notebook becomes a 🔒 symbol. The user is not distracted by content they are not using.

When the user unlocks the notebook, they are prompted for a password. The system does not assume that “unlocked” means “keep unlocked forever”.

**Result:** The user writes. The system waits. The interface is present only when needed.

---

## 5. Forever Design: Built to Last

The system is designed to be used for decades without requiring changes.

### No External Dependencies

The application is a single executable. It does not require an internet connection. It does not require a cloud account. It does not require a package manager. It runs on any machine with Python or as a standalone binary.

### Plain Text Storage

All data is stored as JSON and Git commits. Even if the application stops being maintained, the data can be read by any text editor or Git client. The user is never locked in.

### No Automatic Updates

The system does not force updates. The version that works today will work tomorrow. There is no “phoning home” to check for new versions.

### Offline First

The system works without internet. Git remotes are optional. Encryption does not require a network. The user owns their data completely.

**Result:** The user can write for a lifetime without worrying about software rot, vendor lock‑in, or forced upgrades.

---

## 6. How the Environment Feels

A user sits down, launches the application, and sees:

```
Root Notebooks

[1] Work
[2] Personal
[3] Archive

[C]reate  [V]iew  [S]earch  [Q]uit
```

They press `1`. They see a list of notes. They press `c`, type a title, and start writing in an editor. They save, exit the editor, and the note appears in the list.

They never think about “how do I format text?” because there is no formatting. They never think about “where is the save button?” because the editor autosaves. They never think about “how do I go back?” because `b` is always visible.

The interface disappears. The writing remains.

---

## 7. Conclusion

Terminal Notes was built to be used, not learned. It has no settings, no tutorials, no hidden commands. It forgives mistakes, recovers from crashes, and never loses data by accident. It works for a first‑time user, for a stressed expert, and for someone with memory loss. It is designed to last for decades.

The interface disappears because the only thing that should remain is the writing.

```
