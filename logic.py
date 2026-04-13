# logic.py
import pandas as pd
from datetime import datetime


def calculate_party_overdue(df, today_date=None):
    """
    Calculates party-wise outstanding & overdue.
    - Strictly uses 'TodayDate' column from Excel as reference date
    - Uses 'Invoice Date' to calculate how many days old the invoice is
    - 40-day parties: overdue if Days >= 40
    - 60-day parties: overdue if Days >= 60
    """

    # === STRICTLY USE TodayDate COLUMN FROM EXCEL ===
    if 'TodayDate' in df.columns and not df['TodayDate'].dropna().empty:
        today_raw = df['TodayDate'].dropna().mode()[0]
        if isinstance(today_raw, (int, float)):
            # Convert Excel serial date
            today_date = pd.Timestamp("1899-12-30") + pd.Timedelta(today_raw, unit='D')
        else:
            today_date = pd.to_datetime(today_raw, errors='coerce')
    else:
        # Fallback only if TodayDate column is completely missing
        today_date = datetime.now().date()

    today_date = pd.to_datetime(today_date).date()

    # Required columns check
    required = ['Customer Name', 'Invoice Date', 'Order Value', 'Amount Received',
                'Freight Adjustment', 'Credit Note', 'Credit Days', 'Description']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    # Clean numeric columns
    numeric_cols = ['Order Value', 'Amount Received', 'Freight Adjustment', 'Credit Note', 'Credit Days']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df = df[df['Customer Name'].notna()].copy()

    # Skip 'G Total' rows
    df = df[~df['Customer Name'].str.contains('G Total', na=False, case=False)]

    # Convert Invoice Date
    df['Invoice Date'] = pd.to_datetime(df['Invoice Date'], errors='coerce')

    results = {}
    customers = df['Customer Name'].unique()

    for party in customers:
        df_party = df[df['Customer Name'] == party]

        total_received = df_party['Amount Received'].sum()
        total_freight   = df_party['Freight Adjustment'].sum()
        total_credit    = df_party['Credit Note'].sum()
        total_ded = total_received + total_freight + total_credit

        df_inv = df_party[
            df_party['Description'].astype(str).str.contains('Invoice', case=False, na=False)
        ].copy()

        if df_inv.empty:
            results[party] = {
                'credit_days': 40,
                'outstanding': 0.0,
                'overdue': 0.0
            }
            continue

        total_billed = df_inv['Order Value'].sum()
        outstanding = total_billed - total_ded

        # Calculate Days = TodayDate (from Excel) - Invoice Date
        days_list = []
        for inv_date in df_inv['Invoice Date']:
            if pd.isna(inv_date):
                days_list.append(9999)
            else:
                days_list.append((today_date - inv_date.date()).days)

        df_inv['Days'] = days_list

        # Get credit days for grouping
        credit_series = df_inv['Credit Days'].replace(0, pd.NA).dropna()
        credit_days = int(credit_series.max()) if not credit_series.empty else 40

        df_inv = df_inv.sort_values('Invoice Date')

        remaining_ded = total_ded
        unpaid_portions = []

        for idx, row in df_inv.iterrows():
            val = row['Order Value']
            if remaining_ded >= val:
                remaining_ded -= val
            else:
                unpaid = val - remaining_ded
                unpaid_portions.append({
                    'unpaid': unpaid,
                    'days': int(row['Days']),
                    'credit': credit_days
                })
                remaining_ded = 0
                break

        current_pos = df_inv.index.get_loc(idx)
        if current_pos < len(df_inv) - 1:
            remaining = df_inv.iloc[current_pos + 1:]
            for _, row in remaining.iterrows():
                unpaid_portions.append({
                    'unpaid': row['Order Value'],
                    'days': int(row['Days']),
                    'credit': credit_days
                })

        # Apply threshold
        if credit_days == 60:
            overdue = sum(p['unpaid'] for p in unpaid_portions if p['days'] >= 60)
        else:
            overdue = sum(p['unpaid'] for p in unpaid_portions if p['days'] >= 40)

        results[party] = {
            'credit_days': credit_days,
            'outstanding': round(outstanding, 2),
            'overdue': overdue
        }

    results_40 = {p: v for p, v in results.items() if v['credit_days'] == 40}
    results_60 = {p: v for p, v in results.items() if v['credit_days'] == 60}

    return results_40, results_60, 'Invoice Date'
