import pytest

from fastapi.testclient import TestClient

from app import main

@pytest.fixture
def client():
    main.tasks.clear()
    main.next_id = 1
    return TestClient(main.app)