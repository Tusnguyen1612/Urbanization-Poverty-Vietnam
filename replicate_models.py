#!/usr/bin/env python3
"""
Replication of the district- and household-level fixed-effects models in
"Impact of Urbanization on Poverty in Vietnam".

Reads the two merged panels in ../data/ (VHLSS 2012/2014/2016 + VIIRS nightlight)
and estimates the two-way / three-way fixed-effects models with pyfixest.

Usage
-----
    pip install pandas numpy pyfixest
    python code/replicate_models.py                     # ethnicity control as in the paper's Table 4
    python code/replicate_models.py --ethnicity kinh    # Kinh (=1) dummy instead

Outputs (CSV) are written to ../results/.
"""
import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pyfixest as pf

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
DATA, RESULTS = ROOT / "data", ROOT / "results"
RESULTS.mkdir(exist_ok=True)


# --------------------------------------------------------------------------- #
# Household panel
# --------------------------------------------------------------------------- #
def load_household():
    hh = pd.read_stata(DATA / "merged_panel_hh_121416.dta", convert_categoricals=False)
    print(f"[hh] raw rows: {len(hh):,}")

    hh = hh.dropna(subset=["hh_id"])
    waves = hh.groupby("hh_id")["year"].nunique()
    balanced = hh[hh["hh_id"].isin(waves[waves == 3].index)].copy()
    print(f"[hh] balanced panel: {balanced['hh_id'].nunique():,} households, "
          f"{len(balanced):,} observations (Table 2)")

    # regression sample: households whose district has a nightlight value
    reg = balanced.dropna(subset=["mean_nightlight"]).copy()
    reg["nl"] = reg["mean_nightlight"].astype(float)
    reg["nl2"] = reg["nl"] ** 2
    reg["prov_year"] = reg["province"].astype(str) + "_" + reg["year"].astype(int).astype(str)
    reg["hid"] = reg["hh_id"].astype(int)
    reg["dist"] = reg["huyen"].astype(int)
    reg["dep"] = reg["hh_dependency_share"].astype(float)
    reg["ys"] = reg["ys_hh"].astype(float)
    reg["kinh_d"] = reg["kinh"].astype(float)
    reg["dantoc_code"] = reg["dantoc"].astype(float)   # raw ethnic-group code (1 = Kinh ... 56)
    print(f"[hh] regression sample: {reg['hid'].nunique():,} households, "
          f"{reg['dist'].nunique()} districts, {reg['province'].nunique()} provinces, "
          f"{len(reg):,} observations (Table 4)")
    return balanced, reg


def household_models(reg, ethnicity):
    eth = {"dantoc": "dantoc_code", "kinh": "kinh_d"}[ethnicity]
    rows = []
    for y, label in [("poor", "P0"), ("gap", "P1"), ("gap_sq", "P2")]:
        for fe, model in [("dist + prov_year", "District + Province-Year FE"),
                          ("hid + dist + prov_year", "Household + District + Province-Year FE")]:
            m = pf.feols(f"{y} ~ nl + nl2 + {eth} + dep + ys | {fe}",
                         data=reg, vcov={"CRV1": "dist"})
            t = m.tidy()
            b1, b2 = t.loc["nl", "Estimate"], t.loc["nl2", "Estimate"]
            rows.append(dict(
                outcome=label, model=model, n=m._N, r2=round(m._r2, 3),
                b_nl=b1, se_nl=t.loc["nl", "Std. Error"], p_nl=t.loc["nl", "Pr(>|t|)"],
                b_nl2=b2, se_nl2=t.loc["nl2", "Std. Error"], p_nl2=t.loc["nl2", "Pr(>|t|)"],
                turning_point=-b1 / (2 * b2) if b2 < 0 else np.nan,
                b_ethnicity=t.loc[eth, "Estimate"], p_ethnicity=t.loc[eth, "Pr(>|t|)"],
                b_dependency=t.loc["dep", "Estimate"], p_dependency=t.loc["dep", "Pr(>|t|)"],
                b_schooling=t.loc["ys", "Estimate"], p_schooling=t.loc["ys", "Pr(>|t|)"],
            ))
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# District panel
# --------------------------------------------------------------------------- #
def load_district():
    d = pd.read_stata(DATA / "merged_panel_district_121416.dta", convert_categoricals=False)
    waves = d.groupby("huyen")["year"].nunique()
    d = d[d["huyen"].isin(waves[waves == 3].index)].copy()
    print(f"[dist] balanced panel: {d['huyen'].nunique()} districts, "
          f"{d['P0'].notna().sum():,} obs with poverty data (Table 1)")
    d["nl"] = d["mean_nightlight"].astype(float)
    d["nl2"] = d["nl"] ** 2
    d["eth"] = d["ethnicity_ratio"].astype(float)
    d["dep"] = d["dist_dependency_share"].astype(float)
    d["ys"] = d["ys_district"].astype(float)
    d["dist"] = d["huyen"].astype(int)
    d["prov_year"] = d["province"].astype(str) + "_" + d["year"].astype(int).astype(str)
    return d


def district_models(d):
    rows = []
    for y in ["P0", "P1", "P2"]:
        m = pf.feols(f"{y} ~ nl + nl2 + eth + dep + ys | dist + prov_year",
                     data=d, vcov={"CRV1": "province"})
        t = m.tidy()
        rows.append(dict(
            outcome=y, n=m._N, r2=round(m._r2, 3),
            b_nl=t.loc["nl", "Estimate"], se_nl=t.loc["nl", "Std. Error"], p_nl=t.loc["nl", "Pr(>|t|)"],
            b_nl2=t.loc["nl2", "Estimate"], p_nl2=t.loc["nl2", "Pr(>|t|)"],
            b_ethnicity_ratio=t.loc["eth", "Estimate"], p_ethnicity_ratio=t.loc["eth", "Pr(>|t|)"],
            b_dependency=t.loc["dep", "Estimate"], b_schooling=t.loc["ys", "Estimate"],
            p_schooling=t.loc["ys", "Pr(>|t|)"],
        ))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ethnicity", choices=["dantoc", "kinh"], default="dantoc",
                    help="household ethnicity control (default reproduces the paper's Table 4)")
    a = ap.parse_args()

    balanced, reg = load_household()
    print(balanced[["poor", "gap", "gap_sq", "mean_nightlight", "kinh",
                    "hh_dependency_share", "ys_hh"]].describe().T[["count", "mean", "std", "min", "max"]]
          .round(3), "\n")
    hh_res = household_models(reg, a.ethnicity)
    hh_res.to_csv(RESULTS / f"household_models_{a.ethnicity}.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(hh_res[["outcome", "model", "n", "r2", "b_nl", "p_nl", "b_nl2", "p_nl2",
                      "turning_point"]].round(5).to_string(index=False), "\n")

    dist = load_district()
    d_res = district_models(dist)
    d_res.to_csv(RESULTS / "district_models.csv", index=False)
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(d_res.round(5).to_string(index=False))
