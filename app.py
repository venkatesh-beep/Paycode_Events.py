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

# ================= SIDEBAR =================
with st.sidebar:
    st.title("⚙️ Settings")

    st.text_input("Auth URL", key="AUTH_URL")
    st.text_input("Base URL", key="BASE_URL")
    st.text_input("Default Start Date", key="START_DATE")

    st.divider()

    if st.session_state.token:
        st.success(f"Logged in as\n**{st.session_state.username}**")
        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

# ================= HEADER =================
st.title("🧾 Paycode Event Configuration")
st.caption("Create, Update, Delete & Download Paycode Events")

# ================= LOGIN =================
if not st.session_state.token:
    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

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

        r = requests.post(st.session_state.AUTH_URL, data=payload, headers=headers)

        if r.status_code != 200:
            st.error("❌ Invalid credentials")
        else:
            st.session_state.token = r.json()["access_token"]
            st.session_state.username = username
            st.success("✅ Login successful")
            st.rerun()

    st.stop()

# ================= AUTH HEADER =================
headers_auth = {
    "Authorization": f"Bearer {st.session_state.token}",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json"
}

# ================= INFO =================
st.info(
    "• **Create** → Leave `id` empty\n"
    "• **Update** → Provide `id`"
)

# ================= UPLOAD =================
st.subheader("📤 Upload Paycode Events")

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
    "⬇️ Download Template",
    template_df.to_csv(index=False),
    "paycode_events_template.csv",
    "text/csv"
)

uploaded_file = st.file_uploader("Upload CSV / Excel", ["csv", "xlsx", "xls"])

if uploaded_file:
    store = {}

    if uploaded_file.name.endswith(".csv"):
        reader = csv.DictReader(io.StringIO(uploaded_file.getvalue().decode("utf-8")))
        rows = list(reader)
    else:
        df = pd.read_excel(uploaded_file)
        rows = df.fillna("").to_dict(orient="records")

    for row in rows:
        raw_id = str(row.get("id", "")).strip()
        name = str(row.get("Paycode Event Name", "")).strip()
        description = str(row.get("Description", "")).strip() or name
        paycode_id = int(row.get("paycode_id"))
        holiday_name = str(row.get("holiday_name", "")).strip()
        holiday_date = str(row.get("holiday_date(DD-MM-YYYY)", "")).strip()

        if not name or not holiday_name or not holiday_date:
            continue

        d, m, y = holiday_date.split("-")
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
            "repeatDay": int(d),
            "repeatMonth": int(m),
            "repeatYear": int(y),
            "repeatWeek": "*",
            "repeatWeekday": "*"
        })

    st.session_state.final_body = list(store.values())
    st.success(f"✅ Loaded {len(store)} Paycode Events")

# ================= SUBMIT =================
st.subheader("🚀 Create / Update")

if st.button("Submit Paycode Events"):
    ok, fail = 0, 0

    for payload in st.session_state.final_body:
        if payload.get("id"):
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

        if r.status_code in (200, 201):
            ok += 1
        else:
            fail += 1

    st.success(f"✅ Success: {ok}")
    if fail:
        st.error(f"❌ Failed: {fail}")

# ================= DELETE =================
st.subheader("🗑️ Delete Paycode Events")

ids_input = st.text_input("IDs (comma-separated)")

if st.button("Delete"):
    for pid in [i.strip() for i in ids_input.split(",") if i.isdigit()]:
        r = requests.delete(f"{st.session_state.BASE_URL}/{pid}", headers=headers_auth)
        if r.status_code in (200, 204):
            st.success(f"Deleted {pid}")
        else:
            st.error(f"Failed {pid}")

# ================= AUTO DOWNLOAD =================
st.subheader("⬇️ Download Existing Paycode Events")

if st.button("Download Existing Paycode Events"):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)

    if r.status_code != 200:
        st.error("❌ Failed to fetch")
    else:
        rows = []

        for event in r.json():
            for sch in event.get("schedules", []):
                date = f"{sch.get('repeatDay', ''):02d}-{sch.get('repeatMonth', ''):02d}-{sch.get('repeatYear', '')}"
                rows.append({
                    "id": event.get("id"),
                    "name": event.get("name"),
                    "description": event.get("description"),
                    "paycode_id": event.get("paycode", {}).get("id"),
                    "holiday_name": sch.get("name"),
                    "holiday_date(DD-MM-YYYY)": date
                })

        df = pd.DataFrame(rows)

        st.download_button(
            "⬇️ Download CSV Now",
            df.to_csv(index=False),
            "paycode_events_export.csv",
            "text/csv"
        )
