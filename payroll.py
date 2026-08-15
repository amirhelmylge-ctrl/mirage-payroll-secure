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

try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    st.error(
        "⚠️ تنبيه أمني: لم يتم العثور على كلمة مرور المسؤول في ملف الأسرار"
        " (st.secrets). يرجى إعداد ملف الـ secrets."
    )
    st.stop()


# ====================================================================
# INITIALIZE SESSION STATES
# ====================================================================
if "admin_logged_in" not in st.session_state:
    st.session_state.admin_logged_in = False
if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "logged_in_id" not in st.session_state:
    st.session_state.logged_in_id = None
if "employee_row_data" not in st.session_state:
    st.session_state.employee_row_data = None
if "checked_id" not in st.session_state:
    st.session_state.checked_id = None
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0
if "device_uuid" not in st.session_state:
    st.session_state.device_uuid = None


# ====================================================================
# DEVICE IDENTIFIER (JS LOCALSTORAGE INJECTOR)
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
                deviceId = 'dev_' + Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
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


# ====================================================================
# COLUMN NORMALIZATION HELPER
# ====================================================================
def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = df.columns.str.strip()
    rename_dict = {}

    for col in df.columns:
        col_clean = str(col).strip().lower()
        if col_clean in [
            "password",
            "كلمة المرور",
            "كلمه المرور",
            "باسورد",
            "كلمة السر",
            "كلمه السر",
        ]:
            rename_dict[col] = "Password"
        elif col_clean in [
            "الرقم القومي",
            "الرقم القومى",
            "رقم قومي",
            "رقم القومي",
            "national id",
            "id",
        ]:
            rename_dict[col] = "الرقم القومي"
        elif col_clean in ["الاسم", "اسم الموظف", "الاسم ثلاثي", "name"]:
            rename_dict[col] = "الاسم"

    df = df.rename(columns=rename_dict)

    if "Password" not in df.columns:
        df["Password"] = ""
    if "الرقم القومي" not in df.columns:
        df["الرقم القومي"] = ""

    df["Password"] = (
        df["Password"]
        .fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    df.loc[df["Password"].isin(["nan", "None", "NaN", "null", ""]), "Password"] = (
        ""
    )

    df["الرقم القومي"] = (
        df["الرقم القومي"]
        .fillna("")
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
    )
    return df


# ====================================================================
# DEVICE LOCKING LOGIC FUNCTIONS
# ====================================================================
def load_device_bindings() -> dict:
    if not os.path.exists(DEVICES_FILE):
        return {}
    try:
        with open(DEVICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_device_bindings(bindings: dict):
    with open(DEVICES_FILE, "w", encoding="utf-8") as f:
        json.dump(bindings, f, ensure_ascii=False, indent=2)


def is_device_allowed(device_id: str, national_id: str) -> tuple[bool, str]:
    if not device_id:
        return True, ""

    bindings = load_device_bindings()
    clean_nid = str(national_id).strip()

    for bound_nid, bound_dev in bindings.items():
        if bound_dev == device_id and bound_nid != clean_nid:
            return (
                False,
                f"هذا الجهاز محظور! تم استخدامه سابقاً مع الرقم القومي ({bound_nid}). لا يمكنك استخدام أكثر من رقم قومي على نفس الجهاز.",
            )

    if clean_nid in bindings:
        bound_dev = bindings[clean_nid]
        if bound_dev != device_id:
            return (
                False,
                "هذا الحساب مرتبط بجهاز آخر بالفعل. لا يمكنك تسجيل الدخول إلا من جهازك المعتمد.",
            )

    return True, ""


def bind_device_to_id(device_id: str, national_id: str):
    if not device_id or not national_id:
        return
    bindings = load_device_bindings()
    bindings[str(national_id).strip()] = device_id
    save_device_bindings(bindings)


# ====================================================================
# AUTO LOGOUT LOGIC & COMPONENT
# ====================================================================
query_params = st.query_params
if query_params.get("action") == "auto_logout":
    if st.session_state.get("logged_in_id"):
        if os.path.exists(ONLINE_FILE):
            try:
                with open(ONLINE_FILE, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                s_data.pop(str(st.session_state.logged_in_id).strip(), None)
                with open(ONLINE_FILE, "w", encoding="utf-8") as f:
                    json.dump(s_data, f)
            except Exception:
                pass
    st.session_state.logged_in_user = None
    st.session_state.logged_in_id = None
    st.session_state.employee_row_data = None
    st.session_state.checked_id = None

    dev_id = query_params.get("device_id")
    st.query_params.clear()
    if dev_id:
        st.query_params["device_id"] = dev_id

    st.warning("⏱️ تم تسجيل الخروج تلقائياً لعدم النشاط لمدة 5 دقائق.")


def auto_logout_listener(timeout_minutes=5):
    timeout_ms = timeout_minutes * 60 * 1000
    dev_id = st.session_state.get("device_uuid", "")
    js_code = f"""
    <script>
    (function() {{
        let timeout;
        const TIMEOUT_MS = {timeout_ms};

        function resetTimer() {{
            clearTimeout(timeout);
            timeout = setTimeout(logout, TIMEOUT_MS);
        }}

        function logout() {{
            const currentUrl = new URL(window.parent.location.href.split('?')[0]);
            currentUrl.searchParams.set('action', 'auto_logout');
            if ("{dev_id}") {{
                currentUrl.searchParams.set('device_id', "{dev_id}");
            }}
            window.parent.location.href = currentUrl.toString();
        }}

        window.onload = resetTimer;
        document.onmousemove = resetTimer;
        document.onkeypress = resetTimer;
        document.onclick = resetTimer;
        document.onscroll = resetTimer;
        
        resetTimer();
    }})();
    </script>
    """
    components.html(js_code, height=0, width=0)


# ====================================================================
# ONLINE / OFFLINE TRACKING LOGIC
# ====================================================================
def update_online_status(national_id: str, is_online: bool):
    if not national_id:
        return
    status_data = {}
    if os.path.exists(ONLINE_FILE):
        try:
            with open(ONLINE_FILE, "r", encoding="utf-8") as f:
                status_data = json.load(f)
        except Exception:
            status_data = {}

    clean_id = str(national_id).strip()
    if is_online:
        status_data[clean_id] = time.time()
    else:
        status_data.pop(clean_id, None)

    with open(ONLINE_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f)


def get_online_users(timeout_seconds=300) -> set:
    if not os.path.exists(ONLINE_FILE):
        return set()
    try:
        with open(ONLINE_FILE, "r", encoding="utf-8") as f:
            status_data = json.load(f)
        current_time = time.time()
        active_users = {
            nid
            for nid, last_seen in status_data.items()
            if current_time - last_seen < timeout_seconds
        }
        return active_users
    except Exception:
        return set()


# ====================================================================
# CORE LOGIC: PORTAL STATUS GATEKEEPER
# ====================================================================
def is_portal_open():
    if not os.path.exists(SHARED_FILE):
        return False
    if not os.path.exists(STATUS_FILE):
        return False
    try:
        with open(STATUS_FILE, "r") as f:
            return f.read().strip() == "OPEN"
    except Exception:
        return False


def set_portal_status(is_open: bool):
    with open(STATUS_FILE, "w") as f:
        f.write("OPEN" if is_open else "CLOSED")


# ====================================================================
# TRANSLATIONS DICTIONARY
# ====================================================================
translations = {
    "English": {
        "title": "🔐 بوابة افراد ميراج- لتفاصيل الرواتب و المستحقات المالية",
        "subtitle": "🆔 Please enter your National ID to proceed.",
        "admin_header": "🛠️ Admin Control Panel",
        "admin_pass_label": "🔑 Enter Admin Password:",
        "admin_pass_btn": "🔓 Unlock Admin Panel",
        "admin_access_denied": "❌ Incorrect Admin Password.",
        "admin_panel_unlocked": "✨ Admin Panel Unlocked Successfully!",
        "portal_master_toggle": "🔓 Enable Employee Portal Access",
        "portal_locked_msg": (
            "⚠️ PORTAL LOCKED: Employee login is completely disabled."
        ),
        "upload_label": "📁 Upload Employees Excel File (.xlsx or .xls)",
        "download_btn": "📥 Download Updated Database (Secure)",
        "remove_btn": "🗑️ Remove Excel Sheet (Lock Portal & Wipe Data)",
        "refresh_btn": "🔄 Refresh Data",
        "refresh_success": "✅ Data refreshed successfully!",
        "upload_success": (
            "✅ Excel uploaded successfully! Portal automatically unlocked."
        ),
        "remove_success": "🗑️ Excel file removed. Portal locked and data wiped.",
        "input_label": "🆔 National ID (الرقم القومي):",
        "check_id_btn": "➡️ Next / Verify ID",
        "password_input_label": "🔒 Password (كلمة المرور):",
        "new_password_label": "✨ Create Your Password (أنشئ كلمة المرور):",
        "confirm_password_label": "✔️ Confirm Password (تأكيد كلمة المرور):",
        "register_btn": "🚀 Register & Login",
        "login_btn": "🔑 Login",
        "logout_btn": "🚪 Logout",
        "back_btn": "⬅️ Back",
        "empty_input": "⚠️ Please fill in all required fields.",
        "pass_mismatch": "❌ Passwords do not match. Please try again.",
        "pass_taken": (
            "⚠️ This password is already taken. Please choose a different one."
        ),
        "error_id": "⚠️ National ID not found. Please check and try again.",
        "error_login": "❌ Incorrect Password. Please check and try again.",
        "register_success": "🎉 Password created successfully! Welcome.",
        "error_read": "❌ Error reading file: {error}",
        "dashboard_title": "📊 تفاصيل الراتب الشهري والمستحقات المالية",
        "welcome_banner": "👋 Welcome, {name}!",
        "id_display": "🆔 National ID:",
        "table_col_key": "📋 Field / Column",
        "table_col_val": "💎 Value",
        "admin_employees_header": "👥 Employee Management & Passwords",
        "reset_pass_btn": "🔄 Reset Password",
        "reset_success": "✅ Password successfully reset for {name}.",
        "online_status": "🟢 Online",
        "offline_status": "⚪ Offline",
        "unbind_device_btn": "🔓 Reset Device Lock",
        "unbind_success": "✅ Device lock cleared for {name}.",
    },
    "العربية": {
        "title": "🔐 بوابة افراد ميراج- لتفاصيل الرواتب و المستحقات المالية",
        "subtitle": "🆔 الرجاء إدخال الرقم القومي للمتابعة.",
        "admin_header": "🛠️ لوحة تحكم المسؤول (Admin)",
        "admin_pass_label": "🔑 أدخل كلمة مرور المسؤول:",
        "admin_pass_btn": "🔓 فتح لوحة المسؤول",
        "admin_access_denied": "❌ كلمة مرور المسؤول غير صحيحة.",
        "admin_panel_unlocked": "✨ تم فتح لوحة المسؤول بنجاح!",
        "portal_master_toggle": "🔓 تفعيل دخول الموظفين للبوابة",
        "portal_locked_msg": (
            "⚠️ البوابة مغلقة: تسجيل دخول الموظفين معطل بالكامل."
        ),
        "upload_label": "📁 رفع ملف الـ Excel للموظفين (.xlsx أو .xls)",
        "download_btn": "📥 تحميل قاعدة البيانات (Excel الآمن)",
        "remove_btn": "🗑️ حذف ملف الـ Excel (إغلاق البوابة ومسح البيانات)",
        "refresh_btn": "🔄 تحديث البيانات",
        "refresh_success": "✅ تم تحديث البيانات بنجاح!",
        "upload_success": "✅ تم رفع الملف بنجاح! تم فتح البوابة تلقائياً.",
        "remove_success": "🗑️ تم حذف الملف وإغلاق البوابة ومسح البيانات.",
        "input_label": "🆔 الرقم القومي (National ID):",
        "check_id_btn": "➡️ التالي / التحقق من الرقم",
        "password_input_label": "🔒 كلمة المرور (Password):",
        "new_password_label": "✨ أنشئ كلمة المرور الخاصة بك:",
        "confirm_password_label": "✔️ تأكيد كلمة المرور:",
        "register_btn": "🚀 التسجيل والدخول",
        "login_btn": "🔑 تسجيل الدخول",
        "logout_btn": "🚪 تسجيل الخروج",
        "back_btn": "⬅️ رجوع",
        "empty_input": "⚠️ الرجاء ملء جميع الحقول المطلوبة.",
        "pass_mismatch": "❌ كلمتا المرور غير متطابقتين. يرجى المحاولة مرة أخرى.",
        "pass_taken": (
            "⚠️ كلمة المرور هذه مستخدمة من قبل موظف آخر. اختر كلمة مرور فريدة."
        ),
        "error_id": "⚠️ الرقم القومي غير موجود. يرجى التحقق والمحاولة.",
        "error_login": "❌ كلمة المرور غير صحيحة. يرجى التحقق.",
        "register_success": "🎉 تم إنشاء كلمة المرور بنجاح! أهلاً بك.",
        "error_read": "❌ خطأ في قراءة الملف: {error}",
        "dashboard_title": "📊 تفاصيل الراتب الشهري والمستحقات المالية",
        "welcome_banner": "👋 أهلاً بك يا {name}!",
        "id_display": "🆔 الرقم القومي:",
        "table_col_key": "📋 الحقل / العمود",
        "table_col_val": "💎 القيمة",
        "admin_employees_header": "👥 إدارة الموظفين وكلمات المرور",
        "reset_pass_btn": "🔄 إعادة تعيين كلمة المرور",
        "reset_success": "✅ تم إعادة تعيين كلمة المرور للموظف {name} بنجاح.",
        "online_status": "🟢 متصل الآن",
        "offline_status": "⚪ غير متصل",
        "unbind_device_btn": "🔓 فك ربط الجهاز",
        "unbind_success": "✅ تم فك ربط الجهاز للموظف {name} بنجاح.",
    },
}

selected_lang = st.sidebar.selectbox(
    "🌐 Choose Language / اللغة", ["العربية", "English"]
)
t = translations[selected_lang]


# ====================================================================
# EXCEL HELPER FUNCTIONS (WITH PERFORMANCE CACHING)
# ====================================================================
def read_excel_file(file_path_or_buffer):
    try:
        return pd.read_excel(file_path_or_buffer, dtype=str)
    except Exception as e:
        raise Exception(f"Could not read the Excel file: {e}")


@st.cache_data(ttl=600)  # تخزين مؤقت للبيانات لمدة 10 دقائق لتسريع التنقل بشكل هائل
def load_excel_df():
    if not os.path.exists(SHARED_FILE):
        return None
    try:
        df = read_excel_file(SHARED_FILE)
        df = normalize_dataframe_columns(df)
        return df
    except Exception as e:
        if os.path.exists(SHARED_FILE):
            try:
                os.remove(SHARED_FILE)
            except Exception:
                pass
        if os.path.exists(STATUS_FILE):
            try:
                os.remove(STATUS_FILE)
            except Exception:
                pass
        return None


def save_excel_safely(df):
    df = normalize_dataframe_columns(df)
    df.to_excel(SHARED_FILE, index=False)
    st.cache_data.clear()  # مسح الذاكرة المؤقتة تلقائياً عند تحديث البيانات


# ====================================================================
# ADMIN SECTION (SIDEBAR)
# ====================================================================
st.sidebar.markdown("---")
st.sidebar.header(t["admin_header"])

if not st.session_state.admin_logged_in:
    with st.sidebar.form(key="admin_login_form"):
        admin_pass_input = st.text_input(t["admin_pass_label"], type="password")
        submit_admin = st.form_submit_button(t["admin_pass_btn"])

        if submit_admin:
            if admin_pass_input.strip() == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.success(t["admin_panel_unlocked"])
                st.rerun()
            else:
                st.sidebar.error(t["admin_access_denied"])
else:
    has_file = os.path.exists(SHARED_FILE)
    if has_file:
        current_status = is_portal_open()
        master_toggle = st.sidebar.checkbox(
            t["portal_master_toggle"],
            value=current_status,
        )
        if master_toggle != current_status:
            set_portal_status(master_toggle)
            st.rerun()
    else:
        st.sidebar.warning("⚠️ Upload an Excel sheet to enable portal access.")

    uploaded_file = st.sidebar.file_uploader(
        t["upload_label"],
        type=["xlsx", "xls"],
        key=f"uploader_{st.session_state.uploader_key}",
    )

    if uploaded_file is not None:
        try:
            df_upload = read_excel_file(uploaded_file)
            df_upload = normalize_dataframe_columns(df_upload)

            save_excel_safely(df_upload)
            set_portal_status(True)

            st.session_state.uploader_key += 1
            st.sidebar.success(t["upload_success"])
            st.rerun()
        except Exception as e:
            st.sidebar.error(t["error_read"].format(error=e))

    if os.path.exists(SHARED_FILE):
        st.sidebar.markdown("---")
        st.sidebar.subheader(t["admin_employees_header"])
        df_admin = load_excel_df()

        online_users_set = get_online_users()
        device_bindings = load_device_bindings()

        if df_admin is not None:
            for idx, row in df_admin.iterrows():
                name = row.get("الاسم", f"Employee {idx}")
                nid = str(row.get("الرقم القومي", "")).strip()
                current_pwd = str(row.get("Password", "")).strip()
                has_pass = bool(current_pwd)

                is_online = nid in online_users_set
                has_device_bound = nid in device_bindings
                presence_badge = (
                    t["online_status"] if is_online else t["offline_status"]
                )
                reg_status = "🔒" if has_pass else "⏳"

                with st.sidebar.expander(
                    f"👤 {name} [{presence_badge}] ({reg_status})"
                ):
                    st.write(f"🆔 ID: `{nid}`")
                    st.write(f"🌐 الحالة: **{presence_badge}**")
                    st.write(
                        f"📱 الجهاز: **{'مقترن بجهاز' if has_device_bound else 'غير مقترن'}**"
                    )

                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        if has_pass:
                            if st.button(t["reset_pass_btn"], key=f"reset_{nid}_{idx}"):
                                df_admin.at[idx, "Password"] = ""
                                save_excel_safely(df_admin)
                                st.success(t["reset_success"].format(name=name))
                                st.rerun()
                    with col_btn2:
                        if has_device_bound:
                            if st.button(t["unbind_device_btn"], key=f"unbind_{nid}_{idx}"):
                                device_bindings.pop(nid, None)
                                save_device_bindings(device_bindings)
                                st.success(t["unbind_success"].format(name=name))
                                st.rerun()

            st.sidebar.markdown("---")
            df_export = df_admin.copy()

            export_rename_map = {
                "الرقم القومي": "National ID",
                "الاسم": "Name",
                "Password": "Password",
            }
            df_export = df_export.rename(columns=export_rename_map)

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df_export.to_excel(writer, index=False)
            excel_bytes = output.getvalue()

            st.sidebar.download_button(
                label=t["download_btn"],
                data=excel_bytes,
                file_name="mirage_payroll_database.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            )

    st.sidebar.markdown("---")
    if st.sidebar.button(t["remove_btn"]):
        if os.path.exists(SHARED_FILE):
            os.remove(SHARED_FILE)
        if os.path.exists(STATUS_FILE):
            os.remove(STATUS_FILE)
        if os.path.exists(ONLINE_FILE):
            os.remove(ONLINE_FILE)
        if os.path.exists(DEVICES_FILE):
            os.remove(DEVICES_FILE)
        st.cache_data.clear()
        st.rerun()

    if st.sidebar.button("🔒 Lock Admin Panel / قفل لوحة المسؤول"):
        st.session_state.admin_logged_in = False
        st.cache_data.clear()
        st.rerun()

# ====================================================================
# MAIN PAGE LAYOUT
# ====================================================================
col_title, col_refresh = st.columns([4, 1])
with col_title:
    st.title(t["title"])
with col_refresh:
    st.write("")
    if st.button(t["refresh_btn"]):
        st.cache_data.clear()
        if is_portal_open() and st.session_state.get("logged_in_id"):
            update_online_status(st.session_state.get("logged_in_id"), True)
            df_refresh = load_excel_df()
            if df_refresh is not None:
                matched_ref = df_refresh[
                    df_refresh["الرقم القومي"].astype(str).str.strip()
                    == str(st.session_state.logged_in_id).strip()
                ]
                if not matched_ref.empty:
                    st.session_state.employee_row_data = matched_ref.iloc[0].to_dict()
        st.success(t["refresh_success"])
        st.rerun()

st.markdown("---")

if not is_portal_open():
    st.error(t["portal_locked_msg"])
    st.stop()

# ====================================================================
# EMPLOYEE PORTAL VIEW
# ====================================================================
if st.session_state.get("logged_in_user"):
    auto_logout_listener(timeout_minutes=5)
    update_online_status(st.session_state.get("logged_in_id"), True)

    df_verify = load_excel_df()
    user_exists = False
    if df_verify is not None:
        v_match = df_verify[
            df_verify["الرقم القومي"].astype(str).str.strip()
            == str(st.session_state.get("logged_in_id")).strip()
        ]
        if not v_match.empty:
            user_exists = True
            st.session_state.employee_row_data = v_match.iloc[0].to_dict()

    if not user_exists:
        update_online_status(st.session_state.get("logged_in_id"), False)
        st.session_state.logged_in_user = None
        st.session_state.logged_in_id = None
        st.session_state.employee_row_data = None
        st.session_state.checked_id = None
        st.rerun()

    st.success(t["welcome_banner"].format(name=st.session_state.logged_in_user))
    st.markdown(f"### 📋 {t['dashboard_title']}")
    st.info(
        f"**{t['id_display']}**"
        f" `{str(st.session_state.get('logged_in_id')).strip()}`"
    )

    if st.session_state.get("employee_row_data") is not None:
        row_data = st.session_state.employee_row_data
        table_data = []
        for col_name, val in row_data.items():
            if str(col_name).strip().lower() in ["password", "كلمة المرور"]:
                continue
            display_val = val
            if pd.isna(val) or str(val).strip() == "" or str(val).lower() == "nan":
                display_val = 0
            table_data.append(
                {t["table_col_key"]: str(col_name), t["table_col_val"]: display_val}
            )

        df_display = pd.DataFrame(table_data)

        st.markdown(
            """
            <style>
                [data-testid="stTable"] th, 
                [data-testid="stTable"] td {
                    text-align: center !important;
                    justify-content: center !important;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.table(df_display)

    st.markdown("---")
    if st.button(t["logout_btn"]):
        update_online_status(st.session_state.get("logged_in_id"), False)
        st.session_state.logged_in_user = None
        st.session_state.logged_in_id = None
        st.session_state.employee_row_data = None
        st.session_state.checked_id = None
        st.rerun()

else:
    st.write(t["subtitle"])
    try:
        df = load_excel_df()
        if df is None:
            st.error(t["error_read"].format(error="Could not load data."))
        else:
            if st.session_state.get("checked_id") is None:
                national_id_input = st.text_input(
                    t["input_label"], key="national_id_field"
                )
                submit_id = st.button(t["check_id_btn"])

                if submit_id:
                    if not national_id_input.strip():
                        st.warning(t["empty_input"])
                    else:
                        clean_input_id = (
                            national_id_input.strip().replace(".0", "").replace("\t", "")
                        )

                        current_device = st.session_state.get("device_uuid")
                        allowed, reason = is_device_allowed(current_device, clean_input_id)

                        if not allowed:
                            st.error(f"🛑 {reason}")
                        else:
                            matched = df[
                                df["الرقم القومي"].astype(str).str.strip() == clean_input_id
                            ]
                            if not matched.empty:
                                st.session_state.checked_id = clean_input_id
                                st.rerun()
                            else:
                                st.error(t["error_id"])
            else:
                national_id_input = st.session_state.checked_id
                df_current = load_excel_df()
                matched = df_current[
                    df_current["الرقم القومي"].astype(str).str.strip()
                    == str(national_id_input).strip()
                ]

                if not matched.empty:
                    idx = matched.index[0]
                    current_pass = str(matched.loc[idx, "Password"]).strip()
                    emp_name = matched.loc[idx, "الاسم"]

                    if st.button(t["back_btn"]):
                        st.session_state.checked_id = None
                        st.rerun()

                    if not current_pass:
                        st.info(
                            "✨ لم يتم تعيين كلمة مرور لك بعد. يرجى إنشاء كلمة مرور جديدة"
                            " للحساب."
                        )
                        new_pass = st.text_input(
                            t["new_password_label"], type="password", key="new_pass_field"
                        )
                        confirm_pass = st.text_input(
                            t["confirm_password_label"],
                            type="password",
                            key="new_pass_field_confirm",
                        )
                        submit_register = st.button(t["register_btn"])

                        if submit_register:
                            if not new_pass or not confirm_pass:
                                st.warning(t["empty_input"])
                            elif new_pass != confirm_pass:
                                st.error(t["pass_mismatch"])
                            else:
                                existing_passes = (
                                    df_current["Password"]
                                    .astype(str)
                                    .str.strip()
                                    .tolist()
                                )
                                if new_pass.strip() in existing_passes:
                                    st.error(t["pass_taken"])
                                else:
                                    current_device = st.session_state.get("device_uuid")
                                    bind_device_to_id(current_device, national_id_input)

                                    df_current.at[idx, "Password"] = new_pass.strip()
                                    save_excel_safely(df_current)
                                    st.session_state.logged_in_user = emp_name
                                    st.session_state.logged_in_id = national_id_input
                                    st.session_state.employee_row_data = (
                                        df_current.loc[idx].to_dict()
                                    )
                                    st.session_state.checked_id = None

                                    update_online_status(national_id_input, True)
                                    st.success(t["register_success"])
                                    st.rerun()
                    else:
                        password_input = st.text_input(
                            t["password_input_label"],
                            type="password",
                            key="password_input_field",
                        )
                        submit_login = st.button(t["login_btn"])

                        if submit_login:
                            if not password_input:
                                st.warning(t["empty_input"])
                            elif password_input.strip() == current_pass:
                                current_device = st.session_state.get("device_uuid")
                                bind_device_to_id(current_device, national_id_input)

                                st.session_state.logged_in_user = emp_name
                                st.session_state.logged_in_id = national_id_input
                                st.session_state.employee_row_data = matched.loc[idx].to_dict()
                                st.session_state.checked_id = None

                                update_online_status(national_id_input, True)
                                st.rerun()
                            else:
                                st.error(t["error_login"])

    except Exception as e:
        st.error(t["error_read"].format(error=e))
