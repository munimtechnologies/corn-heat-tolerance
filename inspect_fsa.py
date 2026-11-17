# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Munim, Inc. (MV2). Made with AI agents working in MV2's name.
"""Structure-only inspection of USDA FSA ARC-County yield files (corn-heat-tolerance step c).

Purpose: before any pre-registration of a post-2018 dryland-vs-irrigated test, learn what
the FSA ARC-County "Benchmark Yields and Revenues" and "Detailed ARC-CO NASS and RMA County
Yields" files contain: sheets, header rows, practice codes, which yield years each file
carries, and how many Nebraska / Kansas corn and soybean county-practice rows exist.

It deliberately never prints, stores or summarises any yield VALUE: only header text,
category labels and counts of non-empty cells. No model is fitted.
"""
import argparse
import html.parser
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import zipfile

PAGES = [
    "https://www.fsa.usda.gov/resources/programs/arc-plc/program-data",
    "https://dts.fsa.usda.gov/programs-and-services/arcplc_program/arcplc-program-data/index",
    "https://www.fsa.usda.gov/tools/informational/reports",
]
# Known document URLs (from public search results, 2026-11-17), used if page parsing finds none.
FALLBACK_URLS = [
    "https://www.fsa.usda.gov/documents/arcco-2025-data-2026-11-02",
    "https://www.fsa.usda.gov/documents/arcco-2025-data-20260630",
    "https://www.fsa.usda.gov/sites/default/files/documents/ARC-CO%20Explanation%20for%20Detailed%20Yield%20File%20Posting.docx",
]
UA = "Mozilla/5.0 (X11; Linux x86_64) MV2-Munim-research/0.1 (mv2@munimtech.com)"
MAX_FILES = 40
MAX_BYTES = 80 * 1024 * 1024

LINK_TEXT_RE = re.compile(
    r"(ARC[- ]?C(ounty|O)\b.*(benchmark|yield|data))|(detailed\s+ARC)|(county\s+yields)", re.I)
LINK_HREF_RE = re.compile(r"arc-?co|arc_co|arccounty|benchmark|detailed", re.I)
YEAR_RE = re.compile(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)")
HEADER_KEYS = ("state", "county", "crop", "commodity", "practice", "yield", "irrig")
NE_VALUES = {"NEBRASKA", "NE", "31"}
KS_VALUES = {"KANSAS", "KS", "20"}


class LinkParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, " ".join("".join(self._text).split())))
            self._href = None


def parse_links(html_text, base_url):
    p = LinkParser()
    p.feed(html_text)
    out = []
    for href, text in p.links:
        if not href or href.startswith(("mailto:", "javascript:", "#")):
            continue
        out.append((urllib.parse.urljoin(base_url, href), text))
    return out


def select_links(links):
    """Keep links whose text or href looks like an ARC-County yield file; dedupe by URL."""
    seen, out = set(), []
    for url, text in links:
        if not (LINK_TEXT_RE.search(text or "") or LINK_HREF_RE.search(urllib.parse.urlparse(url).path)):
            continue
        low = url.lower()
        if any(s in low for s in ("/resources/programs/", "/news", "/tools/informational/reports")) \
                and not low.endswith((".xlsx", ".xls", ".zip", ".docx", ".csv")):
            continue
        if "arc-ic" in (text or "").lower() or "arc-ic" in low or "arcic" in low:
            continue
        if url not in seen:
            seen.add(url)
            out.append((url, text))
    out.sort(key=link_priority)
    return out


def link_priority(link):
    """Spreadsheets and yield-detail files first, PDFs last (stable sort keeps page order)."""
    url, text = link
    low, t = url.lower(), (text or "").lower()
    if "pdf" in t or low.endswith(".pdf") or low.endswith("-pdf"):
        return 3
    if "detailed" in t or "benchmark" in t or "excel" in t or low.endswith((".xlsx", ".xls")):
        return 0
    if "data" in low or "excel" in low:
        return 1
    return 2


def sniff(head):
    """Return file kind from the first bytes."""
    if head[:4] == b"PK\x03\x04":
        return "zip"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    if head[:5] == b"%PDF-":
        return "pdf"
    s = head[:512].lstrip().lower()
    if s.startswith(b"<!doctype html") or s.startswith(b"<html") or b"<html" in s:
        return "html"
    return "other"


def zip_kind(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    if "xl/workbook.xml" in names:
        return "xlsx"
    if "word/document.xml" in names:
        return "docx"
    return "zip"


def norm(v):
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return " ".join(str(v).split())


def is_text(v):
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return False
    s = norm(v)
    if not s:
        return False
    try:
        float(s.replace(",", ""))
        return False
    except ValueError:
        return True


def find_header_row(rows, max_scan=25):
    """Index of the first row with >=3 text cells and at least one header keyword."""
    for i, row in enumerate(rows[:max_scan]):
        texts = [norm(v).lower() for v in row if is_text(v)]
        if len(texts) >= 3 and any(k in t for t in texts for k in HEADER_KEYS):
            return i
    return None


def column_names(rows, h):
    """Header names, joining the row above (multi-row headers) when it has text."""
    width = max(len(r) for r in rows[: h + 1]) if rows else 0
    names = []
    for j in range(width):
        parts = []
        for r in ([rows[h - 1]] if h > 0 else []) + [rows[h]]:
            if j < len(r) and is_text(r[j]):
                parts.append(norm(r[j]))
        names.append(" | ".join(parts))
    # forward-fill a merged upper header across empty upper cells is not attempted: report raw
    return names


def pick_cols(names, *keys, exclude=()):
    out = []
    for j, n in enumerate(names):
        low = n.lower()
        if any(k in low for k in keys) and not any(x in low for x in exclude):
            out.append(j)
    return out


def state_of(v):
    s = norm(v).upper()
    if s in NE_VALUES:
        return "NE"
    if s in KS_VALUES:
        return "KS"
    if re.fullmatch(r"31\d{3}", s):
        return "NE"
    if re.fullmatch(r"20\d{3}", s):
        return "KS"
    return None


def crop_of(v):
    s = norm(v).upper()
    if "SOY" in s:
        return "soybeans"
    if "CORN" in s and "POP" not in s and "SWEET" not in s:
        return "corn"
    return None


def year_columns(names):
    return {j: YEAR_RE.findall(n) for j, n in enumerate(names) if YEAR_RE.search(n)}


def inspect_rows(rows, sheet_name):
    """Structure + counts for one sheet; never returns a yield value."""
    info = {"sheet": sheet_name, "n_rows": len(rows),
            "n_cols": max((len(r) for r in rows), default=0)}
    h = find_header_row(rows)
    info["header_row_index"] = h
    if h is None:
        info["first_text_rows"] = [[norm(v)[:40] for v in r if is_text(v)][:20] for r in rows[:6]]
        return info
    names = column_names(rows, h)
    info["columns"] = [n[:80] for n in names]
    info["year_columns"] = {names[j][:80]: ys for j, ys in year_columns(names).items()}
    state_cols = pick_cols(names, "state", exclude=("county",)) or pick_cols(names, "fips", "code")
    crop_cols = pick_cols(names, "crop", "commodity")
    prac_cols = pick_cols(names, "practice", "irrig")
    info["state_cols"] = [names[j] for j in state_cols]
    info["crop_cols"] = [names[j] for j in crop_cols]
    info["practice_cols"] = [names[j] for j in prac_cols]
    data = rows[h + 1:]
    crops, pracs = {}, {}
    sc = None
    for j in state_cols:
        if any(state_of(r[j]) for r in data if j < len(r)):
            sc = j
            break
    info["state_col_used"] = names[sc] if sc is not None else None
    cc = crop_cols[0] if crop_cols else None
    pc = prac_cols[0] if prac_cols else None
    neks = {}
    nonempty = {}
    numeric_cols = [j for j in range(len(names)) if j not in (sc, cc, pc)]
    for r in data:
        if cc is not None and cc < len(r) and is_text(r[cc]):
            k = norm(r[cc])[:40]
            crops[k] = crops.get(k, 0) + 1
        if pc is not None and pc < len(r) and is_text(r[pc]):
            k = norm(r[pc])[:40]
            pracs[k] = pracs.get(k, 0) + 1
        if sc is None or cc is None or sc >= len(r) or cc >= len(r):
            continue
        st, cr = state_of(r[sc]), crop_of(r[cc])
        if not st or not cr:
            continue
        pr = norm(r[pc])[:30] if pc is not None and pc < len(r) else "(none)"
        key = f"{st}|{cr}|{pr}"
        neks[key] = neks.get(key, 0) + 1
        for j in numeric_cols:
            if j < len(r) and r[j] is not None and not is_text(r[j]) and norm(r[j]) != "":
                nk = f"{key}|{names[j][:60]}"
                nonempty[nk] = nonempty.get(nk, 0) + 1
    info["crop_values_top"] = dict(sorted(crops.items(), key=lambda kv: -kv[1])[:40])
    info["practice_values"] = dict(sorted(pracs.items(), key=lambda kv: -kv[1])[:40])
    info["ne_ks_rows"] = neks
    info["ne_ks_nonempty_numeric_cells"] = nonempty
    return info


def read_xlsx(path):
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        out.append(inspect_rows(rows, ws.title))
    wb.close()
    return out


def read_xls(path):
    import xlrd
    wb = xlrd.open_workbook(path)
    out = []
    for sh in wb.sheets():
        rows = [sh.row_values(i) for i in range(sh.nrows)]
        out.append(inspect_rows(rows, sh.name))
    return out


def docx_text(path, limit=30000):
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>", "\n", xml)
    txt = re.sub(r"<[^>]+>", "", xml)
    return txt[:limit]


def fetch(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(MAX_BYTES + 1)
        return r.status, r.headers.get("Content-Type", ""), r.geturl(), data


def safe_name(url):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", urllib.parse.urlparse(url).path.strip("/"))
    return s[-120:] or "index"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/data")
    ap.add_argument("--out-dir", default="/out")
    a = ap.parse_args(argv)
    ddir = os.path.join(a.data_dir, "fsa_arcco")
    os.makedirs(ddir, exist_ok=True)
    os.makedirs(os.path.join(a.out_dir, "pages"), exist_ok=True)
    os.makedirs(os.path.join(a.out_dir, "docs"), exist_ok=True)
    report = {"pages": [], "files": [], "note": "structure and counts only; no yield values"}
    links = []
    for pg in PAGES:
        entry = {"url": pg}
        try:
            st, ct, final, data = fetch(pg)
            entry.update(status=st, final_url=final, bytes=len(data))
            with open(os.path.join(a.out_dir, "pages", safe_name(pg) + ".html"), "wb") as f:
                f.write(data)
            got = parse_links(data.decode("utf-8", "replace"), final)
            sel = select_links(got)
            entry["n_links"], entry["selected"] = len(got), [[u, t] for u, t in sel]
            links.extend(sel)
        except Exception as e:  # report and continue
            entry["error"] = f"{type(e).__name__}: {e}"[:300]
        report["pages"].append(entry)
        print("PAGE", json.dumps(entry)[:2000], flush=True)
    urls = []
    for u, t in links + [(u, "fallback") for u in FALLBACK_URLS]:
        if u not in [x[0] for x in urls]:
            urls.append((u, t))
    for u, t in urls[:MAX_FILES]:
        fe = {"url": u, "link_text": t}
        path = os.path.join(ddir, safe_name(u))
        try:
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                st, ct, final, data = fetch(u, timeout=300)
                fe.update(status=st, content_type=ct, final_url=final)
                if len(data) > MAX_BYTES:
                    fe["error"] = "too large"
                    report["files"].append(fe)
                    continue
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    f.write(data)
                os.replace(tmp, path)
            with open(path, "rb") as f:
                head = f.read(1024)
            kind = sniff(head)
            if kind == "zip":
                kind = zip_kind(path)
            fe.update(kind=kind, bytes=os.path.getsize(path))
            if kind == "html":
                # a document landing page: follow file links on it once
                with open(path, "rb") as f:
                    sub = parse_links(f.read().decode("utf-8", "replace"), u)
                files = [x for x in sub if re.search(r"\.(xlsx|xls|zip|docx|csv)(\?|$)", x[0], re.I)]
                fe["file_links_on_page"] = [[x[0], x[1]] for x in files[:10]]
                for x in files[:3]:
                    if x[0] not in [y[0] for y in urls] and len(urls) < MAX_FILES + 10:
                        urls.append((x[0], f"via {u}"))
            elif kind == "xlsx":
                fe["sheets"] = read_xlsx(path)
            elif kind == "xls":
                fe["sheets"] = read_xls(path)
            elif kind == "docx":
                txt = docx_text(path)
                with open(os.path.join(a.out_dir, "docs", safe_name(u) + ".txt"), "w", encoding="utf-8") as f:
                    f.write(txt)
                fe["docx_chars"] = len(txt)
        except Exception as e:
            fe["error"] = f"{type(e).__name__}: {e}"[:300]
        report["files"].append(fe)
        print("FILE", json.dumps(fe)[:4000], flush=True)
        time.sleep(1.0)
    # urls appended while looping (landing pages) are processed in a second pass
    done = {f["url"] for f in report["files"]}
    for u, t in urls:
        if u in done or len(report["files"]) >= MAX_FILES + 10:
            continue
        fe = {"url": u, "link_text": t}
        path = os.path.join(ddir, safe_name(u))
        try:
            if not (os.path.exists(path) and os.path.getsize(path) > 0):
                st, ct, final, data = fetch(u, timeout=300)
                fe.update(status=st, content_type=ct, final_url=final)
                tmp = path + ".part"
                with open(tmp, "wb") as f:
                    f.write(data[:MAX_BYTES])
                os.replace(tmp, path)
            with open(path, "rb") as f:
                kind = sniff(f.read(1024))
            if kind == "zip":
                kind = zip_kind(path)
            fe.update(kind=kind, bytes=os.path.getsize(path))
            if kind == "xlsx":
                fe["sheets"] = read_xlsx(path)
            elif kind == "xls":
                fe["sheets"] = read_xls(path)
            elif kind == "docx":
                txt = docx_text(path)
                with open(os.path.join(a.out_dir, "docs", safe_name(u) + ".txt"), "w", encoding="utf-8") as f:
                    f.write(txt)
                fe["docx_chars"] = len(txt)
        except Exception as e:
            fe["error"] = f"{type(e).__name__}: {e}"[:300]
        report["files"].append(fe)
        print("FILE2", json.dumps(fe)[:4000], flush=True)
        time.sleep(1.0)
    with open(os.path.join(a.out_dir, "fsa_inspect.json"), "w") as f:
        json.dump(report, f, indent=1)
    n_wb = sum(1 for f in report["files"] if f.get("sheets"))
    print(f"DONE pages={len(report['pages'])} files={len(report['files'])} workbooks={n_wb}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
