import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from urllib.parse import quote

# 1. Setup & Connection
st.set_page_config(page_title="Trip Splitter", layout="centered")
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. Load Data
def load_data():
    friends = conn.read(worksheet="friends", ttl="0") # ttl=0 forces live data
    expenses = conn.read(worksheet="expenses", ttl="0")
    return friends, expenses

friends_df, expenses_df = load_data()

# 3. App Header
st.title("💸 Group Trip Splitter")
st.info("Tip: Add your Name & UPI ID in the sidebar first!")

# 4. Sidebar: Join the Trip
with st.sidebar:
    st.header("Register")
    name = st.text_input("Your Name")
    upi = st.text_input("UPI ID (e.g. name@okaxis)")
    if st.button("Join Trip"):
        new_f = pd.concat([friends_df, pd.DataFrame([{"name": name, "upi_id": upi}])], ignore_index=True)
        conn.update(worksheet="friends", data=new_f)
        st.rerun()

# 5. Main: Add Expense
if not friends_df.empty:
    with st.expander("➕ Add New Expense"):
        with st.form("expense_form"):
            item = st.text_input("What for?")
            amt = st.number_input("Amount", min_value=1.0)
            paid_by = st.selectbox("Who paid?", friends_df["name"])
            split_with = st.multiselect("Who shared this?", friends_df["name"], default=friends_df["name"])
            
            if st.form_submit_button("Save to Group"):
                new_e = pd.concat([expenses_df, pd.DataFrame([{
                    "description": item, "amount": amt, 
                    "payer": paid_by, "involved": ";".join(split_with)
                }])], ignore_index=True)
                conn.update(worksheet="expenses", data=new_e)
                st.rerun()

    # 6. Settlement Logic
    st.subheader("🤝 Settlements")
    balances = {n: 0.0 for n in friends_df["name"]}
    for _, row in expenses_df.iterrows():
        inv = str(row['involved']).split(";")
        share = float(row['amount']) / len(inv)
        balances[row['payer']] += float(row['amount'])
        for p in inv: balances[p] -= share

    # Match Debtors and Creditors
    debtors = sorted([[p, a] for p, a in balances.items() if a < -1], key=lambda x: x[1])
    creditors = sorted([[p, a] for p, a in balances.items() if a > 1], key=lambda x: x[1], reverse=True)

    for d in debtors:
        for c in creditors:
            if c[1] <= 0: continue
            pay_amt = min(abs(d[1]), c[1])
            
            # Display Settlement & Payment Button
            col1, col2 = st.columns([3, 1])
            col1.write(f"**{d[0]}** owes **{c[0]}**: ₹{pay_amt:.2f}")
            
            # Get Creditor UPI ID
            c_upi = friends_df[friends_df['name'] == c[0]]['upi_id'].iloc[0]
            pay_url = f"upi://pay?pa={c_upi}&pn={c[0]}&am={pay_amt:.2f}&cu=INR"
            
            col2.markdown(f'[<button style="background:#00c853;color:white;border:none;border-radius:5px;padding:5px">Pay Now</button>]({pay_url})', unsafe_allow_html=True)
            
            d[1] += pay_amt
            c[1] -= pay_amt
