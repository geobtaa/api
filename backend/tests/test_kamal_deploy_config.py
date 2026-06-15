import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


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
