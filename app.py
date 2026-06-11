import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Gonzi Girls High School Results System",
    page_icon="🎓",
    layout="wide"
)

# ============================================================
# CSS DESIGN
# ============================================================

st.markdown("""
<style>
.main {
    background-color: #f5f7fb;
}

.school-title {
    background: linear-gradient(90deg, #002147, #004080);
    color: white;
    padding: 25px;
    border-radius: 15px;
    text-align: center;
    font-size: 38px;
    font-weight: bold;
    letter-spacing: 1px;
}

.subtitle {
    color: #ffd700;
    font-size: 20px;
    text-align: center;
    margin-top: -10px;
}

.section-box {
    background-color: white;
    padding: 20px;
    border-radius: 14px;
    box-shadow: 0px 3px 12px rgba(0,0,0,0.08);
    margin-top: 20px;
}

.metric-card {
    background: linear-gradient(135deg, #ffffff, #eaf2ff);
    padding: 18px;
    border-radius: 14px;
    text-align: center;
    border-left: 6px solid #004080;
    box-shadow: 0px 2px 8px rgba(0,0,0,0.08);
}

.metric-title {
    font-size: 15px;
    color: #555;
}

.metric-value {
    font-size: 28px;
    color: #002147;
    font-weight: bold;
}

.stButton>button {
    background-color: #004080;
    color: white;
    border-radius: 10px;
    height: 45px;
    font-weight: bold;
}

.stDownloadButton>button {
    background-color: #006400;
    color: white;
    border-radius: 10px;
    height: 45px;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# TITLE
# ============================================================

st.markdown("""
<div class="school-title">
    GONZI GIRLS HIGH SCHOOL
    <div class="subtitle">Student Examination Results Management System</div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR SETTINGS
# ============================================================

st.sidebar.title("⚙️ Results Settings")

exam_type = st.sidebar.text_input(
    "Exam Type",
    value="End Term Examination"
)

grade = st.sidebar.selectbox(
    "Select Grade",
    ["Grade 9", "Grade 10", "Grade 11", "Grade 12"]
)

term = st.sidebar.selectbox(
    "Select Term",
    ["Term 1", "Term 2", "Term 3"]
)

class_teacher = st.sidebar.text_input(
    "Class Teacher",
    value="Teacher Name"
)

record_date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

st.sidebar.info(f"📅 Date Recorded: {record_date}")

# ============================================================
# EDITABLE SUBJECTS
# ============================================================

st.markdown("## 📚 Editable Subject List")

default_subjects = [
    "English",
    "Kiswahili",
    "Mathematics",
    "Science",
    "Agriculture",
    "Pre-Technical",
    "Social Studies",
    "C.R.E",
    "Creative Arts",
    "I.T"
]

subjects_text = st.text_area(
    "Enter subjects separated by commas",
    value=", ".join(default_subjects),
    height=100
)

subjects = [s.strip() for s in subjects_text.split(",") if s.strip()]

st.success(f"Current Subjects: {', '.join(subjects)}")

# ============================================================
# CREATE DEFAULT STUDENT TABLE
# ============================================================

def create_default_table(subjects):
    data = {
        "Student ID": ["GGHS-001", "GGHS-002", "GGHS-003"],
        "Student Name": ["Student One", "Student Two", "Student Three"]
    }

    for subject in subjects:
        data[subject] = [0, 0, 0]

    return pd.DataFrame(data)


if "students_df" not in st.session_state:
    st.session_state.students_df = create_default_table(subjects)

# Reset table if subjects change
if st.button("🔄 Apply / Update Subject Columns"):
    st.session_state.students_df = create_default_table(subjects)
    st.success("Subject columns updated successfully.")

# ============================================================
# STUDENT MARKS ENTRY
# ============================================================

st.markdown("## 📝 Student Marks Entry Dashboard")

st.warning(
    "You can edit student IDs, names, marks, add rows, or delete rows directly in the table."
)

edited_df = st.data_editor(
    st.session_state.students_df,
    num_rows="dynamic",
    use_container_width=True
)

# ============================================================
# CLEAN AND CALCULATE RESULTS
# ============================================================

df = edited_df.copy()

# Ensure all subject marks are numeric
for subject in subjects:
    if subject in df.columns:
        df[subject] = pd.to_numeric(df[subject], errors="coerce").fillna(0)

# Remove empty students
df = df[df["Student ID"].astype(str).str.strip() != ""]
df = df[df["Student Name"].astype(str).str.strip() != ""]

# Avoid duplicate student IDs
if df["Student ID"].duplicated().any():
    st.error("⚠️ Duplicate Student IDs detected. Please make every Student ID unique.")

# Calculate total and mean
if len(subjects) > 0:
    df["Total"] = df[subjects].sum(axis=1)
    df["Mean Score"] = df["Total"] / len(subjects)
else:
    df["Total"] = 0
    df["Mean Score"] = 0

# Rank students
df["Position"] = df["Total"].rank(
    method="min",
    ascending=False
).astype(int)

df = df.sort_values(by=["Position", "Student Name"])

# ============================================================
# CLASS SUMMARY
# ============================================================

st.markdown("## 📊 Class Performance Summary")

total_students = len(df)
class_mean = round(df["Mean Score"].mean(), 2) if total_students > 0 else 0
best_student = df.iloc[0]["Student Name"] if total_students > 0 else "N/A"
best_total = df.iloc[0]["Total"] if total_students > 0 else 0

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Students</div>
        <div class="metric-value">{total_students}</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Class Mean</div>
        <div class="metric-value">{class_mean}</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Best Student</div>
        <div class="metric-value">{best_student}</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Best Total</div>
        <div class="metric-value">{best_total}</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# FINAL RESULTS TABLE
# ============================================================

st.markdown("## 🏆 Final Ranked Results")

st.dataframe(df, use_container_width=True)

# ============================================================
# SUBJECT PERFORMANCE
# ============================================================

st.markdown("## 📘 Subject Performance Analysis")

subject_analysis = pd.DataFrame({
    "Subject": subjects,
    "Grand Total": [df[sub].sum() for sub in subjects],
    "Mean Score": [round(df[sub].mean(), 2) for sub in subjects]
})

subject_analysis["Subject Rank"] = subject_analysis["Mean Score"].rank(
    method="min",
    ascending=False
).astype(int)

subject_analysis = subject_analysis.sort_values(by="Subject Rank")

st.dataframe(subject_analysis, use_container_width=True)

# ============================================================
# EXCEL DOWNLOAD FUNCTION
# ============================================================

def create_excel_file(df, subject_analysis):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book

        title_format = workbook.add_format({
            "bold": True,
            "font_size": 18,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#002147",
            "font_color": "white"
        })

        subtitle_format = workbook.add_format({
            "bold": True,
            "font_size": 12,
            "align": "center",
            "bg_color": "#FFD700",
            "font_color": "#002147"
        })

        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#004080",
            "font_color": "white",
            "border": 1,
            "align": "center"
        })

        cell_format = workbook.add_format({
            "border": 1,
            "align": "center"
        })

        mean_format = workbook.add_format({
            "border": 1,
            "align": "center",
            "bg_color": "#E2F0D9"
        })

        # Results sheet
        df.to_excel(writer, sheet_name="Student Results", startrow=7, index=False)
        worksheet = writer.sheets["Student Results"]

        worksheet.merge_range("A1:E1", "GONZI GIRLS HIGH SCHOOL", title_format)
        worksheet.merge_range("A2:E2", "STUDENT EXAMINATION RESULTS SHEET", subtitle_format)

        worksheet.write("A4", "Exam Type:")
        worksheet.write("B4", exam_type)

        worksheet.write("C4", "Grade:")
        worksheet.write("D4", grade)

        worksheet.write("E4", "Term:")
        worksheet.write("F4", term)

        worksheet.write("A5", "Class Teacher:")
        worksheet.write("B5", class_teacher)

        worksheet.write("C5", "Date Recorded:")
        worksheet.write("D5", record_date)

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(7, col_num, value, header_format)

        for row in range(len(df)):
            for col in range(len(df.columns)):
                worksheet.write(row + 8, col, df.iloc[row, col], cell_format)

        worksheet.set_column(0, len(df.columns), 16)
        worksheet.set_column(1, 1, 25)

        # Subject analysis sheet
        subject_analysis.to_excel(
            writer,
            sheet_name="Subject Analysis",
            startrow=5,
            index=False
        )

        worksheet2 = writer.sheets["Subject Analysis"]
        worksheet2.merge_range("A1:D1", "GONZI GIRLS HIGH SCHOOL", title_format)
        worksheet2.merge_range("A2:D2", "SUBJECT PERFORMANCE ANALYSIS", subtitle_format)

        for col_num, value in enumerate(subject_analysis.columns.values):
            worksheet2.write(5, col_num, value, header_format)

        for row in range(len(subject_analysis)):
            for col in range(len(subject_analysis.columns)):
                worksheet2.write(row + 6, col, subject_analysis.iloc[row, col], mean_format)

        worksheet2.set_column(0, 4, 22)

    output.seek(0)
    return output


excel_file = create_excel_file(df, subject_analysis)

# ============================================================
# DOWNLOAD SECTION
# ============================================================

st.markdown("## 📥 Download Results Sheet")

st.download_button(
    label="📥 Download Decorated Excel Results Sheet",
    data=excel_file,
    file_name=f"{grade}_{term}_{exam_type}_Results.xlsx".replace(" ", "_"),
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

st.download_button(
    label="📄 Download CSV Results",
    data=df.to_csv(index=False),
    file_name=f"{grade}_{term}_Results.csv".replace(" ", "_"),
    mime="text/csv"
)

# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<hr>
<center>
<b>Gonzi Girls High School Results System</b><br>
Designed for accurate ranking, subject analysis, and clean academic reporting.
</center>
""", unsafe_allow_html=True)
