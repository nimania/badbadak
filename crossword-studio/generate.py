#!/usr/bin/env python3
"""Persian crossword draft generator. Standard library only; no external puzzle data."""
import argparse
import json
import random
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent

def normalize(value):
    value = unicodedata.normalize("NFKC", str(value)).translate(str.maketrans({
        "ي": "ی", "ى": "ی", "ك": "ک", "ۀ": "ه", "ة": "ه",
        "أ": "ا", "إ": "ا", "آ": "آ"
    }))
    value = re.sub(r"[\u064b-\u065f\u0670\u200c\s\-]+", "", value)
    return "".join(ch for ch in value if ch.isalpha())

def load_entries(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data["entries"]
    result = []
    seen = set()
    for item in data:
        word = normalize(item.get("answer", ""))
        clue = str(item.get("clue", "")).strip()
        if not (2 <= len(word) <= 30 and clue) or (clue, word) in seen:
            continue
        seen.add((clue, word))
        result.append({**item, "word": word, "clue": clue})
    return result

def can_place(grid, word, row, col, dr, dc):
    n = len(grid)
    before = (row-dr, col-dc)
    after = (row+len(word)*dr, col+len(word)*dc)
    for rr, cc in (before, after):
        if 0 <= rr < n and 0 <= cc < n and grid[rr][cc]:
            return False
    touches = 0
    for i, letter in enumerate(word):
        r, c = row+i*dr, col+i*dc
        if not (0 <= r < n and 0 <= c < n):
            return False
        old = grid[r][c]
        if old:
            if old != letter:
                return False
            touches += 1
        else:
            neighbors = [(r-1,c),(r+1,c)] if dc else [(r,c-1),(r,c+1)]
            if any(0 <= y < n and 0 <= x < n and grid[y][x] for y,x in neighbors):
                return False
    return touches

def place(grid, word, row, col, dr, dc):
    for i, letter in enumerate(word):
        grid[row+i*dr][col+i*dc] = letter

def generate(entries, size, seed):
    rng = random.Random(seed)
    grid = [["" for _ in range(size)] for _ in range(size)]
    candidates = [e for e in entries if 2 <= len(e["word"]) <= size]
    rng.shuffle(candidates)
    # Prefer longer initial crossing anchors, but retain variety.
    candidates.sort(key=lambda e: -len(e["word"]))
    placements = []
    used_answers = set()
    for entry in candidates:
        w = entry["word"]
        if w in used_answers:
            continue
        positions = []
        if not placements:
            # Persian horizontal words progress from right to left.
            positions = [(size//2, min(size-1, (size+len(w))//2), 0, -1)]
        else:
            for old in placements:
                # Prefer perpendicular intersections with existing words.
                odr, odc = old["dr"], old["dc"]
                dr, dc = (1, 0) if odc else (0, -1)
                for i, ch in enumerate(w):
                    for j, other in enumerate(old["word"]):
                        if ch != other:
                            continue
                        y = old["row"]+j*odr
                        x = old["col"]+j*odc
                        positions.append((y-i*dr, x-i*dc, dr, dc))
        rng.shuffle(positions)
        scored = []
        for y,x,dr,dc in positions:
            intersects = can_place(grid,w,y,x,dr,dc)
            if intersects is False:
                continue
            if placements and not intersects:
                continue
            # Higher crossing count; gently favor central placement.
            score = intersects*100 - abs(y-size//2)-abs(x-size//2)
            scored.append((score,y,x,dr,dc))
        if not scored:
            continue
        _,y,x,dr,dc = max(scored)
        place(grid,w,y,x,dr,dc)
        placements.append({**entry,"row":y,"col":x,"dr":dr,"dc":dc})
        used_answers.add(w)
    horizontal, vertical = {}, {}
    for p in placements:
        if p["dc"]:
            key = str(p["row"]+1)
            horizontal.setdefault(key, []).append(p)
        else:
            # Vertical group indexed from rightmost column.
            key = str(size-p["col"])
            vertical.setdefault(key, []).append(p)
    clues = {"horizontal":{}, "vertical":{}}
    for key, group in horizontal.items():
        group.sort(key=lambda p:-p["col"])
        clues["horizontal"][key] = [p["clue"] for p in group]
    for key, group in vertical.items():
        group.sort(key=lambda p:p["row"])
        clues["vertical"][key] = [p["clue"] for p in group]
    return {
        "version":3, "grid":grid, "clues":clues,
        "meta":{"title":f"جدول آزمایشی {size}×{size}", "size":{"rows":size,"cols":size},
                "language":"fa","direction":"rtl", "id":f"draft-{size}-{seed}"},
        "_draft":{"seed":seed,"placed":len(placements),"available":len(candidates),
                  "placements":[{"answer":p["word"],"clue":p["clue"],
                                 "row":p["row"],"col":p["col"],
                                 "direction":"across" if p["dc"] else "down"} for p in placements]}
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",default=str(HERE/"sample.json"))
    parser.add_argument("--size",type=int,default=15)
    parser.add_argument("--count",type=int,default=3)
    parser.add_argument("--seed",type=int,default=2026)
    args=parser.parse_args()
    if not 5 <= args.size <= 35:
        parser.error("size must be between 5 and 35")
    if not 1 <= args.count <= 100:
        parser.error("count must be between 1 and 100")
    entries=load_entries(args.input)
    out=HERE/"output"
    out.mkdir(parents=True,exist_ok=True)
    for i in range(args.count):
        puzzle=generate(entries,args.size,args.seed+i)
        path=out/f"draft-{args.size}-{args.seed+i}.json"
        path.write_text(json.dumps(puzzle,ensure_ascii=False,indent=2),encoding="utf-8")
        print(f"{path}: {puzzle['_draft']['placed']} entries")
if __name__=="__main__":
    main()
