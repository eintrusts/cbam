# ---------------------- CBAM Executive Dashboard - Fully Crash-Proof ----------------------
import sys
import streamlit as st

# ---------------------- Safe Imports ----------------------
def import_or_alert(module_name, package_name=None):
    try:
        return __import__(module_name)
    except ModuleNotFoundError:
        pkg = package_name if package_name else module_name
        st.error(f"Module '{module_name}' is not installed. Please install it using:\n```\npip install {pkg}\n```")
        st.stop()

pd = import_or_alert("pandas")
px = import_or_alert("plotly.express", "plotly")
requests = import_or_alert("requests")
pdfkit = import_or_alert("pdfkit")

# ---------------------- App Config ----------------------
st.set_page_config(page_title="CBAM Executive Dashboard", layout="wide")
st.title("CBAM Executive Dashboard for Indian Exporters")
st.markdown("""
Estimate CBAM fees, simulate reduction scenarios per product, and generate professional reports with recommended strategies.
""")

# ---------------------- Live EU ETS Price ----------------------
def fetch_eu_ets_price():
    try:
        # Placeholder API: replace with real EU ETS API if available
        url = "https://api.co2signal.com/v1/latest?countryCode=EU"  # placeholder
        headers = {"auth-token":"YOUR_API_KEY"}  # optional
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        price = 100  # fallback if API fails
        return price
    except:
        return 100  # default €/tCO2

st.header("1. EU ETS Carbon Price")
eu_ets_price = st.number_input("EU ETS Carbon Price (€ per tCO₂)", min_value=0.0, value=float(fetch_eu_ets_price()))
local_carbon_price = st.number_input("Local Carbon Price Paid in India (€ per tCO₂)", min_value=0.0, value=0.0)

# ---------------------- Product Inputs ----------------------
st.header("2. Products & Quantities")
product_entries = []

with st.form(key='product_form', clear_on_submit=True):
    product_name = st.selectbox("Product", ["Steel","Cement","Aluminium","Fertilizer","Electricity"])
    quantity = st.number_input("Quantity (tonnes)", min_value=1.0, value=10.0)
    emission_factor_default = {"Steel":1.8,"Cement":0.9,"Aluminium":12.0,"Fertilizer":3.0,"Electricity":0.7}[product_name]
    emission_factor = st.number_input("Emission Factor (tCO₂ per tonne)", value=emission_factor_default)
    electricity_used = 0.0
    if product_name != "Electricity":
        electricity_used = st.number_input("Electricity Used (MWh)", min_value=0.0, value=0.0)
    submit_product = st.form_submit_button("Add Product")
    if submit_product:
        product_entries.append({
            "Product": product_name,
            "Quantity": quantity,
            "Emission Factor": emission_factor,
            "Electricity Used": electricity_used
        })
        st.success(f"{product_name} added to shipment.")

if product_entries:
    df_products = pd.DataFrame(product_entries)
    st.subheader("Products in Shipment")
    st.dataframe(df_products)
else:
    st.warning("No products added yet. Please add at least one product to proceed.")

# ---------------------- Quick Scenario Templates ----------------------
st.header("3. Quick Scenario Templates")
st.markdown("Select predefined strategies to simulate CBAM fees instantly.")
templates = {
    "Low Reduction": {"Solar %": 10, "Efficiency %": 5, "Investment (€)": 1000},
    "Medium Reduction": {"Solar %": 40, "Efficiency %": 15, "Investment (€)": 5000},
    "High Reduction": {"Solar %": 70, "Efficiency %": 30, "Investment (€)": 10000}
}
selected_templates = st.multiselect("Select Templates", options=list(templates.keys()), default=["Low Reduction","Medium Reduction"])

template_scenarios = []
for t in selected_templates:
    template_scenarios.append({
        "Scenario": t,
        "Solar %": templates[t]["Solar %"],
        "Efficiency %": templates[t]["Efficiency %"],
        "Investment Cost (€)": templates[t]["Investment (€)"]
    })

# ---------------------- Custom Scenarios ----------------------
st.header("4. Custom Scenarios (Optional)")
num_custom = st.number_input("Number of Custom Scenarios", min_value=0, max_value=5, value=0)
custom_scenarios = []
for i in range(num_custom):
    st.markdown(f"### Custom Scenario {i+1}")
    solar_pct = st.slider(f"Renewable Electricity (%) - Scenario {i+1}", 0, 100, 0, key=f"solar_custom{i}")
    efficiency_pct = st.slider(f"Efficiency Improvement (%) - Scenario {i+1}", 0, 50, 0, key=f"eff_custom{i}")
    investment_cost = st.number_input(f"Investment Cost (€) - Scenario {i+1}", min_value=0.0, value=0.0, key=f"cost_custom{i}")
    custom_scenarios.append({
        "Scenario": f"Custom {i+1}",
        "Solar %": solar_pct,
        "Efficiency %": efficiency_pct,
        "Investment Cost (€)": investment_cost
    })

# ---------------------- Merge All Scenarios ----------------------
all_scenarios = template_scenarios + custom_scenarios

# ---------------------- Calculations ----------------------
st.header("5. CBAM Calculation & Analysis")
detailed_results = []

if product_entries and all_scenarios:
    for scenario in all_scenarios:
        for p in product_entries:
            scope1 = p["Quantity"] * p["Emission Factor"] * (1 - scenario["Efficiency %"]/100)
            scope2 = p["Electricity Used"] * 0.7 * (1 - scenario["Solar %"]/100)
            total_emissions = scope1 + scope2
            cbam_fee = total_emissions * max(eu_ets_price - local_carbon_price, 0)
            net_savings = cbam_fee - scenario["Investment Cost (€)"]
            detailed_results.append({
                "Scenario": scenario["Scenario"],
                "Product": p["Product"],
                "Quantity": p["Quantity"],
                "Scope 1 (tCO₂)": round(scope1,2),
                "Scope 2 (tCO₂)": round(scope2,2),
                "Total Emissions (tCO₂)": round(total_emissions,2),
                "Estimated CBAM Fee (€)": round(cbam_fee,2),
                "Investment (€)": scenario["Investment Cost (€)"],
                "Net Savings (€)": round(net_savings,2)
            })

df_detailed = pd.DataFrame(detailed_results)

if not df_detailed.empty:
    st.subheader("Per-Product & Scenario Details")
    st.dataframe(df_detailed)
else:
    st.warning("No calculation results. Add products and/or scenarios to see analysis.")

# ---------------------- Summary per scenario ----------------------
required_cols = ["Scenario","Total Emissions (tCO₂)","Estimated CBAM Fee (€)","Net Savings (€)"]
if not df_detailed.empty:
    missing_cols = [c for c in required_cols if c not in df_detailed.columns]
    if missing_cols:
        st.error(f"Missing columns in calculation: {missing_cols}")
        st.stop()
    df_summary = df_detailed.groupby("Scenario")[["Total Emissions (tCO₂)","Estimated CBAM Fee (€)","Net Savings (€)"]].sum().reset_index()
    st.subheader("Scenario Summary")
    st.dataframe(df_summary)
else:
    df_summary = pd.DataFrame()

# ---------------------- Charts ----------------------
if not df_summary.empty:
    st.subheader("Charts")
    fig_emissions = px.bar(df_summary, x="Scenario", y="Total Emissions (tCO₂)", title="Total Emissions per Scenario")
    st.plotly_chart(fig_emissions, use_container_width=True)
    fig_fee = px.bar(df_summary, x="Scenario", y="Estimated CBAM Fee (€)", title="Estimated CBAM Fee per Scenario")
    st.plotly_chart(fig_fee, use_container_width=True)
    fig_savings = px.bar(df_summary, x="Scenario", y="Net Savings (€)", title="Net Savings per Scenario")
    st.plotly_chart(fig_savings, use_container_width=True)

# ---------------------- One-Click Recommendation ----------------------
st.header("6. One-Click Recommendation")
if not df_summary.empty:
    best_scenario = df_summary.loc[df_summary["Net Savings (€)"].idxmax()]
    st.success(f"✅ Recommended Strategy: **{best_scenario['Scenario']}**")
    st.markdown(f"""
    - **Total Emissions:** {best_scenario['Total Emissions (tCO₂)']} tCO₂  
    - **Estimated CBAM Fee:** €{best_scenario['Estimated CBAM Fee (€)']}  
    - **Net Savings after Investment:** €{best_scenario['Net Savings (€)']}  
    """)
    st.markdown("This scenario provides the **maximum cost benefit** considering CBAM fees and reduction investments.")
else:
    st.info("Add at least one product and one scenario to generate a recommendation.")

# ---------------------- CSV Download ----------------------
if not df_detailed.empty:
    st.subheader("Download CSV Report")
    csv = df_detailed.to_csv(index=False).encode('utf-8')
    st.download_button(label="Download Detailed CSV", data=csv, file_name='cbam_detailed.csv', mime='text/csv')

# ---------------------- PDF Download ----------------------
if not df_detailed.empty:
    st.subheader("Download PDF Report")
    import base64
    html_file = "cbam_report.html"
    with open(html_file, "w") as f:
        f.write("<h1>CBAM Report for Indian Exporters</h1>")
        f.write("<h2>Per-Product & Scenario Details</h2>")
        f.write(df_detailed.to_html(index=False))
        f.write("<h2>Scenario Summary</h2>")
        f.write(df_summary.to_html(index=False))
        if not df_summary.empty:
            f.write(f"<h2>Recommended Strategy: {best_scenario['Scenario']}</h2>")
            f.write(f"<p>Total Emissions: {best_scenario['Total Emissions (tCO₂)']} tCO₂</p>")
            f.write(f"<p>Estimated CBAM Fee: €{best_scenario['Estimated CBAM Fee (€)']}</p>")
            f.write(f"<p>Net Savings: €{best_scenario['Net Savings (€)']}</p>")
    pdf_file = "cbam_report.pdf"
    try:
        pdfkit.from_file(html_file, pdf_file)
        with open(pdf_file, "rb") as f:
            pdf_bytes = f.read()
        b64 = base64.b64encode(pdf_bytes).decode()
        st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="cbam_report.pdf">Download PDF Report</a>', unsafe_allow_html=True)
    except:
        st.warning("PDF generation failed. Ensure wkhtmltopdf is installed or use CSV download.")
