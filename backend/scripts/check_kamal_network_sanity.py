from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List

DEFAULT_EXTERNAL_URLS = (
    "https://api.github.com",
    "https://raw.githubusercontent.com",
    "https://gin.btaa.org",
    "http://example.com",
)
RESULT_PREFIX = "RESULT\t"


@dataclass
class ProbeResult:
    url: str
    exit_code: int
    details: str

    @property
    def fields(self) -> Dict[str, str]:
        return dict(re.findall(r"([a-z_]+)=([^ ]*)", self.details))

    @property
    def http_code(self) -> str:
        return self.fields.get("http", "")

    @property
    def remote_ip(self) -> str:
        return self.fields.get("remote_ip", "")

    @property
    def total(self) -> str:
        return self.fields.get("total", "")

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and self.http_code not in {"", "000"}


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"ERROR: {name} is required")
    return value


def _probe_script(urls: Iterable[str], *, connect_timeout: str, max_time: str) -> str:
    url_args = " ".join(shlex.quote(url) for url in urls)
    return (
        f"for url in {url_args}; do "
        "out=$(curl -I -sS -o /dev/null "
        f"-w 'http=%{{http_code}} remote_ip=%{{remote_ip}} connect=%{{time_connect}} "
        f"tls=%{{time_appconnect}} total=%{{time_total}}' "
        f"--connect-timeout {shlex.quote(connect_timeout)} "
        f'-m {shlex.quote(max_time)} "$url" 2>&1); '
        "status=$?; "
        'printf \'RESULT\t%s\t%s\t%s\n\' "$url" "$status" "$out"; '
        "done"
    )


def _run_command(cmd: List[str], label: str) -> str:
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise SystemExit(f"ERROR: missing required command for {label}: {exc.filename}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip()
        stdout = exc.stdout.strip()
        detail = stderr or stdout or f"exit status {exc.returncode}"
        raise SystemExit(f"ERROR: {label} failed: {detail}") from exc
    return result.stdout


def _parse_results(output: str) -> Dict[str, ProbeResult]:
    results: Dict[str, ProbeResult] = {}
    for line in output.splitlines():
        if not line.startswith(RESULT_PREFIX):
            continue
        _, url, exit_code, details = line.split("\t", 3)
        results[url] = ProbeResult(url=url, exit_code=int(exit_code), details=details)
    return results


def _print_section(
    title: str, urls: List[str], results: Dict[str, ProbeResult], self_url: str
) -> None:
    print(f"{title}:")
    for url in urls:
        result = results.get(url)
        if result is None:
            print(f"  FAIL {url} (no result)")
            continue
        label = "self" if url == self_url else "ext "
        if result.ok:
            print(
                f"  OK   [{label}] {url} "
                f"http={result.http_code} ip={result.remote_ip or '-'} total={result.total or '-'}"
            )
        else:
            print(
                f"  FAIL [{label}] {url} exit={result.exit_code} "
                f"http={result.http_code or '000'} detail={result.details}"
            )


def main() -> int:
    if shutil.which("ssh") is None:
        raise SystemExit("ERROR: ssh is required")
    if shutil.which("kamal") is None:
        raise SystemExit("ERROR: kamal is required")

    kamal_dest = _required_env("KAMAL_DEST")
    kamal_host = _required_env("KAMAL_HOST")
    kamal_ssh_user = _required_env("KAMAL_SSH_USER")
    kamal_app_role = os.getenv("KAMAL_APP_ROLE", "web").strip() or "web"
    connect_timeout = os.getenv("KAMAL_NETWORK_CONNECT_TIMEOUT", "5").strip() or "5"
    max_time = os.getenv("KAMAL_NETWORK_MAX_TIME", "12").strip() or "12"

    self_url = os.getenv("KAMAL_NETWORK_SELF_URL", "").strip() or f"https://{kamal_host}"
    external_urls = shlex.split(os.getenv("KAMAL_NETWORK_EXTERNAL_URLS", "").strip())
    if not external_urls:
        external_urls = list(DEFAULT_EXTERNAL_URLS)

    urls = list(dict.fromkeys([*external_urls, self_url]))
    probe_script = _probe_script(urls, connect_timeout=connect_timeout, max_time=max_time)

    host_output = _run_command(
        ["ssh", f"{kamal_ssh_user}@{kamal_host}", f"bash -lc {shlex.quote(probe_script)}"],
        "host probe",
    )
    container_output = _run_command(
        [
            "kamal",
            "app",
            "exec",
            "-d",
            kamal_dest,
            "--roles",
            kamal_app_role,
            "--reuse",
            f"bash -lc {shlex.quote(probe_script)}",
        ],
        "container probe",
    )

    host_results = _parse_results(host_output)
    container_results = _parse_results(container_output)

    print(
        f"Network sanity report for {kamal_dest} "
        f"(host={kamal_host}, role={kamal_app_role}, self_url={self_url})"
    )
    print("")
    _print_section("Host shell", urls, host_results, self_url)
    print("")
    _print_section("Container", urls, container_results, self_url)
    print("")

    failures: List[str] = []
    for url in urls:
        host_result = host_results.get(url)
        container_result = container_results.get(url)
        if host_result is None or not host_result.ok:
            failures.append(f"host failed: {url}")
        if container_result is None or not container_result.ok:
            failures.append(f"container failed: {url}")

    host_self_ok = host_results.get(self_url).ok if self_url in host_results else False
    container_self_ok = (
        container_results.get(self_url).ok if self_url in container_results else False
    )
    external_container_failures = [
        url for url in external_urls if not container_results.get(url, ProbeResult(url, 1, "")).ok
    ]

    if not failures:
        print(
            "PASS: host shell and container can reach the expected external URLs "
            "and self public hostname."
        )
        return 0

    if host_self_ok and not container_self_ok and not external_container_failures:
        print(
            "FAIL: host shell can reach the self public hostname, but the container cannot. "
            "This points to a container-to-self-FQDN / hairpin / firewall-path issue."
        )
    else:
        print("FAIL: one or more host/container connectivity probes failed.")

    for failure in failures:
        print(f"  - {failure}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
