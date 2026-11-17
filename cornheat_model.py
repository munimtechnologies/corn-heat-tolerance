# cornheat_model.py - panel regressions for corn-heat-tolerance (MV2, Munim, Inc.)
# SPDX-License-Identifier: Apache-2.0
# Made with AI agents working in MV2's name.
#
# log(yield) = county-by-era FE + state-by-era quadratic trend
#              + era-specific [GDD(10..b), EDD(>b), P, P^2] + error
# with two-way cluster-robust variance (state, year), Cameron-Gelbach-Miller.

import math

import numpy as np


def group_index(keys):
    """Map a list of hashable keys to 0..G-1 integer codes."""
    lut = {}
    out = np.empty(len(keys), dtype=np.int64)
    for i, k in enumerate(keys):
        j = lut.get(k)
        if j is None:
            j = len(lut)
            lut[k] = j
        out[i] = j
    return out, len(lut)


def demean(mat, g, ng):
    """Subtract group means (in place) from each column of a 2-D array."""
    cnt = np.bincount(g, minlength=ng).astype(float)
    for j in range(mat.shape[1]):
        s = np.bincount(g, weights=mat[:, j], minlength=ng)
        mat[:, j] -= (s / cnt)[g]
    return mat


def cluster_meat(scores, cl):
    codes, ng = group_index(list(cl))
    k = scores.shape[1]
    sums = np.zeros((ng, k))
    for j in range(k):
        sums[:, j] = np.bincount(codes, weights=scores[:, j], minlength=ng)
    adj = ng / (ng - 1.0) if ng > 1 else 1.0
    return adj * (sums.T @ sums), ng


def ols_twoway(X, y, cl1, cl2):
    """OLS on already-demeaned X, y. Returns dict with beta, V (two-way),
    V1, V2 (one-way), ssr, n, and cluster counts."""
    XtX = X.T @ X
    bread = np.linalg.pinv(XtX)
    beta = bread @ (X.T @ y)
    e = y - X @ beta
    S = X * e[:, None]
    m1, g1 = cluster_meat(S, cl1)
    m2, g2 = cluster_meat(S, cl2)
    m12, g12 = cluster_meat(S, [(a, b) for a, b in zip(cl1, cl2)])
    V1 = bread @ m1 @ bread
    V2 = bread @ m2 @ bread
    V = bread @ (m1 + m2 - m12) @ bread
    fallback = False
    if np.any(np.diag(V) <= 0):
        V = V1 + V2          # conservative fallback, flagged in output
        fallback = True
    return {"beta": beta, "V": V, "V1": V1, "V2": V2, "ssr": float(e @ e),
            "n": int(len(y)), "g1": g1, "g2": g2, "fallback": fallback}


def p_two_sided(z):
    return math.erfc(abs(z) / math.sqrt(2.0))


def build_design(rows, eras, b=29, season="MarAug", index_coef=None):
    """rows: list of dicts with fips, state, year, logy, dd (dict season ->
    list of degree days above 0..40) and P (dict season -> mm).
    eras: list of (label, y0, y1). A row enters the era whose years hold it.
    If index_coef is given ({era_label: beta4}) the 4 weather columns are
    replaced by one column per era: the weather index beta4 . w.
    Returns X, y, names, cl_state, cl_year (after FE demeaning)."""
    era_of = []
    for r in rows:
        lab = None
        for (L, y0, y1) in eras:
            if y0 <= r["year"] <= y1:
                lab = L
                break
        era_of.append(lab)
    keep = [i for i, L in enumerate(era_of) if L is not None]
    labels = [e[0] for e in eras]
    mids = {L: (y0 + y1) / 2.0 for (L, y0, y1) in eras}
    se_pairs = sorted({(rows[i]["state"], era_of[i]) for i in keep})
    se_col = {p: j for j, p in enumerate(se_pairs)}
    nw = 1 if index_coef is not None else 4
    wnames = ["INDEX"] if index_coef is not None else ["GDD", "EDD", "P", "P2"]
    names = ["%s_%s" % (w, L) for L in labels for w in wnames]
    ntr = 2 * len(se_pairs)
    names += ["trend1_%s_%s" % p for p in se_pairs] + ["trend2_%s_%s" % p for p in se_pairs]
    n = len(keep)
    X = np.zeros((n, nw * len(labels) + ntr))
    y = np.zeros(n)
    fe_keys, cs, cy = [], [], []
    for a, i in enumerate(keep):
        r = rows[i]
        L = era_of[i]
        li = labels.index(L)
        dd = r["dd"][season]
        gdd = dd[10] - dd[b]
        edd = dd[b]
        p = r["P"][season] / 100.0      # decimetres
        w = [gdd, edd, p, p * p]
        if index_coef is not None:
            c = index_coef[L]
            X[a, li] = sum(ci * wi for ci, wi in zip(c, w))
        else:
            X[a, 4 * li: 4 * li + 4] = w
        t = (r["year"] - mids[L]) / 10.0
        j = se_col[(r["state"], L)]
        X[a, nw * len(labels) + j] = t
        X[a, nw * len(labels) + len(se_pairs) + j] = t * t
        y[a] = r["logy"]
        fe_keys.append((r["fips"], L))
        cs.append(r["state"])
        cy.append(r["year"])
    g, ng = group_index(fe_keys)
    demean(X, g, ng)
    y = y - (np.bincount(g, weights=y, minlength=ng) / np.bincount(g, minlength=ng))[g]
    # drop all-zero columns (e.g. a state-era with a single county-year)
    nz = np.abs(X).sum(axis=0) > 1e-12
    X = X[:, nz]
    names = [nm for nm, k in zip(names, nz) if k]
    return X, y, names, cs, cy


def fit(rows, eras, b=29, season="MarAug", index_coef=None):
    X, y, names, cs, cy = build_design(rows, eras, b, season, index_coef)
    res = ols_twoway(X, y, cs, cy)
    res["names"] = names
    return res


def coef(res, name):
    j = res["names"].index(name)
    return float(res["beta"][j]), float(math.sqrt(res["V"][j, j]))


def diff_test(res, a, b):
    """Test beta[a] - beta[b] = 0 using the full two-way covariance."""
    ia, ib = res["names"].index(a), res["names"].index(b)
    d = float(res["beta"][ia] - res["beta"][ib])
    v = float(res["V"][ia, ia] + res["V"][ib, ib] - 2 * res["V"][ia, ib])
    fallback = False
    if not v > 0:   # two-way contrast variance not positive: conservative sum
        W = res["V1"] + res["V2"]
        v = float(W[ia, ia] + W[ib, ib] - 2 * W[ia, ib])
        fallback = True
    se = math.sqrt(v) if v > 0 else float("nan")
    z = d / se if se == se and se > 0 else float("nan")
    p = p_two_sided(z) if z == z else float("nan")
    return {"diff": d, "se": se, "z": z, "p": p, "fallback": fallback}
