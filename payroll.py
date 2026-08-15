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
st.set_page_config(page_title="بوابة أفراد شركة ميراج", page_icon="🔐", layout="wide")

SHARED_FILE = "shared_payroll.xlsx"
STATUS_FILE = "portal_status.txt"
ONLINE_FILE = "online_users.json"
DEVICES_FILE = "device_bindings.json"

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except:
    st.error("⚠️ إعدادات الأمان مفقودة")
    st.stop()

# ====================================================================
# CACHED DATA LOADING (PERFORMANCE OPTIMIZATION)
# ====================================================================
@st.cache_data(ttl=600)
def load_excel_df():
    if not os.path.exists(SHARED_FILE):
        return None
    try:
        df = pd.read_excel(SHARED_FILE, dtype=str)
        df.columns = df.columns.str.strip()
        # التنظيف الأساسي للبيانات
        df = df.rename(columns={
            "كلمة المرور": "Password", "كلمه المرور": "Password",
            "الرقم القومي": "الرقم القومي", "الرقم القومى": "الرقم القومي",
            "رقم قومي": "الرقم القومي"
        })
        return df
    except:
        return None

# ====================================================================
# INITIALIZE SESSION STATES
# ====================================================================
if "admin_logged_in" not in st.session_state: st.session_state.admin_logged_in = False
if "logged_in_id" not in st.session_state: st.session_state.logged_in_id = None

# ====================================================================
# UI HELPERS
# ====================================================================
def get_t():
    lang = st.sidebar.selectbox("🌐 Language", ["العربية", "English"])
    if lang == "العربية":
        return {
            "title": "🔐 بوابة أفراد شركة ميراج - لتفاصيل الرواتب",
            "input_label": "🆔 الرقم القومي:",
            "login_btn": "دخول",
            "password_label": "كلمة المرور:",
            "welcome": "أهلاً بك يا {name}",
            "dashboard": "📊 تفاصيل الراتب"
        }
    return {
        "title": "🔐 Mirage Portal - Payroll Details",
        "input_label": "🆔 National ID:",
        "login_btn": "Login",
        "password_label": "Password:",
        "welcome": "Welcome {name}",
        "dashboard": "📊 Payroll Details"
    }

t = get_t()
st.title(t["title"])

# ====================================================================
# MAIN LOGIC
# ====================================================================
df = load_excel_df()

if st.session_state.logged_in_id:
    # عرض لوحة التحكم للموظف
    emp_data = df[df["الرقم القومي"] == st.session_state.logged_in_id].iloc[0]
    st.success(t["welcome"].format(name=emp_data.get("الاسم", "")))
    
    # تحسين عرض البيانات باستخدام st.dataframe بدلاً من st.table
    st.subheader(t["dashboard"])
    display_df = pd.DataFrame(emp_data.drop("Password"))
    st.dataframe(display_df, use_container_width=True, hide_index=False)
    
    if st.button("🚪 خروج"):
        st.session_state.logged_in_id = None
        st.rerun()

else:
    # شاشة تسجيل الدخول
    with st.form("login_form"):
        nid = st.text_input(t["input_label"])
        pwd = st.text_input(t["password_label"], type="password")
        submitted = st.form_submit_button(t["login_btn"])
        
        if submitted:
            if df is not None and nid in df["الرقم القومي"].values:
                user = df[df["الرقم القومي"] == nid].iloc[0]
                if user["Password"] == pwd:
                    st.session_state.logged_in_id = nid
                    st.rerun()
                else:
                    st.error("كلمة مرور خاطئة")
            else:
                st.error("الرقم القومي غير موجود")

# ====================================================================
# ADMIN SIDEBAR (SIMPLIFIED FOR SPEED)
# ====================================================================
with st.sidebar:
    st.header("🛠️ Admin")
    admin_pwd = st.text_input("Password", type="password")
    if st.button("Login Admin"):
        if admin_pwd == ADMIN_PASSWORD:
            st.session_state.admin_logged_in = True
            st.rerun()
            
    if st.session_state.admin_logged_in:
        uploaded_file = st.file_uploader("تحديث قاعدة البيانات", type=["xlsx"])
        if uploaded_file:
            with open(SHARED_FILE, "wb") as f:
                f.write(uploaded_file.getbuffer())
            st.cache_data.clear() # مسح الكاش لتحديث البيانات فوراً
            st.success("تم التحديث!")
