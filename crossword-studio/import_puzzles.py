#!/usr/bin/env python3
"""Import licensed PersianCrossword v3 JSON files into an independent clue/answer bank."""
import argparse
import hashlib
import json
from pathlib import Path
from generate import normalize

def extract(puzzle):
    grid = puzzle["grid"]
    if not grid or not all(isinstance(r,list) and len(r)==len(grid[0]) for r in grid):
        raise ValueError("invalid grid")
    rows, cols = len(grid), len(grid[0])
    clues = puzzle["clues"]
    for direction, group_type in (("horizontal","across"),("vertical","down")):
        groups = {}
        if direction == "horizontal":
            for r in range(rows):
                c=cols-1
                while c>=0:
                    if grid[r][c]=="":
                        c-=1;continue
                    letters=[]
                    while c>=0 and grid[r][c]!="":
                        letters.append(grid[r][c]);c-=1
                    if len(letters)>=2:
                        groups.setdefault(str(r+1),[]).append("".join(letters))
        else:
            for c in range(cols-1,-1,-1):
                r=0
                while r<rows:
                    if grid[r][c]=="":
                        r+=1;continue
                    letters=[]
                    while r<rows and grid[r][c]!="":
                        letters.append(grid[r][c]);r+=1
                    if len(letters)>=2:
                        groups.setdefault(str(cols-c),[]).append("".join(letters))
        for number, answers in groups.items():
            questions=clues.get(direction,{}).get(number,[])
            if len(questions)!=len(answers):
                raise ValueError(f"{direction}.{number} question count mismatch")
            for clue,answer in zip(questions,answers):
                if not isinstance(clue,str) or not clue.strip():
                    raise ValueError("missing clue")
                if not normalize(answer) or len(normalize(answer))!=len(answer):
                    raise ValueError("invalid answer letters")
                yield clue.strip(),normalize(answer),group_type

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("source",help="Directory containing licensed v3 JSON puzzles")
    parser.add_argument("--output",default="crossword-studio/imported-entries.json")
    args=parser.parse_args()
    source=Path(args.source)
    files=sorted(source.rglob("*.json")) if source.is_dir() else [source]
    items={};errors=[];valid=0
    for path in files:
        try:
            puzzle=json.loads(path.read_text(encoding="utf-8"))
            if puzzle.get("version")!=3:
                raise ValueError("not a version 3 puzzle")
            extracted=list(extract(puzzle))
            meta=puzzle.get("meta",{})
            valid+=1
            for clue,answer,direction in extracted:
                key=(clue,answer)
                entry=items.get(key)
                if entry is None:
                    digest=hashlib.sha256((clue+"\n"+answer).encode()).hexdigest()[:20]
                    entry={"id":f"import-{digest}","clue":clue,"answer":answer,
                           "category":"دسته‌بندی‌نشده","difficulty":meta.get("difficulty","unknown"),
                           "source":meta.get("newspaper","جدول انار"),
                           "license":"user-confirmed","reviewed":False,"occurrences":0,
                           "source_puzzle_ids":[]}
                    items[key]=entry
                entry["occurrences"]+=1
                puzzle_id=str(meta.get("id") or path.stem)
                if puzzle_id not in entry["source_puzzle_ids"]:
                    entry["source_puzzle_ids"].append(puzzle_id)
        except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
            errors.append({"file":str(path),"error":str(exc)})
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(list(items.values()),ensure_ascii=False,indent=2),encoding="utf-8")
    report={"files_scanned":len(files),"valid_puzzles":valid,"unique_entries":len(items),
            "errors":errors[:200]}
    output.with_suffix(".report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k!="errors"},ensure_ascii=False))
    if errors:print(f"{len(errors)} files skipped; see report")
if __name__=="__main__":main()
