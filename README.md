# Palaterm

A terminal-based drawing application inspired by [MonoSketch](https://github.com/nicemicro/MonoSketch). Draw rectangles, lines, and text boxes using Unicode box-drawing characters, all within your terminal.

## Features

- **Rectangle tool** — drag to draw bordered rectangles
- **Line tool** — draw connecting lines (orthogonal L-shaped or straight braille)
- **Text tool** — create text boxes with editable content inside a border
- **Select tool** — click to select, drag to move, handles to resize, rectangle-select multiple shapes
- **Border styles** — light (┌─┐), heavy (┏━┓), double (╔═╗), rounded (╭─╮), braille (⡇⠉⢸)
- **Line styles** — orthogonal (L-shaped) or straight (braille sub-pixel)
- **Text alignment** — horizontal (left/center/right) and vertical (top/middle/bottom)
- **Layer ordering** — bring forward/backward, send to front/back
- **Shape alignment** — align multiple selected shapes (left/center/right/top/middle/bottom)
- **Charset toggle** — switch between Unicode and ASCII rendering
- **Undo/redo** — full command history
- **Save/open** — JSON-based `.palaterm` file format
- **Export** — copy selection or full canvas to clipboard
- **Infinite canvas** — scroll in any direction
- **Auto theme** — detects light/dark terminal background

## Installation & Usage

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run palaterm
```

### Keybindings

| Key | Action |
|-----|--------|
| `s` | Select tool |
| `r` | Rectangle tool |
| `t` | Text tool |
| `l` | Line tool |
| `Delete` | Delete selected shape(s) |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save As |
| `Ctrl+O` | Open file |
| `Ctrl+E` | Export to clipboard |
| `Ctrl+U` | Toggle Unicode/ASCII |
| `a` / `A` | Cycle horizontal/vertical text alignment |
| `]` / `[` | Bring forward / send backward |
| `}` / `{` | Bring to front / send to back |
| `↑↓←→` | Scroll canvas |
| `q` | Quit |

## Code Structure

```
palaterm/
├── app.py              # Textual app, keybindings, event wiring
├── canvas.py           # Shape collection, hit-testing, compositing
├── rendering.py        # Viewport rendering to terminal strips
├── serialization.py    # JSON save/load
├── crossings.py        # Line crossing/intersection detection
├── geometry.py         # Point and Rect primitives
├── shapes.py           # Re-exports from models
├── models/             # Shape classes, enums, charset, braille
├── tools/              # Select, Rectangle, Text, Line tool logic
├── widgets/            # Canvas widget, toolbar, panels, status bar, modals
├── controllers/        # Tool and panel state controllers
└── commands/           # Undo/redo command pattern
```
