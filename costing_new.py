import os
import streamlit as st
import sqlite3
from datetime import date, datetime

# ------------- SIMPLE PASSWORD PROTECTION -------------
# Set your password here OR via an environment variable
APP_PASSWORD = os.getenv("FABRIC_APP_PASSWORD", "2504052243")  # change this

def check_password():
    """Returns True if the user entered the correct password."""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if st.session_state["authenticated"]:
        return True

    st.subheader("🔒 Login")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if password == APP_PASSWORD:
            st.session_state["authenticated"] = True
            st.experimental_rerun()
        else:
            st.error("Wrong password.")

    return False

# ---------------------------
# Database setup
# ---------------------------

DB_PATH = "fabric_costing.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # Yarn prices table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS yarn_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        yarn_type TEXT NOT NULL,  -- 'warp', 'weft', 'both'
        count REAL,
        denier REAL,
        price_per_kg REAL NOT NULL,
        valid_from TEXT NOT NULL  -- ISO date string
    );
    """)

    # Qualities / costings table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS qualities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        quality_name TEXT NOT NULL,

        -- warp inputs
        ends_mode TEXT NOT NULL,           -- 'direct' or 'calc'
        ends REAL,
        reed REAL,
        rs REAL,
        borders REAL,
        warp_denier REAL NOT NULL,
        warp_yarn_name TEXT,
        warp_yarn_price REAL NOT NULL,

        -- weft inputs
        picks REAL NOT NULL,
        weft_rs REAL NOT NULL,
        weft_denier_mode TEXT NOT NULL,    -- 'denier' or 'count'
        weft_denier REAL NOT NULL,
        weft_count REAL,
        weft_yarn_name TEXT,
        weft_yarn_price REAL NOT NULL,

        -- charges & markups
        weaving_rate_per_pick REAL NOT NULL,
        grey_markup_percent REAL NOT NULL,
        rfd_charge_per_m REAL NOT NULL,
        rfd_shortage_percent REAL NOT NULL,   -- used as Rs/m now
        rfd_markup_percent REAL NOT NULL,

        -- outputs (per 100 m)
        warp_weight_100 REAL NOT NULL,
        weft_weight_100 REAL NOT NULL,
        fabric_weight_100 REAL NOT NULL,
        warp_cost_100 REAL NOT NULL,
        weft_cost_100 REAL NOT NULL,
        weaving_charge_100 REAL NOT NULL,
        interest_on_yarn_100 REAL NOT NULL,
        final_grey_cost_100 REAL NOT NULL,
        grey_sale_100 REAL NOT NULL,
        rfd_cost_100 REAL NOT NULL,
        rfd_sale_100 REAL NOT NULL
    );
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------------------
# Helper functions
# ---------------------------

def get_latest_yarn_price(name, yarn_type=None):
    """
    Returns (price_per_kg, denier, count) for the most recent record of this yarn.
    Optionally filter by yarn_type.
    """
    conn = get_conn()
    cur = conn.cursor()
    if yarn_type:
        cur.execute("""
            SELECT price_per_kg, denier, count
            FROM yarn_prices
            WHERE name = ? AND (yarn_type = ? OR yarn_type = 'both')
            ORDER BY date(valid_from) DESC, id DESC
            LIMIT 1
        """, (name, yarn_type))
    else:
        cur.execute("""
            SELECT price_per_kg, denier, count
            FROM yarn_prices
            WHERE name = ?
            ORDER BY date(valid_from) DESC, id DESC
            LIMIT 1
        """, (name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0], row[1], row[2]
    return None, None, None

def list_yarn_names(yarn_type=None):
    conn = get_conn()
    cur = conn.cursor()
    if yarn_type:
        cur.execute("""
            SELECT DISTINCT name FROM yarn_prices
            WHERE yarn_type = ? OR yarn_type = 'both'
            ORDER BY name
        """, (yarn_type,))
    else:
        cur.execute("""
            SELECT DISTINCT name FROM yarn_prices
            ORDER BY name
        """)
    names = [r[0] for r in cur.fetchall()]
    conn.close()
    return names

def save_yarn_price(name, yarn_type, count, denier, price_per_kg, valid_from):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO yarn_prices (name, yarn_type, count, denier, price_per_kg, valid_from)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, yarn_type, count, denier, price_per_kg, valid_from))
    conn.commit()
    conn.close()

def list_all_qualities():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, quality_name, created_at
        FROM qualities
        ORDER BY quality_name COLLATE NOCASE
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_quality_by_id(q_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(qualities)")
    cols = [c[1] for c in cur.fetchall()]
    cur.execute("SELECT * FROM qualities WHERE id = ?", (q_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        return dict(zip(cols, row))
    return None

def save_quality(data):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO qualities (
            created_at, quality_name,
            ends_mode, ends, reed, rs, borders, warp_denier,
            warp_yarn_name, warp_yarn_price,
            picks, weft_rs, weft_denier_mode, weft_denier, weft_count,
            weft_yarn_name, weft_yarn_price,
            weaving_rate_per_pick, grey_markup_percent,
            rfd_charge_per_m, rfd_shortage_percent, rfd_markup_percent,
            warp_weight_100, weft_weight_100, fabric_weight_100,
            warp_cost_100, weft_cost_100, weaving_charge_100,
            interest_on_yarn_100, final_grey_cost_100,
            grey_sale_100, rfd_cost_100, rfd_sale_100
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["created_at"], data["quality_name"],
        data["ends_mode"], data["ends"], data["reed"], data["rs"], data["borders"], data["warp_denier"],
        data["warp_yarn_name"], data["warp_yarn_price"],
        data["picks"], data["weft_rs"], data["weft_denier_mode"], data["weft_denier"], data["weft_count"],
        data["weft_yarn_name"], data["weft_yarn_price"],
        data["weaving_rate_per_pick"], data["grey_markup_percent"],
        data["rfd_charge_per_m"], data["rfd_shortage_percent"], data["rfd_markup_percent"],
        data["warp_weight_100"], data["weft_weight_100"], data["fabric_weight_100"],
        data["warp_cost_100"], data["weft_cost_100"], data["weaving_charge_100"],
        data["interest_on_yarn_100"], data["final_grey_cost_100"],
        data["grey_sale_100"], data["rfd_cost_100"], data["rfd_sale_100"]
    ))

    conn.commit()
    conn.close()

def update_quality(q_id, data):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE qualities SET
            created_at = ?,
            quality_name = ?,
            ends_mode = ?, ends = ?, reed = ?, rs = ?, borders = ?, warp_denier = ?,
            warp_yarn_name = ?, warp_yarn_price = ?,
            picks = ?, weft_rs = ?, weft_denier_mode = ?, weft_denier = ?, weft_count = ?,
            weft_yarn_name = ?, weft_yarn_price = ?,
            weaving_rate_per_pick = ?, grey_markup_percent = ?,
            rfd_charge_per_m = ?, rfd_shortage_percent = ?, rfd_markup_percent = ?,
            warp_weight_100 = ?, weft_weight_100 = ?, fabric_weight_100 = ?,
            warp_cost_100 = ?, weft_cost_100 = ?, weaving_charge_100 = ?,
            interest_on_yarn_100 = ?, final_grey_cost_100 = ?,
            grey_sale_100 = ?, rfd_cost_100 = ?, rfd_sale_100 = ?
        WHERE id = ?
    """, (
        data["created_at"], data["quality_name"],
        data["ends_mode"], data["ends"], data["reed"], data["rs"], data["borders"], data["warp_denier"],
        data["warp_yarn_name"], data["warp_yarn_price"],
        data["picks"], data["weft_rs"], data["weft_denier_mode"], data["weft_denier"], data["weft_count"],
        data["weft_yarn_name"], data["weft_yarn_price"],
        data["weaving_rate_per_pick"], data["grey_markup_percent"],
        data["rfd_charge_per_m"], data["rfd_shortage_percent"], data["rfd_markup_percent"],
        data["warp_weight_100"], data["weft_weight_100"], data["fabric_weight_100"],
        data["warp_cost_100"], data["weft_cost_100"], data["weaving_charge_100"],
        data["interest_on_yarn_100"], data["final_grey_cost_100"],
        data["grey_sale_100"], data["rfd_cost_100"], data["rfd_sale_100"],
        q_id
    ))

    conn.commit()
    conn.close()

def calculate_costing(
    ends, warp_denier, picks, weft_denier, rs,
    warp_yarn_price, weft_yarn_price,
    weaving_rate_per_pick, grey_markup_percent,
    rfd_charge_per_m, rfd_shortage_amount_per_m, rfd_markup_percent
):
    # Base weights (NO shortage)
    warp_weight_100 = (ends * warp_denier) / 90000.0
    weft_weight_100 = (picks * weft_denier * rs) / 90000.0

    # With shortage (for costing)
    warp_weight_100_short = warp_weight_100 * 1.09
    weft_weight_100_short = weft_weight_100 * 1.03

    warp_cost_100 = warp_weight_100_short * warp_yarn_price
    weft_cost_100 = weft_weight_100_short * weft_yarn_price

    fabric_weight_100 = warp_weight_100 + weft_weight_100  # technical, no shortage

    # Weaving (per meter, then per 100 m)
    weaving_per_m = weaving_rate_per_pick * picks
    weaving_charge_100 = weaving_per_m * 100.0

    # Interest on yarn
    interest_on_yarn_100 = (warp_cost_100 + weft_cost_100) * 0.04

    # Grey cost
    final_grey_cost_100 = warp_cost_100 + weft_cost_100 + weaving_charge_100 + interest_on_yarn_100
    grey_cost_per_m = final_grey_cost_100 / 100.0

    # Grey sale with markup as margin on selling price
    if grey_markup_percent == 0:
        grey_sale_per_m = grey_cost_per_m
    else:
        grey_sale_per_m = grey_cost_per_m / (1 - grey_markup_percent / 100.0)
    grey_sale_100 = grey_sale_per_m * 100.0

    # RFD cost: grey + RFD charge + RFD shortage (all in Rs/m)
    rfd_cost_per_m = grey_cost_per_m + rfd_charge_per_m + rfd_shortage_amount_per_m

    # RFD sale with markup as margin on selling price
    if rfd_markup_percent == 0:
        rfd_sale_per_m = rfd_cost_per_m
    else:
        rfd_sale_per_m = rfd_cost_per_m / (1 - rfd_markup_percent / 100.0)
    rfd_cost_100 = rfd_cost_per_m * 100.0
    rfd_sale_100 = rfd_sale_per_m * 100.0

    return {
        "warp_weight_100": warp_weight_100,
        "weft_weight_100": weft_weight_100,
        "fabric_weight_100": fabric_weight_100,
        "warp_cost_100": warp_cost_100,
        "weft_cost_100": weft_cost_100,
        "weaving_charge_100": weaving_charge_100,
        "interest_on_yarn_100": interest_on_yarn_100,
        "final_grey_cost_100": final_grey_cost_100,
        "grey_cost_per_m": grey_cost_per_m,
        "grey_sale_per_m": grey_sale_per_m,
        "grey_sale_100": grey_sale_100,
        "rfd_cost_per_m": rfd_cost_per_m,
        "rfd_sale_per_m": rfd_sale_per_m,
        "rfd_cost_100": rfd_cost_100,
        "rfd_sale_100": rfd_sale_100,
    }

# ---------------------------
# Streamlit UI
# ---------------------------

st.set_page_config(page_title="Fabric Costing App", layout="wide")

st.title("🧵 Fabric Costing App")

page = st.sidebar.radio(
    "Go to",
    ["➕ New Costing", "🔁 What-if Costing", "🧶 Yarn Prices", "🔍 Search Qualities", "📄 Pricing Sheet"]
)

# ---------------------------
# Page: Yarn Prices
# ---------------------------
if page == "🧶 Yarn Prices":
    st.header("🧶 Manage Yarn Prices")

    # Add / update yarn
    with st.form("add_yarn"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Yarn name", placeholder="e.g. 120D Poly Warp")
            yarn_type = st.selectbox("Yarn type", ["warp", "weft", "both"])
            price_per_kg = st.number_input("Price per kg (₹)", min_value=0.0, step=0.1)
        with col2:
            count = st.number_input("Count (optional)", min_value=0.0, step=0.1, value=0.0)
            denier = st.number_input("Denier (optional)", min_value=0.0, step=0.1, value=0.0)
            valid_from = st.date_input("Valid from", value=date.today())

        submitted = st.form_submit_button("Save yarn price")

        if submitted:
            if not name or price_per_kg <= 0:
                st.error("Please enter a yarn name and a valid price.")
            else:
                save_yarn_price(
                    name=name,
                    yarn_type=yarn_type,
                    count=count if count > 0 else None,
                    denier=denier if denier > 0 else None,
                    price_per_kg=price_per_kg,
                    valid_from=valid_from.isoformat()
                )
                st.success("Yarn price saved as latest for this yarn.")

    st.subheader("Existing yarn prices (latest first)")
    conn = get_conn()
    df = None
    try:
        import pandas as pd
        df = pd.read_sql_query("""
            SELECT id, name, yarn_type, count, denier, price_per_kg, valid_from
            FROM yarn_prices
            ORDER BY date(valid_from) DESC, id DESC
        """, conn)
    finally:
        conn.close()

    if df is not None and not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No yarn prices saved yet.")

    # Quick edit + rename
    st.markdown("### ✏️ Quick Edit / Rename Yarn")
    yarn_names_all = list_yarn_names()
    if yarn_names_all:
        selected_yarn = st.selectbox("Select yarn to edit", yarn_names_all)
        if selected_yarn:
            latest_price, latest_denier, latest_count = get_latest_yarn_price(selected_yarn)
            ec0, ec1, ec2, ec3, ec4 = st.columns([2,2,2,2,2])
            with ec0:
                new_name = st.text_input(
                    "Yarn name (can rename)",
                    value=selected_yarn,
                    key="edit_yarn_name"
                )
            with ec1:
                new_price = st.number_input(
                    "New price per kg (₹)",
                    min_value=0.0,
                    step=0.1,
                    value=latest_price if latest_price else 0.0,
                    key="edit_price"
                )
            with ec2:
                new_denier = st.number_input(
                    "Denier (optional)",
                    min_value=0.0,
                    step=0.1,
                    value=latest_denier if latest_denier else 0.0,
                    key="edit_denier"
                )
            with ec3:
                new_count = st.number_input(
                    "Count (optional)",
                    min_value=0.0,
                    step=0.1,
                    value=latest_count if latest_count else 0.0,
                    key="edit_count"
                )
            with ec4:
                new_valid_from = st.date_input("Valid from", value=date.today(), key="edit_valid_from")

            if st.button("Save updated yarn price"):
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT yarn_type FROM yarn_prices WHERE name = ? LIMIT 1", (selected_yarn,))
                row = cur.fetchone()
                conn.close()
                yarn_type = row[0] if row else "both"
                save_yarn_price(
                    name=new_name,
                    yarn_type=yarn_type,
                    count=new_count if new_count > 0 else None,
                    denier=new_denier if new_denier > 0 else None,
                    price_per_kg=new_price,
                    valid_from=new_valid_from.isoformat()
                )
                st.success("Updated yarn price saved as a new latest record.")
    else:
        st.info("Add some yarns above to enable editing.")

# ---------------------------
# Page: New Costing
# ---------------------------
elif page == "➕ New Costing":
    st.header("➕ Create New Costing")

    quality_name = st.text_input("Quality name", placeholder="e.g. Santoon 9kg, 80D x 150D 120x80 58\"")

    st.markdown("### Warp")
    warp_col1, warp_col2, warp_col3 = st.columns(3)

    # Warp yarn selection first to prefill denier & price
    with warp_col3:
        warp_yarn_names = list_yarn_names("warp")
        warp_yarn_name = st.selectbox("Warp yarn (from stored list)", ["(manual price)"] + warp_yarn_names)
        warp_yarn_price_default = 0.0
        warp_denier_from_yarn = None
        if warp_yarn_name != "(manual price)":
            price, dnr, cnt = get_latest_yarn_price(warp_yarn_name, "warp")
            if price:
                warp_yarn_price_default = price
            if dnr:
                warp_denier_from_yarn = dnr
        warp_yarn_price = st.number_input(
            "Warp yarn price per kg (₹)",
            min_value=0.0,
            step=0.1,
            value=warp_yarn_price_default
        )

    with warp_col1:
        ends_mode_label = st.radio("Ends input mode", ["Enter ends directly", "Calculate from reed, RS, borders"])
        ends_mode = "direct" if ends_mode_label == "Enter ends directly" else "calc"
        warp_denier_default = warp_denier_from_yarn if warp_denier_from_yarn else 0.0
        warp_denier = st.number_input("Warp denier", min_value=0.0, step=0.1, value=warp_denier_default)

    with warp_col2:
        ends = None
        reed = None
        rs = st.number_input("RS (for both warp & weft)", min_value=0.0, step=0.1)
        borders = None
        if ends_mode == "direct":
            ends = st.number_input("Ends", min_value=0.0, step=1.0)
            reed_info = st.number_input("Reed (info only, not used in calc)", min_value=0.0, step=0.1, value=0.0)
            reed = reed_info
        else:
            reed = st.number_input("Reed", min_value=0.0, step=0.1)
            borders = st.number_input("Borders (number of extra ends)", min_value=0.0, step=1.0)

    st.markdown("### Weft")
    weft_col1, weft_col2, weft_col3 = st.columns(3)

    with weft_col1:
        picks = st.number_input("Picks", min_value=0.0, step=1.0)
        weft_denier_mode_label = st.radio("Weft specification", ["Denier", "Count (Ne)"])
        weft_denier_mode = "denier" if weft_denier_mode_label == "Denier" else "count"

    with weft_col3:
        weft_yarn_names = list_yarn_names("weft")
        weft_yarn_name = st.selectbox("Weft yarn (from stored list)", ["(manual price)"] + weft_yarn_names)
        weft_yarn_price_default = 0.0
        weft_denier_from_yarn = None
        weft_count_from_yarn = None
        if weft_yarn_name != "(manual price)":
            price, dnr, cnt = get_latest_yarn_price(weft_yarn_name, "weft")
            if price:
                weft_yarn_price_default = price
            if dnr:
                weft_denier_from_yarn = dnr
            if cnt:
                weft_count_from_yarn = cnt
        weft_yarn_price = st.number_input(
            "Weft yarn price per kg (₹)",
            min_value=0.0,
            step=0.1,
            value=weft_yarn_price_default
        )

    with weft_col2:
        weft_denier = None
        weft_count = None
        if weft_denier_mode == "denier":
            default_d = weft_denier_from_yarn if weft_denier_from_yarn else 0.0
            weft_denier = st.number_input("Weft denier", min_value=0.0, step=0.1, value=default_d)
        else:
            default_c = weft_count_from_yarn if weft_count_from_yarn else 0.0
            weft_count = st.number_input("Weft count (Ne)", min_value=0.0, step=0.1, value=default_c)

    st.markdown("### Charges & Markups")
    ch1, ch2, ch3 = st.columns(3)
    with ch1:
        weaving_rate_per_pick = st.number_input(
            "Weaving charge per pick (₹/pick/m)", min_value=0.0, step=0.01, value=0.16
        )
        grey_markup_percent = st.number_input("Grey markup % (margin on sale)", min_value=0.0, step=0.5, value=0.0)
    with ch2:
        rfd_charge_per_m = st.number_input("RFD charge (₹ per m)", min_value=0.0, step=0.1, value=0.0)
        rfd_shortage_per_m = st.number_input("RFD shortage (₹ per m)", min_value=0.0, step=0.1, value=0.0)
    with ch3:
        rfd_markup_percent = st.number_input("RFD markup % (margin on sale)", min_value=0.0, step=0.5, value=0.0)

    if st.button("Calculate & Save"):
        # Basic validation
        if not quality_name:
            st.error("Please enter a quality name.")
        elif warp_denier <= 0 or warp_yarn_price <= 0 or weft_yarn_price <= 0:
            st.error("Please enter valid yarn deniers/prices.")
        elif rs is None or rs <= 0:
            st.error("Please enter a valid RS.")
        elif picks <= 0:
            st.error("Please enter valid picks.")
        elif grey_markup_percent >= 100 or rfd_markup_percent >= 100:
            st.error("Markup % must be less than 100 (it's margin on sale).")
        else:
            # Ends computation
            if ends_mode == "direct":
                if ends is None or ends <= 0:
                    st.error("Please enter valid ends.")
                    st.stop()
            else:
                if reed is None or reed <= 0:
                    st.error("Please enter a valid reed.")
                    st.stop()
                if borders is None:
                    borders = 0.0
                ends = reed * rs + borders

            # Weft denier
            if weft_denier_mode == "denier":
                if weft_denier is None or weft_denier <= 0:
                    st.error("Please enter a valid weft denier.")
                    st.stop()
            else:
                if weft_count is None or weft_count <= 0:
                    st.error("Please enter a valid weft count.")
                    st.stop()
                weft_denier = 5315.0 / weft_count

            cost = calculate_costing(
                ends=ends,
                warp_denier=warp_denier,
                picks=picks,
                weft_denier=weft_denier,
                rs=rs,
                warp_yarn_price=warp_yarn_price,
                weft_yarn_price=weft_yarn_price,
                weaving_rate_per_pick=weaving_rate_per_pick,
                grey_markup_percent=grey_markup_percent,
                rfd_charge_per_m=rfd_charge_per_m,
                rfd_shortage_amount_per_m=rfd_shortage_per_m,
                rfd_markup_percent=rfd_markup_percent
            )

            data = {
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "quality_name": quality_name,
                "ends_mode": ends_mode,
                "ends": ends,
                "reed": reed,
                "rs": rs,
                "borders": borders,
                "warp_denier": warp_denier,
                "warp_yarn_name": None if warp_yarn_name == "(manual price)" else warp_yarn_name,
                "warp_yarn_price": warp_yarn_price,
                "picks": picks,
                "weft_rs": rs,
                "weft_denier_mode": weft_denier_mode,
                "weft_denier": weft_denier,
                "weft_count": weft_count,
                "weft_yarn_name": None if weft_yarn_name == "(manual price)" else weft_yarn_name,
                "weft_yarn_price": weft_yarn_price,
                "weaving_rate_per_pick": weaving_rate_per_pick,
                "grey_markup_percent": grey_markup_percent,
                "rfd_charge_per_m": rfd_charge_per_m,
                "rfd_shortage_percent": rfd_shortage_per_m,
                "rfd_markup_percent": rfd_markup_percent,
                "warp_weight_100": cost["warp_weight_100"],
                "weft_weight_100": cost["weft_weight_100"],
                "fabric_weight_100": cost["fabric_weight_100"],
                "warp_cost_100": cost["warp_cost_100"],
                "weft_cost_100": cost["weft_cost_100"],
                "weaving_charge_100": cost["weaving_charge_100"],
                "interest_on_yarn_100": cost["interest_on_yarn_100"],
                "final_grey_cost_100": cost["final_grey_cost_100"],
                "grey_sale_100": cost["grey_sale_100"],
                "rfd_cost_100": cost["rfd_cost_100"],
                "rfd_sale_100": cost["rfd_sale_100"],
            }

            save_quality(data)

            st.success("Costing calculated and saved.")

            st.markdown("### Results (per meter)")
            grey_cost_per_m = cost["grey_cost_per_m"]
            grey_sale_per_m = cost["grey_sale_per_m"]
            rfd_cost_per_m = cost["rfd_cost_per_m"]
            rfd_sale_per_m = cost["rfd_sale_per_m"]

            c1, c2 = st.columns(2)
            with c1:
                st.metric("Grey cost / m (₹)", f"{grey_cost_per_m:.2f}")
                st.metric("Grey sale / m (₹)", f"{grey_sale_per_m:.2f}")
                st.metric("RFD cost / m (₹)", f"{rfd_cost_per_m:.2f}")
                st.metric("RFD sale / m (₹)", f"{rfd_sale_per_m:.2f}")
            with c2:
                st.markdown("#### Reference (per 100 m)")
                st.write(f"Fabric weight / 100 m (no shortage): **{cost['fabric_weight_100']:.3f} kg**")
                st.write(f"Warp weight / 100 m (no shortage): {cost['warp_weight_100']:.3f} kg")
                st.write(f"Weft weight / 100 m (no shortage): {cost['weft_weight_100']:.3f} kg")
                st.write(f"Warp cost / 100 m: {cost['warp_cost_100']:.2f} ₹")
                st.write(f"Weft cost / 100 m: {cost['weft_cost_100']:.2f} ₹")
                st.write(f"Weaving charge / 100 m: {cost['weaving_charge_100']:.2f} ₹")
                st.write(f"Interest on yarn / 100 m: {cost['interest_on_yarn_100']:.2f} ₹")
                st.write(f"Final grey cost / 100 m: {cost['final_grey_cost_100']:.2f} ₹")
                st.write(f"Grey sale / 100 m: {cost['grey_sale_100']:.2f} ₹")
                st.write(f"RFD cost / 100 m: {cost['rfd_cost_100']:.2f} ₹")
                st.write(f"RFD sale / 100 m: {cost['rfd_sale_100']:.2f} ₹")

# ---------------------------
# Page: What-if Costing
# ---------------------------
elif page == "🔁 What-if Costing":
    st.header("🔁 What-if Costing (no save, just testing)")

    qualities = list_all_qualities()
    if not qualities:
        st.info("No qualities saved yet.")
    else:
        label_to_id = {f"{q[1]} (ID {q[0]})": q[0] for q in qualities}
        labels = ["-- Select quality --"] + list(label_to_id.keys())
        selected_label = st.selectbox("Select a base quality", labels)

        if selected_label != "-- Select quality --":
            q = get_quality_by_id(label_to_id[selected_label])

            st.markdown("### Tweak parameters")

            with st.form("what_if_form"):
                eq1, eq2, eq3 = st.columns(3)
                with eq1:
                    wf_quality_name = st.text_input("Name (for reference only)", value=q["quality_name"])
                    wf_ends_mode_label = st.radio(
                        "Ends mode",
                        ["Enter ends directly", "Calculate from reed, RS, borders"],
                        index=0 if q["ends_mode"] == "direct" else 1
                    )
                    wf_ends_mode = "direct" if wf_ends_mode_label == "Enter ends directly" else "calc"
                with eq2:
                    wf_rs = st.number_input(
                        "RS", min_value=0.0, step=0.1, value=float(q["rs"])
                    )
                    wf_reed = st.number_input(
                        "Reed (info or for calc)", min_value=0.0, step=0.1,
                        value=float(q["reed"] if q["reed"] else 0.0)
                    )
                    wf_borders = st.number_input(
                        "Borders", min_value=0.0, step=1.0,
                        value=float(q["borders"] if q["borders"] else 0.0)
                    )
                with eq3:
                    wf_ends = st.number_input(
                        "Ends", min_value=0.0, step=1.0,
                        value=float(q["ends"])
                    )

                ew1, ew2, ew3 = st.columns(3)
                with ew1:
                    wf_warp_denier = st.number_input(
                        "Warp denier", min_value=0.0, step=0.1,
                        value=float(q["warp_denier"])
                    )
                    wf_picks = st.number_input(
                        "Picks", min_value=0.0, step=1.0,
                        value=float(q["picks"])
                    )
                with ew2:
                    wf_weft_denier_mode_label = st.radio(
                        "Weft specification",
                        ["Denier", "Count (Ne)"],
                        index=0 if q["weft_denier_mode"] == "denier" else 1
                    )
                    wf_weft_denier_mode = "denier" if wf_weft_denier_mode_label == "Denier" else "count"
                    if wf_weft_denier_mode == "denier":
                        wf_weft_denier = st.number_input(
                            "Weft denier", min_value=0.0, step=0.1,
                            value=float(q["weft_denier"])
                        )
                        wf_weft_count = q["weft_count"]
                    else:
                        wf_weft_count = st.number_input(
                            "Weft count (Ne)", min_value=0.0, step=0.1,
                            value=float(q["weft_count"] if q["weft_count"] else 0.0)
                        )
                        wf_weft_denier = q["weft_denier"]
                with ew3:
                    wf_warp_yarn_price = st.number_input(
                        "Warp yarn price per kg (₹)", min_value=0.0, step=0.1,
                        value=float(q["warp_yarn_price"])
                    )
                    wf_weft_yarn_price = st.number_input(
                        "Weft yarn price per kg (₹)", min_value=0.0, step=0.1,
                        value=float(q["weft_yarn_price"])
                    )

                ec1, ec2, ec3 = st.columns(3)
                with ec1:
                    wf_weaving_rate_per_pick = st.number_input(
                        "Weaving charge per pick (₹/pick/m)", min_value=0.0, step=0.01,
                        value=float(q["weaving_rate_per_pick"])
                    )
                    wf_grey_markup_percent = st.number_input(
                        "Grey markup % (margin on sale)", min_value=0.0, step=0.5,
                        value=float(q["grey_markup_percent"])
                    )
                with ec2:
                    wf_rfd_charge_per_m = st.number_input(
                        "RFD charge (₹ per m)", min_value=0.0, step=0.1,
                        value=float(q["rfd_charge_per_m"])
                    )
                    wf_rfd_shortage_per_m = st.number_input(
                        "RFD shortage (₹ per m)", min_value=0.0, step=0.1,
                        value=float(q["rfd_shortage_percent"])
                    )
                with ec3:
                    wf_rfd_markup_percent = st.number_input(
                        "RFD markup % (margin on sale)", min_value=0.0, step=0.5,
                        value=float(q["rfd_markup_percent"])
                    )

                what_if_btn = st.form_submit_button("Recalculate (do not save)")

            if what_if_btn:
                if wf_grey_markup_percent >= 100 or wf_rfd_markup_percent >= 100:
                    st.error("Markup % must be less than 100 (margin on sale).")
                else:
                    # Ends recompute if needed
                    if wf_ends_mode == "calc":
                        wf_ends = wf_reed * wf_rs + wf_borders

                    # Weft denier
                    if wf_weft_denier_mode == "denier":
                        wd = float(wf_weft_denier)
                        wc = wf_weft_count
                    else:
                        wc = float(wf_weft_count)
                        wd = 5315.0 / wc if wc > 0 else 0.0

                    cost = calculate_costing(
                        ends=float(wf_ends),
                        warp_denier=float(wf_warp_denier),
                        picks=float(wf_picks),
                        weft_denier=float(wd),
                        rs=float(wf_rs),
                        warp_yarn_price=float(wf_warp_yarn_price),
                        weft_yarn_price=float(wf_weft_yarn_price),
                        weaving_rate_per_pick=float(wf_weaving_rate_per_pick),
                        grey_markup_percent=float(wf_grey_markup_percent),
                        rfd_charge_per_m=float(wf_rfd_charge_per_m),
                        rfd_shortage_amount_per_m=float(wf_rfd_shortage_per_m),
                        rfd_markup_percent=float(wf_rfd_markup_percent)
                    )

                    st.markdown("### What-if Results (per meter)")
                    grey_cost_per_m = cost["grey_cost_per_m"]
                    grey_sale_per_m = cost["grey_sale_per_m"]
                    rfd_cost_per_m = cost["rfd_cost_per_m"]
                    rfd_sale_per_m = cost["rfd_sale_per_m"]

                    c1, c2 = st.columns(2)
                    with c1:
                        st.metric("Grey cost / m (₹)", f"{grey_cost_per_m:.2f}")
                        st.metric("Grey sale / m (₹)", f"{grey_sale_per_m:.2f}")
                        st.metric("RFD cost / m (₹)", f"{rfd_cost_per_m:.2f}")
                        st.metric("RFD sale / m (₹)", f"{rfd_sale_per_m:.2f}")
                    with c2:
                        warp_weight_100 = cost["warp_weight_100"]
                        weft_weight_100 = cost["weft_weight_100"]
                        fabric_weight_100 = cost["fabric_weight_100"]
                        warp_weight_100_short = warp_weight_100 * 1.09
                        fabric_weight_cost_style = warp_weight_100_short + weft_weight_100

                        st.write(f"Fabric weight / 100 m (no shortage): **{fabric_weight_100:.3f} kg**")
                        st.write(f"Fabric weight / 100 m (warp with shortage, weft no shortage): "
                                 f"**{fabric_weight_cost_style:.3f} kg**")
                        st.write(f"Warp weight / 100 m (no shortage): {warp_weight_100:.3f} kg")
                        st.write(f"Weft weight / 100 m (no shortage): {weft_weight_100:.3f} kg")

                    st.markdown("### Recipe (what-if)")
                    st.write(f"Reed: {wf_reed}")
                    st.write(f"Picks: {wf_picks}")
                    st.write(f"Ends: {wf_ends} (mode: {wf_ends_mode})")
                    st.write(f"RS: {wf_rs}")
                    st.write(f"Warp denier: {wf_warp_denier}")
                    if wf_weft_denier_mode == "denier":
                        st.write(f"Weft denier: {wd}")
                    else:
                        st.write(f"Weft count (Ne): {wc}")
                        st.write(f"(Calculated weft denier: {wd})")

# ---------------------------
# Page: Search Qualities
# ---------------------------
elif page == "🔍 Search Qualities":
    st.header("🔍 Search Saved Qualities")

    qualities = list_all_qualities()
    if not qualities:
        st.info("No qualities saved yet.")
    else:
        # Just one dropdown with type-to-search
        label_to_id = {f"{q[1]} (ID {q[0]})": q[0] for q in qualities}
        labels = ["-- Select quality --"] + list(label_to_id.keys())

        selected_label = st.selectbox(
            "Select quality (type to search)",
            labels
        )

        if selected_label != "-- Select quality --":
            selected_id = label_to_id[selected_label]
            q = get_quality_by_id(selected_id)

            if q:
                st.markdown(f"### {q['quality_name']}")
                st.caption(f"Created at: {q['created_at']}")

                view_mode = st.radio(
                    "View mode",
                    ["Summary", "Recipe", "Details", "Edit"],
                    horizontal=True
                )

                # 👉 keep everything from your existing Summary/Recipe/Details/Edit
                # logic exactly as it is below this point
            if selected_label != "-- Select quality --":
                selected_id = label_to_id[selected_label]
                q = get_quality_by_id(selected_id)

                if q:
                    st.markdown(f"### {q['quality_name']}")
                    st.caption(f"Created at: {q['created_at']}")

                    view_mode = st.radio(
                        "View mode",
                        ["Summary", "Recipe", "Details", "Edit"],
                        horizontal=True
                    )

                    warp_weight_100 = q["warp_weight_100"]
                    weft_weight_100 = q["weft_weight_100"]
                    fabric_weight_100 = q["fabric_weight_100"]
                    warp_weight_100_short = warp_weight_100 * 1.09
                    fabric_weight_costing_style = warp_weight_100_short + weft_weight_100

                    grey_cost_per_m = q["final_grey_cost_100"] / 100.0
                    grey_sale_per_m = q["grey_sale_100"] / 100.0
                    rfd_cost_per_m = q["rfd_cost_100"] / 100.0
                    rfd_sale_per_m = q["rfd_sale_100"] / 100.0

                    if view_mode == "Summary":
                        st.subheader("Summary")
                        sc1, sc2 = st.columns(2)
                        with sc1:
                            st.metric("Grey cost / m (₹)", f"{grey_cost_per_m:.2f}")
                            st.metric("Grey sale / m (₹)", f"{grey_sale_per_m:.2f}")
                            st.metric("RFD cost / m (₹)", f"{rfd_cost_per_m:.2f}")
                            st.metric("RFD sale / m (₹)", f"{rfd_sale_per_m:.2f}")
                        with sc2:
                            st.write(f"Fabric weight / 100 m (no shortage): **{fabric_weight_100:.3f} kg**")
                            st.write(f"Fabric weight / 100 m (warp with shortage, weft no shortage): "
                                     f"**{fabric_weight_costing_style:.3f} kg**")
                            st.write(f"Warp weight / 100 m (no shortage): {warp_weight_100:.3f} kg")
                            st.write(f"Weft weight / 100 m (no shortage): {weft_weight_100:.3f} kg")

                    elif view_mode == "Recipe":
                        st.subheader("Recipe")
                        st.markdown("**Basic construction**")
                        st.write(f"Reed: {q['reed']}")
                        st.write(f"Picks: {q['picks']}")
                        st.write(f"Ends: {q['ends']} (mode: {q['ends_mode']})")
                        st.write(f"RS: {q['rs']}")
                        st.write(f"Warp denier: {q['warp_denier']}")
                        if q["weft_denier_mode"] == "denier":
                            st.write(f"Weft denier: {q['weft_denier']}")
                        else:
                            st.write(f"Weft count (Ne): {q['weft_count']}")
                            st.write(f"(Calculated weft denier used for costing: {q['weft_denier']})")
                        st.write(f"Warp yarn: {q['warp_yarn_name']} @ {q['warp_yarn_price']} ₹/kg")
                        st.write(f"Weft yarn: {q['weft_yarn_name']} @ {q['weft_yarn_price']} ₹/kg")

                    elif view_mode == "Details":
                        col1, col2 = st.columns(2)
                        with col1:
                            st.markdown("**Warp**")
                            st.write(f"Ends mode: {q['ends_mode']}")
                            st.write(f"Ends: {q['ends']}")
                            st.write(f"Reed: {q['reed']}")
                            st.write(f"RS: {q['rs']}")
                            st.write(f"Borders: {q['borders']}")
                            st.write(f"Warp denier: {q['warp_denier']}")
                            st.write(f"Warp yarn: {q['warp_yarn_name']}")
                            st.write(f"Warp yarn price: {q['warp_yarn_price']} ₹/kg")

                            st.markdown("**Weft**")
                            st.write(f"Picks: {q['picks']}")
                            st.write(f"Weft RS: {q['weft_rs']}")
                            st.write(f"Weft mode: {q['weft_denier_mode']}")
                            st.write(f"Weft denier: {q['weft_denier']}")
                            st.write(f"Weft count: {q['weft_count']}")
                            st.write(f"Weft yarn: {q['weft_yarn_name']}")
                            st.write(f"Weft yarn price: {q['weft_yarn_price']} ₹/kg")

                            st.markdown("**Pricing setup**")
                            st.write(f"Weaving rate per pick: {q['weaving_rate_per_pick']} ₹/pick/m")
                            st.write(f"Grey markup %: {q['grey_markup_percent']} %")
                            st.write(f"RFD charge / m: {q['rfd_charge_per_m']} ₹/m")
                            st.write(f"RFD shortage (₹/m): {q['rfd_shortage_percent']} ₹/m")
                            st.write(f"RFD markup %: {q['rfd_markup_percent']} %")

                        with col2:
                            st.markdown("**Costs (per 100 m)**")
                            st.write(f"Warp weight: {warp_weight_100:.3f} kg")
                            st.write(f"Weft weight: {weft_weight_100:.3f} kg")
                            st.write(f"Fabric weight: {fabric_weight_100:.3f} kg")
                            st.write(f"Warp cost: {q['warp_cost_100']:.2f} ₹")
                            st.write(f"Weft cost: {q['weft_cost_100']:.2f} ₹")
                            st.write(f"Weaving charge: {q['weaving_charge_100']:.2f} ₹")
                            st.write(f"Interest on yarn: {q['interest_on_yarn_100']:.2f} ₹")
                            st.write(f"Final grey cost: {q['final_grey_cost_100']:.2f} ₹")
                            st.write(f"Grey sale: {q['grey_sale_100']:.2f} ₹")
                            st.write(f"RFD cost: {q['rfd_cost_100']:.2f} ₹")
                            st.write(f"RFD sale: {q['rfd_sale_100']:.2f} ₹")

                            st.markdown("**Per meter**")
                            st.write(f"Grey cost / m: {grey_cost_per_m:.2f} ₹/m")
                            st.write(f"Grey sale / m: {grey_sale_per_m:.2f} ₹/m")
                            st.write(f"RFD cost / m: {rfd_cost_per_m:.2f} ₹/m")
                            st.write(f"RFD sale / m: {rfd_sale_per_m:.2f} ₹/m")

                    elif view_mode == "Edit":
                        st.subheader("Edit Quality (overwrite)")

                        with st.form("edit_quality_form"):
                            eq1, eq2, eq3 = st.columns(3)
                            with eq1:
                                new_quality_name = st.text_input("Quality name", value=q["quality_name"])
                                new_ends_mode_label = st.radio(
                                    "Ends input mode",
                                    ["Enter ends directly", "Calculate from reed, RS, borders"],
                                    index=0 if q["ends_mode"] == "direct" else 1
                                )
                                new_ends_mode = "direct" if new_ends_mode_label == "Enter ends directly" else "calc"
                            with eq2:
                                new_rs = st.number_input(
                                    "RS (for both warp & weft)", min_value=0.0, step=0.1,
                                    value=float(q["rs"])
                                )
                                new_reed = st.number_input(
                                    "Reed", min_value=0.0, step=0.1,
                                    value=float(q["reed"] if q["reed"] else 0.0)
                                )
                                new_borders = st.number_input(
                                    "Borders", min_value=0.0, step=1.0,
                                    value=float(q["borders"] if q["borders"] else 0.0)
                                )
                            with eq3:
                                new_ends = st.number_input(
                                    "Ends", min_value=0.0, step=1.0,
                                    value=float(q["ends"])
                                )

                            ew1, ew2, ew3 = st.columns(3)
                            with ew1:
                                new_warp_denier = st.number_input(
                                    "Warp denier", min_value=0.0, step=0.1,
                                    value=float(q["warp_denier"])
                                )
                                new_picks = st.number_input(
                                    "Picks", min_value=0.0, step=1.0,
                                    value=float(q["picks"])
                                )
                            with ew2:
                                new_weft_denier_mode_label = st.radio(
                                    "Weft specification",
                                    ["Denier", "Count (Ne)"],
                                    index=0 if q["weft_denier_mode"] == "denier" else 1
                                )
                                new_weft_denier_mode = "denier" if new_weft_denier_mode_label == "Denier" else "count"
                                if new_weft_denier_mode == "denier":
                                    new_weft_denier = st.number_input(
                                        "Weft denier", min_value=0.0, step=0.1,
                                        value=float(q["weft_denier"])
                                    )
                                    new_weft_count = q["weft_count"]
                                else:
                                    new_weft_count = st.number_input(
                                        "Weft count (Ne)", min_value=0.0, step=0.1,
                                        value=float(q["weft_count"] if q["weft_count"] else 0.0)
                                    )
                                    new_weft_denier = q["weft_denier"]
                            with ew3:
                                new_warp_yarn_price = st.number_input(
                                    "Warp yarn price per kg (₹)", min_value=0.0, step=0.1,
                                    value=float(q["warp_yarn_price"])
                                )
                                new_weft_yarn_price = st.number_input(
                                    "Weft yarn price per kg (₹)", min_value=0.0, step=0.1,
                                    value=float(q["weft_yarn_price"])
                                )

                            ec1, ec2, ec3 = st.columns(3)
                            with ec1:
                                new_weaving_rate_per_pick = st.number_input(
                                    "Weaving charge per pick (₹/pick/m)", min_value=0.0, step=0.01,
                                    value=float(q["weaving_rate_per_pick"])
                                )
                                new_grey_markup_percent = st.number_input(
                                    "Grey markup % (margin on sale)", min_value=0.0, step=0.5,
                                    value=float(q["grey_markup_percent"])
                                )
                            with ec2:
                                new_rfd_charge_per_m = st.number_input(
                                    "RFD charge (₹ per m)", min_value=0.0, step=0.1,
                                    value=float(q["rfd_charge_per_m"])
                                )
                                new_rfd_shortage_per_m = st.number_input(
                                    "RFD shortage (₹ per m)", min_value=0.0, step=0.1,
                                    value=float(q["rfd_shortage_percent"])
                                )
                            with ec3:
                                new_rfd_markup_percent = st.number_input(
                                    "RFD markup % (margin on sale)", min_value=0.0, step=0.5,
                                    value=float(q["rfd_markup_percent"])
                                )

                            update_btn = st.form_submit_button("Save changes")

                        if update_btn:
                            if new_grey_markup_percent >= 100 or new_rfd_markup_percent >= 100:
                                st.error("Markup % must be less than 100 (margin on sale).")
                            else:
                                if new_ends_mode == "calc":
                                    new_ends = new_reed * new_rs + new_borders

                                if new_weft_denier_mode == "denier":
                                    wd = float(new_weft_denier)
                                    wc = new_weft_count
                                else:
                                    wc = float(new_weft_count)
                                    wd = 5315.0 / wc if wc > 0 else 0.0

                                cost = calculate_costing(
                                    ends=float(new_ends),
                                    warp_denier=float(new_warp_denier),
                                    picks=float(new_picks),
                                    weft_denier=float(wd),
                                    rs=float(new_rs),
                                    warp_yarn_price=float(new_warp_yarn_price),
                                    weft_yarn_price=float(new_weft_yarn_price),
                                    weaving_rate_per_pick=float(new_weaving_rate_per_pick),
                                    grey_markup_percent=float(new_grey_markup_percent),
                                    rfd_charge_per_m=float(new_rfd_charge_per_m),
                                    rfd_shortage_amount_per_m=float(new_rfd_shortage_per_m),
                                    rfd_markup_percent=float(new_rfd_markup_percent)
                                )

                                upd = {
                                    "created_at": datetime.now().isoformat(timespec="seconds"),
                                    "quality_name": new_quality_name,
                                    "ends_mode": new_ends_mode,
                                    "ends": float(new_ends),
                                    "reed": float(new_reed),
                                    "rs": float(new_rs),
                                    "borders": float(new_borders),
                                    "warp_denier": float(new_warp_denier),
                                    "warp_yarn_name": q["warp_yarn_name"],
                                    "warp_yarn_price": float(new_warp_yarn_price),
                                    "picks": float(new_picks),
                                    "weft_rs": float(new_rs),
                                    "weft_denier_mode": new_weft_denier_mode,
                                    "weft_denier": float(wd),
                                    "weft_count": float(new_weft_count) if new_weft_count else None,
                                    "weft_yarn_name": q["weft_yarn_name"],
                                    "weft_yarn_price": float(new_weft_yarn_price),
                                    "weaving_rate_per_pick": float(new_weaving_rate_per_pick),
                                    "grey_markup_percent": float(new_grey_markup_percent),
                                    "rfd_charge_per_m": float(new_rfd_charge_per_m),
                                    "rfd_shortage_percent": float(new_rfd_shortage_per_m),
                                    "rfd_markup_percent": float(new_rfd_markup_percent),
                                    "warp_weight_100": cost["warp_weight_100"],
                                    "weft_weight_100": cost["weft_weight_100"],
                                    "fabric_weight_100": cost["fabric_weight_100"],
                                    "warp_cost_100": cost["warp_cost_100"],
                                    "weft_cost_100": cost["weft_cost_100"],
                                    "weaving_charge_100": cost["weaving_charge_100"],
                                    "interest_on_yarn_100": cost["interest_on_yarn_100"],
                                    "final_grey_cost_100": cost["final_grey_cost_100"],
                                    "grey_sale_100": cost["grey_sale_100"],
                                    "rfd_cost_100": cost["rfd_cost_100"],
                                    "rfd_sale_100": cost["rfd_sale_100"],
                                }

                                update_quality(selected_id, upd)
                                st.success("Quality updated (overwritten).")

# ---------------------------
# Page: Pricing Sheet
# ---------------------------
elif page == "📄 Pricing Sheet":
    st.header("📄 Pricing Sheet")

    conn = get_conn()
    import pandas as pd
    df = pd.read_sql_query("""
        SELECT id, quality_name,
               warp_weight_100, weft_weight_100,
               grey_sale_100, rfd_sale_100
        FROM qualities
        ORDER BY quality_name COLLATE NOCASE
    """, conn)
    conn.close()

    if df.empty:
        st.info("No qualities saved yet.")
    else:
        df["fabric_weight_tech_kg_100m"] = (df["warp_weight_100"] + df["weft_weight_100"]).round(3)
        df["fabric_weight_costing_kg_100m"] = ((df["warp_weight_100"] * 1.09) + df["weft_weight_100"]).round(3)
        df["grey_sale_per_m"] = (df["grey_sale_100"] / 100.0).round(2)
        df["rfd_sale_per_m"] = (df["rfd_sale_100"] / 100.0).round(2)

        show_df = df[[
            "quality_name",
            "fabric_weight_tech_kg_100m",
            "fabric_weight_costing_kg_100m",
            "grey_sale_per_m",
            "rfd_sale_per_m"
        ]].rename(columns={
            "quality_name": "Quality",
            "fabric_weight_tech_kg_100m": "Weight (tech, kg/100m)",
            "fabric_weight_costing_kg_100m": "Weight (warp+shortage, weft no shortage, kg/100m)",
            "grey_sale_per_m": "Grey Sale (₹/m)",
            "rfd_sale_per_m": "RFD Sale (₹/m)"
        })

        st.dataframe(show_df, use_container_width=True)

        csv = show_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download as CSV",
            data=csv,
            file_name="pricing_sheet.csv",
            mime="text/csv"
        )