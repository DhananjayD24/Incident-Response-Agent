import re
import subprocess
from pathlib import Path

from ..config import GIT_REPO_PATH


SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


def _run_git(args: list[str]) -> str:
    """Execute a read-only git command."""

    result = subprocess.run(
        ["git", "-C", GIT_REPO_PATH, *args],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "Git command failed"
        )

    return result.stdout


def get_recent_commits(
    service: str,
    limit: int,
) -> list[dict[str, str]]:
    """Read recent commits related to a service."""

    service_path = Path("services") / service

    if service_path.is_absolute():
        raise ValueError("Service path must be relative.")

    if ".." in service_path.parts:
        raise ValueError("Invalid service path.")

    output = _run_git(
        [
            "log",
            f"-{limit}",
            "--format=%H%x09%an%x09%ad%x09%s",
            "--date=iso",
            "--",
            str(service_path),
        ]
    )

    commits = []

    for line in output.splitlines():
        parts = line.split("\t", 3)

        if len(parts) != 4:
            continue

        sha, author, date, subject = parts

        commits.append(
            {
                "sha": sha,
                "author": author,
                "date": date,
                "subject": subject,
                "service": service,
            }
        )

    return commits


def get_commit_diff(sha: str) -> str:
    """Read the diff introduced by a specific commit."""

    if not SHA_PATTERN.fullmatch(sha):
        raise ValueError("Invalid commit SHA.")

    return _run_git(
        [
            "show",
            "--no-ext-diff",
            "--format=fuller",
            "--stat",
            sha,
        ]
        + [
            "--",
        ]
    )