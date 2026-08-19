# apps/api/tests/test_bookings_api.py — basic create/list smoke tests for /api/v1/bookings
class TestBookingsAPI:
    def _make_farmer(self, client, phone="+254700000001"):
        resp = client.post("/api/v1/users/", json={"phone": phone, "name": "Farmer"})
        assert resp.status_code == 201
        return resp.json()

    def test_create_booking(self, client):
        farmer = self._make_farmer(client)
        resp = client.post(
            "/api/v1/bookings/",
            json={"ref_code": "VL-20260814-0001", "farmer_id": farmer["id"], "animal_type": "Dog"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["ref_code"] == "VL-20260814-0001"
        assert data["farmer_id"] == farmer["id"]
        assert data["status"] == "requested"
        assert data["channel"] == "ussd"

    def test_list_bookings(self, client):
        farmer = self._make_farmer(client)
        client.post("/api/v1/bookings/", json={"ref_code": "VL-1", "farmer_id": farmer["id"], "animal_type": "Dog"})
        client.post("/api/v1/bookings/", json={"ref_code": "VL-2", "farmer_id": farmer["id"], "animal_type": "Cat"})
        resp = client.get("/api/v1/bookings/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
