import argparse
import json
import subprocess
import urllib.error
import urllib.request
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test the Docker Compose runtime without starting it.",
    )
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--ollama-debug-url", default="http://localhost:11435")
    parser.add_argument(
        "--soft",
        action="store_true",
        help="Print report but return exit code 0 even when checks fail.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checks = [
        compose_config_check(),
        http_json_check("backend_health", f"{args.backend_url.rstrip('/')}/api/health"),
        http_json_check(
            "ollama_host_debug",
            f"{args.ollama_debug_url.rstrip('/')}/api/tags",
        ),
        backend_to_ollama_check(),
        postgres_pgvector_check(),
    ]
    report = {
        "status": "ok" if all(check["passed"] for check in checks) else "failed",
        "checks": checks,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "ok" and not args.soft:
        raise SystemExit(1)


def compose_config_check() -> dict[str, Any]:
    completed = run_command(["docker", "compose", "config"])
    return check_from_completed("docker_compose_config", completed)


def backend_to_ollama_check() -> dict[str, Any]:
    script = (
        "import os, urllib.request; "
        "url=os.getenv('OLLAMA_BASE_URL','http://ollama:11434').rstrip('/') + '/api/tags'; "
        "print(url); "
        "print(urllib.request.urlopen(url, timeout=10).status)"
    )
    completed = run_command(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", script],
    )
    return check_from_completed("backend_to_ollama_network", completed)


def postgres_pgvector_check() -> dict[str, Any]:
    sql = "CREATE EXTENSION IF NOT EXISTS vector; SELECT extname FROM pg_extension WHERE extname='vector';"
    completed = run_command(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "postgres",
            "psql",
            "-U",
            "english_tutor",
            "-d",
            "english_tutor",
            "-c",
            sql,
        ],
    )
    return check_from_completed("postgres_pgvector_extension", completed)


def http_json_check(name: str, url: str) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
        return {
            "name": name,
            "passed": True,
            "url": url,
            "status": "ok",
            "keys": sorted(payload.keys())[:12] if isinstance(payload, dict) else [],
            "error": "",
        }
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "name": name,
            "passed": False,
            "url": url,
            "status": "error",
            "error": str(exc),
        }


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=str(exc),
        )


def check_from_completed(
    name: str,
    completed: subprocess.CompletedProcess[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "passed": completed.returncode == 0,
        "command": " ".join(str(part) for part in completed.args),
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }


if __name__ == "__main__":
    main()
