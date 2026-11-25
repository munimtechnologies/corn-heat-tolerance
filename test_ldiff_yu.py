# test_ldiff_yu.py - hand-checked tests for step 0.7.1 (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import unittest

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None

if np is not None:
    import ldiff_yu as YU
    import ldiff as LD
else:
    YU = LD = None


def dd_array(gdd0, edd):
    """41 thresholds; only dd[0] and dd[29] matter to the Yu specification."""
    a = [0.0] * 41
    a[29] = float(edd)
    a[10] = 0.5 * float(gdd0) + float(edd)     # deliberately different: must be ignored
    a[0] = float(gdd0) + float(edd)
    return a


def row(fips, year, logy, gdd0, edd, p_mm):
    dd = dd_array(gdd0, edd)
    return {"fips": fips, "state": fips[:2], "year": year, "logy": logy,
            "dd": {"AprSep": dd, "MarAug": [0.0] * 41}, "P": {"AprSep": p_mm, "MarAug": 0.0}}


@unittest.skipIf(np is None, "numpy not installed")
class TestDesign(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(YU.YU_SEASON, "AprSep")
        self.assertEqual(YU.YU_B, 29)
        self.assertEqual(YU.P0_CM, 42.0)
        self.assertEqual(YU.YU_MIN_YEARS, 1)
        self.assertEqual(YU.BAND, (-0.90, -0.30))
        self.assertEqual(YU.YU_REPORTED, {"corn": -0.58, "soy": -0.55})
        self.assertEqual(LD.PRIMARY, ((1958, 1962), (2013, 2017)))

    def test_weather_vec_yu(self):
        dd = [0.0] * 41
        dd[0], dd[10], dd[29], dd[30] = 3000.0, 1300.0, 80.0, 60.0
        wet = {"dd": {"AprSep": dd}, "P": {"AprSep": 450.0}}
        dry = {"dd": {"AprSep": dd}, "P": {"AprSep": 300.0}}
        edge = {"dd": {"AprSep": dd}, "P": {"AprSep": 420.0}}
        self.assertEqual(YU.weather_vec_yu(wet), [2920.0, 80.0, 0.0, 3.0])
        self.assertEqual(YU.weather_vec_yu(dry), [2920.0, 80.0, 12.0, 0.0])
        self.assertEqual(YU.weather_vec_yu(edge), [2920.0, 80.0, 0.0, 0.0])

    def test_hinge_is_per_year_then_averaged(self):
        # 300 mm and 540 mm average to 420 mm (no shortfall), but per year the
        # shortfall is 12 and 0 cm and the excess 0 and 12 cm: means 6 and 6.
        rows = [row("19001", 1958, 1.0, 2000, 50, 300),
                row("19001", 1959, 3.0, 2000, 50, 540)]
        m = YU.period_means_yu(rows, (1958, 1962))
        a = m["19001"]
        self.assertEqual(a["n"], 2)
        self.assertAlmostEqual(a["y"], 2.0)
        self.assertAlmostEqual(a["w"][0], 2000.0)
        self.assertAlmostEqual(a["w"][1], 50.0)
        self.assertAlmostEqual(a["w"][2], 6.0)
        self.assertAlmostEqual(a["w"][3], 6.0)

    def test_min_years(self):
        rows = [row("19001", 1958, 1.0, 2000, 50, 500),
                row("19003", 1958, 1.0, 2000, 50, 500),
                row("19003", 1959, 1.0, 2000, 50, 500),
                row("19003", 1960, 1.0, 2000, 50, 500),
                row("19003", 1960, 9.0, 2000, 50, 500)]   # duplicate year: ignored
        self.assertEqual(set(YU.period_means_yu(rows, (1958, 1962))), {"19001", "19003"})
        self.assertEqual(set(YU.period_means_yu(rows, (1958, 1962), min_years=3)), {"19003"})
        self.assertAlmostEqual(YU.period_means_yu(rows, (1958, 1962))["19003"]["y"], 1.0)

    def test_ld_records_yu(self):
        rows = [row("17001", 1958, 4.0, 2000, 50, 400),
                row("17003", 1958, 4.0, 2000, 50, 400),
                row("17001", 2013, 5.0, 2100, 70, 500)]
        recs = YU.ld_records_yu(rows, LD.PRIMARY)
        self.assertEqual([r["fips"] for r in recs], ["17001"])
        r = recs[0]
        self.assertAlmostEqual(r["dy"], 1.0)
        self.assertAlmostEqual(r["dw"][0], 100.0)
        self.assertAlmostEqual(r["dw"][1], 20.0)
        self.assertAlmostEqual(r["dw"][2], -2.0)     # shortfall 2 cm -> 0
        self.assertAlmostEqual(r["dw"][3], 8.0)      # excess 0 -> 8 cm
        self.assertAlmostEqual(r["w1"][3], 8.0)

    def test_relabel(self):
        fit = {"coef": {n: {"b": float(i)} for i, n in enumerate(
            ["dGDD", "dEDD", "dP", "dP2", "GDD_1", "EDD_1", "P_1", "P2_1"])},
            "eta_over_beta_EDD": 5.0, "names": []}
        r = YU.relabel(fit)
        self.assertEqual(r["names"], ["dGDD0_29", "dEDD", "dPshort42", "dPexcess42",
                                      "GDD0_29_1", "EDD_1", "Pshort42_1", "Pexcess42_1"])
        self.assertEqual(r["coef"]["EDD_1"]["b"], 5.0)
        self.assertEqual(r["coef"]["dEDD"]["b"], 1.0)
        self.assertEqual(r["eta_over_beta_EDD"], 5.0)

    def _fit(self, eta, beta=-0.006, states=30):
        return {"coef": {"dEDD": {"b": beta}, "EDD_1": {"b": eta, "p": 0.01}},
                "eta_over_beta_EDD": eta / beta, "states": states}

    def _res(self, cA, cB, sA, sB, pairs, nc=900, ns=500):
        return {"corn": {"counties": nc, "A": cA, "B": cB},
                "soy": {"counties": ns, "A": sA, "B": sB},
                "corn_pairs20": pairs}

    def test_grade(self):
        # corn A: eta/beta = 0.0036 / -0.006 = -0.6 (in band); B: 0.0006/-0.006 = -0.1
        # soy A: 0.0012 / -0.006 = -0.2 (outside band); B: 0.0009 (> half of 0.0012)
        res = self._res(self._fit(0.0036), self._fit(0.0006), self._fit(0.0012), self._fit(0.0009),
                        {"mean_A": -0.4, "mean_B": -0.1})
        g = YU.grade_yu(res)
        self.assertTrue(g["YG1_corn_counties_ge_800"] and g["YG2_soy_counties_ge_400"]
                        and g["YG3_corn_states_ge_15"])
        self.assertTrue(g["YX1_holds_corn_A_replicates_magnitude"])
        self.assertFalse(g["YX2_holds_soy_A_replicates_magnitude"])
        self.assertTrue(g["YX3_holds_corn_shrinks_within_state"])
        self.assertFalse(g["YX4_holds_soy_shrinks_within_state"])
        self.assertTrue(g["YX5_holds_corn_pairs20_shrink_within_state"])
        self.assertEqual(g["predictions_held"], 3)
        self.assertAlmostEqual(g["corn_eta_over_beta_A"], -0.6)

        # heat helps under A (beta > 0): never a replication, even if eta/beta is in band
        res = self._res(self._fit(-0.0036, beta=0.006), self._fit(0.0006), self._fit(0.0048),
                        self._fit(0.0), {"mean_A": -0.4, "mean_B": -0.3}, nc=700, ns=300)
        g = YU.grade_yu(res)
        self.assertFalse(g["YG1_corn_counties_ge_800"])
        self.assertFalse(g["YG2_soy_counties_ge_400"])
        self.assertFalse(g["YX1_holds_corn_A_replicates_magnitude"])
        self.assertTrue(g["YX2_holds_soy_A_replicates_magnitude"])     # -0.8
        self.assertFalse(g["YX3_holds_corn_shrinks_within_state"])     # eta_A < 0
        self.assertTrue(g["YX4_holds_soy_shrinks_within_state"])       # 0 < 0.5 * 0.0048
        self.assertFalse(g["YX5_holds_corn_pairs20_shrink_within_state"])   # -0.3 < -0.2
        self.assertEqual(g["predictions_held"], 2)

    def test_band_and_pairs_edges(self):
        self.assertTrue(YU.in_band(-0.90))
        self.assertTrue(YU.in_band(-0.30))
        self.assertFalse(YU.in_band(-0.29))
        self.assertFalse(YU.in_band(None))
        self.assertTrue(YU.pairs_shrink({"mean_A": -0.4, "mean_B": 0.2}))
        self.assertFalse(YU.pairs_shrink({"mean_A": 0.1, "mean_B": 0.0}))
        self.assertFalse(YU.pairs_shrink({"mean_A": None, "mean_B": 0.0}))


STATES = ("17", "19", "27", "31")
BETA = (0.0002, -0.006, -0.01, -0.002)


def synth(eta, delta_by_state, edd_level, seed):
    """24 counties in 4 states, years of LD.PRIMARY only, no noise. Yearly log yield =
    alpha_c + 1[later] * delta_s + sum_k (BETA_k + 1[later] * eta_k) * w_k with w the
    Yu variables of that year, so period means obey dy = delta_s + BETA.dw + eta.w1."""
    rng = np.random.default_rng(seed)
    rows = []
    for j, s in enumerate(STATES):
        for c in range(6):
            f = s + "%03d" % (2 * c + 1)
            alpha = rng.normal(4.0, 0.2)
            for k, (y0, y1) in enumerate(LD.PRIMARY):
                for y in range(y0, y1 + 1):
                    gdd0 = rng.uniform(1000, 1600)     # same scale as test_ldiff (conditioning)
                    edd = edd_level[j] + rng.uniform(-5, 5) if edd_level else rng.uniform(0, 120)
                    p = rng.uniform(250, 650)
                    r = row(f, y, 0.0, gdd0, edd, p)
                    w = YU.weather_vec_yu(r)
                    ly = alpha + (delta_by_state[j] if k else 0.0)
                    ly += sum((BETA[i] + (eta[i] if k else 0.0)) * w[i] for i in range(4))
                    r["logy"] = ly
                    rows.append(r)
    return rows


@unittest.skipIf(np is None, "numpy not installed")
class TestSynthetic(unittest.TestCase):
    def test_true_change_recovered_by_both(self):
        eta = (-0.0001, 0.003, 0.004, 0.001)
        rows = synth(eta, (0.4, 0.4, 0.4, 0.4), None, seed=11)
        s = YU.summary_yu(rows, LD.PRIMARY)
        self.assertEqual(s["counties"], 24)
        self.assertEqual(s["by_state"], {st: 6 for st in STATES})
        for m in ("A", "B"):
            f = s[m]
            self.assertAlmostEqual(f["coef"]["dGDD0_29"]["b"], BETA[0], places=6)
            self.assertAlmostEqual(f["coef"]["dEDD"]["b"], BETA[1], places=6)
            self.assertAlmostEqual(f["coef"]["dPshort42"]["b"], BETA[2], places=6)
            self.assertAlmostEqual(f["coef"]["Pexcess42_1"]["b"], eta[3], places=6)
            self.assertAlmostEqual(f["coef"]["EDD_1"]["b"], eta[1], places=6)
            self.assertAlmostEqual(f["eta_over_beta_EDD"], -0.5, places=4)

    def test_convergence_fakes_a_fall_only_without_state_effects(self):
        level = (20.0, 60.0, 100.0, 140.0)
        rows = synth((0.0, 0.0, 0.0, 0.0), tuple(0.002 * h for h in level), level, seed=5)
        s = YU.summary_yu(rows, LD.PRIMARY)
        fa, fb = s["A"], s["B"]
        self.assertAlmostEqual(fb["coef"]["EDD_1"]["b"], 0.0, places=6)
        self.assertAlmostEqual(fb["coef"]["dEDD"]["b"], -0.006, places=6)
        self.assertGreater(fa["coef"]["EDD_1"]["b"], 0.0015)
        self.assertTrue(LD.sensitivity_fell(fa))
        self.assertTrue(LD.shrank(fa, fb))

    def test_pairs20_reports_errors_without_data(self):
        rows = synth((0.0, 0.0, 0.0, 0.0), (0.4, 0.4, 0.4, 0.4), None, seed=3)
        p = YU.pairs20_yu(rows)          # synthetic rows exist only in the primary years
        self.assertEqual(len(p["pairs"]), 4)
        self.assertEqual(p["n_ok"], 0)
        self.assertIsNone(p["mean_A"])
        self.assertTrue(all("error" in x for x in p["pairs"]))


if __name__ == "__main__":
    unittest.main()
