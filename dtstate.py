# dtstate.py - drought-tolerant corn adoption by state (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-DT.md (marker corn-heat-tolerance-0.3.0-dt-states-prereg).
# The national corn-minus-soybean difference-in-differences (0.2.0) dilutes any
# effect of drought-tolerant (DT) hybrids, which were adopted unevenly: USDA ERS
# (EIB-204, 2019; ARMS 2016) reports 42% of Nebraska's and 39% of Kansas's corn
# acres in DT hybrids, against 16-21% in Iowa, Illinois, Indiana and Ohio and
# 14-20% in Minnesota, Wisconsin and Michigan. The primary test here is the triple
# difference
#     T = DiD(high-adoption states) - DiD(low-adoption states),
#     DiD(g) = (EDD_C - EDD_B)corn,g - (EDD_C - EDD_B)soy,g,
# from one stacked regression (four blocks: corn/soy x high/low). With only two
# high-adoption states, state-clustered variance is unreliable, so the primary
# decision needs BOTH a year-clustered p < 0.05 AND randomization inference: the
# real split must be the most extreme of all 36 ways to call 2 of the 9 states
# "high" (p_RI = 1/36). The secondary test splits counties by 1981-2010 growing-
# season precipitation (driest vs wettest third) across the whole eastern sample.
#
# Reuses the published cornheat_model / run_cornheat / soyheat modules unchanged
# (commit 287631dc) and the derived tables cached on the same data volume.

import argparse
import itertools
import json
import math
import os
import sys
import time

import run_cornheat as R
import soyheat as S

ERAS = R.ERAS
LATE_ERAS = [("A", 1951, 1980), ("B", 1981, 2010), ("C", 2016, 2025)]
B_CROP = S.B_CROP
log = R.log

HIGH = ("20", "31")                                   # Kansas 39%, Nebraska 42%
LOW = ("17", "18", "19", "26", "27", "39", "55")      # IL IN IA OH 16-21%; MI MN WI 14-20%
MID = ("46", "48")                                    # South Dakota, Texas 20-27% (reported only)
POOL = tuple(sorted(HIGH + LOW))
ERS_DT_2016 = {"31": "42", "20": "39", "46": "20-27", "48": "20-27",
               "19": "16-21", "17": "16-21", "18": "16-21", "39": "16-21",
               "27": "14-20", "55": "14-20", "26": "14-20"}
STATE_NAME = {"20": "Kansas", "31": "Nebraska", "17": "Illinois", "18": "Indiana",
              "19": "Iowa", "26": "Michigan", "27": "Minnesota", "39": "Ohio",
              "55": "Wisconsin", "46": "South Dakota", "48": "Texas"}


# ------------------------------------------------------------------ contrasts
def group_weights(g, sign=1.0):
    """Corn-minus-soybean DiD of group g: (C-B)corn - (C-B)soy."""
    return {"corn%s:EDD_C" % g: sign, "corn%s:EDD_B" % g: -sign,
            "soy%s:EDD_C" % g: -sign, "soy%s:EDD_B" % g: sign}


def ddd_weights():
    w = group_weights("H", 1.0)
    w.update(group_weights("L", -1.0))
    return w


def contrast_v(res, weights, vkey):
    """sum_k w_k beta_k with the variance matrix res[vkey] (V2 = year-clustered)."""
    idx = [(res["names"].index(k), w) for k, w in weights.items()]
    d = sum(w * float(res["beta"][i]) for i, w in idx)
    V = res[vkey]
    v = sum(wi * wj * float(V[i, j]) for i, wi in idx for j, wj in idx)
    se = math.sqrt(v) if v > 0 else float("nan")
    z = d / se if se == se and se > 0 else float("nan")
    p = math.erfc(abs(z) / math.sqrt(2.0)) if z == z else float("nan")
    return {"diff": d, "se": se, "z": z, "p": p}


def ddd_fit(corn, soy, in_h, in_l, eras=ERAS, season="MarAug", b_corn=29, b_soy=30, full=True):
    """Stacked corn/soy x high/low regression. Returns T (the triple difference)
    with year-clustered inference; with full=True also the two-way version, the
    two group DiDs and the EDD coefficients."""
    parts = [("cornH", [r for r in corn if in_h(r)], eras, b_corn, season),
             ("soyH", [r for r in soy if in_h(r)], eras, b_soy, season),
             ("cornL", [r for r in corn if in_l(r)], eras, b_corn, season),
             ("soyL", [r for r in soy if in_l(r)], eras, b_soy, season)]
    for p in parts:
        if not p[1]:
            raise ValueError("empty block %s" % p[0])
    jf = S.joint_fit(parts)
    W = ddd_weights()
    t_year = contrast_v(jf, W, "V2")
    out = {"n": jf["n"], "rows": {p[0]: len(p[1]) for p in parts},
           "T": t_year["diff"], "T_year": t_year}
    if full:
        out["T_twoway"] = S.contrast(jf, W)
        out["did_H_year"] = contrast_v(jf, group_weights("H"), "V2")
        out["did_L_year"] = contrast_v(jf, group_weights("L"), "V2")
        out["coef"] = {}
        for p in ("cornH", "soyH", "cornL", "soyL"):
            for L, _, _ in eras:
                nm = "%s:EDD_%s" % (p, L)
                if nm in jf["names"]:
                    j = jf["names"].index(nm)
                    out["coef"][nm] = {"b": float(jf["beta"][j]),
                                       "se_year": math.sqrt(max(0.0, float(jf["V2"][j, j])))}
    return out


# ------------------------------------------------------------------ inference
def placebo_sets(pool=POOL, k=2):
    return [tuple(c) for c in itertools.combinations(sorted(pool), k)]


def ri_p(t_obs, ts):
    """Two-sided randomization p: share of assignments at least as extreme."""
    return sum(1 for t in ts if abs(t) >= abs(t_obs) * (1 - 1e-9)) / float(len(ts))


def randomization(corn, soy, pool=POOL, high=HIGH, **kw):
    pl = []
    for hs in placebo_sets(pool, len(high)):
        h = set(hs)
        lo = set(pool) - h
        t = ddd_fit(corn, soy, lambda r: r["state"] in h, lambda r: r["state"] in lo,
                    full=False, **kw)["T"]
        pl.append({"high": list(hs), "T": t})
    obs = [x["T"] for x in pl if set(x["high"]) == set(high)]
    if len(obs) != 1:
        raise ValueError("observed assignment not among placebos")
    return {"T_obs": obs[0], "p": ri_p(obs[0], [x["T"] for x in pl]), "placebos": pl}


def ddd_class(t_year, p_ri):
    if t_year["p"] == t_year["p"] and t_year["p"] < 0.05 and p_ri is not None and p_ri < 0.05:
        return "high-adoption corn gained" if t_year["diff"] > 0 else "high-adoption corn lost"
    return "no detectable difference"


def tercile_class(t):
    if t["p"] == t["p"] and t["p"] < 0.05:
        return "dry-county corn gained" if t["diff"] > 0 else "dry-county corn lost"
    return "no detectable difference"


# ------------------------------------------------------------------ groups
def precip_terciles(corn_main, season="MarAug", y0=1981, y1=2010):
    """Counties of the corn era-B sample split by their mean 1981-2010 season
    precipitation: driest third and wettest third (ties broken by FIPS)."""
    acc = {}
    for r in corn_main:
        if y0 <= r["year"] <= y1:
            a = acc.setdefault(r["fips"], [0.0, 0])
            a[0] += r["P"][season]
            a[1] += 1
    means = sorted((a[0] / a[1], f) for f, a in acc.items())
    k = len(means) // 3
    dry = {f for _, f in means[:k]}
    wet = {f for _, f in means[len(means) - k:]} if k else set()
    info = {"counties": len(means), "per_tercile": k,
            "dry_max_mm": means[k - 1][0] if k else None,
            "wet_min_mm": means[len(means) - k][0] if k else None}
    return dry, wet, info


def era_counties(rows, era):
    _L, a, b = era
    return len({r["fips"] for r in rows if a <= r["year"] <= b})


def state_did(corn, soy, st):
    c = [r for r in corn if r["state"] == st]
    s = [r for r in soy if r["state"] == st]
    if not c or not s:
        return None
    jf = S.joint_fit([("corn", c, ERAS, B_CROP["corn"], "MarAug"),
                      ("soy", s, ERAS, B_CROP["soy"], "MarAug")])
    if not all(k in jf["names"] for k in S.DID_W):
        return None
    return dict(contrast_v(jf, S.DID_W, "V2"), corn_rows=len(c), soy_rows=len(s))


# ------------------------------------------------------------------ grading
def grade_dt(res):
    """Pre-registered predictions D1-D4 and gates G1-G3 (PREREG-DT.md)."""
    p = res["primary"]
    t = res["terciles"]
    c = res["counts"]
    g = {
        "G1_high_corn_eraC_counties_ge_80": c["H"]["corn"]["C"] >= 80,
        "G2_high_soy_eraC_counties_ge_60": c["H"]["soy"]["C"] >= 60,
        "G3_low_corn_eraC_counties_ge_300": c["L"]["corn"]["C"] >= 300,
        "D1_class": p["class"],
        "D1_holds_no_detectable_difference": p["class"] == "no detectable difference",
        "D2_holds_T_positive": p["T"] > 0,
        "D3_holds_high_less_heat_sensitive_B":
            abs(p["coef"]["cornH:EDD_B"]["b"]) < abs(p["coef"]["cornL:EDD_B"]["b"]),
        "D4_class": t["class"],
        "D4_holds_no_detectable_difference": t["class"] == "no detectable difference",
    }
    g["predictions_held"] = sum(1 for k in ("D1_holds_no_detectable_difference", "D2_holds_T_positive",
                                            "D3_holds_high_less_heat_sensitive_B",
                                            "D4_holds_no_detectable_difference") if g[k])
    return g


# ------------------------------------------------------------------ pipeline
def wait_for_inputs(ddir, sdir, y0, y1, max_wait_min, poll_s=300):
    """The derived tables are built by the 0.1.0/0.2.0 jobs on the same volume.
    Wait for them (atomic files), up to max_wait_min; False if still missing."""
    t0 = time.time()
    while True:
        need = [os.path.join(ddir, "gazetteer_counties.tsv"),
                os.path.join(sdir, "nass_cornsoy_county.tsv")]
        need += [os.path.join(ddir, "weather", "w_%d.csv" % y) for y in range(y0, y1 + 1)]
        missing = [x for x in need if not os.path.exists(x)]
        if not missing:
            return True
        if time.time() - t0 > max_wait_min * 60:
            log("inputs: still missing %d files after %d min; building them" % (len(missing), max_wait_min))
            return False
        log("inputs: %d files missing (e.g. %s); waiting" % (len(missing), missing[0]))
        time.sleep(poll_s)


def stage_model_dt(ddir, sdir, out, y0, y1, keep):
    rows, census = S.load_panels(ddir, sdir, keep, y0, y1)
    log("panels:", census)
    main = {c: R.era_filter(rows[c], ERAS) for c in ("corn", "soy")}
    late = {c: R.era_filter(rows[c], LATE_ERAS) for c in ("corn", "soy")}
    del rows
    pool = set(POOL)
    pc = [r for r in main["corn"] if r["state"] in pool]
    ps = [r for r in main["soy"] if r["state"] in pool]

    def in_h(r):
        return r["state"] in HIGH

    def in_l(r):
        return r["state"] in LOW

    res = {"census": census, "eras": ERAS, "thresholds": B_CROP,
           "groups": {"HIGH": HIGH, "LOW": LOW, "MID": MID, "ers_dt_2016_pct": ERS_DT_2016}}
    res["counts"] = {g: {crop: {L: era_counties([r for r in main[crop] if r["state"] in sts], (L, a, b))
                                for (L, a, b) in ERAS}
                         for crop in ("corn", "soy")}
                     for g, sts in (("H", HIGH), ("L", LOW), ("M", MID))}

    prim = ddd_fit(pc, ps, in_h, in_l)
    ri = randomization(pc, ps)
    prim["p_ri"] = ri["p"]
    prim["class"] = ddd_class(prim["T_year"], ri["p"])
    res["primary"] = prim
    res["placebos"] = ri["placebos"]
    log("primary:", json.dumps({"T": prim["T"], "p_year": prim["T_year"]["p"], "p_ri": ri["p"],
                                "class": prim["class"]}))

    dry, wet, tinfo = precip_terciles(main["corn"])
    h2 = ddd_fit(main["corn"], main["soy"], lambda r: r["fips"] in dry, lambda r: r["fips"] in wet)
    h2["class"] = tercile_class(h2["T_twoway"])
    h2["terciles"] = tinfo
    res["terciles"] = h2
    log("terciles:", json.dumps({"T": h2["T"], "p_2way": h2["T_twoway"]["p"], "class": h2["class"]}))

    rob = {}
    rob["no2012"] = ddd_fit([r for r in pc if r["year"] != 2012],
                            [r for r in ps if r["year"] != 2012], in_h, in_l)
    rob["AprSep"] = ddd_fit(pc, ps, in_h, in_l, season="AprSep")
    rob["late_C_2016_2025"] = ddd_fit([r for r in late["corn"] if r["state"] in pool],
                                      [r for r in late["soy"] if r["state"] in pool],
                                      in_h, in_l, eras=LATE_ERAS)
    mids = set(MID) | set(LOW)
    try:
        rob["mid_vs_low"] = ddd_fit([r for r in main["corn"] if r["state"] in mids],
                                    [r for r in main["soy"] if r["state"] in mids],
                                    lambda r: r["state"] in MID, in_l)
    except ValueError as e:
        rob["mid_vs_low"] = {"error": str(e)}
    res["robustness"] = rob

    res["states"] = {}
    for st in POOL + MID:
        d = state_did(main["corn"], main["soy"], st)
        res["states"][st] = dict(d or {}, name=STATE_NAME[st], ers_dt_2016_pct=ERS_DT_2016[st])

    res["grades"] = grade_dt(res)
    with open(os.path.join(out, "dtstate_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    log("grades:", json.dumps(res["grades"], indent=1))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--y0", type=int, default=1951)
    ap.add_argument("--y1", type=int, default=2025)
    ap.add_argument("--max-wait-min", type=int, default=480)
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "cornheat")
    sdir = os.path.join(ddir, "soy")
    os.makedirs(sdir, exist_ok=True)
    os.makedirs(a.out_dir, exist_ok=True)
    wait_for_inputs(ddir, sdir, a.y0, a.y1, a.max_wait_min)
    keep = R.east_sample(R.load_geo(R.stage_geo(ddir)))
    log("east sample counties:", len(keep))
    if not os.path.exists(os.path.join(sdir, "nass_cornsoy_county.tsv")):
        S.stage_nass_two(sdir, a.out_dir)
    S.ensure_weather(ddir, a.y0, a.y1, keep)
    stage_model_dt(ddir, sdir, a.out_dir, a.y0, a.y1, keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
