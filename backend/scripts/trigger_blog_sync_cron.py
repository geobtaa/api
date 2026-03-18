from __future__ import annotations

import os

import requests


def main() -> None:
    admin_username = os.getenv("ADMIN_USERNAME", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "changeme")
    application_url = os.getenv("APPLICATION_URL", "").rstrip("/")

    if not application_url:
        raise RuntimeError("APPLICATION_URL is required")

    # Enqueue the Celery job (equivalent to make blog-sync with RUN_NOW omitted/false).
    url = f"{application_url}/api/v1/admin/home/blog/sync"
    resp = requests.post(
        url,
        json={"run_now": False},
        auth=(admin_username, admin_password),
        timeout=60,
    )
    resp.raise_for_status()
    print(resp.text)


if __name__ == "__main__":
    main()

