"""Line crossing resolution for overlapping box-drawing characters.

Uses a 12-bit directional bitmask system (4 bits per weight tier):
  Bits 0-3:  single/light  (L, R, T, B)
  Bits 4-7:  heavy/bold    (L, R, T, B)
  Bits 8-11: double        (L, R, T, B)
"""

# Single (light) direction bits
_SL = 0b0000_0000_0001
_SR = 0b0000_0000_0010
_ST = 0b0000_0000_0100
_SB = 0b0000_0000_1000
_SH = _SL | _SR
_SV = _ST | _SB

# Heavy (bold) direction bits
_HL = 0b0000_0001_0000
_HR = 0b0000_0010_0000
_HT = 0b0000_0100_0000
_HB = 0b0000_1000_0000
_HH = _HL | _HR
_HV = _HT | _HB

# Double direction bits
_DL = 0b0001_0000_0000
_DR = 0b0010_0000_0000
_DT = 0b0100_0000_0000
_DB = 0b1000_0000_0000
_DH = _DL | _DR
_DV = _DT | _DB

CHAR_TO_MASK: dict[str, int] = {
    # === Single/Light ===
    "─": _SH,
    "│": _SV,
    "┌": _SR | _SB,
    "┐": _SL | _SB,
    "└": _SR | _ST,
    "┘": _SL | _ST,
    "├": _SR | _SV,
    "┤": _SL | _SV,
    "┬": _SH | _SB,
    "┴": _SH | _ST,
    "┼": _SH | _SV,
    # Rounded (same connectivity as light)
    "╭": _SR | _SB,
    "╮": _SL | _SB,
    "╰": _SR | _ST,
    "╯": _SL | _ST,

    # === Heavy/Bold ===
    "━": _HH,
    "┃": _HV,
    "┏": _HR | _HB,
    "┓": _HL | _HB,
    "┗": _HR | _HT,
    "┛": _HL | _HT,
    "┣": _HR | _HV,
    "┫": _HL | _HV,
    "┳": _HH | _HB,
    "┻": _HH | _HT,
    "╋": _HH | _HV,

    # === Double ===
    "═": _DH,
    "║": _DV,
    "╔": _DR | _DB,
    "╗": _DL | _DB,
    "╚": _DR | _DT,
    "╝": _DL | _DT,
    "╠": _DR | _DV,
    "╣": _DL | _DV,
    "╦": _DH | _DB,
    "╩": _DH | _DT,
    "╬": _DH | _DV,

    # === Mixed: Single + Heavy ===
    "╼": _SL | _HR,
    "╾": _HL | _SR,
    "╽": _ST | _HB,
    "╿": _HT | _SB,

    # Half-line characters (single direction)
    "╴": _SL,
    "╶": _SR,
    "╵": _ST,
    "╷": _SB,
    "╸": _HL,
    "╺": _HR,
    "╹": _HT,
    "╻": _HB,

    "┍": _HR | _SB,
    "┎": _SR | _HB,
    "┑": _HL | _SB,
    "┒": _SL | _HB,
    "┕": _HR | _ST,
    "┖": _SR | _HT,
    "┙": _HL | _ST,
    "┚": _SL | _HT,

    "┝": _HR | _SV,
    "┠": _SR | _HV,
    "┞": _SR | _HT | _SB,
    "┟": _SR | _ST | _HB,
    "┡": _HR | _HT | _SB,
    "┢": _HR | _ST | _HB,

    "┥": _HL | _SV,
    "┨": _SL | _HV,
    "┦": _SL | _HT | _SB,
    "┧": _SL | _ST | _HB,
    "┩": _HL | _HT | _SB,
    "┪": _HL | _ST | _HB,

    "┭": _HL | _SR | _SB,
    "┮": _SL | _HR | _SB,
    "┯": _HH | _SB,
    "┰": _SH | _HB,
    "┱": _HL | _SR | _HB,
    "┲": _SL | _HR | _HB,

    "┵": _HL | _SR | _ST,
    "┶": _SL | _HR | _ST,
    "┷": _HH | _ST,
    "┸": _SH | _HT,
    "┹": _HL | _SR | _HT,
    "┺": _SL | _HR | _HT,

    "┽": _HL | _SR | _SV,
    "┾": _SL | _HR | _SV,
    "┿": _HH | _SV,
    "╀": _SH | _HT | _SB,
    "╁": _SH | _ST | _HB,
    "╂": _SH | _HV,
    "╃": _HL | _SR | _HT | _SB,
    "╄": _SL | _HR | _HT | _SB,
    "╅": _HL | _SR | _ST | _HB,
    "╆": _SL | _HR | _ST | _HB,
    "╇": _HH | _HT | _SB,
    "╈": _HH | _ST | _HB,
    "╉": _HL | _SR | _HV,
    "╊": _SL | _HR | _HV,

    # === Mixed: Single + Double ===
    "╒": _DR | _SB,
    "╓": _SR | _DB,
    "╕": _DL | _SB,
    "╖": _SL | _DB,
    "╘": _DR | _ST,
    "╙": _SR | _DT,
    "╛": _DL | _ST,
    "╜": _SL | _DT,

    "╞": _DR | _SV,
    "╟": _SR | _DV,
    "╡": _DL | _SV,
    "╢": _SL | _DV,

    "╤": _DH | _SB,
    "╥": _SH | _DB,
    "╧": _DH | _ST,
    "╨": _SH | _DT,

    "╪": _DH | _SV,
    "╫": _SH | _DV,
}

# Reverse lookup: mask → char
MASK_TO_CHAR: dict[int, str] = {mask: ch for ch, mask in CHAR_TO_MASK.items()}
# Resolve ambiguity: rounded chars share masks with light corners; prefer light
for ch in ("╭", "╮", "╰", "╯"):
    mask = CHAR_TO_MASK[ch]
    MASK_TO_CHAR[mask] = {"╭": "┌", "╮": "┐", "╰": "└", "╯": "┘"}[ch]


def is_connectable(ch: str) -> bool:
    return ch in CHAR_TO_MASK


def resolve_crossing(existing: str, new: str) -> str:
    """Combine two overlapping box-drawing chars into the correct crossing char."""
    mask = CHAR_TO_MASK.get(existing, 0) | CHAR_TO_MASK.get(new, 0)
    return MASK_TO_CHAR.get(mask, new)
