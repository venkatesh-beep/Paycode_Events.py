import streamlit as st
import requests
import pandas as pd
import csv
import io

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
init("show_settings", False)
init("AUTH_URL", DEFAULT_AUTH_URL)
init("BASE_URL", DEFAULT_BASE_URL)
init("START_DATE", DEFAULT_START_DATE)

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Paycode Events", layout="wide", page_icon="🧾")

# ================= GLOBAL STYLES =================
st.markdown("""
<style>
.main { background-color: #f4f6fb; }

.tile {
    background: white;
    padding: 22px 26px;
    border-radius: 14px;
    margin-bottom: 24px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.06);
}

.tile-title {
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 12px;
}

.stButton > button {
    border-radius: 10px;
    height: 44px;
    font-weight: 600;
}

.btn-primary > button { background:#2563eb; color:white; }
.btn-success > button { background:#16a34a; color:white; }
.btn-danger > button  { background:#dc2626; color:white; }
.btn-warning > button { background:#f59e0b; color:black; }
</style>
""", unsafe_allow_html=True)

# ================= TOP BAR =================
col1, col2 = st.columns([0.9, 0.1])
with col1:
    st.title("🧾 Paycode Event Configuration")
with col2:
    if st.button("⚙️"):
        st.session_state.show_settings = not st.session_state.show_settings

# ================= SETTINGS TILE =================
if st.session_state.show_settings:
    st.markdown('<div class="tile">', unsafe_allow_html=True)
    st.markdown('<div class="tile-title">⚙️ API Configuration</div>', unsafe_allow_html=True)

    st.session_state.AUTH_URL = st.text_input("Auth URL", st.session_state.AUTH_URL)
    st.session_state.BASE_URL = st.text_input("Base URL", st.session_state.BASE_URL)
    st.session_state.START_DATE = st.text_input("Start Date (YYYY-MM-DD)", st.session_state.START_DATE)

    st.markdown('</div>', unsafe_allow_html=True)

# ================= LOGIN TILE =================
if not st.session_state.token:
    st.markdown('<div class="tile">', unsafe_allow_html=True)
    st.markdown('<div class="tile-title">🔐 Login</div>', unsafe_allow_html=True)

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    st.markdown('<div class="btn-primary">', unsafe_allow_html=True)
    if st.button("Generate Token"):
        payload = {
            "username": username,
            "password": password,
            "grant_type": "password"
        }
        headers = {
            "Authorization": CLIENT_AUTH,
            "Content-Type": "application/x-www-form-urlencoded"
        }

        try:
            r = requests.post(st.session_state.AUTH_URL, data=payload, headers=headers)
            if r.status_code == 200:
                st.session_state.token = r.json()["access_token"]
                st.session_state.username = username
                st.success("✅ Login successful")
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
        except Exception:
            st.error("❌ Authentication failed")

    st.markdown('</div></div>', unsafe_allow_html=True)
    st.stop()

# ================= AUTH HEADER =================
headers_auth = {
    "Authorization": f"Bearer {st.session_state.token}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ================= USER INFO TILE =================
st.markdown('<div class="tile">', unsafe_allow_html=True)
st.success(f"👤 Logged in as **{st.session_state.username}**")

st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
if st.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.markdown('</div></div>', unsafe_allow_html=True)

# ================= INSTRUCTIONS TILE =================
st.markdown('<div class="tile">', unsafe_allow_html=True)
st.info(
    "📝 **Create:** Leave ID empty\n\n"
    "✏️ **Update:** Provide ID"
)
st.markdown('</div>', unsafe_allow_html=True)

# ================= UPLOAD TILE =================
st.markdown('<div class="tile">', unsafe_allow_html=True)
st.markdown('<div class="tile-title">📤 Upload Paycode Events</div>', unsafe_allow_html=True)

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

uploaded_file = st.file_uploader("Upload CSV / Excel", type=["csv", "xlsx"])

if uploaded_file:
    store = {}

    if uploaded_file.name.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(uploaded_file.getvalue().decode()))
        rows = list(reader)
    else:
        rows = pd.read_excel(uploaded_file).fillna("").to_dict("records")

    for row in rows:
        raw_id = str(row.get("id", "")).strip()
        name = str(row.get("Paycode Event Name", "")).strip()
        description = str(row.get("Description", "")).strip() or name
        paycode_id = int(row.get("paycode_id"))
        holiday_name = str(row.get("holiday_name", "")).strip()
        holiday_date = str(row.get("holiday_date(DD-MM-YYYY)", "")).strip()

        if not name or not holiday_name or not holiday_date:
            continue

        day, month, year = holiday_date.split("-")
        key = raw_id if raw_id else name

        if key not in store:
            store[key] = {
                "name": name,
                "description": description,
                "paycode": {"id": paycode_id},
                "schedules": []
            }
            if raw_id:
                store[key]["id"] = int(raw_id)

        store[key]["schedules"].append({
            "name": holiday_name,
            "startDate": st.session_state.START_DATE,
            "repeatDay": int(day),
            "repeatMonth": int(month),
            "repeatYear": int(year),
            "repeatWeek": "*",
            "repeatWeekday": "*"
        })

    st.session_state.final_body = list(store.values())
    st.success(f"✅ Processed {len(store)} Paycode Events")

st.markdown('</div>', unsafe_allow_html=True)

# ================= CREATE / UPDATE TILE =================
st.markdown('<div class="tile">', unsafe_allow_html=True)
st.markdown('<div class="tile-title">🚀 Create / Update Paycode Events</div>', unsafe_allow_html=True)

st.markdown('<div class="btn-success">', unsafe_allow_html=True)
if st.button("Submit Paycode Events"):
    success = failed = 0
    for payload in st.session_state.final_body:
        if payload.get("id"):
            r = requests.put(f"{st.session_state.BASE_URL}/{payload['id']}", headers=headers_auth, json=payload)
        else:
            r = requests.post(st.session_state.BASE_URL, headers=headers_auth, json=payload)

        if r.status_code in (200, 201):
            success += 1
        else:
            failed += 1

    st.info(f"✅ Success: {success} | ❌ Failed: {failed}")

st.markdown('</div></div>', unsafe_allow_html=True)

# ================= DELETE TILE =================
st.markdown('<div class="tile">', unsafe_allow_html=True)
st.markdown('<div class="tile-title">🗑️ Delete Paycode Events</div>', unsafe_allow_html=True)

ids_input = st.text_input("Enter Paycode Event IDs (comma-separated)")

st.markdown('<div class="btn-danger">', unsafe_allow_html=True)
if st.button("Delete Paycode Events"):
    for pid in [i.strip() for i in ids_input.split(",") if i.isdigit()]:
        r = requests.delete(f"{st.session_state.BASE_URL}/{pid}", headers=headers_auth)
        st.write("✅ Deleted" if r.status_code in (200, 204) else "❌ Failed", pid)

st.markdown('</div></div>', unsafe_allow_html=True)

# ================= DOWNLOAD TILE =================
st.markdown('<div class="tile">', unsafe_allow_html=True)
st.markdown('<div class="tile-title">⬇️ Download Existing Paycode Events</div>', unsafe_allow_html=True)

st.markdown('<div class="btn-warning">', unsafe_allow_html=True)
if st.button("Fetch & Download"):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)
    rows = []

    for event in r.json():
        for sch in event.get("schedules", []):
            rows.append({
                "id": event.get("id"),
                "name": event.get("name"),
                "paycode_id": event.get("paycode", {}).get("id"),
                "holiday_name": sch.get("name"),
                "holiday_date": f"{sch.get('repeatDay'):02d}-{sch.get('repeatMonth'):02d}-{sch.get('repeatYear')}"
            })

    df = pd.DataFrame(rows)
    st.download_button(
        "⬇️ Download CSV",
        df.to_csv(index=False),
        "paycode_events_export.csv"
    )

st.markdown('</div></div>', unsafe_allow_html=True)
