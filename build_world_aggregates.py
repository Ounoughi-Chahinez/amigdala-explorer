#!/usr/bin/env python3
"""
Build compact world-aggregate files for the AMIGDALA dashboard.

For every model tag (each data_<tag>/flows/ tree already in the repo), precompute
exporter->world and importer->world totals for "All" and the 8 analytical groups,
so the dashboard can draw region/country-to-world-by-group views from ONE file
instead of thousands of per-pair fetches (which freeze the browser).

Output per tag:  trade_dashboard_worldagg_<tag>.json.gz
  { "exporter": { ISO3: { pkey: {"h":{y,v}, "c":{y,v}} } },
    "importer": { ISO3: { pkey: {"h":{y,v}, "c":{y,v}} } } }
  pkey in: "All", "grp_ag01".."grp_ag08"

Run it from the directory that holds the data_<tag>/ folders (the repo root):
    python3 build_world_aggregates.py
or point it somewhere:
    python3 build_world_aggregates.py /path/to/repo
"""
import os, sys, gzip, json, glob
from collections import defaultdict

# analytical groups — MUST match ANALYTICAL_GROUPS in index.html
def _c2(k): 
    try: return int(k[:2])
    except: return -1
GROUPS = {
    "grp_ag01": lambda k: k[:2] == "27",
    "grp_ag02": lambda k: 28 <= _c2(k) <= 40,
    "grp_ag03": lambda k: _c2(k) in (72, 73),          # Steel
    "grp_ag04": lambda k: k[:4] == "2523",
    "grp_ag05": lambda k: k[:2] == "70",
    "grp_ag06": lambda k: 47 <= _c2(k) <= 49,
    "grp_ag07": lambda k: k[:2] == "76" or k == "260600",
    "grp_ag08": lambda k: k[:2] == "74" or k == "260300",
}
PKEYS = ["All"] + list(GROUPS.keys())

def add_series(acc, s):
    """acc: dict year->value; s: {'y':[...],'v':[...]}"""
    if not s: return
    ys, vs = s.get("y") or [], s.get("v") or []
    for y, v in zip(ys, vs):
        acc[y] += v

def emit(acc):
    if not acc: return {"y": [], "v": []}
    ys = sorted(acc)
    return {"y": ys, "v": [int(round(acc[y])) for y in ys]}

def pair_pkey_series(pair, side_label):
    """Return {pkey: {'h':acc,'c':acc}} contributions from one pair file."""
    out = {pk: {"h": defaultdict(float), "c": defaultdict(float)} for pk in PKEYS}
    # All = pair total
    add_series(out["All"]["h"], pair.get("h"))
    add_series(out["All"]["c"], pair.get("c"))
    # groups = sum matching HS6 within pair.p
    p = pair.get("p") or {}
    for hs6, sv in p.items():
        for pk, test in GROUPS.items():
            if test(hs6):
                add_series(out[pk]["h"], (sv or {}).get("h"))
                add_series(out[pk]["c"], (sv or {}).get("c"))
    return out

def build_tag(flows_dir):
    # exporter[E][pkey] and importer[I][pkey] accumulators
    exp_acc = defaultdict(lambda: {pk: {"h": defaultdict(float), "c": defaultdict(float)} for pk in PKEYS})
    imp_acc = defaultdict(lambda: {pk: {"h": defaultdict(float), "c": defaultdict(float)} for pk in PKEYS})
    n = 0
    for exp_path in sorted(glob.glob(os.path.join(flows_dir, "*"))):
        if not os.path.isdir(exp_path): continue
        E = os.path.basename(exp_path)
        for fp in glob.glob(os.path.join(exp_path, "*.json.gz")):
            I = os.path.basename(fp)[:-len(".json.gz")]
            try:
                with gzip.open(fp, "rt", encoding="utf-8") as fh:
                    pair = json.load(fh)
            except Exception:
                continue
            contrib = pair_pkey_series(pair, None)
            for pk in PKEYS:
                for side in ("h", "c"):
                    ca = contrib[pk][side]
                    if ca:
                        te = exp_acc[E][pk][side]; ti = imp_acc[I][pk][side]
                        for y, v in ca.items():
                            te[y] += v; ti[y] += v
            n += 1
    def finalize(acc):
        return {c: {pk: {"h": emit(d[pk]["h"]), "c": emit(d[pk]["c"])} for pk in PKEYS} for c, d in acc.items()}
    return {"exporter": finalize(exp_acc), "importer": finalize(imp_acc)}, n

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    tags = []
    for d in sorted(glob.glob(os.path.join(root, "data_*"))):
        flows = os.path.join(d, "flows")
        if os.path.isdir(flows):
            tags.append((os.path.basename(d)[len("data_"):], flows))
    if not tags:
        print("No data_<tag>/flows/ directories found under", os.path.abspath(root)); return
    for tag, flows in tags:
        agg, n = build_tag(flows)
        out = os.path.join(root, f"trade_dashboard_worldagg_{tag}.json.gz")
        with gzip.open(out, "wt", encoding="utf-8", compresslevel=6) as fh:
            json.dump(agg, fh, separators=(",", ":"))
        sz = os.path.getsize(out) / 1e6
        print(f"  {tag:22s}: {n:>6} pairs -> {os.path.basename(out)}  ({sz:.2f} MB, "
              f"{len(agg['exporter'])} exporters, {len(agg['importer'])} importers)")
    print("done. upload the trade_dashboard_worldagg_*.json.gz files to the repo root.")

if __name__ == "__main__":
    main()
