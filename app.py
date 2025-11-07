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

# ──────────────────────────────────────────────
# Page setup
# ──────────────────────────────────────────────
st.set_page_config(page_title="Investment Appraisal (ACCA style)", layout="wide")
st.title("💼 Investment Appraisal – NPV, IRR, Payback, ARR")

# --------------------------------------------------------------------
# Default ACCA "CBS Co" example preset
# --------------------------------------------------------------------
CBS_EXAMPLE = {
    "years": 4,
    "capex_t0": 500_000.0,
    "residual_nominal": 50_000.0,
    "sales_year1": 400_000.0,
    "sales_growth": 0.03,
    "var_cost_rate": 0.55,
    "fixed_cost": 80_000.0,
    "discount_rate": 10.0,
    "sales_infl": 3.0,
    "var_infl": 3.0,
    "fixed_infl": 3.0,
    "tax_rate": 25.0,
    "tax_lag": 1,
    "wda": 18.0,
    "wc_pct": 10.0
}

# ──────────────────────────────────────────────
# Sidebar inputs
# ──────────────────────────────────────────────
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
    general_infl = st.number_input("General inflation (%)", value=3.0, step=0.5, format="%.2f")
    sales_infl = st.number_input("Sales inflation (%)", value=3.0, step=0.5, format="%.2f")
    varcost_infl = st.number_input("Variable cost inflation (%)", value=3.0, step=0.5, format="%.2f")
    fixedcost_infl = st.number_input("Fixed cost inflation (%)", value=3.0, step=0.5, format="%.2f")

    st.subheader("Tax & capital allowances")
    tax_rate = st.number_input("Corporation tax rate (%)", value=25.0, step=1.0, format="%.2f")
    tax_lag_years = st.number_input("Tax payment lag (years)", min_value=0, max_value=5, value=1, step=1)
    wda_rate = st.number_input("Writing-down allowance (reducing-balance, %)", value=18.0, step=1.0, format="%.2f")
    pool_restrict_to_cost = st.checkbox("Restrict balancing adjustment to original cost (sensible cap)", value=True)

    st.subheader("Working capital")
    wc_pct_sales = st.number_input("Working capital as % of nominal sales", value=10.0, step=1.0, format="%.2f")

    # Load preset example
    if st.button("📥 Load ACCA 'CBS Co' Example"):
        years = CBS_EXAMPLE["years"]
        capex_t0 = CBS_EXAMPLE["capex_t0"]
        residual_nominal = CBS_EXAMPLE["residual_nominal"]
        disc_rate_input = CBS_EXAMPLE["discount_rate"]
        sales_infl = CBS_EXAMPLE["sales_infl"]
        varcost_infl = CBS_EXAMPLE["var_infl"]
        fixedcost_infl = CBS_EXAMPLE["fixed_infl"]
        tax_rate = CBS_EXAMPLE["tax_rate"]
        tax_lag_years = CBS_EXAMPLE["tax_lag"]
        wda_rate = CBS_EXAMPLE["wda"]
        wc_pct_sales = CBS_EXAMPLE["wc_pct"]
        st.session_state["df_inputs"] = build_projection_inputs(
            years=years,
            base_sales=CBS_EXAMPLE["sales_year1"],
            sales_growth=CBS_EXAMPLE["sales_growth"],
            base_var_cost_rate=CBS_EXAMPLE["var_cost_rate"],
            base_fixed_cost=CBS_EXAMPLE["fixed_cost"]
        )

# ──────────────────────────────────────────────
# Step 1 — Build or edit projection profile
# ──────────────────────────────────────────────
if "df_inputs" not in st.session_state:
    st.session_state["df_inputs"] = build_projection_inputs(
        years=years,
        base_sales=400_000.0,
        sales_growth=0.0,
        base_var_cost_rate=0.55,
        base_fixed_cost=80_000.0
    )

st.markdown("### Step 1 — Build or edit your per-year operating profile")
st.caption("Click **📥 Load ACCA ‘CBS Co’ Example** in the sidebar to auto-populate these values.")
df_inputs = st.data_editor(st.session_state["df_inputs"], use_container_width=True, num_rows="dynamic")

# ──────────────────────────────────────────────
# Step 2 — Calculations
# ──────────────────────────────────────────────
if pricing_mode == "Money (nominal)":
    sales = inflate_series(df_inputs["Sales"], sales_infl / 100.0)
    var_rate = df_inputs["VariableCostRate"]
    var_cost = inflate_series(df_inputs["Sales"] * var_rate, varcost_infl / 100.0)
    fixed_cost = inflate_series(df_inputs["FixedCost"], fixedcost_infl / 100.0)
    discount_rate = disc_rate_input / 100.0
else:
    sales = df_inputs["Sales"]
    var_cost = df_inputs["Sales"] * df_inputs["VariableCostRate"]
    fixed_cost = df_inputs["FixedCost"]
    discount_rate = disc_rate_input / 100.0

wc_mov = compute_working_capital_movements(sales, wc_pct_sales / 100.0)
ca_df = compute_capital_allowances_schedule(
    capex=capex_t0,
    years=years,
    wda_rate=wda_rate / 100.0,
    disposal_value=residual_nominal,
    cap_to_cost=pool_restrict_to_cost
)
op_profit_before_ca = sales - var_cost - fixed_cost
tax_df = compute_tax_schedule(
    op_profit_before_ca=op_profit_before_ca,
    ca_df=ca_df,
    tax_rate=tax_rate / 100.0,
    tax_lag_years=tax_lag_years
)

# Cash flows table
years_index = np.arange(0, years + 1, 1)
cf = pd.DataFrame(index=years_index)
cf.index.name = "Year"

cf["Sales"] = [0.0] + list(sales)
cf["VariableCosts"] = [0.0] + list(var_cost)
cf["FixedCosts"] = [0.0] + list(fixed_cost)
cf["OperatingProfitBeforeCA"] = [0.0] + list(op_profit_before_ca)
cf["CapitalAllowances"] = [0.0] + list(ca_df["Allowance"].values[:-1]) + [ca_df["BalancingAdj"].values[-1]]
cf["TaxableProfit"] = [0.0] + list(tax_df["TaxableProfit"])
cf["Tax@{}%".format(int(tax_rate))] = tax_df["TaxPayable"].reindex(cf.index, fill_value=0.0)
cf["WC_Movement"] = wc_mov.reindex(cf.index, fill_value=0.0)
cf["Capex"] = 0.0
cf.loc[0, "Capex"] = -capex_t0
cf["ResidualValue"] = 0.0
cf.loc[years, "ResidualValue"] = residual_nominal
cf["OpCashFlow_preTax"] = cf["Sales"] - cf["VariableCosts"] - cf["FixedCosts"]
cf["CashTax"] = -cf["Tax@{}%".format(int(tax_rate))]
cf["NetCashFlow"] = cf["OpCashFlow_preTax"] + cf["CashTax"] + cf["WC_Movement"] + cf["Capex"] + cf["ResidualValue"]

disc = discounted_cashflows(cf["NetCashFlow"].values, discount_rate)
cf["DiscountFactor"] = disc["df"]
cf["PV"] = disc["pv"]

npv_value = cf["PV"].sum()
irr_value = irr(cf["NetCashFlow"].values)
pb = payback_period(cf["NetCashFlow"].values)
dpb = discounted_payback_period(cf["NetCashFlow"].values, discount_rate)
avg_profit = (tax_df["TaxableProfit"] * (1 - tax_rate / 100.0)).mean()
arr_val = arr_average_profit(avg_profit, capex_t0)

# ──────────────────────────────────────────────
# Step 3 — Output
# ──────────────────────────────────────────────
st.markdown("### Step 2 — Results")

kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("NPV", f"{currency}{npv_value:,.0f}")
kpi2.metric("IRR", f"{irr_value*100:,.2f}%")
kpi3.metric("Payback", "N/A" if np.isnan(pb) else f"{pb:.2f} yrs")
kpi4.metric("Discounted Payback", "N/A" if np.isnan(dpb) else f"{dpb:.2f} yrs")
kpi5.metric("ARR", f"{arr_val*100:,.2f}%")

st.markdown("### Step 3 — Full cash-flow schedule")
st.dataframe(cf.style.format("{:,.0f}"), use_container_width=True)

csv = cf.to_csv(index=True).encode("utf-8")
st.download_button("⬇️ Download cash-flow table (CSV)", data=csv, file_name="investment_cashflows.csv", mime="text/csv")

st.markdown("---")
with st.expander("How this matches ACCA’s article"):
    st.markdown("""
- Relevant cash flows only – excludes sunk and financing costs.
- Inflation handled with nominal vs real choice.
- Tax calculated on taxable profit with WDA RB.
- Working capital increases = outflows; final release = inflow.
- Residual value and balancing allowance/charge handled automatically.
- Produces NPV, IRR, Payback, Discounted Payback, ARR and a transparent schedule.
""")
