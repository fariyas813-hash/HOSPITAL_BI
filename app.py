import os
import sqlite3
import random
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

# ---------------------------------------------------------
# 1. FLASK APPLICATION INITIALIZATION
# ---------------------------------------------------------
app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "hospital_bi.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------
# 2. AUTO-DATABASE SETUP & SEEDING (Self-Healing)
# ---------------------------------------------------------
def setup_database_if_empty():
    conn = get_db()
    cursor = conn.cursor()

    # Create tables if not present
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS departments (
        department_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_name TEXT UNIQUE NOT NULL,
        total_beds INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS doctors (
        doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_name TEXT NOT NULL,
        department_id INTEGER,
        specialization TEXT,
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );

    CREATE TABLE IF NOT EXISTS beds (
        bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bed_number TEXT UNIQUE NOT NULL,
        department_id INTEGER,
        bed_type TEXT,
        status TEXT CHECK(status IN ('Available', 'Occupied', 'Maintenance')),
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );

    CREATE TABLE IF NOT EXISTS patients (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT,
        contact TEXT,
        blood_group TEXT
    );

    CREATE TABLE IF NOT EXISTS admissions (
        admission_id INTEGER PRIMARY KEY AUTOINCREMENT,
        patient_id INTEGER NOT NULL,
        department_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        bed_id INTEGER,
        admission_date TEXT NOT NULL,
        discharge_date TEXT,
        status TEXT CHECK(status IN ('Admitted', 'Discharged')),
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
        FOREIGN KEY (department_id) REFERENCES departments(department_id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
        FOREIGN KEY (bed_id) REFERENCES beds(bed_id)
    );

    CREATE TABLE IF NOT EXISTS treatments (
        treatment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        treatment_name TEXT NOT NULL,
        patient_id INTEGER NOT NULL,
        doctor_id INTEGER NOT NULL,
        department_id INTEGER NOT NULL,
        treatment_date TEXT NOT NULL,
        status TEXT,
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
        FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id),
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );
    """)

    # Check if data already exists
    cursor.execute("SELECT COUNT(*) FROM departments")
    if cursor.fetchone()[0] == 0:
        print("[*] Empty database detected. Seeding realistic sample hospital data...")
        
        # 1. Departments
        depts = [
            ("ICU", 30),
            ("Cardiology", 50),
            ("General Medicine", 60),
            ("Neurology", 40),
            ("Orthopedics", 40),
            ("Pediatrics", 30)
        ]
        cursor.executemany("INSERT INTO departments (department_name, total_beds) VALUES (?, ?)", depts)

        # 2. Beds
        for dept_id, (_, total) in enumerate(depts, 1):
            for b in range(1, total + 1):
                cursor.execute(
                    "INSERT INTO beds (bed_number, department_id, bed_type, status) VALUES (?, ?, ?, 'Available')",
                    (f"D{dept_id}-B{b:03d}", dept_id, "Standard")
                )

        # 3. Doctors
        docs = [
            ("Dr. Arvind Sharma", 1, "Critical Care"),
            ("Dr. Sunita Mehta", 2, "Cardiology"),
            ("Dr. Rajesh Gupta", 3, "Internal Medicine"),
            ("Dr. Farhan Qureshi", 4, "Neurology"),
            ("Dr. Kavita Iyer", 5, "Orthopedics"),
            ("Dr. Rohan Kulkarni", 6, "Pediatrics"),
            ("Dr. Anand Deshmukh", 2, "Cardiology"),
            ("Dr. Preeti Verma", 3, "General Medicine")
        ]
        cursor.executemany("INSERT INTO doctors (doctor_name, department_id, specialization) VALUES (?, ?, ?)", docs)

        # 4. Historical Patients (Discharged)
        first_names = ["Rahul", "Priya", "Aarav", "Neha", "Ahmed", "Deepak", "Sneha", "Vikram", "Pooja", "Amit"]
        last_names = ["Sharma", "Patel", "Khan", "Verma", "Joshi", "Iyer", "Nair", "Kulkarni", "Singh", "Reddy"]
        treatments_list = ["Cardiac Catheterization", "General Checkup", "Physiotherapy", "Neurological Workup", "IV Fluid Therapy", "Fracture Reduction"]

        base_date = datetime.now() - timedelta(days=90)
        for _ in range(260):
            p_name = f"{random.choice(first_names)} {random.choice(last_names)}"
            cursor.execute("INSERT INTO patients (name, age, gender, contact, blood_group) VALUES (?, ?, ?, '9876543210', 'B+')",
                           (p_name, random.randint(10, 80), random.choice(["Male", "Female"])))
            pid = cursor.lastrowid
            dept_id = random.randint(1, len(depts))
            doc_id = random.randint(1, len(docs))
            
            adm_delta = random.randint(0, 75)
            stay_len = random.randint(2, 9)
            adm_date = (base_date + timedelta(days=adm_delta)).strftime("%Y-%m-%d")
            dis_date = (base_date + timedelta(days=adm_delta + stay_len)).strftime("%Y-%m-%d")

            cursor.execute("""
                INSERT INTO admissions (patient_id, department_id, doctor_id, admission_date, discharge_date, status)
                VALUES (?, ?, ?, ?, ?, 'Discharged')
            """, (pid, dept_id, doc_id, adm_date, dis_date))

            cursor.execute("""
                INSERT INTO treatments (treatment_name, patient_id, doctor_id, department_id, treatment_date, status)
                VALUES (?, ?, ?, ?, ?, 'Completed')
            """, (random.choice(treatments_list), pid, doc_id, dept_id, adm_date))

        # 5. Currently Admitted Patients & Bed Statuses
        cursor.execute("SELECT bed_id, department_id FROM beds")
        all_beds = cursor.fetchall()
        for bed_id, dept_id in all_beds:
            roll = random.random()
            if roll < 0.76:  # Occupied
                cursor.execute("UPDATE beds SET status = 'Occupied' WHERE bed_id = ?", (bed_id,))
                p_name = f"{random.choice(first_names)} {random.choice(last_names)}"
                cursor.execute("INSERT INTO patients (name, age, gender, contact, blood_group) VALUES (?, ?, ?, '9876500000', 'O+')",
                               (p_name, random.randint(12, 85), random.choice(["Male", "Female"])))
                pid = cursor.lastrowid
                adm_date = (datetime.now() - timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")
                doc_id = random.randint(1, len(docs))
                
                cursor.execute("""
                    INSERT INTO admissions (patient_id, department_id, doctor_id, bed_id, admission_date, status)
                    VALUES (?, ?, ?, ?, ?, 'Admitted')
                """, (pid, dept_id, doc_id, bed_id, adm_date))

                cursor.execute("""
                    INSERT INTO treatments (treatment_name, patient_id, doctor_id, department_id, treatment_date, status)
                    VALUES (?, ?, ?, ?, ?, 'Active')
                """, (random.choice(treatments_list), pid, doc_id, dept_id, adm_date))
            elif roll > 0.95:  # Maintenance
                cursor.execute("UPDATE beds SET status = 'Maintenance' WHERE bed_id = ?", (bed_id,))

        conn.commit()
        print("[✓] Sample hospital database ready.")
        
    conn.close()


# ---------------------------------------------------------
# 3. ROUTE: FRONTEND DASHBOARD
# ---------------------------------------------------------
@app.route("/")
def dashboard():
    return render_template("advanced_dashboard.html")


# ---------------------------------------------------------
# 4. ROUTE: ADVANCED ANALYTICS API
# ---------------------------------------------------------
@app.route("/api/advanced-analytics", methods=["GET"])
def advanced_analytics():
    conn = get_db()
    dept = request.args.get("department", "All")

    # Read relevant data
    df_adm = pd.read_sql_query("""
        SELECT a.*, d.department_name, doc.doctor_name, p.age, p.gender, p.name as patient_name
        FROM admissions a
        JOIN departments d ON a.department_id = d.department_id
        JOIN doctors doc ON a.doctor_id = doc.doctor_id
        JOIN patients p ON a.patient_id = p.patient_id
    """, conn)

    df_beds = pd.read_sql_query("""
        SELECT b.*, d.department_name 
        FROM beds b
        JOIN departments d ON b.department_id = d.department_id
    """, conn)

    df_treatments = pd.read_sql_query("""
        SELECT t.*, d.department_name 
        FROM treatments t
        JOIN departments d ON t.department_id = d.department_id
    """, conn)
    conn.close()

    # Department filtering
    if dept != "All":
        df_adm = df_adm[df_adm["department_name"] == dept]
        df_beds = df_beds[df_beds["department_name"] == dept]
        df_treatments = df_treatments[df_treatments["department_name"] == dept]

    # KPIs Calculation
    total_beds = len(df_beds)
    occupied_beds = len(df_beds[df_beds["status"] == "Occupied"])
    available_beds = len(df_beds[df_beds["status"] == "Available"])
    maint_beds = len(df_beds[df_beds["status"] == "Maintenance"])
    occupancy_rate = round((occupied_beds / total_beds * 100), 1) if total_beds > 0 else 0

    # ALOS (Average Length of Stay)
    discharged = df_adm[df_adm["status"] == "Discharged"].copy()
    if not discharged.empty and "discharge_date" in discharged:
        discharged["admission_date"] = pd.to_datetime(discharged["admission_date"])
        discharged["discharge_date"] = pd.to_datetime(discharged["discharge_date"])
        discharged["stay_days"] = (discharged["discharge_date"] - discharged["admission_date"]).dt.days
        avg_stay = round(float(discharged["stay_days"].mean()), 1)
    else:
        avg_stay = 0.0

    # Predictive Demand Forecast (Linear trend / Polyfit)
    df_adm["admission_date"] = pd.to_datetime(df_adm["admission_date"])
    daily_adm = df_adm.set_index("admission_date").resample("D").size().fillna(0)

    if len(daily_adm) > 5:
        x = np.arange(len(daily_adm))
        y = daily_adm.values
        slope, intercept = np.polyfit(x, y, 1)
        future_x = np.arange(len(daily_adm), len(daily_adm) + 14)
        future_y = np.clip(slope * future_x + intercept, a_min=0, a_max=None).round(1).tolist()
        future_dates = [(daily_adm.index[-1] + pd.Timedelta(days=i)).strftime("%b %d") for i in range(1, 15)]
    else:
        future_dates, future_y = [], []

    # Active Doctor Workload
    active_admissions = df_adm[df_adm["status"] == "Admitted"]
    doctor_workload = active_admissions.groupby("doctor_name").size().reset_index(name="patient_count")
    doctor_workload = doctor_workload.sort_values(by="patient_count", ascending=False).head(8)

    # Inflow vs Outflow Trends
    df_adm["adm_month"] = df_adm["admission_date"].dt.strftime("%Y-%m")
    adm_trend = df_adm.groupby("adm_month").size()
    dis_trend = discharged.groupby(discharged["discharge_date"].dt.strftime("%Y-%m")).size() if not discharged.empty else pd.Series(dtype=int)

    months = sorted(list(set(adm_trend.index).union(set(dis_trend.index))))
    inflow_outflow = {
        "labels": months,
        "admissions": [int(adm_trend.get(m, 0)) for m in months],
        "discharges": [int(dis_trend.get(m, 0)) for m in months]
    }

    # Bed Heatmap Matrix Data (64 beds max for clean responsive grid layout)
    bed_matrix = df_beds[["bed_number", "department_name", "bed_type", "status"]].to_dict(orient="records")

    return jsonify({
        "kpis": {
            "total_patients": int(df_adm["patient_id"].nunique()) if not df_adm.empty else 0,
            "currently_admitted": int(len(active_admissions)),
            "available_beds": available_beds,
            "occupied_beds": occupied_beds,
            "maintenance_beds": maint_beds,
            "total_beds": total_beds,
            "bed_occupancy_rate": occupancy_rate,
            "avg_stay": avg_stay
        },
        "forecast": {
            "labels": future_dates,
            "values": future_y
        },
        "doctor_workload": {
            "doctors": doctor_workload["doctor_name"].tolist() if not doctor_workload.empty else [],
            "patients": doctor_workload["patient_count"].tolist() if not doctor_workload.empty else []
        },
        "inflow_outflow": inflow_outflow,
        "top_treatments": df_treatments["treatment_name"].value_counts().head(6).to_dict() if not df_treatments.empty else {},
        "bed_matrix": bed_matrix[:64]
    })


# ---------------------------------------------------------
# 5. ROUTE: DATASET FILE UPLOAD (CSV / XLSX)
# ---------------------------------------------------------
@app.route("/api/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part in request"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "Empty file selected"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        try:
            if filename.endswith(".csv"):
                df_upload = pd.read_csv(filepath)
            else:
                df_upload = pd.read_excel(filepath)

            df_upload.columns = df_upload.columns.str.strip().str.lower()

            required_cols = {"name", "age", "gender", "department", "doctor", "admission_date", "status"}
            if not required_cols.issubset(set(df_upload.columns)):
                return jsonify({
                    "success": False,
                    "message": f"Format invalid! Required columns: {', '.join(required_cols)}"
                }), 400

            conn = get_db()
            cursor = conn.cursor()

            imported_count = 0
            for _, row in df_upload.iterrows():
                # Department resolve/insert
                cursor.execute("SELECT department_id FROM departments WHERE department_name = ?", (str(row["department"]),))
                dept = cursor.fetchone()
                if dept:
                    dept_id = dept["department_id"]
                else:
                    cursor.execute("INSERT INTO departments (department_name, total_beds) VALUES (?, 30)", (str(row["department"]),))
                    dept_id = cursor.lastrowid

                # Doctor resolve/insert
                cursor.execute("SELECT doctor_id FROM doctors WHERE doctor_name = ?", (str(row["doctor"]),))
                doc = cursor.fetchone()
                if doc:
                    doc_id = doc["doctor_id"]
                else:
                    cursor.execute("INSERT INTO doctors (doctor_name, department_id, specialization) VALUES (?, ?, 'General')", 
                                   (str(row["doctor"]), dept_id))
                    doc_id = cursor.lastrowid

                # Patient insert
                cursor.execute(
                    "INSERT INTO patients (name, age, gender, contact, blood_group) VALUES (?, ?, ?, ?, ?)",
                    (str(row["name"]), int(row["age"]), str(row["gender"]), str(row.get("contact", "9876543210")), str(row.get("blood_group", "O+")))
                )
                patient_id = cursor.lastrowid

                # Admission record
                dis_date = str(row["discharge_date"]) if pd.notna(row.get("discharge_date")) and str(row.get("discharge_date")).strip() != "" else None
                status = str(row["status"]).capitalize()

                cursor.execute("""
                    INSERT INTO admissions (patient_id, department_id, doctor_id, admission_date, discharge_date, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (patient_id, dept_id, doc_id, str(row["admission_date"]), dis_date, status))

                # Treatment record
                treatment_name = str(row.get("treatment", "General Consultation"))
                cursor.execute("""
                    INSERT INTO treatments (treatment_name, patient_id, doctor_id, department_id, treatment_date, status)
                    VALUES (?, ?, ?, ?, ?, 'Active')
                """, (treatment_name, patient_id, doc_id, dept_id, str(row["admission_date"])))

                imported_count += 1

            conn.commit()
            conn.close()

            # Clean up uploaded file
            if os.path.exists(filepath):
                os.remove(filepath)

            return jsonify({
                "success": True,
                "message": f"{imported_count} records imported into database successfully!"
            })

        except Exception as e:
            return jsonify({"success": False, "message": f"Parsing Error: {str(e)}"}), 500

    return jsonify({"success": False, "message": "Allowed formats: CSV, XLSX"}), 400


# ---------------------------------------------------------
# 6. APP RUNNER
# ---------------------------------------------------------
if __name__ == "__main__":
    setup_database_if_empty()
    print("\n🚀 MediCore BI Server running at: http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)