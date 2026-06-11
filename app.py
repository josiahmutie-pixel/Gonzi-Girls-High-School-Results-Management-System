import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from io import BytesIO, StringIO
import os
import re

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Gonzi Girls High School Results System",
    page_icon="🎓",
    layout="wide"
)

SAVE_FOLDER = "saved_reports"
os.makedirs(SAVE_FOLDER, exist_ok=True)

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
    font-size: 26px;
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
# HELPER FUNCTIONS
# ============================================================

def system_notice(code, message, notice_type="error"):
    text = f"⚠️ System Notice [{code}]: {message}"
    if notice_type == "error":
        st.error(text)
    elif notice_type == "warning":
        st.warning(text)
    else:
        st.info(text)


def clean_filename(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def grade_code(grade):
    return grade.replace("Grade ", "G")


def prepare_subjects(subjects_text):
    subjects = []
    for subject in subjects_text.split(","):
        subject = subject.strip()
        if subject and subject not in subjects:
            subjects.append(subject)
    return subjects


def get_next_student_id(df, grade):
    prefix = f"GGHS-{grade_code(grade)}-"
    numbers = []

    if "Student ID" in df.columns:
        for sid in df["Student ID"].astype(str):
            sid = sid.strip()
            if sid.startswith(prefix):
                try:
                    numbers.append(int(sid.split("-")[-1]))
                except ValueError:
                    pass

    next_number = max(numbers) + 1 if numbers else 1
    return f"{prefix}{next_number:03d}"


def create_default_table(subjects, grade, n=3):
    rows = []

    for i in range(1, n + 1):
        row = {
            "Student ID": f"GGHS-{grade_code(grade)}-{i:03d}",
            "Student Name": f"Student {i}"
        }

        for subject in subjects:
            row[subject] = 0

        rows.append(row)

    return pd.DataFrame(rows)


def save_editor_changes():
    """
    This function saves changes immediately from st.data_editor.
    It fixes the problem where first-time typed marks disappear.
    """
    if "student_editor_table" not in st.session_state:
        return

    editor_state = st.session_state["student_editor_table"]

    if not isinstance(editor_state, dict):
        return

    current_df = st.session_state.students_df.copy()

    edited_rows = editor_state.get("edited_rows", {})

    for row_index, changes in edited_rows.items():
        row_index = int(row_index)

        if row_index < len(current_df):
            for column_name, new_value in changes.items():
                if column_name in current_df.columns:
                    current_df.at[row_index, column_name] = new_value

    st.session_state.students_df = current_df


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

exam_type = st.sidebar.text_input("Exam Type", value="End Term Examination")

grade = st.sidebar.selectbox(
    "Select Grade",
    ["Grade 9", "Grade 10", "Grade 11", "Grade 12"]
)

term = st.sidebar.selectbox(
    "Select Term",
    ["Term 1", "Term 2", "Term 3"]
)

class_teacher = st.sidebar.text_input("Class Teacher", value="Teacher Name")

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

subjects = prepare_subjects(subjects_text)

if len(subjects) == 0:
    system_notice("SUB-101", "At least one subject is required.", "error")
else:
    st.success(f"Current Subjects: {', '.join(subjects)}")

# ============================================================
# SESSION STATE TABLE
# ============================================================

if "students_df" not in st.session_state:
    st.session_state.students_df = create_default_table(subjects, grade)

if "last_grade" not in st.session_state:
    st.session_state.last_grade = grade

if st.session_state.last_grade != grade:
    st.session_state.students_df = create_default_table(subjects, grade)
    st.session_state.last_grade = grade
    st.rerun()

# ============================================================
# SUBJECT UPDATE
# ============================================================

if st.button("🔄 Apply / Update Subject Columns"):
    save_editor_changes()

    old_df = st.session_state.students_df.copy()

    if "Student ID" not in old_df.columns:
        old_df["Student ID"] = ""

    if "Student Name" not in old_df.columns:
        old_df["Student Name"] = ""

    new_df = old_df[["Student ID", "Student Name"]].copy()

    for subject in subjects:
        if subject in old_df.columns:
            new_df[subject] = old_df[subject]
        else:
            new_df[subject] = 0

    st.session_state.students_df = new_df
    st.success("Subject columns updated successfully.")
    st.rerun()

# ============================================================
# STUDENT MARKS ENTRY
# ============================================================

st.markdown("## 📝 Student Marks Entry Dashboard")

st.warning(
    "Edit names and marks in the table. Student IDs are unique primary keys. "
    "Similar student names are allowed if the Student IDs are different."
)

col_add, col_note = st.columns([1, 3])

with col_add:
    if st.button("➕ Add New Student"):
        save_editor_changes()

        current_df = st.session_state.students_df.copy()
        new_id = get_next_student_id(current_df, grade)

        new_row = {
            "Student ID": new_id,
            "Student Name": ""
        }

        for subject in subjects:
            new_row[subject] = 0

        st.session_state.students_df = pd.concat(
            [current_df, pd.DataFrame([new_row])],
            ignore_index=True
        )

        st.rerun()

with col_note:
    st.info("Use the button to add a new row with the next automatic Student ID.")

column_config = {
    "Student ID": st.column_config.TextColumn(
        "Student ID",
        help="Unique student primary key",
        disabled=True
    ),
    "Student Name": st.column_config.TextColumn(
        "Student Name",
        help="Enter full student name"
    )
}

for subject in subjects:
    column_config[subject] = st.column_config.NumberColumn(
        subject,
        min_value=0,
        max_value=100,
        step=1
    )

st.data_editor(
    st.session_state.students_df,
    num_rows="fixed",
    use_container_width=True,
    column_config=column_config,
    key="student_editor_table",
    on_change=save_editor_changes
)

df = st.session_state.students_df.copy()

# ============================================================
# CLEAN AND CALCULATE RESULTS
# ============================================================

required_columns = ["Student ID", "Student Name"]

for col in required_columns:
    if col not in df.columns:
        df[col] = ""

df["Student ID"] = df["Student ID"].astype(str).str.strip()
df["Student Name"] = df["Student Name"].astype(str).str.strip()

df = df[(df["Student ID"] != "") & (df["Student Name"] != "")]

for subject in subjects:
    if subject in df.columns:
        df[subject] = pd.to_numeric(df[subject], errors="coerce").fillna(0)
        df[subject] = df[subject].clip(lower=0, upper=100)
    else:
        df[subject] = 0

duplicate_ids = (
    df[df["Student ID"].duplicated(keep=False)]["Student ID"]
    .astype(str)
    .unique()
)

has_duplicate_ids = len(duplicate_ids) > 0

if has_duplicate_ids:
    system_notice(
        "ID-409",
        "Repeated Student IDs found. Please correct them before saving or downloading.",
        "error"
    )

if len(subjects) > 0:
    df["Total"] = df[subjects].sum(axis=1)
    df["Mean Score"] = (df["Total"] / len(subjects)).round(2)
else:
    df["Total"] = 0
    df["Mean Score"] = 0

if not df.empty:
    df["Position"] = df["Total"].rank(method="min", ascending=False).astype(int)
    df = df.sort_values(by=["Position", "Student Name"]).reset_index(drop=True)
else:
    df["Position"] = []

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

if total_students > 0 and len(subjects) > 0:
    subject_analysis = pd.DataFrame({
        "Subject": subjects,
        "Grand Total": [df[sub].sum() for sub in subjects],
        "Mean Score": [round(df[sub].mean(), 2) for sub in subjects]
    })

    subject_analysis["Subject Rank"] = subject_analysis["Mean Score"].rank(
        method="min",
        ascending=False
    ).astype(int)

    subject_analysis = subject_analysis.sort_values(
        by="Subject Rank"
    ).reset_index(drop=True)
else:
    subject_analysis = pd.DataFrame(
        columns=["Subject", "Grand Total", "Mean Score", "Subject Rank"]
    )

st.dataframe(subject_analysis, use_container_width=True)

# ============================================================
# VISUALIZATION
# ============================================================

st.markdown("## 📈 Results Visualization Dashboard")

if not subject_analysis.empty:
    fig_subject = px.bar(
        subject_analysis,
        x="Subject",
        y="Mean Score",
        text="Mean Score",
        title="Subject Mean Score Performance"
    )
    fig_subject.update_traces(textposition="outside")
    fig_subject.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_subject, use_container_width=True)

if not df.empty:
    fig_students = px.bar(
        df,
        x="Student Name",
        y="Total",
        text="Position",
        title="Student Total Marks and Class Positions"
    )
    fig_students.update_traces(textposition="outside")
    fig_students.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig_students, use_container_width=True)

# ============================================================
# EXCEL CREATOR
# ============================================================

def create_excel_file(df, subject_analysis):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book

        title_format = workbook.add_format({
            "bold": True,
            "font_size": 20,
            "align": "center",
            "valign": "vcenter",
            "bg_color": "#002147",
            "font_color": "white"
        })

        subtitle_format = workbook.add_format({
            "bold": True,
            "font_size": 13,
            "align": "center",
            "bg_color": "#FFD700",
            "font_color": "#002147"
        })

        label_format = workbook.add_format({
            "bold": True,
            "bg_color": "#D9EAF7",
            "border": 1
        })

        value_format = workbook.add_format({"border": 1})

        header_format = workbook.add_format({
            "bold": True,
            "bg_color": "#004080",
            "font_color": "white",
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        cell_format = workbook.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter"
        })

        name_format = workbook.add_format({
            "border": 1,
            "align": "left",
            "valign": "vcenter"
        })

        top_position_format = workbook.add_format({
            "border": 1,
            "align": "center",
            "bg_color": "#E2F0D9",
            "bold": True
        })

        subject_format = workbook.add_format({
            "border": 1,
            "align": "center",
            "bg_color": "#FFF2CC"
        })

        # Student Results Sheet
        sheet_name = "Student Results"
        worksheet = workbook.add_worksheet(sheet_name)
        writer.sheets[sheet_name] = worksheet

        last_col = max(len(df.columns) - 1, 5)

        worksheet.merge_range(0, 0, 0, last_col, "GONZI GIRLS HIGH SCHOOL", title_format)
        worksheet.merge_range(1, 0, 1, last_col, "STUDENT EXAMINATION RESULTS SHEET", subtitle_format)

        worksheet.write(3, 0, "Exam Type:", label_format)
        worksheet.write(3, 1, exam_type, value_format)
        worksheet.write(3, 2, "Grade:", label_format)
        worksheet.write(3, 3, grade, value_format)
        worksheet.write(3, 4, "Term:", label_format)
        worksheet.write(3, 5, term, value_format)

        worksheet.write(4, 0, "Class Teacher:", label_format)
        worksheet.write(4, 1, class_teacher, value_format)
        worksheet.write(4, 2, "Date Recorded:", label_format)
        worksheet.write(4, 3, record_date, value_format)

        start_row = 7

        for col_num, col_name in enumerate(df.columns):
            worksheet.write(start_row, col_num, col_name, header_format)

        for row_num in range(len(df)):
            for col_num, col_name in enumerate(df.columns):
                value = df.iloc[row_num][col_name]

                if col_name == "Student Name":
                    worksheet.write(row_num + start_row + 1, col_num, value, name_format)
                elif col_name == "Position" and value == 1:
                    worksheet.write(row_num + start_row + 1, col_num, value, top_position_format)
                else:
                    worksheet.write(row_num + start_row + 1, col_num, value, cell_format)

        worksheet.freeze_panes(start_row + 1, 2)
        worksheet.autofilter(start_row, 0, start_row + len(df), len(df.columns) - 1)

        worksheet.set_column(0, 0, 18)
        worksheet.set_column(1, 1, 25)
        worksheet.set_column(2, len(df.columns) - 1, 15)

        # Subject Analysis Sheet
        sheet2 = "Subject Analysis"
        worksheet2 = workbook.add_worksheet(sheet2)
        writer.sheets[sheet2] = worksheet2

        worksheet2.merge_range(0, 0, 0, 4, "GONZI GIRLS HIGH SCHOOL", title_format)
        worksheet2.merge_range(1, 0, 1, 4, "SUBJECT PERFORMANCE ANALYSIS", subtitle_format)

        worksheet2.write(3, 0, "Exam Type:", label_format)
        worksheet2.write(3, 1, exam_type, value_format)
        worksheet2.write(3, 2, "Grade:", label_format)
        worksheet2.write(3, 3, grade, value_format)
        worksheet2.write(4, 0, "Term:", label_format)
        worksheet2.write(4, 1, term, value_format)
        worksheet2.write(4, 2, "Date Recorded:", label_format)
        worksheet2.write(4, 3, record_date, value_format)

        start_row2 = 6

        for col_num, col_name in enumerate(subject_analysis.columns):
            worksheet2.write(start_row2, col_num, col_name, header_format)

        for row_num in range(len(subject_analysis)):
            for col_num, col_name in enumerate(subject_analysis.columns):
                worksheet2.write(
                    row_num + start_row2 + 1,
                    col_num,
                    subject_analysis.iloc[row_num][col_name],
                    subject_format
                )

        worksheet2.set_column(0, 0, 25)
        worksheet2.set_column(1, 3, 18)

        if not subject_analysis.empty:
            chart = workbook.add_chart({"type": "column"})
            chart.add_series({
                "name": "Mean Score",
                "categories": [sheet2, start_row2 + 1, 0, start_row2 + len(subject_analysis), 0],
                "values": [sheet2, start_row2 + 1, 2, start_row2 + len(subject_analysis), 2],
                "data_labels": {"value": True}
            })
            chart.set_title({"name": "Subject Mean Score Performance"})
            chart.set_x_axis({"name": "Subjects"})
            chart.set_y_axis({"name": "Mean Score"})
            chart.set_style(10)

            worksheet2.insert_chart("F3", chart, {"x_scale": 1.6, "y_scale": 1.4})

    output.seek(0)
    return output


# ============================================================
# CSV CREATOR
# ============================================================

def create_full_csv(df, subject_analysis):
    output = StringIO()

    output.write("GONZI GIRLS HIGH SCHOOL\n")
    output.write("STUDENT EXAMINATION RESULTS SHEET\n")
    output.write(f"Exam Type,{exam_type}\n")
    output.write(f"Grade,{grade}\n")
    output.write(f"Term,{term}\n")
    output.write(f"Class Teacher,{class_teacher}\n")
    output.write(f"Date Recorded,{record_date}\n")
    output.write("\n")

    output.write("STUDENT RESULTS\n")
    df.to_csv(output, index=False)

    output.write("\nSUBJECT PERFORMANCE ANALYSIS\n")
    subject_analysis.to_csv(output, index=False)

    return output.getvalue()


excel_file = create_excel_file(df, subject_analysis)
csv_file = create_full_csv(df, subject_analysis)

file_base_name = clean_filename(f"{grade}_{term}_{exam_type}_Results")
excel_filename = f"{file_base_name}.xlsx"
csv_filename = f"{file_base_name}.csv"

# ============================================================
# DOWNLOAD AND SAVE SECTION
# ============================================================

st.markdown("## 📥 Download Results Sheet")

if has_duplicate_ids:
    system_notice(
        "SAVE-409",
        "Download and saving are locked until repeated Student IDs are corrected.",
        "warning"
    )
else:
    st.download_button(
        label="📥 Download Decorated Excel Results Sheet",
        data=excel_file,
        file_name=excel_filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.download_button(
        label="📄 Download Full CSV Results",
        data=csv_file,
        file_name=csv_filename,
        mime="text/csv"
    )

    if st.button("💾 Save Excel and CSV for Future Reference"):
        excel_path = os.path.join(SAVE_FOLDER, excel_filename)
        csv_path = os.path.join(SAVE_FOLDER, csv_filename)

        with open(excel_path, "wb") as f:
            f.write(excel_file.getvalue())

        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(csv_file)

        st.success("Files saved successfully for future reference.")

# ============================================================
# SAVED FILES MANAGER
# ============================================================

st.markdown("## 🗂️ Saved Reports Manager")

saved_files = sorted(os.listdir(SAVE_FOLDER))

if len(saved_files) == 0:
    st.info("No saved reports yet.")
else:
    selected_file = st.selectbox("Select saved file", saved_files)
    selected_path = os.path.join(SAVE_FOLDER, selected_file)

    with open(selected_path, "rb") as f:
        st.download_button(
            label="⬇️ Download Selected Saved File",
            data=f.read(),
            file_name=selected_file
        )

    if st.button("🗑️ Delete Selected Saved File"):
        os.remove(selected_path)
        st.success(f"{selected_file} deleted successfully.")
        st.rerun()

# ============================================================
# FOOTER
# ============================================================

st.markdown("""
<hr>
<center>
<b>Gonzi Girls High School Results System</b><br>
Designed for accurate ranking, subject analysis, clean academic reporting, and future record keeping.
</center>
""", unsafe_allow_html=True)
