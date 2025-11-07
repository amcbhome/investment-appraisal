import streamlit as st
import pandas as pd
import numpy as np
from investment_model import (
    build_projection_inputs,
    inflate_series,
    compute_capital_allowances_schedule,
    compute_tax_schedule,
    compute_working_capital_movements,
    discounted_cashflows,
    irr,
    payback_period,
    discounted_payback_period,
    arr_average_profit
)

st.set_page_config(page_title="Investment Appraisal (ACCA style)", layout="wide")
st.title("💼 Investment Appraisal – NPV, IRR, Payback, ARR")

with st.sidebar:
    st.header("Project setup")
    years = st.number_input("Project life (years)", 1, 50, 4)
    currency = st.text_input("Currency symbol", "£")

    st.subheader("Capex & residual")
    capex_t0 = st.number_input("Initial investment at T0", value=500_000.0, step=10_000.0, format="%.2f")
    residual_nominal = st.number_input("Residual value (disposal proceeds) in final year", value=50_000.0, step=10_000.0, format="%.2f")

    st.subheader("Discounting & inflation")
    pricing_mode = st.radio("Method", ["Money (nominal)", "Real"], index=0)
    disc_rate_input = st.number_input("Discount rate (%)", value=10.0, step=0.5, format="%.2f")
    general_infl = st.number_input("General inflation (for converting between real/nominal) (%)", value=3.0, step=0.5, format="%.2f")
    sales_infl = st.number_input("Sales inflation (%) (money method)", value=3.0, step=0.5, format="%.2f")
    varcost_infl = st.number_input("Variable cost inflation (%) (money method)", value=3.0, step=0.5, format="%.2f")
    fixedcost_infl = st.number_input("Fixed cost inflation (%) (money method)", value=3.0, step=0.5, format="%.2f")

    st.subheader("Tax & capital allowances (UK-style RB)")
    tax_rate = st.number_input("Corporation tax rate (%)", value=25.0, step=1.0, format="%.2f")
    tax_lag_years = st.number_input("Tax payment lag (years)", min_value=0, max_value=5, value=1, step=1)
    wda_rate = st.number_input("Writing-down allowance (reducing-balance, %)", value=18.0, step=1.0, format="%.2f")
    pool_restrict_to_cost = st.checkbox("Restrict balancing adjustment to original cost (sensible cap)", value=True)

    st.subheader("Working capital")
    wc_pct_sales = st.number_input("Working capital as % of nominal sales", value=10.0, step=1.0, format="%.2f")

st.markdown("### Step 1 — Build or edit your per-year operating profile")

default = build_projection_inputs(
    years=years,
    base_sales=400_000.0,
    sales_growth=0.0,  # will be inflated separately if nominal method
    base_var_cost_rate=0.55,
    base_fixed_cost=80_000.0
)

st.caption("Tip: Edit sales/variable rate/fixed cost year by year below.")
df_inputs = st.data_editor(default, use_container_width=True, num_rows="dynamic")

# Compute nominal/real series
if pricing_mode == "Money (nominal)":
    sales = inflate_series(df_inputs["Sales"], sales_infl / 100.0)
    var_rate = df_inputs["VariableCostRate"]  # as proportion of sales
    var_cost = inflate_series(df_inputs["Sales"] * var_rate, varcost_infl / 100.0)
    fixed_cost = inflate_series(df_inputs["FixedCost"], fixedcost_infl / 100.0)
    discount_rate = disc_rate_input / 100.0
else:
    # Real method: keep series as entered (assumed real), discount with real rate
    # Convert nominal input discount rate to real if user mistakenly supplied nominal
    # Here we assume user already set the appropriate real discount rate in sidebar.
    sales = df_inputs["Sales"]
    var_cost = df_inputs["Sales"] * df_inputs["VariableCostRate"]
    fixed_cost = df_inputs["FixedCost"]
    discount_rate = disc_rate_input / 100.0

# Working capital movements (always computed on NOMINAL sales for realism)
# If Real method selected we still base WC % on displayed series; you can switch to nominal if you prefer.
wc_mov = compute_working_capital_movements(sales, wc_pct_sales / 100.0)

# Capital allowances schedule (RB pool, balancing adj at disposal in final year)
ca_df = compute_capital_allowances_schedule(
    capex=capex_t0,
    years=years,
    wda_rate=wda_rate / 100.0,
    disposal_value=residual_nominal,
    cap_to_cost=pool_restrict_to_cost
)

# Operating profit BEFORE capital allowances (no depreciation in tax)
op_profit_before_ca = sales - var_cost - fixed_cost

tax_df = compute_tax_schedule(
    op_profit_before_ca=op_profit_before_ca,
    ca_df=ca_df,
    tax_rate=tax_rate / 100.0,
    tax_lag_years=tax_lag_years
)

# Cash flows:
# T0: -capex - initial WC (wc_mov[0] is usually an outflow if sales>0) ; Tax paid at t may come from lag of t-1.
years_index = np.arange(0, years + 1, 1)
cf = pd.DataFrame(index=years_index)
cf.index.name = "Year"

# Build rows
cf["Sales"] = [0.0] + list(sales)
cf["VariableCosts"] = [0.0] + list(var_cost)
cf["FixedCosts"] = [0.0] + list(fixed_cost)
cf["OperatingProfitBeforeCA"] = [0.0] + list(op_profit_before_ca)
cf["CapitalAllowances"] = [0.0] + list(ca_df["Allowance"].values[:-1]) + [ca_df["BalancingAdj"].values[-1]]
cf["TaxableProfit"] = [0.0] + list(tax_df["TaxableProfit"])
cf["Tax@{}%".format(int(tax_rate))] = tax_df["TaxPayable"].reindex(cf.index, fill_value=0.0)

# Working capital movement:
cf["WC_Movement"] = wc_mov.reindex(cf.index, fill_value=0.0)

# Capex and residual:
cf["Capex"] = 0.0
cf.loc[0, "Capex"] = -capex_t0
cf["ResidualValue"] = 0.0
cf.loc[years, "ResidualValue"] = residual_nominal

# Operating cash flow (pre tax): EBITDA proxy = Sales - Var - Fixed
cf["OpCashFlow_preTax"] = cf["Sales"] - cf["VariableCosts"] - cf["FixedCosts"]

# Cash tax paid (lagged already placed in Tax column)
cf["CashTax"] = -cf["Tax@{}%".format(int(tax_rate))]

# Net cash flow (project): OpCF + tax + WC movement + Capex + Residual
cf["NetCashFlow"] = cf["OpCashFlow_preTax"] + cf["CashTax"] + cf["WC_Movement"] + cf["Capex"] + cf["ResidualValue"]

# Discounting
disc = discounted_cashflows(cf["NetCashFlow"].values, discount_rate)
cf["DiscountFactor"] = disc["df"]
cf["PV"] = disc["pv"]

npv_value = cf["PV"].sum()
irr_value = irr(cf["NetCashFlow"].values)
pb = payback_period(cf["NetCashFlow"].values)
dpb = discounted_payback_period(cf["NetCashFlow"].values, discount_rate)

# ARR using average accounting profit (after tax) over life / initial investment
# Accounting profit after tax approximated as TaxableProfit * (1 - tax_rate) (years 1..N)
avg_profit = (tax_df["TaxableProfit"] * (1 - tax_rate / 100.0)).mean()
arr_val = arr_average_profit(avg_profit, capex_t0)

st.markdown("### Step 2 — Results")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("NPV", f"{currency}{npv_value:,.0f}", help="Sum of discounted net cash flows.")
kpi2.metric("IRR", f"{irr_value*100:,.2f}%", help="Rate that makes NPV=0.")
kpi3.metric("Payback", "N/A" if np.isnan(pb) else f"{pb:.2f} yrs", help="Time until cumulative cash flow becomes positive.")
kpi4.metric("Discounted Payback", "N/A" if np.isnan(dpb) else f"{dpb:.2f} yrs")
kpi5.metric("ARR", f"{arr_val*100:,.2f}%", help="Average accounting return on initial investment.")

st.markdown("### Step 3 — Full cash-flow schedule")
st.dataframe(cf.style.format({
    "Sales": "{:,.0f}",
    "VariableCosts": "{:,.0f}",
    "FixedCosts": "{:,.0f}",
    "OperatingProfitBeforeCA": "{:,.0f}",
    "CapitalAllowances": "{:,.0f}",
    "TaxableProfit": "{:,.0f}",
    f"Tax@{int(tax_rate)}%": "{:,.0f}",
    "WC_Movement": "{:,.0f}",
    "Capex": "{:,.0f}",
    "ResidualValue": "{:,.0f}",
    "OpCashFlow_preTax": "{:,.0f}",
    "CashTax": "{:,.0f}",
    "NetCashFlow": "{:,.0f}",
    "DiscountFactor": "{:,.5f}",
    "PV": "{:,.0f}",
}), use_container_width=True)

# Downloads
csv = cf.to_csv(index=True).encode("utf-8")
st.download_button("⬇️ Download cash-flow table (CSV)", data=csv, file_name="investment_cashflows.csv", mime="text/csv")

st.markdown("---")
with st.expander("How this matches ACCA’s article (quick checklist)"):
    st.markdown("""
- **Relevant cash flows only**: excludes sunk costs and financing; discount rate represents cost of capital.  
- **Inflation**: choose **Money (nominal)** (inflate cash flows & use nominal rate) or **Real** (no inflation & real rate).  
- **Tax**: computed on **taxable profit using capital allowances (WDA RB)**, not depreciation; **paid one year in arrears**.  
- **Working capital**: % of sales; increases are outflows, releases are inflows in final year.  
- **Residual value**: included at the end; **balancing allowance/charge** handled via the pool.  
- **Outputs**: NPV, IRR, Payback, Discounted Payback, ARR, and a transparent schedule.
""")
