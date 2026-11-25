# fetch_deps_yu.py - fetch the published modules that ldiff_yu.py reuses
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name (MV2, Munim, Inc.).
#
# 1) Refuses to continue until PREREG-LD-YU.md (with its marker) is public on main,
#    so no data are read before the 0.7.1 addendum is committed.
# 2) Fetches cornheat_data, cornheat_model, run_cornheat, soyheat and dtstate exactly
#    as published in commit 6771a70f (pre-registration 0.3.0), and ldiff.py from main
#    (published unchanged since pre-registration 0.7.0). Prints the ref and sha256 of
#    every file.
import hashlib
import sys
import time
import urllib.request

REPO = "https://raw.githubusercontent.com/munimtechnologies/corn-heat-tolerance/"
PIN = "6771a70f67d4c7d20c1b542f34aedc0056228960"
FILES = ("cornheat_data.py", "cornheat_model.py", "run_cornheat.py", "soyheat.py", "dtstate.py")
MARKER = b"PREREG-MARKER: corn-heat-tolerance-0.7.1-yu-prereg"
LD_MARKER = b"Pre-registered in PREREG-LD.md (marker corn-heat-tolerance-0.7.0-ld-prereg)."


def get(url):
    last = None
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "corn-heat-tolerance/0.7.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(5 * (k + 1))
    raise RuntimeError("%s: %s" % (url, last))


def wait_prereg(tries=18, pause_s=300):
    for k in range(tries):
        try:
            blob = get(REPO + "main/PREREG-LD-YU.md?nocache=%d" % int(time.time()))
            if MARKER in blob:
                print("PREREG-LD-YU.md public:", hashlib.sha256(blob).hexdigest(), len(blob), flush=True)
                return True
            print("PREREG-LD-YU.md found without marker; waiting", flush=True)
        except RuntimeError as e:
            print("PREREG-LD-YU.md not public yet (%d/%d): %s" % (k + 1, tries, e), flush=True)
        time.sleep(pause_s)
    return False


def main():
    if not wait_prereg():
        print("ABORT: pre-registration 0.7.1 is not public; no data read.")
        return 2
    for f in FILES:
        try:
            blob, ref = get(REPO + PIN + "/" + f), PIN
        except RuntimeError as e:
            print("pinned fetch failed, using main:", e)
            blob, ref = get(REPO + "main/" + f), "main"
        with open(f, "wb") as fh:
            fh.write(blob)
        print(f, ref, hashlib.sha256(blob).hexdigest(), len(blob))
    blob = get(REPO + "main/ldiff.py")
    if LD_MARKER not in blob:
        print("ABORT: ldiff.py on main is not the 0.7.0 module")
        return 2
    with open("ldiff.py", "wb") as fh:
        fh.write(blob)
    print("ldiff.py main", hashlib.sha256(blob).hexdigest(), len(blob))
    return 0


if __name__ == "__main__":
    sys.exit(main())
