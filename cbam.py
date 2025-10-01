# ---------------------- Industrial CBAM Dashboard ----------------------
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Industrial CBAM Dashboard", layout="wide")
st.title("Industrial CBAM Dashboard for Indian Manufacturers")
st.markdown("""
Upload your operational CSV, calculate Scope 1, 2, 3 emissions, CBAM fees, and scenario-based reductions automatically.
""")

# ---------------------- Dynamic Emission Factor CSV ----------------------
st.header("1. Upload Emission Factor CSV (Optional)")
st.markdown("CSV should have columns: Category, Subcategory, EmissionFactor")
emission_factor_file = st.file_uploader("Upload Emission Factor CSV", type=["csv"])
default_factors = {
    "products": {"Steel":1.8, "Cement":0.9, "Aluminium":12.0, "Fertilizer":3.0},
    "fuels": {"Coal":2.5, "Diesel":2.7, "Natural Gas":2.0},
    "electricity":0.7,
    "transport":{"Truck":0.2, "Rail":0.05, "Ship":0.01, "Air":0.6}
}

if emission_factor_file:
    try:
        df_factors = pd.read_csv(emission_factor_file)
        # Convert to nested dicts
        products = df_factors[df_factors.Category=="Product"].set_index("Subcategory")["EmissionFactor"].to_dict()
        fuels = df_factors[df_factors.Category=="Fuel"].set_index("Subcategory")["EmissionFactor"].to_dict()
        transport = df_factors[df_factors.Category=="Transport"].set_index("Subcategory")["EmissionFactor"].to_dict()
        electricity = float(df_factors[df_factors.Category=="Electricity"]["EmissionFactor"].values[0])
        emission_factors = {"products":products,"fuels":fuels,"transport":transport,"electricity":electricity}
        st.success("Emission factors loaded successfully")
    except:
        st.warning("Error in reading emission factor CSV, using default factors")
else:
    emission_factors = default_factors

# ---------------------- Upload Raw Data ----------------------
st.header("2. Upload Raw Data CSV")
st.markdown("CSV must contain: Product, Quantity(t), Electricity(MWh), Fuel Type, Fuel Quantity, Purchased Materials(t), Transport Distance(km), Transport Mode")
uploaded_file = st.file_uploader("Upload Operational Data CSV", type=["csv"], key="data_csv")
if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
else:
    st.warning("Upload CSV to proceed")
    st.stop()

st.subheader("Raw Data Preview")
st.dataframe(df_raw)

# ---------------------- EU ETS Prices ----------------------
st.header("3. EU ETS Carbon Price")
eu_ets_price = st.number_input("EU ETS Price (€ per tCO₂)", min_value=0.0, value=100.0)
local_price = st.number_input("Local Carbon Price (€ per tCO₂)", min_value=0.0, value=0.0)

# ---------------------- Scenario Templates ----------------------
st.header("4. Scenario Templates")
templates = {
    "Low Reduction":{"Solar %":10,"Efficiency %":5,"Investment (€)":1000},
    "Medium Reduction":{"Solar %":40,"Efficiency %":15,"Investment (€)":5000},
    "High Reduction":{"Solar %":70,"Efficiency %":30,"Investment (€)":10000}
}
selected_templates = st.multiselect("Select Templates", list(templates.keys()), default=["Low Reduction"])
all_scenarios = []
for t in selected_templates:
    all_scenarios.append({"Scenario":t, **templates[t]})

# ---------------------- Calculation with Batch Error Handling ----------------------
st.header("5. Calculate Emissions & CBAM Fee")
results = []

for scenario in all_scenarios:
    for idx, row in df_raw.iterrows():
        try:
            # Scope 1: Direct emissions from product + fuel
            scope1 = row["Quantity"] * emission_factors["products"].get(row["Product"],1.0)
            if "Fuel Type" in row and row["Fuel Type"] and row["Fuel Type"] in emission_factors["fuels"]:
                scope1 += row["Fuel Quantity"] * emission_factors["fuels"][row["Fuel Type"]]
            # Scope 2: Electricity emissions
            scope2 = row["Electricity"] * emission_factors["electricity"] * (1 - scenario["Solar %"]/100)
            # Scope 3: Purchased materials + transport
            scope3 = 0
            if "Purchased Materials" in row and row["Purchased Materials"]>0:
                scope3 += row["Purchased Materials"]*emission_factors["products"].get(row["Product"],1.0)
            if "Transport Distance" in row and "Transport Mode" in row and row["Transport Mode"] in emission_factors["transport"]:
                scope3 += row["Quantity"] * row["Transport Distance"] * emission_factors["transport"][row["Transport Mode"]]
            total_emissions = scope1 + scope2 + scope3
            cbam_fee = total_emissions * max(eu_ets_price - local_price,0)
            net_savings = cbam_fee - scenario["Investment (€)"]
            results.append({
                "Scenario":scenario["Scenario"],
                "Product":row["Product"],
                "Scope 1 (tCO₂)":round(scope1,2),
                "Scope 2 (tCO₂)":round(scope2,2),
                "Scope 3 (tCO₂)":round(scope3,2),
                "Total Emissions (tCO₂)":round(total_emissions,2),
                "CBAM Fee (€)":round(cbam_fee,2),
                "Investment (€)":scenario["Investment (€)"],
                "Net Savings (€)":round(net_savings,2)
            })
        except Exception as e:
            st.warning(f"Row {idx} skipped due to error: {e}")

df_results = pd.DataFrame(results)
st.subheader("Detailed Results")
st.dataframe(df_results)

# ---------------------- Scenario Summary ----------------------
summary = df_results.groupby("Scenario")[["Total Emissions (tCO₂)","CBAM Fee (€)","Net Savings (€)"]].sum().reset_index()
st.subheader("Scenario Summary")
st.dataframe(summary)

# ---------------------- Stacked Bar Chart ----------------------
st.subheader("Emissions Breakdown per Scenario")
df_stack = df_results.groupby(["Scenario"])[["Scope 1 (tCO₂)","Scope 2 (tCO₂)","Scope 3 (tCO₂)"]].sum().reset_index()
fig_stack = px.bar(df_stack, x="Scenario", y=["Scope 1 (tCO₂)","Scope 2 (tCO₂)","Scope 3 (tCO₂)"], title="Scope 1,2,3 Emissions per Scenario", labels={"value":"tCO₂","Scenario":"Scenario"})
st.plotly_chart(fig_stack, use_container_width=True)

# ---------------------- Recommendation ----------------------
if not summary.empty:
    best = summary.loc[summary["Net Savings (€)"].idxmax()]
    st.success(f"Recommended Scenario: {best['Scenario']} with Net Savings €{best['Net Savings (€)']}")
else:
    st.warning("No valid scenarios calculated.")

# ---------------------- CSV Download ----------------------
csv = df_results.to_csv(index=False).encode('utf-8')
st.download_button("Download Detailed CSV", data=csv, file_name="cbam_results.csv", mime="text/csv")
