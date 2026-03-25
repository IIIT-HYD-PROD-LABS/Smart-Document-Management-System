"""Shared test fixtures for backend tests."""

import json
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def mock_settings(tmp_path):
    """Provide a Settings-like object with MODEL_DIR pointing to tmp_path."""
    settings_mock = MagicMock()
    settings_mock.MODEL_DIR = str(tmp_path / "models")
    settings_mock.SECRET_KEY = "test-secret-key-that-is-long-enough-for-validation-1234567890"
    settings_mock.ALGORITHM = "HS256"
    settings_mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    settings_mock.DATABASE_URL = "sqlite:///test.db"
    settings_mock.DEBUG = True
    return settings_mock


@pytest.fixture()
def evaluation_report_data():
    """Sample evaluation report matching the structure produced by train.py."""
    return {
        "data_source": "combined",
        "total_samples": 1210,
        "train_size": 847,
        "val_size": 181,
        "test_size": 182,
        "best_model": "Logistic Regression",
        "test_accuracy": 0.85,
        "cv_mean": 0.84,
        "cv_std": 0.02,
        "vocabulary_size": 4392,
        "classification_report": {
            "bank": {"precision": 0.73, "recall": 0.73, "f1-score": 0.73, "support": 30},
            "bills": {"precision": 0.57, "recall": 0.57, "f1-score": 0.57, "support": 30},
            "invoices": {"precision": 0.67, "recall": 0.67, "f1-score": 0.67, "support": 30},
            "tax": {"precision": 0.95, "recall": 0.95, "f1-score": 0.95, "support": 30},
            "tickets": {"precision": 1.00, "recall": 1.00, "f1-score": 1.00, "support": 30},
            "upi": {"precision": 1.00, "recall": 1.00, "f1-score": 1.00, "support": 32},
        },
        "confusion_matrix": [
            [22, 3, 5, 0, 0, 0],
            [4, 17, 6, 2, 1, 0],
            [3, 5, 20, 2, 0, 0],
            [0, 1, 0, 28, 1, 0],
            [0, 0, 0, 0, 30, 0],
            [0, 0, 0, 0, 0, 32],
        ],
        "categories": ["bank", "bills", "invoices", "tax", "tickets", "upi"],
    }


@pytest.fixture()
def evaluation_report_file(tmp_path, evaluation_report_data):
    """Create a temporary evaluation_report.json and return its parent dir."""
    eval_dir = tmp_path / "models" / "evaluation"
    eval_dir.mkdir(parents=True)
    report_path = eval_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(evaluation_report_data))
    return tmp_path / "models"


@pytest.fixture()
def mock_current_user():
    """Return a mock user object for authenticated requests."""
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    user.username = "testuser"
    user.is_active = True
    return user
