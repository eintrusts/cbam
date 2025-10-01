# ---------------------- CBAM Dashboard without st_aggrid ----------------------
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="CBAM Dashboard - Native Inputs", layout="wide")
st.title("CBAM Dashboard for Indian Manufacturers")
st.markdown("""
Add multiple products manually, calculate emissions, CBAM fees, and scenario-based reductions. No extra packages required.
""")

# ---------------------- Emission Factors ----------------------
emission_factors = {
    "products": {"Steel":1.8, "Cement":0.9, "Aluminium":12.0, "Fertilizer":3.0},
    "fuels": {"Coal":2.5, "Diesel":2.7, "Natural Gas":2.0},
    "electricity":0.7,
    "transport":{"Truck":0.2, "Rail":0.05, "Ship":0.01, "Air":0.6}
}

# ---------------------- Session State ----------------------
if "df_raw" not in st.session_state:
    st.session_state.df_raw = pd.DataFrame(columns=["Product","Quantity","Electricity","Fuel Type","Fuel Quantity",
                                                    "Purchased Materials","Transport Distance","Transport Mode"])

# ---------------------- Add / Edit Products ----------------------
st.header("1. Product Data")

with st.form("product_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        product = st.selectbox("Product", ["Steel","Cement","Aluminium","Fertilizer"])
        qty = st.number_input("Quantity (t)", min_value=0.0, value=10.0)
        elec = st.number_input("Electricity (MWh)", min_value=0.0, value=0.0)
        fuel_type = st.selectbox("Fuel Type", ["None","Coal","Diesel","Natural Gas"])
    with col2:
        fuel_qty = st.number_input("Fuel Quantity", min_value=0.0, value=0.0)
        purchased_materials = st.number_input("Purchased Materials (t)", min_value=0.0, value=0.0)
        transport_distance = st.number_input("Transport Distance (km)", min_value=0.0, value=0.0)
        transport_mode = st.selectbox("Transport Mode", ["Truck","Rail","Ship","Air"])
    
    submitted = st.form_submit_button("Add Product")
    if submitted:
        st.session_state.df_raw = pd.concat([st.session_state.df_raw,
                                             pd.DataFrame([{
                                                 "Product": product,
                                                 "Quantity": qty,
                                                 "Electricity": elec,
                                                 "Fuel Type": fuel_type if fuel_type != "None" else "",
                                                 "Fuel Quantity": fuel_qty,
                                                 "Purchased Materials": purchased_materials,
                                                 "Transport Distance": transport_distance,
                                                 "Transport Mode": transport_mode
                                             }])], ignore_index=True)
        st.success(f"{product} added!")

# Display table
st.subheader("Current Product List")
st.dataframe(st.session_state.df_raw)

# ---------------------- Carbon Prices ----------------------
st.header("2. Carbon Prices")
eu_ets_price = st.number_input("EU ETS Price (€ per tCO₂)", min_value=0.0, value=100.0)
local_price = st.number_input("Local Carbon Price (€ per tCO₂)", min_value=0.0, value=0.0)

# ---------------------- Scenario Templates ----------------------
st.header("3. Scenario Templates")
templates = {
    "Low Reduction":{"Solar %":10,"Efficiency %":5,"Investment (€)":1000},
    "Medium Reduction":{"Solar %":40,"Efficiency %":15,"Investment (€)":5000},
    "High Reduction":{"Solar %":70,"Efficiency %":30,"Investment (€)":10000}
}
selected_templates = st.multiselect("Select Templates", list(templates.keys()), default=["Low Reduction"])
all_scenarios = []
for t in selected_templates:
    all_scenarios.append({"Scenario":t, **templates[t]})

# ---------------------- Calculation ----------------------
st.header("4. Calculate Emissions & CBAM Fee")
df_raw = st.session_state.df_raw
if df_raw.empty:
    st.warning("Add at least one product to calculate.")
else:
    results = []
    for scenario in all_scenarios:
        for idx, row in df_raw.iterrows():
            try:
                # Scope 1
                scope1 = row["Quantity"] * emission_factors["products"].get(row["Product"],1.0)
                if row["Fuel Type"] in emission_factors["fuels"]:
                    scope1 += row["Fuel Quantity"] * emission_factors["fuels"][row["Fuel Type"]]
                # Scope 2
                scope2 = row["Electricity"] * emission_factors["electricity"] * (1 - scenario["Solar %"]/100)
                # Scope 3
                scope3 = row["Purchased Materials"] * emission_factors["products"].get(row["Product"],1.0)
                if row["Transport Mode"] in emission_factors["transport"]:
                    scope3 += row["Quantity"] * row["Transport Distance"] * emission_factors["transport"][row["Transport Mode"]]
                total = scope1 + scope2 + scope3
                cbam = total * max(eu_ets_price - local_price,0)
                net_savings = cbam - scenario["Investment (€)"]
                results.append({
                    "Scenario": scenario["Scenario"],
                    "Product": row["Product"],
                    "Scope 1 (tCO₂)": round(scope1,2),
                    "Scope 2 (tCO₂)": round(scope2,2),
                    "Scope 3 (tCO₂)": round(scope3,2),
                    "Total Emissions (tCO₂)": round(total,2),
                    "CBAM Fee (€)": round(cbam,2),
                    "Investment (€)": scenario["Investment (€)"],
                    "Net Savings (€)": round(net_savings,2)
                })
            except Exception as e:
                st.warning(f"Error processing row {idx}: {e}")
                
    df_results = pd.DataFrame(results)
    st.subheader("Detailed Results")
    st.dataframe(df_results)

    # ---------------------- Scenario Summary ----------------------
    summary = df_results.groupby("Scenario")[["Total Emissions (tCO₂)","CBAM Fee (€)","Net Savings (€)"]].sum().reset_index()
    st.subheader("Scenario Summary")
    st.dataframe(summary)

    # ---------------------- Stacked Bar Chart ----------------------
    st.subheader("Emissions Breakdown per Scenario")
    df_stack = df_results.groupby("Scenario")[["Scope 1 (tCO₂)","Scope 2 (tCO₂)","Scope 3 (tCO₂)"]].sum().reset_index()
    fig_stack = px.bar(df_stack, x="Scenario", y=["Scope 1 (tCO₂)","Scope 2 (tCO₂)","Scope 3 (tCO₂)"],
                       title="Scope 1, 2, 3 Emissions per Scenario", labels={"value":"tCO₂","Scenario":"Scenario"})
    st.plotly_chart(fig_stack, use_container_width=True)

    # ---------------------- Recommendation ----------------------
    best = summary.loc[summary["Net Savings (€)"].idxmax()]
    st.success(f"Recommended Scenario: {best['Scenario']} with Net Savings €{best['Net Savings (€)']}")

    # ---------------------- CSV Download ----------------------
    csv = df_results.to_csv(index=False).encode('utf-8')
    st.download_button("Download Detailed CSV", data=csv, file_name="cbam_results.csv", mime="text/csv")
