# Responsive Terminal UI Implementation

## A Technical Description of Dynamic Layout Adaptation

This document describes how the terminal user interface adapts to different terminal dimensions. The implementation uses only the Python standard library and does not rely on external UI frameworks or curses. The UI recalculates layout parameters on every screen redraw, allowing immediate adaptation when the terminal window is resized.

No claims of novelty or superiority are made. This is a factual description of the observed behaviour.

---

## 1. Core Mechanism

The system detects terminal dimensions using:

```python
try:
    columns, rows = shutil.get_terminal_size()
    width = max(60, columns)
    height = rows
except:
    width = 80
    height = 24
```

This function is called on every screen redraw, not only at startup. When the user resizes the terminal window, the very next screen refresh uses the new dimensions.

---

## 2. Dynamic Pagination

The number of items displayed per page depends on the current terminal height:

```python
fixed_lines = 3 + 1 + 2 + 3  # header, title, page indicator, footer
available = terminal_height - fixed_lines
items_per_page = int(available * 0.9)
items_per_page = max(1, items_per_page)
```

A 90% utilisation factor leaves a small margin at the bottom. The minimum is one item per page.

**Result:** A taller terminal shows more items per page. A shorter terminal shows fewer. The user never needs to configure pagination manually.

---

## 3. Fish‑Eye Path Display with Relative Numbering

The path header shows the current location as numbered segments. **Numbers always reset to 1 at the leftmost visible segment.** This means the number the user sees is always relative to the visible context, not an absolute depth.

**Example when the full path fits:**

```
[1]home/[2]user/[3]projects/[4]web/[5]src/
```

The user knows they are five levels deep, but the leftmost visible segment is `[1]home`.

**Example when the path is truncated (terminal too narrow):**

```
...[1]projects/[2]web/[3]src/[4]bin/[5]files/
```

The ellipsis (`...`) indicates that there are ancestors not shown. The numbering still starts at 1 for the leftmost visible segment (`projects`). The user does not need to remember the absolute depth. They only need to know that `[1]` refers to the first visible segment in the current display.

**Truncation algorithm:**

1. Start with the current location and a window of visible segments around it.
2. Expand outward until the rendered width exceeds available space.
3. If ancestors are omitted, add an ellipsis (`...`) at the left edge.
4. If descendants are omitted, add an ellipsis at the right edge.
5. Number the visible segments sequentially starting from 1.

**Properties:**

- The ellipsis appears **only when truncation occurs**. It signals that there are hidden ancestors.
- The user can always jump to `[1]` (the leftmost visible segment) or `[2]`, `[3]`, etc. without knowing absolute depths.
- The numbering is local to the display, not global.

**Result:** The user navigates by relative position, not by memorising absolute paths. The ellipsis provides an implicit cue that there is more above.

---

## 4. Page Indicator Positioning

The page indicator is centred in the available width:

```
<<                            Page 2 of 5                            >>
```

The `<<` symbol appears only when a previous page exists. It is placed exactly 4 spaces before the start of the centred page text. The `>>` symbol appears only when a next page exists. It is placed exactly 4 spaces after the end of the centred page text.

If the terminal is too narrow to show both arrows and the page text, the arrows are omitted. The page text remains visible.

**Result:** The pagination controls adapt to any width without overlapping.

---

## 5. Content Wrapping

Text content (notes, file contents) is wrapped to fit the current terminal width:

```python
def wrap_text(self, text, width=None):
    if width is None:
        width = self.terminal_width - 4
    # ... word‑based wrapping algorithm
```

The algorithm preserves paragraph boundaries. It does not break words unless a single word exceeds the line width (in which case it is split). The wrap width is recalculated on every screen redraw.

**Result:** Resizing the terminal re‑wraps the content immediately. No horizontal scrolling is required.

---

## 6. Column Layout

List views (notebooks, notes, search results, activity, timeline) use a two‑column layout where the left column contains the item number and title, and the right column contains metadata (timestamp, location).

The available width for the title is calculated as:

```
title_max = terminal_width - (len(item_number) + len(timestamp_text) + padding)
```

If the title exceeds this width, it is truncated with ellipsis. If the terminal is too narrow to show both title and timestamp, the timestamp is moved to the next line or omitted (depending on the view).

**Result:** Every item remains readable regardless of terminal width.

---

## 7. Minimum Width Behaviour

All layouts enforce a minimum width of 60 characters:

```python
width = max(60, columns)
```

If the terminal is narrower than 60 columns, the system assumes a width of 60. This prevents extreme truncation that would make the UI unusable. The user is not prevented from shrinking the window further, but the UI will not attempt to render below this threshold.

---

## 8. Supported Range

The implementation has been tested with terminal widths from 60 to 200+ characters and heights from 10 to 50+ rows. It is expected to work on any terminal that reports accurate dimensions via `shutil.get_terminal_size()`.

No assumptions are made about character cell aspect ratio, font size, or terminal emulator features.

---

## 9. Implementation Summary

| Feature | Detection Method | Update Trigger |
|---------|------------------|----------------|
| Terminal width | `shutil.get_terminal_size()` | Every redraw |
| Terminal height | `shutil.get_terminal_size()` | Every redraw |
| Items per page | Calculated from height | Every redraw |
| Path truncation | Calculated from width | Every redraw |
| Path ellipsis | Appears only when truncation occurs | Every redraw |
| Relative numbering | Always starts at 1 for leftmost visible segment | Every redraw |
| Page indicator position | Calculated from width | Every redraw |
| Text wrapping | Calculated from width | Every redraw |
| Column layout | Calculated from width | Every redraw |

No signals, callbacks, or asynchronous events are used. The system is purely reactive: each redraw re‑queries the terminal size and recomputes all layout parameters.

---

## 10. Compatibility

- Linux (tested on Debian 13)
- macOS (expected)
- Windows (expected)
- Any terminal that implements standard terminal size reporting

No `curses` library is used. No external UI framework is required.

---

## Conclusion

The user interface adapts to any terminal size from 60 columns upward and 10 rows upward. Pagination, path display, content wrapping, and page indicators all respond to dimension changes.

The path display uses relative numbering that always starts at 1 for the leftmost visible segment. An ellipsis (`...`) appears only when ancestors are truncated, signalling that deeper navigation is possible without requiring the user to remember absolute depth.

The implementation uses only the Python standard library and recalculates layout on every screen redraw.

The code is open. The behaviour is observable. The user never needs to configure terminal dimensions manually.

```
