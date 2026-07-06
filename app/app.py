"""
Moath Clinic - Pharmacy & Prescription Management
"""
import os
from datetime import date, datetime

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-change-in-production")

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


class DispenseError(Exception):
    def __init__(self, message, status_code, available=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.available = available


def _dispense(prescription_id, session):
    prescription = session.get(Prescription, prescription_id)
    if prescription is None:
        raise DispenseError("Prescription not found.", 404)
    if prescription.dispensed == "yes":
        raise DispenseError("Prescription already dispensed.", 400)

    medication = session.get(Medication, prescription.medication_id)
    if medication.stock_quantity < prescription.quantity:
        raise DispenseError(
            f"Insufficient stock ({medication.stock_quantity} available).",
            400,
            available=medication.stock_quantity,
        )

    medication.stock_quantity -= prescription.quantity
    prescription.dispensed = "yes"
    session.commit()
    return prescription, medication


@app.get("/health")
def health():
    return jsonify(status="ok", time=datetime.utcnow().isoformat()), 200


# ---------------------------------------------------------------------
# GUI (server-rendered HTML)
# ---------------------------------------------------------------------


@app.get("/")
def dashboard():
    session = SessionLocal()
    try:
        low_stock_meds = (
            session.query(Medication)
            .filter(Medication.stock_quantity < 10)
            .order_by(Medication.stock_quantity)
            .all()
        )
        recent_prescriptions = (
            session.query(Prescription).order_by(Prescription.prescribed_at.desc()).limit(5).all()
        )
        return render_template(
            "dashboard.html",
            active="dashboard",
            patient_count=session.query(Patient).count(),
            medication_count=session.query(Medication).count(),
            prescription_count=session.query(Prescription).count(),
            low_stock_meds=low_stock_meds,
            recent_prescriptions=recent_prescriptions,
        )
    finally:
        session.close()


@app.get("/patients")
def patients_page():
    session = SessionLocal()
    try:
        patients = session.query(Patient).order_by(Patient.id.desc()).all()
        return render_template("patients.html", active="patients", patients=patients)
    finally:
        session.close()


@app.post("/patients")
def add_patient():
    session = SessionLocal()
    try:
        patient = Patient(
            full_name=request.form["full_name"],
            date_of_birth=request.form["date_of_birth"],
            phone=request.form.get("phone") or None,
        )
        session.add(patient)
        session.commit()
        flash(f"Added patient {patient.full_name}.", "success")
    finally:
        session.close()
    return redirect(url_for("patients_page"))


@app.get("/medications")
def medications_page():
    session = SessionLocal()
    try:
        medications = session.query(Medication).order_by(Medication.id.desc()).all()
        return render_template("medications.html", active="medications", medications=medications)
    finally:
        session.close()


@app.post("/medications")
def add_medication():
    session = SessionLocal()
    try:
        medication = Medication(
            name=request.form["name"],
            stock_quantity=int(request.form.get("stock_quantity", 0)),
            unit_price=float(request.form["unit_price"]),
            expiry_date=date.fromisoformat(request.form["expiry_date"]),
        )
        session.add(medication)
        session.commit()
        flash(f"Added medication {medication.name}.", "success")
    finally:
        session.close()
    return redirect(url_for("medications_page"))


@app.get("/prescriptions")
def prescriptions_page():
    session = SessionLocal()
    try:
        prescriptions = session.query(Prescription).order_by(Prescription.id.desc()).all()
        patients = session.query(Patient).all()
        medications = session.query(Medication).all()
        return render_template(
            "prescriptions.html",
            active="prescriptions",
            prescriptions=prescriptions,
            patients=patients,
            medications=medications,
        )
    finally:
        session.close()


@app.post("/prescriptions")
def add_prescription():
    session = SessionLocal()
    try:
        prescription = Prescription(
            patient_id=int(request.form["patient_id"]),
            medication_id=int(request.form["medication_id"]),
            dosage=request.form["dosage"],
            quantity=int(request.form["quantity"]),
            prescribed_by=request.form["prescribed_by"],
        )
        session.add(prescription)
        session.commit()
        flash(f"Created prescription #{prescription.id}.", "success")
    finally:
        session.close()
    return redirect(url_for("prescriptions_page"))


@app.post("/prescriptions/<int:prescription_id>/dispense")
def dispense_prescription_ui(prescription_id):
    session = SessionLocal()
    try:
        prescription, medication = _dispense(prescription_id, session)
        flash(
            f"Dispensed prescription #{prescription.id} - {medication.stock_quantity} units of "
            f"{medication.name} remain.",
            "success",
        )
    except DispenseError as e:
        flash(e.message, "danger")
    finally:
        session.close()
    return redirect(url_for("prescriptions_page"))


# ---------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------


@app.get("/api/patients")
def api_list_patients():
    session = SessionLocal()
    try:
        patients = session.query(Patient).all()
        return jsonify([
            {"id": p.id, "full_name": p.full_name, "date_of_birth": p.date_of_birth, "phone": p.phone}
            for p in patients
        ])
    finally:
        session.close()


@app.post("/api/patients")
def api_create_patient():
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


@app.get("/api/medications")
def api_list_medications():
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


@app.post("/api/medications")
def api_create_medication():
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


@app.get("/api/prescriptions")
def api_list_prescriptions():
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


@app.post("/api/prescriptions")
def api_create_prescription():
    data = request.get_json(force=True)
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
        return jsonify(id=prescription.id), 201
    finally:
        session.close()


@app.post("/api/prescriptions/<int:prescription_id>/dispense")
def api_dispense_prescription(prescription_id):
    session = SessionLocal()
    try:
        prescription, medication = _dispense(prescription_id, session)
        return jsonify(id=prescription.id, dispensed="yes", remaining_stock=medication.stock_quantity), 200
    except DispenseError as e:
        payload = {"error": e.message}
        if e.available is not None:
            payload["available"] = e.available
        return jsonify(**payload), e.status_code
    finally:
        session.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
