import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import json
import os
import uuid
import hashlib
from datetime import datetime

# =========================
# Config & helpers
# =========================
st.set_page_config(page_title="SmartSave AI", layout="centered")

USERS_FILE = "users.json"

def center_header(text, level=2):
    st.markdown(
        f"<h{level} style='text-align:center; font-weight:700; margin:0.25rem 0 0.75rem;'>{text}</h{level}>",
        unsafe_allow_html=True
    )

def anchor(id_):
    st.markdown(f"<div id='{id_}' style='position:relative; top:-70px;'></div>", unsafe_allow_html=True)

def scroll_to(id_):
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
    if s is None: return None
    s = s.strip()
    if s == "": return None
    for sym in ["¥", "$", "CNY", "RMB", ","]:
        s = s.replace(sym, "")
    try: return float(s)
    except ValueError: return None

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except Exception:
        return default

def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        st.error(f"Failed to save {os.path.basename(path)}: {e}")

def yyyymm(dt: datetime) -> str:
    return dt.strftime("%Y-%m")

def apply_recurring(transactions: list) -> bool:
    if not transactions: return False
    now = datetime.utcnow()
    current_month = yyyymm(now)
    tx_by_series = {}
    for t in transactions:
        if t.get("recurring") and t.get("series_id"):
            sid = t["series_id"]
            try:
                ts = datetime.strptime(t["timestamp"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
            if sid not in tx_by_series or ts > tx_by_series[sid]["_ts"]:
                tx_by_series[sid] = {"record": t, "_ts": ts}
    updated = False
    for sid, info in tx_by_series.items():
        latest = info["record"]
        latest_month = yyyymm(info["_ts"])
        if latest_month != current_month and latest.get("recurring_interval") == "monthly":
            new_t = {**{k: v for k, v in latest.items() if k != "id"},
                     "id": datetime.utcnow().isoformat(),
                     "timestamp": now.strftime("%Y-%m-%d %H:%M:%S")}
            transactions.append(new_t)
            updated = True
    return updated

# =========================
# User Authentication
# =========================
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def signup(username, password):
    users = load_users()
    if username in users: return False
    users[username] = hash_password(password)
    save_users(users)
    return True

def login(username, password):
    users = load_users()
    return username in users and users[username] == hash_password(password)

# =========================
# Session state
# =========================
if "user" not in st.session_state: st.session_state.user = None
if "transactions" not in st.session_state: st.session_state.transactions = []
if "goals" not in st.session_state: st.session_state.goals = []
if "confirm_clear" not in st.session_state: st.session_state.confirm_clear = False
if "editing_id" not in st.session_state: st.session_state.editing_id = None
if "nav_choice" not in st.session_state: st.session_state.nav_choice = "🏠 Home"

# =========================
# Authentication page
# =========================
if not st.session_state.user:
    st.title("🔐 SmartSave AI Login / Signup")
    auth_choice = st.radio("Choose action:", ["Login", "Signup"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if auth_choice == "Signup" and st.button("Create Account"):
        if signup(username, password):
            st.success("Account created! Please log in.")
        else:
            st.error("Username already exists.")

    if auth_choice == "Login" and st.button("Login"):
        if login(username, password):
            st.session_state.user = username
            st.experimental_rerun()
        else:
            st.error("Invalid username or password")
    st.stop()

# =========================
# Per-user files
# =========================
HISTORY_FILE = f"transactions_{st.session_state.user}.json"
GOALS_FILE   = f"goals_{st.session_state.user}.json"
st.session_state.transactions = load_json(HISTORY_FILE, [])
st.session_state.goals = load_json(GOALS_FILE, [])

# Apply recurring
if apply_recurring(st.session_state.transactions):
    save_json(HISTORY_FILE, st.session_state.transactions)

# =========================
# Logout button
# =========================
if st.sidebar.button("Logout"):
    st.session_state.user = None
    st.experimental_rerun()

# =========================
# Sidebar Navigation
# =========================
sections = ["🏠 Home", "➕ Add Transaction", "📋 Transactions",
            "🧾 Expense Breakdown", "💡 Tips", "🎯 Savings Goals"]
st.sidebar.title("📑 Navigation")
choice = st.sidebar.radio("Jump to section:", sections,
                          index=sections.index(st.session_state.nav_choice))
st.session_state.nav_choice = choice
target_ids = {sec: sec.split()[1] if len(sec.split())>1 else sec for sec in sections}
scroll_to(target_ids[choice])

# =========================
# Page Title
# =========================
anchor("home")
center_header(f"💰 SmartSave AI — {st.session_state.user}'s Budget & Savings", 1)
st.caption("Track expenses & income, auto-apply monthly recurring items, and set savings goals. Data is saved per account.")
st.markdown("---")

# =========================
# Transaction Entry
# =========================
anchor("Add")
center_header("➕ Add Transaction", 2)
with st.form("transaction_form", clear_on_submit=True):
    col1, col2, col3 = st.columns([1.5,2.5,2])
    with col1:
        t_type = st.selectbox("Type", ["Expense", "Income"])
    with col2:
        t_category = st.text_input("Category (e.g. Food, Transport, Salary)")
    with col3:
        t_amount_raw = st.text_input("Amount (e.g. 250.00)", placeholder="e.g. 250.00")

    rcol1, rcol2 = st.columns([2,2])
    with rcol1:
        make_recurring = st.checkbox("Make this a recurring transaction")
    with rcol2:
        recurring_interval = st.selectbox("Repeat every", ["monthly"], disabled=not make_recurring)

    submitted = st.form_submit_button("Add")
    if submitted:
        amount = parse_amount(t_amount_raw)
        if amount is None:
            st.error("Invalid amount.")
        else:
            record = {
                "id": datetime.utcnow().isoformat(),
                "type": t_type,
                "amount": round(float(amount),2),
                "category": t_category.strip() if t_category.strip() else "Misc",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                "recurring": bool(make_recurring),
                "recurring_interval": "monthly" if make_recurring else None,
                "series_id": str(uuid.uuid4()) if make_recurring else None
            }
            st.session_state.transactions.append(record)
            save_json(HISTORY_FILE, st.session_state.transactions)
            st.success(f"{t_type} ¥{record['amount']:.2f} added under '{record['category']}'" +
                       (" (recurring monthly)" if make_recurring else ""))

# ------------------ QUICK CONTROLS ------------------
colA, colB, colC = st.columns([1,1,2])
with colA:
    if st.session_state.transactions:
        df_export = pd.DataFrame(st.session_state.transactions)
        st.download_button("⬇️ Download CSV", df_export.to_csv(index=False).encode("utf-8"),
                           file_name="transactions.csv", mime="text/csv")
    else:
        st.info("No transactions to export.")
with colB:
    if st.button("🧹 Clear all history"):
        st.session_state.confirm_clear = True
with colC:
    if st.session_state.confirm_clear:
        c1,c2,c3 = st.columns([2,1,1])
        c1.warning("⚠️ Permanently delete all saved transactions?")
        if c2.button("Yes, delete everything"):
            st.session_state.transactions=[]
            save_json(HISTORY_FILE, st.session_state.transactions)
            st.session_state.confirm_clear=False
            st.success("All history cleared.")
            st.rerun()
        if c3.button("Cancel"):
            st.session_state.confirm_clear=False

st.markdown("---")
# =========================
# Transactions Table + Metrics
# =========================
anchor("Transactions")
center_header("📋 Transactions",2)
if st.session_state.transactions:
    df = pd.DataFrame(st.session_state.transactions)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    total_income = df[df["type"]=="Income"]["amount"].sum()
    total_expense = df[df["type"]=="Expense"]["amount"].sum()
    balance = total_income - total_expense
    m1,m2,m3 = st.columns(3)
    m1.metric("Total Income (¥)", f"{total_income:.2f}")
    m2.metric("Total Expenses (¥)", f"{total_expense:.2f}")
    m3.metric("Balance (¥)", f"{balance:.2f}")
    st.dataframe(df.sort_values("timestamp",ascending=False))
else:
    st.info("No transactions yet.")

# =========================
# Expense Breakdown
# =========================
anchor("Breakdown")
center_header("🧾 Expense Breakdown",2)
if st.session_state.transactions:
    df_all = pd.DataFrame(st.session_state.transactions)
    df_all["amount"] = pd.to_numeric(df_all["amount"], errors="coerce").fillna(0.0)
    expense_df = df_all[df_all["type"]=="Expense"]
    if not expense_df.empty:
        by_cat = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
        fig,ax=plt.subplots()
        ax.pie(by_cat,labels=by_cat.index, autopct="%1.1f%%", startangle=140)
        ax.set_title("Expenses by Category")
        st.pyplot(fig)
    else:
        st.info("No expense records yet.")
else:
    st.info("No data yet.")

# =========================
# Tips
# =========================
anchor("Tips")
center_header("💡 Tips & Suggestions",2)
tips=[]
if st.session_state.transactions:
    df_all = pd.DataFrame(st.session_state.transactions)
    df_all["amount"] = pd.to_numeric(df_all["amount"], errors="coerce").fillna(0.0)
    total_income = df_all[df_all["type"]=="Income"]["amount"].sum()
    total_expense = df_all[df_all["type"]=="Expense"]["amount"].sum()
    balance = total_income - total_expense
    if balance<0:
        tips.append("Balance is negative. Reduce spending or increase income.")
    expense_df = df_all[df_all["type"]=="Expense"]
    if not expense_df.empty:
        top_cat = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
        if not top_cat.empty:
            top_name, top_val = top_cat.index[0], top_cat.iloc[0]
            if total_expense>0 and (top_val/total_expense)>=0.3:
                tips.append(f"'{top_name}' is {top_val/total_expense:.0%} of expenses — consider reducing.")
    if balance>0:
        tips.append(f"Potential savings per week: ¥{balance/4:.2f}")
if tips:
    for t in tips:
        st.info(t)
else:
    st.write("No tips yet.")

# =========================
# Savings Goals
# =========================
anchor("Goals")
center_header("🎯 Savings Goals",2)
with st.form("goal_form", clear_on_submit=True):
    goal_name = st.text_input("Goal Name", placeholder="e.g. Vacation")
    goal_target = st.text_input("Target Amount", placeholder="e.g. 10000")
    add_goal = st.form_submit_button("Add Goal")
    if add_goal:
        amt = parse_amount(goal_target)
        if not goal_name.strip():
            st.error("Enter a goal name.")
        elif amt is None or amt<=0:
            st.error("Enter a valid positive target amount.")
        else:
            st.session_state.goals.append({
                "id": datetime.utcnow().isoformat(),
                "name": goal_name.strip(),
                "target": round(float(amt),2),
                "created": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_json(GOALS_FILE, st.session_state.goals)
            st.success("Goal added!")

if st.session_state.goals:
    try:
        df_all = pd.DataFrame(st.session_state.transactions)
        cur_balance = df_all[df_all["type"]=="Income"]["amount"].sum() - df_all[df_all["type"]=="Expense"]["amount"].sum()
    except Exception:
        cur_balance = 0.0
    for g in st.session_state.goals:
        p = max(0.0, min(1.0, (cur_balance if cur_balance>0 else 0)/g["target"]))
        st.progress(p)
        cols = st.columns([3,1,1])
        cols[0].markdown(f"**{g['name']}** — Target ¥{g['target']:.2f} · Progress: {p*100:.1f}%")
        if cols[1].button("🗑️ Delete", key=f"del_goal_{g['id']}"):
            st.session_state.goals = [x for x in st.session_state.goals if x["id"]!=g["id"]]
            save_json(GOALS_FILE, st.session_state.goals)
            st.success("Goal deleted.")
            st.rerun()
        if cols[2].button("✏️ Rename", key=f"ren_goal_{g['id']}"):
            new_name = st.text_input(f"Rename '{g['name']}'", key=f"rename_input_{g['id']}")
            if st.button("Save name", key=f"save_rename_{g['id']}"):
                g["name"] = new_name.strip() or g["name"]
                save_json(GOALS_FILE, st.session_state.goals)
                st.success("Goal renamed.")
                st.rerun()

st.caption(f"Transactions are saved to `{HISTORY_FILE}`. Goals saved to `{GOALS_FILE}`.")

