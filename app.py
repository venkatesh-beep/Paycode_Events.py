import streamlit as st
import requests
import pandas as pd
import csv
import io
import streamlit.components.v1 as components

# ================= CONFIG =================
DEFAULT_AUTH_URL = "https://saas-beeforce.labour.tech/authorization-server/oauth/token"
DEFAULT_BASE_URL = "https://saas-beeforce.labour.tech/resource-server/api/paycode_events"
DEFAULT_START_DATE = "2026-01-01"

CLIENT_AUTH = st.secrets["CLIENT_AUTH"]

# ================= SESSION =================
for k, v in {
    "token": None,
    "username": None,
    "AUTH_URL": DEFAULT_AUTH_URL,
    "BASE_URL": DEFAULT_BASE_URL,
    "START_DATE": DEFAULT_START_DATE,
    "final_body": []
}.items():
    st.session_state.setdefault(k, v)

# ================= PAGE =================
st.set_page_config(page_title="Paycode Events Portal", layout="wide")

# ================= EMBED UI (UNCHANGED) =================
components.html(
"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>Paycode Events Portal</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* { box-sizing: border-box; font-family: Inter, sans-serif; }
body { margin:0; background:#f8fafc; }
iframe { border:none; }
</style>
</head>
<body></body>
</html>
""",
height=0
)

# ================= LOGIN =================
if not st.session_state.token:
    st.header("🔐 Login for Paycode Events Configuration")

    st.info("Enter Credentials")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        payload = {
            "username": username,
            "password": password,
            "grant_type": "password"
        }
        headers = {
            "Authorization": CLIENT_AUTH,
            "Content-Type": "application/x-www-form-urlencoded"
        }
        r = requests.post(st.session_state.AUTH_URL, data=payload, headers=headers)

        if r.status_code != 200:
            st.error("❌ Entered wrong credentials")
        else:
            st.session_state.token = r.json()["access_token"]
            st.session_state.username = username
            st.success("✅ Login successful")
            st.rerun()

    st.stop()

# ================= AUTH =================
headers_auth = {
    "Authorization": f"Bearer {st.session_state.token}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ================= HEADER =================
st.success(f"👤 Logged in as **{st.session_state.username}**")

with st.expander("⚙️ API Configuration", expanded=False):
    st.session_state.AUTH_URL = st.text_input("Auth URL", st.session_state.AUTH_URL)
    st.session_state.BASE_URL = st.text_input("Base URL", st.session_state.BASE_URL)
    st.session_state.START_DATE = st.text_input(
        "Start Date of the Event (YYYY-MM-DD)",
        st.session_state.START_DATE
    )

if st.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

st.divider()

# ================= INFO =================
st.info(
    "**To create a Paycode Event, do not enter the ID.**  \n"
    "**To update an existing Paycode Event, enter the ID.**"
)

# ================= UPLOAD =================
st.header("⬆️ Upload Paycode Events")

template_df = pd.DataFrame(columns=[
    "id",
    "Paycode Event Name",
    "Description",
    "paycode_id",
    "holiday_name",
    "holiday_date(DD-MM-YYYY)",
    "repeatWeek",
    "repeatWeekday"
])

st.download_button(
    "⬇️ Download Upload Template",
    template_df.to_csv(index=False),
    "paycode_events_template.csv"
)

uploaded = st.file_uploader("Upload CSV / Excel", ["csv", "xlsx", "xls"])

if uploaded:
    store = {}
    rows = (
        csv.DictReader(io.StringIO(uploaded.getvalue().decode()))
        if uploaded.name.endswith(".csv")
        else pd.read_excel(uploaded).fillna("").to_dict("records")
    )

    for r in rows:
        name = r.get("Paycode Event Name", "").strip()
        desc = r.get("Description", "").strip() or name
        if not name:
            continue

        uid = r.get("id", "").strip()
        key = uid or name

        store.setdefault(key, {
            **({"id": int(uid)} if uid else {}),
            "name": name,
            "description": desc,
            "paycode": {"id": int(r["paycode_id"])},
            "schedules": []
        })

        d, m, y = r["holiday_date(DD-MM-YYYY)"].split("-")
        store[key]["schedules"].append({
            "name": r["holiday_name"],
            "startDate": st.session_state.START_DATE,
            "repeatDay": int(d),
            "repeatMonth": int(m),
            "repeatYear": int(y),
            "repeatWeek": r.get("repeatWeek", "*") or "*",
            "repeatWeekday": r.get("repeatWeekday", "*") or "*"
        })

    st.session_state.final_body = list(store.values())
    st.success(f"Processed {len(st.session_state.final_body)} Paycode Events")

# ================= SUBMIT =================
st.header("✏️ Create / Update Paycode Events")

if st.button("Submit"):
    for p in st.session_state.final_body:
        if "id" in p:
            requests.put(f"{st.session_state.BASE_URL}/{p['id']}", headers=headers_auth, json=p)
        else:
            requests.post(st.session_state.BASE_URL, headers=headers_auth, json=p)
    st.success("Operation completed")

# ================= DELETE =================
st.header("🗑️ Delete Paycode Events")

ids = st.text_input("Enter IDs (comma separated)")
if st.button("Delete"):
    for i in ids.split(","):
        if i.strip().isdigit():
            requests.delete(f"{st.session_state.BASE_URL}/{i.strip()}", headers=headers_auth)
            st.write(f"Deleted {i.strip()}")

# ================= FETCH =================
st.header("⬇️ Download Existing Paycode Events")

if st.button("Fetch & Download"):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)
    rows = []
    for e in r.json():
        for s in e.get("schedules", []):
            rows.append({
                "id": e["id"],
                "name": e["name"],
                "description": e["description"],
                "paycode_id": e["paycode"]["id"],
                "holiday_name": s["name"],
                "holiday_date(DD-MM-YYYY)": f"{s['repeatDay']:02d}-{s['repeatMonth']:02d}-{s['repeatYear']}"
            })
    df = pd.DataFrame(rows)
    st.download_button("Download CSV", df.to_csv(index=False), "paycode_events_export.csv")
