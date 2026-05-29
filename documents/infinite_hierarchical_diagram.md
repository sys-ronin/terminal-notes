# The Infinite Notebook: A Structural Diagram of Terminal Notes

## Visualising Unlimited Depth in a Hierarchical Writing System

---

## Preface

This document presents a structural diagram of a Terminal Notes notebook hierarchy. The diagram shows how notebooks can contain subnotebooks, which contain more subnotebooks, creating indefinite depth.

No theoretical limit exists on depth. Each subnotebook can contain more subnotebooks, which can contain more, ad infinitum.

---

## The Smart Path Header (How Location Is Displayed)

When you are deep in the hierarchy, the system shows a truncated path with numbered segments.

**Key rules (from the code):**
- The root (or first visible notebook) is always numbered `[1]`
- Ellipsis (`...`) indicates truncated ancestors and has **no number**
- Numbering resets per screen and is sequential from the first visible segment
- The user can press `j1`, `j2`, `j3` to jump to any visible segment
- `jb` jumps back to previous location

**Examples:**

| Depth | Smart Path Display |
|-------|---------------------|
| Root | `[1]terminal-notes/` |
| Level 1 | `[1]terminal-notes/[2]Work/` |
| Level 2 | `[1]terminal-notes/[2]Work/[3]Projects/` |
| Level 3 | `.../[1]Work/[2]Projects/[3]web-app/` |
| Level 4 | `.../[1]Projects/[2]web-app/[3]backend/` |
| Level 5 | `.../[1]web-app/[2]backend/[3]models/` |
| Level 6 | `.../[1]backend/[2]models/[3]user/` |

**The user never sees an absolute path. Only relative position.**

---

## The Infinite Hierarchy Diagram

```mermaid
flowchart LR
    Root["📓 terminal-notes"]

    subgraph Level1[" "]
        direction LR
        L1_Work["📓 Work"]
        L1_Personal["📓 Personal"]
        L1_Archive["📓 Archive"]
    end

    Root --> L1_Work
    Root --> L1_Personal
    Root --> L1_Archive

    subgraph Work["📓 Work"]
        direction LR
        L2_Projects["📓 Projects"]
        L2_Meetings["📓 Meetings"]
        L2_Docs["📓 Documentation"]
        L2_Clients["📓 Clients"]
    end

    L1_Work --> Work

    subgraph Projects["📓 Projects"]
        direction LR
        P1["📄 plan.md"]
        P2["📄 timeline.md"]
        P3["🐍 deploy.py"]
        P4["📓 web-app"]
    end

    L2_Projects --> Projects

    subgraph Meetings["📓 Meetings"]
        direction LR
        M1["📄 05-20.md"]
        M2["📄 05-21.md"]
        M3["📄 actions.md"]
    end

    L2_Meetings --> Meetings

    subgraph Docs["📓 Documentation"]
        direction LR
        D1["📄 README.md"]
        D2["📄 api.md"]
        D3["🔧 config.yaml"]
    end

    L2_Docs --> Docs

    subgraph Clients["📓 Clients"]
        direction LR
        C1["📓 ClientA"]
        C2["📓 ClientB"]
    end

    L2_Clients --> Clients

    subgraph ClientA["📓 ClientA"]
        direction LR
        CA1["📓 Contracts"]
        CA2["📓 Designs"]
        CA3["📓 Emails"]
    end

    C1 --> ClientA

    subgraph Contracts["📓 Contracts"]
        direction LR
        CT1["📄 agreement.pdf"]
        CT2["📄 nda.pdf"]
    end

    CA1 --> Contracts

    subgraph Designs["📓 Designs"]
        direction LR
        DG1["🎨 wireframe.fig"]
        DG2["📄 notes.md"]
    end

    CA2 --> Designs

    subgraph Emails["📓 Emails"]
        direction LR
        E1["📄 05-01.md"]
        E2["📄 05-15.md"]
    end

    CA3 --> Emails

    subgraph WebApp["📓 web-app"]
        direction LR
        WA1["📓 backend"]
        WA2["📓 frontend"]
        WA3["📓 database"]
    end

    P4 --> WebApp

    subgraph Backend["📓 backend"]
        direction LR
        BE1["🐍 app.py"]
        BE2["🐍 routes.py"]
        BE3["🐍 models.py"]
        BE4["📓 api"]
    end

    WA1 --> Backend

    subgraph Models["🐍 models.py"]
        direction LR
        MD1["📓 User Model"]
        MD2["📓 Product Model"]
    end

    BE3 --> Models

    subgraph UserModel["📓 User Model"]
        direction LR
        UM1["🐍 fields.py"]
        UM2["🐍 methods.py"]
    end

    MD1 --> UserModel

    subgraph Fields["🐍 fields.py"]
        direction LR
        FL1["username.py"]
        FL2["email.py"]
        FL3["password.py"]
    end

    UM1 --> Fields

    subgraph Api["📓 api"]
        direction LR
        AP1["📓 v1"]
        AP2["📓 v2"]
    end

    BE4 --> Api

    subgraph V1["📓 v1"]
        direction LR
        V1A["🐍 users.py"]
        V1B["🐍 products.py"]
    end

    AP1 --> V1

    subgraph Frontend["📓 frontend"]
        direction LR
        FR1["⚛️ App.jsx"]
        FR2["🎨 App.css"]
        FR3["📓 components"]
    end

    WA2 --> Frontend

    subgraph Components["📓 components"]
        direction LR
        CP1["📓 Header"]
        CP2["📓 Footer"]
    end

    FR3 --> Components

    subgraph Header["📓 Header"]
        direction LR
        HD1["⚛️ Header.jsx"]
        HD2["🎨 Header.css"]
    end

    CP1 --> Header

    subgraph Database["📓 database"]
        direction LR
        DB1["🐍 schema.py"]
        DB2["📄 migrations.sql"]
    end

    WA3 --> Database

    subgraph Personal["📓 Personal"]
        direction LR
        PE1["📓 Journal"]
        PE2["📓 Coding"]
        PE3["📓 Reading"]
    end

    L1_Personal --> Personal

    subgraph Journal["📓 Journal"]
        direction LR
        J1["📄 05-15.md"]
        J2["📄 05-16.md"]
        J3["📄 05-17.md"]
        J4["📄 05-18.md"]
    end

    PE1 --> Journal

    subgraph Coding["📓 Coding"]
        direction LR
        CD1["🐍 script.py"]
        CD2["📓 Python Projects"]
    end

    PE2 --> Coding

    subgraph Archive["📓 Archive"]
        direction LR
        AR1["📓 Old Projects"]
        AR2["📓 Completed"]
    end

    L1_Archive --> Archive

    subgraph OldProjects["📓 Old Projects"]
        direction LR
        OP1["📓 2025"]
        OP2["📓 2024"]
    end

    AR1 --> OldProjects

    subgraph Y2025["📓 2025"]
        direction LR
        Y1["📄 jan.md"]
        Y2["📄 feb.md"]
        Y3["📄 mar.md"]
    end

    OP1 --> Y2025

    subgraph Y2024["📓 2024"]
        direction LR
        Y4["📄 week1.md"]
        Y5["📄 week2.md"]
    end

    OP2 --> Y2024

    %% Styling - 3 colors, no backgrounds
    classDef notebook stroke:#2C3E50,stroke-width:2px,color:#2C3E50
    classDef note stroke:#27AE60,stroke-width:1.5px,color:#27AE60
    classDef file stroke:#E67E22,stroke-width:1.5px,color:#E67E22

    class Root notebook
    class L1_Work,L1_Personal,L1_Archive notebook
    class L2_Projects,L2_Meetings,L2_Docs,L2_Clients notebook
    class L3_Contracts,L3_Designs,L3_Emails notebook
    class C1,C2,CA1,CA2,CA3 notebook
    class P4,WA1,WA2,WA3 notebook
    class BE4,AP1,AP2,FR3,CP1,CP2 notebook
    class MD1,MD2,PE1,PE2,PE3,AR1,AR2 notebook
    class OP1,OP2,Y2025,Y2024 notebook

    class P1,P2,M1,M2,M3,D1,D2,CT1,CT2,DG2,E1,E2,FR1,FR2,DB2,J1,J2,J3,J4,Y1,Y2,Y3,Y4 note
    class P3,CD1,BE1,BE2,BE3,V1A,V1B,HD1,HD2,DB1,UM1,UM2,FL1,FL2,FL3 file
    class DG1,FR1,FR2,HD1,HD2 file
```

---

## How to Read This Diagram

| Shape | Meaning |
|-------|---------|
| 📓 Notebook | A container (can hold notes, files, and more notebooks) |
| 📄 Note | A regular text note |
| 🐍, ⚛️, 🎨, 🔧, etc. | File notes with syntax highlighting |
| Arrows | Parent → child relationship |

---

## What the Diagram Shows

The diagram shows a hierarchy with:

- **1 root notebook** (`terminal-notes`)
- **3 level 1 subnotebooks** (Work, Personal, Archive)
- **~30 subnotebooks** across levels 2-6
- **~35 notes** (regular text notes)
- **~20 file notes** (code, config, markup)

**But this is just a slice.** Every subnotebook could contain more. There is no enforced limit.

---

## How the Smart Path Works at Different Depths

| Depth | Location | Smart Path Display |
|-------|----------|---------------------|
| Root | `terminal-notes` | `[1]terminal-notes/` |
| Level 1 | `Work` | `[1]terminal-notes/[2]Work/` |
| Level 2 | `Projects` | `[1]terminal-notes/[2]Work/[3]Projects/` |
| Level 3 | `web-app` | `.../[1]Work/[2]Projects/[3]web-app/` |
| Level 4 | `backend` | `.../[1]Projects/[2]web-app/[3]backend/` |
| Level 5 | `models` | `.../[1]web-app/[2]backend/[3]models/` |
| Level 6 | `User Model` | `.../[1]backend/[2]models/[3]User/` |

---

## The Infinity Is Manageable

The user never sees the entire diagram. They see only one level at a time:

From root:
```
[1] Work
[2] Personal
[3] Archive
```

From Work:
```
[1] Projects
[2] Meetings
[3] Documentation
[4] Clients
```

From Projects:
```
[1] plan.md
[2] timeline.md
[3] deploy.py
[4] web-app
```

From web-app:
```
[1] backend
[2] frontend
[3] database
```

**Each screen shows only the immediate children. The depth is invisible until you descend.**

---

## Conclusion

The diagram shows a hierarchy that goes 6 levels deep. But there is no limit. Each subnotebook can contain more subnotebooks. The smart path header ensures the user never loses orientation.

**The user explores. The system navigates. The interface disappears.**

---

**End of Document**
---
