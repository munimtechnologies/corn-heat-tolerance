# test_rcx.py - tests for rcx.py (pre-registration 0.8.0), MV2, Munim, Inc.
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Noise-free synthetic counties. The key test builds a county whose yield loses the
# SAME SHARE per degree day in every year (Y = T * (1 + s * kdd anomaly), trend T
# rising from 79 to 139 bu/acre between the midpoints of the first and last window).
# The paper's level estimator must then show a ratio near 139/79 = 1.76 while the
# relative and log estimators stay near 1: the scale effect this step tests for.
import math
import unittest

import rcx as X

K5 = (10.0, -10.0, 20.0, -20.0, 0.0)                  # KDD anomaly cycle, mean 0
G7 = (100.0, 50.0, -30.0, 0.0, -80.0, 20.0, -60.0)    # GDD cycle (different period)


def proportional_county(y0=1960, y1=2019, t0=50.0, slope=2.0, s=-0.005, skip=()):
    ser = {}
    for t in range(y0, y1 + 1):
        if t in skip:
            continue
        kd = K5[(t - y0) % 5]
        T = t0 + slope * (t - y0)
        ser[t] = (T * (1.0 + s * kd), 30.0 + kd, 1500.0 + G7[(t - y0) % 7])
    return ser


class Algebra(unittest.TestCase):
    def test_linfit(self):
        a, b = X.linfit([0, 1, 2, 3], [1, 3, 5, 7])
        self.assertAlmostEqual(a, 1.0, places=9)
        self.assertAlmostEqual(b, 2.0, places=9)
        with self.assertRaises(ValueError):
            X.linfit([1, 1], [2, 3])

    def test_detrend_removes_line(self):
        u, fit = X.detrend([0, 1, 2, 3], [1, 3, 5, 7])
        for v in u:
            self.assertAlmostEqual(v, 0.0, places=9)
        self.assertAlmostEqual(fit[3], 7.0, places=9)

    def test_sd_sample(self):
        self.assertAlmostEqual(X.sd([1, 2, 3, 4]), math.sqrt(5.0 / 3.0), places=9)

    def test_ols_exact(self):
        k = [1, 2, 3, 4, 5]
        g = [2, 1, 4, 3, 6]
        z = [0.5 - 0.3 * a + 0.1 * c for a, c in zip(k, g)]
        bk, bg = X.ols_kdd(z, k, g)
        self.assertAlmostEqual(bk, -0.3, places=9)
        self.assertAlmostEqual(bg, 0.1, places=9)

    def test_ols_collinear(self):
        k = [1, 2, 3, 4, 5]
        with self.assertRaises(ValueError):
            X.ols_kdd([1, 2, 3, 4, 6], k, [2 * a for a in k])

    def test_windows(self):
        s = X.starts_for(1960, 2019)
        self.assertEqual((len(s), s[0], s[-1]), (31, 1960, 1990))
        s = X.starts_for(1960, 2025)
        self.assertEqual((len(s), s[0], s[-1]), (37, 1960, 1996))

    def test_quantile(self):
        self.assertAlmostEqual(X.quantile([3, 1, 2, 4, 5], 0.5), 3.0, places=9)
        self.assertAlmostEqual(X.quantile([0, 10], 0.25), 2.5, places=9)
        self.assertIsNone(X.quantile([], 0.5))


class Series(unittest.TestCase):
    def test_county_series(self):
        dd = [float(41 - k) for k in range(41)]          # dd[9] = 32, dd[29] = 12
        rows = [{"fips": "19001", "state": "19", "year": 1970, "logy": math.log(100.0),
                 "dd": {"AprSep": dd, "MarAug": dd}},
                {"fips": "19001", "state": "19", "year": 2012, "logy": math.log(90.0),
                 "dd": {"AprSep": dd, "MarAug": dd}},
                {"fips": "01001", "state": "01", "year": 1970, "logy": math.log(100.0),
                 "dd": {"AprSep": dd, "MarAug": dd}}]
        out = X.county_series(rows, 1960, 2019, 29, drop_years=(2012,))
        self.assertEqual(sorted(out), ["19001"])
        self.assertEqual(sorted(out["19001"]), [1970])
        y, k, g = out["19001"][1970]
        self.assertAlmostEqual(y, 100.0, places=6)
        self.assertAlmostEqual(k, 12.0, places=9)
        self.assertAlmostEqual(g, 20.0, places=9)
        self.assertEqual(len(X.county_series(rows, 1960, 2019, 29, states=None)), 2)

    def test_anomalies_standardized(self):
        an = X.anomalies(proportional_county(), "level")
        z = [an[t][0] for t in sorted(an)]
        self.assertAlmostEqual(X.sd(z), 1.0, places=9)
        self.assertAlmostEqual(sum(z) / len(z), 0.0, places=9)
        with self.assertRaises(ValueError):
            X.anomalies(proportional_county(), "cubic")


class ScaleEffect(unittest.TestCase):
    """Constant proportional sensitivity: level estimator 'rises', others do not."""

    @classmethod
    def setUpClass(cls):
        cls.res = X.run_forms({"a": proportional_county()}, 1960, 2019, boot=False)

    def test_level_rises_with_trend_yield(self):
        r = self.res["level"]["ratio_last_first"]
        self.assertGreater(r, 1.6)
        self.assertLess(r, 1.95)
        self.assertLess(self.res["level"]["first"], 0.0)

    def test_relative_flat(self):
        r = self.res["relative"]["ratio_last_first"]
        self.assertGreater(r, 0.93)
        self.assertLess(r, 1.07)
        self.assertLess(self.res["relative"]["first"], 0.0)

    def test_log_near_flat(self):
        r = self.res["log"]["ratio_last_first"]
        self.assertGreater(r, 0.8)
        self.assertLess(r, 1.2)
        self.assertLess(r, self.res["level"]["ratio_last_first"] - 0.3)

    def test_trend_yield_ratio(self):
        self.assertAlmostEqual(self.res["trend_yield_ratio"], 139.0 / 79.0, delta=0.02)

    def test_trend_change_sign_matches_ratio(self):
        self.assertGreater(self.res["level"]["trend_change"], 0.0)
        self.assertEqual(self.res["windows"], 31)


class Sample(unittest.TestCase):
    def test_common_counties_and_drop(self):
        series = {"a": proportional_county(),
                  "b": proportional_county(t0=70.0, slope=1.5, s=-0.004),
                  "c": proportional_county(skip=range(1975, 1990))}   # 1960-89 has 15 years
        res = X.run_forms(series, 1960, 2019, boot=True)
        self.assertEqual(res["counties_common"], 2)
        self.assertEqual(res["dropped"]["level"]["few_years"], 1)
        bt = res["bootstrap"]
        for form in X.FORMS:
            self.assertLessEqual(bt[form]["p05"], bt[form]["p50"])
            self.assertLessEqual(bt[form]["p50"], bt[form]["p95"])
        self.assertEqual(bt["counties"], 2)


def fake_res(lv, rl, lg, ex, n=500):
    blk = lambda r: {"first": -0.01, "ratio_last_first": r}
    return {"primary": {"counties_common": n, "level": blk(lv), "relative": blk(rl), "log": blk(lg),
                        "trend_yield_ratio": 1.7},
            "extended": {"relative": blk(ex)}}


class Grading(unittest.TestCase):
    def test_all_hold_scale(self):
        g = X.grade_rcx(fake_res(1.5, 0.85, 0.9, 0.8))
        self.assertEqual(g["predictions_held"], 5)
        self.assertTrue(g["XG1_corn_counties_ge_300"])
        self.assertTrue(g["verdict"].startswith("scale"))

    def test_no_level_rise(self):
        g = X.grade_rcx(fake_res(0.9, 0.7, 0.75, 0.7, n=100))
        self.assertFalse(g["X1_holds_level_rise"])
        self.assertFalse(g["XG1_corn_counties_ge_300"])
        self.assertTrue(g["verdict"].startswith("no-level-rise"))

    def test_proportional_rise(self):
        g = X.grade_rcx(fake_res(1.3, 1.1, 1.05, 1.2))
        self.assertTrue(g["X1_holds_level_rise"])
        self.assertTrue(g["X2_holds_scale_shrinks_rise"])
        self.assertFalse(g["X3_holds_relative_no_rise"])
        self.assertEqual(g["predictions_held"], 2)
        self.assertTrue(g["verdict"].startswith("proportional-rise"))


if __name__ == "__main__":
    unittest.main()
