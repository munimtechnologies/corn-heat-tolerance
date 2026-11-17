# test_cornheat.py - hand-checked tests for corn-heat-tolerance (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import math
import unittest

import cornheat_data as D
import run_cornheat as R

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None


class TestDegreeDays(unittest.TestCase):
    def test_sine_cases(self):
        # M=25, W=5, b=25: theta=0 -> W/pi
        self.assertAlmostEqual(D.dd_above(20, 30, 25), 5 / math.pi, places=6)
        self.assertAlmostEqual(D.dd_above(20, 30, 25), 1.5915, places=4)
        # M=26, W=6, b=29: theta=asin(0.5) -> 0.653986
        self.assertAlmostEqual(D.dd_above(20, 32, 29), 0.6540, places=4)

    def test_edges(self):
        self.assertAlmostEqual(D.dd_above(30, 34, 29), 3.0, places=6)
        self.assertAlmostEqual(D.dd_above(34, 30, 29), 3.0, places=6)
        self.assertEqual(D.dd_above(10, 20, 29), 0.0)
        self.assertEqual(D.dd_above(10, 29, 29), 0.0)
        self.assertAlmostEqual(D.dd_above(29, 35, 29), 3.0, places=6)
        self.assertTrue(math.isnan(D.dd_above(float("nan"), 30, 29)))

    def test_season_row(self):
        dd, p, miss = D.season_row([20.0, float("nan")], [30.0, 30.0], [1.0, 2.0])
        self.assertAlmostEqual(dd[25], 1.5915, places=4)
        self.assertAlmostEqual(dd[0], 25.0, places=6)
        self.assertEqual(miss, 1)
        self.assertAlmostEqual(p, 1.0, places=6)

    @unittest.skipIf(np is None, "numpy not installed")
    def test_numpy_matches_scalar(self):
        rng = np.random.default_rng(1)
        tn = rng.uniform(0, 30, size=(7, 9))
        tx = tn + rng.uniform(0, 18, size=(7, 9))
        tn[0, 0] = np.nan
        for b in (0, 10, 24, 29, 35, 40):
            v = D.dd_above_np(tn, tx, b)
            for i in range(7):
                for j in range(9):
                    s = D.dd_above(float(tn[i, j]), float(tx[i, j]), b)
                    if math.isnan(s):
                        self.assertTrue(np.isnan(v[i, j]))
                    else:
                        self.assertAlmostEqual(float(v[i, j]), s, places=9)


class TestParsers(unittest.TestCase):
    def _line(self, n_real):
        vals = ["%9.2f" % (20 + i * 0.1) for i in range(n_real)]
        vals += ["  -999.99"] * (31 - n_real)
        return "cty,14001,KS: Allen County,2025,06,TMAX," + ",".join(vals)

    def test_days_in_month(self):
        self.assertEqual(D.days_in_month(2024, 2), 29)
        self.assertEqual(D.days_in_month(2025, 6), 30)
        self.assertEqual(D.days_in_month(2025, 12), 31)

    def test_nclimgrid_line(self):
        rec = D.parse_nclimgrid_line(self._line(30), 30)
        fips, abbr, year, month, el, vals = rec
        self.assertEqual(fips, "20001")
        self.assertEqual(abbr, "KS")
        self.assertEqual((year, month, el), (2025, 6, "TMAX"))
        self.assertEqual(len(vals), 30)
        self.assertAlmostEqual(vals[0], 20.0, places=6)
        self.assertAlmostEqual(vals[29], 22.9, places=6)
        rec31 = D.parse_nclimgrid_line('"' + self._line(30) + '"', 31)
        self.assertTrue(math.isnan(rec31[5][30]))
        self.assertIsNone(D.parse_nclimgrid_line("ste,14,KS,2025,06,TMAX,1", 30))

    def test_nclimgrid_text(self):
        txt = self._line(30) + "\n" + self._line(30).replace("14001,KS: Allen", "13169,IA: Story") + "\n"
        d = D.parse_nclimgrid_text(txt, 2025, 6)
        self.assertEqual(sorted(d), ["19169", "20001"])
        self.assertEqual(d["19169"][0], "IA")
        with self.assertRaises(ValueError):
            D.parse_nclimgrid_text(txt, 2024, 6)

    def test_nass_filter(self):
        hdr = "\t".join(["SOURCE_DESC", "AGG_LEVEL_DESC", "SHORT_DESC", "STATE_FIPS_CODE",
                         "COUNTY_ANSI", "YEAR", "REFERENCE_PERIOD_DESC", "DOMAIN_DESC", "VALUE"])
        Y = D.CORN_YIELD_SHORT
        A = D.CORN_AREA_SHORT
        rows = [
            ["SURVEY", "COUNTY", Y, "19", "169", "2025", "YEAR", "TOTAL", "201.5"],
            ["SURVEY", "COUNTY", Y, "19", "", "2025", "YEAR", "TOTAL", "180.0"],
            ["CENSUS", "COUNTY", Y, "19", "169", "2022", "YEAR", "TOTAL", "190.0"],
            ["SURVEY", "COUNTY", Y, "19", "171", "2025", "YEAR", "TOTAL", "(D)"],
            ["SURVEY", "COUNTY", A, "19", "169", "2025", "YEAR", "TOTAL", "1,234"],
            ["SURVEY", "STATE", Y, "19", "", "2025", "YEAR", "TOTAL", "210.0"],
            ["SURVEY", "COUNTY", Y, "19", "998", "2025", "YEAR", "TOTAL", "170.0"],
            ["SURVEY", "COUNTY", "CORN, GRAIN, IRRIGATED - YIELD, MEASURED IN BU / ACRE",
             "19", "169", "2025", "YEAR", "TOTAL", "230.0"],
        ]
        lines = [hdr + "\n"] + ["\t".join(r) + "\n" for r in rows]
        got = list(D.nass_filter_lines(lines))
        self.assertEqual(len(got), 2)
        self.assertEqual(got[0], {"fips": "19169", "year": 2025, "short": Y, "value": 201.5})
        self.assertEqual(got[1]["value"], 1234.0)
        self.assertEqual(got[1]["short"], A)

    def test_find_nass_url(self):
        html = ('<a href="/sites/default/files/datasets/qs.crops_20261116.txt.gz">x</a>'
                '<a href="/sites/default/files/datasets/qs.crops_20261117.txt.gz">y</a>')
        self.assertEqual(D.find_nass_crops_url(html),
                         D.NASS_FILE_BASE + "qs.crops_20261117.txt.gz")
        self.assertIsNone(D.find_nass_crops_url("<html></html>"))

    def test_gazetteer(self):
        txt = ("USPS\tGEOID\tANSICODE\tNAME\tALAND\tAWATER\tALAND_SQMI\tAWATER_SQMI\tINTPTLAT\t"
               "INTPTLONG                 \n"
               "IA\t19169\t00465273\tStory County\t1\t2\t3\t4\t42.036\t-93.465\n")
        g = D.parse_gazetteer(txt)
        self.assertEqual(list(g), ["19169"])
        self.assertAlmostEqual(g["19169"][1], -93.465, places=6)


class TestSample(unittest.TestCase):
    def test_east_sample(self):
        geo = {"19169": (42.0, -93.4), "12001": (29.0, -82.0), "08001": (39.8, -104.3)}
        self.assertEqual(R.east_sample(geo), {"19169"})

    def test_season_days(self):
        for s, (m0, m1) in D.SEASONS.items():
            total = sum(D.days_in_month(2001, m) for m in range(m0, m1 + 1))
            self.assertEqual(total, R.SEASON_DAYS[s])

    def test_era_filter(self):
        rows = [{"fips": "a", "year": y} for y in range(1951, 1971)]   # 20 years
        rows += [{"fips": "b", "year": y} for y in range(1951, 1970)]  # 19 years
        kept = R.era_filter(rows, [("A", 1951, 1980)])
        self.assertEqual({r["fips"] for r in kept}, {"a"})
        self.assertEqual(len(kept), 20)


@unittest.skipIf(np is None, "numpy not installed")
class TestModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import cornheat_model as M
        cls.M = M
        rng = np.random.default_rng(0)
        true_e = {"A": -0.005, "B": -0.007, "C": -0.004}
        rows = []
        for s in ("17", "18", "19", "20"):
            for c in range(8):
                f = s + "%03d" % (2 * c + 1)
                alpha = rng.normal(5.0, 0.1)
                for y in range(1951, 2026):
                    L = "A" if y <= 1980 else ("B" if y <= 2010 else "C")
                    g = rng.uniform(1000, 1600)
                    e = rng.uniform(0, 120)
                    p = rng.uniform(300, 700)
                    t = (y - 1990) / 10.0
                    ly = (alpha + 0.01 * int(s) * t + 0.0003 * g + true_e[L] * e
                          + 0.08 * (p / 100.0) - 0.006 * (p / 100.0) ** 2
                          + rng.normal(0, 0.005))
                    dd = np.zeros(41)
                    dd[29] = e
                    dd[10] = g + e
                    rows.append({"fips": f, "state": s, "year": y, "logy": ly,
                                 "dd": {"MarAug": dd, "AprSep": dd},
                                 "P": {"MarAug": p, "AprSep": p}})
        cls.rows = rows
        cls.fit = M.fit(rows, R.ERAS, b=29, season="MarAug")

    def test_recovers_edd(self):
        for L, v in (("A", -0.005), ("B", -0.007), ("C", -0.004)):
            b, se = self.M.coef(self.fit, "EDD_%s" % L)
            self.assertAlmostEqual(b, v, places=4)
            self.assertTrue(se > 0)
        b, _ = self.M.coef(self.fit, "GDD_B")
        self.assertAlmostEqual(b, 0.0003, places=5)

    def test_diff(self):
        d = self.M.diff_test(self.fit, "EDD_C", "EDD_B")
        self.assertAlmostEqual(d["diff"], 0.003, places=4)
        self.assertLess(d["p"], 0.05)

    def test_oos_lambda(self):
        eC = [r for r in self.rows if r["year"] >= 2011]
        f = self.M.fit(eC, [("C", 2011, 2025)],
                       index_coef={"C": [0.0003, -0.004, 0.08, -0.006]})
        lam, se = self.M.coef(f, "INDEX_C")
        self.assertAlmostEqual(lam, 1.0, places=2)


if __name__ == "__main__":
    unittest.main()
