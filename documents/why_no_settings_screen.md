# Why There Is No Settings Screen

## A Document on Distributed Configuration

---

## Preface

This document explains why the application has no global settings screen. The decision was not made to be different. It was made because settings screens solve a problem this architecture does not have.

The description is factual. No claim of superiority is made. The reader may evaluate the logic for themselves.

---

## The Conventional Assumption

Most applications have a settings screen. It is a central place where the user configures the application's behaviour. The assumption is that settings are global – they affect everything the application does.

This assumption carries hidden costs:

- The user must **find** the settings screen
- The user must **remember** what settings exist
- The user must **understand** the effect of each setting
- The user must **return** to change settings when context changes
- The application must **store** settings somewhere

These costs are not large individually. But they add cognitive friction. And they assume that settings are independent of the objects they affect.

---

## The Alternative: Distributed Configuration

In this application, configuration is not centralised. It is distributed to the object it affects.

| What is configured | Where the configuration lives | When the user interacts with it |
|--------------------|------------------------------|--------------------------------|
| Editor preference | `config.json` file | Once, manually (or never, because defaults work) |
| Git account for a notebook | In the notebook's `git_config` and `account` fields | When linking the notebook to a remote |
| Remote repository for a notebook | In the notebook's `git_config` | When configuring the notebook |
| Visibility (private/public) | In the notebook's `git_config` | When needed, from the notebook view |
| Autolock behaviour | In the master registry entry for that notebook | From the `[C]hange` menu |
| Vault location | In the system entry for that notebook | From the `[C]hange` menu |

**There is no global settings screen because settings are not global. They belong to the object they configure.**

---

## Why This Aligns with Human Cognition

### Settings Are Actions, Not Places

Changing a setting is an action performed on an object. You do not go to a "place" to change a setting. You select the object and perform the action.

- You change a notebook's remote repository from the **notebook view** (`[C]hange`), not from a global settings screen.
- You change the vault location from the **notebook's change menu**, not from a global preferences panel.
- You lock a notebook from the **home screen** or **notebook list**, not from a settings toggle.

**The action is attached to the object. The user does not need to remember where the setting lives. It lives where the object lives.**

### Recognition Over Recall

A settings screen requires recall. The user must remember that a setting exists, what it does, and where to find it.

Distributed configuration uses recognition. When the user is viewing a notebook, the available actions (`[C]hange`, `[L]ink`, `[S]ync`) are visible in the footer. The user recognises the action they need. They do not recall a setting buried in a menu.

### Working Memory Is Not Required

Settings screens often require the user to hold context in working memory: "I am here to change X, but I must navigate to Y, then find Z, then adjust W."

Distributed configuration eliminates this. The context is already present. The user is already looking at the notebook. The action is one key press away.

### Forgiving Defaults

The application has very few settings because the defaults are chosen to work for most users in most situations.

- The editor is auto-detected.
- The vault is created automatically.
- The Git remote is configured only when the user chooses to link.
- The autolock flag is off by default (notebook stays unlocked across restarts).

**The user never needs to configure anything to start writing. The application works out of the box.**

---

## The Absence of a Settings Screen Is Not a Limitation

A settings screen is a solution to a problem: too many configurable behaviours. This application has few configurable behaviours because the architecture does not require them.

- No theme settings – the terminal provides the theme.
- No font settings – the terminal provides the font.
- No keybinding settings – the commands are single letters, visible in the footer.
- No plugin settings – there are no plugins.
- No sync settings – sync is a single action (`[S]ync`) that does everything.
- No account settings – accounts are managed per notebook, from the Notebook Manager.

**The absence of a settings screen is not a missing feature. It is a consequence of simplicity.**

---

## The One Configuration File

The application has a single configuration file: `config.json`. It contains two settings:

```json
{
    "edit": "micro",
    "view": "micro"
}
```

These are the user's preferred editors for editing and viewing. The file is created automatically. The user may edit it manually. There is no UI for it because the UI would add complexity without adding value. The user sets it once and never thinks about it again.

---

## What the User Experiences

A first‑time user launches the application. They see:

```
Root Notebooks

No notebooks yet.

Create your first notebook to get started!

[C]reate  [Q]uit
```

They press `c`. They enter a name. They start writing. They never encounter a settings screen. They never wonder "how do I change the font?" (there is no font setting). They never ask "where is the save button?" (the editor autosaves).

**The interface does not ask. It only responds.**

---

## Conclusion

The application has no settings screen because settings are distributed to the objects they affect. The user interacts with settings as actions, not as a separate configuration space. This aligns with human cognition: recognition over recall, working memory offloaded, context preserved.

The absence of a settings screen is not a design minimalism. It is a logical consequence of the architecture. Settings belong to objects. Objects are where the user already is.

The user does not need to find settings. The settings find the user.

---

**End of Document**
---
