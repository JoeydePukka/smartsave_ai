import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import uuid
from datetime import datetime
import streamlit_authenticator as stauth

# =========================
# Config & Helpers
# =========================
st.set_page_config(page_title="SmartSave AI", layout="centered")

USERS_FILE   = "users.json"

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
# User Data
# =========================
users = load_json(USERS_FILE, [])

# =========================
# Authentication
# =========================
def get_authenticator():
    usernames = [u["username"] for u in users]
    names = [u["name"] for u in users]
    passwords = [u["password"] for u in users]
    return stauth.Authenticate(
        names=names,
        usernames=usernames,
        passwords=passwords,
        cookie_name="smart_save_cookie",
        key="smart_save_key",
        cookie_expiry_days=30
    )

# Login or sign-up selection
option = st.radio("Select Option", ["Login", "Sign Up"], horizontal=True)

# Sign Up section
if option == "Sign Up":
    st.subheader("📝 Create Account")
    with st.form("user_signup"):
        name_input = st.text_input("Full Name")
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submit_signup = st.form_submit_button("Sign Up")
        if submit_signup:
            if any(u["username"] == username_input for u in users):
                st.error("Username already exists")
            elif not name_input or not username_input or not password_input:
                st.error("All fields required")
            else:
                hashed = stauth.Hasher([password_input]).generate()[0]
                users.append({"name": name_input, "username": username_input, "password": hashed})
                save_json(USERS_FILE, users)
                st.success("Account created! Now log in.")
                st.stop()

# Login section
authenticator = get_authenticator()
name, auth_status, username = authenticator.login("Login", "main")

if auth_status is None:
    st.warning("Enter your credentials")
    st.stop()
elif not auth_status:
    st.error("Username/password incorrect")
    st.stop()
else:
    st.success(f"Welcome {name}!")
    authenticator.logout("Logout", "sidebar")

# =========================
# Load User-specific Data
# =========================
HISTORY_FILE = f"transactions_{username}.json"
GOALS_FILE   = f"goals_{username}.json"

transactions = load_json(HISTORY_FILE, [])
goals = load_json(GOALS_FILE, [])

# =========================
# Session State
# =========================
if "transactions" not in st.session_state:
    st.session_state.transactions = transactions
if "goals" not in st.session_state:
    st.session_state.goals = goals
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False

# =========================
# Sidebar Navigation
# =========================
st.sidebar.title("📑 Navigation")
section = st.sidebar.radio(
    "Go to section:",
    ["➕ Add Transaction", "📋 Transactions", "🧾 Expense Breakdown", "💡 Tips", "🎯 Savings Goals"]
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

        rcol1, rcol2 = st.columns([2, 2])
        with rcol1:
            make_recurring = st.checkbox("Make this a recurring transaction")
        with rcol2:
            recurring_interval = st.selectbox("Repeat every", ["monthly"], disabled=not make_recurring)

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
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                    "recurring": make_recurring,
                    "recurring_interval": "monthly" if make_recurring else None,
                    "series_id": str(uuid.uuid4()) if make_recurring else None
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
        st.dataframe(df.sort_values(by="timestamp", ascending=False))
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
# Savings Goals
# =========================
if section == "🎯 Savings Goals":
    center_header("🎯 Savings Goals", 2)
    with st.form("goal_form", clear_on_submit=True):
        goal_name = st.text_input("Goal Name")
        goal_target = st.text_input("Target Amount")
        add_goal = st.form_submit_button("Add Goal")
        if add_goal:
            amt = parse_amount(goal_target)
            if not goal_name.strip():
                st.error("Enter goal name")
            elif amt is None or amt <= 0:
                st.error("Enter valid target")
            else:
                st.session_state.goals.append({
                    "id": datetime.utcnow().isoformat(),
                    "name": goal_name.strip(),
                    "target": round(float(amt), 2),
                    "created": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                })
                save_json(GOALS_FILE, st.session_state.goals)
                st.success("Goal added!")
