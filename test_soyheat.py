# test_soyheat.py - hand-checked tests for the soybean comparison (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import os
import shutil
import tempfile
import unittest

import cornheat_data as D
import run_cornheat as R
import soyheat as S

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None


class TestNass(unittest.TestCase):
    HDR = ["SOURCE_DESC", "SECTOR_DESC", "SHORT_DESC", "DOMAIN_DESC", "AGG_LEVEL_DESC",
           "STATE_FIPS_CODE", "COUNTY_ANSI", "YEAR", "REFERENCE_PERIOD_DESC", "VALUE"]

    def _lines(self):
        CY, SY, SA = D.CORN_YIELD_SHORT, S.SOY_YIELD_SHORT, S.SOY_AREA_SHORT
        rows = [
            ["SURVEY", "CROPS", CY, "TOTAL", "COUNTY", "19", "001", "2020", "YEAR", "180.5"],
            ["SURVEY", "CROPS", SY, "TOTAL", "COUNTY", "19", "001", "2020", "YEAR", "55.1"],
            ["SURVEY", "CROPS", SY, "TOTAL", "STATE", "19", "", "2020", "YEAR", "58.0"],
            ["SURVEY", "CROPS", SY, "TOTAL", "COUNTY", "17", "998", "2020", "YEAR", "50.0"],
            ["SURVEY", "CROPS", SY, "TOTAL", "COUNTY", "17", "003", "2020", "YEAR", "(D)"],
            ["SURVEY", "CROPS", "SOYBEANS - PRODUCTION, MEASURED IN BU", "TOTAL", "COUNTY",
             "17", "003", "2020", "YEAR", "1,000"],
            ["CENSUS", "CROPS", SY, "TOTAL", "COUNTY", "17", "005", "2022", "YEAR", "51.0"],
            ["SURVEY", "CROPS", SA, "TOTAL", "COUNTY", "17", "005", "2021", "YEAR", "12,300"],
            ["SURVEY", "CROPS", SY, "TOTAL", "COUNTY", "17", "005", "2021", "YEAR - AUG FORECAST", "48.2"],
            ["SURVEY", "CROPS", SY, "IRRIGATION", "COUNTY", "17", "005", "2021", "YEAR", "60.0"],
        ]
        return ["\t".join(self.HDR) + "\n"] + ["\t".join(r) + "\n" for r in rows]

    def test_filter_multi(self):
        seen = {}
        got = list(S.nass_filter_multi(self._lines(), seen=seen))
        self.assertEqual(len(got), 3)
        self.assertEqual(got[0], {"fips": "19001", "year": 2020, "crop": "corn", "slot": "yield",
                                  "value": 180.5})
        self.assertEqual(got[1], {"fips": "19001", "year": 2020, "crop": "soy", "slot": "yield",
                                  "value": 55.1})
        self.assertEqual(got[2], {"fips": "17005", "year": 2021, "crop": "soy", "slot": "area",
                                  "value": 12300.0})
        # diagnostics count county SURVEY yield rows before the period/domain/value checks
        self.assertEqual(seen[S.SOY_YIELD_SHORT], 5)
        self.assertEqual(seen[D.CORN_YIELD_SHORT], 1)

    def test_collect(self):
        recs = [{"fips": "19001", "year": 2020, "crop": "soy", "slot": "yield", "value": 55.0},
                {"fips": "19001", "year": 2020, "crop": "soy", "slot": "yield", "value": 55.0},
                {"fips": "19001", "year": 2020, "crop": "soy", "slot": "yield", "value": 54.0},
                {"fips": "19001", "year": 2020, "crop": "corn", "slot": "yield", "value": 180.0}]
        out, conflicts = S.collect_nass(recs)
        self.assertEqual(conflicts, 1)
        self.assertEqual(out[("soy", "19001", 2020)], {"yield": 55.0})
        self.assertEqual(out[("corn", "19001", 2020)], {"yield": 180.0})


class TestWeatherHelpers(unittest.TestCase):
    def test_accumulate_rows(self):
        acc = {}
        S.season_accumulate(acc, ["19001"], [[1.0] * 41], [5.0], [0], 31, 3)
        S.season_accumulate(acc, ["19001"], [[2.0] * 41], [3.0], [1], 30, 4)
        rows = S.weather_rows(acc, 2020)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][:6], ["19001", 2020, "MarAug", 61, 1, 8.0])
        self.assertEqual(rows[0][6], 3.0)
        self.assertEqual(rows[1][:6], ["19001", 2020, "AprSep", 30, 1, 3.0])
        self.assertEqual(rows[1][-1], 2.0)
        self.assertEqual(len(rows[0]), 6 + 41)

    def test_ensure_weather_cached(self):
        d = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(d, "weather"))
            for y in (2024, 2025):
                with open(os.path.join(d, "weather", "w_%d.csv" % y), "w") as fh:
                    fh.write("x\n")
            self.assertEqual(S.ensure_weather(d, 2024, 2025, set()), os.path.join(d, "weather"))
        finally:
            shutil.rmtree(d)


class TestClassesAndGrades(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(S.did_class({"diff": 0.002, "p": 0.01}), "corn gained relative to soybeans")
        self.assertEqual(S.did_class({"diff": -0.002, "p": 0.01}), "corn lost relative to soybeans")
        self.assertEqual(S.did_class({"diff": 0.002, "p": 0.2}), "no detectable difference")
        self.assertEqual(S.did_class({"diff": 0.002, "p": float("nan")}), "no detectable difference")
        self.assertEqual(S.change_class({"diff": -0.001, "p": 0.04}), "worsened")
        self.assertEqual(S.change_class({"diff": 0.001, "p": 0.06}), "no detectable change")

    def _res(self, soy_b=-0.005):
        return {"joint": {"coef": {"corn:EDD_B": {"b": -0.008}}, "did_class": "no detectable difference"},
                "soy": {"coef": {"EDD_B": {"b": soy_b}}, "EDD_C_minus_B": {"diff": 0.001, "p": 0.4}},
                "soy_threshold_scan": {"B": {"best_b": 30}},
                "era_counts": {"soy": {"C": {"counties": 900}}},
                "census": {"soy": {"nass_counties_with_weather_share": 0.95, "nass_rows_2025": 450}}}

    def test_grade_all_hold(self):
        g = S.grade_soy(self._res())
        self.assertEqual(g["predictions_held"], 5)
        self.assertTrue(g["SG1_soy_eraC_counties_ge_800"] and g["SG2_soy_weather_match_ge_0.90"]
                        and g["SG3_soy_2025_rows_ge_400"])

    def test_grade_s3_fails(self):
        g = S.grade_soy(self._res(soy_b=-0.009))
        self.assertFalse(g["S3_holds_soy_less_sensitive_than_corn_B"])
        self.assertTrue(g["S2_holds_soy_B_in_range"])
        self.assertEqual(g["predictions_held"], 4)

    def test_common_rows(self):
        c = [{"fips": "a", "year": 1990}, {"fips": "b", "year": 1990}, {"fips": "a", "year": 2015}]
        s = [{"fips": "a", "year": 1991}, {"fips": "b", "year": 2016}]
        cc, ss, n = S.common_rows(c, s)
        self.assertEqual(n, 1)
        self.assertEqual(cc, [{"fips": "a", "year": 1990}])
        self.assertEqual(ss, [{"fips": "a", "year": 1991}])


@unittest.skipIf(np is None, "numpy not installed")
class TestJointModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cornheat_model as M
        cls.M = M
        rng = np.random.default_rng(0)
        truth = {"corn": ({"A": -0.005, "B": -0.007, "C": -0.004}, 29),
                 "soy": ({"A": -0.003, "B": -0.004, "C": -0.004}, 30)}
        cls.rows = {}
        for crop, (te, b) in truth.items():
            rows = []
            for s in ("17", "18", "19", "20"):
                for c in range(8):
                    f = s + "%03d" % (2 * c + 1)
                    alpha = rng.normal(4.0, 0.1)
                    for y in range(1951, 2026):
                        L = "A" if y <= 1980 else ("B" if y <= 2010 else "C")
                        g = rng.uniform(1000, 1600)
                        e = rng.uniform(0, 120)
                        p = rng.uniform(300, 700)
                        t = (y - 1990) / 10.0
                        ly = (alpha + 0.01 * int(s) * t + 0.0003 * g + te[L] * e
                              + 0.08 * (p / 100.0) - 0.006 * (p / 100.0) ** 2
                              + rng.normal(0, 0.005))
                        dd = np.zeros(41)
                        dd[b] = e
                        dd[10] = g + e
                        rows.append({"fips": f, "state": s, "year": y, "logy": ly,
                                     "dd": {"MarAug": dd, "AprSep": dd},
                                     "P": {"MarAug": p, "AprSep": p}})
            cls.rows[crop] = rows
        cls.sep = {"corn": M.fit(cls.rows["corn"], R.ERAS, b=29, season="MarAug"),
                   "soy": M.fit(cls.rows["soy"], R.ERAS, b=30, season="MarAug")}
        cls.joint = S.joint_fit([("corn", cls.rows["corn"], R.ERAS, 29, "MarAug"),
                                 ("soy", cls.rows["soy"], R.ERAS, 30, "MarAug")])

    def test_joint_equals_separate(self):
        for crop in ("corn", "soy"):
            for L in ("A", "B", "C"):
                for w in ("GDD", "EDD", "P", "P2"):
                    b_sep, se_sep = self.M.coef(self.sep[crop], "%s_%s" % (w, L))
                    b_j, se_j = self.M.coef(self.joint, "%s:%s_%s" % (crop, w, L))
                    self.assertAlmostEqual(b_j / b_sep, 1.0, places=6)
                    self.assertAlmostEqual(se_j / se_sep, 1.0, places=5)

    def test_recovery_and_did(self):
        b, _ = self.M.coef(self.joint, "soy:EDD_B")
        self.assertAlmostEqual(b, -0.004, places=4)
        d = S.contrast(self.joint, S.DID_W)
        self.assertAlmostEqual(d["diff"], 0.003, places=3)
        c = self.joint["names"].index
        arith = (self.joint["beta"][c("corn:EDD_C")] - self.joint["beta"][c("corn:EDD_B")]
                 - self.joint["beta"][c("soy:EDD_C")] + self.joint["beta"][c("soy:EDD_B")])
        self.assertAlmostEqual(d["diff"], float(arith), places=12)
        self.assertLess(d["p"], 0.05)
        self.assertEqual(S.did_class(d), "corn gained relative to soybeans")

    def test_single_crop_contrast_matches_diff_test(self):
        a = S.contrast(self.joint, {"soy:EDD_C": 1.0, "soy:EDD_B": -1.0})
        b = self.M.diff_test(self.sep["soy"], "EDD_C", "EDD_B")
        self.assertAlmostEqual(a["diff"], b["diff"], places=7)
        self.assertAlmostEqual(a["se"] / b["se"], 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
