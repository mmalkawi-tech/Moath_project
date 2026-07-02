def _make_patient(client, name="Test Patient"):
    resp = client.post("/patients", json={"full_name": name, "date_of_birth": "1990-01-01"})
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _make_medication(client, name="Test Medication", stock=10):
    resp = client.post(
        "/medications",
        json={"name": name, "stock_quantity": stock, "unit_price": 4.5, "expiry_date": "2027-01-01"},
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def _make_prescription(client, patient_id, medication_id, quantity):
    resp = client.post(
        "/prescriptions",
        json={
            "patient_id": patient_id,
            "medication_id": medication_id,
            "dosage": "1 tablet 3x/day",
            "quantity": quantity,
            "prescribed_by": "Dr. Smith",
        },
    )
    assert resp.status_code == 201
    return resp.get_json()["id"]


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_create_and_list_patient(client):
    patient_id = _make_patient(client, name="Jane Doe")
    patients = client.get("/patients").get_json()
    assert any(p["id"] == patient_id and p["full_name"] == "Jane Doe" for p in patients)


def test_create_and_list_medication(client):
    medication_id = _make_medication(client, name="Amoxicillin 500mg", stock=100)
    medications = client.get("/medications").get_json()
    assert any(m["id"] == medication_id and m["stock_quantity"] == 100 for m in medications)


def test_create_and_list_prescription(client):
    patient_id = _make_patient(client)
    medication_id = _make_medication(client, stock=50)
    prescription_id = _make_prescription(client, patient_id, medication_id, quantity=5)

    prescriptions = client.get("/prescriptions").get_json()
    assert any(p["id"] == prescription_id and p["dispensed"] == "no" for p in prescriptions)


def test_dispense_decrements_stock_and_marks_dispensed(client):
    patient_id = _make_patient(client)
    medication_id = _make_medication(client, stock=10)
    prescription_id = _make_prescription(client, patient_id, medication_id, quantity=3)

    resp = client.post(f"/prescriptions/{prescription_id}/dispense")
    assert resp.status_code == 200
    assert resp.get_json()["remaining_stock"] == 7

    medications = {m["id"]: m for m in client.get("/medications").get_json()}
    assert medications[medication_id]["stock_quantity"] == 7

    prescriptions = {p["id"]: p for p in client.get("/prescriptions").get_json()}
    assert prescriptions[prescription_id]["dispensed"] == "yes"


def test_dispense_rejects_insufficient_stock(client):
    patient_id = _make_patient(client)
    medication_id = _make_medication(client, stock=2)
    prescription_id = _make_prescription(client, patient_id, medication_id, quantity=5)

    resp = client.post(f"/prescriptions/{prescription_id}/dispense")
    assert resp.status_code == 400
    assert resp.get_json()["available"] == 2

    medications = {m["id"]: m for m in client.get("/medications").get_json()}
    assert medications[medication_id]["stock_quantity"] == 2


def test_dispense_rejects_already_dispensed(client):
    patient_id = _make_patient(client)
    medication_id = _make_medication(client, stock=10)
    prescription_id = _make_prescription(client, patient_id, medication_id, quantity=1)

    first = client.post(f"/prescriptions/{prescription_id}/dispense")
    assert first.status_code == 200

    second = client.post(f"/prescriptions/{prescription_id}/dispense")
    assert second.status_code == 400


def test_dispense_not_found(client):
    resp = client.post("/prescriptions/999999/dispense")
    assert resp.status_code == 404
