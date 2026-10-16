#!/usr/bin/env python3
"""Turn a book's stat blocks (text from pdf_text.py) into content-pack creatures.

A stat block starts with a name in capitals, then "Size type, alignment", then
Armor Class. Ability scores come out of the scans interleaved with other lines, so
labels and values are read in order and paired. Traits, actions, reactions and
legendary actions are run-in entries ("Bite. Melee Weapon Attack: ...").

Usage: python3 tools/extract/creatures.py <book> <first page> <last page> > out.json
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocr

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIZES = "Tiny|Small|Medium|Large|Huge|Gargantuan"
TYPE_RE = re.compile(r"^\s*(%s)\b\s*(.*?)\s*,\s*(.*)$" % SIZES, re.I)
AC_RE = re.compile(r"^\s*Armor\s*C\s*l?\s*a?\s*s?\s*s?\s*(\d+)\s*(\(.*\))?", re.I)
FIELDS = [("hp", r"Hit\s*Points?"), ("speed", r"Speed"), ("saves", r"Saving\s*Throws?"), ("skills", r"Skills?"),
          ("vulnerabilities", r"Damage\s*Vulnerabilit\w*"), ("resistances", r"Damage\s*Resistances?"), ("immunities", r"Damage\s*Immunit\w*"),
          ("conditionImmunities", r"Condition\s*Immunit\w*"), ("senses", r"Senses?"), ("languages", r"Languages?"), ("cr", r"Challenge")]
FIELD_RE = [(k, re.compile(r"^\s*" + p + r"\b\s*(.*)$", re.I)) for k, p in FIELDS]
ABIL_LABEL = re.compile(r"^\s*(STR|DEX|CON|INT|WIS|CHA)\s*$")
ABIL_VALUE = re.compile(r"^\s*(\d{1,2})\s*\(\s*[+\-−–]?\s*\d+\s*\)\s*$")
SECTION = {"ACTIONS": "actions", "REACTIONS": "reactions", "LEGENDARY ACTIONS": "legendary"}
SMALL = {"of", "the", "and", "in", "with", "a", "an", "to", "or", "on", "from"}


def slug(t):
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", t.lower().replace("'", "").replace("’", "")))


def capsy(s):
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 3 and sum(c.isupper() for c in letters) >= 0.8 * len(letters) and len(s) <= 50


def run_in(s):
    """'Multiattack. The dragon ...' -> ('Multiattack', 'The dragon ...')."""
    m = re.match(r"^([A-Z][A-Za-z'’]*(?:[ -][A-Za-z'’]+|\s*\([^)]{1,25}\)){0,6})\s*\.\s+(\S.*)$", s)
    if not m:
        return None
    words = re.sub(r"\([^)]*\)", "", m.group(1)).split()
    if not words or any(w[0].islower() and w.lower() not in SMALL for w in words):
        return None
    return m.group(1).strip(), m.group(2)


def join(body):
    out = ""
    for s in body:
        if out.endswith("-"):
            out = out[:-1] + s
        else:
            out = (out + " " + s).strip()
    return out


def section_name(s):
    t = re.sub(r"[^A-Z ]", "", s.upper()).strip()
    t = re.sub(r"\s+", " ", t)
    for k, v in SECTION.items():
        if t == k or t.replace(" ", "") == k.replace(" ", ""):
            return v
    return None


BREATH = {("acid", "evil"): "Black", ("lightning", "evil"): "Blue", ("poison", "evil"): "Green", ("fire", "evil"): "Red", ("cold", "evil"): "White",
          ("fire", "chaotic good"): "Brass", ("lightning", "good"): "Bronze", ("acid", "good"): "Copper", ("fire", "lawful good"): "Gold", ("cold", "good"): "Silver"}
AGE = {"gargantuan": "Ancient {} Dragon", "huge": "Adult {} Dragon", "large": "Young {} Dragon", "medium": "{} Dragon Wyrmling"}


def dragon_name(lines, i):
    tm = TYPE_RE.match(lines[i][1])
    if not tm or "dragon" not in tm.group(2).lower():
        return None
    block = " ".join(x for _, x in lines[i:i + 60]).lower()
    bm = re.search(r"\b(acid|lightning|poison|fire|cold)\s*breath", block)
    if not bm:
        return None
    al = tm.group(3).lower()
    for (dt, side), color in BREATH.items():
        if dt == bm.group(1) and side in al:
            return AGE[tm.group(1).lower()].format(color)
    return None


# Challenge ratings of creatures that share a heading with others, to tell them apart (facts only).
KNOWN_CR = {"Owl": "0", "Cat": "0", "Raven": "0", "Bat": "0", "Rat": "0", "Hawk": "0", "Frog": "0", "Lizard": "0", "Octopus": "0", "Weasel": "0", "Crab": "0",
            "Wolf": "1/4", "Mastiff": "1/8", "Pony": "1/8", "Riding Horse": "1/4", "Warhorse": "1/2", "Giant Owl": "1/4", "Brown Bear": "1", "Owlbear": "3", "Roc": "11",
            "Goblin": "1/4", "Goblin Boss": "1", "Zombie": "1/4", "Ogre Zombie": "2", "Gnoll": "1/2", "Gnoll Pack Lord": "2", "Lemure": "0", "Shrieker": "0", "Violet Fungus": "1/4",
            "Gas Spore": "1/2", "Hydra": "8", "Chimera": "6", "Mimic": "2", "Sahuagin": "1/2", "Sahuagin Baron": "5", "Sahuagin Priestess": "2", "Beholder": "13", "Spectator": "3",
            "Spider": "0", "Giant Spider": "1", "Phase Spider": "3", "Yeti": "3", "Abominable Yeti": "9", "Orc": "1/2", "Orc War Chief": "4", "Orc Eye of Gruumsh": "2", "Orog": "2",
            "Kobold": "1/8", "Winged Kobold": "1/4", "Hobgoblin": "1/2", "Hobgoblin Captain": "3", "Hobgoblin Warlord": "6", "Imp": "1", "Quasit": "1", "Dretch": "1/4", "Manes": "1/8",
            "Skeleton": "1/4", "Minotaur Skeleton": "2", "Warhorse Skeleton": "1/2", "Vampire": "13", "Vampire Spawn": "5", "Lich": "21", "Ghoul": "1", "Ghast": "2", "Kenku": "1/4",
            "Lizardfolk": "1/2", "Lizardfolk Shaman": "2", "Lizard King/Queen": "4", "Myconid Sprout": "0", "Myconid Adult": "1/2", "Myconid Sovereign": "2", "Bugbear": "1", "Bugbear Chief": "3"}


GROUPS = {"Beholder": ["Spectator", "Gas Spore", "Death Tyrant"], "Yeti": ["Abominable Yeti"], "Sahuagin": ["Sahuagin Baron", "Sahuagin Priestess"],
          "Orc": ["Orc War Chief", "Orc Eye of Gruumsh", "Orog"], "Goblin": ["Goblin Boss"], "Gnoll": ["Gnoll Pack Lord"], "Hobgoblin": ["Hobgoblin Captain", "Hobgoblin Warlord"],
          "Kobold": ["Winged Kobold"], "Zombie": ["Ogre Zombie"], "Skeleton": ["Minotaur Skeleton", "Warhorse Skeleton"], "Vampire": ["Vampire Spawn"], "Ghoul": ["Ghast"],
          "Lizardfolk": ["Lizardfolk Shaman", "Lizard King/Queen"], "Bugbear": ["Bugbear Chief"], "Spider": ["Giant Spider", "Phase Spider"]}


def self_named(lines, i, keys, canon, sq):
    """'The zombie can...': the canonical name the block's own text uses, if it's unambiguous."""
    block = " ".join(x for _, x in lines[i:i + 50]).lower()
    cr = re.search(r"challenge\s*([\d/]+)", block)
    words = {w for w in re.findall(r"\bthe ([a-z'-]+)", block)}
    hits = [n for n in canon if n.lower().split()[-1].rstrip("s") in words or n.lower() in block[:3000] and len(n) > 4 and " " + n.lower() + " " in " " + block + " "]
    hits = [h for h in hits if h.lower() in block or h.lower().split()[-1] in words]
    if len(hits) == 1:
        return hits[0]
    single = [h for h in hits if len(h.split()) == 1]
    if len(single) == 1 and cr:
        return "%s (CR %s)" % (single[0], cr.group(1)) if len(hits) > 1 else single[0]
    return None


def heading_name(lines, i, known):
    for k in range(i - 2, max(0, i - 80), -1):
        s = lines[k][1]
        if capsy(s) and len(s) < 30:
            nm = known(s) or known(re.sub(r"(E?S)\s*$", "", s.strip()))  # "GOBLINS" -> Goblin
            if nm:
                return nm
    return None


def parse(book, first, last):
    lines = []
    for p in range(first, last + 1):
        f = os.path.join(ROOT, "packs", ".text", book, "p%04d.txt" % p)
        if not os.path.exists(f):
            continue
        for ln in open(f, encoding="utf-8").read().split("\n"):
            s = ln.strip()
            if not s or re.fullmatch(r"\d{1,3}", s):
                continue
            lines.append((p, s))
    import difflib
    sq = lambda x: re.sub(r"[^a-z]", "", x.lower().replace("1", "l").replace("0", "o"))
    canon = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "creature-names.json")))  # names only
    keys = {sq(n): n for n in canon}
    def known_name(s):
        hit = difflib.get_close_matches(sq(s), list(keys), n=1, cutoff=0.78)
        return keys[hit[0]] if hit and len(s) <= 50 else None
    # A block is a type line ("Small humanoid (goblinoid), neutral evil") with Armor Class just below;
    # the name is the line above it, which scans garble or drop.
    starts, names, how = [], {}, {}
    for i in range(1, len(lines) - 2):
        # No type line (the zombie's block starts at Armor Class): treat the AC line as the start.
        if AC_RE.match(lines[i][1]) and not TYPE_RE.match(lines[i - 1][1]) and re.match(r"^\s*Hit\s*Points", lines[i + 1][1], re.I):
            nm = next((known_name(x) for _, x in lines[max(0, i - 3):i] if known_name(x)), None) or self_named(lines, i, keys, canon, sq)
            if nm:
                lines.insert(i, (lines[i][0], "Medium creature, unaligned"))  # placeholder type line
                starts.append(i - 1); names[i - 1] = nm; how[i - 1] = "inferred"
            continue
        if TYPE_RE.match(lines[i][1]) and len(lines[i][1]) < 80 and any(AC_RE.match(x) for _, x in lines[i + 1:i + 3]):
            cands = [lines[i - 1][1]] + ([lines[i - 2][1] + " " + lines[i - 1][1]] if i > 1 else [])
            nm = next((known_name(x) for x in cands if known_name(x)), None) or (lines[i - 1][1] if capsy(lines[i - 1][1]) and not TYPE_RE.match(lines[i - 1][1]) else None)
            src = "direct"
            if not nm:  # the name was lost: true dragons are named from size, breath and alignment; others from how the block refers to itself
                nm = dragon_name(lines, i); src = "dragon"
                if not nm:
                    nm = self_named(lines, i, keys, canon, sq) or heading_name(lines, i, known_name); src = "inferred"
            if nm:
                starts.append(i - 1); names[i - 1] = nm; how[i - 1] = src
    out = []
    for n, i in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else min(len(lines), i + 120)
        page, raw = lines[i]
        tm = TYPE_RE.match(lines[i + 1][1])
        c = {"id": None, "name": None, "size": tm.group(1).capitalize(), "type": ocr.clean(tm.group(2)).strip().capitalize() or "Creature",
             "alignment": ocr.clean(tm.group(3)).strip(), "page": page}
        name = names[i] if names[i] in canon or re.match(r".+ \(CR [\d/]+\)$", names[i]) else re.sub(r"\s+", " ", ocr.clean(raw.title())).replace("'S ", "'s ")
        words = name.split()
        if names[i] not in canon and "(CR" not in names[i] and sum(len(w) <= 2 for w in words) > len(words) / 3:  # letters split apart by the scan
            parts = ocr.segment(re.sub(r"[^a-z]", "", raw.lower()))
            name = " ".join(parts).title() if parts else name
        name = re.sub(r"\b(Of|The|And|In)\b", lambda m: m.group(1).lower(), name)
        c["name"], c["id"], c["_how"] = name, slug(name), how.get(i, "direct")
        labels, values, fields, cur, j = [], [], {}, None, i + 2
        # fields and abilities until the first trait/action entry after Challenge
        while j < end:
            s = lines[j][1]
            am = AC_RE.match(s)
            if am and "ac" not in c:
                c["ac"] = int(am.group(1)); c["acNote"] = (am.group(2) or "").strip("() "); cur = None; j += 1; continue
            labs = re.findall(r"\b(STR|DEX|CON|INT|WIS|CHA)\b", s)
            if labs and re.fullmatch(r"(\s*(STR|DEX|CON|INT|WIS|CHA)\b)+\s*", s):  # one label, or all six on a line
                labels += labs; cur = None; j += 1; continue
            vals = re.findall(r"(\d{1,2})\s*\(\s*[+\-−–]?\s*\d+\s*\)", s)
            if vals and re.fullmatch(r"(\s*\d{1,2}\s*\(\s*[+\-−–]?\s*\d+\s*\))+\s*", s):
                values += [int(v) for v in vals]; cur = None; j += 1; continue
            hit = next(((k, m) for k, rx in FIELD_RE for m in [rx.match(s)] if m), None)
            if hit:
                cur = hit[0]; fields[cur] = hit[1].group(1); j += 1; continue
            if "cr" in fields and (run_in(s) or section_name(s)):
                break
            if cur and cur != "cr":
                fields[cur] += " " + s; j += 1; continue
            if "cr" in fields:
                break
            j += 1
        skip = set()
        if len(values) < 6:  # the last scores can land after ACTIONS in column order
            for k in range(j, min(end, j + 14)):
                t = lines[k][1]
                if re.fullmatch(r"(\s*(STR|DEX|CON|INT|WIS|CHA)\b)+\s*", t):
                    labels += re.findall(r"\b(STR|DEX|CON|INT|WIS|CHA)\b", t); skip.add(k)
                elif re.fullmatch(r"(\s*\d{1,2}\s*\(\s*[+\-−–]?\s*\d+\s*\))+\s*", t):
                    values += [int(v) for v in re.findall(r"(\d{1,2})\s*\(", t)]; skip.add(k)
                if len(values) >= 6:
                    break
        if len(values) >= 6:
            order = labels if len(labels) == 6 and len(set(labels)) == 6 else ["STR", "DEX", "CON", "INT", "WIS", "CHA"]
            c["abilities"] = {k.lower(): v for k, v in zip(order, values[:6])}
        hp = re.match(r"\s*(\d+)\s*(\((.*)\))?", fields.get("hp", ""))
        if hp:
            c["hp"] = {"average": int(hp.group(1)), "dice": re.sub(r"\s+", " ", (hp.group(3) or "").replace("d1 0", "d10").replace("d1 2", "d12")).strip()}
        for k in ("speed", "saves", "skills", "vulnerabilities", "resistances", "immunities", "conditionImmunities", "senses", "languages"):
            if fields.get(k):
                c[k] = ocr.clean(re.sub(r"\s+", " ", fields[k])).replace(" ft .", " ft.").replace("ft.", " ft.").replace("  ", " ").strip(" .")
        crm = re.match(r"\s*([\d/]+)", fields.get("cr", "").replace("I", "1").replace("l", "1"))
        if crm:
            c["cr"] = crm.group(1)
        # traits, then sections
        sect, entries = "traits", {"traits": [], "actions": [], "reactions": [], "legendary": []}
        while j < end:
            s = lines[j][1]
            if j in skip:
                j += 1; continue
            sn = section_name(s)
            if sn:
                sect = sn; j += 1; continue
            ri = run_in(s)
            if ri:
                entries[sect].append([ri[0], [ri[1]]])
            elif entries[sect]:
                if capsy(s) and len(s) > 12:  # a lore heading: the block is over
                    break
                entries[sect][-1][1].append(s)
            elif sect == "legendary":
                pass  # the "can take 3 legendary actions" preamble
            j += 1
        for k, v in entries.items():
            if v:
                c[k] = [{"name": ocr.clean(nm), "text": ocr.clean(join(body)).replace("d1 0", "d10").replace("d1 2", "d12")} for nm, body in v]
        if "ac" in c and "hp" in c:
            c.pop("acNote", None) if not c.get("acNote") else None
            out.append(c)
    # A name has to agree with the creature's known challenge rating (scans put stray headings above blocks).
    for c in out:
        if c["name"] in KNOWN_CR and c.get("cr") != KNOWN_CR[c["name"]]:
            c["name"] = "%s (CR %s)" % (c["name"], c.get("cr", "?")); c["id"] = slug(c["name"]); c["_how"] = "inferred"
    # "(CR n)" names stand for a block whose own name was lost; resolve them within their family by CR.
    for c in out:
        m = re.match(r"^(.+) \(CR ([\d/]+)\)$", c["name"])
        if not m:
            continue
        taken = {x["name"] for x in out}
        fam = next((k for k, v in GROUPS.items() if m.group(1) == k or m.group(1) in v), m.group(1))
        group = [fam] + GROUPS.get(fam, [])
        hit = [g for g in group if KNOWN_CR.get(g) == m.group(2) and g not in taken]
        if len(hit) == 1:
            c["name"], c["id"] = hit[0], slug(hit[0])
        elif fam not in GROUPS:  # a stray heading, not a family: don't pretend to know what it is
            c["name"] = "Unidentified creature (CR %s, page %s)" % (m.group(2), c["page"]); c["id"] = slug(c["name"])
    canon_set = set(canon)
    dropped = [c["name"] for c in out if c["name"] not in canon_set and not re.match(r".+ \(CR [\d/]+(, page \d+)?\)$", c["name"])]
    out = [c for c in out if c["name"] not in dropped]
    if dropped:
        sys.stderr.write("names too garbled to keep: %s\n" % ", ".join(dropped))
    rank = {"direct": 0, "dragon": 1, "inferred": 2}
    best = {}
    for c in out:  # same name twice: the directly named block wins, then the fuller one
        b = best.get(c["id"])
        if not b or (rank[c["_how"]], -len(json.dumps(c))) < (rank[b["_how"]], -len(json.dumps(b))):
            best[c["id"]] = c
    for c in best.values():
        c.pop("_how", None)
    return list(best.values())


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    cs = parse(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
    json.dump(cs, sys.stdout, indent=1, ensure_ascii=False)
    sys.stderr.write("%d creatures\n" % len(cs))
