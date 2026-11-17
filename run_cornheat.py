# run_cornheat.py - pipeline for corn-heat-tolerance (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Stages: geo -> nass -> weather -> model. Each data stage caches its small
# derived file under --data-dir and is skipped when the file exists.
# Raw downloads (NASS ~1 GB gz, nClimGrid ~1.7 GB csv) are streamed, never kept.

import argparse
import json
import math
import os
import sys
import time

import cornheat_data as D

ERAS = [("A", 1951, 1980), ("B", 1981, 2010), ("C", 2011, 2025)]
MONTHS = list(range(3, 10))
SEASON_DAYS = {"MarAug": 184, "AprSep": 183}   # full season, every year
STATE_ABBR = {v: k for k, v in D.STATE_FIPS.items()}


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ------------------------------------------------------------------ stages
def stage_geo(ddir):
    path = os.path.join(ddir, "gazetteer_counties.tsv")
    if os.path.exists(path):
        log("geo: cached", path)
        return path
    last = None
    for url in D.GAZETTEER_URLS:
        try:
            gaz = D.gazetteer_from_zip(D.http_get(url))
            if len(gaz) > 3000:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write("fips\tlat\tlon\tsource\n")
                    for k in sorted(gaz):
                        fh.write("%s\t%.6f\t%.6f\t%s\n" % (k, gaz[k][0], gaz[k][1], url))
                log("geo:", len(gaz), "counties from", url)
                return path
        except Exception as e:
            last = e
            log("geo: failed", url, e)
    raise SystemExit("geo: no gazetteer (%s)" % last)


def stage_nass(ddir, out):
    path = os.path.join(ddir, "nass_corn_county.tsv")
    if os.path.exists(path):
        log("nass: cached", path)
        return path
    url = None
    for lu in D.NASS_LISTING_URLS:
        try:
            url = D.find_nass_crops_url(D.http_get(lu).decode("utf-8", errors="replace"))
            if url:
                break
        except Exception as e:
            log("nass: listing failed", lu, e)
    if not url:
        raise SystemExit("nass: no qs.crops file found on the listing page")
    log("nass: streaming", url)
    recs = {}
    dup_conflict = 0
    n = 0
    for r in D.nass_filter_lines(D.stream_nass(url)):
        n += 1
        key = (r["fips"], r["year"])
        slot = "yield" if r["short"] == D.CORN_YIELD_SHORT else "area"
        cur = recs.setdefault(key, {})
        if slot in cur and abs(cur[slot] - r["value"]) > 1e-9:
            dup_conflict += 1
            continue
        cur.setdefault(slot, r["value"])
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("fips\tyear\tyield_bu_ac\tarea_ac\n")
        for (f, y) in sorted(recs):
            c = recs[(f, y)]
            fh.write("%s\t%d\t%s\t%s\n" % (f, y, c.get("yield", ""), c.get("area", "")))
    os.replace(tmp, path)
    meta = {"source_url": url, "rows_matched": n, "county_years": len(recs),
            "duplicate_conflicts": dup_conflict}
    with open(os.path.join(ddir, "nass_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    with open(os.path.join(out, "nass_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=1)
    log("nass:", meta)
    return path


def load_geo(path):
    out = {}
    with open(path, encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            f = line.rstrip("\n").split("\t")
            out[f[0]] = (float(f[1]), float(f[2]))
    return out


def east_sample(geo):
    """Pre-registered spatial sample: county centroid east of 100 W, not Florida."""
    return {k for k, (la, lo) in geo.items() if lo > -100.0 and not k.startswith("12")}


def stage_weather(ddir, y0, y1, keep):
    import numpy as np
    wdir = os.path.join(ddir, "weather")
    os.makedirs(wdir, exist_ok=True)
    for year in range(y0, y1 + 1):
        path = os.path.join(wdir, "w_%d.csv" % year)
        if os.path.exists(path):
            continue
        acc = {}   # fips -> season -> [dd array, P, miss, ndays]
        for month in MONTHS:
            data = {}
            for var in ("tmin", "tmax", "prcp"):
                url = D.NCLIMGRID_URL.format(year=year, month=month, var=var)
                txt = D.http_get(url).decode("utf-8", errors="replace")
                data[var] = D.parse_nclimgrid_text(txt, year, month)
            fipss = sorted(set(data["tmin"]) & set(data["tmax"]) & set(data["prcp"]) & keep)
            if not fipss:
                raise SystemExit("weather: no counties for %d-%02d" % (year, month))
            tn = np.array([data["tmin"][f][1] for f in fipss])
            tx = np.array([data["tmax"][f][1] for f in fipss])
            pr = np.array([data["prcp"][f][1] for f in fipss])
            bad = np.isnan(tn) | np.isnan(tx) | np.isnan(pr)
            miss = bad.sum(axis=1)
            psum = np.where(bad, 0.0, pr).sum(axis=1)
            dd = np.zeros((len(fipss), len(D.THRESHOLDS)))
            for k, b in enumerate(D.THRESHOLDS):
                v = D.dd_above_np(tn, tx, b)
                dd[:, k] = np.where(bad, 0.0, v).sum(axis=1)
            nd = tn.shape[1]
            for i, f in enumerate(fipss):
                for s, (m0, m1) in D.SEASONS.items():
                    if m0 <= month <= m1:
                        a = acc.setdefault(f, {}).setdefault(
                            s, [np.zeros(len(D.THRESHOLDS)), 0.0, 0, 0])
                        a[0] += dd[i]
                        a[1] += float(psum[i])
                        a[2] += int(miss[i])
                        a[3] += nd
        rows = []
        for f in sorted(acc):
            for s in D.SEASONS:
                a = acc[f].get(s)
                if a is None:
                    continue
                rows.append([f, year, s, a[3], a[2], round(a[1], 2)] +
                            [round(float(x), 3) for x in a[0]])
        hdr = ["fips", "year", "season", "ndays", "nmiss", "prcp_mm"] + \
              ["dd%d" % b for b in D.THRESHOLDS]
        D.write_csv(path + ".tmp", hdr, rows)
        os.replace(path + ".tmp", path)
        log("weather:", year, len(rows), "rows")
    return wdir


def load_panel(ddir, keep, y0, y1):
    import numpy as np
    ylds = {}
    with open(os.path.join(ddir, "nass_corn_county.tsv"), encoding="utf-8") as fh:
        next(fh)
        for line in fh:
            f, y, yl, ar = line.rstrip("\n").split("\t")
            if yl and f in keep and y0 <= int(y) <= y1 and float(yl) > 0:
                ylds[(f, int(y))] = float(yl)
    rows = []
    nass_fips = {f for (f, y) in ylds}
    w_fips = set()
    import csv
    for year in range(y0, y1 + 1):
        with open(os.path.join(ddir, "weather", "w_%d.csv" % year), encoding="utf-8") as fh:
            rd = csv.reader(fh)
            hdr = next(rd)
            tmp = {}
            for r in rd:
                f = r[0]
                w_fips.add(f)
                if (f, year) not in ylds:
                    continue
                if int(r[4]) != 0 or int(r[3]) != SEASON_DAYS[r[2]]:
                    continue
                tmp.setdefault(f, {})[r[2]] = (np.array([float(x) for x in r[6:]]), float(r[5]))
            for f, d in tmp.items():
                if set(d) != set(D.SEASONS):
                    continue
                rows.append({"fips": f, "state": f[:2], "year": year,
                             "logy": math.log(ylds[(f, year)]),
                             "dd": {s: d[s][0] for s in d}, "P": {s: d[s][1] for s in d}})
    match = len(nass_fips & w_fips) / max(1, len(nass_fips))
    return rows, {"nass_county_years": len(ylds), "nass_counties": len(nass_fips),
                  "nass_counties_with_weather_share": round(match, 4),
                  "panel_rows": len(rows),
                  "nass_rows_2025": sum(1 for (f, y) in ylds if y == 2025)}


def era_filter(rows, eras, min_share=2.0 / 3.0):
    """Keep a county in an era only if it has >= ceil(min_share * era years) rows."""
    out = []
    for (L, y0, y1) in eras:
        need = math.ceil(min_share * (y1 - y0 + 1) - 1e-9)
        cnt = {}
        for r in rows:
            if y0 <= r["year"] <= y1:
                cnt[r["fips"]] = cnt.get(r["fips"], 0) + 1
        ok = {f for f, c in cnt.items() if c >= need}
        out += [r for r in rows if y0 <= r["year"] <= y1 and r["fips"] in ok]
    return out


def stage_model(ddir, out, y0, y1, keep):
    import numpy as np
    import cornheat_model as M
    rows, census = load_panel(ddir, keep, y0, y1)
    log("panel:", census)
    res = {"census": census, "eras": ERAS}
    main_rows = era_filter(rows, ERAS)
    res["era_counts"] = {L: {"rows": sum(1 for r in main_rows if a <= r["year"] <= b),
                             "counties": len({r["fips"] for r in main_rows if a <= r["year"] <= b})}
                         for (L, a, b) in ERAS}
    fit = M.fit(main_rows, ERAS, b=29, season="MarAug")
    main = {"n": fit["n"], "states": fit["g1"], "years": fit["g2"], "fallback": fit["fallback"],
            "coef": {}}
    for L, _, _ in ERAS:
        for w in ("GDD", "EDD", "P", "P2"):
            nm = "%s_%s" % (w, L)
            j = fit["names"].index(nm)
            main["coef"][nm] = {"b": float(fit["beta"][j]),
                                "se2way": math.sqrt(fit["V"][j, j]),
                                "se_state": math.sqrt(fit["V1"][j, j]),
                                "se_year": math.sqrt(fit["V2"][j, j])}
    main["EDD_C_minus_B"] = M.diff_test(fit, "EDD_C", "EDD_B")
    main["EDD_B_minus_A"] = M.diff_test(fit, "EDD_B", "EDD_A")
    main["EDD_C_minus_A"] = M.diff_test(fit, "EDD_C", "EDD_A")
    res["main"] = main
    bB = [main["coef"]["%s_B" % w]["b"] for w in ("GDD", "EDD", "P", "P2")]
    log("main EDD:", {L: main["coef"]["EDD_%s" % L] for L, _, _ in ERAS})

    # threshold scan, each era alone
    scan = {}
    for era in ERAS:
        er = [r for r in main_rows if era[1] <= r["year"] <= era[2]]
        prof = {}
        for b in range(24, 37):
            prof[b] = M.fit(er, [era], b=b, season="MarAug")["ssr"]
        best = min(prof, key=lambda k: prof[k])
        scan[era[0]] = {"best_b": best, "ssr": prof}
    res["threshold_scan"] = scan

    # out-of-sample: era-B weather index applied to era C
    eC = [r for r in main_rows if 2011 <= r["year"] <= 2025]
    oos = M.fit(eC, [("C", 2011, 2025)], index_coef={"C": bB})
    lam, lse = M.coef(oos, "INDEX_C")
    res["oos_lambda"] = {"lambda": lam, "se2way": lse, "n": oos["n"]}

    # reported robustness (not graded)
    rob = {}
    for tag, rr, season in (("AprSep", main_rows, "AprSep"),
                            ("no2012", [r for r in main_rows if r["year"] != 2012], "MarAug")):
        f2 = M.fit(rr, ERAS, b=29, season=season)
        rob[tag] = {L: M.coef(f2, "EDD_%s" % L) for L, _, _ in ERAS}
        rob[tag]["C_minus_B"] = M.diff_test(f2, "EDD_C", "EDD_B")
    res["robustness"] = rob

    # rolling 15-year windows (descriptive)
    roll = []
    for s in range(1951, 2012, 5):
        win = ("W", s, s + 14)
        wr = era_filter(rows, [win])
        if len(wr) < 1000:
            continue
        fw = M.fit(wr, [win], b=29, season="MarAug")
        bb, se = M.coef(fw, "EDD_W")
        roll.append({"years": [s, s + 14], "EDD": bb, "se2way": se, "n": fw["n"]})
    res["rolling"] = roll

    res["grades"] = grade(res)
    with open(os.path.join(out, "cornheat_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1))
    return res


def grade(res):
    """Pre-registered predictions P1-P5 and data gates G1-G3 (PREREG.md)."""
    c = res["main"]["coef"]
    d = res["main"]["EDD_C_minus_B"]
    if d["p"] == d["p"] and d["p"] < 0.05:
        cls = "improved" if d["diff"] > 0 else "worsened"
    else:
        cls = "no detectable change"
    sc = res["threshold_scan"]
    g = {
        "G1_eraC_counties_ge_1000": res["era_counts"]["C"]["counties"] >= 1000,
        "G2_nass_weather_match_ge_0.90": res["census"]["nass_counties_with_weather_share"] >= 0.90,
        "G3_nass_2025_rows_ge_500": res["census"]["nass_rows_2025"] >= 500,
        "P1_class": cls,
        "P1_holds_not_improved": cls != "improved",
        "P2_holds_B_more_negative_than_A": c["EDD_B"]["b"] < c["EDD_A"]["b"],
        "P3_holds_B_in_range": -0.012 <= c["EDD_B"]["b"] <= -0.003,
        "P4_holds_threshold": 27 <= sc["C"]["best_b"] <= 32 and abs(sc["C"]["best_b"] - sc["B"]["best_b"]) <= 2,
        "P5_holds_lambda": 0.8 <= res["oos_lambda"]["lambda"] <= 1.3,
    }
    g["predictions_held"] = sum(1 for k in ("P1_holds_not_improved", "P2_holds_B_more_negative_than_A",
                                            "P3_holds_B_in_range", "P4_holds_threshold",
                                            "P5_holds_lambda") if g[k])
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
    os.makedirs(ddir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    gpath = stage_geo(ddir)
    keep = east_sample(load_geo(gpath))
    log("east sample counties:", len(keep))
    if a.stage in ("all", "data"):
        stage_nass(ddir, a.out_dir)
        stage_weather(ddir, a.y0, a.y1, keep)
    if a.stage in ("all", "model"):
        stage_model(ddir, a.out_dir, a.y0, a.y1, keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
