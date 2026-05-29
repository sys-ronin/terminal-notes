# Prior Art Disclosure: Universal Navigation System
## Hierarchical Fish‑Eye Navigation with Relative Numbering

**Date of Disclosure:** March 2026  
**Author:** sys_ronin  
**Status:** Public, Timestamped, Irrevocable  
**Repository:** [github.com/sys-ronin/terminal-notes](https://github.com/sys-ronin/terminal-notes)

---

## Summary

A universal navigation system for hierarchical data structures that enables:

1. **O(1) cognitive access** to any node regardless of depth
2. **Navigation by relative position** rather than absolute path
3. **Fish‑eye path display** respecting human working memory limits
4. **Single‑keystroke jump** to any visible segment
5. **Smart truncation with ellipsis** for infinite depth
6. **Jump history** for backtracking
7. **Pagination** for breadth navigation
8. **Context‑aware action buttons** that change based on selected item type
9. **Unified search across all states** with type/action filters

This system is not tied to note‑taking. It is a general navigation paradigm applicable to any hierarchical interface: network configuration, filesystems, databases, cloud consoles, code navigation, API documentation, system settings, container orchestration, and any other domain where users navigate depth.

---

## The Cognitive Principle

Human spatial memory operates by relative position, not absolute path.

You do not remember: *"I am at /home/user/projects/web/src/components/Header"*  
You remember: *"I am three levels deep in the web project"*

This system externalizes that cognitive pattern:
- Position is shown, not hidden
- Depth is visible, not inferred
- Navigation is relative, not absolute

---

## The Core Architecture (8 Layers)

### Layer 1: Relative Numbering

Every displayed item has a number. The numbers reset per screen. Numbers are independent of absolute depth.

```
[1] projects
  [1] web
    [1] index.html
    [2] styles.css
    [3] script.js
  [2] mobile
  [3] desktop
[2] personal
[3] archives
```

**Numbering rules:**
- Numbers start at 1 for each screen
- Numbers are sequential (1, 2, 3…)
- Numbers reset when context changes
- Numbers are displayed, not hidden

**Commands:**
- `v1`, `v2`, `v3` → view item 1, 2, 3
- `d1`, `d2`, `d3` → delete item 1, 2, 3
- `r1`, `r2`, `r3` → rename item 1, 2, 3
- `c` → create (applies to current context)
- `b` → back (pop navigation stack)

---

### Layer 2: Fish‑Eye Path Display

The path header shows current position with relative numbering:

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

When path exceeds terminal width, smart truncation applies:

```
[1]…/[2]web/[3]src/
```

**Truncation rules:**
- Left side truncated first (older ancestors)
- Ellipsis (`…`) indicates truncated content
- Minimum 4‑7 segments shown (Miller’s Law)
- Each visible segment is numbered sequentially

**Result:** Users always know:
- Where they are (visible segments)
- How deep they are (ellipsis indicates truncation)
- How to go back (`jb` command)
- How to jump (`j<number>` command)

---

### Layer 3: Numbered Segment Jump

Each segment in the path header has a number:

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

**Commands:**
- `j2` → jump to “user” (second segment)
- `j4` → jump to “web” (fourth segment)
- `jb` → jump back to previous position

**Jump behavior:**
- If target is in current navigation stack: truncate stack at target
- If target not in stack: rebuild full path to target
- Jump history preserved (`jb` navigates backward through jumps)
- Maximum 20 jump history entries

**Result:** Navigation by position, not by typing paths.

---

### Layer 4: Smart Path Truncation Algorithm

Given: Full path segments `S[0..n-1]`, current position `i`, terminal width `W`

**Algorithm:**
1. Start with segments `i-2..i+2` (current context plus 2 each direction)
2. If total width < W, expand outward
3. If total width > W, contract inward
4. Add ellipsis (`…`) for truncated left segments
5. Add ellipsis for truncated right segments
6. Number segments sequentially starting at 1

**Result:**
- Always shows 4‑7 segments (Miller’s Law)
- Always shows current position
- Always shows context (parent and child)
- Always shows relative numbers

---

### Layer 5: Depth Navigation

Users navigate depth through:

**Numbered items (vertical navigation):**
- `v1` → view first item
- `v2` → view second item
- Navigation is by visible position

**Numbered path segments (horizontal navigation):**
- `j2` → jump to second path segment
- Navigation is by structural position

**Jump back (temporal navigation):**
- `jb` → return to previous position
- Navigation is by history

**Page navigation (breadth navigation):**
- `n` → next page
- `p` → previous page
- Navigation is by pagination

All navigation uses only numbers and single keys. No path memorization.

---

### Layer 6: Pagination

When items exceed screen height, pagination applies:

```
[1] Item 1
[2] Item 2
…
[14] Item 14

<<                            Page 2 of 5                            >>
```

**Pagination rules:**
- Items per page = terminal height – fixed UI elements
- Page indicator centered
- `<<` shows previous page available
- `>>` shows next page available
- `n`/`p` commands navigate pages

**Result:** Infinite breadth navigable with O(1) cognitive load.

---

### Layer 7: Jump History

Every jump (`j<number>`) saves current position to history.

**History structure:**
- Maximum 20 entries (FIFO)
- Each entry contains: screen, id, page
- Jump back (`jb`) pops most recent entry

**Jump back behavior:**
- Restores previous screen, notebook, page
- Works across different notebook depths
- Works across different screens (notebook view, search results, timeline)

**Result:** Navigation is reversible. Users explore freely.

---

### Layer 8: Responsive Terminal UI

Terminal dimensions detected at each redraw:

```python
try:
    columns, rows = shutil.get_terminal_size()
    width = max(60, columns)
    height = rows
except:
    width = 80
    height = 24
```

All elements adapt:
- Items per page = height – fixed_lines
- Path truncation based on width
- Pagination indicators adjust to width
- No fixed sizes. No assumption about terminal.

---

## Unified Search with Action Buttons

### Search Interface

Search results show all items regardless of state (current, deleted, renamed):

```
Search: 'config' (3 matches)

[1] deleted: config.txt                                          [network]
[2] updated: interface.conf (+12/-5)                             [router1]
[3] created: vlan10                                              [switch]

[S]earch  [V]iew  [R]estore  [B]ack  [Q]uit
```

**Search syntax (order independent):**
- `created*`, `deleted*`, `updated*`, `renamed*`, `restored*`, `erased*`
- `file*`, `sub*`, `notebook*`
- `date* DD-MM-YYYY [DD-MM-YYYY]`
- `today*`, `yesterday*`, `thisweek*`, `lastweek*`
- `g*` (global override)
- `in* [context]` (must be at end)
- text query (remaining words)

**Intent‑based display:**
- With action wildcard (`created*`): NO action prefix
- Without action wildcard: SHOW action prefix

---

### Context‑Aware Action Buttons

Action buttons change based on selected item type and state.

---

## Applications Across Domains (Interface Visualizations)

### Domain 1: Network Device Configuration (Cisco, Juniper, Arista)

```
=====================================
[1]configure/[2]interface/[3]gigabitethernet0/1/
=====================================

[1] ip address 10.0.0.1/24
[2] mtu 1500
[3] speed 1000
[4] duplex full

[V]iew  [E]dit  [C]opy  [A]pply  [D]elete  [R]evert  [B]ack  [Q]uit

> v1
```

---

### Domain 2: Filesystem Navigation

```
=====================================
[1]home/[2]user/[3]projects/[4]web/[5]src/
=====================================

[1] index.js (3.2KB)
[2] styles.css (12KB)
[3] script.js (8KB)
[4] package.json (1.1KB)

[V]iew  [E]dit  [M]ove  [C]opy  [D]elete  [R]ename  [B]ack  [Q]uit

> v1
```

---

### Domain 3: Database Administration

```
=====================================
[1]production/[2]public/[3]tables/
=====================================

[1] users (2,345 rows)
[2] orders (45,678 rows)
[3] products (123 rows)
[4] inventory (890 rows)

[V]iew  [E]dit  [S]elect  [B]ackup  [D]rop  [Q]uit

> v1
```

---

### Domain 4: Cloud Infrastructure (AWS)

```
=====================================
[1]EC2/[2]Instances/[3]i-1234abcd/
=====================================

[1] Name: web-server
[2] Type: t3.medium
[3] State: running
[4] Public IP: 54.123.45.67

[V]iew  [S]tart  [S]top  [R]eboot  [T]erminate  [C]onnect  [B]ack  [Q]uit

> v1
```

---

### Domain 5: Container Orchestration (Kubernetes)

```
=====================================
[1]namespaces/[2]default/[3]pods/
=====================================

[1] web-app (Running)
[2] db (Running)
[3] cache (Pending)
[4] worker (Running)

[V]iew  [L]ogs  [E]xec  [D]elete  [R]estart  [B]ack  [Q]uit

> v1
```

---

### Domain 6: API Documentation

```
=====================================
[1]API/[2]v2/[3]users/
=====================================

[1] GET /users - List all users
[2] POST /users - Create user
[3] GET /users/{id} - Get user
[4] PUT /users/{id} - Update user
[5] DELETE /users/{id} - Delete user

[V]iew  [T]est  [C]opy  [E]xport  [B]ack  [Q]uit

> v1
```

---

### Domain 7: System Monitoring (Cockpit)

```
=====================================
[1]System/[2]Services/
=====================================

[1] nginx (active)
[2] postgresql (active)
[3] redis (inactive)
[4] docker (active)

[V]iew  [S]tart  [S]top  [R]estart  [L]ogs  [B]ack  [Q]uit

> v1
```

---

### Domain 8: Operating System Settings

```
=====================================
[1]System/[2]Network/[3]Wi-Fi/
=====================================

[1] Starbucks WiFi (Connected)
[2] Home Network (Saved)
[3] Office Guest (Open)
[4] Mobile Hotspot (Available)

[V]iew  [C]onnect  [F]orget  [P]roperties  [B]ack  [Q]uit

> v1
```

---

### Domain 9: Source Code Repository (Git)

```
=====================================
[1]repository/[2]src/[3]main.py
=====================================

[1] def main(): (line 42)
[2] import sys (line 1)
[3] class App: (line 15)

[V]iew  [E]dit  [C]ommit  [P]ush  [P]ull  [B]ranch  [B]ack  [Q]uit

> v1
```

---

### Domain 10: IoT Device Management

```
=====================================
[1]factory/[2]floor2/[3]sensor_012/
=====================================

[1] Temperature: 23.5°C
[2] Humidity: 45%
[3] Status: Active
[4] Battery: 87%

[V]iew  [C]alibrate  [R]eboot  [U]pdate  [D]isable  [B]ack  [Q]uit

> v1
```

---

## Unified Search Across All Domains

### Search Results (Network Domain)

```
deleted: (2 matches)

[1] interface vlan10                                                [switch]
[2] route 0.0.0.0/0                                                 [router]

[S]earch  [V]iew  [R]estore  [B]ack  [Q]uit

> v1
```

### Search Results (Filesystem Domain)

```
deleted: (1 matches)

[1] old_config.txt                                                  [backup]

[S]earch  [V]iew  [R]estore  [B]ack  [Q]uit

> v1
```

### Search Results (Database Domain)

```
updated: (1 matches)

[1] users (+234/-120)                                               [public]

[S]earch  [V]iew  [B]ack  [Q]uit

> v1
```

### Search Results (Cloud Domain)

```
deleted: (1 matches)

[1] i-5678efgh                                                      [terminated]

[S]earch  [V]iew  [R]estore  [B]ack  [Q]uit

> v1
```

---

## Cognitive Science Validation

| Theory | How the System Implements It |
|--------|------------------------------|
| **Spatial Memory** (Tversky, 1992) | Relative numbers, not absolute paths |
| **Working Memory** (Miller, 1956) | Shows 4‑7 path segments |
| **Recognition Over Recall** (Norman, 1988) | All commands visible in footer |
| **Affordance** (Gibson, 1979) | Numbers invite pressing; commands invite typing |
| **Progressive Disclosure** (Norman, 1988) | Basic navigation first; advanced discovered through use |
| **Fish‑Eye View** (Furnas, 1986) | Context + focus display with truncated ancestors |
| **Cognitive Load** (Sweller, 1988) | No path memorization; no command recall |
| **Flow** (Csikszentmihalyi, 1990) | Navigation becomes automatic |

---

## Prior Art Establishment

This disclosure establishes prior art for:

1. Hierarchical navigation by relative numbering
2. Fish‑eye path display with numbered segments
3. Smart truncation algorithm with ellipsis
4. Jump command (`j<number>`) for path segments
5. Jump back (`jb`) with history
6. Pagination with numbered items
7. Responsive terminal adaptation
8. Unified search across temporal states with action/type filters
9. Context‑aware action buttons that change based on selected item type
10. Any combination of the above in any domain

This prior art is timestamped, public, and irrevocable.

**Any system implementing these patterns—regardless of domain—practices the disclosed invention. No party may patent these concepts.**

---

## License

This navigation system is disclosed under the Eternal License (see LICENSE file in repository). Key provisions:

- Use freely for any purpose
- Modify and distribute modifications
- Build products and services
- Do not patent any concept disclosed
- Do not assert intellectual property rights
- Do not remove attribution

---

## Conclusion

This is not a note‑taking feature. This is a universal navigation paradigm for any hierarchical information system.

The patterns disclosed here will be used by:

- **Network engineers** configuring devices
- **Sysadmins** navigating filesystems
- **DBAs** managing databases
- **Cloud operators** managing infrastructure
- **DevOps engineers** managing containers
- **API consumers** reading documentation
- **Users** adjusting settings
- **Developers** managing code
- **IoT operators** managing devices

They will navigate by number, not by path.  
They will jump by position, not by command.  
They will search across time, not just current state.  
They will act with context‑aware buttons that match their domain.  
They will never memorize another absolute path.

This is the legacy of this work.

---

**End of Disclosure**
```
