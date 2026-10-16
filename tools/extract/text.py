"""Find a heading in a book's extracted pages and return the text under it.

Headings in the scans are their own short lines ("Spell Thief", "COLLEGE OF VALOR").
section() takes the paragraphs after the heading until the next heading it's told
about, a line in capitals, or a length limit.
"""
import difflib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ocr

_cache = {}


def lines(book, first, last):
    key = (book, first, last)
    if key not in _cache:
        out = []
        for p in range(first, last + 1):
            f = os.path.join(ROOT, "packs", ".text", book, "p%04d.txt" % p)
            if os.path.exists(f):
                for ln in open(f, encoding="utf-8").read().split("\n"):
                    s = ln.strip()
                    if not s or re.fullmatch(r"\d{1,3}", s) or re.match(r"^(CHAPTER \d|PART \d)", s, re.I):
                        continue
                    out.append((p, s))
        _cache[key] = out
    return _cache[key]


def norm(t):
    return re.sub(r"[^a-z]", "", t.lower().replace("1", "l").replace("0", "o"))


def is_heading(s, names):
    if re.match(r"^\s*\d{1,2}\s*(st|nd|rd|th)\b", s):  # a row of a level table ("10th Zealous Presence")
        return False
    n = norm(s)
    return bool(n) and len(s) <= 48 and any(n == norm(x) or difflib.SequenceMatcher(None, n, norm(x)).ratio() > 0.86 for x in names)


def run_in(s, names):
    """For a line like 'Darkvision. Accustomed to ...', the heading it starts with and the rest."""
    m = re.match(r"^([A-Z][^\W\d_]?[^\W\d_' :,-]*(?:[ '’:,-]+[^\W\d_]+){0,7})[.:]\s+(.*)$", s)
    if m and is_heading(m.group(1), names):
        return m.group(2)
    return None


def section(book, first, last, heading, stops=(), limit=2400, after=None):
    """Text under `heading`; `after` is a heading that should come first (the subclass title).
    Scanned columns sometimes put a feature above its title, so a heading that appears only
    once in the pages is also accepted from anywhere."""
    t = _section(book, first, last, heading, stops, limit, after)
    if t is None and after:
        ls = lines(book, first, last)
        hits = [i for i, (_, s) in enumerate(ls) if is_heading(s, [heading]) or run_in(s, [heading]) is not None]
        if len(hits) == 1:
            t = _section(book, first, last, heading, stops, limit, None)
    return t


def _section(book, first, last, heading, stops=(), limit=2400, after=None):
    ls = lines(book, first, last)
    start = 0
    if after:
        for i, (_, s) in enumerate(ls):
            if is_heading(s, [after]):
                start = i + 1
                break
    for i in range(start, len(ls)):
        rest = None
        if not is_heading(ls[i][1], [heading]):
            rest = run_in(ls[i][1], [heading])
            if rest is None:
                continue
        body = [rest] if rest else []
        for _, s in ls[i + 1:]:
            if is_heading(s, list(stops)) or run_in(s, list(stops)) is not None or (s.isupper() and len(s) > 4 and not re.search(r"\d", s)):
                break
            body.append(s)
            if sum(len(x) for x in body) > limit:
                break
        text = join(body)
        if len(text) > 40:  # a short hit is a table entry; keep looking for the real heading
            return ocr.clean(text).strip()
    return None


def join(body):
    out = ""
    for s in body:
        if out.endswith("-"):
            out = out[:-1] + s
        elif out and re.search(r"[.!?:]$", out) and s[:1].isupper():
            out += "\n\n" + s
        else:
            out = (out + " " + s).strip()
    return out
