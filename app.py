import streamlit as st
import pandas as pd
import numpy as np
from calculations import working1_capital_allowances, working2_working_capital, npv_proforma, irr

st.set_page_config(page_title="ACCA Investment Appraisal", layout="wide")
st.title("💼 Investment Appraisal (ACCA Method)")

# ─── Inputs ───────────────────────────────────
with st.sidebar:
    st.header("Project Data")
    years = st.number_input("Project life (yrs)",1,20,4)
    cost = st.number_input("Initial Investment",10000,10_000_000,500_000,step=10_000)
    disposal = st.number_input("Residual Value",0,1_000_000,50_000,step=10_000)
    sales_y1 = st.number_input("Sales Year 1",10000,10_000_000,400_000,step=10_000)
    growth = st.number_input("Sales growth %",0.0,20.0,3.0)/100
    var_rate = st.number_input("Variable cost % of sales",0.0,1.0,0.55)
    fixed_cost = st.number_input("Fixed cost (£ p.a.)",0,1_000_000,80_000,step=10_000)
    wda = st.number_input("WDA (%)",0.0,100.0,18.0)/100
    tax_rate = st.number_input("Tax (%)",0.0,100.0,25.0)/100
    discount = st.number_input("Discount rate (%)",0.0,30.0,10.0)/100
    wc_pct = st.number_input("Working capital % of sales",0.0,100.0,10.0)/100

# ─── Workings ─────────────────────────────────
sales = np.array([sales_y1*((1+growth)**i) for i in range(years)])
ca_df = working1_capital_allowances(cost,wda,years,disposal)
wc_df = working2_working_capital(sales,wc_pct)
npv_df = npv_proforma(sales,var_rate,fixed_cost,cost,disposal,ca_df,wc_df,tax_rate,discount)

# ─── Results ──────────────────────────────────
npv_value = npv_df["PV"].sum()
irr_value = irr(npv_df["NetCashFlow"].values)

st.subheader("Results Summary")
col1,col2 = st.columns(2)
col1.metric("Net Present Value",f"£{npv_value:,.0f}")
col2.metric("Internal Rate of Return",f"{irr_value*100:,.2f}%")

# ─── Display Workings ─────────────────────────
st.markdown("### Working 1 – Capital Allowances")
st.dataframe(ca_df.style.format("{:,.0f}"),use_container_width=True)

st.markdown("### Working 2 – Working Capital Movements")
st.dataframe(wc_df.style.format("{:,.0f}"),use_container_width=True)

st.markdown("### NPV Pro forma")
st.dataframe(npv_df.style.format("{:,.0f}"),use_container_width=True)

# download
csv = npv_df.to_csv(index=False).encode("utf-8")
st.download_button("⬇️ Download NPV Schedule (CSV)",csv,"npv_schedule.csv","text/csv")
