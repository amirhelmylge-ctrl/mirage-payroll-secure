import io
import json
import os
import time
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ====================================================================
# PAGE CONFIGURATION
# ====================================================================
st.set_page_config(
    page_title="بوابة أفراد شركة ميراج", page_icon="🔐", layout="wide"
)

# ====================================================================
# GLOBAL CONSTANTS & FILE PATHS
# ====================================================================
SHARED_FILE = "shared_payroll.xlsx"
STATUS_FILE = "portal_status.txt"
ONLINE_FILE = "online_users.json"
DEVICES_FILE = "device_bindings.json"

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    st.error("⚠️ تنبيه أمني: لم يتم العثور على كلمة مرور المسؤول في ملف الأسرار.")
    st.stop()

# ====================================================================
# INITIALIZE SESSION STATES
# ====================================================================
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None
if "logged_in_id" not in st.session_state: st.session_state.logged_in_id = None
if "employee_row_data" not in st.session_state: st.session_state.employee_row_data = None
if "checked_id" not in st.session_state: st.session_state.checked_id = None
if "uploader_key" not in st.session_state: st.session_state.uploader_key = 0
if "device_uuid" not in st.session_state: st.session_state.device_uuid = None

# ====================================================================
# DEVICE IDENTIFIER
# ====================================================================
def device_id_fetcher():
    query_params = st.query_params
    device_id_param = query_params.get("device_id")
    if device_id_param:
        st.session_state.device_uuid = device_id_param
    else:
        js_code = """<script>(function(){let deviceId=localStorage.getItem('mirage_device_uuid');if(!deviceId){deviceId='dev_'+Math.random().toString(36).substring(2,15);localStorage.setItem('mirage_device_uuid',deviceId);}const currentUrl=new URL(window.parent.location.href);if(!currentUrl.searchParams.get('device_id')){currentUrl.searchParams.set('device_id',deviceId);window.parent.location.href=currentUrl.toString();}})();</script>"""
        components.html(js_code, height=0, width=0)

device_id_fetcher()

# ====================================================================
# FUNCTIONS (Normalization, Locking, Status)
# ====================================================================
def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    rename_dict = {
        "كلمة المرور": "Password", "كلمه المرور": "Password", "باسورد": "Password",
        "الرقم القومي": "الرقم القومي", "الرقم القومى": "الرقم القومي", "id": "الرقم القومي",
        "الاسم": "الاسم", "اسم الموظف": "الاسم"
    }
    df = df.rename(columns=rename_dict)
    if "Password" not in df.columns: df["Password"] = ""
    if "الرقم القومي" not in df.columns: df["الرقم القومي"] = ""
    df["Password"] = df["Password"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    df["الرقم القومي"] = df["الرقم القومي"].fillna("").astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    return df

def load_excel_df():
    if not os.path.exists(SHARED_FILE): return None
    try:
        df = pd.read_excel(SHARED_FILE, dtype=str)
        return normalize_dataframe_columns(df)
    except: return None

def save_excel_safely(df):
    df.to_excel(SHARED_FILE, index=False)
    st.cache_data.clear()

def is_portal_open():
    if not os.path.exists(STATUS_FILE): return False
    with open(STATUS_FILE, "r") as f: return f.read().strip() == "OPEN"

# ====================================================================
# TRANSLATIONS & UI
# ====================================================================
translations = {
    "العربية": {
        "title": "🔐 بوابة أفراد شركة ميراج - لتفاصيل الرواتب و المستحقات المالية",
        "login_btn": "تسجيل الدخول",
        "register_btn": "التسجيل والدخول",
        "logout_btn": "تسجيل الخروج",
        "input_label": "الرقم القومي:",
        "password_label": "كلمة المرور:"
    },
    "English": {
        "title": "🔐 Mirage Portal - Payroll & Financials",
        "login_btn": "Login",
        "register_btn": "Register & Login",
        "logout_btn": "Logout",
        "input_label": "National ID:",
        "password_label": "Password:"
    }
}
selected_lang = st.sidebar.selectbox("Language / اللغة", ["العربية", "English"])
t = translations[selected_lang]

st.title(t["title"])

# ====================================================================
# MAIN PORTAL LOGIC
# ====================================================================
if not is_portal_open():
    st.error("⚠️ البوابة مغلقة حالياً.")
else:
    # (هنا يوضع باقي منطق الكود الخاص بعرض البيانات، التسجيل، ولوحة المسؤول كما في الكود السابق)
    # ... الكود المعتاد ...
    st.write("مرحباً بك في بوابة شركة ميراج.")
