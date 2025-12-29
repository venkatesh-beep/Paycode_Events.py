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
if "token" not in st.session_state:
    st.session_state.token = None

if "username" not in st.session_state:
    st.session_state.username = None

if "final_body" not in st.session_state:
    st.session_state.final_body = []

if "show_settings" not in st.session_state:
    st.session_state.show_settings = False

if "AUTH_URL" not in st.session_state:
    st.session_state.AUTH_URL = DEFAULT_AUTH_URL

if "BASE_URL" not in st.session_state:
    st.session_state.BASE_URL = DEFAULT_BASE_URL

if "START_DATE" not in st.session_state:
    st.session_state.START_DATE = DEFAULT_START_DATE

# ================= PAGE CONFIG =================
st.set_page_config(
    page_title="Paycode Events",
    layout="wide"
)

# ================= TOP BAR =================
col1, col2 = st.columns([0.9, 0.1])

with col1:
    st.title("🧾 Paycode Event Configuration")

with col2:
    if st.button("⚙️", help="Settings"):
        st.session_state.show_settings = not st.session_state.show_settings

# ================= SETTINGS PANEL =================
if st.session_state.show_settings:
    st.markdown("### ⚙️ API Configuration")
    st.session_state.AUTH_URL = st.text_input("Auth URL", st.session_state.AUTH_URL)
    st.session_state.BASE_URL = st.text_input("Base URL", st.session_state.BASE_URL)
    st.session_state.START_DATE = st.text_input(
        "Start Date of the Event (YYYY-MM-DD)",
        st.session_state.START_DATE
    )
    st.divider()

# ================= LOGIN =================
if not st.session_state.token:
    st.header("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Generate Token"):
        try:
            payload = {
                "username": username,
                "password": password,
                "grant_type": "password"
            }

            headers = {
                "Authorization": CLIENT_AUTH,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            r = requests.post(
                st.session_state.AUTH_URL,
                data=payload,
                headers=headers
            )

            if r.status_code != 200:
                st.error("❌ Entered wrong credentials")
            else:
                st.session_state.token = r.json()["access_token"]
                st.session_state.username = username
                st.success("✅ Login successful (token valid for 30 minutes)")
                st.rerun()

        except Exception:
            st.error("❌ Entered wrong credentials")

    st.stop()

# ================= AUTH HEADER =================
headers_auth = {
    "Authorization": f"Bearer {st.session_state.token}",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json"
}

# ================= USER INFO =================
st.success(f"👤 Logged in as **{st.session_state.username}**")

if st.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

st.divider()

# ================= INSTRUCTIONS =================
st.info(
    "**To create a Paycode Event, do not enter the ID.**\n\n"
    "**To update an existing Paycode Event, enter the ID.**"
)

# ================= UPLOAD SECTION =================
st.header("📤 Upload Paycode Events File")

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
    file_name="paycode_events_template.csv",
    mime="text/csv"
)

uploaded_file = st.file_uploader(
    "Upload CSV or Excel file",
    type=["csv", "xlsx", "xls"]
)

if uploaded_file:
    store = {}

    if uploaded_file.name.endswith(".csv"):
        reader = csv.DictReader(
            io.StringIO(uploaded_file.getvalue().decode("utf-8"))
        )
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
        repeat_week = str(row.get("repeatWeek", "")).strip() or "*"
        repeat_weekday = str(row.get("repeatWeekday", "")).strip() or "*"

        if not name or not holiday_name or not holiday_date:
            continue

        day, month, year = holiday_date.split("-")

        unique_key = raw_id if raw_id else name

        if unique_key not in store:
            base = {
                "name": name,
                "description": description,
                "paycode": {"id": paycode_id},
                "schedules": []
            }
            if raw_id:
                base["id"] = int(raw_id)

            store[unique_key] = base

        store[unique_key]["schedules"].append({
            "name": holiday_name,
            "startDate": st.session_state.START_DATE,
            "repeatDay": int(day),
            "repeatMonth": int(month),
            "repeatYear": int(year),
            "repeatWeek": repeat_week,
            "repeatWeekday": repeat_weekday
        })

    st.session_state.final_body = list(store.values())
    st.success(f"✅ File processed. Total Paycode Events: {len(st.session_state.final_body)}")

# ================= CREATE / UPDATE =================
st.header("🚀 Create / Update Paycode Events")

if st.button("Submit Paycode Events"):
    success = 0
    failed = 0

    for payload in st.session_state.final_body:
        try:
            if payload.get("id"):
                r = requests.put(
                    f"{st.session_state.BASE_URL}/{payload['id']}",
                    headers=headers_auth,
                    json=payload
                )
                if r.status_code in (200, 201):
                    success += 1
                    st.write(f"✅ Updated ID {payload['id']}")
                else:
                    failed += 1
            else:
                r = requests.post(
                    st.session_state.BASE_URL,
                    headers=headers_auth,
                    json=payload
                )
                if r.status_code in (200, 201):
                    success += 1
                    st.write(f"✅ Created ID {r.json().get('id')}")
                else:
                    failed += 1
        except Exception:
            failed += 1

    st.info(f"Summary → Success: {success}, Failed: {failed}")

# ================= DELETE =================
st.header("🗑️ Delete Paycode Events")

ids_input = st.text_input("Enter Paycode Event IDs (comma-separated)")

if st.button("Delete Paycode Events"):
    ids = [i.strip() for i in ids_input.split(",") if i.strip().isdigit()]

    for pid in ids:
        r = requests.delete(
            f"{st.session_state.BASE_URL}/{pid}",
            headers=headers_auth
        )
        if r.status_code in (200, 204):
            st.write(f"✅ Paycode Event deleted {pid}")
        else:
            st.write(f"❌ Failed to delete {pid}")

# ================= FETCH & DOWNLOAD =================
st.header("⬇️ Download Existing Paycode Events")

if st.button("Download"):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)

    rows = []
    for event in r.json():
        for sch in event.get("schedules", []):
            try:
                date = f"{int(sch['repeatDay']):02d}-{int(sch['repeatMonth']):02d}-{int(sch['repeatYear'])}"
            except Exception:
                date = ""

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
        "⬇️ Download CSV",
        df.to_csv(index=False),
        file_name="paycode_events_export.csv",
        mime="text/csv"
    )
