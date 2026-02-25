import streamlit as st
from streamlit_autorefresh import st_autorefresh
from st_supabase_connection import SupabaseConnection, execute_query
import plotly.express as px
import pandas as pd
import datetime

st.set_page_config(
    page_title="GTNH - Items Tracker",
    layout="wide"
)

st.title("GTNH - Applied Energistics Items Track")

# Refresh every 15 minutes
st_autorefresh(interval=900000, key="refresh_page")

# Supabase view/table
supabase_table = "ae_items_flat"

# Initialize connection
conn = st.connection("supabase", type=SupabaseConnection)

# time filter deprecated
items_resp = execute_query(
    conn.table(supabase_table).select("item"),
    ttl="20m",
)

rows_resp = execute_query(
    conn.table(supabase_table).select("*"),
    ttl="20m",
)

# ---------------------------
# Load distinct items
# ---------------------------
items_resp = execute_query(
    conn.table(supabase_table).select("item").gt("datetime", filter_time.isoformat()),
    ttl="20m",
)

items = pd.DataFrame(items_resp.data or [])

if items.empty or "item" not in items.columns:
    st.warning("No item data found yet.")
    st.stop()

distinct_items = items["item"].dropna().unique()

if len(distinct_items) == 0:
    st.warning("No items found in the selected time window.")
    st.stop()

# Select item
items_filter = st.selectbox("Select the Item", distinct_items)

# ---------------------------
# Load all rows for charts
# ---------------------------
rows_resp = execute_query(
    conn.table(supabase_table).select("*").gt("datetime", filter_time.isoformat()),
    ttl="20m",
)

sort_table = pd.DataFrame(rows_resp.data or [])

if sort_table.empty:
    st.warning("No chart data found yet.")
    st.stop()

# Ensure expected columns exist
required_cols = {"item", "quantity", "datetime"}
if not required_cols.issubset(sort_table.columns):
    st.error(f"Missing required columns: {required_cols - set(sort_table.columns)}")
    st.stop()

# Clean types
sort_table["datetime"] = pd.to_datetime(sort_table["datetime"], errors="coerce")
sort_table["quantity"] = pd.to_numeric(sort_table["quantity"], errors="coerce")

sort_table = sort_table.dropna(subset=["datetime", "item", "quantity"])
sort_table = sort_table.sort_values("datetime")

if sort_table.empty:
    st.warning("Data exists, but all rows were invalid after cleaning.")
    st.stop()

# ---------------------------
# Selected item data
# ---------------------------
item_track = sort_table.loc[sort_table["item"] == items_filter].copy()

if item_track.empty:
    st.warning(f"No rows found for {items_filter}.")
    st.stop()

# ---------------------------
# Layout
# ---------------------------
fig_col1, fig_col2 = st.columns([0.2, 0.8])

with fig_col1:
    st.markdown("### " + items_filter)
    st.markdown("#### Past 24-hour metrics")

    now = pd.Timestamp.utcnow()
    last_24h = item_track[item_track["datetime"] >= now - pd.Timedelta(days=1)].copy()

    if len(last_24h) <= 1:
        kpi_avg = 0
        kpi_change = 0
    else:
        last_24h["real_production"] = last_24h["quantity"].diff().fillna(0)
        total_production = float(last_24h["real_production"].sum())

        total_hours = (
            last_24h["datetime"].max() - last_24h["datetime"].min()
        ).total_seconds() / 3600

        if total_hours <= 0:
            kpi_avg = 0
        else:
            kpi_avg = int(round(total_production / total_hours))

        kpi_change = int(round(total_production))

    st.metric(label="Average Produced per Hour", value="{:,}".format(kpi_avg))
    st.metric(label="Total Amount Produced", value="{:,}".format(kpi_change))

with fig_col2:
    fig1 = px.line(
        item_track,
        x="datetime",
        y="quantity",
        title="Quantity of: " + items_filter
    )
    st.plotly_chart(fig1, use_container_width=True)

# ---------------------------
# All items
# ---------------------------
with st.expander("All items:"):
    for col in distinct_items:
        temp_df = sort_table.loc[sort_table["item"] == col].copy()

        if temp_df.empty:
            continue

        fig = px.line(
            temp_df,
            x="datetime",
            y="quantity",
            title="Quantity of: " + col
        )

        st.plotly_chart(fig, use_container_width=True)
