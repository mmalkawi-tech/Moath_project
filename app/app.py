"""
Moath Clinic - Pharmacy & Prescription Management API
"""
import os
from datetime import date, datetime

from flask import Flask, jsonify, request

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

app = Flask(__name__)

APPINSIGHTS_CONNECTION_STRING = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
if APPINSIGHTS_CONNECTION_STRING:
    # azure-monitor-opentelemetry auto-instruments Flask + logging + requests;
    # it's the actively maintained successor to the opencensus exporters
    # (which cap at Flask<3.0 and no longer receive updates).
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(connection_string=APPINSIGHTS_CONNECTION_STRING)

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///local_dev.db")
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Patient(Base):
    __tablename__ = "patients"
    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    date_of_birth = Column(String(20), nullable=False)
    phone = Column(String(30))
    prescriptions = relationship("Prescription", back_populates="patient")


class Medication(Base):
    __tablename__ = "medications"
    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    stock_quantity = Column(Integer, nullable=False, default=0)
    unit_price = Column(Float, nullable=False)
    expiry_date = Column(Date, nullable=False)
    prescriptions = relationship("Prescription", back_populates="medication")


class Prescription(Base):
    __tablename__ = "prescriptions"
    id = Column(Integer, primary_key=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    dosage = Column(String(120), nullable=False)
    quantity = Column(Integer, nullable=False)
    prescribed_by = Column(String(120), nullable=False)
    prescribed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    dispensed = Column(String(10), nullable=False, default="no")
    patient = relationship("Patient", back_populates="prescriptions")
    medication = relationship("Medication", back_populates="prescriptions")


Base.metadata.create_all(engine)


@app.get("/health")
def health():
    return jsonify(status="ok", time=datetime.utcnow().isoformat()), 200


@app.get("/patients")
def list_patients():
    session = SessionLocal()
    try:
        patients = session.query(Patient).all()
        return jsonify([
            {"id": p.id, "full_name": p.full_name, "date_of_birth": p.date_of_birth, "phone": p.phone}
            for p in patients
        ])
    finally:
        session.close()


@app.post("/patients")
def create_patient():
    data = request.get_json(force=True)
    session = SessionLocal()
    try:
        patient = Patient(
            full_name=data["full_name"],
            date_of_birth=data["date_of_birth"],
            phone=data.get("phone"),
        )
        session.add(patient)
        session.commit()
        return jsonify(id=patient.id), 201
    finally:
        session.close()


@app.get("/medications")
def list_medications():
    session = SessionLocal()
    try:
        meds = session.query(Medication).all()
        return jsonify([
            {
                "id": m.id,
                "name": m.name,
                "stock_quantity": m.stock_quantity,
                "unit_price": m.unit_price,
                "expiry_date": m.expiry_date.isoformat(),
            }
            for m in meds
        ])
    finally:
        session.close()


@app.post("/medications")
def create_medication():
    data = request.get_json(force=True)
    session = SessionLocal()
    try:
        medication = Medication(
            name=data["name"],
            stock_quantity=int(data.get("stock_quantity", 0)),
            unit_price=float(data["unit_price"]),
            expiry_date=date.fromisoformat(data["expiry_date"]),
        )
        session.add(medication)
        session.commit()
        return jsonify(id=medication.id), 201
    finally:
        session.close()


@app.get("/prescriptions")
def list_prescriptions():
    session = SessionLocal()
    try:
        prescriptions = session.query(Prescription).all()
        return jsonify([
            {
                "id": p.id,
                "patient_id": p.patient_id,
                "medication_id": p.medication_id,
                "dosage": p.dosage,
                "quantity": p.quantity,
                "prescribed_by": p.prescribed_by,
                "prescribed_at": p.prescribed_at.isoformat(),
                "dispensed": p.dispensed,
            }
            for p in prescriptions
        ])
    finally:
        session.close()


@app.get("/prescriptions/new")
def new_prescription_form():
    session = SessionLocal()
    try:
        patients = session.query(Patient).all()
        medications = session.query(Medication).all()
    finally:
        session.close()

    if not patients or not medications:
        return "<p>Create at least one patient and one medication first.</p>", 200

    patient_options = "".join(f'<option value="{p.id}">{p.full_name} (id {p.id})</option>' for p in patients)
    medication_options = "".join(f'<option value="{m.id}">{m.name} (id {m.id})</option>' for m in medications)
    return f"""
    <!doctype html>
    <html>
    <head><title>New Prescription - Moath Clinic</title></head>
    <body style="font-family: sans-serif; max-width: 480px; margin: 40px auto;">
      <h2>New Prescription</h2>
      <form method="POST" action="/prescriptions">
        <label>Patient</label><br>
        <select name="patient_id" required>{patient_options}</select><br><br>
        <label>Medication</label><br>
        <select name="medication_id" required>{medication_options}</select><br><br>
        <label>Dosage</label><br>
        <input type="text" name="dosage" required><br><br>
        <label>Quantity</label><br>
        <input type="number" name="quantity" min="1" required><br><br>
        <label>Prescribed by</label><br>
        <input type="text" name="prescribed_by" required><br><br>
        <button type="submit">Create</button>
      </form>
    </body>
    </html>
    """


@app.post("/prescriptions")
def create_prescription():
    data = request.get_json(silent=True) or request.form
    session = SessionLocal()
    try:
        prescription = Prescription(
            patient_id=int(data["patient_id"]),
            medication_id=int(data["medication_id"]),
            dosage=data["dosage"],
            quantity=int(data["quantity"]),
            prescribed_by=data["prescribed_by"],
        )
        session.add(prescription)
        session.commit()
        if request.form:
            return f"""
            <p>Prescription #{prescription.id} created.</p>
            <p><a href="/prescriptions/new">Create another</a></p>
            """, 201
        return jsonify(id=prescription.id), 201
    finally:
        session.close()


@app.post("/prescriptions/<int:prescription_id>/dispense")
def dispense_prescription(prescription_id):
    session = SessionLocal()
    try:
        prescription = session.get(Prescription, prescription_id)
        if prescription is None:
            return jsonify(error="prescription not found"), 404
        if prescription.dispensed == "yes":
            return jsonify(error="prescription already dispensed"), 400

        medication = session.get(Medication, prescription.medication_id)
        if medication.stock_quantity < prescription.quantity:
            return jsonify(error="insufficient stock", available=medication.stock_quantity), 400

        medication.stock_quantity -= prescription.quantity
        prescription.dispensed = "yes"
        session.commit()
        return jsonify(id=prescription.id, dispensed="yes", remaining_stock=medication.stock_quantity), 200
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
