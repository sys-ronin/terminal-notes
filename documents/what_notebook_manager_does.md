# Notebook Manager: What It Does

## How to Open It

From the main screen, press `[M]anage`. This opens the Notebook Manager.

---

## What You See First

A list of all your notebooks. Each notebook shows:

- Its name
- Whether it is locked (🔒) or unlocked (🔐)
- How many notes it has
- How many files it has
- How many sub‑notebooks it contains
- Which Git account it uses (if any)

---

## What You Can Do

### Add a Git Account

If you want to save your notebooks online, you need an account with a service like GitHub, GitLab, or Bitbucket.

- Press `[A]dd`
- Choose your service
- Enter your username
- Create a token (the app will guide you)
- Paste the token

The app stores your token safely. It never leaves your computer in plain text.

### Link a Notebook to Your Account

Once you have an account, you can link a notebook to it.

- Select a notebook from the list
- Choose your account
- The app suggests a repository name (you can change it)
- Choose whether the repository is private or public
- Confirm

After linking, your notebook can be saved online and synced across your devices.

### Save Your Notebook Online (Push)

When you have made changes on your computer, you can send them to the online copy.

- Select the notebook
- Press `[S]ync`
- The app checks what needs to be sent
- Confirm

Your changes appear online. Other devices can now download them.

### Get Updates from Online (Pull)

If you made changes on another device, you can download them.

- Select the notebook
- Press `[S]ync`
- The app checks what needs to be downloaded
- Confirm

Your local notebook now has the latest changes from all your devices.

### Change Who Can See Your Notebook (Visibility)

If your notebook is online, you can change who can see it.

- Select the notebook
- Press `[V]isibility`
- Choose private (only you) or public (everyone)

This only affects the online copy. Your local notebook stays the same.

### Remove the Online Copy (Delete Remote)

If you no longer want your notebook online:

- Select the notebook
- Press `[D]elete`
- Choose "Delete remote repository only"
- Type the repository name to confirm

Your local notebook stays on your computer. The online copy is gone.

### Stop Using the Online Copy (Unlink)

If you want to keep the online copy but stop syncing from this computer:

- Select the notebook
- Press `[D]elete`
- Choose "Unlink remote"
- Confirm

The online copy remains. Your local notebook becomes independent.

### Change Your Password

If your notebook is encrypted, you can change the password.

- Select the notebook
- Press `[C]hange`
- Choose "Change password"
- Enter your old password (or recovery phrase)
- Enter your new password twice

The recovery phrase stays the same. You only change the password you type daily.

### Change Where Your Keys Are Stored (Vault Location)

Your encryption keys are kept in a file called a vault. You can move this file to a USB drive or another folder.

- Select the notebook
- Press `[C]hange`
- Choose "Change vault location"
- Pick an existing vault or create a new one
- Confirm

This is for advanced users who want to keep their keys separate from their notebooks.

### See Which Devices Can Unlock Your Notebook (Trusted Devices)

Each computer you use creates its own entry in the vault. You can see all of them.

- Select the notebook
- Press `[C]hange`
- Choose "Trusted devices"

You can remove old devices. If you remove the current device, the notebook locks immediately. You will need your recovery phrase to unlock it again.

### Remove an Account

If you no longer use a Git account:

- Go to the Accounts screen
- Select the account
- Press `[R]emove`

The account is removed from the app. Notebooks linked to it are no longer linked. They stay on your computer.

### Import a Notebook from Another Location

If you have a notebook folder on a USB drive or in another folder:

- Press `[I]mport` from the main screen
- Choose "Import existing notebook"
- Enter the folder path

The notebook appears in your list. All your notes are there.

### Import from a Git URL

If someone shared a notebook repository with you:

- Press `[I]mport`
- Choose "Import from Git URL"
- Paste the URL

The app downloads the notebook. If it is encrypted, you need the recovery phrase.

### Delete a Notebook from Your Computer

If you no longer need a notebook:

- Select the notebook from the list
- Press `[D]elete`
- Choose "Standard delete"

The notebook folder is removed from your computer. You can import it again later if you have a backup or an online copy.

---

## What You Never Need to Do

- You never need to touch Git commands.
- You never need to resolve merge conflicts.
- You never need to understand branches or rebasing.
- You never need to remember where your keys are stored.
- You never need to configure anything before you start writing.

The app handles all of this. You just write.

---

## The Accounts Screen

When you press `[A]ccounts`, you see a list of your Git accounts. For each account, you see how many notebooks are actually linked to it on this computer.

You can:

- Add a new account (`[A]dd`)
- View an account's repositories (`[V]iew`)
- Remove an account (`[R]emove`)

The count shown is real. It is based on your actual notebook folders, not on remembered information.

---

## The Bigger Picture

The Notebook Manager exists for tasks you do once or rarely:

- Add an account – once
- Link a notebook – once
- Change visibility – rarely
- Remove a device – rarely

Everything else – writing, editing, searching, viewing history – happens in the main application.

The manager steps aside. It does not interrupt your writing. It is there when you need it, invisible when you do not.

---

**End of Document**
