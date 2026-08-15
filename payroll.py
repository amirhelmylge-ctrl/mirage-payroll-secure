import streamlit as st
import pandas as pd
import os

# --- إعدادات الصفحة ---
st.set_page_config(
    page_title="بوابة أفراد شركة ميراج",
    page_icon="🔒",
    layout="wide"
)

# --- التحقق من الأمان عبر st.secrets ---
try:
    ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]
except Exception:
    st.error("تنبيه أمني: لم يتم العثور على كلمة مرور المسؤول في ملف الأسرار (st.secrets). يرجى إعدادها في لوحة تحكم Streamlit Cloud.")
    ADMIN_PASSWORD = "default_fallback_password"

# --- العنوان الرئيسي المحدث ---
st.title("بوابة أفراد شركة ميراج - لتفاصيل الرواتب و المستحقات المالية 🔒")

# --- محتوى التطبيق التجريبي / الأساسي ---
st.sidebar.selectbox("Choose Language / اللغة", ["العربية", "English"])

# قسم تسجيل دخول المشرف (Admin)
st.sidebar.markdown("---")
st.sidebar.subheader("🛠️ لوحة تحكم المسؤول (Admin)")
admin_pass_input = st.sidebar.text_input("🔑 أدخل كلمة مرور المسؤول:", type="password")

if st.sidebar.button("🔓 فتح لوحة التحكم"):
    if admin_pass_input == ADMIN_PASSWORD:
        st.sidebar.success("تم تسجيل الدخول بنجاح!")
        st.success("أهلاً بك يا مشرف النظام. يمكنك الآن تعديل أو رفع ملفات الرواتب.")
    else:
        st.sidebar.error("كلمة المرور غير صحيحة.")

# نموذج البحث للموظفين
st.markdown("---")
st.markdown("🆔 **الرجاء إدخال الرقم القومي للمتابعة.**")

col1, col2 = st.columns([1, 2])
with col1:
    if st.button("⬅️ رجوع"):
        st.info("تم العودة للخلف.")

national_id = st.text_input("🔒 كلمة المرور (Password):", type="password")

if st.button("🔑 تسجيل الدخول"):
    if national_id:
        st.warning("جاري البحث عن بيانات الرواتب...")
    else:
        st.error("يرجى إدخال الرقم القومي أولاً.")
