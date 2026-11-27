# rcz_inspect.py - structure-only look at Raghuram & Coffel's Zenodo archive
# (doi:10.5281/zenodo.20185245, CC BY 4.0) for pre-registration 0.8.1.
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name (MV2, Munim, Inc.).
#
# Downloads rep.7z once (cached on the data volume), checks the md5 Zenodo lists,
# extracts it, and writes /out/rcz_structure.json: every file with its size, and for
# each R data file its object names, column names, dtypes and row counts. It never
# prints or saves a data value. It copies the authors' notebook and text/code files to
# /out/code/ so their exact steps can be read before 0.8.1 is written. Nothing from the
# archive is executed.
import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request

URL = "https://zenodo.org/records/20185245/files/rep.7z?download=1"
MD5 = "3d845e0d3f2f947051b86ec8f2b4e646"
CODE_EXT = (".ipynb", ".txt", ".r", ".R", ".md", ".py", ".csv.meta")
MAX_CODE_BYTES = 5_000_000


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(dest):
    if os.path.exists(dest) and md5(dest) == MD5:
        print("archive cached", dest, flush=True)
        return
    req = urllib.request.Request(URL, headers={"User-Agent": "corn-heat-tolerance/0.8.0 (structure check)"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dest + ".part", "wb") as fh:
        shutil.copyfileobj(r, fh)
    os.replace(dest + ".part", dest)


def describe_r(path):
    try:
        import pyreadr
    except ImportError as e:
        return {"error": "pyreadr missing: %s" % e}
    try:
        res = pyreadr.read_r(path)
    except Exception as e:                      # rasters and S4 objects are not readable
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:300])}
    out = {}
    for name, df in res.items():
        try:
            out[str(name)] = {"rows": int(df.shape[0]), "cols": int(df.shape[1]),
                              "columns": [str(c) for c in df.columns][:200],
                              "dtypes": [str(t) for t in df.dtypes][:200]}
        except Exception as e:
            out[str(name)] = {"error": str(e)[:300]}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.data_dir, exist_ok=True)
    arc = os.path.join(a.data_dir, "rep.7z")
    fetch(arc)
    got = md5(arc)
    report = {"url": URL, "md5_expected": MD5, "md5": got, "md5_ok": got == MD5,
              "archive_bytes": os.path.getsize(arc), "files": [], "r_objects": {}}
    if got != MD5:
        print("ABORT: md5 mismatch", got, flush=True)
        with open(os.path.join(a.out_dir, "rcz_structure.json"), "w") as fh:
            json.dump(report, fh, indent=1)
        return 2
    import py7zr
    ext = "/tmp/rcz"
    shutil.rmtree(ext, ignore_errors=True)
    os.makedirs(ext)
    with py7zr.SevenZipFile(arc, "r") as z:
        z.extractall(ext)
    code_dir = os.path.join(a.out_dir, "code")
    os.makedirs(code_dir, exist_ok=True)
    for root, _dirs, files in os.walk(ext):
        for f in sorted(files):
            p = os.path.join(root, f)
            rel = os.path.relpath(p, ext).replace(os.sep, "/")
            size = os.path.getsize(p)
            report["files"].append({"path": rel, "bytes": size})
            low = f.lower()
            if low.endswith((".rds", ".rdata", ".rda")):
                report["r_objects"][rel] = describe_r(p)
            if f.endswith(CODE_EXT) and size <= MAX_CODE_BYTES:
                dst = os.path.join(code_dir, rel.replace("/", "__"))
                shutil.copyfile(p, dst)
    report["n_files"] = len(report["files"])
    with open(os.path.join(a.out_dir, "rcz_structure.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print("files:", report["n_files"], "r objects:", len(report["r_objects"]), flush=True)
    for x in report["files"]:
        print(x["bytes"], x["path"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
