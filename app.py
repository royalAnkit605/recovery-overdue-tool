# app.py
import streamlit as st
import pandas as pd
from datetime import datetime
import plotly.express as px

from logic import calculate_party_overdue

def round_half_away_from_zero(x):
    """Round 0.5 and above away from zero, below towards zero"""
    if x >= 0:
        return round(x + 0.5 - 1e-10)
    else:
        return round(x - 0.5 + 1e-10)

st.set_page_config(page_title="Recovery Overdue Dashboard", layout="wide")

st.title("Party-wise Overdue Analyzer")
st.markdown("Upload your **Recovery Master** Excel file to view overdue amounts and insights")

uploaded_file = st.file_uploader(
    "Choose Excel file",
    type=["xlsx", "xls"],
    help="Should contain sheet with invoice data"
)

if uploaded_file is not None:
    with st.spinner("Reading file and calculating..."):
        try:
            df = pd.read_excel(uploaded_file, sheet_name=0)

            df.columns = df.columns.astype(str).str.strip()
            df.columns = df.columns.str.replace(r'\s+', ' ', regex=True)

            rename_map = {}
            for col in df.columns:
                lower = col.lower().replace(" ", "")
                if "customer" in lower and "name" in lower:
                    rename_map[col] = "Customer Name"
                elif "invoice" in lower and "date" in lower:
                    rename_map[col] = "Invoice Date"
                elif "today" in lower:
                    rename_map[col] = "TodayDate"
                elif "order" in lower and "value" in lower:
                    rename_map[col] = "Order Value"
                elif "amount" in lower and "received" in lower:
                    rename_map[col] = "Amount Received"
                elif "credit" in lower and "note" in lower:
                    rename_map[col] = "Credit Note"
                elif "freight" in lower:
                    rename_map[col] = "Freight Adjustment"
                elif "description" in lower:
                    rename_map[col] = "Description"
                elif "credit" in lower and "days" in lower:
                    rename_map[col] = "Credit Days"

            df = df.rename(columns=rename_map)

            today_str = None
            if "TodayDate" in df.columns:
                today_vals = df["TodayDate"].dropna()
                if not today_vals.empty:
                    today_raw = today_vals.mode()[0]
                    if isinstance(today_raw, (int, float)):
                        today = pd.Timestamp("1899-12-30") + pd.Timedelta(today_raw, unit='D')
                        today_str = today.strftime("%Y-%m-%d")

            if not today_str:
                today_str = datetime.now().strftime("%Y-%m-%d")

            overdue_40, overdue_60, date_col_used = calculate_party_overdue(df, today_date=today_str)

            # Apply custom rounding IN-PLACE to overdue column
            for d in [overdue_40, overdue_60]:
                for party in d:
                    d[party]['overdue'] = round_half_away_from_zero(d[party]['overdue'])

            # Search bar
            search = st.text_input("Search party name", "")

            all_parties = {**overdue_40, **overdue_60}
            if all_parties:
                debug_df = pd.DataFrame.from_dict(all_parties, orient='index')
                debug_df = debug_df[['credit_days', 'outstanding', 'overdue']].sort_index()

                debug_df['section'] = debug_df['credit_days'].apply(
                    lambda x: '40 days' if x == 40 else '60 days' if x == 60 else 'Other'
                )

                if search:
                    debug_df = debug_df[debug_df.index.str.contains(search, case=False)]

                # Theme-aware styling: negative in red, positive in default (black/white auto)
                def style_cells(row):
                    styles = [''] * len(row)  # let Streamlit handle default color
                    if row['overdue'] < 0:
                        styles[row.index.get_loc('overdue')] = 'color: #ff4d4d; font-weight: bold'  # bright red + bold for negative
                    return styles

                st.subheader("All Parties (searchable, sorted by name)")
                st.dataframe(
                    debug_df.style.format({
                        'outstanding': '{:,.2f}',
                        'overdue': '{:,.0f}'
                    }).apply(style_cells, axis=1),
                    use_container_width=True
                )

            # Summary for charts
            party_summary = pd.DataFrame.from_dict(all_parties, orient='index')
            party_summary = party_summary[['outstanding', 'overdue']].reset_index().rename(columns={'index': 'Customer Name'})

            payment_summary = df.groupby('Customer Name').agg({
                'Order Value': 'sum',
                'Amount Received': 'sum'
            }).reset_index().rename(columns={
                'Order Value': 'Total Ordered',
                'Amount Received': 'Total Payments'
            })

            party_summary = party_summary.merge(payment_summary, on='Customer Name', how='left').fillna(0)

            # ==================
            # GRAPHS & CHARTS
            # ==================

            st.markdown("---")
            st.subheader("Key Insights & Charts")

            # Chart 1: Top 10 Parties by Total Payments
            st.subheader("Top 10 Parties by Total Payments Made")
            top_payments = party_summary.sort_values('Total Payments', ascending=False).head(10)
            fig1 = px.bar(
                top_payments,
                x='Customer Name',
                y='Total Payments',
                title="Highest Payments Received from Parties",
                labels={'Total Payments': 'Total Payments (₹)', 'Customer Name': 'Party'},
                color='Total Payments',
                color_continuous_scale='Blues'
            )
            fig1.update_layout(xaxis_tickangle=-45, height=500)
            st.plotly_chart(fig1, use_container_width=True)

            # Chart 2: Top 10 Parties by Total Order Value
            st.subheader("Top 10 Parties by Total Order Value")
            top_orders = party_summary.sort_values('Total Ordered', ascending=False).head(10)
            fig2 = px.bar(
                top_orders,
                x='Customer Name',
                y='Total Ordered',
                title="Highest Order Value Parties",
                labels={'Total Ordered': 'Total Ordered (₹)', 'Customer Name': 'Party'},
                color='Total Ordered',
                color_continuous_scale='Greens'
            )
            fig2.update_layout(xaxis_tickangle=-45, height=500)
            st.plotly_chart(fig2, use_container_width=True)

            # Chart 3: Top 10 Parties by Overdue Amount
            st.subheader("Top 10 Parties by Overdue Amount")
            top_overdue = party_summary[party_summary['overdue'] > 0].sort_values('overdue', ascending=False).head(10)
            fig3 = px.bar(
                top_overdue,
                x='Customer Name',
                y='overdue',
                title="Highest Overdue Parties",
                labels={'overdue': 'Overdue Amount (₹)', 'Customer Name': 'Party'},
                color='overdue',
                color_continuous_scale='Reds'
            )
            fig3.update_layout(xaxis_tickangle=-45, height=500)
            st.plotly_chart(fig3, use_container_width=True)

            # Chart 4: Pie Chart - Payment Distribution (Top 10)
            st.subheader("Payment Distribution - Top 10 Parties")
            fig4 = px.pie(
                top_payments,
                values='Total Payments',
                names='Customer Name',
                title="Share of Total Payments - Top 10 Parties",
                hole=0.4
            )
            st.plotly_chart(fig4, use_container_width=True)

            # Existing 40/60 days tables
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("40 Days Credit Term")
                df40 = pd.DataFrame.from_dict(overdue_40, orient='index').sort_index()
                if search:
                    df40 = df40[df40.index.str.contains(search, case=False)]
                st.dataframe(
                    df40.style.format({'outstanding': '{:,.2f}', 'overdue': '{:,.0f}'})
                             .apply(style_cells, axis=1),
                    use_container_width=True
                )
                st.metric("Total Overdue (40 days)", f"₹ {sum(d['overdue'] for d in overdue_40.values()):,.0f}")

            with col2:
                st.subheader("60 Days Credit Term")
                df60 = pd.DataFrame.from_dict(overdue_60, orient='index').sort_index()
                if search:
                    df60 = df60[df60.index.str.contains(search, case=False)]
                st.dataframe(
                    df60.style.format({'outstanding': '{:,.2f}', 'overdue': '{:,.0f}'})
                             .apply(style_cells, axis=1),
                    use_container_width=True
                )
                st.metric("Total Overdue (60 days)", f"₹ {sum(d['overdue'] for d in overdue_60.values()):,.0f}")

            grand = sum(d['overdue'] for d in overdue_40.values()) + sum(d['overdue'] for d in overdue_60.values())
            st.markdown("---")
            st.metric("Grand Total Overdue", f"₹ {grand:,.0f}", delta_color="inverse")

        except Exception as e:
            st.error(f"Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc(), language="python")

else:
    st.info("Upload your Recovery Master Excel file to start.")

st.markdown("---")
st.caption("Recovery Overdue Tool • Theme-aware colors • Negative overdue in red • Rounding in same column • Graphs included")
