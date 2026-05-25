"""Helpers for triggering GitHub Actions workflows from the editor."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request


@dataclass
class WorkflowDispatchResult:
    ok: bool
    message: str
    repo: str = ""
    ref: str = ""
    workflow: str = ""
    url: str = ""
    provider: str = ""
    tag: str = ""


def trigger_github_workflow(repo_dir: str,
                            workflow_file: str,
                            ref: str | None = None,
                            require_clean: bool = True,
                            tag_fallback_prefix: str | None = None,
                            progress=None) -> WorkflowDispatchResult:
    """Trigger a workflow_dispatch workflow for the current GitHub repo."""
    root = _git_root(repo_dir)
    workflow_file = str(workflow_file or "").strip()
    if not workflow_file:
        return WorkflowDispatchResult(False, "GitHub workflow file is empty")
    workflow_path = root / ".github" / "workflows" / workflow_file
    if not workflow_path.is_file():
        return WorkflowDispatchResult(
            False,
            f"GitHub workflow not found: .github/workflows/{workflow_file}",
            workflow=workflow_file,
        )

    _progress(progress, "Checking GitHub repository")
    branch = ref or _current_branch(root)
    if not branch:
        return WorkflowDispatchResult(
            False,
            "Current git ref is detached. Check out a branch before running Actions.",
            workflow=workflow_file,
        )
    if require_clean:
        clean_ok, clean_msg = _check_remote_ready(root, branch)
        if not clean_ok:
            return WorkflowDispatchResult(
                False,
                clean_msg,
                ref=branch,
                workflow=workflow_file,
            )

    repo = (_env("PVNM_GITHUB_REPOSITORY")
            or _github_repo_from_remote(_git_stdout(root, "remote", "get-url",
                                                    "origin")))
    if not repo:
        return WorkflowDispatchResult(
            False,
            "Could not infer GitHub repository from origin remote.",
            ref=branch,
            workflow=workflow_file,
        )

    direct_error: WorkflowDispatchResult | None = None
    gh = _find_gh()
    if gh:
        _progress(progress, "Running gh workflow dispatch")
        result = _dispatch_with_gh(root, gh, workflow_file, branch, repo,
                                   progress)
        if result.ok:
            return result
        direct_error = result
        token = _github_token()
        if not token and not tag_fallback_prefix:
            return result

    token = _github_token()
    if token:
        _progress(progress, "Running GitHub API dispatch")
        result = _dispatch_with_api(repo, workflow_file, branch, token, progress)
        if result.ok:
            return result
        direct_error = result
        if not tag_fallback_prefix:
            return result

    if tag_fallback_prefix:
        _progress(progress, "Pushing GitHub Actions trigger tag")
        return _dispatch_with_git_tag(
            root, repo, workflow_file, branch, tag_fallback_prefix,
            direct_error=direct_error, progress=progress)

    return WorkflowDispatchResult(
        False,
        "GitHub authentication is not configured. Install gh and run "
        "`gh auth login`, or set PVNM_GITHUB_TOKEN.",
        repo=repo,
        ref=branch,
        workflow=workflow_file,
        url=_workflow_url(repo, workflow_file),
    )


def _progress(progress, message: str) -> None:
    if progress:
        try:
            progress(message)
        except Exception:
            pass


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _run_git(root: Path, *args: str, timeout: int = 15) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _git_stdout(root: Path, *args: str, timeout: int = 15) -> str:
    try:
        result = _run_git(root, *args, timeout=timeout)
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    return (result.stdout or "").strip()


def _git_root(repo_dir: str) -> Path:
    base = Path(repo_dir or ".").expanduser().resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(base),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip()).resolve()
    except Exception:
        pass
    return base


def _current_branch(root: Path) -> str:
    branch = _git_stdout(root, "branch", "--show-current")
    if branch:
        return branch
    ref = _git_stdout(root, "rev-parse", "--abbrev-ref", "HEAD")
    return "" if ref == "HEAD" else ref


def _check_remote_ready(root: Path, branch: str) -> tuple[bool, str]:
    status = _git_stdout(root, "status", "--porcelain")
    if status:
        first = "; ".join(status.splitlines()[:4])
        return (
            False,
            "Git working tree has local changes. Commit and push before "
            f"running Actions: {first}",
        )

    upstream = _git_stdout(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    if not upstream:
        return (
            False,
            f"Branch `{branch}` has no upstream. Push with "
            f"`git push -u origin {branch}` before running Actions.",
        )

    counts = _git_stdout(root, "rev-list", "--left-right", "--count",
                         f"{upstream}...HEAD")
    parts = counts.split()
    if len(parts) == 2:
        try:
            ahead = int(parts[1])
        except ValueError:
            ahead = 0
        if ahead > 0:
            return (
                False,
                f"Branch `{branch}` has {ahead} unpushed commit(s). Push "
                "before running Actions.",
            )
    return True, ""


def _github_repo_from_remote(remote_url: str) -> str:
    raw = str(remote_url or "").strip()
    if not raw:
        return ""
    raw = raw.removesuffix(".git").rstrip("/")
    patterns = [
        r"^git@github\.com:(?P<repo>[^/]+/[^/]+)$",
        r"^ssh://git@github\.com/(?P<repo>[^/]+/[^/]+)$",
        r"^https://github\.com/(?P<repo>[^/]+/[^/]+)$",
        r"^http://github\.com/(?P<repo>[^/]+/[^/]+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, raw)
        if match:
            return match.group("repo")
    return ""


def _find_gh() -> str:
    found = shutil.which("gh")
    if found:
        return found
    for path in ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"):
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return ""


def _github_token() -> str:
    for name in ("PVNM_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        value = _env(name)
        if value:
            return value
    return ""


def _workflow_url(repo: str, workflow_file: str) -> str:
    if not repo:
        return ""
    return f"https://github.com/{repo}/actions/workflows/{workflow_file}"


def _dispatch_with_gh(root: Path, gh: str, workflow_file: str, ref: str,
                      repo: str, progress) -> WorkflowDispatchResult:
    try:
        result = subprocess.run(
            [gh, "workflow", "run", workflow_file, "--ref", ref],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception as exc:
        return WorkflowDispatchResult(
            False,
            f"gh workflow run failed: {exc}",
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="gh",
            url=_workflow_url(repo, workflow_file),
        )

    if result.returncode != 0:
        msg = (result.stderr or result.stdout or "gh workflow run failed").strip()
        return WorkflowDispatchResult(
            False,
            msg[:240],
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="gh",
            url=_workflow_url(repo, workflow_file),
        )

    url = _latest_run_url_with_gh(root, gh, workflow_file, ref, progress)
    return WorkflowDispatchResult(
        True,
        "GitHub Actions workflow started",
        repo=repo,
        ref=ref,
        workflow=workflow_file,
        provider="gh",
        url=url or _workflow_url(repo, workflow_file),
    )


def _latest_run_url_with_gh(root: Path, gh: str, workflow_file: str,
                            ref: str, progress) -> str:
    for _ in range(3):
        time.sleep(1)
        _progress(progress, "Looking up GitHub Actions run")
        try:
            result = subprocess.run(
                [gh, "run", "list",
                 "--workflow", workflow_file,
                 "--branch", ref,
                 "--event", "workflow_dispatch",
                 "--limit", "1",
                 "--json", "url,createdAt,status,conclusion"],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception:
            continue
        if result.returncode != 0:
            continue
        try:
            runs = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            continue
        if isinstance(runs, list) and runs:
            url = str(runs[0].get("url") or "").strip()
            if url:
                return url
    return ""


def _dispatch_with_api(repo: str, workflow_file: str, ref: str, token: str,
                       progress) -> WorkflowDispatchResult:
    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_file}/dispatches"
    payload = json.dumps({"ref": ref}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "PVNM",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = int(getattr(response, "status", 0) or 0)
    except urllib.error.HTTPError as exc:
        body = _read_http_error(exc)
        msg = body or f"GitHub API dispatch failed: HTTP {exc.code}"
        return WorkflowDispatchResult(
            False,
            msg[:240],
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="api",
            url=_workflow_url(repo, workflow_file),
        )
    except Exception as exc:
        return WorkflowDispatchResult(
            False,
            f"GitHub API dispatch failed: {exc}",
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="api",
            url=_workflow_url(repo, workflow_file),
        )

    if status not in (200, 201, 202, 204):
        return WorkflowDispatchResult(
            False,
            f"GitHub API dispatch returned HTTP {status}",
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="api",
            url=_workflow_url(repo, workflow_file),
        )

    run_url = _latest_run_url_with_api(repo, workflow_file, ref, token, progress)
    return WorkflowDispatchResult(
        True,
        "GitHub Actions workflow started",
        repo=repo,
        ref=ref,
        workflow=workflow_file,
        provider="api",
        url=run_url or _workflow_url(repo, workflow_file),
    )


def _dispatch_with_git_tag(root: Path, repo: str, workflow_file: str,
                           ref: str, tag_prefix: str,
                           direct_error: WorkflowDispatchResult | None,
                           progress) -> WorkflowDispatchResult:
    sha = _git_stdout(root, "rev-parse", "--short=12", "HEAD") or "head"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    safe_prefix = _safe_tag_prefix(tag_prefix)
    tag = f"{safe_prefix}-{stamp}-{sha[:7]}"

    create = _run_git(root, "tag", tag, timeout=15)
    if create.returncode != 0:
        return WorkflowDispatchResult(
            False,
            _tag_fallback_error(
                "Could not create local trigger tag",
                create.stderr or create.stdout,
                direct_error,
            ),
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="git tag",
            url=_workflow_url(repo, workflow_file),
            tag=tag,
        )

    try:
        push = _run_git(root, "push", "origin", f"refs/tags/{tag}",
                        timeout=120)
    except Exception as exc:
        _run_git(root, "tag", "-d", tag, timeout=15)
        return WorkflowDispatchResult(
            False,
            _tag_fallback_error(
                "Could not push trigger tag",
                str(exc),
                direct_error,
            ),
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="git tag",
            url=_workflow_url(repo, workflow_file),
            tag=tag,
        )

    _run_git(root, "tag", "-d", tag, timeout=15)
    if push.returncode != 0:
        return WorkflowDispatchResult(
            False,
            _tag_fallback_error(
                "Could not push trigger tag",
                push.stderr or push.stdout,
                direct_error,
            ),
            repo=repo,
            ref=ref,
            workflow=workflow_file,
            provider="git tag",
            url=_workflow_url(repo, workflow_file),
            tag=tag,
        )

    _progress(progress, "GitHub Actions trigger tag pushed")
    return WorkflowDispatchResult(
        True,
        f"GitHub Actions workflow started by tag {tag}",
        repo=repo,
        ref=tag,
        workflow=workflow_file,
        provider="git tag",
        url=_workflow_url(repo, workflow_file),
        tag=tag,
    )


def _safe_tag_prefix(raw: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._/-]+", "-", str(raw or "").strip())
    safe = safe.strip("./-")
    return safe or "pvnm-build"


def _tag_fallback_error(prefix: str, detail: str,
                        direct_error: WorkflowDispatchResult | None) -> str:
    parts = [prefix]
    detail = str(detail or "").strip()
    if detail:
        parts.append(detail[:160])
    if direct_error and direct_error.message:
        parts.append(f"Direct dispatch also failed: {direct_error.message[:120]}")
    return ". ".join(parts)


def _latest_run_url_with_api(repo: str, workflow_file: str, ref: str,
                             token: str, progress) -> str:
    encoded_ref = urllib.parse.quote(ref, safe="")
    url = (
        f"https://api.github.com/repos/{repo}/actions/workflows/"
        f"{workflow_file}/runs?branch={encoded_ref}"
        "&event=workflow_dispatch&per_page=1"
    )
    for _ in range(3):
        time.sleep(1)
        _progress(progress, "Looking up GitHub Actions run")
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "User-Agent": "PVNM",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception:
            continue
        runs = data.get("workflow_runs") if isinstance(data, dict) else None
        if isinstance(runs, list) and runs:
            run_url = str(runs[0].get("html_url") or "").strip()
            if run_url:
                return run_url
    return ""


def _read_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if isinstance(data, dict):
        msg = str(data.get("message") or "").strip()
        if msg:
            return msg
    return raw.strip()
