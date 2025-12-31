import streamlit as st
import requests
import pandas as pd
import csv
import io

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="Paycode Events",
    page_icon="🧾",
    layout="wide"
)

# ================= DEFAULT CONFIG =================
DEFAULT_AUTH_URL = "https://saas-beeforce.labour.tech/authorization-server/oauth/token"
DEFAULT_BASE_URL = "https://saas-beeforce.labour.tech/resource-server/api/paycode_events"
DEFAULT_START_DATE = "2026-01-01"

CLIENT_AUTH = st.secrets["CLIENT_AUTH"]

# ================= SESSION STATE =================
def init(key, value):
    if key not in st.session_state:
        st.session_state[key] = value

init("token", None)
init("username", None)
init("final_body", [])
init("AUTH_URL", DEFAULT_AUTH_URL)
init("BASE_URL", DEFAULT_BASE_URL)
init("START_DATE", DEFAULT_START_DATE)

# ================= DATE PARSER (FIX) =================
def parse_date(value):
    if value is None or str(value).strip() == "":
        return None

    if isinstance(value, pd.Timestamp):
        return value.day, value.month, value.year

    val = str(value).strip()

    for sep in ["-", "/"]:
        parts = val.split(sep)
        if len(parts) == 3:
            if len(parts[0]) == 4:  # YYYY-MM-DD
                y, m, d = parts
            else:                   # DD-MM-YYYY
                d, m, y = parts

            if d.isdigit() and m.isdigit() and y.isdigit():
                return int(d), int(m), int(y)
    return None

# ================= SIDEBAR =================
with st.sidebar:
    st.title("⚙️ Configuration")
    st.text_input("Auth URL", key="AUTH_URL")
    st.text_input("Base URL", key="BASE_URL")
    st.text_input("Default Start Date", key="START_DATE")

    if st.session_state.token:
        st.success(f"👤 {st.session_state.username}")
        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

# ================= HEADER =================
st.title("🧾 Paycode Event Configuration")

# ================= LOGIN =================
if not st.session_state.token:
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Generate Token"):
        r = requests.post(
            st.session_state.AUTH_URL,
            data={"username": username, "password": password, "grant_type": "password"},
            headers={"Authorization": CLIENT_AUTH, "Content-Type": "application/x-www-form-urlencoded"}
        )
        if r.status_code != 200:
            st.error("Invalid credentials")
        else:
            st.session_state.token = r.json()["access_token"]
            st.session_state.username = username
            st.rerun()
    st.stop()

headers_auth = {
    "Authorization": f"Bearer {st.session_state.token}",
    "Content-Type": "application/json"
}

# ================= UPLOAD =================
st.subheader("📤 Upload Paycode Events")

uploaded_file = st.file_uploader("Upload CSV / Excel", ["csv", "xlsx", "xls"])

if uploaded_file:
    store = {}

    df = pd.read_excel(uploaded_file) if not uploaded_file.name.endswith(".csv") \
        else pd.read_csv(uploaded_file)

    df = df.fillna("")

    for _, row in df.iterrows():
        raw_id = str(row.get("id", "")).strip()
        name = str(row.get("Paycode Event Name", "")).strip()
        paycode_id = str(row.get("paycode_id", "")).strip()
        holiday_name = str(row.get("holiday_name", "")).strip()
        date_parts = parse_date(row.get("holiday_date(DD-MM-YYYY)"))

        if not name or not holiday_name or not paycode_id.isdigit() or not date_parts:
            continue

        d, m, y = date_parts
        key = raw_id if raw_id.isdigit() else name

        if key not in store:
            store[key] = {
                "name": name,
                "description": name,
                "paycode": {"id": int(paycode_id)},
                "schedules": []
            }
            if raw_id.isdigit():
                store[key]["id"] = int(raw_id)

        store[key]["schedules"].append({
            "name": holiday_name,
            "startDate": st.session_state.START_DATE,
            "repeatDay": d,
            "repeatMonth": m,
            "repeatYear": y,
            "repeatWeek": row.get("repeatWeek", "*") or "*",
            "repeatWeekday": row.get("repeatWeekday", "*") or "*"
        })

    st.session_state.final_body = list(store.values())
    st.success(f"Loaded {len(store)} Paycode Events")

# ================= CREATE / UPDATE WITH STATUS =================
st.subheader("🚀 Create / Update Paycode Events")

if st.button("Submit"):
    results = []

    for payload in st.session_state.final_body:
        is_update = "id" in payload

        if is_update:
            r = requests.put(
                f"{st.session_state.BASE_URL}/{payload['id']}",
                headers=headers_auth,
                json=payload
            )
        else:
            r = requests.post(
                st.session_state.BASE_URL,
                headers=headers_auth,
                json=payload
            )

        results.append({
            "Paycode Event": payload["name"],
            "Action": "Update" if is_update else "Create",
            "Status": "Success" if r.status_code in (200, 201) else "Failed",
            "HTTP Status": r.status_code
        })

    st.dataframe(pd.DataFrame(results), use_container_width=True)

# ================= DOWNLOAD =================
st.subheader("⬇️ Download Existing Paycode Events")

if st.button("Download"):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)
    rows = []

    for e in r.json():
        for s in e.get("schedules", []):
            if all(str(s.get(k, "")).isdigit() for k in ["repeatDay", "repeatMonth", "repeatYear"]):
                date = f"{s['repeatDay']:02d}-{s['repeatMonth']:02d}-{s['repeatYear']}"
            else:
                date = ""

            rows.append({
                "id": e.get("id"),
                "name": e.get("name"),
                "paycode_id": e.get("paycode", {}).get("id"),
                "holiday_name": s.get("name"),
                "holiday_date(DD-MM-YYYY)": date,
                "repeatWeek": s.get("repeatWeek", "*"),
                "repeatWeekday": s.get("repeatWeekday", "*")
            })

    st.download_button(
        "⬇️ Download CSV",
        pd.DataFrame(rows).to_csv(index=False),
        "paycode_events_export.csv",
        "text/csv"
    )
