# app.py
import streamlit as st
import pandas as pd
from datetime import datetime

from logic import calculate_party_overdue

def round_half_away_from_zero(x):
    if x >= 0:
        return round(x + 0.5 - 1e-10)
    else:
        return round(x - 0.5 + 1e-10)

st.set_page_config(page_title="Recovery Overdue Dashboard", layout="wide")

st.title("Party-wise Overdue Analyzer")
st.markdown("Upload Recovery Master Excel file")

uploaded_file = st.file_uploader("Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    with st.spinner("Processing..."):
        try:
            df = pd.read_excel(uploaded_file, sheet_name=0)

            df.columns = df.columns.str.strip().str.replace(r'\s+', ' ', regex=True)

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

            # Apply rounding IN-PLACE to overdue column
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

                def style_cells(row):
                    styles = ['color: white'] * len(row)
                    if row['overdue'] < 0:
                        styles[row.index.get_loc('overdue')] = 'color: #ffcccc'  # light pink
                    return styles

                st.subheader("All Parties (searchable, sorted by name)")
                st.dataframe(
                    debug_df.style.format({
                        'outstanding': '{:,.2f}',
                        'overdue': '{:,.0f}'
                    }).apply(style_cells, axis=1),
                    use_container_width=True
                )

            col1, col2 = st.columns(2)

            with col1:
                st.subheader("40 Days Credit")
                df40 = pd.DataFrame.from_dict(overdue_40, orient='index').sort_index()
                if search:
                    df40 = df40[df40.index.str.contains(search, case=False)]
                st.dataframe(
                    df40.style.format({'outstanding': '{:,.2f}', 'overdue': '{:,.0f}'})
                             .apply(style_cells, axis=1),
                    use_container_width=True
                )
                st.metric("Total Overdue 40d", f"₹ {sum(d['overdue'] for d in overdue_40.values()):,.0f}")

            with col2:
                st.subheader("60 Days Credit")
                df60 = pd.DataFrame.from_dict(overdue_60, orient='index').sort_index()
                if search:
                    df60 = df60[df60.index.str.contains(search, case=False)]
                st.dataframe(
                    df60.style.format({'outstanding': '{:,.2f}', 'overdue': '{:,.0f}'})
                             .apply(style_cells, axis=1),
                    use_container_width=True
                )
                st.metric("Total Overdue 60d", f"₹ {sum(d['overdue'] for d in overdue_60.values()):,.0f}")

        except Exception as e:
            st.error(f"Error: {str(e)}")
            import traceback
            st.code(traceback.format_exc(), language="python")

else:
    st.info("Upload the file")

st.caption("Recovery Tool • White font • Negative overdue in light pink • Rounding in same column")