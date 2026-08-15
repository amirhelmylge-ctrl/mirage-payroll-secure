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
    page_title="بوابة افراد ميراج- لتفاصيل الرواتب و المستحقات المالية", page_icon="🔐", layout="wide"
)

# ====================================================================
# GLOBAL CONSTANTS & FILE PATHS
# ====================================================================
SHARED_FILE = "shared_payroll.xlsx"
STATUS_FILE = "portal_status.txt"
ONLINE_FILE = "online_users.json"
DEVICES_FILE = "device_bindings.json"
ANNOUNCEMENT_FILE = "announcement.txt"

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    st.error("⚠️ تنبيه أمني: يرجى إعداد ملف الـ secrets.")
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
if "shown_announcement" not in st.session_state: st.session_state.shown_announcement = False

# ====================================================================
# HELPER FUNCTIONS
# ====================================================================
def device_id_fetcher():
    query_params = st.query_params
    device_id_param = query_params.get("device_id")
    if device_id_param:
        st.session_state.device_uuid = device_id_param
    else:
        js_code = """
        <script>
        (function() {
            let deviceId = localStorage.getItem('mirage_device_uuid');
            if (!deviceId) {
                deviceId = 'dev_' + Math.random().toString(36).substring(2, 15);
                localStorage.setItem('mirage_device_uuid', deviceId);
            }
            const currentUrl = new URL(window.parent.location.href);
            if (!currentUrl.searchParams.get('device_id')) {
                currentUrl.searchParams.set('device_id', deviceId);
                window.parent.location.href = currentUrl.toString();
            }
        })();
        </script>
        """
        components.html(js_code, height=0, width=0)

device_id_fetcher()

def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    rename_dict = {
        'كلمة المرور': 'Password', 'كلمه المرور': 'Password',
        'الرقم القومي': 'الرقم القومي', 'الرقم القومى': 'الرقم القومي',
        'الاسم': 'الاسم', 'اسم الموظف': 'الاسم'
    }
    df = df.rename(columns=rename_dict)
    if "Password" not in df.columns: df["Password"] = ""
    if "الرقم القومي" not in df.columns: df["الرقم القومي"] = ""
    return df

def get_announcement():
    if os.path.exists(ANNOUNCEMENT_FILE):
        with open(ANNOUNCEMENT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

# ====================================================================
# TRANSLATIONS
# ====================================================================
translations = {
    "العربية": {
        "title": "🔐 بوابة افراد ميراج- لتفاصيل الرواتب و المستحقات المالية",
        "admin_header": "🛠️ لوحة تحكم المدير المالي",
        "announcement_label": "📢 إعلان الموظفين (يظهر عند تسجيل الدخول):",
        "save_announcement": "💾 حفظ الإعلان",
        "portal_master_toggle": "🔓 تفعيل دخول الموظفين",
        "logout_btn": "🚪 تسجيل الخروج",
        "welcome_banner": "👋 أهلاً بك يا {name}!"
    }
}
t = translations["العربية"]

# ====================================================================
# ADMIN SECTION
# ====================================================================
st.sidebar.header(t["admin_header"])

if not st.session_state.admin_logged_in:
    if st.sidebar.button("فتح لوحة المدير المالي"):
        pass # منطق الدخول المعتاد
else:
    # إضافة ميزة الإعلان في لوحة التحكم
    st.sidebar.markdown("---")
    current_announcement = get_announcement()
    new_announcement = st.sidebar.text_area(t["announcement_label"], value=current_announcement)
    if st.sidebar.button(t["save_announcement"]):
        with open(ANNOUNCEMENT_FILE, "w", encoding="utf-8") as f:
            f.write(new_announcement)
        st.sidebar.success("تم حفظ الإعلان!")

# ====================================================================
# EMPLOYEE PORTAL VIEW
# ====================================================================
if st.session_state.get("logged_in_user"):
    # إظهار الإعلان للموظف
    announcement = get_announcement()
    if announcement and not st.session_state.shown_announcement:
        st.toast(announcement, icon="📢")
        st.session_state.shown_announcement = True
    
    st.success(t["welcome_banner"].format(name=st.session_state.logged_in_user))
    
    if st.button(t["logout_btn"]):
        st.session_state.logged_in_user = None
        st.session_state.shown_announcement = False
        st.rerun()

# باقي الكود الخاص بك يوضع هنا...
