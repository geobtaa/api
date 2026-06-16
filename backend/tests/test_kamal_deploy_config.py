import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
APP_REVISION_EXPR = (
    "ENV.fetch('APP_REVISION') { ENV.fetch('KAMAL_VERSION') "
    "{ `git rev-parse --verify HEAD`.strip } }"
)


def _load_deploy_config(path: str) -> dict:
    config_text = (REPO_ROOT / path).read_text()
    config_text = re.sub(r"<%.*?%>", "", config_text, flags=re.DOTALL)
    return yaml.safe_load(config_text)


def test_prd_secret_override_keeps_base_secrets():
    base_config = _load_deploy_config("config/deploy.yml")
    prd_config = _load_deploy_config("config/deploy.prd.yml")

    base_secrets = set(base_config["env"]["secret"])
    prd_secrets = set(prd_config["env"]["secret"])

    missing = base_secrets - prd_secrets
    assert not missing, (
        "config/deploy.prd.yml env.secret replaces the base list; "
        f"missing inherited secrets: {sorted(missing)}"
    )


def test_prd_allows_search_engine_indexing():
    prd_config = _load_deploy_config("config/deploy.prd.yml")

    assert prd_config["env"]["clear"]["SEARCH_ENGINE_INDEXING_ENABLED"] == "true"


def test_prd_uses_canonical_geoportal_base_url():
    prd_config = _load_deploy_config("config/deploy.prd.yml")

    assert prd_config["env"]["clear"]["GEOPORTAL_BASE_URL"] == "https://geo.btaa.org"


def test_prd_feedback_defaults_to_sendmail():
    config_text = (REPO_ROOT / "config/deploy.prd.yml").read_text()

    assert "ENV.fetch('FEEDBACK_DELIVERY', 'sendmail')" in config_text


def test_appsignal_prd_identity():
    prd_env = _load_deploy_config("config/deploy.prd.yml")["env"]["clear"]
    config_text = (REPO_ROOT / "config/deploy.prd.yml").read_text()

    assert prd_env["APPSIGNAL_ACTIVE"] == "true"
    assert prd_env["APPSIGNAL_APP_ENV"] == "production"
    assert prd_env["APPSIGNAL_APP_NAME"] == "BTAA Geospatial API - Production"
    assert prd_env["APPSIGNAL_BACKEND_ACTIVE"] == "true"
    assert prd_env["APPSIGNAL_BACKEND_APP_ENV"] == "production"
    assert prd_env["APPSIGNAL_BACKEND_APP_NAME"] == "BTAA Geospatial API - Production"
    assert prd_env["APPSIGNAL_BACKEND_ENABLE_HOST_METRICS"] == "true"
    assert prd_env["APPSIGNAL_BACKEND_HOST_ROLE"] == "backend"
    assert prd_env["APPSIGNAL_BACKEND_OPENTELEMETRY_PORT"] == "8099"
    assert prd_env["APPSIGNAL_FRONTEND_ACTIVE"] == "true"
    assert prd_env["APPSIGNAL_FRONTEND_APP_ENV"] == "production"
    assert prd_env["APPSIGNAL_FRONTEND_APP_NAME"] == "BTAA Geoportal SSR - Production"
    assert prd_env["APPSIGNAL_FRONTEND_ENABLE_HOST_METRICS"] == "false"
    assert prd_env["APPSIGNAL_FRONTEND_HOST_ROLE"] == "frontend"
    assert prd_env["APPSIGNAL_FRONTEND_OPENTELEMETRY_PORT"] == "8100"
    assert "APP_REVISION" in prd_env
    assert APP_REVISION_EXPR in config_text
    assert "unknown" not in prd_env["APP_REVISION"]
    assert "'unknown'" not in config_text


def test_appsignal_dev2_identity():
    dev2_env = _load_deploy_config("config/deploy.dev2.yml")["env"]["clear"]
    config_text = (REPO_ROOT / "config/deploy.dev2.yml").read_text()

    assert dev2_env["APPSIGNAL_ACTIVE"] == "true"
    assert dev2_env["APPSIGNAL_APP_ENV"] == "development"
    assert dev2_env["APPSIGNAL_APP_NAME"] == "BTAA Geospatial API - Development"
    assert dev2_env["APPSIGNAL_BACKEND_ACTIVE"] == "true"
    assert dev2_env["APPSIGNAL_BACKEND_APP_ENV"] == "development"
    assert dev2_env["APPSIGNAL_BACKEND_APP_NAME"] == "BTAA Geospatial API - Development"
    assert dev2_env["APPSIGNAL_BACKEND_ENABLE_HOST_METRICS"] == "true"
    assert dev2_env["APPSIGNAL_BACKEND_HOST_ROLE"] == "backend"
    assert dev2_env["APPSIGNAL_BACKEND_OPENTELEMETRY_PORT"] == "8099"
    assert dev2_env["APPSIGNAL_FRONTEND_ACTIVE"] == "true"
    assert dev2_env["APPSIGNAL_FRONTEND_APP_ENV"] == "development"
    assert dev2_env["APPSIGNAL_FRONTEND_APP_NAME"] == "BTAA Geoportal SSR - Development"
    assert dev2_env["APPSIGNAL_FRONTEND_ENABLE_HOST_METRICS"] == "false"
    assert dev2_env["APPSIGNAL_FRONTEND_HOST_ROLE"] == "frontend"
    assert dev2_env["APPSIGNAL_FRONTEND_OPENTELEMETRY_PORT"] == "8100"
    assert "APP_REVISION" in dev2_env
    assert APP_REVISION_EXPR in config_text
    assert "unknown" not in dev2_env["APP_REVISION"]
    assert "'unknown'" not in config_text


def test_appsignal_dev1_disabled():
    dev1_env = _load_deploy_config("config/deploy.dev1.yml")["env"]["clear"]
    config_text = (REPO_ROOT / "config/deploy.dev1.yml").read_text()

    assert dev1_env["APPSIGNAL_ACTIVE"] == "false"
    assert dev1_env["APPSIGNAL_APP_ENV"] == "development"
    assert dev1_env["APPSIGNAL_BACKEND_ACTIVE"] == "false"
    assert dev1_env["APPSIGNAL_BACKEND_APP_ENV"] == "development"
    assert dev1_env["APPSIGNAL_BACKEND_APP_NAME"] == "BTAA Geospatial API - Development"
    assert dev1_env["APPSIGNAL_BACKEND_ENABLE_HOST_METRICS"] == "false"
    assert dev1_env["APPSIGNAL_BACKEND_HOST_ROLE"] == "backend"
    assert dev1_env["APPSIGNAL_BACKEND_OPENTELEMETRY_PORT"] == "8099"
    assert dev1_env["APPSIGNAL_FRONTEND_ACTIVE"] == "false"
    assert dev1_env["APPSIGNAL_FRONTEND_APP_ENV"] == "development"
    assert dev1_env["APPSIGNAL_FRONTEND_APP_NAME"] == "BTAA Geoportal SSR - Development"
    assert dev1_env["APPSIGNAL_FRONTEND_ENABLE_HOST_METRICS"] == "false"
    assert dev1_env["APPSIGNAL_FRONTEND_HOST_ROLE"] == "frontend"
    assert dev1_env["APPSIGNAL_FRONTEND_OPENTELEMETRY_PORT"] == "8100"
    assert "APP_REVISION" in dev1_env
    assert APP_REVISION_EXPR in config_text
    assert "unknown" not in dev1_env["APP_REVISION"]
    assert "'unknown'" not in config_text


def test_frontend_appsignal_uses_node_option_names():
    config_text = (REPO_ROOT / "frontend/appsignal.cjs").read_text()

    assert "enableHostMetrics:" in config_text
    assert "hostRole:" in config_text
    assert "opentelemetryPort:" in config_text
    assert "opentelemetry_port:" not in config_text
