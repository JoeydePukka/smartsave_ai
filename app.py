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
st.set_page_config(page_title="SmartSave AI", layout="centered")

HISTORY_FILE = "transactions.json"
GOALS_FILE   = "goals.json"

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
    if s is None:
        return None
    s = s.strip()
    if s == "":
        return None
    for sym in ["¥", "$", "CNY", "RMB", ","]:
        s = s.replace(sym, "")
    try:
        return float(s)
    except ValueError:
        return None

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

def load_transactions():
    return load_json(HISTORY_FILE, [])

def save_transactions(transactions):
    save_json(HISTORY_FILE, transactions)

def load_goals():
    return load_json(GOALS_FILE, [])

def save_goals(goals):
    save_json(GOALS_FILE, goals)

def yyyymm(dt: datetime) -> str:
    return dt.strftime("%Y-%m")

def apply_recurring(transactions: list) -> bool:
    """
    Auto-add one instance this month for every recurring series_id that
    doesn't yet have a record in the current month. Returns True if modified.
    """
    if not transactions:
        return False

    now = datetime.utcnow()
    current_month = yyyymm(now)
    tx_by_series = {}

    # Collect latest record per series_id
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
            # Clone with new id/timestamp
            new_t = {
                **{k: v for k, v in latest.items() if k != "id"},
                "id": datetime.utcnow().isoformat(),
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
            }
            transactions.append(new_t)
            updated = True

    return updated


# =========================
# Session state
# =========================
if "transactions" not in st.session_state:
    st.session_state.transactions = load_transactions()
if "goals" not in st.session_state:
    st.session_state.goals = load_goals()
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "nav_choice" not in st.session_state:
    st.session_state.nav_choice = "🏠 Home"

# Apply recurring on load
if apply_recurring(st.session_state.transactions):
    save_transactions(st.session_state.transactions)

# =========================
# Sidebar navigation
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
center_header("Track expenses & income, auto-apply monthly recurring items, and set savings goals. Data is saved locally.",3)

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
        # manual entry (free typing)
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
            save_transactions(st.session_state.transactions)
            st.success(f"{t_type} ¥{record['amount']:.2f} added under '{record['category']}'"
                       + (" (recurring monthly)" if make_recurring else ""))

# Quick controls
colA, colB, colC = st.columns([1, 1, 2])
with colA:
    if st.session_state.transactions:
        df_export = pd.DataFrame(st.session_state.transactions)
        st.download_button(
            "⬇️ Download CSV",
            data=df_export.to_csv(index=False).encode("utf-8"),
            file_name="transactions.csv",
            mime="text/csv",
            help="Export all transactions"
        )
    else:
        st.info("No transactions to export.")
with colB:
    if st.button("🧹 Clear all history"):
        st.session_state.confirm_clear = True
with colC:
    if st.session_state.confirm_clear:
        c1, c2, c3 = st.columns([2, 1, 1])
        c1.warning("⚠️ Permanently delete all saved transactions?")
        if c2.button("Yes, delete everything"):
            st.session_state.transactions = []
            save_transactions(st.session_state.transactions)
            st.session_state.confirm_clear = False
            st.success("All history cleared.")
            st.rerun()
        if c3.button("Cancel"):
            st.session_state.confirm_clear = False

st.markdown("---")

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

        # Rows
        for _, row in df_display.iterrows():
            rid = row["id"]
            c1, c2, c3, c4, c5, c6 = st.columns([2, 1, 2, 1.2, 1, 1])

            c1.write(row["timestamp"])
            c2.write(row["type"])
            c3.write(row["category"])
            c4.write(f"¥{row['amount']:.2f}")
            c5.write("Yes" if row.get("recurring") else "No")

            a1, a2 = c6.columns(2)
            if a1.button("✏️", key=f"edit_{rid}", help="Edit"):
                st.session_state.editing_id = rid
                # scroll to edit block (appears right below table)
                scroll_to("edit_block")
            if a2.button("🗑️", key=f"del_{rid}", help="Delete"):
                st.session_state.transactions = [t for t in st.session_state.transactions if t["id"] != rid]
                save_transactions(st.session_state.transactions)
                st.success("Transaction deleted.")
                st.rerun()

    # Edit form (appears when editing_id is set)
    anchor("edit_block")
    if st.session_state.editing_id:
        edit_id = st.session_state.editing_id
        record = next((t for t in st.session_state.transactions if t["id"] == edit_id), None)
        st.subheader("✏️ Edit Transaction")
        if record:
            with st.form("edit_form"):
                new_type = st.selectbox("Type", ["Expense", "Income"], index=0 if record["type"] == "Expense" else 1)
                new_amount_raw = st.text_input("Amount", str(record["amount"]))
                new_category = st.text_input("Category", record["category"])
                rec_col1, rec_col2 = st.columns([1, 1])
                with rec_col1:
                    new_recurring = st.checkbox("Recurring monthly", value=bool(record.get("recurring")))
                with rec_col2:
                    st.text_input("Series ID (auto)", value=(record.get("series_id") or "—"), disabled=True)

                save_btn = st.form_submit_button("Save Changes")
                cancel_btn = st.form_submit_button("Cancel")

                if save_btn:
                    new_amount = parse_amount(new_amount_raw)
                    if new_amount is None:
                        st.error("Invalid amount.")
                    else:
                        record.update({
                            "type": new_type,
                            "amount": round(float(new_amount), 2),
                            "category": new_category.strip() if new_category.strip() else "Misc",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "recurring": bool(new_recurring),
                            "recurring_interval": "monthly" if new_recurring else None,
                            "series_id": record.get("series_id") or (str(uuid.uuid4()) if new_recurring else None),
                        })
                        save_transactions(st.session_state.transactions)
                        st.session_state.editing_id = None
                        st.success("Transaction updated.")
                        st.rerun()
                elif cancel_btn:
                    st.session_state.editing_id = None
                    st.info("Edit cancelled.")
                    st.rerun()
else:
    st.info("No transactions yet. Add income or expenses above.")

st.markdown("---")

# =========================
# Expense Breakdown
# =========================
anchor("breakdown")
center_header("🧾 Expense Breakdown", 2)

if st.session_state.transactions:
    df_all = pd.DataFrame(st.session_state.transactions)
    df_all["amount"] = pd.to_numeric(df_all["amount"], errors="coerce").fillna(0.0)
    expense_df = df_all[df_all["type"] == "Expense"]
    if not expense_df.empty:
        by_cat = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
        fig, ax = plt.subplots()
        ax.pie(by_cat, labels=by_cat.index, autopct="%1.1f%%", startangle=140)
        ax.set_title("Expenses by Category")
        st.pyplot(fig)
    else:
        st.info("No expense records yet to build a breakdown chart.")
else:
    st.info("No data yet.")

st.markdown("---")

# =========================
# Tips
# =========================
anchor("tips")
center_header("💡 Tips & Suggestions", 2)

tips = []
if st.session_state.transactions:
    df_all = pd.DataFrame(st.session_state.transactions)
    df_all["amount"] = pd.to_numeric(df_all["amount"], errors="coerce").fillna(0.0)
    total_income = df_all[df_all["type"] == "Income"]["amount"].sum()
    total_expense = df_all[df_all["type"] == "Expense"]["amount"].sum()
    balance = total_income - total_expense

    if balance < 0:
        tips.append("Your balance is negative. Reduce non-essential spending or increase income.")

    expense_df = df_all[df_all["type"] == "Expense"]
    if not expense_df.empty:
        top_cat = expense_df.groupby("category")["amount"].sum().sort_values(ascending=False)
        if not top_cat.empty:
            top_name, top_val = top_cat.index[0], top_cat.iloc[0]
            if total_expense > 0 and (top_val / total_expense) >= 0.30:
                tips.append(f"'{top_name}' makes up {top_val/total_expense:.0%} of your expenses — consider cutting it down.")

    if balance > 0:
        tips.append(f"Based on your current balance, you could save about ¥{balance/4:.2f} per week.")

if tips:
    for t in tips:
        st.info(t)
else:
    st.write("No suggestions yet — keep tracking to get tailored tips.")

st.markdown("---")

# =========================
# Savings Goals
# =========================
anchor("goals")
center_header("🎯 Savings Goals", 2)

with st.form("goal_form", clear_on_submit=True):
    goal_name = st.text_input("Goal Name", placeholder="e.g. Vacation")
    goal_target = st.text_input("Target Amount", placeholder="e.g. 10000")
    add_goal = st.form_submit_button("Add Goal")
    if add_goal:
        amt = parse_amount(goal_target)
        if not goal_name.strip():
            st.error("Please enter a goal name.")
        elif amt is None or amt <= 0:
            st.error("Please enter a valid positive target amount.")
        else:
            st.session_state.goals.append({
                "id": datetime.utcnow().isoformat(),
                "name": goal_name.strip(),
                "target": round(float(amt), 2),
                "created": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            })
            save_goals(st.session_state.goals)
            st.success("Goal added!")

if st.session_state.goals:
    # Progress uses current (>=0) balance against target for a rough sense
    try:
        df_all = pd.DataFrame(st.session_state.transactions)
        cur_balance = (
            pd.to_numeric(df_all[df_all["type"] == "Income"]["amount"], errors="coerce").fillna(0).sum()
            - pd.to_numeric(df_all[df_all["type"] == "Expense"]["amount"], errors="coerce").fillna(0).sum()
        )
    except Exception:
        cur_balance = 0.0

    for g in st.session_state.goals:
        p = 0.0
        if g.get("target", 0) > 0:
            p = max(0.0, min(1.0, (cur_balance if cur_balance > 0 else 0.0) / g["target"]))
        st.progress(p)
        cols = st.columns([3, 1, 1])
        cols[0].markdown(f"**{g['name']}** — Target ¥{g['target']:.2f} · Progress: {p*100:.1f}%")
        if cols[1].button("🗑️ Delete", key=f"del_goal_{g['id']}"):
            st.session_state.goals = [x for x in st.session_state.goals if x["id"] != g["id"]]
            save_goals(st.session_state.goals)
            st.success("Goal deleted.")
            st.rerun()
        if cols[2].button("✏️ Rename", key=f"ren_goal_{g['id']}"):
            new_name = st.text_input(f"Rename '{g['name']}'", key=f"rename_input_{g['id']}")
            if st.button("Save name", key=f"save_rename_{g['id']}"):
                g["name"] = new_name.strip() or g["name"]
                save_goals(st.session_state.goals)
                st.success("Goal renamed.")
                st.rerun()

st.caption(f"Transactions are saved locally to `{HISTORY_FILE}`. Goals are saved to `{GOALS_FILE}`.")

