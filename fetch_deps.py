# fetch_deps.py - fetch the published 0.1.0 corn modules that soyheat.py reuses
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name (MV2, Munim, Inc.).
#
# The soybean job imports cornheat_data, cornheat_model and run_cornheat exactly
# as published in commit bf32f815 (pre-registration 0.1.0). Falls back to main
# only if the pinned commit cannot be fetched; prints which one and the sha256.
import hashlib
import sys
import time
import urllib.request

REPO = "https://raw.githubusercontent.com/munimtechnologies/corn-heat-tolerance/"
PIN = "bf32f815d447a305d19e4f71ea45387d8307c864"
FILES = ("cornheat_data.py", "cornheat_model.py", "run_cornheat.py", "test_cornheat.py")


def get(url):
    for k in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "corn-heat-tolerance/0.2"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:
            last = e
            time.sleep(5 * (k + 1))
    raise RuntimeError("%s: %s" % (url, last))


def main():
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
