# irrpractice.py - dryland versus irrigated fields (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-IRR.md (marker corn-heat-tolerance-0.4.0-irrigation-prereg).
# Drought-tolerant (DT) corn was planted far more on dryland than on irrigated
# fields: USDA ERS (McFadden, Chart of Note 29 July 2019; 2016 ARMS) reports 60% of
# Nebraska's non-irrigated corn fields in DT varieties against nearly 31% of its
# irrigated fields. NASS published county yields separately for irrigated and
# non-irrigated corn and soybeans until the 2018 crop. Dryland and irrigated
# fields of one county share the same weather, the same year and the same
# market, so the within-county contrast removes far more than a contrast
# between states can. The primary test is
#     T = DiD(dryland) - DiD(irrigated),
#     DiD(p) = (EDD_C - EDD_B)corn,p - (EDD_C - EDD_B)soy,p,
# with B = 1981-2010 and C = 2011-2018, from one stacked regression of four blocks
# (corn/soy x dryland/irrigated) in the eastern parts of Nebraska and Kansas.
# Block labels reuse dtstate.ddd_fit: H = dryland (higher DT share), L = irrigated.
#
# Reuses the published cornheat_data / cornheat_model / run_cornheat / soyheat /
# dtstate modules unchanged (commit 6771a70f) and the weather tables cached on
# the same data volume.

import argparse
import csv
import json
import math
import os
import sys
import time

import cornheat_data as D
import dtstate as T
import run_cornheat as R
import soyheat as S

ERAS_IRR = [("B", 1981, 2010), ("C", 2011, 2018)]
PLACEBO_ERAS = [("B", 1981, 1995), ("C", 1996, 2010)]
LATE_ERAS = [("B", 1981, 2010), ("C", 2014, 2018)]
Y0, Y1 = 1981, 2018
POOL = ("20", "31")                       # Kansas, Nebraska (east of 100 W)
KEYS = (("corn", "dry"), ("corn", "irr"), ("soy", "dry"), ("soy", "irr"))
CROP_PREFIX = {"corn": "CORN, GRAIN, ", "soy": "SOYBEANS, "}
KIND_SUFFIX = {"yield": " - YIELD, MEASURED IN BU / ACRE", "area": " - ACRES HARVESTED"}
PRACTICE_TOKEN = {"NON-IRRIGATED": "dry", "IRRIGATED": "irr"}
LABELS = {"H": "dryland (NASS NON-IRRIGATED)", "L": "irrigated (NASS IRRIGATED)"}
ERS_NE_DT_2016_PCT = {"dryland": 60, "irrigated": 31}
log = R.log


# ------------------------------------------------------------------ NASS
def practice_of(short):
    """(crop, practice, kind) for the four pre-registered SHORT_DESC families,
    e.g. 'CORN, GRAIN, NON-IRRIGATED - YIELD, MEASURED IN BU / ACRE' ->
    ('corn', 'dry', 'yield'); None for anything else."""
    for crop, pre in CROP_PREFIX.items():
        if not short.startswith(pre):
            continue
        for kind, suf in KIND_SUFFIX.items():
            if short.endswith(suf):
                prac = PRACTICE_TOKEN.get(short[len(pre):len(short) - len(suf)])
                return (crop, prac, kind) if prac else None
    return None


def practice_filter(lines, seen=None):
    """County-level annual SURVEY rows (domain TOTAL) of the practice series.
    Yields dicts fips, year, crop ('corn:dry' ...), slot, value. If `seen` is a
    dict, it counts every county SURVEY SHORT_DESC of corn or soybeans that
    contains 'IRRIGATED' (diagnostics for the published file)."""
    it = iter(lines)
    hdr = [h.strip().strip('"').upper() for h in next(it).rstrip("\r\n").split("\t")]
    col = {h: i for i, h in enumerate(hdr)}
    for n in ("SOURCE_DESC", "AGG_LEVEL_DESC", "SHORT_DESC", "STATE_FIPS_CODE", "YEAR", "VALUE"):
        if n not in col:
            raise KeyError("NASS header lacks %s; header=%s" % (n, hdr))
    cty = col.get("COUNTY_ANSI", col.get("COUNTY_CODE"))
    if cty is None:
        raise KeyError("NASS header lacks COUNTY_ANSI/COUNTY_CODE")
    per = col.get("REFERENCE_PERIOD_DESC")
    dom = col.get("DOMAIN_DESC")
    for line in it:
        if "COUNTY" not in line or "IRRIGATED" not in line:
            continue
        if "CORN, GRAIN, " not in line and "SOYBEANS, " not in line:
            continue
        f = [x.strip().strip('"') for x in line.rstrip("\r\n").split("\t")]
        if len(f) < len(hdr):
            continue
        if f[col["AGG_LEVEL_DESC"]] != "COUNTY" or f[col["SOURCE_DESC"]] != "SURVEY":
            continue
        short = f[col["SHORT_DESC"]]
        if seen is not None and "IRRIGATED" in short:
            seen[short] = seen.get(short, 0) + 1
        key = practice_of(short)
        if key is None:
            continue
        if per is not None and f[per] != "YEAR":
            continue
        if dom is not None and f[dom] != "TOTAL":
            continue
        c = f[cty]
        s = f[col["STATE_FIPS_CODE"]]
        if not c.isdigit() or not s.isdigit() or int(c) >= 998:
            continue
        try:
            val = float(f[col["VALUE"]].replace(",", ""))
        except ValueError:
            continue
        yield {"fips": "%02d%03d" % (int(s), int(c)), "year": int(f[col["YEAR"]]),
               "crop": "%s:%s" % (key[0], key[1]), "slot": key[2], "value": val}


def stage_nass_practice(idir, out):
    path = os.path.join(idir, "nass_practice_county.tsv")
    if os.path.exists(path):
        log("nass-irr: cached", path)
        return path
    url = None
    for lu in D.NASS_LISTING_URLS:
        try:
            url = D.find_nass_crops_url(D.http_get(lu).decode("utf-8", errors="replace"))
            if url:
                break
        except Exception as e:
            log("nass-irr: listing failed", lu, e)
    if not url:
        raise SystemExit("nass-irr: no qs.crops file found on the listing page")
    log("nass-irr: streaming", url)
    seen = {}
    recs, conflicts = S.collect_nass(practice_filter(D.stream_nass(url), seen=seen))
    by_key, years = {}, {}
    for (k, f, y), c in recs.items():
        if "yield" in c:
            by_key[k] = by_key.get(k, 0) + 1
            years.setdefault(k, set()).add(y)
    meta = {"source_url": url, "county_years_with_yield": by_key,
            "year_range": {k: [min(v), max(v)] for k, v in years.items()},
            "duplicate_conflicts": conflicts,
            "irrigated_short_descs_seen": dict(sorted(seen.items(), key=lambda kv: -kv[1])[:60])}
    with open(os.path.join(out, "irr_nass_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    missing = ["%s:%s" % k for k in KEYS if not by_key.get("%s:%s" % k)]
    if missing:
        # Pre-registered stop: no model is fitted; the strings are corrected in a
        # labelled amendment before any weather-yield data are combined.
        raise SystemExit("nass-irr: no county yields for %s; see irr_nass_meta.json" % missing)
    tmp = "%s.irr%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("key\tfips\tyear\tyield_bu_ac\tarea_ac\n")
        for k in sorted(recs):
            c = recs[k]
            fh.write("%s\t%s\t%d\t%s\t%s\n" % (k[0], k[1], k[2], c.get("yield", ""), c.get("area", "")))
    os.replace(tmp, path)
    with open(os.path.join(idir, "irr_nass_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    log("nass-irr:", by_key, "conflicts", conflicts)
    return path


# ------------------------------------------------------------------ panels
def irrigated_shares(area, pool=POOL, eras=ERAS_IRR):
    """Irrigated share of harvested acres (counties in the sample) by crop and era."""
    out = {}
    for crop in ("corn", "soy"):
        out[crop] = {}
        for L, a, b in eras:
            irr = sum(v for (f, y), v in area[(crop, "irr")].items() if f[:2] in pool and a <= y <= b)
            dry = sum(v for (f, y), v in area[(crop, "dry")].items() if f[:2] in pool and a <= y <= b)
            out[crop][L] = round(irr / (irr + dry), 4) if irr + dry > 0 else None
    return out


def load_practice_panels(ddir, path, keep, y0=Y0, y1=Y1, pool=POOL):
    """rows[(crop, practice)] in the cornheat_model row format (plus crop and
    practice); weather arrays are shared between practices of a county-year."""
    import numpy as np
    ylds = {k: {} for k in KEYS}
    area = {k: {} for k in KEYS}
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            key, f, y, yl, ar = line.rstrip("\n").split("\t")
            k = tuple(key.split(":"))
            y = int(y)
            if k not in ylds or f not in keep or not (y0 <= y <= y1):
                continue
            if yl and float(yl) > 0:
                ylds[k][(f, y)] = float(yl)
            if ar and float(ar) > 0:
                area[k][(f, y)] = float(ar)
    want = set()
    for k in KEYS:
        want |= set(ylds[k])
    rows = {k: [] for k in KEYS}
    w_fips = set()
    for year in range(y0, y1 + 1):
        with open(os.path.join(ddir, "weather", "w_%d.csv" % year), encoding="utf-8") as fh:
            rd = csv.reader(fh)
            next(rd)
            tmp = {}
            for r in rd:
                f = r[0]
                w_fips.add(f)
                if (f, year) not in want:
                    continue
                if int(r[4]) != 0 or int(r[3]) != R.SEASON_DAYS[r[2]]:
                    continue
                tmp.setdefault(f, {})[r[2]] = (np.array([float(x) for x in r[6:]]), float(r[5]))
            for f, d in tmp.items():
                if set(d) != set(D.SEASONS):
                    continue
                dd = {s: d[s][0] for s in d}
                P = {s: d[s][1] for s in d}
                for k in KEYS:
                    v = ylds[k].get((f, year))
                    if v is not None:
                        rows[k].append({"fips": f, "state": f[:2], "year": year, "crop": k[0],
                                        "practice": k[1], "logy": math.log(v), "dd": dd, "P": P})
    census = {}
    for k in KEYS:
        nf = {f for (f, y) in ylds[k]}
        census["%s:%s" % k] = {
            "nass_county_years": len(ylds[k]), "nass_counties": len(nf),
            "nass_counties_with_weather_share": round(len(nf & w_fips) / max(1, len(nf)), 4),
            "panel_rows": len(rows[k]),
            "pool_years": sorted({y for (f, y) in ylds[k] if f[:2] in pool})}
    return rows, census, irrigated_shares(area, pool)


# ------------------------------------------------------------------ design
def era_label(year, eras):
    for L, a, b in eras:
        if a <= year <= b:
            return L
    return None


def paired(rows_a, rows_b, eras):
    """Keep only (county, era) cells present in both lists."""
    ka = {(r["fips"], era_label(r["year"], eras)) for r in rows_a}
    kb = {(r["fips"], era_label(r["year"], eras)) for r in rows_b}
    both = {k for k in ka & kb if k[1] is not None}
    return ([r for r in rows_a if (r["fips"], era_label(r["year"], eras)) in both],
            [r for r in rows_b if (r["fips"], era_label(r["year"], eras)) in both], both)


def is_dry(r):
    return r["practice"] == "dry"


def is_irr(r):
    return r["practice"] == "irr"


def prep(rows, eras, states=POOL, pair=True, drop_year=None):
    """Era filter (2/3 rule) per crop x practice, then (by default) keep only the
    county-eras in which both practices of that crop pass."""
    out, info = {}, {}
    for crop in ("corn", "soy"):
        sel = {}
        for prac in ("dry", "irr"):
            sel[prac] = R.era_filter([r for r in rows[(crop, prac)]
                                      if (states is None or r["state"] in states)
                                      and r["year"] != drop_year], eras)
        if pair:
            dry, irr, both = paired(sel["dry"], sel["irr"], eras)
        else:
            dry, irr = sel["dry"], sel["irr"]
            both = {(r["fips"], era_label(r["year"], eras)) for r in dry + irr}
        out[crop] = dry + irr
        info[crop] = {L: len({f for (f, l) in both if l == L}) for (L, _a, _b) in eras}
    info["states"] = sorted({r["state"] for r in out["corn"] + out["soy"]})
    return out["corn"], out["soy"], info


def fit_practice(rows, eras, states=POOL, pair=True, season="MarAug", drop_year=None, full=True):
    corn, soy, info = prep(rows, eras, states, pair, drop_year)
    res = T.ddd_fit(corn, soy, is_dry, is_irr, eras=eras, season=season, full=full)
    res["counties"] = info
    return res


def safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:      # reported analyses only; the primary fit is not wrapped
        return {"error": "%s: %s" % (type(e).__name__, e)}


# ------------------------------------------------------------------ grading
def irr_class(t_year, placebo_year):
    """Primary class. A significant T counts only if the pre-period placebo
    (1996-2010 vs 1981-1995) has year-clustered p >= 0.10."""
    if not (t_year["p"] == t_year["p"] and t_year["p"] < 0.05):
        return "no detectable difference"
    if placebo_year is None or not (placebo_year["p"] == placebo_year["p"]) or placebo_year["p"] < 0.10:
        return "not interpretable (placebo failed)"
    return "dryland corn gained" if t_year["diff"] > 0 else "dryland corn lost"


def grade_irr(res):
    """Pre-registered predictions I1-I6 and gates G1-G4 (PREREG-IRR.md)."""
    p = res["primary"]
    c = p["counties"]
    cf = p["coef"]
    pl_p = res["placebo"].get("T_year", {}).get("p", float("nan"))
    g = {
        "G1_paired_corn_eraC_counties_ge_40": c["corn"]["C"] >= 40,
        "G2_paired_soy_eraC_counties_ge_25": c["soy"]["C"] >= 25,
        "G3_paired_corn_eraB_counties_ge_40": c["corn"]["B"] >= 40,
        "G4_corn_practice_rows_every_year_2011_2018": res["coverage"]["corn_years_2011_2018_complete"],
        "I1_class": p["class"],
        "I1_holds_no_detectable_difference": p["class"] == "no detectable difference",
        "I2_holds_T_positive": p["T"] > 0,
        "I3_holds_dry_corn_more_heat_sensitive_B": cf["cornH:EDD_B"]["b"] < cf["cornL:EDD_B"]["b"],
        "I4_holds_dry_soy_more_heat_sensitive_B": cf["soyH:EDD_B"]["b"] < cf["soyL:EDD_B"]["b"],
        "I5_holds_irr_corn_under_half_of_dry_B":
            abs(cf["cornL:EDD_B"]["b"]) < 0.5 * abs(cf["cornH:EDD_B"]["b"]),
        "I6_holds_placebo_p_ge_0.10": pl_p == pl_p and pl_p >= 0.10,
    }
    g["predictions_held"] = sum(1 for k in ("I1_holds_no_detectable_difference", "I2_holds_T_positive",
                                            "I3_holds_dry_corn_more_heat_sensitive_B",
                                            "I4_holds_dry_soy_more_heat_sensitive_B",
                                            "I5_holds_irr_corn_under_half_of_dry_B",
                                            "I6_holds_placebo_p_ge_0.10") if g[k])
    return g


# ------------------------------------------------------------------ pipeline
def load_keep(ddir, max_wait_min, poll_s=300):
    """East sample from the shared gazetteer table; builds it if absent and waits
    if another job is still writing it."""
    gpath = os.path.join(ddir, "gazetteer_counties.tsv")
    t0 = time.time()
    while True:
        if not os.path.exists(gpath):
            R.stage_geo(ddir)
        try:
            geo = R.load_geo(gpath)
        except (ValueError, IndexError):
            geo = {}
        if len(geo) > 3000:
            return R.east_sample(geo)
        if time.time() - t0 > max_wait_min * 60:
            raise SystemExit("geo: gazetteer table incomplete after %d min" % max_wait_min)
        log("geo: gazetteer has %d counties (being written?); waiting" % len(geo))
        time.sleep(poll_s)


def stage_model_irr(ddir, path, out, keep):
    rows, census, shares = load_practice_panels(ddir, path, keep)
    log("panels:", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "pool_years"}
                               for k, v in census.items()}))
    res = {"census": census, "eras": ERAS_IRR, "placebo_eras": PLACEBO_ERAS,
           "thresholds": S.B_CROP, "pool_states": POOL, "labels": LABELS,
           "ers_nebraska_dt_2016_pct": ERS_NE_DT_2016_PCT, "irrigated_area_share": shares}
    res["coverage"] = {"corn_years_2011_2018_complete": all(
        y in census["corn:irr"]["pool_years"] and y in census["corn:dry"]["pool_years"]
        for y in range(2011, 2019))}

    prim = fit_practice(rows, ERAS_IRR)
    plac = safe(fit_practice, rows, PLACEBO_ERAS)
    prim["class"] = irr_class(prim["T_year"], plac.get("T_year"))
    res["primary"] = prim
    res["placebo"] = plac
    log("primary:", json.dumps({"T": prim["T"], "p_year": prim["T_year"]["p"],
                                "placebo_p_year": plac.get("T_year", {}).get("p"),
                                "class": prim["class"], "counties": prim["counties"]}, default=float))

    rob = {}
    rob["unpaired"] = safe(fit_practice, rows, ERAS_IRR, pair=False)
    rob["no2012"] = safe(fit_practice, rows, ERAS_IRR, drop_year=2012)
    rob["AprSep"] = safe(fit_practice, rows, ERAS_IRR, season="AprSep")
    rob["late_C_2014_2018"] = safe(fit_practice, rows, LATE_ERAS)
    rob["nebraska_only"] = safe(fit_practice, rows, ERAS_IRR, states=("31",))
    rob["kansas_only"] = safe(fit_practice, rows, ERAS_IRR, states=("20",))
    rob["all_states_east"] = safe(fit_practice, rows, ERAS_IRR, states=None)
    res["robustness"] = rob

    res["grades"] = grade_irr(res)
    with open(os.path.join(out, "irrpractice_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-wait-min", type=int, default=120)
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "cornheat")
    idir = os.path.join(ddir, "irr")
    os.makedirs(idir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    path = stage_nass_practice(idir, a.out_dir)
    keep = load_keep(ddir, a.max_wait_min)
    log("east sample counties:", len(keep))
    S.ensure_weather(ddir, Y0, Y1, keep)
    stage_model_irr(ddir, path, a.out_dir, keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
