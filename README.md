# investment-appraisal
# Investment Appraisal (ACCA-style) – Streamlit Web App

A transparent web app that replicates the ACCA investment appraisal workflow:

- **NPV, IRR, Payback, Discounted Payback, ARR**
- **Capital allowances** (reducing-balance WDA) with **balancing allowance/charge** at disposal
- **Tax in arrears**
- **Working capital** as a % of sales (increases = outflow; final release = inflow)
- **Inflation handling**: **Money (nominal)** or **Real** method
- Full **cash-flow schedule** with downloadable CSV

## Quick start

```bash
git clone <your-repo-url>.git
cd investment-appraisal
python -m venv .venv && source .venv/bin/activate  # (Windows: .venv\Scripts\activate)
pip install -r requirements.txt
streamlit run app.py
