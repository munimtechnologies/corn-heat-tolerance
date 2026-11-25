# ldiff_yu.py - step 0.7.1: Yu, Miao & Khanna's exact long-difference specification,
# with and without state fixed effects (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Pre-registered in PREREG-LD-YU.md (marker corn-heat-tolerance-0.7.1-yu-prereg),
# an addendum to PREREG-LD.md (0.7.0) written on 2026-11-25, before any result of
# this project existed.
#
# 0.7.0 (ldiff.py) uses this project's own weather variables (March-August, degree
# days 10..b and > b, precipitation and its square, at least 3 of 5 years per
# period). Re-reading Yu et al.'s Methods (Sci. Rep. 11:12351, 2021) showed that
# their model uses, per year and then averaged over each 5-year period:
#   * April 1 - September 30,
#   * "normal GDD" between 0 and 29 C and "overheating GDD" above 29 C, for both crops,
#   * precipitation as two hinge terms around p0 = 42 cm: max(42 - P, 0) and
#     max(P - 42, 0), in cm,
#   * log yield, county fixed effects with a period dummy interacted with each
#     variable (equivalent to the two-period cross-section in ldiff.py), no weights
#     in the regression, and counties dropped only if they grow the crop in just one
#     period (no minimum number of years).
# This step re-runs the 0.7.0 models A (one intercept) and B (state fixed effects)
# on exactly those variables, so the replication of their 58% (corn) and 55%
# (soybeans) fall, and the within-state test, cannot be blamed on our own choice of
# variables. It reuses ldiff.fit_ld unchanged.

import argparse
import json
import os
import sys

import ldiff as LD
import dtstate as DT
import run_cornheat as R
import soyheat as S

YU_NAMES = ("GDD0_29", "EDD29", "Pshort42", "Pexcess42")
YU_SEASON = "AprSep"
YU_B = 29                      # both crops, as in Yu et al.
P0_CM = 42.0
YU_MIN_YEARS = 1               # Yu et al.: dropped only if absent from a period
YU_REPORTED = {"corn": -0.58, "soy": -0.55}      # 1958-62 vs 2013-17, eta/beta convention
BAND = (-0.90, -0.30)          # YX1/YX2: magnitude replicates within this band


def weather_vec_yu(r, season=YU_SEASON):
    """[GDD 0..29, GDD > 29, precipitation shortfall below 42 cm, excess above 42 cm]
    of one county-year row. P in the rows is in mm."""
    dd = r["dd"][season]
    p_cm = float(r["P"][season]) / 10.0
    return [float(dd[0]) - float(dd[YU_B]), float(dd[YU_B]),
            max(P0_CM - p_cm, 0.0), max(p_cm - P0_CM, 0.0)]


def period_means_yu(rows, period, min_years=YU_MIN_YEARS, season=YU_SEASON):
    """Per county: mean log yield and mean Yu weather over the years of `period`
    that have a yield (each year's hinge terms are computed first, then averaged)."""
    y0, y1 = period
    acc = {}
    for r in rows:
        if not y0 <= r["year"] <= y1:
            continue
        a = acc.setdefault(r["fips"], {"state": r["state"], "years": set(), "y": 0.0,
                                       "w": [0.0] * len(YU_NAMES)})
        if r["year"] in a["years"]:
            continue
        a["years"].add(r["year"])
        a["y"] += float(r["logy"])
        for k, v in enumerate(weather_vec_yu(r, season)):
            a["w"][k] += v
    out = {}
    for f, a in acc.items():
        n = len(a["years"])
        if n >= min_years:
            out[f] = {"state": a["state"], "n": n, "y": a["y"] / n, "w": [x / n for x in a["w"]]}
    return out


def ld_records_yu(rows, pair, min_years=YU_MIN_YEARS):
    m0 = period_means_yu(rows, pair[0], min_years)
    m1 = period_means_yu(rows, pair[1], min_years)
    recs = []
    for f in sorted(set(m0) & set(m1)):
        a, c = m0[f], m1[f]
        recs.append({"fips": f, "state": a["state"], "dy": c["y"] - a["y"], "y0": a["y"],
                     "dw": [x1 - x0 for x0, x1 in zip(a["w"], c["w"])],
                     "w0": list(a["w"]), "w1": list(c["w"])})
    return recs


def relabel(fit):
    """ldiff.fit_ld names the 4 columns GDD, EDD, P, P2; give them Yu's meaning.
    The EDD keys (dEDD, EDD_1) keep their names so ldiff's grading helpers apply."""
    m = {"GDD": "GDD0_29", "P": "Pshort42", "P2": "Pexcess42"}
    out = dict(fit)
    coef = {}
    for k, v in fit["coef"].items():
        if k.startswith("d") and k[1:] in m:
            k = "d" + m[k[1:]]
        elif k.endswith("_1") and k[:-2] in m:
            k = m[k[:-2]] + "_1"
        coef[k] = v
    out["coef"] = coef
    out["names"] = list(coef)
    return out


def ab_yu(recs):
    return {"A": relabel(LD.fit_ld(recs, "none")), "B": relabel(LD.fit_ld(recs, "state"))}


def summary_yu(rows, pair, min_years=YU_MIN_YEARS):
    recs = ld_records_yu(rows, pair, min_years)
    out = ab_yu(recs)
    out["periods"] = [list(pair[0]), list(pair[1])]
    out["min_years"] = min_years
    out["counties"] = len(recs)
    out["by_state"] = {}
    for r in recs:
        out["by_state"][r["state"]] = out["by_state"].get(r["state"], 0) + 1
    out["mean_dEDD"] = sum(r["dw"][1] for r in recs) / len(recs)
    return out


def pairs20_yu(rows, min_years=YU_MIN_YEARS):
    p20 = []
    for pair in LD.PAIRS20:
        try:
            ps = summary_yu(rows, pair, min_years)
            p20.append({"periods": ps["periods"], "counties": ps["counties"],
                        "A": ps["A"]["eta_over_beta_EDD"], "B": ps["B"]["eta_over_beta_EDD"],
                        "eta_A": ps["A"]["coef"]["EDD_1"], "eta_B": ps["B"]["coef"]["EDD_1"]})
        except (ValueError, ZeroDivisionError) as e:
            p20.append({"periods": [list(pair[0]), list(pair[1])], "error": str(e)})
    ok = [x for x in p20 if "error" not in x and x["A"] is not None and x["B"] is not None]
    return {"pairs": p20, "n_ok": len(ok),
            "mean_A": sum(x["A"] for x in ok) / len(ok) if ok else None,
            "mean_B": sum(x["B"] for x in ok) / len(ok) if ok else None}


# ------------------------------------------------------------------ grading
def in_band(x, lo=BAND[0], hi=BAND[1]):
    return x is not None and lo <= x <= hi


def pairs_shrink(p):
    """Mean 20-year eta/beta is negative under A (a fall) and model B's mean is less
    than half as negative (or not negative at all)."""
    a, b = p.get("mean_A"), p.get("mean_B")
    return a is not None and b is not None and a < 0 and b > 0.5 * a


YU_PRED_KEYS = ("YX1_holds_corn_A_replicates_magnitude", "YX2_holds_soy_A_replicates_magnitude",
                "YX3_holds_corn_shrinks_within_state", "YX4_holds_soy_shrinks_within_state",
                "YX5_holds_corn_pairs20_shrink_within_state")


def grade_yu(res):
    """Pre-registered predictions YX1-YX5 and gates YG1-YG3 (PREREG-LD-YU.md)."""
    c, s = res["corn"], res["soy"]
    g = {
        "YG1_corn_counties_ge_800": c["counties"] >= 800,
        "YG2_soy_counties_ge_400": s["counties"] >= 400,
        "YG3_corn_states_ge_15": c["B"]["states"] >= 15,
        "YX1_holds_corn_A_replicates_magnitude": LD.sensitivity_fell(c["A"]) and in_band(c["A"]["eta_over_beta_EDD"]),
        "YX2_holds_soy_A_replicates_magnitude": LD.sensitivity_fell(s["A"]) and in_band(s["A"]["eta_over_beta_EDD"]),
        "YX3_holds_corn_shrinks_within_state": LD.shrank(c["A"], c["B"]),
        "YX4_holds_soy_shrinks_within_state": LD.shrank(s["A"], s["B"]),
        "YX5_holds_corn_pairs20_shrink_within_state": pairs_shrink(res["corn_pairs20"]),
        "corn_eta_over_beta_A": c["A"]["eta_over_beta_EDD"],
        "corn_eta_over_beta_B": c["B"]["eta_over_beta_EDD"],
        "soy_eta_over_beta_A": s["A"]["eta_over_beta_EDD"],
        "soy_eta_over_beta_B": s["B"]["eta_over_beta_EDD"],
        "yu_reported": dict(YU_REPORTED),
    }
    g["predictions_held"] = sum(1 for k in YU_PRED_KEYS if g[k])
    return g


# ------------------------------------------------------------------ pipeline
def stage_model_yu(rows, census, out):
    res = {"census": census, "season": YU_SEASON, "threshold": YU_B, "p0_cm": P0_CM,
           "min_years": YU_MIN_YEARS, "primary": LD.PRIMARY, "variables": YU_NAMES,
           "units": "log yield per degree day; precipitation hinge terms in cm"}
    for crop in ("corn", "soy"):
        res[crop] = summary_yu(rows[crop], LD.PRIMARY)
        res[crop + "_pairs20"] = pairs20_yu(rows[crop])
        LD.log(crop, "Yu-exact A eta/beta:", res[crop]["A"]["eta_over_beta_EDD"],
               "B:", res[crop]["B"]["eta_over_beta_EDD"], "n", res[crop]["counties"])
    rob = {}
    for crop in ("corn", "soy"):
        rob[crop + "_min3"] = summary_yu(rows[crop], LD.PRIMARY, min_years=3)
        rob[crop + "_extended_2021_25"] = summary_yu(rows[crop], LD.EXTENDED)
        mw = [r for r in ld_records_yu(rows[crop], LD.PRIMARY) if r["state"] in LD.MW12]
        rob[crop + "_mw12"] = ab_yu(mw) if len(mw) > 30 else {"error": "too few counties"}
    res["robustness"] = rob
    res["grades"] = grade_yu(res)
    with open(os.path.join(out, "ldiff_yu_results.json"), "w") as fh:
        json.dump(res, fh, indent=1, default=float)
    LD.log("grades:", json.dumps(res["grades"], indent=1, default=float))
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--max-wait-min", type=int, default=720)
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "cornheat")
    sdir = os.path.join(ddir, "soy")
    os.makedirs(a.out_dir, exist_ok=True)
    # This step never builds the shared tables itself (the 0.1.0/0.2.0/0.7.0 jobs
    # do), so it can never collide with another writer on the volume.
    if not DT.wait_for_inputs(ddir, sdir, 1951, 2025, a.max_wait_min):
        LD.log("inputs not ready; nothing read. Re-run after the cornheat/soyheat/ldiff jobs.")
        return 3
    keep = R.east_sample(R.load_geo(R.stage_geo(ddir)))
    LD.log("east sample counties:", len(keep))
    rows, census = S.load_panels(ddir, sdir, keep, LD.Y0, LD.Y1)
    LD.log("panels:", census)
    stage_model_yu(rows, census, a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
