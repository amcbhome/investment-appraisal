import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf   # <— for IRR()

# ──────────────────────────────────────────────
# Page setup
# ──────────────────────────────────────────────
st.set_page_config(page_title="ACCA Investment Appraisal", layout="wide")
st.title("💼 Investment Appraisal – ACCA Method (TAD + NPV)")

# ──────────────────────────────────────────────
# Sidebar inputs
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("Inputs")
    cost = st.number_input("Initial investment (£'000)", 0, 1_000_000, 160_000, step=10_000)
    disposal = st.number_input("Residual value (£'000)", 0, 1_000_000, 40_000, step=10_000)
    years = st.number_input("Asset life (years)", 1, 10, 4)
    wda_rate = st.number_input("Writing-down allowance (%)", 0.0, 100.0, 25.0) / 100
    tax_rate = st.number_input("Tax rate (%)", 0.0, 100.0, 30.0) / 100
    disc_rate = st.number_input("Discount rate (%)", 0.0, 30.0, 10.0) / 100
    sales_y1 = st.number_input("Sales – Year 1 (£'000)", 0, 1_000_000, 400_000, step=10_000)
    growth = st.number_input("Sales growth (%)", 0.0, 20.0, 3.0) / 100
    var_rate = st.number_input("Variable cost % of sales", 0.0, 1.0, 0.55)
    fixed_cost = st.number_input("Fixed cost (£'000)", 0, 1_000_000, 80_000, step=10_000)
    wc_pct = st.number_input("Working capital % of sales", 0.0, 100.0, 10.0) / 100

# ──────────────────────────────────────────────
# Step 0 – Input Data Summary
# ──────────────────────────────────────────────
input_data = {
    "Parameter": [
        "Initial investment (£'000)",
        "Residual value (£'000)",
        "Asset life (years)",
        "Writing-down allowance",
        "Tax rate",
        "Discount rate",
        "Sales – Year 1 (£'000)",
        "Sales growth",
        "Variable cost % of sales",
        "Fixed cost (£'000)",
        "Working capital % of sales"
    ],
    "Value": [
        cost,
        disposal,
        years,
        f"{wda_rate*100:.1f}%",
        f"{tax_rate*100:.1f}%",
        f"{disc_rate*100:.1f}%",
        sales_y1,
        f"{growth*100:.1f}%",
        f"{var_rate*100:.1f}%",
        fixed_cost,
        f"{wc_pct*100:.1f}%"
    ]
}
st.markdown("### Input Data Summary")
st.dataframe(pd.DataFrame(input_data), use_container_width=True)

# ──────────────────────────────────────────────
# Working 1 – Tax Benefits on TAD
# ──────────────────────────────────────────────
def working1_tad(cost, rate, years, disposal, tax_rate):
    twdv = cost
    rows = []
    for y in range(1, years):
        tad = twdv * rate
        twdv -= tad
        tax_benefit = tad * tax_rate
        rows.append([f"{y} – {int(rate*100)}% TAD", tad, tax_benefit, f"T{y+1}"])
    bal_allow = twdv - disposal
    tax_ben_bal = bal_allow * tax_rate
    rows.append([f"{years} – Balancing allowance", bal_allow, tax_ben_bal, f"T{years+1}"])
    return pd.DataFrame(rows, columns=[
        "Year", "Value", f"Tax benefit @ {int(tax_rate*100)}%", "Timing"
    ])

tad_df = working1_tad(cost, wda_rate, years, disposal, tax_rate)
st.markdown("### Working 1 – Tax benefits on tax-allowable depreciation (TAD)")
st.dataframe(
    tad_df.style.format({"Value": "{:,.0f}", f"Tax benefit @ {int(tax_rate*100)}%": "{:,.1f}"}),
    use_container_width=True,
)

# ──────────────────────────────────────────────
# Working 2 – Working Capital (Required Balances)
# ──────────────────────────────────────────────
def working2_wc(sales, pct):
    wc_req = [s * pct for s in sales]
    return pd.DataFrame({"Year": range(1, len(sales) + 1), "Working Capital Required": wc_req})

sales = np.array([sales_y1 * ((1 + growth) ** i) for i in range(years)])
wc_df = working2_wc(sales, wc_pct)
st.markdown("### Working 2 – Working Capital (Required balances)")
st.dataframe(wc_df.style.format({"Working Capital Required": "{:,.0f}"}), use_container_width=True)

# ──────────────────────────────────────────────
# NPV Pro-forma
# ──────────────────────────────────────────────
def npv_proforma(sales, var_rate, fixed_cost, cost, disposal, tad_df, wc_df, disc_rate):
    yrs = len(sales)
    df = pd.DataFrame({"Year": range(0, yrs + 1)})
    df["Sales"] = [0] + list(sales)
    df["Variable costs"] = [0] + list(sales * var_rate)
    df["Fixed costs"] = [0] + [fixed_cost] * yrs
    df["Operating profit"] = df["Sales"] - df["Variable costs"] - df["Fixed costs"]
    df.loc[0, "Operating profit"] = 0
    df["Capex"] = 0.0
    df.loc[0, "Capex"] = -cost
    df["Residual value"] = 0.0
    df.loc[yrs, "Residual value"] = disposal
    # Working capital change (outflow then release)
    wc = [wc_df["Working Capital Required"].iloc[0]] + list(
        np.diff([0] + list(wc_df["Working Capital Required"]))
    )
    wc[-1] = -wc_df["Working Capital Required"].iloc[-1]
    df["Δ Working Capital"] = wc
    # Tax-benefit timing (T2 → Year 2)
    tax_ben = pd.Series([0] * (yrs + 1))
    for row in tad_df.itertuples():
        pay_year = int(row.Timing[1:])
        if pay_year <= yrs:
            tax_ben[pay_year] += getattr(row, "_3")  # 3rd column = tax benefit
    df["Tax benefit"] = tax_ben
    # Net cash flow + discounting
    df["Net cash flow"] = (
        df["Operating profit"] + df["Δ Working Capital"] +
        df["Tax benefit"] + df["Capex"] + df["Residual value"]
    )
    df["Discount factor"] = (1 + disc_rate) ** (-df["Year"])
    df["Present value"] = df["Net cash flow"] * df["Discount factor"]
    return df

npv_df = npv_proforma(sales, var_rate, fixed_cost, cost, disposal, tad_df, wc_df, disc_rate)
npv_value = npv_df["Present value"].sum()

try:
    irr_val = npf.irr(npv_df["Net cash flow"])
except Exception:
    irr_val = float("nan")

st.markdown("### NPV Pro-forma")
st.dataframe(npv_df.style.format("{:,.0f}"), use_container_width=True)

# Download button
csv = npv_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download NPV schedule (CSV)", data=csv,
                   file_name="npv_schedule.csv", mime="text/csv")

# ──────────────────────────────────────────────
# Results summary
# ──────────────────────────────────────────────
st.subheader("Results")
c1, c2 = st.columns(2)
c1.metric("Net Present Value (NPV)", f"£{npv_value:,.0f}")
c2.metric("Internal Rate of Return (IRR)", f"{irr_val*100:,.2f}%")
