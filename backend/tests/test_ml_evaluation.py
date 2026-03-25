"""Tests for the ML evaluation API endpoint (GET /api/ml/evaluation)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_with_auth(mock_current_user):
    """Create a FastAPI TestClient with auth dependency overridden."""
    from app.routers.ml import router
    from app.utils.security import require_admin
    from fastapi import FastAPI

    mock_current_user.role = "admin"
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: mock_current_user
    return app


@pytest.fixture()
def client(app_with_auth):
    return TestClient(app_with_auth)


@pytest.fixture()
def unauthenticated_client():
    """Client without auth override -- endpoint should reject requests."""
    from app.routers.ml import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestGetEvaluationReport:
    """GET /api/ml/evaluation"""

    def test_returns_200_with_valid_report(self, client, evaluation_report_file, evaluation_report_data):
        """Endpoint returns 200 and full report JSON when evaluation_report.json exists."""
        with patch("app.routers.ml.settings") as mock_settings:
            mock_settings.MODEL_DIR = str(evaluation_report_file)
            response = client.get("/api/ml/evaluation")

        assert response.status_code == 200
        data = response.json()
        assert data["test_accuracy"] == evaluation_report_data["test_accuracy"]
        assert "classification_report" in data
        assert "confusion_matrix" in data
        assert "categories" in data

    def test_response_contains_required_keys(self, client, evaluation_report_file):
        """Response includes all required top-level keys."""
        with patch("app.routers.ml.settings") as mock_settings:
            mock_settings.MODEL_DIR = str(evaluation_report_file)
            response = client.get("/api/ml/evaluation")

        assert response.status_code == 200
        data = response.json()
        required_keys = {"test_accuracy", "classification_report", "confusion_matrix", "categories"}
        assert required_keys.issubset(set(data.keys()))

    def test_returns_404_when_no_report(self, client, tmp_path):
        """Endpoint returns 404 when evaluation_report.json does not exist."""
        with patch("app.routers.ml.settings") as mock_settings:
            mock_settings.MODEL_DIR = str(tmp_path / "empty_models")
            response = client.get("/api/ml/evaluation")

        assert response.status_code == 404
        assert "evaluation report" in response.json()["detail"].lower()

    def test_requires_authentication(self, unauthenticated_client, evaluation_report_file):
        """Endpoint rejects unauthenticated requests without Bearer token."""
        with patch("app.routers.ml.settings") as mock_settings:
            mock_settings.MODEL_DIR = str(evaluation_report_file)
            response = unauthenticated_client.get("/api/ml/evaluation")

        # HTTPBearer rejects missing credentials with 401 or 403
        assert response.status_code in (401, 403)

    def test_classification_report_structure(self, client, evaluation_report_file):
        """Each category in classification_report has precision, recall, f1-score, support."""
        with patch("app.routers.ml.settings") as mock_settings:
            mock_settings.MODEL_DIR = str(evaluation_report_file)
            response = client.get("/api/ml/evaluation")

        data = response.json()
        for category, metrics in data["classification_report"].items():
            assert "precision" in metrics, f"Missing precision for {category}"
            assert "recall" in metrics, f"Missing recall for {category}"
            assert "f1-score" in metrics, f"Missing f1-score for {category}"
            assert "support" in metrics, f"Missing support for {category}"
