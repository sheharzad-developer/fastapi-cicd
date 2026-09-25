def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_create_task(client):
    response = client.post("/tasks", json={"title": "Learn CI/CD"})
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "Learn CI/CD"
    assert data["status"] == "pending"


def test_list_tasks(client):
    client.post("/tasks", json={"title": "one"})
    client.post("/tasks", json={"title": "two"})
    response = client.get("/tasks")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_get_task(client):
    client.post("/tasks", json={"title": "one"})
    response = client.get("/tasks/1")
    assert response.status_code == 200
    assert response.json()["title"] == "one"


def test_update_task(client):
    client.post("/tasks", json={"title": "one"})
    response = client.put("/tasks/1", json={"status": "completed"})
    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["title"] == "one"


def test_delete_task(client):
    client.post("/tasks", json={"title": "one"})
    assert client.delete("/tasks/1").status_code == 200
    assert client.get("/tasks/1").status_code == 404


def test_get_missing_task_returns_404(client):
    assert client.get("/tasks/999").status_code == 404


def test_empty_title_rejected(client):
    assert client.post("/tasks", json={"title": ""}).status_code == 422


def test_invalid_status_rejected(client):
    response = client.post("/tasks", json={"title": "x", "status": "done"})
    assert response.status_code == 422


def test_non_integer_id_rejected(client):
    assert client.get("/tasks/abc").status_code == 422


def test_empty_update_rejected(client):
    client.post("/tasks", json={"title": "one"})
    assert client.put("/tasks/1", json={}).status_code == 400
