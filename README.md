# Palaterm

A terminal-based drawing application inspired by [MonoSketch](https://github.com/nicemicro/MonoSketch). Draw rectangles, lines, and text boxes using Unicode box-drawing characters, all within your terminal.

## Features

- **Rectangle tool** — drag to draw bordered rectangles
- **Line tool** — draw connecting lines (orthogonal L-shaped or straight braille)
- **Text tool** — create text boxes with editable content inside a border
- **Select tool** — click to select, drag to move, handles to resize, rectangle-select multiple shapes
- **Border styles** — light (┌─┐), heavy (┏━┓), double (╔═╗), rounded (╭─╮), braille (⡇⠉⢸)
- **Line styles** — orthogonal (L-shaped) or straight (braille sub-pixel)
- **Line endings** — arrow, square, circle, star
- **Connectors** — lines snap to box edges and follow when boxes move
- **Text alignment** — horizontal (left/center/right) and vertical (top/middle/bottom)
- **Layer ordering** — bring forward/backward, send to front/back
- **Shape alignment** — align multiple selected shapes (left/center/right/top/middle/bottom)
- **Colors** — foreground color per shape
- **Fill styles** — none, light, medium, full, space
- **Copy/paste** — duplicate shapes with connectors preserved
- **Charset toggle** — switch between Unicode and ASCII rendering
- **Undo/redo** — full command history
- **Save/open** — versioned JSON-based `.palaterm` file format (v1)
- **Export** — copy to clipboard as plain text, HTML, SVG, or presenterm format
- **Infinite canvas** — scroll in any direction
- **Auto theme** — detects light/dark terminal background

## Installation & Usage

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run palaterm
```

Open an existing file:

```bash
uv run palaterm path/to/file.palaterm
```

### Keybindings

| Key | Action |
|-----|--------|
| `s` | Select tool |
| `b` | Rectangle (box) tool |
| `t` | Text tool |
| `l` | Line tool |
| `Delete` | Delete selected shape(s) |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |
| `Ctrl+C` | Copy |
| `Ctrl+X` | Cut |
| `Ctrl+V` | Paste |
| `Ctrl+S` | Save |
| `Ctrl+Shift+S` | Save As |
| `Ctrl+O` | Open file |
| `Ctrl+E` | Export to clipboard |
| `Ctrl+U` | Toggle Unicode/ASCII |
| `a` / `A` | Cycle horizontal/vertical text alignment |
| `]` / `[` | Bring forward / send backward |
| `}` / `{` | Bring to front / send to back |
| `Escape` | Deselect |
| `↑↓←→` | Scroll canvas |
| `q` | Quit |

## Development

```bash
uv sync                    # install deps
uv run pytest              # run tests
uv run ruff check          # lint
uv run ruff format --check # check formatting
```

## Code Structure

```
palaterm/
├── app.py              # Textual app, keybindings, event wiring
├── canvas.py           # Shape collection, hit-testing, compositing
├── canvas_geometry.py  # Virtual extent and scroll math
├── commands.py         # Undo/redo command pattern
├── connectors.py       # Line-to-box snap anchoring
├── controllers.py      # Tool and panel state controllers
├── crossings.py        # Line crossing/intersection glyphs
├── exporters.py        # HTML, SVG, presenterm export
├── geometry.py         # Point and Rect primitives
├── rendering.py        # Viewport rendering to terminal strips
├── serialization.py    # JSON save/load (format v1)
├── sidebar_state.py    # Pure-function sidebar derivation
├── style_application.py # Attribute change via commands
├── models/             # Shape classes, enums, charset, braille
├── tools/              # Select, Rectangle, Text, Line tool logic
└── widgets/            # Canvas widget, toolbar, panels, status bar, modals
```

## License

MIT
