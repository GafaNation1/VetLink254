# apps/api/tests/test_users_api.py — basic create/list smoke tests for /api/v1/users
class TestUsersAPI:
    def test_create_user(self, client):
        resp = client.post(
            "/api/v1/users/",
            json={"phone": "+254700000001", "name": "Test Farmer", "role": "farmer"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["phone"] == "+254700000001"
        assert data["name"] == "Test Farmer"
        assert data["role"] == "farmer"
        assert data["ussd_only_flag"] is True

    def test_create_user_defaults(self, client):
        resp = client.post("/api/v1/users/", json={"phone": "+254700000003"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "farmer"
        assert data["ussd_only_flag"] is True

    def test_list_users(self, client):
        client.post("/api/v1/users/", json={"phone": "+254700000001", "name": "A"})
        client.post("/api/v1/users/", json={"phone": "+254700000002", "name": "B"})
        resp = client.get("/api/v1/users/")
        assert resp.status_code == 200
        assert len(resp.json()) == 2
