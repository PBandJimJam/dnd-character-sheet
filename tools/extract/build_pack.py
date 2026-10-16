#!/usr/bin/env python3
"""Build packs/<book>.json from the book's extracted text.

Spells come from spells.py; feats, races, backgrounds and subclasses from the
book's definition file in tools/extract/books/<book>.py (structure and effects),
with their text looked up in the extracted pages. Book text stays in packs/,
which git ignores.

Usage: python3 tools/extract/build_pack.py <book>
"""
import importlib.util, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import spells as spellparser

BOOKS = {
    "phb": {"name": "Player's Handbook", "abbr": "PHB", "spells": (211, 291)},
    "xge": {"name": "Xanathar's Guide to Everything", "abbr": "XGE", "spells": (150, 172)},
    "tce": {"name": "Tasha's Cauldron of Everything", "abbr": "TCE", "spells": (104, 118)},
    "mpmm": {"name": "Mordenkainen Presents: Monsters of the Multiverse", "abbr": "MPMM"},
    "ftd": {"name": "Fizban's Treasury of Dragons", "abbr": "FTD", "spells": (19, 25)},
    "dmg": {"name": "Dungeon Master's Guide", "abbr": "DMG"},
}


def main(book):
    meta = BOOKS[book]
    pack = {"format": "dnd-content-pack", "schema": 2, "edition": "2014", "id": book, "name": meta["name"],
            "_about": "Built from your copy of the book by tools/extract/build_pack.py. Keep it out of the repo.",
            "source": {"abbr": meta["abbr"], "title": meta["name"]}}
    fixes = json.load(open(os.path.join(HERE, "fixes.json"))).get(book, {})
    if meta.get("spells"):
        sp, misses = spellparser.parse(book, *meta["spells"])
        for s in sp:
            s.update(fixes.get("spells", {}).get(s["id"], {}))
        pack["spells"] = sp
        print("spells: %d (%d names not matched: %s)" % (len(sp), len(misses), ", ".join(misses)))
    defs = os.path.join(HERE, "books", book + ".py")
    if os.path.exists(defs):
        spec = importlib.util.spec_from_file_location(book, defs)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        for k, v in mod.build().items():
            pack[k] = v
            print("%s: %d" % (k, len(v)))
    out = os.path.join(ROOT, "packs", book + ".json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=1, ensure_ascii=False)
    print("wrote", os.path.relpath(out, ROOT))


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in BOOKS:
        sys.exit(__doc__)
    main(sys.argv[1])
