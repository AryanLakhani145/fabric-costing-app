import os
import json 
import streamlit as st
import sqlite3
from datetime import date, datetime

st.caption("🔁 Build: multi-weft v2")

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
            st.rerun()
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
    # ✅ New: column for multi-weft data
    try:
        cur.execute("ALTER TABLE qualities ADD COLUMN wefts_json TEXT;")
    except sqlite3.OperationalError:
        pass

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

def get_latest_yarn_row(name, yarn_type=None):
    """
    Return latest full row for this yarn:
    {id, name, yarn_type, count, denier, price_per_kg, valid_from}
    """
    conn = get_conn()
    cur = conn.cursor()
    if yarn_type:
        cur.execute("""
            SELECT id, name, yarn_type, count, denier, price_per_kg, valid_from
            FROM yarn_prices
            WHERE name = ? AND (yarn_type = ? OR yarn_type = 'both')
            ORDER BY date(valid_from) DESC, id DESC
            LIMIT 1
        """, (name, yarn_type))
    else:
        cur.execute("""
            SELECT id, name, yarn_type, count, denier, price_per_kg, valid_from
            FROM yarn_prices
            WHERE name = ?
            ORDER BY date(valid_from) DESC, id DESC
            LIMIT 1
        """, (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "yarn_type": row[2],
        "count": row[3],
        "denier": row[4],
        "price_per_kg": row[5],
        "valid_from": row[6],
    }

def update_yarn_row(row_id, name, yarn_type, count, denier, price_per_kg, valid_from):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE yarn_prices
        SET name = ?, yarn_type = ?, count = ?, denier = ?, price_per_kg = ?, valid_from = ?
        WHERE id = ?
    """, (name, yarn_type, count, denier, price_per_kg, valid_from, row_id))
    conn.commit()
    conn.close()

def delete_yarn_completely(name):
    """Delete ALL rows with this yarn name."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM yarn_prices WHERE name = ?", (name,))
    conn.commit()
    conn.close()

def get_latest_yarn_row(name, yarn_type=None):
    """
    Returns full latest row for this yarn (id, name, yarn_type, count, denier, price_per_kg, valid_from)
    """
    conn = get_conn()
    cur = conn.cursor()
    if yarn_type:
        cur.execute("""
            SELECT id, name, yarn_type, count, denier, price_per_kg, valid_from
            FROM yarn_prices
            WHERE name = ? AND (yarn_type = ? OR yarn_type = 'both')
            ORDER BY date(valid_from) DESC, id DESC
            LIMIT 1
        """, (name, yarn_type))
    else:
        cur.execute("""
            SELECT id, name, yarn_type, count, denier, price_per_kg, valid_from
            FROM yarn_prices
            WHERE name = ?
            ORDER BY date(valid_from) DESC, id DESC
            LIMIT 1
        """, (name,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "yarn_type": row[2],
        "count": row[3],
        "denier": row[4],
        "price_per_kg": row[5],
        "valid_from": row[6],
    }

def update_yarn_row(row_id, name, yarn_type, count, denier, price_per_kg, valid_from):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE yarn_prices
        SET name = ?, yarn_type = ?, count = ?, denier = ?, price_per_kg = ?, valid_from = ?
        WHERE id = ?
    """, (name, yarn_type, count, denier, price_per_kg, valid_from, row_id))
    conn.commit()
    conn.close()

def delete_yarn_completely(name):
    """
    Delete ALL rows for this yarn name (in case you want to wipe it).
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM yarn_prices WHERE name = ?", (name,))
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
            grey_sale_100, rfd_cost_100, rfd_sale_100,
            wefts_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        data.get("wefts_json")  # 👈 new
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
            grey_sale_100 = ?, rfd_cost_100 = ?, rfd_sale_100 = ?,
            wefts_json = ?
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
        data.get("wefts_json"),
        q_id
    ))

    conn.commit()
    conn.close()

def delete_quality(q_id):
    """Delete a quality by id."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM qualities WHERE id = ?", (q_id,))
    conn.commit()
    conn.close()

def compute_dynamic_cost(q):
    """
    Recompute costing using the recipe + latest yarn prices.
    - Uses wefts_json if present (multi-weft).
    - Falls back to single-weft fields if not.
    """
    # --- Warp: dynamic price & optional denier from yarn table ---
    warp_denier = float(q["warp_denier"]) if q["warp_denier"] is not None else 0.0
    warp_price = float(q["warp_yarn_price"]) if q["warp_yarn_price"] is not None else 0.0

    if q.get("warp_yarn_name"):
        latest_price, latest_dnr, latest_cnt = get_latest_yarn_price(q["warp_yarn_name"], "warp")
        if latest_price:
            warp_price = latest_price
        if latest_dnr:
            warp_denier = latest_dnr  # if you want denier to follow yarn table

    ends = float(q["ends"])
    rs = float(q["rs"])

    # --- Build weft list ---
    # --- Build weft list ---
    weft_entries = []
    weft_details = []   # 👈 for per-weft breakdown

    if q.get("wefts_json"):
        # Multi-weft case
        try:
            stored_wefts = json.loads(q["wefts_json"])
        except Exception:
            stored_wefts = []

        for wf in stored_wefts:
            p = float(wf.get("picks", 0.0) or 0.0)
            d = float(wf.get("denier", 0.0) or 0.0)
            price = float(wf.get("price", 0.0) or 0.0)
            mode = wf.get("mode", "denier")
            cnt = wf.get("count", 0.0) or 0.0
            yarn_name = wf.get("yarn_name")

            # Override from yarn table if yarn_name is linked
            if yarn_name and yarn_name != "(manual price)":
                latest_price, latest_dnr, latest_cnt = get_latest_yarn_price(yarn_name, "weft")
                if latest_price:
                    price = latest_price
                if mode == "denier" and latest_dnr:
                    d = latest_dnr
                if mode == "count":
                    # Prefer count from yarn table, then convert to denier
                    if latest_cnt:
                        cnt = latest_cnt
                    if cnt and cnt > 0:
                        d = 5315.0 / cnt

            # per-weft technical weight / 100 m (no shortage)
            if p > 0 and d > 0:
                weight_100 = (p * d * rs) / 90000.0
            else:
                weight_100 = 0.0

            if p > 0 and d > 0 and price > 0:
                weft_entries.append({"picks": p, "denier": d, "price": price})

            if p > 0 and d > 0:
                weft_details.append({
                    "label": f"Weft {len(weft_details) + 1}",
                    "picks": p,
                    "denier": d,
                    "price": price,
                    "weight_100": weight_100,
                    "mode": mode,
                    "count": cnt,
                    "yarn_name": yarn_name,
                })
    else:
        # Old single-weft records (no wefts_json)
        p = float(q["picks"])
        d = float(q["weft_denier"])
        price = float(q["weft_yarn_price"])
        mode = q.get("weft_denier_mode", "denier")
        cnt = q.get("weft_count")
        yarn_name = q.get("weft_yarn_name")

        if yarn_name:
            latest_price, latest_dnr, latest_cnt = get_latest_yarn_price(yarn_name, "weft")
            if latest_price:
                price = latest_price
            if mode == "denier" and latest_dnr:
                d = latest_dnr
            if mode == "count":
                if latest_cnt:
                    cnt = latest_cnt
                if cnt and cnt > 0:
                    d = 5315.0 / cnt

        if p > 0 and d > 0 and price > 0:
            weft_entries.append({"picks": p, "denier": d, "price": price})

        if p > 0 and d > 0:
            weight_100 = (p * d * rs) / 90000.0
            weft_details.append({
                "label": "Weft 1",
                "picks": p,
                "denier": d,
                "price": price,
                "weight_100": weight_100,
                "mode": mode,
                "count": cnt,
                "yarn_name": yarn_name,
            })

    # --- Aggregate wefts to effective denier & price ---
    total_picks = sum(w["picks"] for w in weft_entries)
    num_for_den = sum(w["picks"] * w["denier"] for w in weft_entries)
    num_for_price = sum(w["picks"] * w["denier"] * w["price"] for w in weft_entries)

    if total_picks <= 0 or num_for_den <= 0:
        # Fallback to stored single-weft values if something's off
        total_picks = float(q["picks"])
        eff_weft_denier = float(q["weft_denier"])
        eff_weft_price = float(q["weft_yarn_price"])
    else:
        eff_weft_denier = num_for_den / total_picks
        eff_weft_price = num_for_price / num_for_den

    weaving_rate = float(q["weaving_rate_per_pick"])
    grey_markup = float(q["grey_markup_percent"])
    rfd_charge = float(q["rfd_charge_per_m"])
    rfd_short = float(q["rfd_shortage_percent"])
    rfd_markup = float(q["rfd_markup_percent"])

    # 🔥 Use your existing costing function
    cost = calculate_costing(
        ends=ends,
        warp_denier=warp_denier,
        picks=total_picks,
        weft_denier=eff_weft_denier,
        rs=rs,
        warp_yarn_price=warp_price,
        weft_yarn_price=eff_weft_price,
        weaving_rate_per_pick=weaving_rate,
        grey_markup_percent=grey_markup,
        rfd_charge_per_m=rfd_charge,
        rfd_shortage_percent=rfd_short,
        rfd_markup_percent=rfd_markup,
    )

    # Also return the aggregated weft info in case UI wants it
    cost["_dynamic_total_picks"] = total_picks
    cost["_dynamic_eff_weft_denier"] = eff_weft_denier
    cost["_dynamic_eff_weft_price"] = eff_weft_price
    cost["_weft_breakdown"] = weft_details

    return cost

def calculate_costing(
    ends, warp_denier, picks, weft_denier, rs,
    warp_yarn_price, weft_yarn_price,
    weaving_rate_per_pick, grey_markup_percent,
    rfd_charge_per_m, rfd_shortage_percent, rfd_markup_percent,
    include_interest=True,       # 👈 NEW
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

    # 🔹 Interest on yarn – now optional
    interest_on_yarn_100_full = (warp_cost_100 + weft_cost_100) * 0.04
    interest_on_yarn_100 = interest_on_yarn_100_full if include_interest else 0.0

    # Grey cost
    final_grey_cost_100 = warp_cost_100 + weft_cost_100 + weaving_charge_100 + interest_on_yarn_100
    grey_cost_per_m = final_grey_cost_100 / 100.0

    # Grey sale with markup as margin on selling price
    if grey_markup_percent == 0:
        grey_sale_per_m = grey_cost_per_m
    else:
        grey_sale_per_m = grey_cost_per_m / (1 - grey_markup_percent / 100.0)
    grey_sale_100 = grey_sale_per_m * 100.0

    # RFD cost: (grey + RFD charge) * (1 + shortage%)
    base_for_rfd = grey_cost_per_m + rfd_charge_per_m
    rfd_cost_per_m = base_for_rfd * (1 + rfd_shortage_percent / 100.0)

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

def calculate_costing_multi_weft(
    ends, warp_denier, rs,
    warp_yarn_price,
    weft_list,
    weaving_rate_per_pick, grey_markup_percent,
    rfd_charge_per_m, rfd_shortage_percent, rfd_markup_percent,
    include_interest=True,
):
    """
    Multi-weft version of calculate_costing.
    weft_list = [
        {"picks": ..., "weft_denier": ..., "weft_yarn_price": ...},
        ...
    ]
    """
    # ---- Warp (same logic as before) ----
    warp_weight_100 = (ends * warp_denier) / 90000.0
    warp_weight_100_short = warp_weight_100 * 1.09
    warp_cost_100 = warp_weight_100_short * warp_yarn_price

    # ---- Sum over all wefts ----
    total_weft_weight_100 = 0.0          # technical (no shortage)
    total_weft_weight_100_short = 0.0    # with shortage
    total_weft_cost_100 = 0.0
    total_picks = 0.0

    for w in weft_list:
        picks = w["picks"]
        weft_den = w["weft_denier"]
        price = w["weft_yarn_price"]

        weft_weight_100 = (picks * weft_den * rs) / 90000.0
        weft_weight_100_short = weft_weight_100 * 1.03
        weft_cost_100 = weft_weight_100_short * price

        total_weft_weight_100 += weft_weight_100
        total_weft_weight_100_short += weft_weight_100_short
        total_weft_cost_100 += weft_cost_100
        total_picks += picks

    # ---- Fabric weight (technical) ----
    fabric_weight_100 = warp_weight_100 + total_weft_weight_100

    # ---- Weaving ----
    weaving_per_m = weaving_rate_per_pick * total_picks
    weaving_charge_100 = weaving_per_m * 100.0

    # ---- Interest on yarn (respect toggle) ----
    if include_interest:
        interest_on_yarn_100 = (warp_cost_100 + total_weft_cost_100) * 0.04
    else:
        interest_on_yarn_100 = 0.0

    # ---- Grey cost ----
    final_grey_cost_100 = warp_cost_100 + total_weft_cost_100 + weaving_charge_100 + interest_on_yarn_100
    grey_cost_per_m = final_grey_cost_100 / 100.0

    # Grey sale with markup as margin on selling price
    if grey_markup_percent == 0:
        grey_sale_per_m = grey_cost_per_m
    else:
        grey_sale_per_m = grey_cost_per_m / (1 - grey_markup_percent / 100.0)
    grey_sale_100 = grey_sale_per_m * 100.0

    # RFD cost: (grey + RFD charge) * (1 + shortage%)
    base_for_rfd = grey_cost_per_m + rfd_charge_per_m
    rfd_cost_per_m = base_for_rfd * (1 + rfd_shortage_percent / 100.0)

    # RFD sale with markup as margin on selling price
    if rfd_markup_percent == 0:
        rfd_sale_per_m = rfd_cost_per_m
    else:
        rfd_sale_per_m = rfd_cost_per_m / (1 - rfd_markup_percent / 100.0)
    rfd_cost_100 = rfd_cost_per_m * 100.0
    rfd_sale_100 = rfd_sale_per_m * 100.0

    return {
        "warp_weight_100": warp_weight_100,
        "weft_weight_100": total_weft_weight_100,
        "fabric_weight_100": fabric_weight_100,
        "warp_cost_100": warp_cost_100,
        "weft_cost_100": total_weft_cost_100,
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

# 🔒 Password gate – everything below runs only after correct password
if not check_password():
    st.stop()

st.title("🧵 Fabric Costing App")

# How many wefts to show in "What-if → Start from scratch"
if "scratch_weft_rows" not in st.session_state:
    st.session_state["scratch_weft_rows"] = 1

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

    # Quick edit + rename + delete (edit latest row, not add new)
    st.markdown("### ✏️ Quick Edit / Rename Yarn")
    yarn_names_all = list_yarn_names()
    if yarn_names_all:
        selected_yarn = st.selectbox(
            "Select yarn to edit",
            yarn_names_all,
            key="edit_yarn_select"
        )

        row = get_latest_yarn_row(selected_yarn)
        if row:
            try:
                default_date = date.fromisoformat(row["valid_from"])
            except Exception:
                default_date = date.today()

            # Use keys that depend on selected_yarn so values refresh when selection changes
            ec0, ec1, ec2, ec3, ec4 = st.columns([2, 2, 2, 2, 2])
            with ec0:
                new_name = st.text_input(
                    "Yarn name (can rename)",
                    value=row["name"],
                    key=f"edit_yarn_name_{selected_yarn}"
                )
            with ec1:
                new_price = st.number_input(
                    "Price per kg (₹)",
                    min_value=0.0,
                    step=0.1,
                    value=float(row["price_per_kg"] if row["price_per_kg"] else 0.0),
                    key=f"edit_price_{selected_yarn}"
                )
            with ec2:
                new_denier = st.number_input(
                    "Denier (optional)",
                    min_value=0.0,
                    step=0.1,
                    value=float(row["denier"] if row["denier"] else 0.0),
                    key=f"edit_denier_{selected_yarn}"
                )
            with ec3:
                new_count = st.number_input(
                    "Count (optional)",
                    min_value=0.0,
                    step=0.1,
                    value=float(row["count"] if row["count"] else 0.0),
                    key=f"edit_count_{selected_yarn}"
                )
            with ec4:
                new_valid_from = st.date_input(
                    "Valid from",
                    value=default_date,
                    key=f"edit_valid_from_{selected_yarn}"
                )

            b1, b2 = st.columns(2)
            with b1:
                if st.button("💾 Save changes to this yarn", key=f"save_yarn_{selected_yarn}"):
                    update_yarn_row(
                        row_id=row["id"],
                        name=new_name,
                        yarn_type=row["yarn_type"],
                        count=new_count if new_count > 0 else None,
                        denier=new_denier if new_denier > 0 else None,
                        price_per_kg=new_price,
                        valid_from=new_valid_from.isoformat()
                    )
                    st.success("Yarn updated successfully.")
            with b2:
                if st.button("🗑 Delete this yarn completely", key=f"delete_yarn_{selected_yarn}"):
                    delete_yarn_completely(selected_yarn)
                    st.warning(f"Yarn '{selected_yarn}' deleted. Reload page to refresh.")
        else:
            st.info("No data found for this yarn.")
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

    # 🔹 Initialise session list for new-costing wefts
    if "new_costing_wefts" not in st.session_state:
        st.session_state["new_costing_wefts"] = [
            {
                "label": "Weft 1",
                "picks": 0.0,
                "mode": "denier",   # or "count"
                "denier": 0.0,
                "count": 0.0,
                "yarn_name": "(manual price)",
                "price": 0.0,
            }
        ]

    wefts = st.session_state["new_costing_wefts"]

    # 🔘 Button to add weft (kept near the weft section)
    if st.button("➕ Add weft"):
        wefts.append(
            {
                "label": f"Weft {len(wefts) + 1}",
                "picks": 0.0,
                "mode": "denier",
                "denier": 0.0,
                "count": 0.0,
                "yarn_name": "(manual price)",
                "price": 0.0,
            }
        )

    # Show each weft row
    # Show each weft row
    for idx, wf in enumerate(wefts):
        st.markdown(f"**{wf['label']}**")

        # ---- define keys for this row ----
        picks_key   = f"new_weft_picks_{idx}"
        mode_key    = f"new_weft_mode_{idx}"
        denier_key  = f"new_weft_denier_{idx}"
        count_key   = f"new_weft_count_{idx}"
        price_key   = f"new_weft_price_{idx}"
        yarn_key    = f"new_weft_yarn_{idx}"
        last_yarn_key = f"new_weft_last_yarn_{idx}"

        # ---- read current mode & yarn *from state* (before widgets) ----
        current_mode_label = st.session_state.get(mode_key, "Denier")
        current_mode = "denier" if current_mode_label == "Denier" else "count"

        weft_yarn_names = list_yarn_names("weft")
        yarn_options = ["(manual price)"] + weft_yarn_names
        current_yarn = st.session_state.get(yarn_key, wf["yarn_name"])
        if current_yarn not in yarn_options:
            current_yarn = "(manual price)"

        prev_yarn = st.session_state.get(last_yarn_key, None)

        # ---- if yarn selected (and possibly changed), push latest vals into widget state ----
        if current_yarn != "(manual price)":
            latest_price, latest_denier, latest_count = get_latest_yarn_price(current_yarn, "weft")

            yarn_changed = (current_yarn != prev_yarn)

            # price
            if latest_price is not None and (yarn_changed or st.session_state.get(price_key, 0.0) == 0.0):
                st.session_state[price_key] = float(latest_price)

            # denier / count depending on mode
            if current_mode == "denier":
                if latest_denier is not None and latest_denier > 0 \
                   and (yarn_changed or st.session_state.get(denier_key, 0.0) == 0.0):
                    st.session_state[denier_key] = float(latest_denier)
                elif latest_count is not None and latest_count > 0 \
                     and (yarn_changed or st.session_state.get(denier_key, 0.0) == 0.0):
                    st.session_state[denier_key] = 5315.0 / float(latest_count)
            else:  # count mode
                if latest_count is not None and latest_count > 0 \
                   and (yarn_changed or st.session_state.get(count_key, 0.0) == 0.0):
                    st.session_state[count_key] = float(latest_count)
                    st.session_state[denier_key] = 5315.0 / float(latest_count)
                elif latest_denier is not None and latest_denier > 0 \
                     and (yarn_changed or st.session_state.get(denier_key, 0.0) == 0.0):
                    st.session_state[denier_key] = float(latest_denier)

        # remember yarn for next run
        st.session_state[last_yarn_key] = current_yarn

        # ---------- now draw the widgets ----------
        c1, c2, c3, c4 = st.columns([1.2, 1.5, 1.5, 0.7])

        with c1:
            wf["picks"] = st.number_input(
                "Picks",
                min_value=0.0,
                step=1.0,
                key=picks_key,
                value=float(wf["picks"])
            )

        with c2:
            mode_label = st.radio(
                "Weft spec",
                ["Denier", "Count (Ne)"],
                index=0 if current_mode == "denier" else 1,
                key=mode_key,
                horizontal=True,
            )
            wf["mode"] = "denier" if mode_label == "Denier" else "count"

            if wf["mode"] == "denier":
                wf["denier"] = st.number_input(
                    "Denier",
                    min_value=0.0,
                    step=0.1,
                    key=denier_key,
                    value=float(st.session_state.get(denier_key, wf["denier"]))
                )
                wf["count"] = 0.0
            else:
                wf["count"] = st.number_input(
                    "Count (Ne)",
                    min_value=0.0,
                    step=0.1,
                    key=count_key,
                    value=float(st.session_state.get(count_key, wf["count"]))
                )
                if wf["count"] > 0:
                    wf["denier"] = 5315.0 / wf["count"]

        with c3:
            wf["yarn_name"] = st.selectbox(
                "Weft yarn",
                yarn_options,
                key=yarn_key,
                index=yarn_options.index(current_yarn),
            )

            wf["price"] = st.number_input(
                "Price (₹/kg)",
                min_value=0.0,
                step=0.1,
                key=price_key,
                value=float(st.session_state.get(price_key, wf["price"]))
            )

        with c4:
            if st.button("🗑 Remove", key=f"new_weft_remove_{idx}"):
                wefts.pop(idx)
                st.rerun()

    st.markdown("### Charges & Markups")
    ch1, ch2, ch3 = st.columns(3)
    with ch1:
        weaving_rate_per_pick = st.number_input(
            "Weaving charge per pick (₹/pick/m)", min_value=0.0, step=0.01, value=0.16
        )
        grey_markup_percent = st.number_input("Grey markup % (margin on sale)", min_value=0.0, step=0.5, value=0.0)
    with ch2:
        rfd_charge_per_m = st.number_input("RFD charge (₹ per m)", min_value=0.0, step=0.1, value=0.0)
        rfd_shortage_percent = st.number_input("RFD shortage (%)", min_value=0.0, step=0.1, value=0.0)
    with ch3:
        rfd_markup_percent = st.number_input("RFD markup % (margin on sale)", min_value=0.0, step=0.5, value=0.0)
        
        include_interest_new = st.checkbox(
        "Include 4% interest on yarn in grey cost",
        value=True,
        key="include_interest_new"
    )

    if st.button("Calculate & Save"):
        # ✅ Basic validation (warp + RS etc.)
        if not quality_name:
            st.error("Please enter a quality name.")
            st.stop()
        elif warp_denier <= 0 or warp_yarn_price <= 0:
            st.error("Please enter valid warp yarn denier/price.")
            st.stop()
        elif rs is None or rs <= 0:
            st.error("Please enter a valid RS.")
            st.stop()
        elif grey_markup_percent >= 100 or rfd_markup_percent >= 100:
            st.error("Markup % must be less than 100 (it's margin on sale).")
            st.stop()

        # ✅ Build wefts list from session
        raw_wefts = st.session_state.get("new_costing_wefts", [])
        valid_wefts = []
        total_picks = 0.0
        num_for_den = 0.0       # Σ(picks * denier)
        num_for_price = 0.0     # Σ(picks * denier * price)

        for wf in raw_wefts:
            p = float(wf.get("picks", 0.0) or 0.0)
            d = float(wf.get("denier", 0.0) or 0.0)
            price = float(wf.get("price", 0.0) or 0.0)
            mode = wf.get("mode", "denier")
            cnt = float(wf.get("count", 0.0) or 0.0)
            yarn_name = wf.get("yarn_name")

            if p > 0 and d > 0 and price > 0:
                # 👉 this goes into DB in wefts_json
                valid_wefts.append(
                    {
                        "picks": p,
                        "denier": d,
                        "price": price,
                        "mode": mode,
                        "count": cnt,
                        "yarn_name": yarn_name,
                    }
                )
                total_picks += p
                num_for_den += p * d
                num_for_price += p * d * price

        if not valid_wefts:
            st.error("Please enter at least one valid weft (picks, denier and price > 0).")
            st.stop()

        # 🔢 Effective weft values for the existing single-weft formula
        # We want weight and cost to match sums over all wefts.
        eff_weft_denier = num_for_den / total_picks        # Σ(p*d)/Σ(p)
        eff_weft_price = num_for_price / num_for_den       # Σ(p*d*price)/Σ(p*d)

        # ✅ Ends computation (same as before)
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

        # 🔥 Call your existing single-weft costing function
        # Here we pass total_picks + effective weft denier/price
        cost = calculate_costing(
            ends=float(ends),
            warp_denier=float(warp_denier),
            picks=float(total_picks),
            weft_denier=float(eff_weft_denier),
            rs=float(rs),
            warp_yarn_price=float(warp_yarn_price),
            weft_yarn_price=float(eff_weft_price),
            weaving_rate_per_pick=float(weaving_rate_per_pick),
            grey_markup_percent=float(grey_markup_percent),
            rfd_charge_per_m=float(rfd_charge_per_m),
            rfd_shortage_percent=float(rfd_shortage_percent),
            rfd_markup_percent=float(rfd_markup_percent),
            # 👇 if your calculate_costing has include_interest,
            # uncomment this and make sure include_interest_new exists:
            # include_interest=include_interest_new,
        )

        # 🧾 Save everything, including full wefts as JSON
        data = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "quality_name": quality_name,
            "ends_mode": ends_mode,
            "ends": float(ends),
            "reed": float(reed) if reed is not None else None,
            "rs": float(rs),
            "borders": float(borders) if borders is not None else 0.0,
            "warp_denier": float(warp_denier),
            "warp_yarn_name": None if warp_yarn_name == "(manual price)" else warp_yarn_name,
            "warp_yarn_price": float(warp_yarn_price),

            # Store aggregated weft as "main" fields for backward compatibility
            "picks": float(total_picks),
            "weft_rs": float(rs),
            "weft_denier_mode": "denier",
            "weft_denier": float(eff_weft_denier),
            "weft_count": None,
            "weft_yarn_name": None,  # multiple yarns, so we don't show a single name
            "weft_yarn_price": float(eff_weft_price),

            "weaving_rate_per_pick": float(weaving_rate_per_pick),
            "grey_markup_percent": float(grey_markup_percent),
            "rfd_charge_per_m": float(rfd_charge_per_m),
            "rfd_shortage_percent": float(rfd_shortage_percent),
            "rfd_markup_percent": float(rfd_markup_percent),

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

            # 🔐 Full multi-weft detail
            "wefts_json": json.dumps(valid_wefts),
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

    mode = st.radio(
        "Mode",
        ["Use existing quality as base", "Start from scratch (new recipe)"],
        horizontal=True
    )

    # ---------- MODE 1: EXISTING QUALITY AS BASE ----------
    if mode == "Use existing quality as base":
        qualities = list_all_qualities()
        if not qualities:
            st.info("No qualities saved yet.")
        else:
            label_to_id = {f"{q[1]} (ID {q[0]})": q[0] for q in qualities}
            labels = ["-- Select quality --"] + list(label_to_id.keys())
            selected_label = st.selectbox("Select base quality", labels)

            if selected_label != "-- Select quality --":
                q = get_quality_by_id(label_to_id[selected_label])
                if not q:
                    st.error("Could not load this quality.")
                else:
                    # ✅ EVERYTHING till form_submit_button stays inside this form
                    with st.form("what_if_existing_form"):
                        ref_name = st.text_input("Reference name (not saved)", value=q["quality_name"])

                        # --- Warp section (similar idea to New Costing) ---
                        st.markdown("### Warp")
                        w1, w2 = st.columns(2)
                        with w1:
                            wf_ends_mode_label = st.radio(
                                "Ends input mode",
                                ["Enter ends directly", "Calculate from reed, RS, borders"],
                                index=0 if q["ends_mode"] == "direct" else 1
                            )
                            wf_ends_mode = "direct" if wf_ends_mode_label == "Enter ends directly" else "calc"
                            wf_warp_denier = st.number_input(
                                "Warp denier",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["warp_denier"])
                            )
                        with w2:
                            wf_rs = st.number_input(
                                "RS (for both warp & weft)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["rs"])
                            )
                            wf_reed = st.number_input(
                                "Reed",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["reed"] if q["reed"] else 0.0)
                            )
                            wf_borders = st.number_input(
                                "Borders",
                                min_value=0.0,
                                step=1.0,
                                value=float(q["borders"] if q["borders"] else 0.0)
                            )
                            wf_ends = st.number_input(
                                "Ends",
                                min_value=0.0,
                                step=1.0,
                                value=float(q["ends"])
                            )

                        # --- Weft section ---
                        st.markdown("### Weft")
                        wf1, wf2 = st.columns(2)
                        with wf1:
                            wf_picks = st.number_input(
                                "Picks",
                                min_value=0.0,
                                step=1.0,
                                value=float(q["picks"])
                            )
                            wf_weft_mode_label = st.radio(
                                "Weft specification",
                                ["Denier", "Count (Ne)"],
                                index=0 if q["weft_denier_mode"] == "denier" else 1
                            )
                            wf_weft_mode = "denier" if wf_weft_mode_label == "Denier" else "count"
                        with wf2:
                            if wf_weft_mode == "denier":
                                wf_weft_denier = st.number_input(
                                    "Weft denier",
                                    min_value=0.0,
                                    step=0.1,
                                    value=float(q["weft_denier"])
                                )
                                wf_weft_count = q["weft_count"]
                            else:
                                wf_weft_count = st.number_input(
                                    "Weft count (Ne)",
                                    min_value=0.0,
                                    step=0.1,
                                    value=float(q["weft_count"] if q["weft_count"] else 0.0)
                                )
                                wf_weft_denier = q["weft_denier"]

                        # --- Charges & Markups ---
                        st.markdown("### Charges & Markups")
                        c1, c2, c3 = st.columns(3)
                        with c1:
                            # default to latest yarn prices if yarn names exist
                            default_warp_price = q["warp_yarn_price"]
                            if q["warp_yarn_name"]:
                                latest_warp_price, _, _ = get_latest_yarn_price(q["warp_yarn_name"], "warp")
                                if latest_warp_price:
                                    default_warp_price = latest_warp_price

                            default_weft_price = q["weft_yarn_price"]
                            if q["weft_yarn_name"]:
                                latest_weft_price, _, _ = get_latest_yarn_price(q["weft_yarn_name"], "weft")
                                if latest_weft_price:
                                    default_weft_price = latest_weft_price

                            wf_warp_price = st.number_input(
                                "Warp yarn price per kg (₹)",
                                min_value=0.0,
                                step=0.1,
                                value=float(default_warp_price)
                            )
                            wf_weft_price = st.number_input(
                                "Weft yarn price per kg (₹)",
                                min_value=0.0,
                                step=0.1,
                                value=float(default_weft_price)
                            )
                        with c2:
                            wf_weaving_rate = st.number_input(
                                "Weaving charge per pick (₹/pick/m)",
                                min_value=0.0,
                                step=0.01,
                                value=float(q["weaving_rate_per_pick"])
                            )
                            wf_grey_markup = st.number_input(
                                "Grey markup % (margin on sale)",
                                min_value=0.0,
                                step=0.5,
                                value=float(q["grey_markup_percent"])
                            )
                        with c3:
                            wf_rfd_charge = st.number_input(
                                "RFD charge (₹/m)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["rfd_charge_per_m"])
                            )
                            wf_rfd_shortage_percent = st.number_input(
                                "RFD shortage (%)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["rfd_shortage_percent"])
                            )
                            wf_rfd_markup = st.number_input(
                                "RFD markup % (margin on sale)",
                                min_value=0.0,
                                step=0.5,
                                value=float(q["rfd_markup_percent"])
                            )

                            # ✅ interest toggle must also be inside the form
                            include_interest_wf_existing = st.checkbox(
                                "Include 4% interest on yarn in grey cost",
                                value=True,
                                key="include_interest_wf_existing",
                            )

                        # 👇 THIS BUTTON **must** stay inside the `with st.form(...)` block
                        run_existing = st.form_submit_button("Recalculate (do not save)")

                    if run_existing:
                        errors = []
                        if wf_rs <= 0:
                            errors.append("RS must be > 0")
                        if wf_picks <= 0:
                            errors.append("Picks must be > 0")
                        if wf_warp_denier <= 0:
                            errors.append("Warp denier must be > 0")
                        if wf_ends_mode == "direct" and wf_ends <= 0:
                            errors.append("Ends must be > 0 when entering directly")
                        if wf_ends_mode == "calc" and wf_reed <= 0:
                            errors.append("Reed must be > 0 when calculating ends")
                        if wf_weft_mode == "denier":
                            if wf_weft_denier <= 0:
                                errors.append("Weft denier must be > 0")
                        else:
                            if not wf_weft_count or wf_weft_count <= 0:
                                errors.append("Weft count must be > 0")
                        if wf_grey_markup >= 100 or wf_rfd_markup >= 100:
                            errors.append("Markup % must be < 100 (margin on sale)")

                        if errors:
                            st.error("Fix these issues:\n- " + "\n- ".join(errors))
                        else:
                            if wf_ends_mode == "calc":
                                wf_ends = wf_reed * wf_rs + wf_borders
                            if wf_weft_mode == "count":
                                wf_weft_denier = 5315.0 / wf_weft_count

                            cost = calculate_costing(
                                ends=float(wf_ends),
                                warp_denier=float(wf_warp_denier),
                                picks=float(wf_picks),
                                weft_denier=float(wf_weft_denier),
                                rs=float(wf_rs),
                                warp_yarn_price=float(wf_warp_price),
                                weft_yarn_price=float(wf_weft_price),
                                weaving_rate_per_pick=float(wf_weaving_rate),
                                grey_markup_percent=float(wf_grey_markup),
                                rfd_charge_per_m=float(wf_rfd_charge),
                                rfd_shortage_percent=float(wf_rfd_shortage_percent),
                                rfd_markup_percent=float(wf_rfd_markup),
                                include_interest=include_interest_wf_existing,
                            )

                            warp_weight_100 = cost["warp_weight_100"]
                            weft_weight_100 = cost["weft_weight_100"]
                            fabric_weight_100 = cost["fabric_weight_100"]
                            warp_weight_100_short = warp_weight_100 * 1.09
                            fabric_weight_cost_style = warp_weight_100_short + weft_weight_100

                            c1, c2 = st.columns(2)
                            with c1:
                                st.metric("Grey cost / m (₹)", f"{cost['grey_cost_per_m']:.2f}")
                                st.metric("Grey sale / m (₹)", f"{cost['grey_sale_per_m']:.2f}")
                                st.metric("RFD cost / m (₹)", f"{cost['rfd_cost_per_m']:.2f}")
                                st.metric("RFD sale / m (₹)", f"{cost['rfd_sale_per_m']:.2f}")
                            with c2:
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
                            if wf_weft_mode == "denier":
                                st.write(f"Weft denier: {wf_weft_denier:.2f}")
                            else:
                                st.write(f"Weft count (Ne): {wf_weft_count}")
                                st.write(f"(Weft denier used for costing: {wf_weft_denier:.2f})")

    # ---------- MODE 2: SCRATCH / NEW RECIPE (NOT SAVED) ----------
    # ---------- MODE 2: SCRATCH / NEW RECIPE (NOT SAVED) ----------
    else:
        st.markdown("### Start from scratch (new recipe, not saved)")

        # Keep track of how many wefts we have in scratch mode
        if "wf_scratch_num_wefts" not in st.session_state:
            st.session_state["wf_scratch_num_wefts"] = 1
        num_wefts = st.session_state["wf_scratch_num_wefts"]

        # We'll fill this inside the form and use it after
        weft_rows = []

        with st.form("what_if_scratch_form"):
            scratch_name = st.text_input("Reference name (not saved)", value="Scratch recipe")

            # ---- WARP ----
            st.markdown("### Warp")
            sw1, sw2 = st.columns(2)
            with sw1:
                sc_ends_mode_label = st.radio(
                    "Ends input mode",
                    ["Enter ends directly", "Calculate from reed, RS, borders"],
                    index=0,
                    key="wf_scratch_ends_mode"
                )
                sc_ends_mode = "direct" if sc_ends_mode_label == "Enter ends directly" else "calc"
                sc_warp_denier = st.number_input(
                    "Warp denier",
                    min_value=0.0,
                    step=0.1,
                    value=120.0,
                    key="wf_scratch_warp_denier"
                )
            with sw2:
                sc_rs = st.number_input(
                    "RS (for both warp & weft)",
                    min_value=0.0,
                    step=0.1,
                    value=45.5,
                    key="wf_scratch_rs"
                )
                sc_reed = st.number_input(
                    "Reed",
                    min_value=0.0,
                    step=0.1,
                    value=80.0,
                    key="wf_scratch_reed"
                )
                sc_borders = st.number_input(
                    "Borders",
                    min_value=0.0,
                    step=1.0,
                    value=0.0,
                    key="wf_scratch_borders"
                )
                sc_ends = st.number_input(
                    "Ends",
                    min_value=0.0,
                    step=1.0,
                    value=3000.0,
                    key="wf_scratch_ends"
                )

            # ---- WEFT (multi-weft) ----
            st.markdown("### Weft")

            header_col, btn_col = st.columns([3, 1])
            with header_col:
                st.write("Configure one or more wefts below:")
            with btn_col:
                col_add, col_remove = st.columns(2)
                with col_add:
                    add_weft_clicked = st.form_submit_button("➕", use_container_width=True)
                with col_remove:
                    remove_weft_clicked = st.form_submit_button("➖", use_container_width=True)

            # Per-weft rows
            for i in range(num_wefts):
                st.markdown(f"**Weft {i+1}**")
                c1, c2, c3 = st.columns(3)

                with c1:
                    picks_i = st.number_input(
                        "Picks",
                        min_value=0.0,
                        step=1.0,
                        value=48.0 if i == 0 else 0.0,
                        key=f"wf_scratch_picks_{i}"
                    )

                with c2:
                    mode_label_i = st.radio(
                        "Weft specification",
                        ["Denier", "Count (Ne)"],
                        index=0,
                        key=f"wf_scratch_mode_{i}",
                        horizontal=True
                    )

                with c3:
                    price_i = st.number_input(
                        "Weft yarn price (₹/kg)",
                        min_value=0.0,
                        step=0.1,
                        value=220.0 if i == 0 else 0.0,
                        key=f"wf_scratch_price_{i}"
                    )

                if mode_label_i == "Denier":
                    denier_i = st.number_input(
                        "Weft denier",
                        min_value=0.0,
                        step=0.1,
                        value=75.0 if i == 0 else 0.0,
                        key=f"wf_scratch_denier_{i}"
                    )
                    count_i = None
                    mode_i = "denier"
                else:
                    count_i = st.number_input(
                        "Weft count (Ne)",
                        min_value=0.0,
                        step=0.1,
                        value=0.0,
                        key=f"wf_scratch_count_{i}"
                    )
                    denier_i = None
                    mode_i = "count"

                weft_rows.append(
                    {
                        "picks": picks_i,
                        "mode": mode_i,
                        "denier": denier_i,
                        "count": count_i,
                        "price": price_i,
                    }
                )

            # ---- CHARGES & MARKUPS ----
            st.markdown("### Charges & Markups")
            sch1, sch2, sch3 = st.columns(3)
            with sch1:
                sc_warp_price = st.number_input(
                    "Warp yarn price (₹/kg)",
                    min_value=0.0,
                    step=0.1,
                    value=450.0,
                    key="wf_scratch_warp_price"
                )
            with sch2:
                sc_weaving_rate = st.number_input(
                    "Weaving charge per pick (₹/pick/m)",
                    min_value=0.0,
                    step=0.01,
                    value=0.16,
                    key="wf_scratch_weaving_rate"
                )
                sc_grey_markup = st.number_input(
                    "Grey markup % (margin on sale)",
                    min_value=0.0,
                    step=0.5,
                    value=8.0,
                    key="wf_scratch_grey_markup"
                )
            with sch3:
                sc_rfd_charge = st.number_input(
                    "RFD charge (₹/m)",
                    min_value=0.0,
                    step=0.1,
                    value=1.7,
                    key="wf_scratch_rfd_charge"
                )
                sc_rfd_short = st.number_input(
                    "RFD shortage (%)",
                    min_value=0.0,
                    step=0.1,
                    value=5.5,
                    key="wf_scratch_rfd_short"
                )
                sc_rfd_markup = st.number_input(
                    "RFD markup % (margin on sale)",
                    min_value=0.0,
                    step=0.5,
                    value=10.0,
                    key="wf_scratch_rfd_markup"
                )

            include_interest_wf_scratch = st.checkbox(
                "Include interest in costing?",
                value=True,
                key="include_interest_wf_scratch"
            )

            # Final calculate button
            scratch_calc_clicked = st.form_submit_button("Calculate (do not save)")

        # ---------- Handle button actions outside the form ----------

        # Add / remove wefts (these just change state and rerun)
        if 'add_weft_clicked' in locals() and add_weft_clicked:
            st.session_state["wf_scratch_num_wefts"] = num_wefts + 1
            st.rerun()

        if 'remove_weft_clicked' in locals() and remove_weft_clicked:
            if num_wefts > 1:
                st.session_state["wf_scratch_num_wefts"] = num_wefts - 1
                st.rerun()

        # Main calculation
        if scratch_calc_clicked:
            errors = []

            # Basic warp validations
            if sc_rs <= 0:
                errors.append("RS must be > 0")
            if sc_warp_denier <= 0:
                errors.append("Warp denier must be > 0")
            if sc_ends_mode == "direct" and sc_ends <= 0:
                errors.append("Ends must be > 0 when entering directly")
            if sc_ends_mode == "calc" and sc_reed <= 0:
                errors.append("Reed must be > 0 when calculating ends")
            if sc_warp_price <= 0:
                errors.append("Warp yarn price must be > 0")

            if sc_grey_markup >= 100 or sc_rfd_markup >= 100:
                errors.append("Markup % must be < 100 (margin on sale)")

            # Weft validations + conversion to actual denier
            active_wefts = []
            for idx, row in enumerate(weft_rows):
                label = f"Weft {idx+1}"
                if row["picks"] <= 0:
                    errors.append(f"{label}: Picks must be > 0")
                if row["price"] <= 0:
                    errors.append(f"{label}: Weft yarn price must be > 0")

                if row["mode"] == "denier":
                    if row["denier"] is None or row["denier"] <= 0:
                        errors.append(f"{label}: Weft denier must be > 0")
                        continue
                    weft_den_val = row["denier"]
                else:
                    if row["count"] is None or row["count"] <= 0:
                        errors.append(f"{label}: Weft count (Ne) must be > 0")
                        continue
                    weft_den_val = 5315.0 / row["count"]

                active_wefts.append(
                    {
                        "picks": float(row["picks"]),
                        "weft_denier": float(weft_den_val),
                        "weft_yarn_price": float(row["price"]),
                    }
                )

            if not active_wefts:
                errors.append("At least one valid weft is required.")

            if errors:
                st.error("Fix these issues:\n- " + "\n- ".join(errors))
            else:
                # Compute ends if needed
                if sc_ends_mode == "calc":
                    sc_ends = sc_reed * sc_rs + sc_borders

                cost = calculate_costing_multi_weft(
                    ends=float(sc_ends),
                    warp_denier=float(sc_warp_denier),
                    rs=float(sc_rs),
                    warp_yarn_price=float(sc_warp_price),
                    weft_list=active_wefts,
                    weaving_rate_per_pick=float(sc_weaving_rate),
                    grey_markup_percent=float(sc_grey_markup),
                    rfd_charge_per_m=float(sc_rfd_charge),
                    rfd_shortage_percent=float(sc_rfd_short),
                    rfd_markup_percent=float(sc_rfd_markup),
                    include_interest=include_interest_wf_scratch,
                )

                warp_weight_100 = cost["warp_weight_100"]
                weft_weight_100 = cost["weft_weight_100"]
                fabric_weight_100 = cost["fabric_weight_100"]
                warp_weight_100_short = warp_weight_100 * 1.09
                fabric_weight_cost_style = warp_weight_100_short + weft_weight_100

                c1, c2 = st.columns(2)
                with c1:
                    st.metric("Grey cost / m (₹)", f"{cost['grey_cost_per_m']:.2f}")
                    st.metric("Grey sale / m (₹)", f"{cost['grey_sale_per_m']:.2f}")
                    st.metric("RFD cost / m (₹)", f"{cost['rfd_cost_per_m']:.2f}")
                    st.metric("RFD sale / m (₹)", f"{cost['rfd_sale_per_m']:.2f}")
                with c2:
                    st.write(f"Fabric weight / 100 m (no shortage): **{fabric_weight_100:.3f} kg**")
                    st.write(
                        "Fabric weight / 100 m (warp with shortage, weft no shortage): "
                        f"**{fabric_weight_cost_style:.3f} kg**"
                    )
                    st.write(f"Warp weight / 100 m (no shortage): {warp_weight_100:.3f} kg")
                    st.write(f"Weft weight / 100 m (no shortage): {weft_weight_100:.3f} kg")

                st.markdown("### Recipe (scratch)")
                st.write(f"Reed: {sc_reed}")
                st.write(f"RS: {sc_rs}")
                st.write(f"Ends: {sc_ends} (mode: {sc_ends_mode})")
                st.write(f"Warp denier: {sc_warp_denier}")
                for idx, row in enumerate(weft_rows):
                    label = f"Weft {idx+1}"
                    if row["mode"] == "denier":
                        st.write(f"{label}: Picks {row['picks']}, Denier {row['denier']}, Price {row['price']} ₹/kg")
                    else:
                        weft_den_val = 5315.0 / row["count"] if row["count"] and row["count"] > 0 else 0
                        st.write(
                            f"{label}: Picks {row['picks']}, Count (Ne) {row['count']}, "
                            f"Denier used {weft_den_val:.2f}, Price {row['price']} ₹/kg"
                        )


# ---------------------------
# Page: Search Qualities
# ---------------------------

# ---------------------------
# Page: Search Qualities
# ---------------------------
elif page == "🔍 Search Qualities":
    st.header("🔍 Search Saved Qualities")

    qualities = list_all_qualities()
    if not qualities:
        st.info("No qualities saved yet.")
    else:
        label_to_id = {f"{q[1]} (ID {q[0]})": q[0] for q in qualities}
        labels = ["-- Select quality --"] + list(label_to_id.keys())

        selected_label = st.selectbox(
            "Select quality (type to search)",
            labels,
            key="search_quality_select"
        )

        if selected_label != "-- Select quality --":
            selected_id = label_to_id[selected_label]
            q = get_quality_by_id(selected_id)

            if q:
                st.markdown(f"### {q['quality_name']}")
                st.caption(f"Created at: {q['created_at']}")

                # SINGLE radio with explicit key to avoid duplicate id
                view_mode = st.radio(
                    "View mode",
                    ["Summary", "Recipe", "Details", "Edit"],
                    horizontal=True,
                    key="quality_view_mode"
                )

                # 🔥 Recompute using latest yarn prices + multi-weft
                cost = compute_dynamic_cost(q)

                warp_weight_100 = cost["warp_weight_100"]
                weft_weight_100 = cost["weft_weight_100"]
                fabric_weight_100 = cost["fabric_weight_100"]
                warp_weight_100_short = warp_weight_100 * 1.09
                fabric_weight_costing_style = warp_weight_100_short + weft_weight_100

                grey_cost_per_m = cost["grey_cost_per_m"]
                grey_sale_per_m = cost["grey_sale_per_m"]
                rfd_cost_per_m = cost["rfd_cost_per_m"]
                rfd_sale_per_m = cost["rfd_sale_per_m"]

                weft_breakdown = cost.get("_weft_breakdown", None)

                # ---------- SUMMARY ----------
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
                        st.write(
                            "Fabric weight / 100 m (warp with shortage, weft no shortage): "
                            f"**{fabric_weight_costing_style:.3f} kg**"
                        )
                        st.write(f"Warp weight / 100 m (no shortage): {warp_weight_100:.3f} kg")
                        st.write(f"Weft weight / 100 m (no shortage): {weft_weight_100:.3f} kg")
                        
                        if weft_breakdown:
                            st.markdown("**Weft-wise weight / 100 m (no shortage)**")
                            for wf in weft_breakdown:
                                st.write(
                                    f"{wf['label']}: Picks {wf['picks']}, "
                                    f"Denier {wf['denier']:.2f}, "
                                    f"Weight {wf['weight_100']:.3f} kg"
                                )

                # ---------- RECIPE ----------
                elif view_mode == "Recipe":
                    st.subheader("Recipe")
                    st.markdown("**Basic construction**")
                    st.write(f"Reed: {q['reed']}")
                    st.write(f"Ends: {q['ends']} (mode: {q['ends_mode']})")
                    st.write(f"RS: {q['rs']}")
                    st.write(f"Warp denier: {q['warp_denier']}")
                    st.write(f"Warp yarn: {q['warp_yarn_name']} @ {q['warp_yarn_price']} ₹/kg")

                    # --- Weft section ---
                    st.markdown("### Weft recipe")

                    # Try multi-weft first
                    multi_wefts = None
                    if q.get("wefts_json"):
                        try:
                            multi_wefts = json.loads(q["wefts_json"])
                        except Exception:
                            multi_wefts = None

                    if multi_wefts:
                        # Show each weft row
                        for i, wf in enumerate(multi_wefts, start=1):
                            p = wf.get("picks", 0)
                            d = wf.get("denier", 0)
                            mode = wf.get("mode", "denier")
                            cnt = wf.get("count", 0)
                            yarn_name = wf.get("yarn_name")
                            price = wf.get("price", 0)

                            st.markdown(f"**Weft {i}**")
                            st.write(f"Picks: {p}")
                            if mode == "count":
                                st.write(f"Count: {cnt} Ne")
                                st.write(f"(Denier used for costing: {d:.2f})")
                            else:
                                st.write(f"Denier: {d:.2f}")
                            st.write(f"Yarn: {yarn_name}")
                            st.write(f"Price: {price} ₹/kg")
                            st.write("---")
                    else:
                        # Old single-weft fallback
                        st.write(f"Picks: {q['picks']}")
                        if q["weft_denier_mode"] == "denier":
                            st.write(f"Weft denier: {q['weft_denier']}")
                        else:
                            st.write(f"Weft count (Ne): {q['weft_count']}")
                            st.write(f"(Calculated weft denier used for costing: {q['weft_denier']})")
                        st.write(f"Weft yarn: {q['weft_yarn_name']} @ {q['weft_yarn_price']} ₹/kg")

                # ---------- DETAILS ----------
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
                        st.write(f"RFD shortage (%): {q['rfd_shortage_percent']} %")
                        st.write(f"RFD markup %: {q['rfd_markup_percent']} %")

                    with col2:
                        st.markdown("**Costs (per 100 m)**")
                        st.write(f"Warp weight: {warp_weight_100:.3f} kg")
                        st.write(f"Weft weight: {weft_weight_100:.3f} kg")
                        st.write(f"Fabric weight: {fabric_weight_100:.3f} kg")
                        st.write(f"Warp cost: {cost['warp_cost_100']:.2f} ₹")
                        st.write(f"Weft cost: {cost['weft_cost_100']:.2f} ₹")
                        st.write(f"Weaving charge: {cost['weaving_charge_100']:.2f} ₹")
                        st.write(f"Interest on yarn: {cost['interest_on_yarn_100']:.2f} ₹")
                        st.write(f"Final grey cost: {cost['final_grey_cost_100']:.2f} ₹")
                        st.write(f"Grey sale: {cost['grey_sale_100']:.2f} ₹")
                        st.write(f"RFD cost: {cost['rfd_cost_100']:.2f} ₹")
                        st.write(f"RFD sale: {cost['rfd_sale_100']:.2f} ₹")
                        
                        st.markdown("**Per meter**")
                        st.write(f"Grey cost / m: {grey_cost_per_m:.2f} ₹/m")
                        st.write(f"Grey sale / m: {grey_sale_per_m:.2f} ₹/m")
                        st.write(f"RFD cost / m: {rfd_cost_per_m:.2f} ₹/m")
                        st.write(f"RFD sale / m: {rfd_sale_per_m:.2f} ₹/m")

                # ---------- EDIT ----------
                elif view_mode == "Edit":
                    st.subheader("Edit Quality (overwrite)")

                    # 🔹 Load existing wefts (multi or single) as base rows
                    base_wefts = []
                    if q.get("wefts_json"):
                        try:
                            base_wefts = json.loads(q["wefts_json"])
                        except Exception:
                            base_wefts = []
                    if not base_wefts:
                        # fallback: single-weft legacy
                        base_wefts = [{
                            "picks": q["picks"],
                            "mode": q["weft_denier_mode"],
                            "denier": q["weft_denier"],
                            "count": q["weft_count"],
                            "yarn_name": q["weft_yarn_name"],
                            "price": q["weft_yarn_price"],
                        }]

                    weft_rows = []  # will be filled inside form

                    with st.form("edit_quality_form"):
                        eq1, eq2, eq3 = st.columns(3)
                        with eq1:
                            new_quality_name = st.text_input("Quality name", value=q["quality_name"])
                            new_ends_mode_label = st.radio(
                                "Ends input mode",
                                ["Enter ends directly", "Calculate from reed, RS, borders"],
                                index=0 if q["ends_mode"] == "direct" else 1,
                                key="edit_ends_mode"
                            )
                            new_ends_mode = "direct" if new_ends_mode_label == "Enter ends directly" else "calc"
                        with eq2:
                            new_rs = st.number_input(
                                "RS (for both warp & weft)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["rs"])
                            )
                            new_reed = st.number_input(
                                "Reed",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["reed"] if q["reed"] else 0.0)
                            )
                            new_borders = st.number_input(
                                "Borders",
                                min_value=0.0,
                                step=1.0,
                                value=float(q["borders"] if q["borders"] else 0.0)
                            )
                        with eq3:
                            new_ends = st.number_input(
                                "Ends",
                                min_value=0.0,
                                step=1.0,
                                value=float(q["ends"])
                            )

                        ew1, ew2 = st.columns(2)
                        with ew1:
                            new_warp_denier = st.number_input(
                                "Warp denier",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["warp_denier"])
                            )
                        with ew2:
                            new_warp_yarn_price = st.number_input(
                                "Warp yarn price per kg (₹)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["warp_yarn_price"])
                            )

                        # 🔹 Multi-weft edit section
                        st.markdown("### Weft (multi-weft)")

                        weft_yarn_names = list_yarn_names("weft")

                        for idx, wf in enumerate(base_wefts):
                            st.markdown(f"**Weft {idx+1}**")
                            c1, c2, c3 = st.columns([1.2, 1.5, 1.5])

                            with c1:
                                picks_val = st.number_input(
                                    "Picks",
                                    min_value=0.0,
                                    step=1.0,
                                    key=f"edit_weft_picks_{selected_id}_{idx}",
                                    value=float(wf.get("picks", 0.0) or 0.0),
                                )

                            with c2:
                                mode_label = st.radio(
                                    "Weft spec",
                                    ["Denier", "Count (Ne)"],
                                    index=0 if wf.get("mode", "denier") == "denier" else 1,
                                    key=f"edit_weft_mode_{selected_id}_{idx}",
                                    horizontal=True,
                                )
                                mode = "denier" if mode_label == "Denier" else "count"

                                denier_val = float(wf.get("denier", 0.0) or 0.0)
                                count_val = float(wf.get("count", 0.0) or 0.0)

                                if mode == "denier":
                                    denier_val = st.number_input(
                                        "Denier",
                                        min_value=0.0,
                                        step=0.1,
                                        key=f"edit_weft_denier_{selected_id}_{idx}",
                                        value=denier_val,
                                    )
                                    count_val = 0.0
                                else:
                                    count_val = st.number_input(
                                        "Count (Ne)",
                                        min_value=0.0,
                                        step=0.1,
                                        key=f"edit_weft_count_{selected_id}_{idx}",
                                        value=count_val,
                                    )
                                    if count_val > 0:
                                        denier_val = 5315.0 / count_val

                            with c3:
                                yarn_options = ["(manual price)"] + weft_yarn_names
                                yarn_name_val = wf.get("yarn_name") or "(manual price)"

                                yarn_name_val = st.selectbox(
                                    "Weft yarn",
                                    yarn_options,
                                    key=f"edit_weft_yarn_{selected_id}_{idx}",
                                    index=yarn_options.index(yarn_name_val) if yarn_name_val in yarn_options else 0,
                                )

                                price_val = float(wf.get("price", 0.0) or 0.0)

                                # 🔥 Auto-fill from yarn table
                                if yarn_name_val != "(manual price)":
                                    latest_price, latest_dnr, latest_cnt = get_latest_yarn_price(yarn_name_val, "weft")
                                    if latest_price is not None:
                                        price_val = latest_price
                                    if mode == "denier":
                                        if latest_dnr is not None and latest_dnr > 0:
                                            denier_val = latest_dnr
                                        elif latest_cnt is not None and latest_cnt > 0:
                                            denier_val = 5315.0 / latest_cnt
                                    else:
                                        if latest_cnt is not None and latest_cnt > 0:
                                            count_val = latest_cnt
                                            denier_val = 5315.0 / latest_cnt
                                        elif latest_dnr is not None and latest_dnr > 0:
                                            denier_val = latest_dnr

                                price_val = st.number_input(
                                    "Price (₹/kg)",
                                    min_value=0.0,
                                    step=0.1,
                                    key=f"edit_weft_price_{selected_id}_{idx}",
                                    value=price_val,
                                )

                            weft_rows.append({
                                "picks": picks_val,
                                "mode": mode,
                                "denier": denier_val,
                                "count": count_val,
                                "price": price_val,
                                "yarn_name": yarn_name_val,
                            })

                        # 🔹 Charges & Markups
                        ec1, ec2, ec3 = st.columns(3)
                        with ec1:
                            new_weaving_rate_per_pick = st.number_input(
                                "Weaving charge per pick (₹/pick/m)",
                                min_value=0.0,
                                step=0.01,
                                value=float(q["weaving_rate_per_pick"])
                            )
                            new_grey_markup_percent = st.number_input(
                                "Grey markup % (margin on sale)",
                                min_value=0.0,
                                step=0.5,
                                value=float(q["grey_markup_percent"])
                            )
                        with ec2:
                            new_rfd_charge_per_m = st.number_input(
                                "RFD charge (₹ per m)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["rfd_charge_per_m"])
                            )
                            new_rfd_shortage_percent = st.number_input(
                                "RFD shortage (%)",
                                min_value=0.0,
                                step=0.1,
                                value=float(q["rfd_shortage_percent"])
                            )
                        with ec3:
                            new_rfd_markup_percent = st.number_input(
                                "RFD markup % (margin on sale)",
                                min_value=0.0,
                                step=0.5,
                                value=float(q["rfd_markup_percent"])
                            )
                            include_interest_edit = st.checkbox(
                                "Include 4% interest on yarn in grey cost",
                                value=True,
                                key="include_interest_edit"
                            )

                        update_btn = st.form_submit_button("Save changes")

                    if update_btn:
                        # basic validation
                        errors = []
                        if new_rs <= 0:
                            errors.append("RS must be > 0")
                        if new_warp_denier <= 0:
                            errors.append("Warp denier must be > 0")
                        if new_ends_mode == "direct" and new_ends <= 0:
                            errors.append("Ends must be > 0 when entering directly")
                        if new_ends_mode == "calc" and new_reed <= 0:
                            errors.append("Reed must be > 0 when calculating ends")
                        if new_grey_markup_percent >= 100 or new_rfd_markup_percent >= 100:
                            errors.append("Markup % must be < 100 (margin on sale)")

                        # weft validations + aggregation
                        valid_wefts = []
                        total_picks = 0.0
                        num_for_den = 0.0
                        num_for_price = 0.0

                        for wf in weft_rows:
                            p = float(wf["picks"] or 0.0)
                            d = float(wf["denier"] or 0.0)
                            price = float(wf["price"] or 0.0)
                            mode = wf["mode"]
                            cnt = float(wf["count"] or 0.0)
                            yarn_name = wf["yarn_name"]

                            label = f"Weft (yarn: {yarn_name})"
                            if p <= 0:
                                errors.append(f"{label}: Picks must be > 0")
                                continue
                            if price <= 0:
                                errors.append(f"{label}: Price must be > 0")
                                continue
                            if d <= 0:
                                errors.append(f"{label}: Denier must be > 0")
                                continue

                            valid_wefts.append({
                                "picks": p,
                                "denier": d,
                                "price": price,
                                "mode": mode,
                                "count": cnt,
                                "yarn_name": yarn_name,
                            })

                            total_picks += p
                            num_for_den += p * d
                            num_for_price += p * d * price

                        if not valid_wefts:
                            errors.append("At least one valid weft is required.")

                        if errors:
                            st.error("Fix these issues:\n- " + "\n- ".join(errors))
                        else:
                            if new_ends_mode == "calc":
                                new_ends = new_reed * new_rs + new_borders

                            eff_weft_denier = num_for_den / total_picks
                            eff_weft_price = num_for_price / num_for_den

                            cost = calculate_costing(
                                ends=float(new_ends),
                                warp_denier=float(new_warp_denier),
                                picks=float(total_picks),
                                weft_denier=float(eff_weft_denier),
                                rs=float(new_rs),
                                warp_yarn_price=float(new_warp_yarn_price),
                                weft_yarn_price=float(eff_weft_price),
                                weaving_rate_per_pick=float(new_weaving_rate_per_pick),
                                grey_markup_percent=float(new_grey_markup_percent),
                                rfd_charge_per_m=float(new_rfd_charge_per_m),
                                rfd_shortage_percent=float(new_rfd_shortage_percent),
                                rfd_markup_percent=float(new_rfd_markup_percent),
                                include_interest=include_interest_edit,
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

                                # aggregated weft
                                "picks": float(total_picks),
                                "weft_rs": float(new_rs),
                                "weft_denier_mode": "denier",
                                "weft_denier": float(eff_weft_denier),
                                "weft_count": None,
                                "weft_yarn_name": None,
                                "weft_yarn_price": float(eff_weft_price),

                                "weaving_rate_per_pick": float(new_weaving_rate_per_pick),
                                "grey_markup_percent": float(new_grey_markup_percent),
                                "rfd_charge_per_m": float(new_rfd_charge_per_m),
                                "rfd_shortage_percent": float(new_rfd_shortage_percent),
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

                                "wefts_json": json.dumps(valid_wefts),
                            }

                            update_quality(selected_id, upd)
                            st.success("Quality updated (overwritten).")

                    # 🔥 Delete button (outside the form)
                    if st.button(
                        "🗑 Delete this quality",
                        key=f"delete_quality_{selected_id}"
                    ):
                        delete_quality(selected_id)
                        st.success(f"Quality '{q['quality_name']}' deleted.")

# ---------------------------
# Page: Pricing Sheet
# ---------------------------
elif page == "📄 Pricing Sheet":
    st.header("📄 Pricing Sheet")

    qualities = list_all_qualities()
    if not qualities:
        st.info("No qualities saved yet.")
    else:
        import pandas as pd

        rows = []
        for q_id, q_name, created_at in qualities:
            q = get_quality_by_id(q_id)
            if not q:
                continue

            # 🔥 dynamic recalc using latest yarn prices + multi-weft
            cost = compute_dynamic_cost(q)

            warp_w_100 = cost["warp_weight_100"]
            weft_w_100 = cost["weft_weight_100"]

            # your preferred single weight column:
            fabric_weight_cost = warp_w_100 * 1.09 + weft_w_100

            rows.append({
                "Quality": q_name,
                "Weight (warp+shortage, weft no shortage, kg/100m)": round(fabric_weight_cost, 3),
                "Grey Sale (₹/m)": round(cost["grey_sale_per_m"], 2),
                "RFD Sale (₹/m)": round(cost["rfd_sale_per_m"], 2),
            })

        if not rows:
            st.info("No qualities found.")
        else:
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True)

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download as CSV",
                data=csv,
                file_name="pricing_sheet.csv",
                mime="text/csv"
            )