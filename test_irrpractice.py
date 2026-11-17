# test_irrpractice.py - hand-checked tests for the dryland/irrigated step (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
import math
import os
import shutil
import tempfile
import unittest

import irrpractice as I

try:
    import numpy as np
except ImportError:  # numpy-only tests skip cleanly
    np = None

HDR = "\t".join(["SOURCE_DESC", "AGG_LEVEL_DESC", "SHORT_DESC", "STATE_FIPS_CODE", "COUNTY_ANSI",
                 "YEAR", "REFERENCE_PERIOD_DESC", "DOMAIN_DESC", "VALUE"]) + "\n"


def line(src, agg, short, st, cty, year, per, dom, val):
    return "\t".join([src, agg, short, st, cty, str(year), per, dom, val]) + "\n"


CIY = "CORN, GRAIN, IRRIGATED - YIELD, MEASURED IN BU / ACRE"
CDY = "CORN, GRAIN, NON-IRRIGATED - YIELD, MEASURED IN BU / ACRE"
SIA = "SOYBEANS, IRRIGATED - ACRES HARVESTED"
SDY = "SOYBEANS, NON-IRRIGATED - YIELD, MEASURED IN BU / ACRE"


class TestNass(unittest.TestCase):
    def test_practice_of(self):
        self.assertEqual(I.practice_of(CIY), ("corn", "irr", "yield"))
        self.assertEqual(I.practice_of(CDY), ("corn", "dry", "yield"))
        self.assertEqual(I.practice_of(SIA), ("soy", "irr", "area"))
        self.assertEqual(I.practice_of(SDY), ("soy", "dry", "yield"))
        self.assertEqual(I.practice_of("CORN, GRAIN, NON-IRRIGATED - ACRES HARVESTED"),
                         ("corn", "dry", "area"))
        self.assertIsNone(I.practice_of("CORN, GRAIN - YIELD, MEASURED IN BU / ACRE"))
        self.assertIsNone(I.practice_of("CORN, GRAIN, IRRIGATED - YIELD, MEASURED IN BU / NET PLANTED ACRE"))
        self.assertIsNone(I.practice_of("CORN, GRAIN, IRRIGATED, ENTIRE CROP - YIELD, MEASURED IN BU / ACRE"))
        self.assertIsNone(I.practice_of("WHEAT, WINTER, IRRIGATED - YIELD, MEASURED IN BU / ACRE"))

    def test_filter(self):
        lines = [HDR,
                 line("SURVEY", "COUNTY", CIY, "31", "001", 2015, "YEAR", "TOTAL", "201.5"),      # kept
                 line("SURVEY", "COUNTY", CDY, "31", "001", 2015, "YEAR", "TOTAL", "1,120.0"),    # kept
                 line("SURVEY", "COUNTY", SIA, "20", "015", 1990, "YEAR", "TOTAL", "3,400"),      # kept
                 line("SURVEY", "STATE", CIY, "31", "", 2015, "YEAR", "TOTAL", "200"),            # no COUNTY
                 line("CENSUS", "COUNTY", CIY, "31", "001", 2017, "YEAR", "TOTAL", "190"),        # census
                 line("SURVEY", "COUNTY", CIY, "31", "998", 2015, "YEAR", "TOTAL", "180"),        # other cties
                 line("SURVEY", "COUNTY", CDY, "31", "003", 2015, "YEAR", "TOTAL", "(D)"),        # withheld
                 line("SURVEY", "COUNTY", CDY, "31", "005", 2015, "MARKETING YEAR", "TOTAL", "99"),
                 line("SURVEY", "COUNTY", "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE",
                      "31", "001", 2015, "YEAR", "TOTAL", "150"),                                 # all practices
                 line("SURVEY", "COUNTY", "CORN, GRAIN, IRRIGATED, ENTIRE CROP - ACRES HARVESTED",
                      "31", "001", 2015, "YEAR", "TOTAL", "5")]                                   # seen only
        seen = {}
        out = list(I.practice_filter(lines, seen=seen))
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0], {"fips": "31001", "year": 2015, "crop": "corn:irr", "slot": "yield",
                                  "value": 201.5})
        self.assertEqual(out[1]["crop"], "corn:dry")
        self.assertAlmostEqual(out[1]["value"], 1120.0)
        self.assertEqual(out[2], {"fips": "20015", "year": 1990, "crop": "soy:irr", "slot": "area",
                                  "value": 3400.0})
        # seen: county SURVEY rows with IRRIGATED in SHORT_DESC (before the other checks)
        self.assertEqual(seen[CIY], 2)      # 31001 and 31998
        self.assertEqual(seen[CDY], 3)      # 001, 003 (D), 005 marketing year
        self.assertEqual(seen[SIA], 1)
        self.assertEqual(seen["CORN, GRAIN, IRRIGATED, ENTIRE CROP - ACRES HARVESTED"], 1)
        self.assertEqual(len(seen), 4)

    def test_filter_header(self):
        with self.assertRaises(KeyError):
            list(I.practice_filter(["A\tB\n"]))


class TestDesign(unittest.TestCase):
    def test_eras(self):
        self.assertEqual(I.era_label(2010, I.ERAS_IRR), "B")
        self.assertEqual(I.era_label(2011, I.ERAS_IRR), "C")
        self.assertEqual(I.era_label(2019, I.ERAS_IRR), None)
        self.assertEqual(I.era_label(1980, I.ERAS_IRR), None)
        self.assertEqual(I.era_label(1996, I.PLACEBO_ERAS), "C")
        self.assertEqual(I.era_label(2012, I.LATE_ERAS), None)

    def test_paired(self):
        dry = [{"fips": "a", "year": 1990}, {"fips": "a", "year": 2012},
               {"fips": "b", "year": 1991}, {"fips": "c", "year": 2015}]
        irr = [{"fips": "a", "year": 1995}, {"fips": "b", "year": 1999}, {"fips": "b", "year": 2013}]
        d, i, both = I.paired(dry, irr, I.ERAS_IRR)
        self.assertEqual(both, {("a", "B"), ("b", "B")})
        self.assertEqual([r["year"] for r in d], [1990, 1991])
        self.assertEqual([r["year"] for r in i], [1995, 1999])

    def test_shares(self):
        area = {k: {} for k in I.KEYS}
        area[("corn", "irr")] = {("31001", 1990): 300.0, ("31001", 2015): 500.0, ("19001", 2015): 900.0}
        area[("corn", "dry")] = {("31001", 1990): 700.0, ("31001", 2015): 500.0}
        sh = I.irrigated_shares(area)
        self.assertAlmostEqual(sh["corn"]["B"], 0.3)
        self.assertAlmostEqual(sh["corn"]["C"], 0.5)      # Iowa (19) is outside the pool
        self.assertIsNone(sh["soy"]["B"])

    def test_class(self):
        sig = {"diff": 0.002, "p": 0.01}
        self.assertEqual(I.irr_class(sig, {"p": 0.5}), "dryland corn gained")
        self.assertEqual(I.irr_class({"diff": -0.002, "p": 0.01}, {"p": 0.10}), "dryland corn lost")
        self.assertEqual(I.irr_class(sig, {"p": 0.09}), "not interpretable (placebo failed)")
        self.assertEqual(I.irr_class(sig, None), "not interpretable (placebo failed)")
        self.assertEqual(I.irr_class(sig, {"p": float("nan")}), "not interpretable (placebo failed)")
        self.assertEqual(I.irr_class({"diff": 0.002, "p": 0.06}, {"p": 0.01}), "no detectable difference")
        self.assertEqual(I.irr_class({"diff": 0.002, "p": float("nan")}, {"p": 0.5}),
                         "no detectable difference")

    def _res(self, t=0.0004, cls="no detectable difference", cd=-0.012, ci=-0.004, sd=-0.008, si=-0.003,
             plp=0.4, nc=60, ns=30, nb=70, cov=True):
        return {"coverage": {"corn_years_2011_2018_complete": cov},
                "placebo": {"T_year": {"p": plp}},
                "primary": {"class": cls, "T": t,
                            "counties": {"corn": {"B": nb, "C": nc}, "soy": {"B": 40, "C": ns}},
                            "coef": {"cornH:EDD_B": {"b": cd}, "cornL:EDD_B": {"b": ci},
                                     "soyH:EDD_B": {"b": sd}, "soyL:EDD_B": {"b": si}}}}

    def test_grade(self):
        g = I.grade_irr(self._res())
        self.assertEqual(g["predictions_held"], 6)
        self.assertTrue(g["G1_paired_corn_eraC_counties_ge_40"] and g["G2_paired_soy_eraC_counties_ge_25"]
                        and g["G3_paired_corn_eraB_counties_ge_40"]
                        and g["G4_corn_practice_rows_every_year_2011_2018"])
        # irrigated corn at exactly half of dryland fails I5 (strict); placebo p 0.05 fails I6
        g = I.grade_irr(self._res(t=-0.001, ci=-0.006, plp=0.05, nc=39, cov=False))
        self.assertEqual(g["predictions_held"], 3)
        self.assertFalse(g["I2_holds_T_positive"])
        self.assertFalse(g["I5_holds_irr_corn_under_half_of_dry_B"])
        self.assertFalse(g["I6_holds_placebo_p_ge_0.10"])
        self.assertFalse(g["G1_paired_corn_eraC_counties_ge_40"])
        self.assertFalse(g["G4_corn_practice_rows_every_year_2011_2018"])
        # placebo that failed to fit counts as not clean
        r = self._res()
        r["placebo"] = {"error": "ValueError: empty block"}
        self.assertFalse(I.grade_irr(r)["I6_holds_placebo_p_ge_0.10"])


@unittest.skipIf(np is None, "numpy not installed")
class TestSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rng = np.random.default_rng(7)
        # EDD coefficient by era; T = (0.003 - 0) - (0.0005 - 0) = 0.0025
        truth = {("corn", "dry"): ({"B": -0.010, "C": -0.007}, 29, 0.0),
                 ("corn", "irr"): ({"B": -0.003, "C": -0.0025}, 29, 0.5),
                 ("soy", "dry"): ({"B": -0.006, "C": -0.006}, 30, 0.0),
                 ("soy", "irr"): ({"B": -0.002, "C": -0.002}, 30, 0.3)}
        cls.rows = {k: [] for k in I.KEYS}
        for s in ("20", "31"):
            for c in range(6):
                f = s + "%03d" % (2 * c + 1)
                for y in range(1981, 2019):
                    L = "B" if y <= 2010 else "C"
                    g = rng.uniform(1000, 1600)
                    e = rng.uniform(0, 120)
                    p = rng.uniform(300, 700)
                    t = (y - 1995) / 10.0
                    for k, (te, b, lift) in truth.items():
                        ly = (4.0 + lift + 0.01 * int(s) * t + 0.0003 * g + te[L] * e
                              + 0.08 * (p / 100.0) - 0.006 * (p / 100.0) ** 2 + rng.normal(0, 0.005))
                        dd = np.zeros(41)
                        dd[b] = e
                        dd[10] = g + e
                        cls.rows[k].append({"fips": f, "state": s, "year": y, "crop": k[0], "practice": k[1],
                                            "logy": ly, "dd": {"MarAug": dd, "AprSep": dd},
                                            "P": {"MarAug": p, "AprSep": p}})
        cls.fit = I.fit_practice(cls.rows, I.ERAS_IRR)

    def test_recovery(self):
        f = self.fit
        self.assertAlmostEqual(f["T"], 0.0025, places=3)
        self.assertLess(f["T_year"]["p"], 0.05)
        self.assertAlmostEqual(f["did_H_year"]["diff"], 0.003, places=3)
        self.assertAlmostEqual(f["did_L_year"]["diff"], 0.0005, places=3)
        self.assertAlmostEqual(f["coef"]["cornH:EDD_B"]["b"], -0.010, places=4)
        self.assertAlmostEqual(f["coef"]["cornL:EDD_C"]["b"], -0.0025, places=4)
        self.assertEqual(f["rows"]["cornH"], 12 * 38)
        self.assertEqual(f["counties"]["corn"], {"B": 12, "C": 12})
        self.assertEqual(f["counties"]["states"], ["20", "31"])

    def test_placebo_and_subsets(self):
        pl = I.fit_practice(self.rows, I.PLACEBO_ERAS)
        self.assertAlmostEqual(pl["T"], 0.0, places=3)
        self.assertEqual(pl["rows"]["soyL"], 12 * 30)
        ne = I.fit_practice(self.rows, I.ERAS_IRR, states=("31",))
        self.assertAlmostEqual(ne["T"], 0.0025, places=3)
        up = I.fit_practice(self.rows, I.ERAS_IRR, pair=False)
        self.assertAlmostEqual(up["T"], self.fit["T"], places=12)    # complete panel: same rows
        d12 = I.fit_practice(self.rows, I.ERAS_IRR, drop_year=2012)
        self.assertEqual(d12["rows"]["cornH"], 12 * 37)
        late = I.fit_practice(self.rows, I.LATE_ERAS)
        self.assertEqual(late["rows"]["cornH"], 12 * (30 + 5))

    def test_pairing_drops_unmatched(self):
        rows = {k: list(v) for k, v in self.rows.items()}
        # county 31001 loses its irrigated corn in era C: its corn era-C cell drops in both practices
        rows[("corn", "irr")] = [r for r in rows[("corn", "irr")]
                                 if not (r["fips"] == "31001" and r["year"] >= 2011)]
        f = I.fit_practice(rows, I.ERAS_IRR)
        self.assertEqual(f["counties"]["corn"], {"B": 12, "C": 11})
        self.assertEqual(f["counties"]["soy"], {"B": 12, "C": 12})
        self.assertEqual(f["rows"]["cornH"], 12 * 38 - 8)

    def test_empty(self):
        with self.assertRaises(ValueError):
            I.fit_practice(self.rows, I.ERAS_IRR, states=("55",))
        self.assertIn("error", I.safe(I.fit_practice, self.rows, I.ERAS_IRR, states=("55",)))

    def test_load_panels(self):
        tmp = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(tmp, "weather"))
            for year in (2011, 2012):
                with open(os.path.join(tmp, "weather", "w_%d.csv" % year), "w", encoding="utf-8") as fh:
                    fh.write("fips,year,season,ndays,nmiss,prcp_mm," + ",".join("dd%d" % b for b in range(41)) + "\n")
                    for f in ("31001", "31003"):
                        for s, nd in (("MarAug", 184), ("AprSep", 183)):
                            miss = 1 if (f == "31003" and year == 2012 and s == "AprSep") else 0
                            fh.write("%s,%d,%s,%d,%d,500.0,%s\n" % (f, year, s, nd, miss,
                                                                    ",".join(str(40 - b) for b in range(41))))
            path = os.path.join(tmp, "practice.tsv")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("key\tfips\tyear\tyield_bu_ac\tarea_ac\n")
                fh.write("corn:dry\t31001\t2011\t100\t2000\n")
                fh.write("corn:irr\t31001\t2011\t200\t6000\n")
                fh.write("corn:irr\t31003\t2012\t210\t\n")       # weather row has a missing day
                fh.write("soy:dry\t31001\t2012\t\t50\n")          # no yield
                fh.write("corn:dry\t19001\t2011\t150\t10\n")      # outside keep
                fh.write("corn:dry\t31001\t2019\t150\t10\n")      # outside years
            rows, census, shares = I.load_practice_panels(tmp, path, {"31001", "31003"}, 2011, 2012)
            self.assertEqual(len(rows[("corn", "dry")]), 1)
            self.assertEqual(len(rows[("corn", "irr")]), 1)
            self.assertEqual(len(rows[("soy", "dry")]), 0)
            r = rows[("corn", "irr")][0]
            self.assertAlmostEqual(r["logy"], math.log(200))
            self.assertEqual((r["fips"], r["state"], r["practice"]), ("31001", "31", "irr"))
            self.assertAlmostEqual(float(r["dd"]["MarAug"][29]), 11.0)
            self.assertAlmostEqual(r["P"]["AprSep"], 500.0)
            self.assertEqual(census["corn:irr"]["nass_county_years"], 2)
            self.assertEqual(census["corn:irr"]["panel_rows"], 1)
            self.assertEqual(census["corn:irr"]["pool_years"], [2011, 2012])
            self.assertAlmostEqual(census["corn:dry"]["nass_counties_with_weather_share"], 1.0)
            self.assertAlmostEqual(shares["corn"]["C"], 0.75)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main()
