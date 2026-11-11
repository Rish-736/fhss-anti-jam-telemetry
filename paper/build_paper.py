"""
Build the IEEE Transactions manuscript as a .docx.

    python paper/build_paper.py

The supplied IEEE Transactions Word template is unpacked, its own styles,
numbering, header and section setup are kept untouched, and only
word/document.xml is regenerated from the content defined below. That way
the output carries the template's exact formatting rather than an
imitation of it.

Figures come from paper/figures/ (built by make_paper_figures.py).
"""

import os
import re
import shutil
import zipfile
from refs_list import REFS, NUM

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIGDIR = os.path.join(HERE, "figures")
TEMPLATE = os.path.join(HERE, "template.docx")
BUILD = os.path.join(HERE, "build")
OUTDOC = os.path.join(HERE, "FHSS_Anti_Jam_UAV_Telemetry_IEEE.docx")

COLUMN_TWIPS = 5040          # one IEEE column
EMU_PER_INCH = 914400

# ---------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------

_rels = []          # (rId, target) for images
_next_rid = [900]
_next_docpr = [100]


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def rpr(bold=False, italic=False, sz=None, smallcaps=False, sub=False,
        sup=False, mono=False, color=None):
    parts = []
    if mono:
        parts.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas" '
                     'w:cs="Consolas"/>')
    if bold:
        parts.append("<w:b/>")
    if italic:
        parts.append("<w:i/>")
    if smallcaps:
        parts.append("<w:smallCaps/>")
    if color:
        parts.append(f'<w:color w:val="{color}"/>')
    if sz:
        parts.append(f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>')
    if sub:
        parts.append('<w:vertAlign w:val="subscript"/>')
    if sup:
        parts.append('<w:vertAlign w:val="superscript"/>')
    return f"<w:rPr>{''.join(parts)}</w:rPr>" if parts else ""


def run(text, **kw):
    return (f"<w:r>{rpr(**kw)}"
            f'<w:t xml:space="preserve">{esc(text)}</w:t></w:r>')


# Inline markup understood in body text:
#   **bold**   *italic*   `monospace`   ~subscript~   ^superscript^
TOKEN = re.compile(r"(\*\*.+?\*\*|\*.+?\*|`.+?`|~.+?~|\^.+?\^)")


CITE_RE = re.compile(r"\[@([A-Za-z0-9_]+)\]")


def cites(text):
    """Resolve [@key] citations against the ordered reference list.

    Keeping citations symbolic in the body means the reference list
    can be reordered without renumbering anything by hand.
    """
    def one(m):
        key = m.group(1)
        if key not in NUM:
            raise KeyError(f"citation [@{key}] has no reference")
        return f"[{NUM[key]}]"
    return CITE_RE.sub(one, text)


def rich(text, base=None):
    text = cites(text)
    base = dict(base or {})
    out = []
    for part in TOKEN.split(text):
        if not part:
            continue
        kw = dict(base)
        if part.startswith("**") and part.endswith("**"):
            kw["bold"] = True
            part = part[2:-2]
        elif part.startswith("*") and part.endswith("*"):
            kw["italic"] = True
            part = part[1:-1]
        elif part.startswith("`") and part.endswith("`"):
            kw["mono"] = True
            kw.setdefault("sz", 17)
            part = part[1:-1]
        elif part.startswith("~") and part.endswith("~"):
            kw["sub"] = True
            part = part[1:-1]
        elif part.startswith("^") and part.endswith("^"):
            kw["sup"] = True
            part = part[1:-1]
        out.append(run(part, **kw))
    return "".join(out)


# The schema fixes the order of the children of w:pPr, and Word rejects
# a file that gets it wrong. Rather than make every call site remember
# the sequence, para() parses whatever fragments it is handed and sorts
# them.
PPR_ORDER = [
    "pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr",
    "widowControl", "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs",
    "suppressAutoHyphens", "kinsoku", "wordWrap", "overflowPunct",
    "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi", "adjustRightInd",
    "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment",
    "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr",
    "pPrChange",
]


def _split_elements(s):
    """Break a run of sibling XML elements into (tag, text) pairs."""
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] != "<":
            i += 1
            continue
        j = s.index(">", i)
        tag = re.match(r"<w:([A-Za-z]+)", s[i:j + 1]).group(1)
        if s[j - 1] == "/":
            out.append((tag, s[i:j + 1]))
            i = j + 1
        else:
            close = f"</w:{tag}>"
            k = s.index(close, j)
            out.append((tag, s[i:k + len(close)]))
            i = k + len(close)
    return out


def para(content, style=None, props="", rpr_tail=""):
    raw = ""
    if style:
        raw += f'<w:pStyle w:val="{style}"/>'
    raw += props + rpr_tail
    if not raw:
        return f"<w:p>{content}</w:p>"
    els = _split_elements(raw)
    els.sort(key=lambda e: PPR_ORDER.index(e[0])
             if e[0] in PPR_ORDER else len(PPR_ORDER))
    ppr = "".join(x for _, x in els)
    return f"<w:p><w:pPr>{ppr}</w:pPr>{content}</w:p>"


# ---------------------------------------------------------------------
# document-level block builders
# ---------------------------------------------------------------------

def title(text):
    frame = ('<w:framePr w:w="0" w:hSpace="0" w:vSpace="0" w:wrap="auto" '
             'w:vAnchor="margin" w:hAnchor="text" w:xAlign="left" '
             'w:yAlign="inline"/>')
    # The template's Title style is 24 pt, which overpowers a short
    # title and eats a third of the first page.
    return para(run(text, sz=34), style="Title",
                props=frame + '<w:spacing w:after="160"/>')


def centred(text, sz=22, italic=False, bold=False, after=0):
    props = '<w:jc w:val="center"/>'
    if after:
        props = f'<w:spacing w:after="{after}"/>' + props
    return para(rich(text, dict(sz=sz, italic=italic, bold=bold)),
                props=props)


def abstract(text):
    props = ('<w:spacing w:before="20"/><w:ind w:firstLine="202"/>'
             '<w:jc w:val="both"/>')
    body = (run("Abstract", bold=True, italic=True, sz=18)
            + run("—", bold=True, sz=18)
            + rich(text, dict(bold=True, sz=18)))
    return para(body, props=props)


def index_terms(text):
    props = '<w:jc w:val="both"/><w:spacing w:before="120"/>'
    body = (run("Index Terms", bold=True, italic=True, sz=18)
            + run("—", bold=True, sz=18)
            + rich(text, dict(bold=True, sz=18)))
    return para(body, props=props)


def h1(text):
    return para(run(text), style="Heading1")


def h2(text):
    kill = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'
    return para(rich(text, dict(italic=True)), style="Heading2", props=kill)


def body(text, first=False):
    # The template leaves no space between paragraphs, which reads as
    # a solid block in a two-column layout.
    return para(rich(text), style="PARA" if first else "Text",
                props='<w:spacing w:after="70"/>')


def equation(formula, number):
    props = '<w:ind w:left="340"/><w:spacing w:before="60" w:after="90"/>'
    content = (rich(formula) + "<w:r><w:tab/></w:r>" + run(f"({number})"))
    return para(content, style="Equation", props=props)


def bullet(text, indent=360):
    props = (f'<w:ind w:left="{indent + 160}" w:hanging="160"/>'
             '<w:jc w:val="both"/><w:spacing w:line="252" '
             'w:lineRule="auto"/>')
    return para(run("•   ") + rich(text), props=props)


def listed(label, text, indent=340):
    """A hanging-indent numbered or lettered item."""
    props = (f'<w:ind w:left="{indent}" w:hanging="{indent}"/>'
             '<w:jc w:val="both"/><w:spacing w:line="252" '
             'w:lineRule="auto" w:after="70"/>')
    return para(run(label, italic=True) + run("  ") + rich(text),
                props=props)


def blank(sz=18):
    return para("", rpr_tail=f'<w:rPr><w:sz w:val="{sz}"/></w:rPr>')


def placeholder(text):
    """A clearly marked gap for something the authors must supply."""
    props = ('<w:pBdr><w:top w:val="single" w:sz="4" w:color="B23A48"/>'
             '<w:left w:val="single" w:sz="4" w:color="B23A48"/>'
             '<w:bottom w:val="single" w:sz="4" w:color="B23A48"/>'
             '<w:right w:val="single" w:sz="4" w:color="B23A48"/></w:pBdr>'
             '<w:shd w:val="clear" w:color="auto" w:fill="FBEFF1"/>'
             '<w:spacing w:before="80" w:after="80"/>'
             '<w:jc w:val="center"/>')
    return para(rich(text, dict(sz=16, bold=True, color="B23A48")),
                props=props)


# ---------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------

def figure(filename, caption, width_in=3.4):
    from PIL import Image
    path = os.path.join(FIGDIR, filename)
    with Image.open(path) as im:
        w, h = im.size
    cx = int(width_in * EMU_PER_INCH)
    cy = int(cx * h / w)

    rid = f"rId{_next_rid[0]}"
    _next_rid[0] += 1
    _rels.append((rid, filename))
    did = _next_docpr[0]
    _next_docpr[0] += 1

    drawing = (
        '<w:r><w:drawing>'
        '<wp:inline distT="0" distB="0" distL="0" distR="0">'
        f'<wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{did}" name="Figure {did}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/'
        'drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/'
        'drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{did}" name="{filename}"/>'
        '<pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/>'
        '<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic>'
        '</wp:inline></w:drawing></w:r>')

    img_p = para(drawing, props='<w:jc w:val="center"/>'
                                '<w:spacing w:before="200" w:after="60"/>'
                                '<w:keepNext/>')
    cap_p = para(rich(caption, dict(sz=16)), style="FigureCaption",
                 props='<w:spacing w:after="260"/>')
    return img_p + cap_p


def fig_placeholder(tag, caption, description):
    return (placeholder(tag) +
            para(rich(description, dict(sz=16, italic=True)),
                 props='<w:jc w:val="both"/><w:spacing w:after="60"/>') +
            para(rich(caption, dict(sz=16)), style="FigureCaption",
                 props='<w:spacing w:after="160"/>'))


# ---------------------------------------------------------------------
# tables  (IEEE three-rule style)
# ---------------------------------------------------------------------

def table(number, caption, header, rows, widths, aligns=None, sz=15,
          note=None):
    total = sum(widths)
    scale = COLUMN_TWIPS / total
    widths = [int(w * scale) for w in widths]
    widths[-1] += COLUMN_TWIPS - sum(widths)
    aligns = aligns or ["center"] * len(header)

    head_p = (para(run(f"TABLE {number}"),
                   props='<w:jc w:val="center"/><w:keepNext/>'
                         '<w:spacing w:before="240"/>') +
              para(run(caption, smallcaps=True), style="TableTitle",
                   props='<w:keepNext/><w:spacing w:after="60"/>'))

    def cell(text, w, align, bold=False, bottom=False, top=False,
             keep=True):
        borders = []
        if top:
            borders.append('<w:top w:val="single" w:sz="8" '
                           'w:color="000000"/>')
        if bottom:
            borders.append('<w:bottom w:val="single" w:sz="6" '
                           'w:color="000000"/>')
        b = f"<w:tcBorders>{''.join(borders)}</w:tcBorders>" if borders else ""
        return (f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/>{b}'
                '<w:vAlign w:val="center"/></w:tcPr>'
                '<w:p><w:pPr>'
                + ('<w:keepNext/>' if keep else '')
                + '<w:spacing w:before="40" w:after="40"/>'
                + f'<w:jc w:val="{align}"/>'
                f'<w:rPr><w:sz w:val="{sz}"/></w:rPr></w:pPr>'
                f'{rich(text, dict(sz=sz, bold=bold))}</w:p></w:tc>')

    xml = ['<w:tbl><w:tblPr>'
           f'<w:tblW w:w="{COLUMN_TWIPS}" w:type="dxa"/>'
           '<w:jc w:val="center"/>'
           '<w:tblBorders>'
           '<w:top w:val="single" w:sz="8" w:color="000000"/>'
           '<w:bottom w:val="single" w:sz="8" w:color="000000"/>'
           '</w:tblBorders>'
           '<w:tblCellMar>'
           '<w:top w:w="10" w:type="dxa"/><w:left w:w="50" w:type="dxa"/>'
           '<w:bottom w:w="10" w:type="dxa"/><w:right w:w="50" w:type="dxa"/>'
           '</w:tblCellMar></w:tblPr><w:tblGrid>']
    xml += [f'<w:gridCol w:w="{w}"/>' for w in widths]
    xml.append("</w:tblGrid>")

    xml.append('<w:tr><w:trPr><w:cantSplit/><w:tblHeader/>'
               '<w:jc w:val="center"/></w:trPr>')
    for t, w, a in zip(header, widths, aligns):
        xml.append(cell(t, w, a, bold=True, bottom=True))
    xml.append("</w:tr>")

    for n, r in enumerate(rows):
        last = n == len(rows) - 1
        xml.append('<w:tr><w:trPr><w:cantSplit/>'
                   '<w:jc w:val="center"/></w:trPr>')
        for t, w, a in zip(r, widths, aligns):
            xml.append(cell(str(t), w, a, keep=not last))
        xml.append("</w:tr>")
    xml.append("</w:tbl>")

    tail = ""
    if note:
        tail = para(rich(note, dict(sz=14)),
                    props='<w:jc w:val="both"/><w:spacing w:before="60" '
                          'w:after="260"/>')
    else:
        tail = blank(20)
    return head_p + "".join(xml) + tail


def algorithm(title_text, lines):
    out = [para(run(title_text, bold=True, sz=16),
                props='<w:pBdr><w:top w:val="single" w:sz="8" '
                      'w:color="000000"/><w:bottom w:val="single" w:sz="4" '
                      'w:color="000000"/></w:pBdr>'
                      '<w:spacing w:before="160" w:after="40"/>'
                      '<w:keepNext/>')]
    for n, (depth, text) in enumerate(lines, 1):
        # Line numbers sit in a fixed gutter and the body is indented by a
        # tab, so nesting depth does not drag the numbering across with it.
        stop = 230 + depth * 180
        props = (f'<w:keepNext/><w:tabs><w:tab w:val="left" '
                 f'w:pos="{stop}"/></w:tabs>'
                 f'<w:ind w:left="{stop}" w:hanging="{stop}"/>'
                 '<w:spacing w:after="0"/>')
        out.append(para(run(f"{n:>2}:", sz=15) + "<w:r><w:tab/></w:r>"
                        + rich(text, dict(sz=15)), props=props))
    out.append(para("", props='<w:pBdr><w:top w:val="single" w:sz="8" '
                              'w:color="000000"/></w:pBdr>'
                              '<w:spacing w:after="160"/>',
                    rpr_tail='<w:rPr><w:sz w:val="8"/></w:rPr>'))
    return "".join(out)


def reference(n, text):
    """IEEE bracketed reference with a hanging indent.

    The template's References style auto-numbers as "1."; automatic
    numbering is switched off and the bracketed label typed instead, so
    the output does not depend on Word's list state.
    """
    props = ('<w:numPr><w:ilvl w:val="0"/><w:numId w:val="0"/></w:numPr>'
             '<w:tabs><w:tab w:val="left" w:pos="340"/></w:tabs>'
             '<w:ind w:left="340" w:hanging="340"/>'
             '<w:spacing w:after="20"/>')
    label = run(f"[{n}]", sz=16) + "<w:r><w:tab/></w:r>"
    return para(label + rich(text, dict(sz=16)), style="References",
                props=props)


# =====================================================================
#                           PAPER CONTENT
# =====================================================================

TITLE = "Measuring Schedule Loss in Self-Scheduled Frequency-Hopping Links"

# IEEE conference-style author block: one column per author.
AUTHOR_COLUMNS = [
    ["Rishit Sinha 24BEC0529",
     "Electronics and Communications",
     "Vellore Institute of Technology",
     "Vellore, India",
     "rishit.sinha2024@vitstudent.ac.in"],
    ["Rupsa Mittra 24BEC0176",
     "Electronics and Communications",
     "Vellore Institute of Technology",
     "Vellore, India",
     "rupsa.mittra2024@vitstudent.ac.in"],
    ["Velmurugan T.",
     "Electronics and Communications",
     "Vellore Institute of Technology",
     "Vellore, India",
     "tvelmurugan@vit.ac.in"],
]


def author_block(columns):
    """Three side-by-side author entries, as in the IEEE conference
    template: name in roman, affiliation lines in italic, then city and
    e-mail in roman."""
    width = 10080 // len(columns)

    def cell(lines):
        paras = []
        for i, text in enumerate(lines):
            italic = i in (1, 2)
            sz = 22 if i == 0 else 20
            paras.append(
                '<w:p><w:pPr><w:spacing w:after="0"/>'
                '<w:jc w:val="center"/>'
                f'<w:rPr><w:sz w:val="{sz}"/></w:rPr></w:pPr>'
                + rich(text, dict(sz=sz, italic=italic)) + '</w:p>')
        return (f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>'
                '</w:tcPr>' + "".join(paras) + '</w:tc>')

    grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in columns)
    cells = "".join(cell(c) for c in columns)
    return ('<w:tbl><w:tblPr><w:tblW w:w="10080" w:type="dxa"/>'
            '<w:jc w:val="center"/>'
            '<w:tblCellMar><w:left w:w="80" w:type="dxa"/>'
            '<w:right w:w="80" w:type="dxa"/></w:tblCellMar>'
            f'</w:tblPr><w:tblGrid>{grid}</w:tblGrid>'
            f'<w:tr>{cells}</w:tr></w:tbl>')


ABSTRACT = (
    "A frequency-hopping link that carries its own hop schedule inside "
    "its data packets needs neither a synchronised clock nor a control "
    "channel, which makes it attractive for low-cost unmanned aerial "
    "vehicle (UAV) telemetry. This paper shows that the arrangement "
    "couples two failures that are usually independent: losing a packet "
    "also loses the schedule. The consequence is measured on a two-node "
    "433 MHz link built from ESP32 microcontrollers and CC1101 "
    "transceivers, under channel denial emulated in firmware so that no "
    "interference is ever transmitted. Denying one of five channels "
    "removed 98 % of traffic rather than the 20 % a per-channel "
    "argument predicts, an amplification of 4.9. Adding cyclic "
    "rendezvous recovery bounds the damage but makes it *saturate*: "
    "delivery becomes independent of how many channels are denied and "
    "depends only on the hop distance from the rendezvous channel to "
    "the first denied one. A closed-form expression in that single "
    "parameter reproduces three measured delivery counts exactly, with "
    "no fitted quantity. Transmitter-side clear-channel assessment "
    "avoids the channels it can detect as occupied and reduces loss to "
    "2 %, with "
    "no false alarms in 101 measurements against a noise floor of "
    "\u2212105.3 \u00b1 1.6 dBm. The contribution is a characterisation "
    "and a model of a failure mode rather than a new hopping scheme. "
    "Reliability improves when interference affects part of the hop "
    "set; no claim is made against wideband denial."
)

INDEX_TERMS = (
    "Channel blacklisting, clear channel assessment, frequency-hopping "
    "spread spectrum, hop schedule, link reliability, rendezvous "
    "recovery, unmanned aerial vehicle telemetry."
)

# ---------------------------------------------------------------------

DOC = []
A = DOC.append

A(title(TITLE))
A(author_block(AUTHOR_COLUMNS))
A(blank(16))
A(abstract(ABSTRACT))
A(index_terms(INDEX_TERMS))

SECT1 = ('<w:sectPr><w:headerReference w:type="default" r:id="rId9"/>'
         '<w:type w:val="continuous"/>'
         '<w:pgSz w:w="12240" w:h="15840"/>'
         '<w:pgMar w:top="1008" w:right="936" w:bottom="1008" w:left="936" '
         'w:header="432" w:footer="432" w:gutter="0"/>'
         '<w:pgNumType w:start="1"/><w:cols w:space="288"/></w:sectPr>')
A(para("", props=SECT1 + '<w:spacing w:after="200"/>'))

# ----------------------------- I ------------------------------------
A(h1("I. Introduction"))

A(body(
    "A small unmanned aerial vehicle (UAV) depends on its telemetry link "
    "for state reporting, command upload and, critically, for the "
    "failsafe and return-to-home behaviour invoked when something goes "
    "wrong. In the low-cost segment that link is almost always a single "
    "narrowband channel: a fixed-frequency serial radio bridging the "
    "flight controller to a ground station. Any device placing energy on "
    "that one channel removes the entire link, and removes it precisely "
    "when the aircraft most needs to be told what to do.", first=True))

A(body(
    "Frequency-hopping spread spectrum (FHSS) is the classical answer. "
    "The two ends agree on a set of channels and move through them "
    "together, so energy confined to one channel can only affect the "
    "fraction of traffic sent while the link happens to be there. Adding "
    "transmitter-side clear-channel assessment (CCA) sharpens this "
    "further: a channel that looks occupied is skipped before it is "
    "used, rather than discovered to be unusable after a packet has "
    "already been lost on it."))

A(body(
    "Two design choices follow from the constraint that the radio is a "
    "microcontroller-class device with no accurate time reference. "
    "First, the hop schedule is *self-scheduled*: each packet names the "
    "channel the transmitter will move to next, so neither a shared "
    "clock nor a control channel is required. Second, the receiver "
    "returns to an agreed rendezvous channel when it has heard nothing "
    "for a fixed interval. Both choices are standard, and both are "
    "cheap."))

A(body(
    "Much of the published work on UAV anti-jamming is evaluated in "
    "simulation [@atheeq24], [@wang25], [@jiao23], where the schedule is modelled as "
    "being known to both ends. On hardware the distribution of that "
    "schedule is itself a failure surface, and this paper shows that it "
    "is the dominant one. Self-scheduling couples two failures that are "
    "normally independent: a packet lost on an unusable channel also "
    "carries away the instruction that would have told the receiver "
    "where to go next. The link does not degrade in proportion to the "
    "fraction of the band removed \u2014 it stops."))

A(body(
    "This paper is therefore a characterisation and a model rather than "
    "a new hopping scheme. The contributions are as follows."))

A(listed("1)",
         "*Schedule-coupled loss* is identified and measured. Denying "
         "one channel of five removed 98 % of traffic rather than 20 %, "
         "an amplification of 4.9, and the mechanism is traced to loss "
         "of the next-channel instruction rather than to loss of the "
         "payload."))
A(listed("2)",
         "*Denial saturation* is reported: once rendezvous recovery is "
         "present, delivery no longer depends on how many channels are "
         "denied, only on the hop distance *d* from the rendezvous "
         "channel to the first denied one. Denying a second channel "
         "changed the measured delivery count by zero packets."))
A(listed("3)",
         "A closed-form delivery model in the single parameter *d* is "
         "derived from the mechanism and reproduces three measured "
         "delivery counts exactly, with no fitted quantity."))
A(listed("4)",
         "The resulting design rule is quantified: recovery is "
         "necessary but not sufficient, and transmitter-side clear "
         "channel assessment, which avoids the affected channel "
         "before the schedule is lost on it, "
         "takes the same link from 98 % loss to 2 %. Supporting "
         "measurements include a noise floor of "
         "\u2212105.3 \u00b1 1.6 dBm, a false-alarm rate of 0 in 101, "
         "and a channel-plan error that only measurement exposed."))

# ----------------------------- II -----------------------------------
A(h1("II. Related Work"))

A(h2("A. Anti-Jamming for UAV Links"))
A(body(
    "The telemetry protocols in common use offer no protection of their "
    "own. MAVLink, surveyed by Koubaa *et al.* [@koubaa19], transmits "
    "unauthenticated and unencrypted by default; MAVSec [@allouch19] adds "
    "encryption at the cost of latency, and neither addresses "
    "availability. Petnga and Xu [@petnga16] place jamming within a broader "
    "cyber-physical threat model for UAVs. Surveys of jamming and its "
    "countermeasures [@pirayesh22], [@jaitly17], together with the measurement study of "
    "Xu *et al.* [@xu05], establish both how cheaply a narrowband link is "
    "removed and how awkward it is to distinguish jamming from "
    "ordinary poor reception.", first=True))

A(body(
    "Recent UAV-specific countermeasures are largely learning-based or "
    "game-theoretic. Lv *et al.* [@lv17] formulate transmit power as a "
    "game against a jammer; Jiao *et al.* [@jiao23] shape the trajectory of "
    "the aircraft itself; Liu *et al.* [@liu18] select channels from a "
    "spectrum waterfall using deep reinforcement learning; and Wang "
    "*et al.* [@wang25] switch between intelligent hopping and backscatter. "
    "All four are evaluated in simulation and assume computational and "
    "sensing resources well beyond a microcontroller-class telemetry "
    "radio, which is the design point addressed here."))

A(body(
    "The most recent work continues in the same direction. Cheng *et "
    "al.* [@cheng25] apply deep reinforcement learning to fast "
    "frequency hopping, and Song *et al.* [@songl25] jointly adapt rate "
    "and frequency against a jammer; Xie *et al.* [@xie25] extend the "
    "approach to UAV-assisted device-to-device networks. A parallel "
    "line of work detects rather than evades: Cibecchini *et al.* "
    "[@cibecchini25] classify drone jamming with a lightweight model, "
    "Ayegun *et al.* [@ayegun25] target universal detection across "
    "attack types, and Oh and Kang [@oh26] give early warning from "
    "link statistics in drone ad-hoc networks. Detection is "
    "complementary to the present work: the failure reported here is "
    "visible precisely because the link is instrumented packet by "
    "packet, but detecting a bad channel is of no use if the act of "
    "discovering it destroys the schedule."))

A(h2("B. Hop-Sequence Secrecy Versus Hop-Schedule Distribution"))
A(body(
    "A distinction the literature does not usually draw is central to "
    "this paper. Most anti-jamming hopping work improves the "
    "*sequence*: how the order of channels is generated, and how hard "
    "it is for an adversary to predict. Atheeq *et al.* [@atheeq24] are "
    "representative, deriving the hop order from a chaotic map so that "
    "observing past hops does not reveal future ones. Classical "
    "treatments of processing gain under partial-band jamming [@pickholtz82], [@lo91] "
    "likewise concern the sequence and the spreading factor.",
    first=True))

A(body(
    "The present work concerns the *distribution* of the schedule "
    "instead: given that both ends must agree on where to go next, how "
    "is that agreement conveyed, and what happens when the conveying "
    "mechanism fails? Sequence secrecy and schedule distribution are "
    "orthogonal. A perfectly unpredictable sequence must still be "
    "communicated, and if it is communicated in band it inherits the "
    "coupling reported in Section V. To the authors' knowledge the cost "
    "of that coupling has not previously been measured or modelled."))

A(h2("C. Sensing Before Transmitting"))
A(body(
    "Assessing a channel before using it is long established. Energy "
    "detection and its alternatives are surveyed by Yucek and Arslan "
    "[@yucek09]. Within hopping systems specifically, Bluetooth adaptive "
    "frequency hopping classifies channels and removes bad ones from "
    "the hop set [@moon06], and Kim *et al.* [@kim01] combine listen-before-talk "
    "with adaptive hopping for Bluetooth/WLAN coexistence, which is the "
    "closest prior art to the sensing layer used here. "
    "Listen-before-talk underpins unlicensed-band coexistence more "
    "generally [@song16], and measured coexistence in shared ISM "
    "spectrum is reported in [@sikora05] and, more recently and at "
    "length, in [@lora25]. Threshold choice remains an active question: "
    "He *et al.* [@he26] set a sliding-window detection threshold "
    "adaptively for high-speed hopping signals, where a fixed threshold "
    "either misses occupancy or raises false alarms. The present work "
    "uses a fixed threshold and reports its measured false-alarm rate "
    "rather than tuning it. The sensing mechanism in this paper is "
    "therefore "
    "not claimed as novel; it is used as the control that establishes "
    "the cost of the coupling.", first=True))

A(h2("D. Blacklisting in Scheduled Hopping Networks"))
A(body(
    "Blacklisting is well studied in IEEE 802.15.4 time-slotted channel "
    "hopping. Kotsiou *et al.* [@kotsiou19] compare distributed and global "
    "blacklisting against an experimental dataset, Elsts *et al.* [@elsts17] "
    "adapt channel selection online, and Cena *et al.* [@cena22] apply "
    "probabilistic blacklisting for low-power operation. The setting in "
    "all three is a scheduled multi-hop mesh with a network-wide slot "
    "number [@palattella15], so blacklist state can be disseminated and agreed "
    "between nodes. A two-node telemetry link has neither a global "
    "clock nor a dissemination path, which is precisely why the in-band "
    "scheduling of Section III-C is used, and why its failure mode "
    "matters.", first=True))

A(body(
    "How a blacklisted channel is brought back also matters. Jo and "
    "Baek [@jo26] show that the remapping used by adaptive fast "
    "frequency hopping leaves recovered channels under-used, and "
    "propose an explicit restoration step. The cooldown of "
    "Section III-E serves the same purpose by the simplest available "
    "means: a blacklisted channel is retried after a fixed number of "
    "cycles, so a channel that was briefly busy returns to the hop set "
    "without any signalling between the two ends."))

A(h2("E. Rendezvous and Schedule Re-Acquisition"))
A(body(
    "Returning to an agreed channel after losing contact is the "
    "rendezvous problem of cognitive radio. Lin *et al.* [@lin11] give a "
    "jump-stay construction with a guaranteed bound on time to "
    "rendezvous, and Tan and Yuan [@tan19] extend blind rendezvous to "
    "multi-radio nodes; Chang *et al.* [@chang26] and Asadi Vasfi and "
    "Shahgholi Ghahfarokhi [@vasfi25] give more recent sequences with "
    "tighter diversity and time-to-rendezvous guarantees. That "
    "literature asks how quickly two nodes "
    "*can* meet. The question here is different and, for this failure "
    "mode, more consequential: given that they do meet, how much "
    "traffic is delivered before the schedule is lost again? The "
    "saturation result of Section V follows from that second question.",
    first=True))

A(h2("F. Patent Precedent"))
A(body(
    "The constituent mechanisms have patent precedent and are not "
    "claimed here. US 6,169,761 [@marcoccia01] claims, for a frequency-hop "
    "system, comparing a received signal strength measurement against a "
    "threshold to classify a channel as busy, omitting busy channels "
    "from use, and recovering synchronisation through an agreed "
    "channel. US 8,165,242 [@voglewede12] addresses jamming avoidance at the "
    "*receiver*, selecting among dwells and resynchronising, without "
    "involving the transmitter in channel selection and without "
    "maintaining a blacklist.", first=True))

A(h2("G. Position of This Work"))
A(body(
    "Table I sets this paper against its closest neighbour in the "
    "literature. The difference is one of contribution type as much as "
    "of mechanism: [@atheeq24] proposes a scheme and shows it works in "
    "simulation, whereas this paper measures and models why a widely "
    "used arrangement fails on hardware. The two are complementary, in "
    "that a chaotic sequence distributed in band would exhibit exactly "
    "the coupling reported here.", first=True))

A(table(
    "I",
    "Position Relative to the Closest Prior Work",
    ["Aspect", "Atheeq *et al.* [@atheeq24]", "This work"],
    [["Object of study", "Hop sequence generation",
      "Hop schedule distribution"],
     ["Mechanism", "Chaotic map", "In-band next-channel announcement"],
     ["Adversary assumed", "Predicts the sequence",
      "Renders part of the hop set unusable"],
     ["Evaluation", "Network simulation",
      "Two-node COTS hardware, 433 MHz"],
     ["Headline output", "A scheme that mitigates jamming",
      "A closed-form delivery model, validated"],
     ["Failure analysis", "Not reported", "The primary contribution"],
     ["Denial method", "Modelled jammer",
      "Firmware-emulated; nothing transmitted"]],
    [1120, 1680, 2240],
    ["left", "left", "left"]))

# ----------------------------- III ----------------------------------
A(h1("III. System Design"))

A(h2("A. Hardware"))
A(body(
    "The system comprises two identical nodes, shown in Fig. 1. Each "
    "pairs an ESP32 DevKit v1 [@esp32] with a CC1101 sub-1 GHz transceiver "
    "[@cc1101] over a four-wire SPI bus at 3.3 V. Table II gives the inventory "
    "and the interconnection.", first=True))

A(body(
    "One node runs transmitter firmware and one runs receiver firmware, "
    "but the hardware is interchangeable, and both share a single "
    "configuration header copied into each sketch at build time. That "
    "makes it structurally impossible for the two ends to disagree about "
    "the channel plan or the radio parameters."))

A(table(
    "II",
    "Hardware and Interconnection",
    ["Item", "Qty", "Role"],
    [["ESP32 DevKit v1", "2", "Protocol logic, SPI master, logging"],
     ["CC1101 433 MHz module", "2", "2-FSK transceiver, RSSI measurement"],
     ["Quarter-wave antenna", "2", "One per transceiver"],
     ["", "", ""],
     ["*CC1101 pin*", "", "*ESP32 pin*"],
     ["VCC", "", "3.3 V"],
     ["GND", "", "GND"],
     ["SCK", "", "GPIO 18"],
     ["MOSI / SI", "", "GPIO 23"],
     ["MISO / SO", "", "GPIO 19"],
     ["CSN / CS", "", "GPIO 5"]],
    [1700, 400, 2940],
    ["left", "center", "left"]))

A(figure("fig1_architecture.png",
         "Fig. 1.  System architecture. All adaptive behaviour sits at "
         "the transmitter, so the receiver firmware is unchanged between "
         "the basic and adaptive designs."))

A(h2("B. Physical Layer and Channel Plan"))
A(body(
    "Table III lists the physical-layer configuration, applied "
    "identically at both ends. Binary frequency-shift keying is used at "
    "99.97 kb/s with 47.60 kHz deviation, a 16-bit sync word and "
    "hardware CRC.", first=True))

A(table(
    "III",
    "Physical-Layer Configuration",
    ["Parameter", "Value", "Purpose"],
    [["Modulation", "2-FSK", "Simple and robust"],
     ["Deviation", "47.60 kHz", "Sets occupied bandwidth, (1)"],
     ["Data rate", "99.97 kb/s", "Short dwell per packet"],
     ["Receive bandwidth", "270.83 kHz", "Passes (1), rejects neighbours"],
     ["Sync word", "0xD391 (16 bit)", "16/16 bits must match; MDMCFG2.SYNC_MODE = 2"],
     ["CRC", "Enabled", "Corrupt frames dropped in hardware"],
     ["Transmit power", "+10 dBm", "Within the 10 mW e.r.p. limit"],
     ["Hop set size *N*", "5", "Five channels, 400 kHz apart"],
     ["Packet interval", "1.2 s", "Measured mean"]],
    [1480, 1180, 2380],
    ["left", "center", "left"]))

A(body(
    "The occupied bandwidth of one transmission follows Carson's rule,"))
A(equation("*B* ≈ 2(Δ*f* + *R*~b~/2) = 2(47.60 + 50.0) "
           "≈ 195 kHz,", 1))
A(body(
    "where Δ*f* is the peak deviation and *R*~b~ the bit rate. The "
    "five channel centres are"))
A(equation("*f*~i~ = 433.05 + 0.40 *i*  MHz,   *i* = 0, …, 4,", 2))
A(body(
    "placing all five inside the 433.05–434.79 MHz licence-exempt "
    "band [@gsr22]. Fig. 2 shows the plan."))

A(figure("fig2_channel_plan.png",
         "Fig. 2.  Channel plan. Each transmission occupies about "
         "195 kHz; the receiver passband is 270.83 kHz, so energy from "
         "an adjacent channel falls outside it."))

A(body(
    "The spacing matters more than it first appears. With 400 kHz "
    "spacing the nearest edge of an adjacent transmission sits at"))
A(equation("Δ = 400 − *B*/2 = 400 − 97.5 = 302.5 kHz", 3))
A(body(
    "from the wanted centre, against a receiver half-bandwidth of "
    "135.4 kHz. The channels are therefore genuinely independent. "
    "Section V-E describes the earlier configuration in which they were "
    "not."))

A(body(
    "Two further quantities follow directly from the modulation. The "
    "modulation index, the ratio of peak-to-peak deviation to bit rate, "
    "is"))
A(equation("*h* = 2Δ*f* / *R*~b~ = 2(47.60) / 99.97 ≈ 0.952,", 4))
A(body(
    "which places the link just below the *h* = 1 point and keeps the "
    "two tones separable in a 270.83 kHz passband. The bit duration is"))
A(equation("*T*~b~ = 1 / *R*~b~ = 1 / 99.97 kb/s ≈ 10.0 μs.", 5))
A(body("The spread-spectrum processing gain is"))
A(equation("*G*~p~ = *W*~ss~ / *B* ≈ 1.80 MHz / 195 kHz ≈ 9.2 "
           "(9.6 dB).", 6))
A(body(
    "Against a single-channel interferer the more conservative figure is "
    "the hop-set size itself,"))
A(equation("*G*~p,min~ = 10 log~10~ *N* = 10 log~10~ 5 = 7.0 dB.", 7))
A(body(
    "Neither bounds performance against an interferer covering the whole "
    "band. For reference, the thermal noise power in the receiver "
    "passband is"))
A(equation("*P*~n~ = −174 + 10 log~10~ *B*~rx~ = −174 + 54.3 "
           "= −119.7 dBm,", 8))
A(body(
    "with *B*~rx~ = 270.83 kHz; Section V-F compares this with the "
    "floor actually measured."))

A(h2("C. In-Band Hop Scheduling"))
A(body(
    "Hopping requires both ends to be on the same channel at the same "
    "instant. The usual means are a shared clock or a separate control "
    "channel, and a two-node link built from two microcontrollers has "
    "neither. The scheme used here carries the schedule inside the data. "
    "Every packet has the form", first=True))
A(para(rich("`SEQ:<sequence number>,NEXT:<hop index>`"),
       props='<w:jc w:val="center"/><w:spacing w:before="80" '
             'w:after="80"/>'))
A(body(
    "so on receiving a packet the receiver learns both its position in "
    "the stream and the channel the transmitter is about to move to. "
    "Writing *c*~rx~(*k*) for the channel the receiver is tuned to after "
    "packet *k*, the schedule it follows is the recurrence"))
A(equation("*c*~rx~(*k*+1) = NEXT(*p*~k~) on success,  "
           "*c*~rx~(*k*) on loss.", 9))
A(body(
    "The second branch is the whole problem: a loss does not advance the "
    "receiver, so it is left on a channel the transmitter has already "
    "left. The transmitter visits every channel once per cycle, so the "
    "period at which it revisits any given channel is set by the "
    "end-to-end packet cadence *T*~i~ rather than by the programmed "
    "inter-packet delay *T*~p~ = 700 ms. Measured over runs 3, 7 and 8, "
    "*T*~i~ has a median of 1.200 s and a mean of 1.23 s; the excess "
    "over *T*~p~ is spent in the blocking driver transmit call and the "
    "serial logging that follows it. The revisit period is therefore"))
A(equation("*T*~c~ = *N* · *T*~i~ = 5 × 1.200 s = 6.0 s,", 10))
A(body(
    "so a stranded receiver hears the transmitter exactly once every "
    "*T*~c~ and is deaf for the remaining *N* − 1 transmissions. All "
    "timing figures quoted in this paper use the measured *T*~i~, not "
    "the programmed *T*~p~. Fig. 3(a) shows the nominal case."))

A(body(
    "This needs no clock discipline, but it couples data delivery to "
    "schedule delivery, and that coupling is the failure surface. If a "
    "packet is lost, the receiver loses not only its payload but its "
    "instruction for where to go next. The transmitter hops; the "
    "receiver does not; the link is gone. Fig. 3(b) shows this, and "
    "Section V-B measures it."))

A(figure("fig3_protocol.png",
         "Fig. 3.  In-band hop scheduling. (a) Each packet names the "
         "channel the transmitter will use next. (b) A packet discarded "
         "on a denied channel takes its NEXT field with it, stranding "
         "the receiver."))

A(h2("D. Rendezvous Recovery"))
A(body(
    "The mitigation is a cyclic fallback. If the receiver has accepted "
    "nothing valid for 2000 ms it retunes to a pre-agreed rendezvous "
    "channel, here channel 0, and waits. The transmitter passes through "
    "that channel once per cycle of five packets, so contact is "
    "re-established within roughly one cycle. This converts total "
    "collapse into bounded, periodic loss.", first=True))

A(body("The trigger is a silence timer:"))
A(equation("*t* \u2212 *t*~last~ > *T*~r~ = 2000 ms  \u21d2  "
           "*c*~rx~ \u2190 *c*~0~,", 11))
A(body(
    "with *t*~last~ the arrival time of the last accepted packet. Once "
    "the receiver is parked on *c*~0~ the transmitter passes it within "
    "one cycle, so the nominal time from loss of synchronisation to "
    "recovery is"))
A(equation("*T*~acq~ ≈ *T*~r~ + *T*~c~ = 2.0 + 6.0 = 8.0 s.", 12))
A(body(
    "This is a typical figure under the measured operating conditions, "
    "not a guaranteed bound. It is computed from the median cadence, "
    "and individual inter-packet gaps of up to about 4 s were observed "
    "in the logs, so a true worst case would be longer. Establishing a "
    "guaranteed bound would require the transmit path to be given a "
    "deterministic timing budget, which the blocking driver call used "
    "here does not provide."))
A(body(
    "The receiver therefore has only two states, shown in Fig. 4, and "
    "Algorithm 2 gives the loop. Note that the receiver never senses "
    "and never chooses a channel: all adaptivity lives at the "
    "transmitter, so the same receiver firmware serves every "
    "configuration in Section IV."))

A(figure("fig_rx_state.png",
         "Fig. 4.  Receiver schedule tracking. A decoded packet advances "
         "the receiver to the announced channel; *T*~r~ of silence sends "
         "it back to the rendezvous channel *c*~0~."))

A(algorithm("Algorithm 2  Receiver schedule tracking and recovery", [
    (0, "**procedure** ReceiveLoop"),
    (1, "*c*~rx~ \u2190 *c*~0~;  *t*~last~ \u2190 now"),
    (1, "**loop**"),
    (2, "**if** PacketReady() **and** CrcOk() **then**"),
    (3, "**if** denied(*c*~rx~) **then**"),
    (4, "discard packet   \u25b7 NEXT is lost with it"),
    (3, "**else**"),
    (4, "(*seq*, *next*) \u2190 Parse(payload)"),
    (4, "record *seq*;  *t*~last~ \u2190 now"),
    (4, "*c*~rx~ \u2190 *next*;  tune to *f*~next~"),
    (3, "**end if**"),
    (2, "**else if** now \u2212 *t*~last~ > *T*~r~ **then**"),
    (3, "*c*~rx~ \u2190 *c*~0~;  tune to *f*~0~;  "
        "*t*~last~ \u2190 now"),
    (2, "**end if**"),
    (1, "**end loop**"),
    (0, "**end procedure**"),
]))

A(h2("E. Sense-Before-Hop Channel Avoidance"))
A(body(
    "The adaptive transmitter does not simply advance to the next "
    "channel. Before committing it tunes to the candidate, lets the RSSI "
    "register settle for 5 ms, and reads the ambient level. A candidate "
    "whose level exceeds a threshold Λ is declared occupied, is "
    "blacklisted for three cycles, and the next candidate is examined:",
    first=True))
A(equation("accept channel *c*  ⇔  *P*~RSSI~(*c*) < Λ,  "
           "Λ = −75 dBm.", 13))
A(body(
    "A refused channel is not banned permanently. Each channel carries a "
    "cooldown counter that is set on refusal and aged once per hop "
    "cycle,"))
A(equation("cd~c~ \u2190 3 on refusal;   "
           "cd~c~ \u2190 max(cd~c~ \u2212 1, 0) each cycle,", 14))
A(body(
    "so a channel that was briefly busy rejoins the hop set after three "
    "cycles with no signalling between the two ends. Writing *B* for the "
    "set of channels currently refused, the usable hop set and the "
    "condition for the link to continue at all are"))
A(equation("|*A*| = *N* − |*B*|,     |*A*| ≥ 1  and  "
           "*c*~0~ ∉ *B*.", 15))
A(body(
    "Both conditions are needed. The first keeps a channel available to "
    "carry traffic; the second keeps the rendezvous channel usable, "
    "without which a receiver that loses the schedule cannot re-acquire "
    "it however many other channels remain. Channel 0 was never denied "
    "in any run reported here, so the second condition held throughout "
    "and was not tested. This is the sense in which hopping buys a "
    "bounded amount of protection: it fails when the whole hop set is "
    "denied, which is the wideband case excluded throughout. "
    "Algorithm 1, drawn "
    "as Fig. 5, gives the selection procedure, and Algorithm 3 the "
    "transmit cycle that calls it. Two design choices are worth drawing "
    "out. If every candidate appears occupied the transmitter falls back "
    "to plain sequential hopping rather than stalling: a link that keeps "
    "trying is more useful than one that stops. And whatever channel is "
    "chosen is announced in the NEXT field exactly as the non-adaptive "
    "transmitter would announce it, so the receiver needs no "
    "modification between the basic and adaptive designs."))

A(algorithm("Algorithm 1  Sense-before-hop channel selection", [
    (0, "**procedure** SelectNextHop(*current*)"),
    (1, "**for** *offset* = 1 **to** *N* **do**"),
    (2, "*c* ← (*current* + *offset*) **mod** *N*"),
    (2, "**if** cooldown[*c*] > 0 **then continue**"),
    (2, "tune to *f*~c~; enter RX; wait 5 ms"),
    (2, "*p* ← ReadRSSI()"),
    (2, "**if** *p* < Λ **then return** *c*"),
    (2, "cooldown[*c*] ← 3"),
    (1, "**end for**"),
    (1, "**return** (*current* + 1) **mod** *N*   ▷ fallback"),
    (0, "**end procedure**"),
]))

A(figure("fig_sense_flow.png",
         "Fig. 5.  Sense-before-hop channel selection (Algorithm 1). A "
         "candidate is refused either because it is still cooling down "
         "or because its measured level exceeds \u039b."))

A(algorithm("Algorithm 3  Adaptive transmit cycle", [
    (0, "**procedure** TransmitCycle"),
    (1, "**for** *c* = 0 **to** *N* \u2212 1 **do**"),
    (2, "cooldown[*c*] \u2190 max(cooldown[*c*] \u2212 1, 0)"),
    (1, "**end for**"),
    (1, "*next* \u2190 SelectNextHop(*current*)   "
        "\u25b7 Algorithm 1"),
    (1, "*payload* \u2190 \u201cSEQ:\u27e8*seq*\u27e9,"
        "NEXT:\u27e8*next*\u27e9\u201d"),
    (1, "transmit *payload* on *f*~current~"),
    (1, "*seq* \u2190 (*seq* + 1) **mod** *M*"),
    (1, "*current* \u2190 *next*"),
    (1, "wait *T*~p~ = 700 ms   ▷ cadence *T*~i~ ≈ 1.2 s"),
    (0, "**end procedure**"),
]))

# ----------------------------- IV -----------------------------------
A(h1("IV. Experimental Method"))

A(h2("A. Emulated Channel Denial"))
A(body(
    "No interference is transmitted at any point in this work. Channel "
    "denial is emulated in firmware, for three reasons: operating an "
    "interference source requires authorisation this project does not "
    "hold; a third radio would be needed and only two are available; and "
    "emulation is exactly repeatable, so runs are genuinely comparable.",
    first=True))

A(body(
    "A bitmask marks channels as denied. At the receiver, a packet "
    "arriving while tuned to a denied channel is discarded on arrival, "
    "taking its NEXT field with it, which reproduces what an unusable "
    "channel actually costs. At the adaptive transmitter, a denied "
    "channel returns a synthetic −35 dBm when sensed, so the "
    "avoidance logic responds as it would to a genuinely occupied one."))

A(body(
    "The scope of this choice bounds what the results support. "
    "Emulation validates the decision and recovery logic under channel "
    "denial. It does not validate the RF sensing front end against a "
    "real interferer: the only runs in which every sensing reading comes "
    "from the radio are those with no denied channels, and run 7 is "
    "therefore the sole source of the false-alarm statistic in "
    "Section V-F."))

A(h2("B. Experiment Matrix and Metrics"))
A(body(
    "Nine configurations were measured, listed in Table IV. Each sends "
    "exactly *M* = 100 numbered packets. The matrix is driven by a "
    "single host script that compiles each sketch with the appropriate "
    "flags, uploads to the correct serial port, resets the receiver, "
    "starts the transmitter, captures both serial streams onto one "
    "timeline and parses the receiver's summary. Manual intervention is "
    "eliminated, so a run can be repeated exactly.", first=True))

A(table(
    "IV",
    "Experiment Matrix",
    ["Run", "Link design", "Recovery", "Denied", "Purpose"],
    [["1", "Fixed", "—", "0", "Control"],
     ["2", "Fixed", "—", "1", "Motivating failure"],
     ["3", "Basic FHSS", "off", "0", "Hopping baseline"],
     ["4", "Basic FHSS", "off", "1", "Sync-loss collapse"],
     ["5", "Basic FHSS", "on", "1", "Recovery bounds loss"],
     ["6", "Basic FHSS", "on", "2", "Scaling with denial"],
     ["7", "Adaptive", "on", "0", "Genuine RSSI sensing"],
     ["8", "Adaptive", "on", "1", "Avoidance"],
     ["9", "Adaptive", "on", "2", "Avoidance, two channels"]],
    [420, 1180, 780, 640, 2020],
    ["center", "left", "center", "center", "left"],
    note="Channel 2 is denied for one; channels 2 and 4 for two. The "
         "rendezvous channel is channel 0 throughout."))

A(body("The primary metric is packet loss,"))
A(equation("*L* = (1 − *R*/*M*) × 100 %,", 16))
A(body(
    "where *R* is the number of **unique** sequence numbers accepted. "
    "Reception is recorded in a Boolean array indexed by sequence number "
    "and bounds-checked, so a duplicate cannot inflate the count. A "
    "second quantity, *denied drops*, counts packets heard and then "
    "discarded because the receiver was tuned to a denied channel; these "
    "are a subset of losses in which the frame was physically received."))

A(body("The complementary ratio is the packet delivery ratio,"))
A(equation("PDR = *R* / *M* = 1 − *L*/100,", 17))
A(body(
    "so run 8, with *R* = 98 of *M* = 100, gives PDR = 0.98."))

A(body(
    "One accounting detail is worth stating, because the counts do not "
    "look self-consistent otherwise. Run 2 records 101 denied drops "
    "against 100 packets sent. The drop counter counts frames physically "
    "received and then discarded, and the capture logs show SEQ:0 "
    "transmitted twice at the start of a run, because opening the serial "
    "port restarts the transmitter after it has already begun. The 101 "
    "discarded frames therefore carry 100 distinct sequence numbers. "
    "Delivery is counted on distinct sequence numbers throughout, so the "
    "duplicate affects no reported loss figure."))

A(body(
    "Operation in 433.05–434.79 MHz is licence-exempt in India under the "
    "2022 Rules [@gsr22], which permit 10 mW effective radiated power at "
    "up to a 10 % duty cycle. A frame of *L*~f~ = 22 bytes occupies"))
A(equation("*T*~on~ = 8*L*~f~ / *R*~b~ = 176 / 99.97 kb/s ≈ 1.8 ms,", 18))
A(body(
    "and at the measured inter-packet interval *T*~i~ = 1.200 s "
    "established in Section III-C, the duty cycle is"))
A(equation("*D* = *T*~on~ / *T*~i~ = 1.8 / 1200 ≈ 1.5 × 10⁻³ "
           "= 0.15 %,", 19))
A(body("roughly two orders of magnitude inside the limit."))

# ----------------------------- V ------------------------------------
A(h1("V. Results and Discussion"))

A(body(
    "Table V gives the complete measured matrix and Fig. 6 plots loss "
    "against the number of denied channels. Table VI gives the "
    "per-channel distribution, which is the most diagnostic output. All "
    "values are from single runs of 100 packets.", first=True))

A(table(
    "V",
    "Measured Results, Nine Configurations",
    ["Run", "Design", "Rec.", "Den.", "*R*", "*L* (%)", "Drops",
     "Resync"],
    [["1", "Fixed", "—", "0", "100", "0.00", "0", "0"],
     ["2", "Fixed", "—", "1", "0", "100.00", "101", "0"],
     ["3", "Basic", "off", "0", "95", "5.00", "0", "0"],
     ["4", "Basic", "off", "1", "2", "98.00", "20", "0"],
     ["5", "Basic", "on", "1", "40", "60.00", "20", "47"],
     ["6", "Basic", "on", "2", "40", "60.00", "19", "47"],
     ["7", "Adaptive", "on", "0", "100", "0.00", "0", "1"],
     ["8", "Adaptive", "on", "1", "98", "2.00", "0", "2"],
     ["9", "Adaptive", "on", "2", "99", "1.00", "0", "2"]],
    [400, 900, 520, 480, 420, 640, 600, 680],
    ["center"] * 8,
    sz=15,
    note="Rec. = rendezvous recovery; Den. = denied channels; "
         "*R* = unique packets received; Drops = denied drops."))

A(figure("fig4_loss_vs_denial.png",
         "Fig. 6.  Packet loss against the number of denied channels. "
         "The fixed link and the basic hopping link without recovery "
         "both collapse at a single denied channel; the adaptive link "
         "does not."))

A(h2("A. Baselines"))
A(body(
    "Run 1 delivered 100 of 100 packets on a fixed channel, "
    "establishing that the link, the wiring and the radio configuration "
    "are sound. Run 2 denied that one channel and delivered none: 100 % "
    "loss, with 101 denied drops confirming that the energy was arriving "
    "and being deliberately discarded. This pair is the motivation for "
    "the project in two numbers.", first=True))

A(body(
    "Run 3, basic hopping with nothing denied, delivered 95 of 100 with "
    "an almost perfectly even distribution of 19 packets on each of the "
    "five channels, confirming the hop schedule cycles as intended. The "
    "5 % loss relative to the fixed baseline is the cost of hopping "
    "itself: retuning takes time and every hop is an opportunity to lose "
    "synchronisation."))

A(h2("B. Collapse of In-Band Scheduling"))
A(body(
    "Run 4 is the central negative result. One channel of five was "
    "denied and recovery was disabled. A per-channel argument predicts "
    "20 % loss. The measured loss was **98 %**. Defining the "
    "amplification of a partial-band denial as the ratio of measured to "
    "predicted loss,", first=True))
A(equation("*A* = *L*~meas~ / *L*~naive~ = 98 / 20 \u2248 4.9.", 20))

A(body(
    "The per-channel tally explains it exactly. The receiver accepted "
    "one packet on channel 0 and one on channel 1, followed the schedule "
    "onto channel 2, and lost the packet there together with its NEXT "
    "field. Stranded on channel 2, it then heard the transmitter only on "
    "that channel, once every five packets:"))
A(equation("2 accepted + 20 discarded + 78 unheard = 100.", 21))
A(body(
    "The denial itself cost 20 packets; loss of synchronisation cost the "
    "other 78. With the hop schedule embedded in the data, the dominant "
    "damage mechanism is not the denied channel but the "
    "desynchronisation it triggers."))

A(h2("C. Recovery and the Saturation Effect"))
A(body(
    "Runs 5 and 6 enable cyclic recovery. Run 5, with one channel "
    "denied, lost 60 % instead of 98 %. Run 6, with *two* channels "
    "denied, lost 60 % as well — the same figure to two decimal "
    "places, with identical per-channel tallies and the same 47 "
    "resynchronisation events.", first=True))

A(body(
    "This is not measurement noise. The receiver, having recovered to "
    "rendezvous channel 0, walks forward through the schedule until it "
    "meets the *first* denied channel, where it is stranded again and "
    "the timer returns it to rendezvous. It never reaches any channel "
    "beyond the first denied one, so denying channel 4 as well changed "
    "nothing."))

A(body(
    "Let *d* be the number of hops from the rendezvous channel to the "
    "first denied channel in schedule order. Per recovery cycle the "
    "receiver delivers *d* packets out of *N*. Without recovery it "
    "delivers *d* packets in total and then stops; with recovery it "
    "repeats once per cycle. Hence"))
A(equation("*R*~no rec~ = *d*,     *R*~rec~ ≈ *d* · *M*/*N*.", 22))
A(body(
    "Neither expression contains the number of denied channels *K*. The "
    "model therefore predicts saturation outright,"))
A(equation("\u2202*R*~rec~ / \u2202*K* = 0   for   *K* \u2265 1,", 23))
A(body(
    "because the receiver never survives past the first denied channel "
    "and so never reaches the second. Runs 5 and 6 differ only in *K*, "
    "and both delivered 40 packets."))

A(body(
    "The second expression follows from counting cycles. Over *M* "
    "packets the transmitter completes"))
A(equation("*n*~c~ = ⌊*M* / *N*⌋ = ⌊100 / 5⌋ = 20", 24))
A(body(
    "cycles, and each one delivers the *d* packets that precede the "
    "denied channel, giving *R*~rec~ = *d* · *n*~c~ = 2 × 20 = 40. "
    "Treating the denied channel as equally likely to be any of the "
    "*N* − 1 non-rendezvous channels makes *d* uniform on "
    "{1, …, *N* − 1}, so that E[*d*] = *N*/2 and"))
A(equation("E[*R*~rec~] = (*N*/2)(*M*/*N*) = *M*/2 = 50.", 25))
A(body(
    "Half the stream is lost on average, independently of how many "
    "channels the link hops over. Widening the hop set does not help, "
    "because it lengthens the cycle in exactly the proportion it "
    "increases the number of channels reached before the bad one. This "
    "is a prediction of the model rather than a measurement: only "
    "*d* = 2 was tested, and Section VI lists varying *d* as the "
    "experiment that would confirm it."))
A(body(
    "With rendezvous at channel 0 and the first denied channel at "
    "index 2, *d* = 2, *N* = 5 and *M* = 100. The model predicts 2 "
    "delivered packets for run 4, 40 for run 5 and 40 for run 6. The "
    "measured values are 2, 40 and 40. All three are reproduced exactly, "
    "which is strong evidence that the mechanism has been correctly "
    "identified rather than merely described."))

A(body(
    "The practical consequence is worth stating: under in-band "
    "scheduling with cyclic recovery, link quality is governed by "
    "*where* the first unusable channel sits relative to the rendezvous "
    "point, not by *how many* channels are unusable. Adding channels to "
    "the hop set does not help if the obstruction is early in the order. "
    "Avoidance, not recovery, is what addresses this."))

A(table(
    "VI",
    "Per-Channel Packets Received",
    ["Run", "Design", "CH0", "CH1", "CH2", "CH3", "CH4", "Total"],
    [["3", "Basic, 0 denied", "19", "19", "19", "19", "19", "95"],
     ["4", "Basic, 1 denied", "1", "1", "0*", "0", "0", "2"],
     ["5", "Basic + rec., 1 den.", "20", "20", "0*", "0", "0", "40"],
     ["6", "Basic + rec., 2 den.", "20", "20", "0*", "0", "0*", "40"],
     ["7", "Adaptive, 0 denied", "20", "20", "20", "20", "20", "100"],
     ["8", "Adaptive, 1 denied", "25", "25", "0*", "24", "24", "98"],
     ["9", "Adaptive, 2 denied", "34", "33", "0*", "32", "0*", "99"]],
    [360, 1380, 440, 440, 440, 440, 440, 520],
    ["center", "left", "center", "center", "center", "center", "center",
     "center"],
    sz=15,
    note="An asterisk marks a denied channel."))

A(figure("fig5_per_channel.png",
         "Fig. 7.  Per-channel packet distribution. (b) With recovery "
         "and one denied channel the receiver never advances past "
         "channel 2, which is why denying a second changes nothing. "
         "(c), (d) The adaptive transmitter redistributes traffic onto "
         "the remaining channels."))

A(h2("D. Adaptive Avoidance"))
A(body(
    "Runs 7 to 9 use the sense-before-hop transmitter. With nothing "
    "denied it delivered 100 of 100. With one channel denied it "
    "delivered 98, a loss of 2 %. With two denied it delivered 99.",
    first=True))

A(body(
    "The per-channel tallies in Table VI show the mechanism working "
    "directly. In run 8 the denied channel 2 received exactly zero "
    "packets while the other four carried 25, 25, 24 and 24 — the "
    "traffic was redistributed, not merely lost. In run 9 the two denied "
    "channels carried zero and the three remaining channels carried 34, "
    "33 and 32. The transmitter avoided the unusable channels in advance "
    "instead of discovering them by failure."))

A(body(
    "Run 9 showing marginally lower loss than run 8 should not be read "
    "as a trend; a difference of one packet in a hundred from single "
    "runs is well inside the expected variation. Both are properly "
    "described as near-complete avoidance, and the responsible summary "
    "is that for a single denied channel, loss falls from 98 % under "
    "basic hopping to 2 % under adaptive avoidance."))

A(h2("E. A Channel-Plan Error Found by Measurement"))
A(body(
    "The first version of the design used 200 kHz channel spacing with "
    "an 812.50 kHz receive bandwidth. A 195 kHz transmission in a "
    "200 kHz grid very nearly touches its neighbours, and a "
    "±406 kHz passband is *wider than the entire 800 kHz hop "
    "span*, so a receiver parked on any single channel still hears most "
    "of the others.", first=True))

A(body(
    "This was caught by an anomaly in the data rather than predicted. "
    "Under that configuration a stranded receiver was observed picking "
    "up roughly half of all transmissions, which is impossible if the "
    "channels are isolated. Widening the spacing to 400 kHz and "
    "narrowing the filter to 270.83 kHz produced the geometry of (3) and "
    "the clean, mutually exclusive per-channel tallies of Table VI. The "
    "episode illustrates that a spread-spectrum design can appear to "
    "work while delivering none of the isolation it claims."))

A(h2("F. Noise Floor and False-Alarm Rate"))
A(body(
    "Run 7 is the only run in which every sensing reading comes from the "
    "radio rather than from emulation. Across 101 genuine channel "
    "assessments the measured level was −105.3 ± 1.6 dBm, "
    "ranging from −109 to −101 dBm, with per-channel means "
    "between −106.3 and −104.3 dBm (Fig. 8). None of the 101 "
    "readings reached the −75 dBm threshold, giving a measured "
    "false-alarm rate of 0/101 with the threshold roughly 30 dB above "
    "the floor.", first=True))

A(body(
    "Comparing the measured floor with the thermal prediction of (8) "
    "gives the combined noise figure and implementation loss of the "
    "receive chain,"))
A(equation("*F* = *P*~meas~ − *P*~n~ = −105.3 − (−119.7) = 14.4 dB,", 26))
A(body(
    "which is unremarkable for a low-cost integrated transceiver. The "
    "threshold sits far above the floor; expressed in standard "
    "deviations of the measured distribution the margin is"))
A(equation("(Λ − *μ*) / *σ* = (−75 + 105.3) / 1.6 ≈ 18.9 *σ*.", 27))
A(body(
    "No false alarm was therefore expected and none occurred. With zero "
    "events in *n* = 101 trials the rule of three places a 95 % upper "
    "confidence bound on the false-alarm probability at"))
A(equation("*P*~fa~ < 3 / *n* = 3 / 101 ≈ 0.030,", 28))
A(body(
    "so the measurement bounds the false-alarm rate below about 3 %; it "
    "does not establish that it is zero."))

A(figure("fig6_noise_floor.png",
         "Fig. 8.  Measured noise floor from run 7. (a) Distribution of "
         "all 101 assessments against the −75 dBm threshold. "
         "(b) Per-channel mean and standard deviation; the five channels "
         "agree to within 2 dB."))

A(body(
    "This establishes that the threshold does not fire on the ambient "
    "laboratory environment. It says nothing about the detection rate "
    "against a real interferer, which emulation cannot measure."))

A(body(
    "Sensing costs about 5 ms per packet with no denial, rising to "
    "roughly 8.5 ms with two denied channels, because a cooldown "
    "suppresses repeated testing of a channel already known to be bad. "
    "The end-to-end packet cadence was 1.215 s for basic hopping and "
    "1.221 s for adaptive, a difference well inside the variation of the "
    "serial logging that dominates both."))

A(h2("G. Ground-Station Dashboard"))
A(body(
    "A host-side dashboard reads both serial streams and serves a live "
    "view over HTTP. It renders the five-channel map with the current "
    "transmit and receive channels, per-channel reception counts and "
    "sensed levels, running delivery and loss statistics, a rolling loss "
    "trace and an event feed. Two controls are interactive: clicking a "
    "channel denies or releases it at run time, and a mode toggle pins "
    "the transmitter to a single channel so the fixed-frequency failure "
    "can be shown beside the hopping link without reflashing. Nothing in "
    "the dashboard transmits interference.", first=True))

A(fig_placeholder(
    "[INSERT DASHBOARD SCREENSHOT HERE]",
    "Fig. 9.  Live ground-station dashboard during a run with one "
    "channel denied by operator action.",
    "Capture the browser window at http://localhost:8080 while the "
    "demonstration firmware is running and one channel has been denied. "
    "Make sure the channel map, the statistics and the event feed are "
    "visible. Save at 300 dpi or greater."))

A(fig_placeholder(
    "[INSERT HARDWARE PHOTOGRAPH HERE]",
    "Fig. 10.  The two-node prototype: ESP32 DevKit v1 and CC1101 "
    "transceiver per node.",
    "Photograph both assembled nodes side by side on a plain background, "
    "with the wiring and antennas clearly visible. IEEE requires "
    "photographs at 300 dpi minimum."))

# ----------------------------- VI -----------------------------------
A(h1("VI. Limitations"))

A(body(
    "The following bound what the results support, and are stated here "
    "rather than left to be discovered.", first=True))

A(listed("1)",
         "*Denial is emulated in firmware, not transmitted.* This "
         "validates decision and recovery logic. It does not validate "
         "the RF sensing front end against a real interferer."))
A(listed("2)",
         "*The delivery model is validated at a single operating "
         "point.* All three counts reproduced by (22) come from the "
         "same hop set, the same rendezvous channel and the same "
         "distance *d* = 2. That delivery scales with *d* and is "
         "independent of *K* follows from the mechanism and is "
         "consistent with three measurements, but it is not a swept "
         "parameter. Denying channel 1 (*d* = 1) and channel 3 "
         "(*d* = 3) and comparing against the prediction is the "
         "single experiment that would most strengthen this work, "
         "and it requires no additional hardware."))
A(listed("3)",
         "*Single trials.* Every entry in Table V is one run of 100 "
         "packets; no variance is reported. Differences of one or two "
         "packets between runs carry no weight."))
A(listed("4)",
         "*A five-channel hop set is small.* Operational systems use "
         "tens of channels. With five, denying two removes 40 % of the "
         "spectrum."))
A(listed("5)",
         "*The hop order is fixed and predictable,* and the rendezvous "
         "channel is a single point of failure. Deriving the sequence "
         "from a shared secret, as in [@atheeq24], and rotating the rendezvous "
         "channel are the natural next steps."))
A(listed("6)",
         "*The channel plan overruns the band edge.* With the occupied "
         "bandwidth of (1), five channels at 400 kHz spacing require "
         "4(400) + 195 = 1795 kHz, whereas 433.05\u2013434.79 MHz "
         "provides 1740 kHz. The plan does not fit the band at any "
         "placement, and as placed the lower skirt of channel 0 extends "
         "about 97.5 kHz below the lower edge. A compliant five-channel "
         "plan at this bandwidth needs a spacing of at most 386 kHz. "
         "This was found in review, after the measurements were taken; "
         "it does not affect the protocol results, which concern "
         "scheduling rather than emission, but the regulatory claim in "
         "Section IV should be read as conducted power only. Relatedly, "
         "+10 dBm at the transmitter output is a conducted figure: "
         "effective radiated power depends on antenna gain and feed "
         "loss, neither of which was measured."))
A(listed("7)",
         "*Benchtop conditions,* and no claim against wideband denial. "
         "Frequency hopping helps when interference affects part of the "
         "hop set; against energy covering the whole band it has nowhere "
         "to go."))

# ----------------------------- VII ----------------------------------
A(h1("VII. Conclusion"))

A(body(
    "A complete adaptive frequency-hopping telemetry link was built from "
    "two ESP32 microcontrollers and two CC1101 transceivers and measured "
    "across nine configurations under firmware-emulated channel denial, "
    "with no interference transmitted at any point.", first=True))

A(body(
    "Carrying the hop schedule inside the data packets is economical but "
    "fails abruptly: one denied channel of five produced 98 % loss "
    "rather than the 20 % a per-channel argument suggests, because 78 of "
    "the 100 packets were lost to desynchronisation rather than to "
    "denial. Adding cyclic recovery bounds the damage but makes it "
    "saturate at a value set by the distance from the rendezvous channel "
    "to the first denied channel, not by the number of channels denied; "
    "a model built on that single parameter reproduced the measured "
    "delivery counts of 2, 40 and 40 exactly. Transmitter-side "
    "clear-channel assessment removed the failure mode rather than "
    "bounding it, reducing loss for a single denied channel from 98 % to "
    "2 %, with zero false alarms across 101 genuine assessments against "
    "a measured floor of −105.3 ± 1.6 dBm."))

A(body(
    "A design error found only by measurement is reported alongside "
    "these results: a receive bandwidth wider than the whole hop span, "
    "which left the channels non-independent while the link appeared to "
    "function."))

A(body(
    "Future work falls into three parts: validation against a real "
    "interference source in a conducted, shielded setup; a hop sequence "
    "derived from a shared secret, with a rotating rendezvous channel; "
    "and carrying real MAVLink telemetry in the position a commercial "
    "telemetry radio occupies between flight controller and ground "
    "station."))

A(h1("Acknowledgment"))
A(body(
    "The authors thank Velmurugan T. for supervision and guidance "
    "throughout the project, and the School of Electronics Engineering, "
    "Vellore Institute of Technology, for laboratory access.",
    first=True))

# ----------------------------- refs ---------------------------------
A(para(run("References"), style="ReferenceHead"))

for i, r in enumerate(REFS, 1):
    A(reference(i, r))

# final section properties: two columns
SECT2 = ('<w:sectPr><w:footnotePr><w:numRestart w:val="eachSect"/>'
         '</w:footnotePr><w:type w:val="continuous"/>'
         '<w:pgSz w:w="12240" w:h="15840"/>'
         '<w:pgMar w:top="1008" w:right="936" w:bottom="1008" w:left="936" '
         'w:header="432" w:footer="432" w:gutter="0"/>'
         '<w:pgNumType w:start="1"/>'
         '<w:cols w:num="2" w:space="720" w:equalWidth="0">'
         '<w:col w:w="5040" w:space="288"/><w:col w:w="5040" w:space="0"/>'
         '</w:cols></w:sectPr>')


# =====================================================================
#                              BUILD
# =====================================================================

def main():
    if not os.path.exists(TEMPLATE):
        raise SystemExit(f"template not found: {TEMPLATE}")

    if os.path.isdir(BUILD):
        shutil.rmtree(BUILD)
    os.makedirs(BUILD)
    with zipfile.ZipFile(TEMPLATE) as z:
        z.extractall(BUILD)

    docpath = os.path.join(BUILD, "word", "document.xml")
    original = open(docpath, encoding="utf-8").read()
    head = original[:original.index("<w:body>") + len("<w:body>")]

    xml = head + "".join(DOC) + SECT2 + "</w:body></w:document>"
    with open(docpath, "w", encoding="utf-8") as fh:
        fh.write(xml)

    # copy figures in and register them
    media = os.path.join(BUILD, "word", "media")
    os.makedirs(media, exist_ok=True)
    relpath = os.path.join(BUILD, "word", "_rels", "document.xml.rels")
    rels = open(relpath, encoding="utf-8").read()
    add = []
    for rid, fname in _rels:
        shutil.copy(os.path.join(FIGDIR, fname),
                    os.path.join(media, fname))
        add.append(
            f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats'
            f'.org/officeDocument/2006/relationships/image" '
            f'Target="media/{fname}"/>')
    rels = rels.replace("</Relationships>", "".join(add) + "</Relationships>")
    with open(relpath, "w", encoding="utf-8") as fh:
        fh.write(rels)

    if os.path.exists(OUTDOC):
        os.remove(OUTDOC)
    with zipfile.ZipFile(OUTDOC, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(BUILD):
            for f in files:
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, BUILD).replace("\\", "/"))

    print("wrote", os.path.relpath(OUTDOC, ROOT))
    print(f"  {len(DOC)} blocks, {len(_rels)} embedded figures, "
          f"{len(REFS)} references")


if __name__ == "__main__":
    main()
