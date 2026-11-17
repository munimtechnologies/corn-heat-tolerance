# test_dtstate.py - hand-checked tests for the by-state DT-adoption step (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import math
import unittest

import dtstate as T

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None


class TestDesign(unittest.TestCase):
    def test_groups(self):
        self.assertEqual(len(T.POOL), 9)
        self.assertFalse(set(T.HIGH) & set(T.LOW))
        self.assertFalse(set(T.MID) & set(T.POOL))
        for s in T.POOL + T.MID:
            self.assertIn(s, T.ERS_DT_2016)
            self.assertIn(s, T.STATE_NAME)
        self.assertEqual(T.STATE_NAME["31"], "Nebraska")
        self.assertEqual(T.ERS_DT_2016["20"], "39")

    def test_weights(self):
        w = T.ddd_weights()
        self.assertEqual(len(w), 8)
        self.assertEqual(w["cornH:EDD_C"], 1.0)
        self.assertEqual(w["cornH:EDD_B"], -1.0)
        self.assertEqual(w["soyH:EDD_C"], -1.0)
        self.assertEqual(w["soyH:EDD_B"], 1.0)
        self.assertEqual(w["cornL:EDD_C"], -1.0)
        self.assertEqual(w["cornL:EDD_B"], 1.0)
        self.assertEqual(w["soyL:EDD_C"], 1.0)
        self.assertEqual(w["soyL:EDD_B"], -1.0)
        self.assertEqual(sum(w.values()), 0.0)

    def test_placebos(self):
        ps = T.placebo_sets()
        self.assertEqual(len(ps), 36)
        self.assertEqual(len(set(ps)), 36)
        self.assertIn(("20", "31"), ps)

    def test_ri_p(self):
        self.assertAlmostEqual(T.ri_p(0.5, [0.5, 0.1, -0.2, 0.3]), 0.25)
        self.assertAlmostEqual(T.ri_p(0.2, [0.2, 0.1, -0.2, 0.3]), 0.75)
        self.assertAlmostEqual(T.ri_p(-0.4, [0.1] * 35 + [-0.4]), 1 / 36.0)

    def test_classes(self):
        self.assertEqual(T.ddd_class({"diff": 0.001, "p": 0.01}, 1 / 36.0), "high-adoption corn gained")
        self.assertEqual(T.ddd_class({"diff": -0.001, "p": 0.01}, 1 / 36.0), "high-adoption corn lost")
        self.assertEqual(T.ddd_class({"diff": 0.001, "p": 0.01}, 2 / 36.0), "no detectable difference")
        self.assertEqual(T.ddd_class({"diff": 0.001, "p": 0.2}, 1 / 36.0), "no detectable difference")
        self.assertEqual(T.ddd_class({"diff": 0.001, "p": float("nan")}, 1 / 36.0),
                         "no detectable difference")
        self.assertEqual(T.tercile_class({"diff": 0.001, "p": 0.04}), "dry-county corn gained")
        self.assertEqual(T.tercile_class({"diff": -0.001, "p": 0.04}), "dry-county corn lost")
        self.assertEqual(T.tercile_class({"diff": 0.001, "p": 0.06}), "no detectable difference")

    def test_terciles(self):
        rows = []
        for i, p in enumerate([100, 200, 300, 400, 500, 600, 700]):
            f = "19%03d" % (i + 1)
            rows.append({"fips": f, "year": 1990, "P": {"MarAug": p}})
            rows.append({"fips": f, "year": 1991, "P": {"MarAug": p + 10}})
            rows.append({"fips": f, "year": 2015, "P": {"MarAug": 0}})   # era C: ignored
        dry, wet, info = T.precip_terciles(rows)
        self.assertEqual(dry, {"19001", "19002"})
        self.assertEqual(wet, {"19006", "19007"})
        self.assertEqual(info["counties"], 7)
        self.assertEqual(info["per_tercile"], 2)
        self.assertAlmostEqual(info["dry_max_mm"], 205.0)
        self.assertAlmostEqual(info["wet_min_mm"], 605.0)

    def test_era_counties(self):
        rows = [{"fips": "a", "year": 2011}, {"fips": "a", "year": 2012}, {"fips": "b", "year": 2010}]
        self.assertEqual(T.era_counties(rows, ("C", 2011, 2025)), 1)
        self.assertEqual(T.era_counties(rows, ("B", 1981, 2010)), 1)

    def _res(self, t=0.0005, cls="no detectable difference", hb=-0.005, lb=-0.008,
             tcls="no detectable difference"):
        cnt = {"H": {"corn": {"C": 100}, "soy": {"C": 70}}, "L": {"corn": {"C": 500}, "soy": {"C": 450}}}
        return {"counts": cnt,
                "primary": {"class": cls, "T": t,
                            "coef": {"cornH:EDD_B": {"b": hb}, "cornL:EDD_B": {"b": lb}}},
                "terciles": {"class": tcls}}

    def test_grade(self):
        g = T.grade_dt(self._res())
        self.assertEqual(g["predictions_held"], 4)
        self.assertTrue(g["G1_high_corn_eraC_counties_ge_80"] and g["G2_high_soy_eraC_counties_ge_60"]
                        and g["G3_low_corn_eraC_counties_ge_300"])
        g = T.grade_dt(self._res(t=-0.001, hb=-0.009, tcls="dry-county corn lost"))
        self.assertEqual(g["predictions_held"], 1)
        self.assertTrue(g["D1_holds_no_detectable_difference"])
        self.assertFalse(g["D3_holds_high_less_heat_sensitive_B"])


@unittest.skipIf(np is None, "numpy not installed")
class TestSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(1)
        gain = {"A": -0.006, "B": -0.007, "C": -0.004}     # corn C-B = +0.003
        small = {"A": -0.006, "B": -0.007, "C": -0.006}    # corn C-B = +0.001
        flat = {"A": -0.004, "B": -0.004, "C": -0.004}     # soybeans: no change
        truth = {"corn": ({"20": gain, "31": gain, "17": small, "19": small}, 29),
                 "soy": ({"20": flat, "31": flat, "17": flat, "19": flat}, 30)}
        cls.rows = {}
        for crop, (te, b) in truth.items():
            rows = []
            for s in ("17", "19", "20", "31"):
                for c in range(6):
                    f = s + "%03d" % (2 * c + 1)
                    alpha = rng.normal(4.0, 0.1)
                    for y in range(1951, 2026):
                        L = "A" if y <= 1980 else ("B" if y <= 2010 else "C")
                        g = rng.uniform(1000, 1600)
                        e = rng.uniform(0, 120)
                        p = rng.uniform(300, 700)
                        t = (y - 1990) / 10.0
                        ly = (alpha + 0.01 * int(s) * t + 0.0003 * g + te[s][L] * e
                              + 0.08 * (p / 100.0) - 0.006 * (p / 100.0) ** 2
                              + rng.normal(0, 0.005))
                        dd = np.zeros(41)
                        dd[b] = e
                        dd[10] = g + e
                        rows.append({"fips": f, "state": s, "year": y, "logy": ly,
                                     "dd": {"MarAug": dd, "AprSep": dd},
                                     "P": {"MarAug": p, "AprSep": p}})
            cls.rows[crop] = rows
        cls.fit = T.ddd_fit(cls.rows["corn"], cls.rows["soy"],
                            lambda r: r["state"] in ("20", "31"), lambda r: r["state"] in ("17", "19"))

    def test_contrast_v(self):
        res = {"names": ["a", "b"], "beta": np.array([0.3, 0.1]),
               "V2": np.array([[0.04, 0.01], [0.01, 0.09]])}
        c = T.contrast_v(res, {"a": 1.0, "b": -1.0}, "V2")
        self.assertAlmostEqual(c["diff"], 0.2)
        self.assertAlmostEqual(c["se"], math.sqrt(0.11))

    def test_recovery(self):
        f = self.fit
        self.assertAlmostEqual(f["T"], 0.002, places=3)
        self.assertLess(f["T_year"]["p"], 0.05)
        self.assertAlmostEqual(f["did_H_year"]["diff"], 0.003, places=3)
        self.assertAlmostEqual(f["did_L_year"]["diff"], 0.001, places=3)
        self.assertAlmostEqual(f["T"], f["did_H_year"]["diff"] - f["did_L_year"]["diff"], places=12)
        self.assertAlmostEqual(f["T"], f["T_twoway"]["diff"], places=12)
        self.assertAlmostEqual(f["coef"]["cornH:EDD_B"]["b"], -0.007, places=4)
        self.assertAlmostEqual(f["coef"]["soyL:EDD_C"]["b"], -0.004, places=4)
        self.assertEqual(f["rows"]["cornH"], 2 * 6 * 75)

    def test_randomization_small_pool(self):
        ri = T.randomization(self.rows["corn"], self.rows["soy"], pool=("17", "19", "20", "31"),
                             high=("20", "31"))
        self.assertEqual(len(ri["placebos"]), 6)
        self.assertAlmostEqual(ri["T_obs"], self.fit["T"], places=12)
        # the mirror split (17,19 high) gives -T; the four mixed splits are near 0
        self.assertAlmostEqual(ri["p"], 2 / 6.0)

    def test_state_did(self):
        d = T.state_did(self.rows["corn"], self.rows["soy"], "20")
        self.assertAlmostEqual(d["diff"], 0.003, places=3)
        self.assertEqual(d["corn_rows"], 6 * 75)
        self.assertIsNone(T.state_did(self.rows["corn"], self.rows["soy"], "55"))

    def test_empty_block(self):
        with self.assertRaises(ValueError):
            T.ddd_fit(self.rows["corn"], self.rows["soy"],
                      lambda r: r["state"] == "55", lambda r: r["state"] == "17")


if __name__ == "__main__":
    unittest.main()
