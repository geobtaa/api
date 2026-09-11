"""Configured storage identities are explicit; local ambient profiles are never selected."""

import os

import boto3
import pytest

from app.services.analytics_reporting.archive import configured_archives


@pytest.fixture
def setup(monkeypatch):
    for key in os.environ:
        if key.startswith("ANALYTICS_ARCHIVE_"):
            monkeypatch.delenv(key)
    calls = []

    class Client:
        def get_bucket_acl(self, *, Bucket):
            return {"Owner": {"ID": Bucket}}

        def get_bucket_versioning(self, **kwargs):
            return {"Status": "Enabled"}

        def get_public_access_block(self, **kwargs):
            return {
                "PublicAccessBlockConfiguration": dict.fromkeys(
                    [
                        "BlockPublicAcls",
                        "IgnorePublicAcls",
                        "BlockPublicPolicy",
                        "RestrictPublicBuckets",
                    ],
                    True,
                )
            }

        def get_bucket_lifecycle_configuration(self, **kwargs):
            return {"Rules": []}

    class Session:
        def __init__(self, **kwargs):
            calls.append(kwargs)

        def client(self, service):
            assert service == "s3"
            return Client()

    monkeypatch.setattr(boto3, "Session", Session)
    for role in ("PRIMARY", "RECOVERY"):
        monkeypatch.setenv(f"ANALYTICS_ARCHIVE_{role}_BUCKET", role.lower())
    return calls


def test_explicit_project_credentials_do_not_use_ambient_profiles(monkeypatch, setup):
    for role in ("PRIMARY", "RECOVERY"):
        prefix = f"ANALYTICS_ARCHIVE_{role}_"
        monkeypatch.setenv(prefix + "ACCESS_KEY_ID", "fixture-access")
        monkeypatch.setenv(prefix + "SECRET_ACCESS_KEY", "fixture-secret")
        monkeypatch.setenv(prefix + "REGION", "us-east-2")
    archives = configured_archives()
    assert len(archives) == 2
    assert all("profile_name" not in call for call in setup)
    assert all(call["region_name"] == "us-east-2" for call in setup)


def test_missing_credentials_never_fall_back_to_local_default(setup):
    with pytest.raises(RuntimeError, match="explicit credential"):
        configured_archives()
    assert setup == []


def test_ambiguous_credential_sources_are_rejected(monkeypatch, setup):
    monkeypatch.setenv("ANALYTICS_ARCHIVE_PRIMARY_PROFILE", "fixture")
    monkeypatch.setenv("ANALYTICS_ARCHIVE_PRIMARY_ACCESS_KEY_ID", "fixture-access")
    with pytest.raises(RuntimeError, match="either"):
        configured_archives()
    assert setup == []


def test_existing_explicit_profiles_still_verify_bucket_ownership(monkeypatch, setup):
    for role in ("PRIMARY", "RECOVERY"):
        monkeypatch.setenv(f"ANALYTICS_ARCHIVE_{role}_PROFILE", role.lower())
    assert len(configured_archives()) == 2
    assert [call["profile_name"] for call in setup] == ["primary", "recovery"]
    monkeypatch.setenv("ANALYTICS_ARCHIVE_RECOVERY_BUCKET", "primary")
    with pytest.raises(RuntimeError, match="independent storage account"):
        configured_archives()
