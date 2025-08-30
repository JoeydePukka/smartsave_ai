import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import uuid
from datetime import datetime

# =========================
# Config & tiny helpers
# =========================
st.set_page_config(page_title="Nii's SmartSave AI", layout="wide")  # Ensure full-width layout

# Generate a unique user ID for each session
user_id = str(uuid.uuid4())  # Generate unique ID per user session
HISTORY_FILE = f"transactions_{user_id}.json"  # User-specific transaction file
GOALS_FILE = f"goals_{user_id}.json"  # User-specific goals file

def center_header(text, level=2):
    st.markdown(
        f"<h{level} style='text-align:center; font-weight:700; margin:0.25rem 0 0.75rem;'>{text}</h{level}>",
        unsafe_allow_html=True
    )

def anchor(id_):
    """Place an invisible HTML anchor the JS can scroll to."""
    st.markdown(f"<div id='{id_}' style='position:relative; top:-70px;'></div>", unsafe_allow_html=True)

def scroll_to(id_):
    """Emit a small JS snippet to smoothly scroll to the target anchor."""
    st.markdown(
        f"""
        <script>
        const el = document.getElementById("{id_}");
        if (el) el.scrollIntoView({{behavior: "smooth", block: "start"}}); 
        </script>
        """,
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
    """Load JSON data from file, or return default if not found"""
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except:
        return default

def save_json(path, data):
    """Save JSON data to file"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save {os.path.basename(path)}: {e}")

# =========================
# Load User Data
# =========================
transactions = load_json(HISTORY_FILE, [])
goals = load_json(GOALS_FILE, [])

# =========================
# Session State
# =========================
if "transactions" not in st.session_state:
    st.session_state.transactions = transactions
if "goals" not in st.session_state:
    st.session_state.goals = goals
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = "🏠 Home"

# =========================
# Sidebar Navigation
# =========================
st.sidebar.title("📑 Navigation")
choice = st.sidebar.radio(
    "Jump to section:",
    ["🏠 Home", "➕ Add Transaction", "📋 Transactions", "🧾 Expense Breakdown", "💡 Tips", "🎯 Savings Goals"],
    index=["🏠 Home", "➕ Add Transaction", "📋 Transactions", "🧾 Expense Breakdown", "💡 Tips", "🎯 Savings Goals"].index(st.session_state.nav_choice)
)
st.session_state.nav_choice = choice

# When the choice changes, request a smooth scroll to that anchor
target_ids = {
    "🏠 Home": "home",
    "➕ Add Transaction": "entry",
    "📋 Transactions": "table",
    "🧾 Expense Breakdown": "breakdown",
    "💡 Tips": "tips",
    "🎯 Savings Goals": "goals"
}
scroll_to(target_ids[choice])

# =========================
# Title
# =========================
anchor("home")
center_header("💰Nii's SmartSave AI — Budget & Savings (Single-Page)", 1)
center_header("Track expenses & income, auto-apply monthly recurring items, and set savings goals. Data is saved locally.", 5)

st.markdown("---")

# =========================
# Add Transaction
# =========================
anchor("entry")
center_header("➕ Add Transaction", 2)
with st.form("transaction_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([1.5, 2.5, 2])
    with col1:
        t_type = st.selectbox("Type", ["Expense", "Income"])
    with col2:
        t_category = st.text_input("Category (e.g. Food, Transport, Salary)", value="")
    with col3:
        t_amount_raw = st.text_input("Amount (e.g. 250.00)", placeholder="e.g. 250.00")

    rcol1, rcol2 = st.columns([2, 2])
    with rcol1:
        make_recurring = st.checkbox("Make this a recurring transaction")
    with rcol2:
        recurring_interval = st.selectbox("Repeat every", ["monthly"], disabled=not make_recurring)

    submitted = st.form_submit_button("Add")
    if submitted:
        amount = parse_amount(t_amount_raw)
        if amount is None:
            st.error("Invalid amount. Type numbers like 123.45 (you can include commas or a currency symbol).")
        else:
            record = {
                "id": datetime.utcnow().isoformat(),
                "type": t_type,
                "amount": round(float(amount), 2),
                "category": t_category.strip() if t_category.strip() else "Misc",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "recurring": bool(make_recurring),
                "recurring_interval": "monthly" if make_recurring else None,
                "series_id": str(uuid.uuid4()) if make_recurring else None,
            }
            st.session_state.transactions.append(record)
            save_json(HISTORY_FILE, st.session_state.transactions)
            st.success(f"{t_type} ¥{record['amount']:.2f} added under '{record['category']}'"
                       + (" (recurring monthly)" if make_recurring else ""))

# =========================
# Transactions + Metrics
# =========================
anchor("table")
center_header("📋 Transactions", 2)

if st.session_state.transactions:
    df = pd.DataFrame(st.session_state.transactions)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)

    # Filters
    fcol1, fcol2, fcol3 = st.columns([2, 1, 1])
    with fcol1:
        search_term = st.text_input("🔍 Search by category or type", placeholder="e.g. Food or Expense")
    with fcol2:
        type_filter = st.selectbox("Type filter", ["All", "Expense", "Income"])
    with fcol3:
        show_only_recurring = st.checkbox("Only recurring")

    df_display = df.copy()
    if search_term:
        mask = (
            df_display["category"].str.contains(search_term, case=False, na=False) |
            df_display["type"].str.contains(search_term, case=False, na=False)
        )
        df_display = df_display[mask]
    if type_filter != "All":
        df_display = df_display[df_display["type"] == type_filter]
    if show_only_recurring:
        df_display = df_display[df_display["recurring"] == True]

    df_display = df_display.sort_values(by="timestamp", ascending=False).reset_index(drop=True)

    # Metrics
    total_income = df[df["type"] == "Income"]["amount"].sum()
    total_expense = df[df["type"] == "Expense"]["amount"].sum()
    balance = total_income - total_expense

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Income (¥)", f"{total_income:.2f}")
    m2.metric("Total Expenses (¥)", f"{total_expense:.2f}")
    m3.metric("Balance (¥)", f"{balance:.2f}")

    # Table header
    if df_display.empty:
        st.info("No transactions match the current filters.")
    else:
        h1, h2, h3, h4, h5, h6 = st.columns([2, 1, 2, 1.2, 1, 1])
        h1.write("Timestamp")
        h2.write("Type")
        h3.write("Category")
        h4.write("Amount")
        h5.write("Recurring")
        h6.write("Actions")

        # Render table data rows
        for index, row in df_display.iterrows():
            h1.write(row["timestamp"])
            h2.write(row["type"])
            h3.write(row["category"])
            h4.write(f"¥{row['amount']:.2f}")
            h5.write("Yes" if row["recurring"] else "No")
            h6.write("❌" if not row["recurring"] else "✅")

else:
    st.info("No transactions yet.")

# =========================
# Expense Breakdown
# =========================
anchor("breakdown")
center_header("🧾 Expense Breakdown", 2)

if st.session_state.transactions:
    df = pd.DataFrame(st.session_state.transactions)
    expense_df = df[df["type"] == "Expense"]
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
# Tips & Suggestions
# =========================
anchor("tips")
center_header("💡 Tips & Suggestions", 2)

if st.session_state.transactions:
    df = pd.DataFrame(st.session_state.transactions)
    total_income = df[df["type"] == "Income"]["amount"].sum()
    total_expense = df[df["type"] == "Expense"]["amount"].sum()
    balance = total_income - total_expense
    tips = []
    if balance < 0:
        tips.append("Balance negative — reduce spending or increase income")
    if total_expense > 0:
        top_cat = df[df["type"] == "Expense"].groupby("category")["amount"].sum().sort_values(ascending=False)
        if not top_cat.empty:
            cat, val = top_cat.index[0], top_cat.iloc[0]
            if val / total_expense >= 0.3:
                tips.append(f"{cat} makes up {val/total_expense:.0%} of expenses — consider cutting down")
    if balance > 0:
        tips.append(f"You could save ~¥{balance/4:.2f} per week")
    for t in tips:
        st.info(t)
else:
    st.info("No transactions yet.")
