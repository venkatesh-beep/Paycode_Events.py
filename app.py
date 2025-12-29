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

init("logged_in", False)
init("username", "")
init("token", None)
init("view", "login")   # login | dashboard | api
init("AUTH_URL", DEFAULT_AUTH_URL)
init("BASE_URL", DEFAULT_BASE_URL)
init("START_DATE", DEFAULT_START_DATE)
init("final_body", [])

# ================= PAGE CONFIG =================
st.set_page_config(page_title="Paycode Events Portal", layout="wide")

# ================= GLOBAL STYLE =================
st.markdown("""
<style>
body { background:#f4f6fb; font-family: Inter, sans-serif; }

.card {
  background:#fff;
  padding:30px;
  border-radius:12px;
  box-shadow:0 15px 30px rgba(0,0,0,.1);
  max-width:380px;
  margin:auto;
}

.grid {
  display:grid;
  grid-template-columns:repeat(2, 260px);
  gap:20px;
  justify-content:center;
}

button {
  font-weight:600;
  border-radius:8px !important;
}

.top-right {
  position:fixed;
  top:20px;
  right:30px;
}
</style>
""", unsafe_allow_html=True)

# ================= LOGIN =================
if st.session_state.view == "login":

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("## Paycode Portal")

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
            st.error("❌ Invalid login")
        else:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.token = r.json()["access_token"]
            st.session_state.view = "dashboard"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ================= API CONFIG =================
if st.session_state.view == "api":

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### API Configuration")

    st.session_state.AUTH_URL = st.text_input(
        "Auth URL", st.session_state.AUTH_URL
    )
    st.session_state.BASE_URL = st.text_input(
        "Base API URL", st.session_state.BASE_URL
    )
    st.session_state.START_DATE = st.text_input(
        "Start Date of the Event (YYYY-MM-DD)",
        st.session_state.START_DATE
    )

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Save"):
            st.session_state.view = "dashboard"
            st.rerun()
    with c2:
        if st.button("Cancel"):
            st.session_state.view = "dashboard"
            st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# ================= AUTH HEADER =================
headers_auth = {
    "Authorization": f"Bearer {st.session_state.token}",
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json"
}

# ================= DASHBOARD =================
st.markdown("<div class='top-right'>", unsafe_allow_html=True)
if st.button("⚙️"):
    st.session_state.view = "api"
    st.rerun()

if st.button("Logout"):
    st.session_state.clear()
    st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("## Paycode Events Dashboard")
st.markdown(
    "**To create a Paycode Event, do not enter the ID.**  \n"
    "**To update a Paycode Event, enter the ID.**"
)

# ================= ACTION GRID =================
st.markdown("<div class='grid'>", unsafe_allow_html=True)

if st.button("Upload Paycode Events File"):
    st.session_state.view = "upload"
if st.button("Create / Update Paycode Events"):
    st.session_state.view = "submit"
if st.button("Delete Paycode Events"):
    st.session_state.view = "delete"
if st.button("Download Paycode Events"):
    st.session_state.view = "download"

st.markdown("</div>", unsafe_allow_html=True)

# ================= UPLOAD =================
if st.session_state.view == "upload":

    st.subheader("Upload Paycode Events File")

    template = pd.DataFrame(columns=[
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
        "Download Upload Template",
        template.to_csv(index=False),
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
            if not name:
                continue

            desc = r.get("Description", "").strip() or name
            uid = str(r.get("id", "")).strip()
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
        st.success("File processed successfully")

# ================= SUBMIT =================
if st.session_state.view == "submit":

    st.subheader("Create / Update Paycode Events")

    for p in st.session_state.final_body:
        if "id" in p:
            requests.put(
                f"{st.session_state.BASE_URL}/{p['id']}",
                headers=headers_auth,
                json=p
            )
        else:
            requests.post(
                st.session_state.BASE_URL,
                headers=headers_auth,
                json=p
            )

    st.success("Operation completed")

# ================= DELETE =================
if st.session_state.view == "delete":

    st.subheader("Delete Paycode Events")

    ids = st.text_input("Enter IDs (comma separated)")
    if st.button("Delete"):
        for i in ids.split(","):
            if i.strip().isdigit():
                requests.delete(
                    f"{st.session_state.BASE_URL}/{i.strip()}",
                    headers=headers_auth
                )
        st.success("Delete completed")

# ================= DOWNLOAD =================
if st.session_state.view == "download":

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
    st.download_button(
        "Download CSV",
        df.to_csv(index=False),
        "paycode_events_export.csv"
    )
