"""Builds the CS4110 presentation deck.

Diagram-led and deliberately light on text: every slide carries one idea and one
visual. Three of them are automata -- the compiler as a machine, the word-token DFA,
and the parser's control loop -- because those are what an audience remembers.

    python docs/slides/build_deck.py [output.pptx]
"""

from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent.parent
LOGO = ROOT / "docs" / "report" / "figures" / "logo.png"

# Palette mirrors the application's theme tokens (src/styles/theme.css).
DEEP = RGBColor(0x0F, 0x3D, 0x2E)
ACCENT = RGBColor(0x17, 0x66, 0x4A)
GOLD = RGBColor(0xE2, 0xBC, 0x58)
NAVY = RGBColor(0x16, 0x20, 0x2A)
PANEL = RGBColor(0xE8, 0xF3, 0xEC)
CANVAS = RGBColor(0xF7, 0xF9, 0xF8)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREY = RGBColor(0x46, 0x5A, 0x50)
FAINT = RGBColor(0x8A, 0x9A, 0x92)
DANGER = RGBColor(0xAD, 0x35, 0x46)
INFO = RGBColor(0x2E, 0x5B, 0xCC)
RULE = RGBColor(0xCB, 0xDC, 0xD2)

W, H = 10.0, 5.625


# --------------------------------------------------------------------------- utils
def add_slide(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = CANVAS
    bg.line.fill.background()
    bg.shadow.inherit = False
    return s


def box(slide, x, y, w, h, fill=WHITE, line=RULE, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        line_w=1.0, radius=0.12):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if line is None:
        sh.line.fill.background()
    else:
        sh.line.color.rgb = line
        sh.line.width = Pt(line_w)
    sh.shadow.inherit = False
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sh.adjustments[0] = radius
        except (IndexError, ValueError):
            pass
    return sh


def text(slide, x, y, w, h, runs, size=14, color=NAVY, bold=False, align=PP_ALIGN.LEFT,
         anchor=MSO_ANCHOR.TOP, spacing=1.0, font="Segoe UI"):
    """`runs` is a string, or a list of (text, {overrides}) for mixed formatting."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

    lines = runs if isinstance(runs, list) else [(runs, {})]
    for i, item in enumerate(lines):
        body, over = item if isinstance(item, tuple) else (item, {})
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = over.get("align", align)
        p.line_spacing = over.get("spacing", spacing)
        if over.get("space_before"):
            p.space_before = Pt(over["space_before"])
        r = p.add_run()
        r.text = body
        f = r.font
        f.name = over.get("font", font)
        f.size = Pt(over.get("size", size))
        f.bold = over.get("bold", bold)
        f.color.rgb = over.get("color", color)
    return tb


def header(slide, title, num, kicker=None):
    box(slide, 0, 0, W, 0.92, fill=DEEP, line=None, shape=MSO_SHAPE.RECTANGLE)
    box(slide, 0, 0.92, W, 0.045, fill=GOLD, line=None, shape=MSO_SHAPE.RECTANGLE)
    if kicker:
        text(slide, 0.55, 0.14, 7.5, 0.24, kicker, size=10, color=GOLD, bold=True)
        text(slide, 0.55, 0.38, 7.8, 0.44, title, size=21, color=WHITE, bold=True)
    else:
        text(slide, 0.55, 0.26, 7.8, 0.5, title, size=22, color=WHITE, bold=True,
             anchor=MSO_ANCHOR.MIDDLE)
    text(slide, 8.9, 0.28, 0.6, 0.4, str(num), size=13, color=GOLD, bold=True,
         align=PP_ALIGN.RIGHT)


def tip(connector):
    """python-pptx exposes no arrowhead API, so write the tailEnd element directly."""
    ln = connector.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:tailEnd"),
                             {"type": "triangle", "w": "med", "len": "med"}))
    return connector


def arrow(slide, x, y, w, color=ACCENT, h=0.0):
    """Horizontal (or sloped) arrow connector."""
    c = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Inches(x), Inches(y), Inches(x + w), Inches(y + h)
    )
    c.line.color.rgb = color
    c.line.width = Pt(2)
    return tip(c)


def state(slide, cx, cy, d, label, sub=None, fill=WHITE, line=ACCENT, accepting=False,
          label_size=13, label_color=DEEP):
    """A circular automaton state, optionally drawn as an accepting double circle."""
    if accepting:
        outer = slide.shapes.add_shape(
            MSO_SHAPE.OVAL, Inches(cx - d / 2 - 0.07), Inches(cy - d / 2 - 0.07),
            Inches(d + 0.14), Inches(d + 0.14)
        )
        outer.fill.background()
        outer.line.color.rgb = line
        outer.line.width = Pt(1.5)
        outer.shadow.inherit = False
    sh = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(cx - d / 2), Inches(cy - d / 2),
                                Inches(d), Inches(d))
    sh.fill.solid()
    sh.fill.fore_color.rgb = fill
    sh.line.color.rgb = line
    sh.line.width = Pt(2)
    sh.shadow.inherit = False
    off = 0.10 if sub else 0.0
    text(slide, cx - d / 2, cy - 0.13 - off, d, 0.26, label, size=label_size,
         color=label_color, bold=True, align=PP_ALIGN.CENTER)
    if sub:
        text(slide, cx - d / 2 - 0.2, cy + 0.02, d + 0.4, 0.22, sub, size=8.5,
             color=GREY, align=PP_ALIGN.CENTER)
    return sh


def edge_label(slide, cx, y, w, label, color=GREY, size=9.5, bold=False):
    text(slide, cx - w / 2, y, w, 0.22, label, size=size, color=color, bold=bold,
         align=PP_ALIGN.CENTER)


def note(slide, x, y, w, h, title, body, tint=PANEL, bar=ACCENT):
    box(slide, x, y, w, h, fill=tint, line=None)
    box(slide, x, y, 0.055, h, fill=bar, line=None, shape=MSO_SHAPE.RECTANGLE)
    text(slide, x + 0.22, y + 0.14, w - 0.42, 0.24, title, size=11, color=DEEP, bold=True)
    # Clamped: a negative extent makes PowerPoint reject the whole file.
    text(slide, x + 0.22, y + 0.42, w - 0.42, max(0.22, h - 0.55), body, size=10.5,
         color=GREY, spacing=1.15)


# --------------------------------------------------------------------------- slides
def slide_title(prs):
    s = add_slide(prs)
    box(s, 0, 0, W, 3.75, fill=DEEP, line=None, shape=MSO_SHAPE.RECTANGLE)
    box(s, 0, 3.75, W, 0.06, fill=GOLD, line=None, shape=MSO_SHAPE.RECTANGLE)

    if LOGO.exists():
        s.shapes.add_picture(str(LOGO), Inches(0.62), Inches(0.62), height=Inches(1.5))

    text(s, 2.42, 0.72, 7.0, 0.24, "THE ICT UNIVERSITY  ·  YAOUNDÉ, CAMEROON",
         size=10.5, color=GOLD, bold=True)
    text(s, 2.42, 1.02, 7.0, 0.62, "Francanglais Studio", size=34, color=WHITE, bold=True)
    text(s, 2.42, 1.72, 6.6, 0.46,
         "A lexical and syntactic analyzer for everyday speech in Yaoundé",
         size=13.5, color=RGBColor(0xC7, 0xDE, 0xD1))

    box(s, 0.62, 2.62, 3.05, 0.62, fill=None, line=GOLD, line_w=1.2)
    text(s, 0.62, 2.62, 3.05, 0.62, "CS4110 · Compiler Construction", size=12,
         color=GOLD, bold=True, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)

    names = [
        ("Kamdeu Yamdjeuson Neil Marshall", "ICTU20241386"),
        ("Eyong Seanna Tabe", "ICTU20241297"),
        ("Tuheu Tchoubi Pempeme Moussa Fahdil", "ICTU20241393"),
    ]
    text(s, 0.62, 4.05, 4.0, 0.22, "PRESENTED BY", size=10, color=ACCENT, bold=True)
    for i, (n, m) in enumerate(names):
        y = 4.35 + i * 0.30
        text(s, 0.62, y, 4.3, 0.26, n, size=11.5, color=NAVY, bold=True)
        text(s, 5.0, y, 1.6, 0.26, m, size=11, color=GREY, font="Consolas")

    text(s, 6.9, 4.35, 2.5, 0.9,
         [("Instructor", {"size": 10, "color": ACCENT, "bold": True}),
          ("Engr. Tanwi Nkiamboh", {"size": 11.5, "color": NAVY, "bold": True}),
          ("29 September 2026", {"size": 10.5, "color": GREY})],
         align=PP_ALIGN.RIGHT)
    return s


def slide_problem(prs):
    s = add_slide(prs)
    header(s, "One sentence, four languages", 2, kicker="THE PROBLEM")

    text(s, 0.55, 1.22, 9.0, 0.3,
         "This is ordinary speech in a Yaoundé taxi:", size=13, color=GREY)

    sentence = [("Le taximan ", ACCENT), ("go ", INFO), ("bring ", INFO),
                ("me ", ACCENT), ("for ", DANGER), ("kwatt", NAVY)]
    box(s, 0.55, 1.62, 8.9, 0.78, fill=WHITE, line=RULE)
    x = 0.95
    for word, col in sentence:
        tb = text(s, x, 1.78, 1.9, 0.46, word, size=19, color=col, bold=True)
        x += 0.16 + len(word) * 0.148

    legend = [
        ("French grammar", "le, taximan, me", ACCENT),
        ("English verbs", "go, bring, send", INFO),
        ("Pidgin particles", "for, ashia, waka", DANGER),
        ("Duala / Ewondo", "kwatt, mbom, ngola", GOLD),
    ]
    for i, (title, ex, col) in enumerate(legend):
        x = 0.55 + i * 2.28
        box(s, x, 2.68, 2.08, 1.0, fill=WHITE, line=RULE)
        box(s, x, 2.68, 2.08, 0.075, fill=col, line=None, shape=MSO_SHAPE.RECTANGLE)
        text(s, x + 0.16, 2.9, 1.8, 0.24, title, size=11, color=NAVY, bold=True)
        text(s, x + 0.16, 3.18, 1.8, 0.4, ex, size=10, color=GREY, font="Consolas")

    note(s, 0.55, 3.92, 8.9, 1.05, "Why a compiler cannot just be pointed at it",
         "A normal compiler assumes one language with one keyword table. Here there are 15 donor "
         "languages, no dictionary, no standard spelling — and speakers switch mid-sentence, so "
         "you cannot detect the language first and analyse afterwards.")
    return s


def slide_pipeline(prs):
    s = add_slide(prs)
    header(s, "How the analyzer works, end to end", 3, kicker="OVERVIEW")
    text(s, 0.55, 1.18, 9.0, 0.3,
         "Text enters on the left and leaves as one of two answers. Each stage is covered "
         "in turn.", size=12.5, color=GREY)

    y = 2.45
    d = 0.92
    xs = [1.15, 3.05, 4.95, 6.85]
    labels = [("input", "raw text"), ("scan", "character runs"), ("lex", "tokens"),
              ("parse", "verdict")]
    for (cx, (lab, sub)) in zip(xs, labels):
        state(s, cx, y, d, lab, sub, label_size=11)

    # Entry arrow.
    arrow(s, 0.35, y, 0.32)

    transitions = [
        (2.10, "raw text"),
        (4.00, "character runs"),
        (5.90, "tokens"),
    ]
    for cx, lab in transitions:
        arrow(s, cx - 0.42, y, 0.84)
        edge_label(s, cx, y - 0.42, 1.7, lab)

    # Branch to the two terminating states.
    state(s, 8.62, 1.62, d, "accept", None, line=ACCENT, fill=PANEL, accepting=True,
          label_size=10)
    state(s, 8.62, 3.35, d, "reject", None, line=DANGER,
          fill=RGBColor(0xFB, 0xEC, 0xEF), accepting=True, label_color=DANGER,
          label_size=10)

    arrow(s, 7.34, y - 0.22, 0.80, h=-0.52)
    edge_label(s, 7.22, 1.52, 2.3, "nothing left to read", color=ACCENT, bold=True)
    arrow(s, 7.34, y + 0.22, 0.80, h=0.48, color=DANGER)
    edge_label(s, 7.22, 3.42, 2.3, "no table entry", color=DANGER, bold=True)

    cards = [
        ("Stage 1 · Scanning", "Cut the text into runs: words, numbers, punctuation, spaces."),
        ("Stage 2 · Lexing", "Look each word up. Give it a class: NOUN, VERB, DET…"),
        ("Stage 3 · Parsing", "Check the classes form a legal sentence shape."),
    ]
    for i, (t, b) in enumerate(cards):
        x = 0.55 + i * 3.02
        box(s, x, 4.18, 2.82, 0.92, fill=WHITE, line=RULE)
        text(s, x + 0.16, 4.3, 2.55, 0.24, t, size=10.5, color=DEEP, bold=True)
        text(s, x + 0.16, 4.56, 2.55, 0.5, b, size=9.5, color=GREY, spacing=1.12)
    return s


def slide_scanning(prs):
    s = add_slide(prs)
    header(s, "Step 1 — Scanning: cut the text up", 4, kicker="LEXICAL ANALYSIS")
    text(s, 0.55, 1.18, 9.0, 0.3,
         "Five regular expressions decide where one piece of text ends and the next begins.",
         size=12.5, color=GREY)

    rows = [
        ("WORD", "letters, accents, apostrophes", "taximan, ça, j'ai", ACCENT),
        ("NUMBER", "a run of digits", "500, 2026", INFO),
        ("SEPARATOR", "comma, semicolon, colon", ", ; :", GOLD),
        ("PUNCTUATION", "sentence marks", ". ! ?", GREY),
        ("SPACE", "gaps and line breaks", "\u2423", FAINT),
    ]
    for i, (name, desc, ex, col) in enumerate(rows):
        y = 1.62 + i * 0.58
        box(s, 0.55, y, 4.55, 0.48, fill=WHITE, line=RULE)
        box(s, 0.55, y, 0.07, 0.48, fill=col, line=None, shape=MSO_SHAPE.RECTANGLE)
        text(s, 0.76, y + 0.06, 1.35, 0.24, name, size=10.5, color=NAVY, bold=True,
             font="Consolas")
        text(s, 2.15, y + 0.08, 1.7, 0.24, desc, size=9.5, color=GREY)
        text(s, 3.95, y + 0.06, 1.1, 0.26, ex, size=10, color=DEEP, font="Consolas")

    box(s, 5.45, 1.62, 4.0, 2.28, fill=NAVY, line=None)
    text(s, 5.68, 1.78, 3.6, 0.22, "ONE SENTENCE, SCANNED", size=9.5, color=GOLD, bold=True)
    text(s, 5.68, 2.10, 3.6, 0.3, "Combi, va au kwatt.", size=14, color=WHITE,
         font="Consolas")
    pieces = [("Combi", "WORD"), (",", "SEP"), ("va", "WORD"),
              ("au", "WORD"), ("kwatt", "WORD"), (".", "PUNCT")]
    x, y = 5.68, 2.62
    for word, kind in pieces:
        w = max(0.52, 0.17 * len(word) + 0.26)
        if x + w > 9.25:
            x, y = 5.68, y + 0.62
        box(s, x, y, w, 0.5, fill=RGBColor(0x1F, 0x2C, 0x38), line=RGBColor(0x2E, 0x40, 0x50))
        text(s, x, y + 0.04, w, 0.22, word, size=10, color=WHITE, align=PP_ALIGN.CENTER,
             font="Consolas")
        text(s, x, y + 0.26, w, 0.2, kind, size=7.5, color=GOLD, align=PP_ALIGN.CENTER)
        x += w + 0.1

    note(s, 0.55, 4.6, 8.9, 0.72, "Punctuation is not thrown away",
         "Commas become SEP tokens, because in speech a comma is a real clause boundary that the "
         "grammar needs to see. Full stops stay invisible.")
    return s


def selfloop(slide, cx, top, color=ACCENT, width=0.30, height=0.52):
    """A squared self-loop above a state, drawn as a freeform so it can carry an arrowhead."""
    b = slide.shapes.build_freeform(Inches(cx - width), Inches(top))
    b.add_line_segments([
        (Inches(cx - width), Inches(top - height)),
        (Inches(cx + width), Inches(top - height)),
        (Inches(cx + width), Inches(top)),
    ], close=False)
    sh = b.convert_to_shape()
    sh.fill.background()
    sh.line.color.rgb = color
    sh.line.width = Pt(2)
    sh.shadow.inherit = False
    tip(sh)
    return sh


def selfloop_side(slide, right, cy, color=ACCENT, depth=0.30, height=0.20):
    """A compact self-loop hanging off the right edge of a state."""
    b = slide.shapes.build_freeform(Inches(right), Inches(cy - height))
    b.add_line_segments([
        (Inches(right + depth), Inches(cy - height)),
        (Inches(right + depth), Inches(cy + height)),
        (Inches(right), Inches(cy + height)),
    ], close=False)
    sh = b.convert_to_shape()
    sh.fill.background()
    sh.line.color.rgb = color
    sh.line.width = Pt(1.75)
    sh.shadow.inherit = False
    tip(sh)
    return sh


def tuple_panel(slide, x, y, w, lines, title="FORMAL DEFINITION"):
    """The machine's defining 5-tuple, so states and inputs are unambiguous."""
    h = 0.34 + 0.27 * len(lines)
    box(slide, x, y, w, h, fill=NAVY, line=None)
    text(slide, x + 0.2, y + 0.11, w - 0.4, 0.22, title, size=9, color=GOLD, bold=True)
    for i, (sym, body) in enumerate(lines):
        yy = y + 0.36 + i * 0.27
        text(slide, x + 0.2, yy, 0.5, 0.24, sym, size=10.5, color=GOLD, bold=True,
             font="Consolas")
        text(slide, x + 0.72, yy + 0.015, w - 0.92, 0.24, body, size=9.5, color=WHITE)
    return h


def delta_table(slide, x, y, symbols, rows, col_w=0.86, row_h=0.32, head="δ"):
    """Transition function as a total table: every state × every input symbol."""
    name_w = 1.05
    box(slide, x, y, name_w, row_h, fill=DEEP, line=None, shape=MSO_SHAPE.RECTANGLE)
    text(slide, x, y + 0.055, name_w, 0.24, head, size=11, color=GOLD, bold=True,
         align=PP_ALIGN.CENTER)
    for j, sym in enumerate(symbols):
        box(slide, x + name_w + j * col_w, y, col_w, row_h, fill=DEEP, line=None,
            shape=MSO_SHAPE.RECTANGLE)
        text(slide, x + name_w + j * col_w, y + 0.055, col_w, 0.24, sym, size=10,
             color=WHITE, bold=True, align=PP_ALIGN.CENTER, font="Consolas")
    for i, (name, accepting, cells) in enumerate(rows):
        yy = y + row_h + i * row_h
        box(slide, x, yy, name_w, row_h, fill=PANEL if accepting else RGBColor(0xF1, 0xF4, 0xF2),
            line=None, shape=MSO_SHAPE.RECTANGLE)
        text(slide, x, yy + 0.055, name_w, 0.24, name, size=9.5,
             color=DEEP if accepting else NAVY, bold=accepting, align=PP_ALIGN.CENTER,
             font="Consolas")
        for j, cell in enumerate(cells):
            dead = cell in ("X", "\u2717")
            box(slide, x + name_w + j * col_w, yy, col_w, row_h,
                fill=RGBColor(0xFB, 0xEC, 0xEF) if dead else WHITE, line=RULE, line_w=0.75,
                shape=MSO_SHAPE.RECTANGLE)
            text(slide, x + name_w + j * col_w, yy + 0.055, col_w, 0.24, cell, size=9.5,
                 color=DANGER if dead else ACCENT, align=PP_ALIGN.CENTER, font="Consolas")
    return row_h * (len(rows) + 1)


def slide_dfa_scanner(prs):
    """DFA 1: classify one maximal run of characters. Genuinely finite-state."""
    s = add_slide(prs)
    header(s, "DFA 1 — deciding what a run of characters is", 5,
           kicker="LEXICAL ANALYSIS")

    text(s, 0.55, 1.18, 4.35, 0.34,
         "Each accepting state loops on its own symbol only, so a run ends the moment the "
         "character class changes.", size=9.5, color=GREY, spacing=1.1)

    # --- state diagram -------------------------------------------------------
    q0y = 3.16
    state(s, 1.15, q0y, 0.66, "q0", fill=WHITE, line=NAVY, label_size=11)
    arrow(s, 0.42, q0y, 0.36)
    text(s, 0.2, q0y - 0.44, 0.9, 0.22, "start", size=9, color=GREY, align=PP_ALIGN.CENTER)

    finals = [("qW", "word", 1.92, "\u2113"), ("qN", "number", 2.54, "d"),
              ("qS", "space", 3.16, "\u2423"), ("qL", "newline", 3.78, "\u23ce"),
              ("qP", "punct", 4.40, "\u25aa")]
    for name, sub, cy, sym in finals:
        state(s, 3.10, cy, 0.56, name, fill=PANEL, line=ACCENT, accepting=True,
              label_size=9.5)
        text(s, 3.76, cy - 0.10, 1.0, 0.22, sub, size=9, color=GREY)
        arrow(s, 1.52, q0y, 1.26, h=cy - q0y)
        selfloop_side(s, 3.38, cy, depth=0.26, height=0.17)
        mid = (q0y + cy) / 2
        text(s, 1.90, mid - 0.26 if cy <= q0y else mid + 0.03, 0.55, 0.22, sym, size=11,
             color=DEEP, bold=True, font="Consolas", align=PP_ALIGN.CENTER)

    state(s, 1.15, 4.58, 0.58, "X", "dead", fill=RGBColor(0xFB, 0xEC, 0xEF), line=DANGER,
          label_size=10.5, label_color=DANGER)
    selfloop_side(s, 1.44, 4.58, color=DANGER, depth=0.26, height=0.17)
    text(s, 0.4, 4.94, 1.9, 0.22, "any other symbol", size=8.5, color=DANGER,
         align=PP_ALIGN.CENTER)

    # --- transition function -------------------------------------------------
    syms = ["\u2113", "d", "\u2423", "\u23ce", "\u25aa"]
    rows = [
        ("q0", False, ["qW", "qN", "qS", "qL", "qP"]),
        ("qW", True, ["qW", "X", "X", "X", "X"]),
        ("qN", True, ["X", "qN", "X", "X", "X"]),
        ("qS", True, ["X", "X", "qS", "X", "X"]),
        ("qL", True, ["X", "X", "X", "qL", "X"]),
        ("qP", True, ["X", "X", "X", "X", "qP"]),
        ("X", False, ["X", "X", "X", "X", "X"]),
    ]
    text(s, 5.05, 1.22, 4.4, 0.24, "TRANSITION FUNCTION \u03b4  (total)", size=9,
         color=ACCENT, bold=True)
    delta_table(s, 5.05, 1.5, syms, rows, col_w=0.67)

    tuple_panel(s, 5.05, 4.28, 4.4, [
        ("\u03a3", "\u2113 letter/accent   d digit   \u2423 space   \u23ce newline   \u25aa punctuation"),
        ("Q", "q0, qW, qN, qS, qL, qP, X"),
        ("F", "qW, qN, qS, qL, qP   \u2014  X is the dead state"),
    ])
    return s


def slide_dfa_word(prs):
    """DFA 2: the inside of a word run -- letters joined by apostrophes or hyphens."""
    s = add_slide(prs)
    header(s, "DFA 2 — what counts as one word", 6, kicker="LEXICAL ANALYSIS")
    text(s, 0.55, 1.2, 9.0, 0.28,
         "State qW above expands into this machine. Double circle = a complete, valid word.",
         size=11, color=GREY)

    y = 2.42
    d = 0.78
    arrow(s, 0.42, y, 0.34)
    text(s, 0.2, y - 0.44, 0.9, 0.22, "start", size=9, color=GREY, align=PP_ALIGN.CENTER)

    state(s, 1.22, y, d, "A", "no letter yet", fill=WHITE, line=NAVY, label_size=12)
    state(s, 3.30, y, d, "B", "valid word", fill=PANEL, line=ACCENT, accepting=True,
          label_size=12)
    state(s, 5.55, y, d, "C", "after ' or -", fill=WHITE, line=GOLD, label_size=12)

    arrow(s, 1.65, y, 1.22)
    edge_label(s, 2.26, y - 0.38, 1.2, "\u2113", size=12, bold=True, color=DEEP)

    arrow(s, 3.73, y, 1.40)
    edge_label(s, 4.43, y - 0.38, 1.2, "m", size=12, bold=True, color=DEEP)

    c = s.shapes.add_connector(MSO_CONNECTOR.ELBOW, Inches(5.55), Inches(y + 0.42),
                               Inches(3.30), Inches(y + 0.42))
    c.line.color.rgb = ACCENT
    c.line.width = Pt(2)
    tip(c)
    edge_label(s, 4.43, y + 0.48, 1.2, "\u2113", size=12, bold=True, color=DEEP)

    selfloop(s, 3.30, y - d / 2, height=0.44)
    edge_label(s, 3.30, y - d / 2 - 0.68, 1.2, "\u2113", size=12, bold=True, color=DEEP)

    state(s, 7.85, y, d, "X", "dead", fill=RGBColor(0xFB, 0xEC, 0xEF), line=DANGER,
          label_size=12, label_color=DANGER)
    arrow(s, 5.98, y, 1.45, color=DANGER)
    edge_label(s, 6.70, y - 0.38, 1.4, "m", size=12, bold=True, color=DANGER)
    selfloop_side(s, 8.26, y, color=DANGER)
    text(s, 8.55, y + 0.30, 1.1, 0.22, "\u2113, m", size=9.5, color=DANGER,
         font="Consolas")

    syms = ["\u2113", "m"]
    rows = [
        ("A", False, ["B", "X"]),
        ("B", True, ["B", "C"]),
        ("C", False, ["B", "X"]),
        ("X", False, ["X", "X"]),
    ]
    text(s, 0.55, 3.42, 3.0, 0.24, "TRANSITION FUNCTION \u03b4  (total)", size=9,
         color=ACCENT, bold=True)
    delta_table(s, 0.55, 3.70, syms, rows, col_w=0.8)

    tuple_panel(s, 3.30, 3.70, 3.1, [
        ("\u03a3", "\u2113 = any letter or accent"),
        ("", "m = apostrophe ' \u2019 or hyphen -"),
        ("Q", "A, B, C, X      q\u2080 = A"),
        ("F", "{ B }"),
    ])

    examples = [("taximan", "\u2113\u2113\u2113\u2113\u2113\u2113\u2113", "A B B B B B B B", True),
                ("j'ai", "\u2113 m \u2113 \u2113", "A B C B B", True),
                ("est-ce", "\u2113\u2113\u2113 m \u2113\u2113", "A B B B C B B", True),
                ("'x", "m \u2113", "A X X", False)]
    text(s, 6.65, 3.42, 2.8, 0.24, "TRACES", size=9, color=ACCENT, bold=True)
    for i, (word, ins, path, ok) in enumerate(examples):
        yy = 3.70 + i * 0.42
        col = ACCENT if ok else DANGER
        box(s, 6.65, yy, 2.8, 0.36, fill=WHITE if ok else RGBColor(0xFB, 0xEC, 0xEF),
            line=RULE, line_w=0.75)
        text(s, 6.78, yy + 0.06, 1.0, 0.24, word, size=9.5, color=col, bold=True,
             font="Consolas")
        text(s, 7.78, yy + 0.06, 1.55, 0.24, path, size=8.5, color=GREY, font="Consolas")
    return s


def slide_lexing(prs):
    s = add_slide(prs)
    header(s, "Step 2 — Lexing: give every word a job", 7, kicker="LEXICAL ANALYSIS")
    text(s, 0.55, 1.18, 9.0, 0.3,
         "Each word is looked up in a 688-word lexicon built from the speech we collected.",
         size=12.5, color=GREY)

    box(s, 0.55, 1.62, 4.3, 2.55, fill=WHITE, line=RULE)
    text(s, 0.78, 1.8, 3.9, 0.24, "ONE WORD, RESOLVED", size=9.5, color=ACCENT, bold=True)
    text(s, 0.78, 2.1, 3.9, 0.4, "kwatt", size=24, color=NAVY, bold=True, font="Consolas")
    facts = [("Class", "NOUN"), ("Meaning", "neighbourhood / quartier"),
             ("From", "Duala"), ("Slang?", "yes")]
    for i, (k, v) in enumerate(facts):
        y = 2.62 + i * 0.36
        text(s, 0.78, y, 1.0, 0.24, k, size=10, color=GREY)
        text(s, 1.85, y, 2.8, 0.24, v, size=10.5, color=NAVY, bold=True)

    classes = [
        ("NOUN", "290"), ("VERB", "210"), ("ADV", "35"), ("ADJ", "33"),
        ("DET", "30"), ("PRON", "23"), ("PREP", "22"), ("INTJ", "19"),
        ("CONJ", "14"), ("FORMULA", "7"), ("NEG", "5"), ("SEP", "—"),
    ]
    text(s, 5.15, 1.62, 4.3, 0.26, "12 WORD CLASSES THE GRAMMAR USES", size=9.5,
         color=ACCENT, bold=True)
    for i, (name, count) in enumerate(classes):
        col, row = i % 3, i // 3
        x = 5.15 + col * 1.45
        y = 1.96 + row * 0.55
        box(s, x, y, 1.33, 0.45, fill=PANEL, line=None)
        text(s, x + 0.1, y + 0.04, 1.15, 0.22, name, size=9.5, color=DEEP, bold=True,
             font="Consolas")
        text(s, x + 0.1, y + 0.24, 1.15, 0.2, count + " words", size=8, color=GREY)

    note(s, 0.55, 4.38, 8.9, 0.92, "An unknown word is never dropped",
         "It becomes an UNKNOWN token that still remembers where it came from — so the parser can "
         "point at the exact character, and we can suggest the closest real word.")
    return s


def slide_grammar(prs):
    s = add_slide(prs)
    header(s, "Step 3 — Writing the grammar, then fixing it", 8, kicker="SYNTACTIC ANALYSIS")
    text(s, 0.55, 1.18, 9.0, 0.3,
         "We wrote the rules the natural way first. That version cannot be parsed — so the tool "
         "rewrites it.", size=12.5, color=GREY)

    box(s, 0.55, 1.62, 4.25, 1.72, fill=RGBColor(0xFB, 0xEC, 0xEF), line=None)
    text(s, 0.78, 1.78, 3.8, 0.24, "PROBLEM · left recursion", size=9.5, color=DANGER,
         bold=True)
    text(s, 0.78, 2.12, 3.8, 0.9,
         [("Seq → Seq CONJ Unit", {"size": 13, "font": "Consolas", "color": NAVY,
                                   "bold": True}),
          ("      | Unit", {"size": 13, "font": "Consolas", "color": NAVY})])
    text(s, 0.78, 2.86, 3.8, 0.38,
         "Seq starts by asking for Seq. The parser would loop forever.",
         size=9.5, color=DANGER, spacing=1.1)

    arrow(s, 4.95, 2.48, 0.5)
    text(s, 4.72, 2.62, 0.95, 0.22, "rewrite", size=9, color=GREY, align=PP_ALIGN.CENTER)

    box(s, 5.62, 1.62, 3.83, 1.72, fill=PANEL, line=None)
    text(s, 5.85, 1.78, 3.4, 0.24, "FIXED · no left recursion", size=9.5, color=ACCENT,
         bold=True)
    text(s, 5.85, 2.12, 3.4, 0.9,
         [("Seq  → Unit Seq′", {"size": 13, "font": "Consolas", "color": NAVY,
                                "bold": True}),
          ("Seq′ → CONJ Unit Seq′ | ε", {"size": 12, "font": "Consolas", "color": NAVY})])
    text(s, 5.85, 2.86, 3.4, 0.38,
         "Now it reads left to right and always makes progress.",
         size=9.5, color=ACCENT, spacing=1.1)

    steps = [
        ("1", "Remove left recursion", "Seq", ACCENT),
        ("2", "Factor SEP", "Seq′", GOLD),
        ("3", "Factor INTJ", "Unit", GOLD),
        ("4", "Factor DET", "NP", GOLD),
    ]
    text(s, 0.55, 3.55, 5.0, 0.24, "4 RECORDED STEPS  ·  37 → 41 RULES", size=9.5,
         color=ACCENT, bold=True)
    for i, (n, what, where, col) in enumerate(steps):
        x = 0.55 + i * 2.28
        box(s, x, 3.88, 2.08, 0.72, fill=WHITE, line=RULE)
        box(s, x + 0.14, 4.02, 0.32, 0.32, fill=col, line=None, shape=MSO_SHAPE.OVAL)
        text(s, x + 0.14, 4.07, 0.32, 0.22, n, size=10, color=WHITE, bold=True,
             align=PP_ALIGN.CENTER)
        text(s, x + 0.56, 4.02, 1.45, 0.22, what, size=9.5, color=NAVY, bold=True)
        text(s, x + 0.56, 4.24, 1.45, 0.22, "on " + where, size=9, color=GREY,
             font="Consolas")

    note(s, 0.55, 4.76, 8.9, 0.6, "Order matters",
         "Removing left recursion CREATES a new clash on SEP. Factoring must come second, or the "
         "grammar still isn't LL(1).", tint=RGBColor(0xFF, 0xF3, 0xD6), bar=GOLD)
    return s


def slide_table(prs):
    s = add_slide(prs)
    header(s, "Step 4 — The parsing table: a lookup grid", 9, kicker="SYNTACTIC ANALYSIS")
    text(s, 0.55, 1.18, 9.0, 0.3,
         "Row = what we're expecting. Column = the next word's class. The cell says which rule "
         "to use.", size=12.5, color=GREY)

    cols = ["DET", "NOUN", "VERB", "INTJ", "$"]
    rows = [
        ("S",   ["s1", "s1", "s1", "s1", ""]),
        ("NP",  ["np1", "np4", "", "", ""]),
        ("NP′", ["", "np1a", "", "", ""]),
        ("Unit", ["u4", "u4", "u4", "u1", ""]),
    ]
    x0, y0, cw, ch = 0.85, 1.72, 1.32, 0.42
    text(s, x0 - 0.3, y0 + 0.1, 1.05, 0.24, "", size=9)
    for j, c in enumerate(cols):
        box(s, x0 + 1.05 + j * cw, y0, cw, ch, fill=DEEP, line=None)
        text(s, x0 + 1.05 + j * cw, y0 + 0.1, cw, 0.24, c, size=10, color=WHITE,
             bold=True, align=PP_ALIGN.CENTER, font="Consolas")
    for i, (name, cells) in enumerate(rows):
        y = y0 + ch + i * ch
        box(s, x0, y, 1.05, ch, fill=PANEL, line=None)
        text(s, x0, y + 0.1, 1.05, 0.24, name, size=10, color=DEEP, bold=True,
             align=PP_ALIGN.CENTER, font="Consolas")
        for j, cell in enumerate(cells):
            fill = WHITE if cell else RGBColor(0xF1, 0xF4, 0xF2)
            box(s, x0 + 1.05 + j * cw, y, cw, ch, fill=fill, line=RULE, line_w=0.75,
                shape=MSO_SHAPE.RECTANGLE)
            if cell:
                text(s, x0 + 1.05 + j * cw, y + 0.11, cw, 0.22, cell, size=9.5,
                     color=ACCENT, align=PP_ALIGN.CENTER, font="Consolas")

    text(s, 0.85, 3.90, 4.5, 0.26, "Grey = illegal here. That is how errors are caught.",
         size=10, color=GREY)

    box(s, 6.6, 4.02, 2.85, 1.0, fill=PANEL, line=None)
    box(s, 6.78, 4.20, 0.46, 0.46, fill=ACCENT, line=None, shape=MSO_SHAPE.OVAL)
    text(s, 6.78, 4.28, 0.46, 0.26, "✓", size=14, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
    text(s, 7.38, 4.21, 1.9, 0.24, "Conflict-free", size=11.5, color=DEEP, bold=True)
    text(s, 7.38, 4.47, 1.95, 0.46, "No cell holds two rules. One word of lookahead is always "
         "enough.", size=9, color=GREY, spacing=1.1)

    note(s, 0.55, 4.28, 5.85, 0.78, "Built by one rule",
         "Put rule A → α in cell [A, t] for every word class t that α can start with. If α can "
         "vanish, also for everything that can follow A.")
    return s


def biarrow(slide, x1, y1, x2, y2, color=ACCENT):
    """A two-way connector: go do the move, then come back to the decision point."""
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                   Inches(x2), Inches(y2))
    c.line.color.rgb = color
    c.line.width = Pt(2)
    ln = c.line._get_or_add_ln()
    ln.append(ln.makeelement(qn("a:headEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    ln.append(ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"}))
    return c


def slide_pda_parser(prs):
    """The parser is a pushdown automaton -- a DFA provably cannot do this job."""
    s = add_slide(prs)
    header(s, "The parser — a pushdown automaton", 10, kicker="SYNTACTIC ANALYSIS")
    text(s, 0.55, 1.18, 9.0, 0.28,
         "Same idea as the DFAs, plus one thing a finite automaton does not have: a stack.",
         size=11, color=GREY)

    cx, cy = 2.70, 3.05
    state(s, cx, cy, 1.25, "q", None, fill=DEEP, line=DEEP, label_size=15,
          label_color=WHITE)
    text(s, cx - 0.85, cy + 0.16, 1.7, 0.36, "read top of stack\nand next class",
         size=8, color=RGBColor(0xA8, 0xC8, 0xB6), align=PP_ALIGN.CENTER, spacing=1.0)

    arrow(s, 0.52, cy, 0.38)
    text(s, 0.12, cy - 0.62, 1.4, 0.22, "push  S $", size=9.5, color=GREY,
         align=PP_ALIGN.CENTER, font="Consolas")
    state(s, 1.34, cy, 0.72, "q\u2080", fill=WHITE, line=ACCENT, label_size=11)
    arrow(s, 1.72, cy, 0.34)

    state(s, cx, 1.92, 0.76, "match", fill=WHITE, line=ACCENT, label_size=9)
    biarrow(s, cx, cy - 0.65, cx, 2.32)
    text(s, cx + 0.56, 1.80, 3.2, 0.48,
         [("\u03b4(q, a, a) = (q, \u03b5)", {"size": 10, "font": "Consolas", "color": DEEP,
                                    "bold": True}),
          ("pop the class, consume the word", {"size": 9, "color": GREY})])

    state(s, cx, 4.22, 0.76, "predict", fill=WHITE, line=ACCENT, label_size=8.5)
    biarrow(s, cx, cy + 0.65, cx, 3.82)
    text(s, cx + 0.56, 4.08, 3.2, 0.48,
         [("\u03b4(q, a, A) = (q, \u03b1\u1d3f)", {"size": 10, "font": "Consolas", "color": DEEP,
                                    "bold": True}),
          ("pop A, push table[A,a] reversed", {"size": 9, "color": GREY})])

    state(s, 8.45, 2.22, 0.86, "acc", fill=PANEL, line=ACCENT, accepting=True,
          label_size=10)
    arrow(s, 3.38, cy - 0.26, 4.62, h=-0.52)
    edge_label(s, 6.10, 2.02, 2.9, "\u03b4(q, $, $) = (acc, \u03b5)", color=ACCENT, bold=True,
               size=9.5)

    state(s, 8.45, 3.98, 0.86, "rej", fill=RGBColor(0xFB, 0xEC, 0xEF), line=DANGER,
          accepting=True, label_size=10, label_color=DANGER)
    arrow(s, 3.38, cy + 0.26, 4.62, h=0.52, color=DANGER)
    edge_label(s, 6.10, 3.92, 2.9, "\u03b4 undefined \u2192 error", color=DANGER, bold=True,
               size=9.5)

    tuple_panel(s, 0.55, 4.62, 4.15, [
        ("\u03a3", "the 12 word classes, plus $"),
        ("\u0393", "word classes + rule names + $"),
    ], title="PUSHDOWN AUTOMATON")

    box(s, 4.95, 4.62, 4.5, 0.88, fill=RGBColor(0xFF, 0xF3, 0xD6), line=None)
    box(s, 4.95, 4.62, 0.055, 0.88, fill=GOLD, line=None, shape=MSO_SHAPE.RECTANGLE)
    text(s, 5.16, 4.72, 4.15, 0.22, "Why not a DFA?", size=10, color=DEEP, bold=True)
    text(s, 5.16, 4.96, 4.18, 0.46,
         "A DFA has finitely many states, so it cannot count nesting. The stack can grow "
         "without limit — that is the whole difference.", size=8.5, color=GREY, spacing=1.05)
    return s


def slide_trace(prs):
    s = add_slide(prs)
    header(s, "Watch it run", 11, kicker="THE PARSER")
    text(s, 0.55, 1.18, 9.0, 0.3,
         "“le taximan a une voiture”  →  DET NOUN VERB DET NOUN", size=13,
         color=NAVY, bold=True)

    heads = ["Stack (top first)", "Next word", "Move"]
    widths = [3.9, 1.5, 3.5]
    x = 0.55
    for h_, w_ in zip(heads, widths):
        box(s, x, 1.62, w_, 0.4, fill=DEEP, line=None)
        text(s, x + 0.12, 1.71, w_ - 0.2, 0.24, h_, size=10, color=WHITE, bold=True)
        x += w_ + 0.05

    steps = [
        ("S $", "DET", "expand S → Seq", ACCENT),
        ("NP ClauseTail …", "DET", "expand NP → DET NP′", ACCENT),
        ("DET NP′ …", "DET", "match “le” ✓", INFO),
        ("NP′ …", "NOUN", "expand NP′ → NOUN", ACCENT),
        ("NOUN …", "NOUN", "match “taximan” ✓", INFO),
        ("Predicate …", "VERB", "expand, then match “a” ✓", INFO),
        ("Comps Seq′ $", "$", "both vanish (ε)", GREY),
        ("$", "$", "ACCEPT", ACCENT),
    ]
    for i, (stack, look, move, col) in enumerate(steps):
        y = 2.06 + i * 0.33
        fill = WHITE if i % 2 == 0 else RGBColor(0xF1, 0xF4, 0xF2)
        last = i == len(steps) - 1
        x = 0.55
        for j, w_ in enumerate(widths):
            f = PANEL if last else fill
            box(s, x, y, w_, 0.31, fill=f, line=None, shape=MSO_SHAPE.RECTANGLE)
            x += w_ + 0.05
        text(s, 0.67, y + 0.04, 3.7, 0.24, stack, size=9.5,
             color=NAVY if not last else DEEP, font="Consolas", bold=last)
        text(s, 4.62, y + 0.04, 1.3, 0.24, look, size=9.5, color=GREY, font="Consolas")
        text(s, 6.22, y + 0.04, 3.3, 0.24, move, size=9.5,
             color=col, bold=last or "match" in move or "ACCEPT" in move)

    note(s, 0.55, 4.82, 8.9, 0.72, "The ε steps are the clever part",
         "“Comps” and “Seq′” are allowed to match nothing — which is exactly what FOLLOW sets tell "
         "the parser.")
    return s


def slide_results(prs):
    s = add_slide(prs)
    header(s, "Results: 20 of our 22 sentences parse", 12, kicker="EVALUATION")

    # Simple proportional bar instead of a chart object.
    text(s, 0.55, 1.3, 4.6, 0.24, "OUR COLLECTED SENTENCES", size=9.5, color=ACCENT,
         bold=True)
    box(s, 0.55, 1.62, 4.6, 0.62, fill=RGBColor(0xF1, 0xF4, 0xF2), line=None)
    box(s, 0.55, 1.62, 4.6 * 20 / 22, 0.62, fill=ACCENT, line=None)
    text(s, 0.75, 1.78, 3.0, 0.3, "20 accepted", size=13, color=WHITE, bold=True)
    text(s, 4.28, 1.78, 0.8, 0.3, "2", size=13, color=DANGER, bold=True,
         align=PP_ALIGN.CENTER)

    text(s, 0.55, 2.44, 2.2, 0.62, "91%", size=34, color=DEEP, bold=True)
    text(s, 1.85, 2.58, 3.3, 0.6,
         "acceptance — every one with a full derivation showing why", size=10.5,
         color=GREY, spacing=1.15)

    text(s, 5.6, 1.3, 3.9, 0.24, "THE TWO WE REJECT — ON PURPOSE", size=9.5,
         color=DANGER, bold=True)
    rejects = [
        ("Adverb after the object", "“…tchop le poisson ici” — our rules only allow "
         "adverbs before the verb."),
        ("Pronoun stuck after the verb", "“va me bring” — fixing it would create a "
         "conflict in the table."),
    ]
    for i, (t, b) in enumerate(rejects):
        y = 1.62 + i * 1.02
        box(s, 5.6, y, 3.85, 0.9, fill=WHITE, line=RULE)
        box(s, 5.6, y, 0.055, 0.9, fill=DANGER, line=None, shape=MSO_SHAPE.RECTANGLE)
        text(s, 5.8, y + 0.12, 3.5, 0.24, t, size=10.5, color=NAVY, bold=True)
        text(s, 5.8, y + 0.38, 3.5, 0.46, b, size=9.5, color=GREY, spacing=1.1)

    note(s, 0.55, 3.9, 8.9, 0.82, "We left them failing on purpose",
         "We could widen the grammar until everything passed. But a grammar that accepts every "
         "sentence proves nothing — so we report the limit instead of hiding it.",
         tint=RGBColor(0xFF, 0xF3, 0xD6), bar=GOLD)

    stats = [("22", "sentences"), ("688", "lexicon words"), ("15", "donor languages"),
             ("158", "tests passing")]
    for i, (n, lab) in enumerate(stats):
        x = 0.55 + i * 2.28
        box(s, x, 4.86, 2.08, 0.54, fill=PANEL, line=None)
        text(s, x + 0.14, 4.93, 0.9, 0.3, n, size=15, color=DEEP, bold=True)
        text(s, x + 1.02, 5.0, 1.0, 0.26, lab, size=9, color=GREY)
    return s


def slide_why_hard(prs):
    s = add_slide(prs)
    header(s, "Why this language is hard to analyse", 13, kicker="DISCUSSION")

    items = [
        ("15", "languages in one lexicon",
         "No single dictionary would recognise even half of a normal sentence."),
        ("mid-\nword", "switching happens inside a clause",
         "So the language label belongs to each word, not to the sentence."),
        ("é = e", "spelling is unstable",
         "Typed on phones: accents come and go. We match without them — as a fallback only."),
        ("à ≠ a", "but accents carry meaning",
         "“a” is a verb, “à” is a preposition. Strip them blindly and the sentence changes."),
    ]
    for i, (big, title, body) in enumerate(items):
        x = 0.55 + (i % 2) * 4.6
        y = 1.32 + (i // 2) * 1.55
        box(s, x, y, 4.35, 1.35, fill=WHITE, line=RULE)
        box(s, x, y, 0.06, 1.35, fill=GOLD if i > 1 else ACCENT, line=None,
            shape=MSO_SHAPE.RECTANGLE)
        text(s, x + 0.22, y + 0.18, 1.15, 0.6, big, size=17, color=DEEP, bold=True,
             spacing=0.85)
        text(s, x + 1.5, y + 0.2, 2.7, 0.44, title, size=11, color=NAVY, bold=True,
             spacing=1.05)
        text(s, x + 1.5, y + 0.68, 2.7, 0.56, body, size=9.5, color=GREY, spacing=1.12)

    note(s, 0.55, 4.5, 8.9, 0.82, "Our answer",
         "Don't force the speech into a tidier model. Record where every decision came from — the "
         "language of each word, the evidence for each lexicon entry, the rule behind each parse "
         "step — so any claim can be traced back.")
    return s


def slide_close(prs):
    s = add_slide(prs)
    box(s, 0, 0, W, H, fill=DEEP, line=None, shape=MSO_SHAPE.RECTANGLE)
    box(s, 0, 0, W, 0.07, fill=GOLD, line=None, shape=MSO_SHAPE.RECTANGLE)

    if LOGO.exists():
        s.shapes.add_picture(str(LOGO), Inches(4.45), Inches(0.82), height=Inches(1.15))

    text(s, 0.6, 2.25, 8.8, 0.66, "Thank you", size=38, color=WHITE, bold=True,
         align=PP_ALIGN.CENTER)
    text(s, 0.6, 2.98, 8.8, 0.34, "Questions?", size=16, color=GOLD,
         align=PP_ALIGN.CENTER)

    box(s, 3.2, 3.62, 3.6, 0.045, fill=RGBColor(0x2A, 0x5E, 0x49), line=None,
        shape=MSO_SHAPE.RECTANGLE)

    text(s, 0.6, 3.92, 8.8, 0.3,
         "Kamdeu Yamdjeuson Neil Marshall  ·  Eyong Seanna Tabe  ·  "
         "Tuheu Tchoubi Pempeme Moussa Fahdil",
         size=11, color=RGBColor(0xC7, 0xDE, 0xD1), align=PP_ALIGN.CENTER)
    text(s, 0.6, 4.28, 8.8, 0.3,
         "CS4110 · Compiler Construction  ·  The ICT University, Yaoundé",
         size=10, color=RGBColor(0x8F, 0xB3, 0xA2), align=PP_ALIGN.CENTER)
    text(s, 0.6, 4.78, 8.8, 0.3, "francanglais.duckdns.org", size=11, color=GOLD,
         bold=True, align=PP_ALIGN.CENTER, font="Consolas")
    return s


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Francanglais_Studio_CS4110.pptx"

    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)

    builders = [
        slide_title, slide_problem, slide_pipeline, slide_scanning,
        slide_dfa_scanner, slide_dfa_word, slide_lexing, slide_grammar, slide_table,
        slide_pda_parser, slide_trace, slide_results, slide_why_hard, slide_close,
    ]
    for b in builders:
        b(prs)

    prs.save(str(out))
    print(f"Wrote {out.name}: {len(prs.slides.__iter__.__self__._sldIdLst)} slides, "
          f"{out.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
