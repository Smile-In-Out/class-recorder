# streamlit_app.py
import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage, auth
from google.cloud import storage as gcs
import pandas as pd
import datetime
import os, json


# Firebase 초기화 (Streamlit Cloud에서는 환경 변수 사용 권장)
if not firebase_admin._apps:
    firebase_key = json.loads(os.environ["FIREBASE_KEY"])
    cred = credentials.Certificate(firebase_key)
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'class-recorder-4023f.firebasestorage.app'
    })

db = firestore.client()
bucket = storage.bucket()

st.set_page_config(page_title="수업 관리 시스템", layout="wide")
st.title("📘 수업 관리 시스템 (Streamlit + Firebase)")

# 사이드바 메뉴 구성
menu = st.sidebar.selectbox("메뉴를 선택하세요", [
    "로그인",
    "교과 관리",
    "수업 등록",
    "학생 등록",
    "진도 및 특기사항",
    "출결 및 특기사항"
])

# 로그인 기능 (Firebase Auth 이메일/비밀번호)
def login_page():
    st.subheader("🔐 로그인")
    st.info("Firebase Authentication 연동 필요 (기초 구현 생략 가능)")

# 1. 교과 관리
if menu == "교과 관리":
    st.subheader("📘 담당 교과 관리")
    with st.form("subject_form"):
        subject_name = st.text_input("교과명")
        year = st.selectbox("학년도", list(range(2020, datetime.datetime.now().year + 1))[::-1])
        semester = st.selectbox("학기", [1, 2])
        pdf_file = st.file_uploader("수업 및 평가계획서 (PDF)", type="pdf")
        submit = st.form_submit_button("등록")

        if submit:
            if pdf_file and pdf_file.size <= 10 * 1024 * 1024:
                file_path = f"plans/{year}_{semester}_{subject_name}.pdf"
                blob = bucket.blob(file_path)
                blob.upload_from_file(pdf_file, content_type='application/pdf')
                file_url = blob.public_url
                db.collection("subjects").add({
                    "name": subject_name,
                    "year": year,
                    "semester": semester,
                    "file_url": file_url
                })
                st.success("교과 등록 완료!")
            else:
                st.error("10MB 이하의 PDF만 업로드 가능합니다.")

    st.markdown("### 🔍 등록된 교과")
    subjects = db.collection("subjects").stream()
    for doc in subjects:
        s = doc.to_dict()
        st.write(f"📘 {s['year']}학년도 {s['semester']}학기 - {s['name']}")
        st.markdown(f"[PDF 보기]({s['file_url']})")

# 2. 수업 등록
elif menu == "수업 등록":
    st.subheader("📚 수업 등록")
    subjects = db.collection("subjects").stream()
    subject_list = [(doc.id, doc.to_dict()) for doc in subjects]
    subject_dict = {f"{s['year']}학년도 {s['semester']}학기 - {s['name']}": sid for sid, s in subject_list}

    with st.form("class_form"):
        class_name = st.text_input("수업 반 (예: 1반)")
        day = st.selectbox("요일", ["월", "화", "수", "목", "금"])
        period = st.selectbox("교시", list(range(1, 9)))
        subject_label = st.selectbox("교과 선택", list(subject_dict.keys()))
        submit = st.form_submit_button("수업 등록")

        if submit:
            db.collection("classes").add({
                "class_name": class_name,
                "day": day,
                "period": period,
                "subject_id": subject_dict[subject_label]
            })
            st.success("수업이 등록되었습니다.")

# 3. 학생 등록
elif menu == "학생 등록":
    st.subheader("👩‍🎓 수업 반별 학생 등록")
    classes = db.collection("classes").stream()
    class_list = [(doc.id, doc.to_dict()) for doc in classes]
    class_dict = {f"{c['class_name']} ({c['day']} {c['period']}교시)": cid for cid, c in class_list}
    selected_class = st.selectbox("수업 반 선택", list(class_dict.keys()))

    tab1, tab2 = st.tabs(["직접 입력", "CSV 업로드"])
    with tab1:
        with st.form("manual_student_form"):
            sid = st.text_input("학번")
            name = st.text_input("이름")
            submit = st.form_submit_button("학생 추가")
            if submit:
                db.collection("students").add({
                    "student_id": sid,
                    "name": name,
                    "class_id": class_dict[selected_class]
                })
                st.success("학생 추가 완료")

    with tab2:
        csv_file = st.file_uploader("CSV 파일 업로드", type="csv")
        if csv_file:
            df = pd.read_csv(csv_file)
            for _, row in df.iterrows():
                db.collection("students").add({
                    "student_id": row["학번"],
                    "name": row["성명"],
                    "class_id": class_dict[selected_class]
                })
            st.success("CSV 학생 목록 등록 완료")

# 4. 진도 및 특기사항 기록
elif menu == "진도 및 특기사항":
    st.subheader("📖 진도 및 특기사항 기록")
    classes = db.collection("classes").stream()
    class_list = [(doc.id, doc.to_dict()) for doc in classes]
    class_dict = {f"{c['class_name']} ({c['day']} {c['period']}교시)": cid for cid, c in class_list}
    selected_class = st.selectbox("수업 반 선택", list(class_dict.keys()))
    date = st.date_input("날짜 선택", datetime.date.today())
    lesson = st.text_input("진도 내용")
    note = st.text_area("특기사항")

    if st.button("기록 저장"):
        db.collection("lesson_logs").add({
            "class_id": class_dict[selected_class],
            "date": str(date),
            "lesson": lesson,
            "note": note
        })
        st.success("기록 저장 완료")

# 5. 출결 및 특기사항
elif menu == "출결 및 특기사항":
    st.subheader("🗓️ 학생 출결 및 특기사항 기록")
    classes = db.collection("classes").stream()
    class_list = [(doc.id, doc.to_dict()) for doc in classes]
    class_dict = {f"{c['class_name']} ({c['day']} {c['period']}교시)": cid for cid, c in class_list}
    selected_class = st.selectbox("수업 반 선택", list(class_dict.keys()))
    date = st.date_input("날짜 선택", datetime.date.today())

    students = db.collection("students").where("class_id", "==", class_dict[selected_class]).stream()
    for doc in students:
        student = doc.to_dict()
        st.markdown(f"**{student['student_id']} - {student['name']}**")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            att = st.checkbox("출석", key=f"att_{doc.id}")
        with col2:
            lat = st.checkbox("지각", key=f"lat_{doc.id}")
        with col3:
            abs = st.checkbox("결석", key=f"abs_{doc.id}")
        with col4:
            lev = st.checkbox("조퇴", key=f"lev_{doc.id}")
        note = st.text_input("특기사항", key=f"note_{doc.id}")

        if st.button("저장", key=f"save_{doc.id}"):
            db.collection("attendance").add({
                "student_id": student['student_id'],
                "class_id": class_dict[selected_class],
                "date": str(date),
                "출석": att,
                "지각": lat,
                "결석": abs,
                "조퇴": lev,
                "note": note
            })
            st.success(f"{student['name']} 저장 완료!")
