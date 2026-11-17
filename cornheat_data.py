# cornheat_data.py - data layer for corn-heat-tolerance (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# Degree-day maths (single-sine method), nClimGrid-Daily county parser,
# NASS Quick Stats bulk-file streaming filter and Census gazetteer reader.
# Standard library only; numpy is used only when available (dd_above_np).

import csv
import gzip
import io
import math
import re
import time
import urllib.request
import zipfile

USER_AGENT = "corn-heat-tolerance/0.1 (MV2, Munim, Inc.; mv2@munimtech.com)"

NCLIMGRID_URL = ("https://www.ncei.noaa.gov/data/nclimgrid-daily/access/averages/"
                 "{year}/{var}-{year}{month:02d}-cty-scaled.csv")
NASS_LISTING_URLS = ["https://www.nass.usda.gov/datasets/index.php",
                     "https://www.nass.usda.gov/datasets/"]
NASS_FILE_BASE = "https://www.nass.usda.gov/sites/default/files/datasets/"
GAZETTEER_URLS = [
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2020_Gazetteer/2020_Gaz_counties_national.zip",
    "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_counties_national.zip",
]

CORN_YIELD_SHORT = "CORN, GRAIN - YIELD, MEASURED IN BU / ACRE"
CORN_AREA_SHORT = "CORN, GRAIN - ACRES HARVESTED"

# USPS abbreviation -> state FIPS. nClimGrid county codes use NCEI's own
# alphabetical state numbers (e.g. KS = 14), so we map by the abbreviation in
# the name field ("KS: Allen County") and keep the last 3 digits (FIPS county).
STATE_FIPS = {
    "AL": "01", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29",
    "MT": "30", "NE": "31", "NV": "32", "NH": "33", "NJ": "34", "NM": "35",
    "NY": "36", "NC": "37", "ND": "38", "OH": "39", "OK": "40", "OR": "41",
    "PA": "42", "RI": "44", "SC": "45", "SD": "46", "TN": "47", "TX": "48",
    "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56",
}

MISSING_BELOW = -99.0  # nClimGrid pads short months with -999.99


# ----------------------------------------------------------------- degree days
def dd_above(tmin, tmax, b):
    """Degree days above threshold b for one day, single-sine interpolation
    between tmin and tmax (Baskerville-Emin). Returns float; NaN in -> NaN out."""
    if tmin is None or tmax is None:
        return float("nan")
    if math.isnan(tmin) or math.isnan(tmax):
        return float("nan")
    lo, hi = (tmin, tmax) if tmin <= tmax else (tmax, tmin)
    if lo >= b:
        return (lo + hi) / 2.0 - b
    if hi <= b:
        return 0.0
    m = (lo + hi) / 2.0
    w = (hi - lo) / 2.0
    s = (b - m) / w
    s = max(-1.0, min(1.0, s))
    th = math.asin(s)
    return ((m - b) * (math.pi / 2.0 - th) + w * math.cos(th)) / math.pi


def dd_above_np(tmin, tmax, b):
    """Vectorised dd_above for numpy arrays of equal shape."""
    import numpy as np
    tmin = np.asarray(tmin, dtype=float)
    tmax = np.asarray(tmax, dtype=float)
    lo = np.minimum(tmin, tmax)
    hi = np.maximum(tmin, tmax)
    m = (lo + hi) / 2.0
    w = (hi - lo) / 2.0
    out = np.zeros(m.shape, dtype=float)
    nan = np.isnan(m)
    above = (~nan) & (lo >= b)
    out[above] = m[above] - b
    mid = (~nan) & (~above) & (hi > b)
    if mid.any():
        mm = m[mid]
        ww = w[mid]
        s = np.clip((b - mm) / ww, -1.0, 1.0)
        th = np.arcsin(s)
        out[mid] = ((mm - b) * (np.pi / 2.0 - th) + ww * np.cos(th)) / np.pi
    out[nan] = np.nan
    return out


def days_in_month(year, month):
    if month == 12:
        nxt = (year + 1, 1)
    else:
        nxt = (year, month + 1)
    import datetime
    return (datetime.date(*nxt, 1) - datetime.date(year, month, 1)).days


# ----------------------------------------------------------------- nClimGrid
def parse_nclimgrid_line(line, ndays):
    """Parse one county row. Returns (fips5, abbr, year, month, element, values)
    or None for blank/foreign rows. values has exactly ndays floats (NaN for
    missing)."""
    line = line.strip().strip('"').strip()
    if not line:
        return None
    fields = line.split(",")
    if len(fields) < 7 or fields[0].strip() != "cty":
        return None
    idx = None
    for i in range(3, len(fields)):
        if fields[i].strip().upper() in ("TMAX", "TMIN", "TAVG", "PRCP"):
            idx = i
            break
    if idx is None or idx < 5:
        return None
    code = fields[1].strip()
    name = ",".join(fields[2:idx - 2]).strip()
    year = int(fields[idx - 2])
    month = int(fields[idx - 1])
    element = fields[idx].strip().upper()
    raw = fields[idx + 1: idx + 1 + ndays]
    if len(raw) < ndays:
        raise ValueError("row has %d values, need %d: %s" % (len(raw), ndays, line[:60]))
    vals = []
    for r in raw:
        v = float(r)
        vals.append(float("nan") if v < MISSING_BELOW else v)
    abbr = name.split(":", 1)[0].strip().upper()
    sf = STATE_FIPS.get(abbr)
    if sf is None or len(code) != 5:
        return None
    fips = sf + code[2:5]
    return fips, abbr, year, month, element, vals


def parse_nclimgrid_text(text, year, month):
    """dict fips -> (abbr, values) for one monthly county file."""
    nd = days_in_month(year, month)
    out = {}
    for line in text.splitlines():
        rec = parse_nclimgrid_line(line, nd)
        if rec is None:
            continue
        fips, abbr, y, m, _el, vals = rec
        if y != year or m != month:
            raise ValueError("file for %d-%02d holds a row for %d-%02d" % (year, month, y, m))
        out[fips] = (abbr, vals)
    return out


def http_get(url, tries=4, timeout=120):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network errors are retried
            last = e
            time.sleep(5 * (k + 1))
    raise RuntimeError("GET failed after %d tries: %s (%s)" % (tries, url, last))


# ----------------------------------------------------------------- NASS
def find_nass_crops_url(listing_html):
    """Newest qs.crops_YYYYMMDD.txt.gz named in the listing page, as absolute URL."""
    names = re.findall(r"qs\.crops_(\d{8})\.txt\.gz", listing_html)
    if not names:
        return None
    newest = max(names)
    return NASS_FILE_BASE + "qs.crops_%s.txt.gz" % newest


def nass_filter_lines(lines, shorts=(CORN_YIELD_SHORT, CORN_AREA_SHORT)):
    """Filter Quick Stats tab-separated lines (first line = header).
    Yields dicts with fips, year, short, value for county-level annual SURVEY
    rows of the wanted SHORT_DESC values. Suppressed values are skipped."""
    it = iter(lines)
    header = next(it).rstrip("\r\n").split("\t")
    hdr = [h.strip().strip('"').upper() for h in header]
    col = {h: i for i, h in enumerate(hdr)}
    need = ["SOURCE_DESC", "AGG_LEVEL_DESC", "SHORT_DESC", "STATE_FIPS_CODE",
            "YEAR", "VALUE"]
    for n in need:
        if n not in col:
            raise KeyError("NASS header lacks %s; header=%s" % (n, hdr))
    cty = col.get("COUNTY_ANSI", col.get("COUNTY_CODE"))
    if cty is None:
        raise KeyError("NASS header lacks COUNTY_ANSI/COUNTY_CODE")
    per = col.get("REFERENCE_PERIOD_DESC")
    dom = col.get("DOMAIN_DESC")
    shortset = set(shorts)
    for line in it:
        if "COUNTY" not in line or "CORN, GRAIN - " not in line:
            continue
        f = [x.strip().strip('"') for x in line.rstrip("\r\n").split("\t")]
        if len(f) < len(hdr):
            continue
        if f[col["SHORT_DESC"]] not in shortset:
            continue
        if f[col["AGG_LEVEL_DESC"]] != "COUNTY" or f[col["SOURCE_DESC"]] != "SURVEY":
            continue
        if per is not None and f[per] != "YEAR":
            continue
        if dom is not None and f[dom] != "TOTAL":
            continue
        c = f[cty]
        s = f[col["STATE_FIPS_CODE"]]
        if not c.isdigit() or not s.isdigit():
            continue
        if int(c) >= 998:   # "OTHER (COMBINED) COUNTIES"
            continue
        v = f[col["VALUE"]].replace(",", "")
        try:
            val = float(v)
        except ValueError:
            continue
        yield {"fips": "%02d%03d" % (int(s), int(c)), "year": int(f[col["YEAR"]]),
               "short": f[col["SHORT_DESC"]], "value": val}


def stream_nass(url, timeout=600):
    """Yield decoded lines of a remote .txt.gz without saving it."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    r = urllib.request.urlopen(req, timeout=timeout)
    gz = gzip.GzipFile(fileobj=r)
    for line in io.TextIOWrapper(gz, encoding="utf-8", errors="replace"):
        yield line


# ----------------------------------------------------------------- gazetteer
def parse_gazetteer(text):
    """dict GEOID -> (lat, lon) from a Census county gazetteer text file."""
    rows = text.splitlines()
    hdr = [h.strip().upper() for h in rows[0].split("\t")]
    gi, la, lo = hdr.index("GEOID"), hdr.index("INTPTLAT"), hdr.index("INTPTLONG")
    out = {}
    for line in rows[1:]:
        f = [x.strip() for x in line.split("\t")]
        if len(f) <= max(gi, la, lo) or not f[gi]:
            continue
        out[f[gi].zfill(5)] = (float(f[la]), float(f[lo]))
    return out


def gazetteer_from_zip(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
        return parse_gazetteer(z.read(name).decode("utf-8", errors="replace"))


# ----------------------------------------------------------------- season sums
THRESHOLDS = list(range(0, 41))   # degree-day thresholds stored, deg C
SEASONS = {"MarAug": (3, 8), "AprSep": (4, 9)}


def season_row(tmin_days, tmax_days, prcp_days):
    """Sum degree days above every threshold and precipitation over a list of
    daily values. Returns (dd list, prcp_sum, n_missing). Pure Python."""
    dd = [0.0] * len(THRESHOLDS)
    miss = 0
    p = 0.0
    for tn, tx, pr in zip(tmin_days, tmax_days, prcp_days):
        if math.isnan(tn) or math.isnan(tx) or math.isnan(pr):
            miss += 1
            continue
        p += pr
        for k, b in enumerate(THRESHOLDS):
            dd[k] += dd_above(tn, tx, b)
    return dd, p, miss


def write_csv(path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            w.writerow(r)
