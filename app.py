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

# ================= DATE PARSER (NO FUNCTIONAL CHANGE, ONLY SAFETY) =================
def parse_date(value):
    if value is None or str(value).strip() == "":
        return None

    if isinstance(value, pd.Timestamp):
        return value.day, value.month, value.year

    val = str(value).strip()

    for sep in ["-", "/"]:
        parts = val.split(sep)
        if len(parts) == 3:
            if len(parts[0]) == 4:   # YYYY-MM-DD
                y, m, d = parts
            else:                    # DD-MM-YYYY
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

    st.divider()

    if st.session_state.token:
        st.success(f"👤 {st.session_state.username}")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# ================= HEADER =================
st.title("🧾 Paycode Event Configuration")
st.caption("Create • Update • Delete • Download Paycode Events")

# ================= LOGIN =================
if not st.session_state.token:
    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Generate Token", use_container_width=True):
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
    "• **Update** → Provide numeric `id` in all rows\n"
    "• **repeatWeek / repeatWeekday** → Defaults to `*` if blank"
)

# ================= UPLOAD SECTION =================
st.subheader("📤 Upload Paycode Events")

uploaded_file = st.file_uploader("Upload CSV or Excel file", ["csv", "xlsx", "xls"])

if uploaded_file:
    store = {}

    if uploaded_file.name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    df = df.fillna("")

    for _, row in df.iterrows():
        raw_id = str(row.get("id", "")).strip()
        name = str(row.get("Paycode Event Name", "")).strip()
        description = str(row.get("Description", "")).strip() or name
        paycode_id = str(row.get("paycode_id", "")).strip()
        holiday_name = str(row.get("holiday_name", "")).strip()

        repeat_week = str(row.get("repeatWeek", "")).strip() or "*"
        repeat_weekday = str(row.get("repeatWeekday", "")).strip() or "*"

        date_parts = parse_date(row.get("holiday_date(DD-MM-YYYY)"))

        if not name or not holiday_name or not paycode_id.isdigit() or not date_parts:
            continue

        d, m, y = date_parts
        key = raw_id if raw_id.isdigit() else name

        if key not in store:
            store[key] = {
                "name": name,
                "description": description,
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
            "repeatWeek": repeat_week,
            "repeatWeekday": repeat_weekday
        })

    st.session_state.final_body = list(store.values())
    st.success(f"✅ Loaded {len(store)} Paycode Events")

# ================= CREATE / UPDATE (STATUS SHOWN – NO LOGIC CHANGE) =================
st.subheader("🚀 Create / Update Paycode Events")

if st.button("Submit Paycode Events", use_container_width=True):

    if not st.session_state.final_body:
        st.warning("No Paycode Events to submit")
    else:
        results = []

        for payload in st.session_state.final_body:
            is_update = bool(payload.get("id"))

            try:
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
                    "Paycode Event": payload.get("name"),
                    "Action": "Update" if is_update else "Create",
                    "Status": "Success" if r.status_code in (200, 201) else "Failed",
                    "HTTP Status": r.status_code,
                    "ID": payload.get("id") or (r.json().get("id") if r.status_code in (200, 201) else "")
                })

            except Exception:
                results.append({
                    "Paycode Event": payload.get("name"),
                    "Action": "Update" if is_update else "Create",
                    "Status": "Error",
                    "HTTP Status": "",
                    "ID": ""
                })

        st.dataframe(pd.DataFrame(results), use_container_width=True)

# ================= DOWNLOAD EXISTING =================
st.subheader("⬇️ Download Existing Paycode Events")

if st.button("Download Existing Paycode Events", use_container_width=True):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)

    if r.status_code != 200:
        st.error("❌ Failed to fetch Paycode Events")
    else:
        rows = []

        for event in r.json():
            for sch in event.get("schedules", []):
                rd, rm, ry = sch.get("repeatDay"), sch.get("repeatMonth"), sch.get("repeatYear")

                date = (
                    f"{int(rd):02d}-{int(rm):02d}-{int(ry)}"
                    if str(rd).isdigit() and str(rm).isdigit() and str(ry).isdigit()
                    else ""
                )

                rows.append({
                    "id": event.get("id"),
                    "name": event.get("name"),
                    "description": event.get("description"),
                    "paycode_id": event.get("paycode", {}).get("id"),
                    "holiday_name": sch.get("name"),
                    "holiday_date(DD-MM-YYYY)": date,
                    "repeatWeek": sch.get("repeatWeek", "*"),
                    "repeatWeekday": sch.get("repeatWeekday", "*")
                })

        df = pd.DataFrame(rows)

        st.download_button(
            "⬇️ Download CSV Now",
            data=df.to_csv(index=False),
            file_name="paycode_events_export.csv",
            mime="text/csv"
        )
