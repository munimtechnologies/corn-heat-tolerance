# fetch_deps_irr.py - fetch the published modules that irrpractice.py reuses
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name (MV2, Munim, Inc.).
#
# 1) Refuses to continue until PREREG-IRR.md (with its marker) is public on main,
#    so no data are read before the pre-registration is committed.
# 2) Fetches cornheat_data, cornheat_model, run_cornheat, soyheat, dtstate and their
#    tests exactly as published in commit 6771a70f (pre-registration 0.3.0). Falls
#    back to main only if the pinned commit cannot be fetched; prints ref and sha256.
import hashlib
import sys
import time
import urllib.request

REPO = "https://raw.githubusercontent.com/munimtechnologies/corn-heat-tolerance/"
PIN = "6771a70f67d4c7d20c1b542f34aedc0056228960"
FILES = ("cornheat_data.py", "cornheat_model.py", "run_cornheat.py", "soyheat.py", "dtstate.py",
         "test_cornheat.py", "test_soyheat.py", "test_dtstate.py")
MARKER = b"PREREG-MARKER: corn-heat-tolerance-0.4.0-irrigation-prereg"


def get(url):
    last = None
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "corn-heat-tolerance/0.4"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(5 * (k + 1))
    raise RuntimeError("%s: %s" % (url, last))


def wait_prereg(tries=18, pause_s=300):
    for k in range(tries):
        try:
            blob = get(REPO + "main/PREREG-IRR.md?nocache=%d" % int(time.time()))
            if MARKER in blob:
                print("PREREG-IRR.md public:", hashlib.sha256(blob).hexdigest(), len(blob), flush=True)
                return True
            print("PREREG-IRR.md found without marker; waiting", flush=True)
        except RuntimeError as e:
            print("PREREG-IRR.md not public yet (%d/%d): %s" % (k + 1, tries, e), flush=True)
        time.sleep(pause_s)
    return False


def main():
    if not wait_prereg():
        print("ABORT: pre-registration 0.4.0 is not public; no data read.")
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
