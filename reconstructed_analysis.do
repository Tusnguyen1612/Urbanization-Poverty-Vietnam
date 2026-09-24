*==============================================================================
* Impact of Urbanization on Poverty in Vietnam -- Stata analysis
*
* NOTE: RECONSTRUCTED script. The original project do-file was not archived, so
* this file was rebuilt from the paper's model specification and cross-checked
* against the Python replication in code/replicate_models.py (which reproduces
* the paper's sample sizes and estimates). It has NOT been run in Stata.
* Requires:  ssc install reghdfe, replace  |  ssc install ftools, replace
*==============================================================================
clear all
set more off
global root "."                       // set to the repository root
cap mkdir "$root/results"

* Ethnicity control in the household models:
*   dantoc = raw ethnic-group code (this is what reproduces the paper's Table 4)
*   kinh   = Kinh (=1) dummy (matches the variable label used in the paper text)
global ETH dantoc

*------------------------------------------------------------------------------
* 1. HOUSEHOLD LEVEL  (balanced panel: 1,895 households / 5,685 obs;
*                      regression sample: 5,592 obs after dropping missing nightlight)
*------------------------------------------------------------------------------
use "$root/data/merged_panel_hh_121416.dta", clear
drop if missing(hh_id)
bysort hh_id: gen n_waves = _N
keep if n_waves == 3
drop if missing(mean_nightlight)

egen prov_year = group(province year)
gen nl  = mean_nightlight
gen nl2 = nl^2

* outcomes: poor = P0, gap = P1, gap_sq = P2
foreach y in poor gap gap_sq {

    * Model A: district FE + province-year FE
    reghdfe `y' nl nl2 $ETH hh_dependency_share ys_hh, ///
        absorb(huyen prov_year) vce(cluster huyen)
    estimates store A_`y'
    nlcom (turning_point: -_b[nl]/(2*_b[nl2]))

    * Model B: household FE + district FE + province-year FE
    reghdfe `y' nl nl2 $ETH hh_dependency_share ys_hh, ///
        absorb(hh_id huyen prov_year) vce(cluster huyen)
    estimates store B_`y'
    nlcom (turning_point: -_b[nl]/(2*_b[nl2]))
}

* marginal effect of nightlight on P1 at selected nightlight levels (Model B)
quietly reghdfe gap nl nl2 $ETH hh_dependency_share ys_hh, ///
    absorb(hh_id huyen prov_year) vce(cluster huyen)
foreach x in 0 10 20 30 40 50 60 70 {
    di as text "NL = `x'"
    lincom _b[nl] + 2*`x'*_b[nl2]
}

esttab A_* B_* using "$root/results/household_models_stata.csv", ///
    replace csv se star(* 0.10 ** 0.05 *** 0.01) ///
    keep(nl nl2 $ETH hh_dependency_share ys_hh) stats(N r2)

*------------------------------------------------------------------------------
* 2. DISTRICT LEVEL  (balanced panel: 698 districts; 2,034 obs in regressions)
*------------------------------------------------------------------------------
use "$root/data/merged_panel_district_121416.dta", clear
bysort huyen: gen n_waves = _N
keep if n_waves == 3

egen prov_year = group(province year)
gen nl  = mean_nightlight
gen nl2 = nl^2

foreach y in P0 P1 P2 {
    reghdfe `y' nl nl2 ethnicity_ratio dist_dependency_share ys_district, ///
        absorb(huyen prov_year) vce(cluster tinh)
    estimates store D_`y'
}
esttab D_* using "$root/results/district_models_stata.csv", ///
    replace csv se star(* 0.10 ** 0.05 *** 0.01) stats(N r2)
