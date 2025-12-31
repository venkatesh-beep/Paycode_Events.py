import streamlit as st
import requests
import pandas as pd
import csv
import io
# ================= DOWNLOAD TEMPLATE =================
st.subheader("📥 Download Upload Template")

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

def fetch_paycodes(headers_auth, base_url):
    url = base_url.replace("paycode_events", "paycodes")
    r = requests.get(url, headers=headers_auth)

    if r.status_code != 200:
        return pd.DataFrame(columns=["id", "paycode"])

    return pd.DataFrame([
        {
            "id": p.get("id"),
            "paycode": p.get("code")
        }
        for p in r.json()
    ])

col_t1, col_t2 = st.columns([0.7, 0.3])

with col_t1:
    st.caption(
        "• **Sheet 1** → Paycode Events upload format\n"
        "• **Sheet 2** → Paycodes reference (id + paycode)"
    )

with col_t2:
    if st.button("⬇️ Download Template", use_container_width=True):

        paycodes_df = fetch_paycodes(headers_auth, st.session_state.BASE_URL)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            template_df.to_excel(
                writer,
                index=False,
                sheet_name="Paycode Events"
            )
            paycodes_df.to_excel(
                writer,
                index=False,
                sheet_name="Paycodes"
            )

        # single-click download (Streamlit limitation compliant)
        st.download_button(
            label="⬇️ Click to Download Excel",
            data=output.getvalue(),
            file_name="paycode_events_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

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

# ================= DATE PARSER (FIX ONLY) =================
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
st.caption("Create • Update • Delete • Download Paycode Events")

# ================= LOGIN =================
if not st.session_state.token:
    st.subheader("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Generate Token"):
        r = requests.post(
            st.session_state.AUTH_URL,
            data={"username": username, "password": password, "grant_type": "password"},
            headers={
                "Authorization": CLIENT_AUTH,
                "Content-Type": "application/x-www-form-urlencoded"
            }
        )
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

# ================= UPLOAD =================
st.subheader("📤 Upload Paycode Events File")

uploaded_file = st.file_uploader("Upload CSV or Excel", ["csv", "xlsx", "xls"])

if uploaded_file:
    store = {}

    df = (
        pd.read_csv(uploaded_file)
        if uploaded_file.name.endswith(".csv")
        else pd.read_excel(uploaded_file)
    )

    df = df.fillna("")

    for _, row in df.iterrows():
        raw_id = str(row.get("id", "")).strip()
        name = str(row.get("Paycode Event Name", "")).strip()
        description = str(row.get("Description", "")).strip() or name
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
            "repeatWeek": str(row.get("repeatWeek", "")).strip() or "*",
            "repeatWeekday": str(row.get("repeatWeekday", "")).strip() or "*"
        })

    st.session_state.final_body = list(store.values())
    st.success(f"✅ File processed. Paycode Events: {len(store)}")

# ================= CREATE / UPDATE =================
st.subheader("🚀 Create / Update Paycode Events")

if st.button("Submit Paycode Events"):
    results = []

    for payload in st.session_state.final_body:
        is_update = "id" in payload

        r = (
            requests.put(
                f"{st.session_state.BASE_URL}/{payload['id']}",
                headers=headers_auth,
                json=payload
            )
            if is_update
            else requests.post(
                st.session_state.BASE_URL,
                headers=headers_auth,
                json=payload
            )
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

if st.button("Download Existing Paycode Events"):
    r = requests.get(st.session_state.BASE_URL, headers=headers_auth)

    if r.status_code != 200:
        st.error("❌ Failed to fetch Paycode Events")
    else:
        rows = []

        for e in r.json():
            for s in e.get("schedules", []):
                rd, rm, ry = s.get("repeatDay"), s.get("repeatMonth"), s.get("repeatYear")

                date = (
                    f"{int(rd):02d}-{int(rm):02d}-{int(ry)}"
                    if str(rd).isdigit() and str(rm).isdigit() and str(ry).isdigit()
                    else ""
                )

                rows.append({
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "description": e.get("description"),
                    "paycode_id": e.get("paycode", {}).get("id"),
                    "holiday_name": s.get("name"),
                    "holiday_date(DD-MM-YYYY)": date,
                    "repeatWeek": s.get("repeatWeek", "*"),
                    "repeatWeekday": s.get("repeatWeekday", "*")
                })

        df = pd.DataFrame(rows)

        # single-click download (maximum allowed)
        st.download_button(
            "⬇️ Download CSV",
            data=df.to_csv(index=False),
            file_name="paycode_events_export.csv",
            mime="text/csv"
        )
