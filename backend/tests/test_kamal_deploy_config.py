from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_deploy_config(path: str) -> dict:
    with (REPO_ROOT / path).open() as config_file:
        return yaml.safe_load(config_file)


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
