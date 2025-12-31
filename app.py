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

# ================= FETCH PAYCODES =================
def fetch_paycodes(headers_auth, base_url):
    url = base_url.replace("paycode_events", "paycodes")
    r = requests.get(url, headers=headers_auth)

    if r.status_code != 200:
        return pd.DataFrame(columns=["id", "paycode"])

    return pd.DataFrame([
        {"id": p.get("id"), "paycode": p.get("code")}
        for p in r.json()
    ])

# ================= INFO =================
st.info(
    "• **Create** → Leave `id` empty\n"
    "• **Update** → Provide numeric `id` in all rows\n"
    "• **repeatWeek / repeatWeekday** → Defaults to `*` if blank"
)

# ================= UPLOAD SECTION =================
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

# ================= TEMPLATE DOWNLOAD =================
st.markdown("### 📥 Download Upload Template")

col1, col2 = st.columns([0.7, 0.3])

with col1:
    st.caption(
        "• Sheet 1 → Paycode Events Upload\n"
        "• Sheet 2 → Paycodes Reference (id + paycode)"
    )

with col2:
    if st.button("⬇️ Download Template", use_container_width=True):
        paycodes_df = fetch_paycodes(headers_auth, st.session_state.BASE_URL)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            template_df.to_excel(writer, index=False, sheet_name="Paycode Events")
            paycodes_df.to_excel(writer, index=False, sheet_name="Paycodes")

        st.download_button(
            "⬇️ Click to Download Excel",
            data=output.getvalue(),
            file_name="paycode_events_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ================= FILE UPLOAD =================
uploaded_file = st.file_uploader("Upload CSV or Excel file", ["csv", "xlsx", "xls"])

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
        paycode_id = str(row.get("paycode_id", "")).strip()
        holiday_name = str(row.get("holiday_name", "")).strip()
        holiday_date = str(row.get("holiday_date(DD-MM-YYYY)", "")).strip()

        repeat_week = str(row.get("repeatWeek", "")).strip() or "*"
        repeat_weekday = str(row.get("repeatWeekday", "")).strip() or "*"

        if not name or not holiday_name or not paycode_id.isdigit():
            continue

        parts = holiday_date.split("-")
        if len(parts) != 3:
            continue

        d, m, y = [p.strip() for p in parts]
        if not (d.isdigit() and m.isdigit() and y.isdigit()):
            continue

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
            "repeatDay": int(d),
            "repeatMonth": int(m),
            "repeatYear": int(y),
            "repeatWeek": repeat_week,
            "repeatWeekday": repeat_weekday
        })

    st.session_state.final_body = list(store.values())
    st.success(f"✅ Loaded {len(store)} Paycode Events")

# ================= CREATE / UPDATE =================
st.subheader("🚀 Create / Update Paycode Events")

if st.button("Submit Paycode Events", use_container_width=True):
    success, failed = 0, 0

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
            success += 1
        else:
            failed += 1

    st.success(f"✅ Success: {success}")
    if failed:
        st.error(f"❌ Failed: {failed}")

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
