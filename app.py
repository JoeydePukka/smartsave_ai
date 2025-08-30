import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import uuid
from datetime import datetime

# =========================
# Config & Helpers
# =========================
st.set_page_config(page_title="SmartSave AI", layout="wide")

HISTORY_FILE = "transactions.json"  # This file will store transaction data locally

def center_header(text, level=2):
    st.markdown(
        f"<h{level} style='text-align:center; font-weight:700; margin:0.25rem 0 0.75rem;'>{text}</h{level}>",
        unsafe_allow_html=True
    )

def parse_amount(s: str):
    if s is None or s.strip() == "":
        return None
    for sym in ["¥", "$", "CNY", "RMB", ","]:
        s = s.replace(sym, "")
    try:
        return float(s)
    except:
        return None

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except:
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save {os.path.basename(path)}: {e}")

# =========================
# Load Local Data
# =========================
transactions = load_json(HISTORY_FILE, [])

# =========================
# Session State
# =========================
if "transactions" not in st.session_state:
    st.session_state.transactions = transactions
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

# =========================
# Sidebar Navigation
# =========================
st.sidebar.title("📑 Navigation")
section = st.sidebar.radio(
    "Go to section:",
    ["➕ Add Transaction", "📋 Transactions", "🧾 Expense Breakdown", "💡 Tips"]
)

# =========================
# Add Transaction
# =========================
if section == "➕ Add Transaction":
    center_header("➕ Add Transaction", 2)
    with st.form("transaction_form", clear_on_submit=True):
        col1, col2, col3 = st.columns([1.5, 2.5, 2])
        with col1:
            t_type = st.selectbox("Type", ["Expense", "Income"])
        with col2:
            t_category = st.text_input("Category (e.g. Food, Transport, Salary)")
        with col3:
            t_amount_raw = st.text_input("Amount (e.g. 250.00)")

        submitted = st.form_submit_button("Add")
        if submitted:
            amount = parse_amount(t_amount_raw)
            if amount is None:
                st.error("Invalid amount")
            else:
                record = {
                    "id": datetime.utcnow().isoformat(),
                    "type": t_type,
                    "amount": round(float(amount), 2),
                    "category": t_category.strip() or "Misc",
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                }
                st.session_state.transactions.append(record)
                save_json(HISTORY_FILE, st.session_state.transactions)
                st.success(f"{t_type} ¥{record['amount']:.2f} added under '{record['category']}'")

# =========================
# Transactions Table
# =========================
if section == "📋 Transactions":
    center_header("📋 Transactions", 2)
    if st.session_state.transactions:
        df = pd.DataFrame(st.session_state.transactions)
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

        # Display the table with responsive layout
        st.dataframe(df.sort_values(by="timestamp", ascending=False), use_container_width=True)
    else:
        st.info("No transactions yet.")

# =========================
# Expense Breakdown
# =========================
if section == "🧾 Expense Breakdown":
    center_header("🧾 Expense Breakdown", 2)
    if st.session_state.transactions:
        df = pd.DataFrame(st.session_state.transactions)
        expense_df = df[df["type"]=="Expense"]
        if not expense_df.empty:
            by_cat = expense_df.groupby("category")["amount"].sum()
            fig, ax = plt.subplots()
            ax.pie(by_cat, labels=by_cat.index, autopct="%1.1f%%", startangle=140)
            ax.set_title("Expenses by Category")
            st.pyplot(fig)
        else:
            st.info("No expense records")
    else:
        st.info("No data yet")

# =========================
# Tips
# =========================
if section == "💡 Tips":
    center_header("💡 Tips & Suggestions", 2)
    if st.session_state.transactions:
        df = pd.DataFrame(st.session_state.transactions)
        total_income = df[df["type"]=="Income"]["amount"].sum()
        total_expense = df[df["type"]=="Expense"]["amount"].sum()
        balance = total_income - total_expense
        tips = []
        if balance < 0:
            tips.append("Balance negative — reduce spending or increase income")
        if total_expense > 0:
            top_cat = df[df["type"]=="Expense"].groupby("category")["amount"].sum().sort_values(ascending=False)
            if not top_cat.empty:
                cat, val = top_cat.index[0], top_cat.iloc[0]
                if val/total_expense >= 0.3:
                    tips.append(f"{cat} makes up {val/total_expense:.0%} of expenses — consider cutting down")
        if balance > 0:
            tips.append(f"You could save ~¥{balance/4:.2f} per week")
        for t in tips:
            st.info(t)
    else:
        st.info("No transactions yet.")

# =========================
# Clear History
# =========================
if st.button("Clear History"):
    st.session_state.confirm_clear = True

if st.session_state.get("confirm_clear", False):
    st.warning("Are you sure you want to clear the history?")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Yes, clear history"):
            st.session_state.transactions = []  # Clear session state
            save_json(HISTORY_FILE, st.session_state.transactions)  # Clear the file
            st.session_state.confirm_clear = False  # Reset confirmation
            st.success("History cleared successfully!")
            st.experimental_rerun()  # Force rerun to update UI
    with col2:
        if st.button("Cancel"):
            st.session_state.confirm_clear = False  # Reset confirmation if cancelled
