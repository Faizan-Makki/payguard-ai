import os

from payguard.config import load_project_env


def test_project_env_loader_reads_expected_names_without_overriding_process(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "PAYPAL_CLIENT_ID=test-client-id\n"
        "PAYPAL_CLIENT_SECRET=test-client-secret\n"
        "PAYGUARD_DATA_SOURCE=demo\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("PAYPAL_CLIENT_ID", raising=False)
    monkeypatch.delenv("PAYPAL_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("PAYGUARD_DATA_SOURCE", "demo")

    assert load_project_env(env_path) is True
    assert os.environ["PAYPAL_CLIENT_ID"] == "test-client-id"
    assert os.environ["PAYPAL_CLIENT_SECRET"] == "test-client-secret"
    assert os.environ["PAYGUARD_DATA_SOURCE"] == "demo"


def test_project_env_loader_does_not_override_existing_environment(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("PAYPAL_CLIENT_ID=file-id\n", encoding="utf-8")
    monkeypatch.setenv("PAYPAL_CLIENT_ID", "process-id")

    assert load_project_env(env_path) is True
    assert os.environ["PAYPAL_CLIENT_ID"] == "process-id"
