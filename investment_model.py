import numpy as np
import pandas as pd

def build_projection_inputs(years:int, base_sales:float, sales_growth:float, base_var_cost_rate:float, base_fixed_cost:float) -> pd.DataFrame:
    """Create an editable per-year table."""
    idx = np.arange(1, years+1)
    sales = [base_sales * ((1 + sales_growth) ** (t-1)) for t in idx]
    df = pd.DataFrame({
        "Year": idx,
        "Sales": sales,
        "VariableCostRate": [base_var_cost_rate]*years,  # proportion of sales (e.g., 0.55)
        "FixedCost": [base_fixed_cost]*years
    })
    return df

def inflate_series(series: pd.Series, rate: float) -> pd.Series:
    """Inflate each period forward by rate, compounding from Year 1 baseline."""
    s = series.reset_index(drop=True).astype(float).copy()
    out = []
    for i, v in enumerate(s, start=1):
        out.append(v * ((1 + rate) ** (i-1)))
    return pd.Series(out, index=range(1, len(s)+1))

def compute_capital_allowances_schedule(capex: float, years: int, wda_rate: float, disposal_value: float, cap_to_cost=True) -> pd.DataFrame:
    """
    Reducing-balance WDA with balancing adjustment at disposal (final year).
    - TWDV_0 = capex
    - Year 1..N-1: Allowance = wda_rate * TWDV_{t-1}
    - Year N: balancing adjustment = TWDV_{N-1} - disposal_value (capped if desired)
      If positive => balancing allowance (deduction); if negative => balancing charge (adds to taxable profit)
    Returns df indexed 1..N with columns: TWDV_start, Allowance, TWDV_end, BalancingAdj (only in N).
    """
    years_idx = np.arange(1, years+1)
    twdv_start = np.zeros(years)
    allowance = np.zeros(years)
    twdv_end = np.zeros(years)
    bal_adj = np.zeros(years)

    twdv = capex
    for y in years_idx:
        twdv_start[y-1] = twdv
        if y < years:
            allowance[y-1] = wda_rate * twdv
            twdv = twdv - allowance[y-1]
            twdv_end[y-1] = twdv
        else:
            # final year: balancing adjustment
            # cap disposal used for pool to original cost if requested
            disp = min(disposal_value, capex) if cap_to_cost else disposal_value
            bal = twdv - disp
            bal_adj[y-1] = bal  # +ve allowance, -ve charge
            twdv_end[y-1] = 0.0

    df = pd.DataFrame({
        "Year": years_idx,
        "TWDV_Start": twdv_start,
        "Allowance": allowance,
        "TWDV_End": twdv_end,
        "BalancingAdj": bal_adj
    }).set_index("Year")
    return df

def compute_tax_schedule(op_profit_before_ca: pd.Series, ca_df: pd.DataFrame, tax_rate: float, tax_lag_years:int=1) -> pd.DataFrame:
    """
    Compute taxable profit and cash tax payments with lag.
    Taxable profit = op_profit_before_ca - CA (allowances or balancing adj).
    Cash tax of year t is paid at t+lag.
    """
    years = len(op_profit_before_ca)
    idx = np.arange(1, years+1)
    ca_vec = ca_df["Allowance"].values[:-1].tolist() + [ca_df["BalancingAdj"].values[-1]]
    taxable = op_profit_before_ca.values - np.array(ca_vec)

    tax_payable = np.maximum(taxable, 0.0) * tax_rate  # losses carried forward ignored for simplicity
    # Create a cash schedule with lag
    cash_tax = np.zeros(years + tax_lag_years + 1)  # allow spill
    for t in range(years):
        pay_year = t + 1 + tax_lag_years
        if pay_year <= years:
            cash_tax[pay_year] += tax_payable[t]

    out = pd.DataFrame({
        "Year": idx,
        "TaxableProfit": taxable,
    }).set_index("Year")
    # align to 0..years for app table (we’ll reindex in app)
    tax_paid = pd.Series(0.0, index=np.arange(0, years+1))
    for t in range(len(cash_tax)):
        year_index = t
        if year_index <= years:
            tax_paid.iloc[year_index] = cash_tax[t]

    out_full = out.copy()
    out_full["TaxPayable"] = tax_paid.reindex(out_full.index, fill_value=0.0)
    return out_full

def compute_working_capital_movements(sales: pd.Series, wc_pct: float) -> pd.Series:
    """
    WC each year = wc_pct * that year's sales; movement = delta WC.
    Year 0: outflow equals WC required for Year 1; final year: release WC back (inflow).
    Returns series indexed 0..N with movements.
    """
    years = len(sales)
    wc_required = [wc_pct * s for s in sales.values]
    wc_required = [wc_required[0]] + wc_required  # Year 0 requirement based on Year1 sales
    # movements from 0..N: delta
    wc_mov = [wc_required[0]]  # initial outflow at T0
    for t in range(1, len(wc_required)):
        wc_mov.append(wc_required[t] - wc_required[t-1])
    # release all in final year (N): negative requirement -> inflow
    wc_mov[-1] = -wc_required[-2]
    return pd.Series(wc_mov, index=np.arange(0, years+1))

def discounted_cashflows(cashflows: np.ndarray, r: float) -> dict:
    idx = np.arange(0, len(cashflows))
    df = (1 + r) ** (-idx)
    pv = cashflows * df
    return {"df": df, "pv": pv}

def irr(cashflows: np.ndarray, guess: float = 0.1) -> float:
    # Robust IRR with numpy; fallback to nan if no sign change
    if not (np.any(cashflows > 0) and np.any(cashflows < 0)):
        return np.nan
    try:
        return np.irr(cashflows)
    except Exception:
        # Newton fallback
        r = guess
        for _ in range(100):
            idx = np.arange(len(cashflows))
            denom = (1 + r) ** idx
            npv = np.sum(cashflows / denom)
            d_npv = np.sum(-idx * cashflows / ((1 + r) ** (idx + 1)))
            if abs(d_npv) < 1e-12:
                break
            r_new = r - npv / d_npv
            if abs(r_new - r) < 1e-8:
                r = r_new
                break
            r = r_new
        return r

def payback_period(cashflows: np.ndarray) -> float:
    cum = np.cumsum(cashflows)
    if cum[-1] < 0:
        return np.nan
    for t in range(len(cum)):
        if cum[t] >= 0:
            if t == 0:
                return 0.0
            prev = cum[t-1]
            inc = cashflows[t]
            if inc == 0:
                return float(t)
            frac = -prev / inc
            return (t-1) + frac
    return np.nan

def discounted_payback_period(cashflows: np.ndarray, r: float) -> float:
    idx = np.arange(len(cashflows))
    pv = cashflows / ((1 + r) ** idx)
    cum = np.cumsum(pv)
    if cum[-1] < 0:
        return np.nan
    for t in range(len(cum)):
        if cum[t] >= 0:
            if t == 0:
                return 0.0
            prev = cum[t-1]
            inc = pv[t]
            if inc == 0:
                return float(t)
            frac = -prev / inc
            return (t-1) + frac
    return np.nan

def arr_average_profit(avg_annual_profit_after_tax: float, initial_investment: float) -> float:
    if initial_investment == 0:
        return np.nan
    return avg_annual_profit_after_tax / initial_investment
