import pandas as pd
from datetime import datetime


def calculate_party_overdue(df, today_date=None):
    """
    Calculates party-wise outstanding & overdue using FIFO allocation.
    - For 40-day credit parties: overdue if Days >= 40
    - For 60-day credit parties: overdue if Days >= 60
    - Uses MAX Credit Days per party for grouping
    - Allows negative overdue (excess deductions on overdue invoices)
    - Skips summary rows like 'G Total'
    """
    if today_date is None:
        today_date = datetime.now().date()
    else:
        today_date = pd.to_datetime(today_date).date()

    # Required columns check
    required = ['Customer Name', 'Invoice Date', 'Order Value', 'Amount Received',
                'Freight Adjustment', 'Credit Note', 'Credit Days', 'Description']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    # Clean numerics
    numeric_cols = ['Order Value', 'Amount Received', 'Freight Adjustment', 'Credit Note', 'Credit Days']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df = df[df['Customer Name'].notna()].copy()

    # Skip summary rows like 'G Total'
    df = df[~df['Customer Name'].str.contains('G Total', na=False, case=False)]

    invoice_date_col = 'Invoice Date'
    df[invoice_date_col] = pd.to_datetime(df[invoice_date_col], errors='coerce')

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

        df_inv['Days'] = df_inv[invoice_date_col].apply(
            lambda d: (today_date - d.date()).days if pd.notna(d) else 9999
        )

        credit_series = df_inv['Credit Days'].replace(0, pd.NA).dropna()
        credit_days = int(credit_series.max()) if not credit_series.empty else 40

        df_inv = df_inv.sort_values(invoice_date_col)

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
                    'days': row['Days'],
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
                    'days': row['Days'],
                    'credit': credit_days
                })

        # Apply different overdue threshold based on party's credit_days
        if credit_days == 60:
            overdue = sum(p['unpaid'] for p in unpaid_portions if p['days'] >= 60)
        else:
            overdue = sum(p['unpaid'] for p in unpaid_portions if p['days'] >= 40)

        results[party] = {
            'credit_days': credit_days,
            'outstanding': round(outstanding, 2),
            'overdue': overdue  # can be negative
        }

    results_40 = {p: v for p, v in results.items() if v['credit_days'] == 40}
    results_60 = {p: v for p, v in results.items() if v['credit_days'] == 60}

    return results_40, results_60, invoice_date_col
