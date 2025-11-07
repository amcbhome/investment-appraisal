import pandas as pd
import numpy as np

def working1_capital_allowances(cost, rate, years, disposal, cap_to_cost=True):
    """Compute capital allowances (reducing balance) and balancing adjustment."""
    tbl = []
    twdv = cost
    for y in range(1, years):
        allowance = twdv * rate
        twdv -= allowance
        tbl.append((y, twdv + allowance, allowance, twdv, 0))
    # final year
    disp = min(disposal, cost) if cap_to_cost else disposal
    bal_adj = twdv - disp
    tbl.append((years, twdv, 0, 0, bal_adj))
    df = pd.DataFrame(tbl, columns=["Year","TWDV_start","Allowance","TWDV_end","BalancingAdj"])
    return df

def working2_working_capital(sales, pct):
    """Working capital requirement as % of next year’s sales."""
    wc = [sales[0]*pct]
    for i in range(1,len(sales)):
        wc.append(sales[i]*pct)
    mov = [wc[0]]
    for i in range(1,len(wc)):
        mov.append(wc[i]-wc[i-1])
    mov[-1] = -wc[-1]   # release in final year
    df = pd.DataFrame({"Year":range(0,len(sales)),"Movement":mov})
    return df

def npv_proforma(sales, var_rate, fixed_cost, capex, disposal, ca_df, wc_df, tax_rate, discount):
    """Build full NPV schedule combining workings."""
    years = len(sales)
    df = pd.DataFrame({"Year":range(0,years+1)})
    df["Sales"] = [0]+list(sales)
    df["VariableCost"] = [0]+list(sales*var_rate)
    df["FixedCost"] = [0]+[fixed_cost]*years
    df["OperatingProfitBeforeCA"] = df["Sales"]-df["VariableCost"]-df["FixedCost"]
    df.loc[0,"OperatingProfitBeforeCA"]=0
    df["CapitalAllowance"] = [0]+list(ca_df["Allowance"].values[:-1])+[ca_df["BalancingAdj"].values[-1]]
    df["TaxableProfit"] = df["OperatingProfitBeforeCA"]-df["CapitalAllowance"]
    df["Tax"] = -np.maximum(df["TaxableProfit"],0)*tax_rate
    df["WC_Movement"] = wc_df["Movement"]
    df["Capex"] = 0.0
    df.loc[0,"Capex"]=-capex
    df["Residual"] = 0.0
    df.loc[years,"Residual"]=disposal
    df["NetCashFlow"]=df["OperatingProfitBeforeCA"]+df["Tax"]+df["WC_Movement"]+df["Capex"]+df["Residual"]
    df["DF"]=(1+discount)**(-df["Year"])
    df["PV"]=df["NetCashFlow"]*df["DF"]
    return df

def irr(cfs):
    try:
        return np.irr(cfs)
    except Exception:
        return np.nan
