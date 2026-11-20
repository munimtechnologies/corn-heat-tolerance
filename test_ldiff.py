# test_ldiff.py - hand-checked tests for the 0.7.0 long-difference step (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import unittest

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None

if np is not None:
    import ldiff as LD
else:
    LD = None


def dd_array(gdd, edd, b=29):
    """41 thresholds; only dd[10] and dd[b] matter to the model."""
    a = [0.0] * 41
    a[b] = float(edd)
    a[10] = float(gdd) + float(edd)
    return a


def row(fips, year, logy, gdd, edd, p_mm, b=29):
    dd = dd_array(gdd, edd, b)
    return {"fips": fips, "state": fips[:2], "year": year, "logy": logy,
            "dd": {"MarAug": dd, "AprSep": dd}, "P": {"MarAug": p_mm, "AprSep": p_mm}}


@unittest.skipIf(np is None, "numpy not installed")
class TestDesign(unittest.TestCase):
    def test_constants(self):
        self.assertEqual(LD.PRIMARY, ((1958, 1962), (2013, 2017)))
        self.assertEqual(LD.PRIMARY[1][0] - LD.PRIMARY[0][0], 55)
        self.assertEqual(LD.EXTENDED[1], (2021, 2025))
        for p0, p1 in LD.PAIRS20 + (LD.PRIMARY, LD.EXTENDED):
            self.assertEqual(p0[1] - p0[0], 4)
            self.assertEqual(p1[1] - p1[0], 4)
        for p0, p1 in LD.PAIRS20:
            self.assertEqual(p1[0] - p0[0], 20)
        self.assertEqual(len(set(LD.MW12)), 12)
        self.assertEqual(LD.B_CROP, {"corn": 29, "soy": 30})
        self.assertEqual(LD.MIN_YEARS, 3)

    def test_weather_vec(self):
        dd = [0.0] * 41
        dd[10], dd[29], dd[30] = 1300.0, 80.0, 60.0
        r = {"dd": {"MarAug": dd}, "P": {"MarAug": 450.0}}
        self.assertEqual(LD.weather_vec(r, 29), [1220.0, 80.0, 4.5, 20.25])
        self.assertEqual(LD.weather_vec(r, 30), [1240.0, 60.0, 4.5, 20.25])

    def test_period_means(self):
        rows = [row("19001", 1958, 1.0, 1000, 100, 500),
                row("19001", 1959, 2.0, 1000, 100, 700),
                row("19001", 1960, 3.0, 1000, 100, 600),
                row("19001", 1960, 9.0, 1000, 100, 600),    # duplicate year: ignored
                row("19001", 1963, 9.0, 1000, 100, 600),    # outside the period
                row("19003", 1958, 1.0, 1000, 100, 500),    # only two years: dropped
                row("19003", 1961, 1.0, 1000, 100, 500)]
        m = LD.period_means(rows, (1958, 1962), 29)
        self.assertEqual(set(m), {"19001"})
        a = m["19001"]
        self.assertEqual(a["n"], 3)
        self.assertEqual(a["state"], "19")
        self.assertAlmostEqual(a["y"], 2.0)
        self.assertAlmostEqual(a["w"][0], 1000.0)
        self.assertAlmostEqual(a["w"][1], 100.0)
        self.assertAlmostEqual(a["w"][2], 6.0)
        self.assertAlmostEqual(a["w"][3], 110.0 / 3.0)
        m2 = LD.period_means(rows, (1958, 1962), 29, min_years=2)
        self.assertEqual(set(m2), {"19001", "19003"})

    def test_ld_records(self):
        rows = []
        for y in (1958, 1959, 1960):
            rows.append(row("17001", y, 4.0, 1200, 50, 400))
            rows.append(row("17003", y, 4.0, 1200, 50, 400))
        for y in (2013, 2014, 2015, 2016):
            rows.append(row("17001", y, 5.0, 1250, 70, 500))
        recs = LD.ld_records(rows, LD.PRIMARY, 29)
        self.assertEqual([r["fips"] for r in recs], ["17001"])
        r = recs[0]
        self.assertAlmostEqual(r["dy"], 1.0)
        self.assertAlmostEqual(r["y0"], 4.0)
        self.assertAlmostEqual(r["dw"][0], 50.0)
        self.assertAlmostEqual(r["dw"][1], 20.0)
        self.assertAlmostEqual(r["dw"][2], 1.0)
        self.assertAlmostEqual(r["dw"][3], 9.0)
        self.assertAlmostEqual(r["w1"][1], 70.0)
        self.assertEqual(r["state"], "17")

    def _fit(self, eA, bA=-0.006, pA=0.01, eB=0.0005, bB=-0.006, pB=0.4):
        return ({"coef": {"dEDD": {"b": bA}, "EDD_1": {"b": eA, "p": pA}},
                 "eta_over_beta_EDD": eA / bA, "states": 30},
                {"coef": {"dEDD": {"b": bB}, "EDD_1": {"b": eB, "p": pB}},
                 "eta_over_beta_EDD": eB / bB, "states": 30})

    def _res(self, corn, soy, nc=900, ns=500):
        return {"corn": {"counties": nc, "A": corn[0], "B": corn[1]},
                "soy": {"counties": ns, "A": soy[0], "B": soy[1]}}

    def test_grade(self):
        res = self._res(self._fit(0.003), self._fit(0.002, bA=-0.004, eB=0.0012, bB=-0.004))
        g = LD.grade_ld(res)
        self.assertTrue(g["LG1_corn_counties_ge_800"] and g["LG2_soy_counties_ge_400"]
                        and g["LG3_corn_states_ge_15"])
        self.assertTrue(g["LD1_holds_corn_fell_A"])
        self.assertTrue(g["LD2_holds_soy_fell_A"])
        self.assertTrue(g["LD3_holds_corn_shrinks_within_state"])
        self.assertFalse(g["LD4_holds_soy_shrinks_within_state"])
        self.assertTrue(g["LD5_holds_corn_no_detectable_fall_B"])
        self.assertEqual(g["predictions_held"], 4)
        self.assertAlmostEqual(g["corn_eta_over_beta_A"], -0.5)

        res = self._res(self._fit(-0.001, eB=0.0025, pB=0.001),
                        self._fit(0.002, bA=-0.004, eB=0.0012, bB=-0.004), nc=700, ns=300)
        g = LD.grade_ld(res)
        self.assertFalse(g["LG1_corn_counties_ge_800"])
        self.assertFalse(g["LG2_soy_counties_ge_400"])
        self.assertFalse(g["LD1_holds_corn_fell_A"])
        self.assertFalse(g["LD3_holds_corn_shrinks_within_state"])
        self.assertFalse(g["LD5_holds_corn_no_detectable_fall_B"])
        self.assertEqual(g["predictions_held"], 1)

    def test_reconcile(self):
        rc_t, rc_f = {"RC1_holds_rise_direction": True}, {"RC1_holds_rise_direction": False}

        def ld(fell, shr):
            return {"LD1_holds_corn_fell_A": fell, "LD3_holds_corn_shrinks_within_state": shr}

        self.assertEqual(LD.reconcile(rc_t, ld(True, True)),
                         "reconciled: the long-difference fall is between-state")
        self.assertEqual(LD.reconcile(rc_t, ld(True, False)), "conflict persists within states")
        self.assertEqual(LD.reconcile(rc_t, ld(False, False)),
                         "no conflict on this data: long differences show no fall")
        self.assertEqual(LD.reconcile(rc_f, ld(True, True)),
                         "no conflict on this data: year-to-year sensitivity did not rise")
        self.assertEqual(LD.reconcile(rc_f, ld(False, True)), "neither published direction on this data")


STATES = ("17", "19", "27", "31")
BETA = (0.0003, -0.006, 0.08, -0.006)


def synth(eta, delta_by_state, edd_level, seed):
    """24 counties in 4 states, years of LD.PRIMARY only. Yearly log yield =
    alpha_c + 1[later] * delta_s + sum_k (BETA_k + 1[later] * eta_k) * w_k, no noise,
    so period means obey dy = delta_s + BETA . dw + eta . w1 exactly."""
    rng = np.random.default_rng(seed)
    rows = []
    for j, s in enumerate(STATES):
        for c in range(6):
            f = s + "%03d" % (2 * c + 1)
            alpha = rng.normal(4.0, 0.2)
            for k, (y0, y1) in enumerate(LD.PRIMARY):
                for y in range(y0, y1 + 1):
                    gdd = rng.uniform(1000, 1600)
                    edd = edd_level[j] + rng.uniform(-5, 5) if edd_level else rng.uniform(0, 120)
                    p = rng.uniform(300, 700)
                    w = (gdd, edd, p / 100.0, (p / 100.0) ** 2)
                    ly = alpha + (delta_by_state[j] if k else 0.0)
                    ly += sum((BETA[i] + (eta[i] if k else 0.0)) * w[i] for i in range(4))
                    rows.append(row(f, y, ly, gdd, edd, p))
    return rows


@unittest.skipIf(np is None, "numpy not installed")
class TestSynthetic(unittest.TestCase):
    def test_true_change_recovered_by_both(self):
        eta = (-0.0001, 0.003, 0.01, -0.001)
        rows = synth(eta, (0.4, 0.4, 0.4, 0.4), None, seed=11)
        recs = LD.ld_records(rows, LD.PRIMARY, 29)
        self.assertEqual(len(recs), 24)
        for fe in ("none", "state"):
            f = LD.fit_ld(recs, fe)
            for i, w in enumerate(LD.WNAMES):
                self.assertAlmostEqual(f["coef"]["d" + w]["b"], BETA[i], places=6)
                self.assertAlmostEqual(f["coef"][w + "_1"]["b"], eta[i], places=6)
            self.assertAlmostEqual(f["eta_over_beta_EDD"], -0.5, places=4)
            self.assertTrue(LD.sensitivity_fell(f))
        self.assertEqual(LD.fit_ld(recs, "state")["states"], 4)
        self.assertEqual(LD.fit_ld(recs, "none")["n"], 24)

    def test_convergence_fakes_a_fall_only_without_state_effects(self):
        level = (20.0, 60.0, 100.0, 140.0)                 # state EDD levels
        rows = synth((0.0, 0.0, 0.0, 0.0), tuple(0.002 * h for h in level), level, seed=5)
        recs = LD.ld_records(rows, LD.PRIMARY, 29)
        fa = LD.fit_ld(recs, "none")
        fb = LD.fit_ld(recs, "state")
        # within states the truth (no change in sensitivity) is recovered exactly
        self.assertAlmostEqual(fb["coef"]["EDD_1"]["b"], 0.0, places=6)
        self.assertAlmostEqual(fb["coef"]["dEDD"]["b"], -0.006, places=6)
        # across states, hot states' faster growth looks like a fall in sensitivity
        self.assertGreater(fa["coef"]["EDD_1"]["b"], 0.0015)
        self.assertLess(fa["coef"]["dEDD"]["b"], 0.0)
        self.assertTrue(LD.sensitivity_fell(fa))
        self.assertFalse(LD.sensitivity_fell(fb) and fb["coef"]["EDD_1"]["b"] > 1e-6)
        self.assertTrue(LD.shrank(fa, fb))

    def test_standard_and_initial_yield_variants(self):
        rows = synth((0.0, 0.0, 0.0, 0.0), (0.4, 0.4, 0.4, 0.4), None, seed=3)
        recs = LD.ld_records(rows, LD.PRIMARY, 29)
        f = LD.fit_ld(recs, "none", flexible=False)
        self.assertEqual(f["names"], ["dGDD", "dEDD", "dP", "dP2"])
        self.assertAlmostEqual(f["coef"]["dEDD"]["b"], -0.006, places=6)
        self.assertNotIn("eta_over_beta_EDD", f)
        g = LD.fit_ld(recs, "none", add_y0=True)
        self.assertEqual(g["names"][-1], "y0")
        self.assertEqual(len(g["names"]), 9)
        with self.assertRaises(ValueError):
            LD.fit_ld(recs[:9], "none")

    def test_pair_summary(self):
        rows = synth((0.0, 0.003, 0.0, 0.0), (0.4, 0.4, 0.4, 0.4), None, seed=13)
        ps = LD.pair_summary(rows, LD.PRIMARY, 29)
        self.assertEqual(ps["counties"], 24)
        self.assertEqual(ps["by_state"], {s: 6 for s in STATES})
        self.assertEqual(ps["periods"], [[1958, 1962], [2013, 2017]])
        self.assertAlmostEqual(ps["A"]["coef"]["EDD_1"]["b"], 0.003, places=6)
        self.assertAlmostEqual(ps["B"]["coef"]["EDD_1"]["b"], 0.003, places=6)


if __name__ == "__main__":
    unittest.main()
