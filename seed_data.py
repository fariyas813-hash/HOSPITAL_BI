import sqlite3
import random
from datetime import datetime, timedelta

DB_FILE = "hospital_bi.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Drop existing tables if rebuilding
    cursor.executescript('''
    DROP TABLE IF EXISTS treatments;
    DROP TABLE IF EXISTS admissions;
    DROP TABLE IF EXISTS beds;
    DROP TABLE IF EXISTS doctors;
    DROP TABLE IF EXISTS patients;
    DROP TABLE IF EXISTS departments;

    CREATE TABLE departments (
        department_id INTEGER PRIMARY KEY AUTOINCREMENT,
        department_name TEXT UNIQUE NOT NULL,
        total_beds INTEGER NOT NULL
    );

    CREATE TABLE doctors (
        doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        doctor_name TEXT NOT NULL,
        department_id INTEGER,
        specialization TEXT,
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );

    CREATE TABLE beds (
        bed_id INTEGER PRIMARY KEY AUTOINCREMENT,
        bed_number TEXT UNIQUE NOT NULL,
        department_id INTEGER,
        bed_type TEXT,
        status TEXT CHECK(status IN ('Available', 'Occupied', 'Reserved', 'Maintenance')),
        FOREIGN KEY (department_id) REFERENCES departments(department_id)
    );

    CREATE TABLE patients (
        patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT CHECK(gender IN ('Male', 'Female', 'Other')),
        contact TEXT,
        blood_group TEXT
    );

    CREATE TABLE admissions (
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

    CREATE TABLE treatments (
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
    ''')

    # Seed Departments
    dept_specs = [
        ("ICU", 30),
        ("Cardiology", 50),
        ("General Medicine", 60),
        ("Neurology", 40),
        ("Orthopedics", 40),
        ("Pediatrics", 30)
    ]
    cursor.executemany("INSERT INTO departments (department_name, total_beds) VALUES (?, ?)", dept_specs)

    # Seed Beds
    bed_types = ['Standard', 'Deluxe', 'ICU Special']
    for dept_id, (_, total) in enumerate(dept_specs, 1):
        for i in range(1, total + 1):
            b_type = 'ICU Special' if dept_id == 1 else random.choice(bed_types[:2])
            cursor.execute(
                "INSERT INTO beds (bed_number, department_id, bed_type, status) VALUES (?, ?, ?, 'Available')",
                (f"D{dept_id}-B{i:03d}", dept_id, b_type)
            )

    # Seed Doctors
    docs = [
        ("Dr. Arvind Sharma", 1, "Critical Care"),
        ("Dr. Sunita Mehta", 2, "Cardiology"),
        ("Dr. Rajesh Gupta", 3, "Internal Medicine"),
        ("Dr. Farhan Qureshi", 4, "Neurology"),
        ("Dr. Kavita Iyer", 5, "Orthopedic Surgery"),
        ("Dr. Rohan Kulkarni", 6, "Pediatrics"),
        ("Dr. Anand Deshmukh", 2, "Cardiology"),
        ("Dr. Preeti Verma", 3, "General Medicine")
    ]
    cursor.executemany("INSERT INTO doctors (doctor_name, department_id, specialization) VALUES (?, ?, ?)", docs)

    # Seed Patients & History over the last 90 days
    first_names = ["Rahul", "Priya", "Aarav", "Neha", "Ahmed", "Deepak", "Sneha", "Vikram", "Pooja", "Amit"]
    last_names = ["Sharma", "Patel", "Khan", "Verma", "Joshi", "Iyer", "Nair", "Kulkarni", "Singh", "Reddy"]
    treatments_pool = ["General Checkup", "Cardiac Catheterization", "Physiotherapy", "Neurological Workup", "Fracture Reduction", "IV Fluid Therapy"]

    base_date = datetime.now() - timedelta(days=90)
    
    # 1. Historical Discharged Admissions
    for i in range(1, 351):
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        age = random.randint(5, 82)
        gender = random.choices(["Male", "Female", "Other"], weights=[52, 45, 3])[0]
        cursor.execute("INSERT INTO patients (name, age, gender, contact, blood_group) VALUES (?, ?, ?, '9876543210', 'B+')", (name, age, gender))
        pid = cursor.lastrowid

        dept_id = random.randint(1, len(dept_specs))
        doc_id = random.randint(1, len(docs))
        adm_delta = random.randint(0, 75)
        stay_len = random.randint(2, 10)
        adm_date = (base_date + timedelta(days=adm_delta)).strftime("%Y-%m-%d")
        dis_date = (base_date + timedelta(days=adm_delta + stay_len)).strftime("%Y-%m-%d")

        cursor.execute('''
            INSERT INTO admissions (patient_id, department_id, doctor_id, bed_id, admission_date, discharge_date, status)
            VALUES (?, ?, ?, NULL, ?, ?, 'Discharged')
        ''', (pid, dept_id, doc_id, adm_date, dis_date))

        cursor.execute('''
            INSERT INTO treatments (treatment_name, patient_id, doctor_id, department_id, treatment_date, status)
            VALUES (?, ?, ?, ?, ?, 'Completed')
        ''', (random.choice(treatments_pool), pid, doc_id, dept_id, adm_date))

    # 2. Currently Admitted Patients
    cursor.execute("SELECT bed_id, department_id FROM beds")
    all_beds = cursor.fetchall()
    
    # High ICU load for realistic analytics/alerts
    occupied_count = 0
    for bed_id, dept_id in all_beds:
        occupy_chance = 0.92 if dept_id == 1 else 0.78
        if random.random() < occupy_chance and occupied_count < 210:
            cursor.execute("UPDATE beds SET status = 'Occupied' WHERE bed_id = ?", (bed_id,))
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            age = random.randint(8, 85)
            gender = random.choices(["Male", "Female", "Other"], weights=[55, 43, 2])[0]
            cursor.execute("INSERT INTO patients (name, age, gender, contact, blood_group) VALUES (?, ?, ?, '9876500000', 'O+')", (name, age, gender))
            pid = cursor.lastrowid

            adm_date = (datetime.now() - timedelta(days=random.randint(1, 8))).strftime("%Y-%m-%d")
            doc_id = random.randint(1, len(docs))
            cursor.execute('''
                INSERT INTO admissions (patient_id, department_id, doctor_id, bed_id, admission_date, discharge_date, status)
                VALUES (?, ?, ?, ?, ?, NULL, 'Admitted')
            ''', (pid, dept_id, doc_id, bed_id, adm_date))

            cursor.execute('''
                INSERT INTO treatments (treatment_name, patient_id, doctor_id, department_id, treatment_date, status)
                VALUES (?, ?, ?, ?, ?, 'Active')
            ''', (random.choice(treatments_pool), pid, doc_id, dept_id, adm_date))
            occupied_count += 1

    conn.commit()
    conn.close()
    print("Database initialized and populated successfully.")

if __name__ == "__main__":
    init_db()