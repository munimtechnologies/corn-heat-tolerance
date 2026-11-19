# test_rcheck.py - hand-checked tests for the 0.6.0 replication step (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import unittest

import rcheck as RC

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None


class TestDesign(unittest.TestCase):
    def test_states_windows(self):
        self.assertEqual(len(RC.MW12), 12)
        self.assertEqual(len(set(RC.MW12)), 12)
        for e in (RC.E1, RC.L1, RC.E2, RC.L2):
            self.assertEqual(e[2] - e[1] + 1, 30)
        self.assertEqual(RC.E1[1], 1960)
        self.assertEqual(RC.L1[2], 2019)
        self.assertEqual(RC.L2[2], 2025)
        self.assertEqual(RC.E1[0], RC.E2[0])
        self.assertEqual(RC.L1[0], RC.L2[0])
        self.assertTrue(set(RC.MW12) >= set(RC.DT.POOL))

    def test_weights(self):
        self.assertEqual(RC.change_weights(), {"EDD_L": 1.0, "EDD_E": -1.0})
        self.assertEqual(RC.change_weights("corn"), {"corn:EDD_L": 1.0, "corn:EDD_E": -1.0})
        self.assertEqual(RC.did_weights("corn", "soy"),
                         {"corn:EDD_L": 1.0, "corn:EDD_E": -1.0, "soy:EDD_L": -1.0, "soy:EDD_E": 1.0})
        t = RC.sub_weights(RC.did_weights("cornW", "soyW"), RC.did_weights("cornK", "soyK"))
        self.assertEqual(len(t), 8)
        self.assertEqual(t["cornW:EDD_L"], 1.0)
        self.assertEqual(t["cornK:EDD_L"], -1.0)
        self.assertEqual(t["soyK:EDD_L"], 1.0)
        self.assertEqual(t["soyK:EDD_E"], -1.0)
        self.assertEqual(sum(t.values()), 0.0)

    def test_classes(self):
        self.assertEqual(RC.rise_class({"diff": -0.001, "p": 0.01}), "rise replicated")
        self.assertEqual(RC.rise_class({"diff": -0.001, "p": 0.3}), "rise in direction only")
        self.assertEqual(RC.rise_class({"diff": 0.001, "p": 0.01}), "fall")
        self.assertEqual(RC.rise_class({"diff": 0.001, "p": 0.3}), "no rise")
        self.assertEqual(RC.rise_class({"diff": -0.001, "p": float("nan")}), "rise in direction only")
        self.assertEqual(RC.warm_class({"diff": -0.002, "p": 0.04}), "warming counties lost")
        self.assertEqual(RC.warm_class({"diff": 0.002, "p": 0.04}), "warming counties gained")
        self.assertEqual(RC.warm_class({"diff": 0.002, "p": 0.06}), "no detectable difference")

    def test_quantile(self):
        self.assertAlmostEqual(RC.quantile([5, 1, 3, 2, 4], 0.25), 2.0)
        self.assertAlmostEqual(RC.quantile([1, 2, 3, 4, 5], 0.5), 3.0)
        self.assertAlmostEqual(RC.quantile([1, 2], 0.5), 1.5)
        self.assertAlmostEqual(RC.quantile([7], 0.75), 7.0)
        self.assertIsNone(RC.quantile([], 0.5))

    def test_temp_trends(self):
        rows = []
        for y in range(1960, 2020):
            rows.append({"fips": "19001", "year": y, "dd": {"MarAug": [184.0 * (12.0 + 0.05 * (y - 1960))]}})
            rows.append({"fips": "19003", "year": y, "dd": {"MarAug": [184.0 * (14.0 - 0.01 * (y - 1960))]}})
        for y in range(1960, 1970):      # only 10 years: dropped
            rows.append({"fips": "19005", "year": y, "dd": {"MarAug": [184.0 * 13.0]}})
        rows.append({"fips": "19001", "year": 2024, "dd": {"MarAug": [0.0]}})   # outside the window
        tr = RC.temp_trends(rows, 1960, 2019)
        self.assertEqual(set(tr), {"19001", "19003"})
        self.assertAlmostEqual(tr["19001"], 0.5, places=6)
        self.assertAlmostEqual(tr["19003"], -0.1, places=6)
        self.assertAlmostEqual(RC.tbar(rows[0]), 12.0)

    def test_terciles(self):
        tr = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.4, "e": 0.5, "f": 0.6, "g": 0.7}
        warm, cool, info = RC.trend_terciles(tr)
        self.assertEqual(cool, {"a", "b"})
        self.assertEqual(warm, {"f", "g"})
        self.assertEqual(info["counties"], 7)
        self.assertEqual(info["per_tercile"], 2)
        self.assertAlmostEqual(info["cool_max_C_per_decade"], 0.2)
        self.assertAlmostEqual(info["warm_min_C_per_decade"], 0.6)
        self.assertAlmostEqual(info["median_C_per_decade"], 0.4)

    def _res(self, d1=-0.001, c1="rise in direction only", dcls="no detectable difference",
             d3=-0.0005, c3="rise in direction only", w4=-0.001,
             wcls="no detectable difference", tcls="no detectable difference"):
        return {"rc1_corn_mw12": {"counties": {"L": 800}, "change": {"diff": d1}, "class": c1},
                "rc2_joint_mw12": {"counties": {"soy": {"L": 600}}, "did_class": dcls},
                "rc3_corn_mw12_to2025": {"change": {"diff": d3}, "class": c3},
                "rc45_mechanism": {"W4": {"diff": w4}, "W4_class": wcls, "T4_class": tcls},
                "terciles": {"per_tercile": 250}}

    def test_grade(self):
        g = RC.grade_rc(self._res())
        self.assertEqual(g["predictions_held"], 5)
        self.assertTrue(g["RG1_corn_L_counties_ge_500"] and g["RG2_soy_L_counties_ge_400"]
                        and g["RG3_tercile_counties_ge_100"])
        g = RC.grade_rc(self._res(d1=0.001, c1="no rise", dcls="corn lost relative to soybeans",
                                  w4=0.001, tcls="warming counties lost"))
        self.assertEqual(g["predictions_held"], 1)
        self.assertFalse(g["RC1_holds_rise_direction"])
        self.assertTrue(g["RC3_holds_rise_direction_to2025"])
        self.assertEqual(g["RC2_class"], "corn lost relative to soybeans")


@unittest.skipIf(np is None, "numpy not installed")
class TestSynthetic(unittest.TestCase):
    """24 counties in 4 states, 1951-2025. Corn's EDD effect is -0.006, except in
    the 8 fastest-warming counties from 1990 on, where it is -0.009. Soybeans' is
    -0.004 throughout. Season mean temperature trends are exact by construction."""

    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(7)
        cls.rows = {"corn": [], "soy": []}
        cls.warm_truth, cls.cool_truth = set(), set()
        for j, s in enumerate(("17", "19", "27", "31")):
            for c in range(6):
                f = s + "%03d" % (2 * c + 1)
                slope = 0.6 - 0.16 * c + 0.001 * j          # deg C per decade
                if c < 2:
                    cls.warm_truth.add(f)
                if c > 3:
                    cls.cool_truth.add(f)
                alpha = {"corn": rng.normal(4.0, 0.1), "soy": rng.normal(3.0, 0.1)}
                for y in range(1951, 2026):
                    t = (y - 1990) / 10.0
                    tb = 15.0 + slope * (y - 1960) / 10.0
                    for crop, b in (("corn", 29), ("soy", 30)):
                        if crop == "corn":
                            beta = -0.009 if (y >= 1990 and c < 2) else -0.006
                        else:
                            beta = -0.004
                        g = rng.uniform(1000, 1600)
                        e = rng.uniform(0, 120)
                        p = rng.uniform(300, 700)
                        ly = (alpha[crop] + 0.01 * int(s) * t + 0.0003 * g + beta * e
                              + 0.08 * (p / 100.0) - 0.006 * (p / 100.0) ** 2
                              + rng.normal(0, 0.005))
                        dd = np.zeros(41)
                        dd[0] = 184.0 * tb
                        dd[b] = e
                        dd[10] = g + e
                        cls.rows[crop].append({"fips": f, "state": s, "year": y, "logy": ly,
                                               "dd": {"MarAug": dd, "AprSep": dd},
                                               "P": {"MarAug": p, "AprSep": p}})

    def test_terciles_recover(self):
        tr = RC.temp_trends(self.rows["corn"], 1960, 2019)
        self.assertEqual(len(tr), 24)
        self.assertAlmostEqual(tr["17001"], 0.6, places=6)
        warm, cool, info = RC.trend_terciles(tr)
        self.assertEqual(warm, self.warm_truth)
        self.assertEqual(cool, self.cool_truth)
        self.assertEqual(info["per_tercile"], 8)

    def test_pair_fit(self):
        rows = [r for r in self.rows["corn"] if r["fips"] in self.warm_truth]
        pf = RC.pair_fit(rows, RC.PAIR1, 29)
        self.assertAlmostEqual(pf["EDD_E"]["b"], -0.006, places=4)
        self.assertAlmostEqual(pf["EDD_L"]["b"], -0.009, places=4)
        self.assertAlmostEqual(pf["ratio_L_over_E"], 1.5, delta=0.02)
        self.assertAlmostEqual(pf["change"]["diff"], -0.003, places=3)
        self.assertEqual(pf["class"], "rise replicated")
        self.assertEqual(pf["counties"], {"E": 8, "L": 8})
        self.assertEqual(pf["windows"], {"E": [1960, 1989], "L": [1990, 2019]})
        self.assertIn("year", pf["change"])

    def test_pair_joint(self):
        pj = RC.pair_joint(self.rows["corn"], self.rows["soy"], RC.PAIR1)
        self.assertLess(pj["did"]["diff"], 0)
        self.assertAlmostEqual(pj["soy_change"]["diff"], 0.0, places=3)
        self.assertAlmostEqual(pj["coef"]["soy:EDD_E"]["b"], -0.004, places=4)
        self.assertEqual(pj["counties"]["corn"]["L"], 24)
        self.assertEqual(pj["counties"]["soy"]["E"], 24)
        self.assertIn("year", pj["did"])

    def test_mechanism(self):
        m = RC.mechanism(self.rows["corn"], self.rows["soy"], self.warm_truth, self.cool_truth)
        self.assertAlmostEqual(m["W4"]["diff"], -0.003, places=3)
        self.assertAlmostEqual(m["T4"]["diff"], -0.003, places=3)
        self.assertAlmostEqual(m["soy_warm_minus_cool"]["diff"], 0.0, places=3)
        self.assertAlmostEqual(m["coef"]["cornW:EDD_L"], -0.009, places=4)
        self.assertAlmostEqual(m["coef"]["cornK:EDD_L"], -0.006, places=4)
        self.assertEqual(m["rows"]["cornW"], 8 * 60)
        self.assertEqual(m["W4_class"], "warming counties lost")

    def test_rolling(self):
        ro = RC.rolling30(self.rows["soy"], 30, starts=(1960, 1990), min_rows=10)
        self.assertEqual([x["years"] for x in ro], [[1960, 1989], [1990, 2019]])
        self.assertAlmostEqual(ro[0]["EDD"], -0.004, places=4)
        self.assertEqual(ro[1]["counties"], 24)

    def test_dt_trend_trim(self):
        tr = RC.temp_trends(self.rows["corn"], 1981, 2025)
        d = RC.dt_trend_trim(self.rows["corn"], self.rows["soy"], tr,
                             pool=("17", "19", "27", "31"), high=("31",), low=("17", "19", "27"))
        self.assertEqual(d["counties_kept"], 12)
        self.assertAlmostEqual(d["mean_trend_high_all"], 0.203, places=6)
        self.assertIn("T", d)
        self.assertEqual(d["rows"]["cornH"], 3 * 75)


if __name__ == "__main__":
    unittest.main()
