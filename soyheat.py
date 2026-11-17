# soyheat.py - soybean comparison crop for corn-heat-tolerance (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-SOY.md (marker corn-heat-tolerance-0.2.0-soy-prereg).
# Soybeans had no widely sold drought-tolerant trait in 2011-2025, while corn had
# drought-tolerant hybrids from 2011. If corn's extreme-heat coefficient changed
# between 1981-2010 and 2011-2025 and soybeans' did not, the change is more
# plausibly about corn itself than about weather data, management common to both
# crops or the reporting counties. The joint (stacked) regression gives the
# corn-minus-soybean difference-in-differences with two-way clustered variance
# shared across both crops.
#
# Reuses the published cornheat_data / cornheat_model / run_cornheat modules
# unchanged. Weather tables are shared with run_cornheat under
# <data-dir>/cornheat/weather (same data volume); NASS rows for both crops come
# from one pass over one bulk file and are cached under <data-dir>/cornheat/soy/.

import argparse
import csv
import json
import math
import os
import sys
import time

import cornheat_data as D
import run_cornheat as R

SOY_YIELD_SHORT = "SOYBEANS - YIELD, MEASURED IN BU / ACRE"
SOY_AREA_SHORT = "SOYBEANS - ACRES HARVESTED"
SHORT_SLOT = {
    D.CORN_YIELD_SHORT: ("corn", "yield"),
    D.CORN_AREA_SHORT: ("corn", "area"),
    SOY_YIELD_SHORT: ("soy", "yield"),
    SOY_AREA_SHORT: ("soy", "area"),
}
PREFIXES = ("CORN, GRAIN - ", "SOYBEANS - ")
B_CROP = {"corn": 29, "soy": 30}       # Schlenker-Roberts thresholds
ERAS = R.ERAS
log = R.log


# ------------------------------------------------------------------ NASS
def nass_filter_multi(lines, short_slot=SHORT_SLOT, prefixes=PREFIXES, seen=None):
    """Like cornheat_data.nass_filter_lines but for several crops at once.
    Yields dicts fips, year, crop, slot, value for county-level annual SURVEY
    TOTAL rows. If `seen` is a dict, it counts every SHORT_DESC that contains
    'YIELD' among county SURVEY rows of the wanted crops (diagnostics)."""
    it = iter(lines)
    header = next(it).rstrip("\r\n").split("\t")
    hdr = [h.strip().strip('"').upper() for h in header]
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
        if "COUNTY" not in line:
            continue
        if not any(p in line for p in prefixes):
            continue
        f = [x.strip().strip('"') for x in line.rstrip("\r\n").split("\t")]
        if len(f) < len(hdr):
            continue
        if f[col["AGG_LEVEL_DESC"]] != "COUNTY" or f[col["SOURCE_DESC"]] != "SURVEY":
            continue
        short = f[col["SHORT_DESC"]]
        if seen is not None and "YIELD" in short:
            seen[short] = seen.get(short, 0) + 1
        if short not in short_slot:
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
        crop, slot = short_slot[short]
        yield {"fips": "%02d%03d" % (int(s), int(c)), "year": int(f[col["YEAR"]]),
               "crop": crop, "slot": slot, "value": val}


def collect_nass(records):
    """dict (crop, fips, year) -> {slot: value}; conflicting duplicates keep the
    first value and are counted."""
    out, conflicts = {}, 0
    for r in records:
        cur = out.setdefault((r["crop"], r["fips"], r["year"]), {})
        if r["slot"] in cur and abs(cur[r["slot"]] - r["value"]) > 1e-9:
            conflicts += 1
            continue
        cur.setdefault(r["slot"], r["value"])
    return out, conflicts


def stage_nass_two(sdir, out):
    path = os.path.join(sdir, "nass_cornsoy_county.tsv")
    if os.path.exists(path):
        log("nass2: cached", path)
        return path
    url = None
    for lu in D.NASS_LISTING_URLS:
        try:
            url = D.find_nass_crops_url(D.http_get(lu).decode("utf-8", errors="replace"))
            if url:
                break
        except Exception as e:
            log("nass2: listing failed", lu, e)
    if not url:
        raise SystemExit("nass2: no qs.crops file found on the listing page")
    log("nass2: streaming", url)
    seen = {}
    recs, conflicts = collect_nass(nass_filter_multi(D.stream_nass(url), seen=seen))
    by_crop = {}
    for (crop, f, y), c in recs.items():
        if "yield" in c:
            by_crop[crop] = by_crop.get(crop, 0) + 1
    meta = {"source_url": url, "county_years_with_yield": by_crop,
            "duplicate_conflicts": conflicts,
            "yield_short_descs_seen": dict(sorted(seen.items(), key=lambda kv: -kv[1])[:40])}
    with open(os.path.join(out, "nass2_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    if not by_crop.get("soy") or not by_crop.get("corn"):
        raise SystemExit("nass2: a crop has no county yields: %s" % by_crop)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("crop\tfips\tyear\tyield_bu_ac\tarea_ac\n")
        for k in sorted(recs):
            c = recs[k]
            fh.write("%s\t%s\t%d\t%s\t%s\n" % (k[0], k[1], k[2], c.get("yield", ""), c.get("area", "")))
    os.replace(tmp, path)
    with open(os.path.join(sdir, "nass2_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    log("nass2:", by_crop, "conflicts", conflicts)
    return path


# ------------------------------------------------------------------ weather
def ensure_weather(ddir, y0, y1, keep, idle_min=20, max_wait_min=300, poll_s=120):
    """The weather tables are shared with run_cornheat on the same data volume.
    If another job is still writing them (a file changed within idle_min), wait;
    then build whatever is still missing with run_cornheat.stage_weather."""
    wdir = os.path.join(ddir, "weather")
    os.makedirs(wdir, exist_ok=True)
    t0 = time.time()
    while True:
        missing = [y for y in range(y0, y1 + 1)
                   if not os.path.exists(os.path.join(wdir, "w_%d.csv" % y))]
        if not missing:
            log("weather: all %d years cached" % (y1 - y0 + 1))
            return wdir
        names = os.listdir(wdir)
        newest = max([os.path.getmtime(os.path.join(wdir, n)) for n in names] or [0.0])
        idle = time.time() - newest
        if idle > idle_min * 60 or time.time() - t0 > max_wait_min * 60:
            break
        log("weather: %d years missing, another writer active %.0fs ago; waiting" % (len(missing), idle))
        time.sleep(poll_s)
    # Newest year first and a private temp name, so that a run_cornheat job
    # building oldest-first on the same volume never shares a temp file.
    log("weather: building %d missing years (newest first)" % len(missing))
    for year in sorted(missing, reverse=True):
        build_weather_year(wdir, year, keep)
    return wdir


def season_accumulate(acc, fipss, dd, psum, miss, nd, month):
    """Add one month's per-county sums into acc[fips][season]."""
    for i, f in enumerate(fipss):
        for s, (m0, m1) in D.SEASONS.items():
            if m0 <= month <= m1:
                a = acc.setdefault(f, {}).setdefault(s, [[0.0] * len(D.THRESHOLDS), 0.0, 0, 0])
                for k in range(len(D.THRESHOLDS)):
                    a[0][k] += float(dd[i][k])
                a[1] += float(psum[i])
                a[2] += int(miss[i])
                a[3] += nd
    return acc


def weather_rows(acc, year):
    rows = []
    for f in sorted(acc):
        for s in D.SEASONS:
            a = acc[f].get(s)
            if a is None:
                continue
            rows.append([f, year, s, a[3], a[2], round(a[1], 2)] + [round(float(x), 3) for x in a[0]])
    return rows


def build_weather_year(wdir, year, keep):
    """Same table as run_cornheat.stage_weather for one year (same header,
    rounding and missing-day rules), written via a private temp file."""
    import numpy as np
    path = os.path.join(wdir, "w_%d.csv" % year)
    if os.path.exists(path):
        return path
    acc = {}
    for month in R.MONTHS:
        data = {}
        for var in ("tmin", "tmax", "prcp"):
            url = D.NCLIMGRID_URL.format(year=year, month=month, var=var)
            data[var] = D.parse_nclimgrid_text(D.http_get(url).decode("utf-8", errors="replace"),
                                               year, month)
        fipss = sorted(set(data["tmin"]) & set(data["tmax"]) & set(data["prcp"]) & keep)
        if not fipss:
            raise SystemExit("weather: no counties for %d-%02d" % (year, month))
        tn = np.array([data["tmin"][f][1] for f in fipss])
        tx = np.array([data["tmax"][f][1] for f in fipss])
        pr = np.array([data["prcp"][f][1] for f in fipss])
        bad = np.isnan(tn) | np.isnan(tx) | np.isnan(pr)
        dd = np.zeros((len(fipss), len(D.THRESHOLDS)))
        for k, b in enumerate(D.THRESHOLDS):
            dd[:, k] = np.where(bad, 0.0, D.dd_above_np(tn, tx, b)).sum(axis=1)
        season_accumulate(acc, fipss, dd, np.where(bad, 0.0, pr).sum(axis=1),
                          bad.sum(axis=1), tn.shape[1], month)
    hdr = ["fips", "year", "season", "ndays", "nmiss", "prcp_mm"] + ["dd%d" % b for b in D.THRESHOLDS]
    tmp = "%s.soy%d.tmp" % (path, os.getpid())
    D.write_csv(tmp, hdr, weather_rows(acc, year))
    if os.path.exists(path):      # another writer finished first: same content
        os.remove(tmp)
    else:
        os.replace(tmp, path)
    log("weather(soy):", year)
    return path


# ------------------------------------------------------------------ panel
def load_panels(ddir, sdir, keep, y0, y1):
    """rows per crop in the cornheat_model row format; weather arrays shared."""
    import numpy as np
    ylds = {"corn": {}, "soy": {}}
    with open(os.path.join(sdir, "nass_cornsoy_county.tsv"), encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            crop, f, y, yl, _ar = line.rstrip("\n").split("\t")
            if crop in ylds and yl and f in keep and y0 <= int(y) <= y1 and float(yl) > 0:
                ylds[crop][(f, int(y))] = float(yl)
    want = set(ylds["corn"]) | set(ylds["soy"])
    rows = {"corn": [], "soy": []}
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
                for crop in ("corn", "soy"):
                    v = ylds[crop].get((f, year))
                    if v is not None:
                        rows[crop].append({"fips": f, "state": f[:2], "year": year,
                                           "logy": math.log(v), "dd": dd, "P": P})
    census = {}
    for crop in ("corn", "soy"):
        nf = {f for (f, y) in ylds[crop]}
        census[crop] = {"nass_county_years": len(ylds[crop]), "nass_counties": len(nf),
                        "nass_counties_with_weather_share": round(len(nf & w_fips) / max(1, len(nf)), 4),
                        "panel_rows": len(rows[crop]),
                        "nass_rows_2025": sum(1 for (f, y) in ylds[crop] if y == 2025)}
    return rows, census


# ------------------------------------------------------------------ joint model
def fwl_weather(rows, eras, b, season):
    """Fixed-effect-demeaned design with the state-by-era trends partialled out
    (Frisch-Waugh-Lovell). Point estimates and cluster scores of the weather
    coefficients equal those of cornheat_model.fit on the same rows."""
    import numpy as np
    import cornheat_model as M
    X, y, names, cs, cy = M.build_design(rows, eras, b, season)
    wi = [j for j, n in enumerate(names) if not n.startswith("trend")]
    ti = [j for j, n in enumerate(names) if n.startswith("trend")]
    W = X[:, wi]
    if ti:
        T = X[:, ti]
        W = W - T @ np.linalg.lstsq(T, W, rcond=None)[0]
        y = y - T @ np.linalg.lstsq(T, y, rcond=None)[0]
    return W, y, [names[j] for j in wi], cs, cy


def joint_fit(parts):
    """parts: list of (prefix, rows, eras, b, season). Stacks the crops with
    fully crop-specific coefficients, fixed effects and trends; clusters (state,
    year) are shared across crops, so cross-crop covariances are estimated."""
    import numpy as np
    import cornheat_model as M
    blocks = [fwl_weather(rows, eras, b, season) for (_p, rows, eras, b, season) in parts]
    n = sum(bl[0].shape[0] for bl in blocks)
    k = sum(bl[0].shape[1] for bl in blocks)
    X = np.zeros((n, k))
    y = np.zeros(n)
    names, cs, cy = [], [], []
    r0 = c0 = 0
    for (p, *_rest), (W, yy, nm, s, t) in zip(parts, blocks):
        X[r0:r0 + W.shape[0], c0:c0 + W.shape[1]] = W
        y[r0:r0 + W.shape[0]] = yy
        names += ["%s:%s" % (p, x) for x in nm]
        cs += list(s)
        cy += list(t)
        r0 += W.shape[0]
        c0 += W.shape[1]
    res = M.ols_twoway(X, y, cs, cy)
    res["names"] = names
    return res


def contrast(res, weights):
    """Linear combination sum_k w_k beta_k with two-way variance; falls back to
    the sum of one-way variances (flagged) if that is not positive."""
    idx = [(res["names"].index(k), w) for k, w in weights.items()]
    d = sum(w * float(res["beta"][i]) for i, w in idx)

    def var(V):
        return sum(wi * wj * float(V[i, j]) for i, wi in idx for j, wj in idx)

    v, fb = var(res["V"]), False
    if not v > 0:
        v, fb = var(res["V1"] + res["V2"]), True
    se = math.sqrt(v) if v > 0 else float("nan")
    z = d / se if se == se and se > 0 else float("nan")
    p = math.erfc(abs(z) / math.sqrt(2.0)) if z == z else float("nan")
    return {"diff": d, "se": se, "z": z, "p": p, "fallback": fb}


DID_W = {"corn:EDD_C": 1.0, "corn:EDD_B": -1.0, "soy:EDD_C": -1.0, "soy:EDD_B": 1.0}


def did_class(t):
    if t["p"] == t["p"] and t["p"] < 0.05:
        return "corn gained relative to soybeans" if t["diff"] > 0 else "corn lost relative to soybeans"
    return "no detectable difference"


def change_class(t):
    if t["p"] == t["p"] and t["p"] < 0.05:
        return "improved" if t["diff"] > 0 else "worsened"
    return "no detectable change"


def joint_summary(corn_rows, soy_rows, season="MarAug", b_corn=29, b_soy=30):
    jf = joint_fit([("corn", corn_rows, ERAS, b_corn, season),
                    ("soy", soy_rows, ERAS, b_soy, season)])
    out = {"n": jf["n"], "states": jf["g1"], "years": jf["g2"], "fallback": jf["fallback"],
           "coef": {}}
    for crop in ("corn", "soy"):
        for L, _, _ in ERAS:
            nm = "%s:EDD_%s" % (crop, L)
            j = jf["names"].index(nm)
            out["coef"][nm] = {"b": float(jf["beta"][j]), "se2way": math.sqrt(jf["V"][j, j])}
        out["%s_C_minus_B" % crop] = contrast(jf, {"%s:EDD_C" % crop: 1.0, "%s:EDD_B" % crop: -1.0})
    out["did"] = contrast(jf, DID_W)
    out["did_class"] = did_class(out["did"])
    return out


def common_rows(main_c, main_s):
    """Rows of each crop whose (county, era) is in both crops' era samples."""
    def era(y):
        for L, a, b in ERAS:
            if a <= y <= b:
                return L
    kc = {(r["fips"], era(r["year"])) for r in main_c}
    ks = {(r["fips"], era(r["year"])) for r in main_s}
    both = kc & ks
    return ([r for r in main_c if (r["fips"], era(r["year"])) in both],
            [r for r in main_s if (r["fips"], era(r["year"])) in both], len(both))


def stage_model_soy(ddir, sdir, out, y0, y1, keep):
    import cornheat_model as M
    rows, census = load_panels(ddir, sdir, keep, y0, y1)
    log("panels:", census)
    res = {"census": census, "eras": ERAS, "thresholds": B_CROP}
    main = {c: R.era_filter(rows[c], ERAS) for c in ("corn", "soy")}
    res["era_counts"] = {c: {L: {"rows": sum(1 for r in main[c] if a <= r["year"] <= b),
                                 "counties": len({r["fips"] for r in main[c] if a <= r["year"] <= b})}
                             for (L, a, b) in ERAS} for c in main}

    # soybeans alone (all four weather terms, as in the corn analysis)
    fs = M.fit(main["soy"], ERAS, b=B_CROP["soy"], season="MarAug")
    soy = {"n": fs["n"], "fallback": fs["fallback"], "coef": {}}
    for L, _, _ in ERAS:
        for w in ("GDD", "EDD", "P", "P2"):
            nm = "%s_%s" % (w, L)
            j = fs["names"].index(nm)
            soy["coef"][nm] = {"b": float(fs["beta"][j]), "se2way": math.sqrt(fs["V"][j, j])}
    soy["EDD_C_minus_B"] = M.diff_test(fs, "EDD_C", "EDD_B")
    soy["EDD_B_minus_A"] = M.diff_test(fs, "EDD_B", "EDD_A")
    res["soy"] = soy

    # joint corn + soybeans: primary difference-in-differences
    res["joint"] = joint_summary(main["corn"], main["soy"])
    log("joint:", json.dumps({k: res["joint"][k] for k in ("did", "did_class")}, default=float))

    # soybean threshold scan, each era alone
    scan = {}
    for era in ERAS:
        er = [r for r in main["soy"] if era[1] <= r["year"] <= era[2]]
        prof = {b: M.fit(er, [era], b=b, season="MarAug")["ssr"] for b in range(24, 37)}
        scan[era[0]] = {"best_b": min(prof, key=lambda k: prof[k]), "ssr": prof}
    res["soy_threshold_scan"] = scan

    # reported robustness (not graded)
    rob = {}
    cc, cs_, npairs = common_rows(main["corn"], main["soy"])
    rob["common_counties"] = dict(joint_summary(cc, cs_), county_eras=npairs)
    rob["no2012"] = joint_summary([r for r in main["corn"] if r["year"] != 2012],
                                  [r for r in main["soy"] if r["year"] != 2012])
    rob["AprSep"] = joint_summary(main["corn"], main["soy"], season="AprSep")
    rob["same_threshold_30"] = joint_summary(main["corn"], main["soy"], b_corn=30, b_soy=30)
    rob["same_threshold_29"] = joint_summary(main["corn"], main["soy"], b_corn=29, b_soy=29)
    res["robustness"] = rob

    roll = []
    for s in range(1951, 2012, 5):
        win = ("W", s, s + 14)
        wr = R.era_filter(rows["soy"], [win])
        if len(wr) < 1000:
            continue
        fw = M.fit(wr, [win], b=B_CROP["soy"], season="MarAug")
        bb, se = M.coef(fw, "EDD_W")
        roll.append({"years": [s, s + 14], "EDD": bb, "se2way": se, "n": fw["n"]})
    res["soy_rolling"] = roll

    res["grades"] = grade_soy(res)
    with open(os.path.join(out, "soyheat_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1))
    return res


def grade_soy(res):
    """Pre-registered predictions S1-S5 and gates SG1-SG3 (PREREG-SOY.md)."""
    j = res["joint"]
    s = res["soy"]
    sB = s["coef"]["EDD_B"]["b"]
    cB = j["coef"]["corn:EDD_B"]["b"]
    soy_cls = change_class(s["EDD_C_minus_B"])
    best = res["soy_threshold_scan"]["B"]["best_b"]
    g = {
        "SG1_soy_eraC_counties_ge_800": res["era_counts"]["soy"]["C"]["counties"] >= 800,
        "SG2_soy_weather_match_ge_0.90": res["census"]["soy"]["nass_counties_with_weather_share"] >= 0.90,
        "SG3_soy_2025_rows_ge_400": res["census"]["soy"]["nass_rows_2025"] >= 400,
        "S1_class": j["did_class"],
        "S1_holds_no_detectable_difference": j["did_class"] == "no detectable difference",
        "S2_holds_soy_B_in_range": -0.012 <= sB <= -0.002,
        "S3_holds_soy_less_sensitive_than_corn_B": abs(sB) < abs(cB),
        "S4_class": soy_cls,
        "S4_holds_soy_no_detectable_change": soy_cls == "no detectable change",
        "S5_holds_soy_threshold_B_28_33": 28 <= best <= 33,
    }
    g["predictions_held"] = sum(1 for k in ("S1_holds_no_detectable_difference", "S2_holds_soy_B_in_range",
                                            "S3_holds_soy_less_sensitive_than_corn_B",
                                            "S4_holds_soy_no_detectable_change",
                                            "S5_holds_soy_threshold_B_28_33") if g[k])
    return g


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--y0", type=int, default=1951)
    ap.add_argument("--y1", type=int, default=2025)
    ap.add_argument("--stage", default="all", choices=["all", "data", "model"])
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "cornheat")
    sdir = os.path.join(ddir, "soy")
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    keep = R.east_sample(R.load_geo(R.stage_geo(ddir)))
    log("east sample counties:", len(keep))
    if a.stage in ("all", "data"):
        stage_nass_two(sdir, a.out_dir)
        ensure_weather(ddir, a.y0, a.y1, keep)
    if a.stage in ("all", "model"):
        stage_model_soy(ddir, sdir, a.out_dir, a.y0, a.y1, keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
