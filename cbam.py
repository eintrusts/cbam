import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------- Page Setup ----------------------
st.set_page_config(page_title="EinTrust CBAM Assistant", layout="wide")
st.title("EinTrust CBAM Assistant")
st.markdown("""
This tool helps manufacturers calculate potential CBAM fees for exporting to the EU.  
Just enter basic production data — no technical knowledge required.  
""")

# ---------------------- Emission Factors ----------------------
emission_factors = {
    "products": {"Steel":1.8, "Cement":0.9, "Aluminium":12.0, "Fertilizer":3.0},
    "fuels": {"Coal":2.5, "Diesel":2.7, "Natural Gas":2.0},
    "electricity":0.7,
    "transport":{"Truck":0.2, "Rail":0.05, "Ship":0.01, "Air":0.6}
}

# ---------------------- CN Codes ----------------------
cn_codes = {
    "Steel": ["7208 10 00","7208 25 00","7208 26 00"],
    "Cement": ["2523 10 00","2523 29 00"],
    "Aluminium": ["7601 10 00","7601 20 00"],
    "Fertilizer": ["3102 10 00","3102 21 00"]
}

cn_emission_factors = {
    "7208 10 00":1.85, "7208 25 00":1.80, "7208 26 00":1.82,
    "2523 10 00":0.92, "2523 29 00":0.88,
    "7601 10 00":12.5, "7601 20 00":11.8,
    "3102 10 00":3.2, "3102 21 00":2.9
}

# ---------------------- Session State ----------------------
if "df_products" not in st.session_state:
    st.session_state.df_products = pd.DataFrame(columns=[
        "Product","CN Code","Quantity","Electricity","Fuel Type","Fuel Quantity",
        "Purchased Materials","Transport Distance","Transport Mode"
    ])

# ---------------------- Step 1: Add Product Data ----------------------
st.header("Step 1: Enter Product Data")
st.info("Select product and CN code, then enter production and fuel info. Use approximate numbers if exact data is unavailable.")

with st.form("product_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        product = st.selectbox("Product", ["Steel","Cement","Aluminium","Fertilizer"])
        cn_code = st.selectbox("CN Code", cn_codes[product])
        qty = st.number_input("Quantity (tons)", min_value=0.0, value=10.0, format="%.2f")
        elec = st.number_input("Electricity used (MWh)", min_value=0.0, value=0.0, format="%.2f")
        fuel_type = st.selectbox("Fuel Type", ["None","Coal","Diesel","Natural Gas"])
    with col2:
        fuel_qty = st.number_input("Fuel Quantity", min_value=0.0, value=0.0, format="%.2f")
        purchased_materials = st.number_input("Purchased Materials (tons)", min_value=0.0, value=0.0, format="%.2f")
        transport_distance = st.number_input("Transport Distance (km)", min_value=0.0, value=0.0, format="%.2f")
        transport_mode = st.selectbox("Transport Mode", ["Truck","Rail","Ship","Air"])
    
    submitted = st.form_submit_button("Add Product")
    if submitted:
        st.session_state.df_products = pd.concat([st.session_state.df_products,
            pd.DataFrame([{
                "Product": product,
                "CN Code": cn_code,
                "Quantity": qty,
                "Electricity": elec,
                "Fuel Type": fuel_type if fuel_type != "None" else "",
                "Fuel Quantity": fuel_qty,
                "Purchased Materials": purchased_materials,
                "Transport Distance": transport_distance,
                "Transport Mode": transport_mode
            }])
        ], ignore_index=True)
        st.success(f"{product} with CN code {cn_code} added!")

st.subheader("Current Product List")
st.dataframe(st.session_state.df_products)

# ---------------------- Step 2: Carbon Prices ----------------------
st.header("Step 2: Enter Carbon Prices")
eu_ets_price = st.number_input("EU ETS Price (€ per tCO₂)", min_value=0.0, value=100.0, format="%.2f")
local_price = st.number_input("Local Carbon Price (€ per tCO₂, optional)", min_value=0.0, value=0.0, format="%.2f")

# ---------------------- Step 3: Reduction Strategies ----------------------
st.header("Step 3: Explore Reduction Strategies")
st.subheader("Adjust sliders to see how renewable energy or efficiency improvements reduce CBAM fees.")
solar_pct = st.slider("% Electricity from Renewable (Solar/Wind)", min_value=0, max_value=100, value=20)
efficiency_pct = st.slider("% Process Efficiency Improvement", min_value=0, max_value=50, value=10)
investment = st.number_input("Investment Required (€)", min_value=0.0, value=5000.0, format="%.2f")

# ---------------------- Step 4: Calculate Emissions & CBAM Fees ----------------------
st.header("Step 4: Results")

df_raw = st.session_state.df_products
if df_raw.empty:
    st.warning("Add at least one product to calculate.")
else:
    results = []
    for idx, row in df_raw.iterrows():
        try:
            factor = cn_emission_factors.get(row["CN Code"], emission_factors["products"].get(row["Product"],1.0))
            
            # Scope 1
            scope1 = row["Quantity"] * factor
            if row["Fuel Type"] in emission_factors["fuels"]:
                scope1 += row["Fuel Quantity"] * emission_factors["fuels"][row["Fuel Type"]]
            scope1 *= (1 - efficiency_pct/100)

            # Scope 2
            scope2 = row["Electricity"] * emission_factors["electricity"] * (1 - solar_pct/100)

            # Scope 3
            scope3 = row["Purchased Materials"] * factor
            if row["Transport Mode"] in emission_factors["transport"]:
                scope3 += row["Quantity"] * row["Transport Distance"] * emission_factors["transport"][row["Transport Mode"]]
            scope3 *= (1 - efficiency_pct/100)

            total_emissions = scope1 + scope2 + scope3
            cbam_fee = total_emissions * max(eu_ets_price - local_price,0)

            results.append({
                "Product": row["Product"],
                "CN Code": row["CN Code"],
                "Scope 1 (Direct)": round(scope1,2),
                "Scope 2 (Electricity)": round(scope2,2),
                "Scope 3 (Other)": round(scope3,2),
                "Total Emissions (tCO₂)": round(total_emissions,2),
                "CBAM Fee (€)": round(cbam_fee,2)
            })
        except Exception as e:
            st.warning(f"Error processing row {idx}: {e}")

    df_results = pd.DataFrame(results)
    st.subheader("Emissions & CBAM Fee per Product")
    st.dataframe(df_results)

    # Summary
    summary = df_results[["Total Emissions (tCO₂)","CBAM Fee (€)"]].sum().to_frame().T
    summary["Investment (€)"] = investment
    summary["Net Savings (€)"] = summary["CBAM Fee (€)"] - investment
    st.subheader("Strategy Summary")
    st.dataframe(summary)

    st.success(f"Recommended Strategy: Implementing this strategy could save €{round(summary['Net Savings (€)'].values[0],2)}")

    # Emissions Breakdown Chart
    st.subheader("Emissions Breakdown")
    df_stack = df_results[["Product","Scope 1 (Direct)","Scope 2 (Electricity)","Scope 3 (Other)"]].set_index("Product")
    fig = px.bar(df_stack, x=df_stack.index, y=["Scope 1 (Direct)","Scope 2 (Electricity)","Scope 3 (Other)"],
                 title="Scope Emissions per Product", labels={"value":"tCO₂","Product":"Product"})
    st.plotly_chart(fig, use_container_width=True)

    # CSV Download
    csv = df_results.to_csv(index=False).encode('utf-8')
    st.download_button("Download Detailed CSV", data=csv, file_name="cbam_results.csv", mime="text/csv")
