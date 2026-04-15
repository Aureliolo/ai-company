"""GitHub REST API client for code modification proposals.

Pushes file changes, creates branches and draft PRs via the GitHub
Contents and Git Refs APIs.  No local ``git`` or ``gh`` CLI required,
making this safe to run inside Docker containers.
"""

import base64
from typing import Any, Self

import httpx

from synthorg.meta.models import CodeChange, CodeOperation
from synthorg.observability import get_logger
from synthorg.observability.events.meta import (
    META_CODE_BRANCH_CREATED,
    META_CODE_FILE_WRITTEN,
    META_CODE_GITHUB_API_FAILED,
    META_CODE_PR_CREATED,
)

logger = get_logger(__name__)

_DEFAULT_TIMEOUT = 30


class HttpGitHubClient:
    """GitHub REST API client backed by httpx.

    Uses the Contents API for file operations (one commit per file)
    and the Git Refs API for branch management.

    Args:
        token: GitHub personal access token or app installation token.
        repo: Repository in ``owner/repo`` format.
        base_branch: Default branch to create feature branches from.
        timeout: HTTP request timeout in seconds.
    """

    def __init__(
        self,
        *,
        token: str,
        repo: str,
        base_branch: str = "main",
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token
        self._repo = repo
        self._base_branch = base_branch
        self._timeout = timeout
        # Lazily created to avoid deepcopy issues (RLock inside
        # httpx.AsyncClient is not picklable, and the meta factory
        # deep-copies the appliers registry).
        self.__client: httpx.AsyncClient | None = None

    @property
    def _client(self) -> httpx.AsyncClient:
        """Lazily create the httpx client on first use."""
        if self.__client is None:
            self.__client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=self._timeout,
            )
        return self.__client

    async def aclose(self) -> None:
        """Close the underlying httpx client if it was created."""
        if self.__client is not None:
            await self.__client.aclose()
            self.__client = None

    async def __aenter__(self) -> Self:
        """Support ``async with`` usage."""
        return self

    async def __aexit__(self, *exc: object) -> None:
        """Close on context manager exit."""
        await self.aclose()

    async def create_branch(self, name: str) -> None:
        """Create a branch from the default branch HEAD.

        Args:
            name: Branch name to create.

        Raises:
            RuntimeError: If the API call fails.
        """
        sha = await self._get_branch_sha(self._base_branch)
        resp = await self._client.post(
            f"/repos/{self._repo}/git/refs",
            json={"ref": f"refs/heads/{name}", "sha": sha},
        )
        _check_response(resp, f"create branch '{name}'")
        logger.info(
            META_CODE_BRANCH_CREATED,
            branch=name,
            from_sha=sha[:8],
        )

    async def push_change(
        self,
        *,
        branch: str,
        change: CodeChange,
        message: str,
    ) -> None:
        """Push a single file change to a branch.

        Args:
            branch: Target branch name.
            change: The code change to push.
            message: Commit message.

        Raises:
            RuntimeError: If the API call fails.
        """
        if change.operation == CodeOperation.DELETE:
            await self._delete_file(branch, change.file_path, message)
        else:
            await self._create_or_update_file(
                branch,
                change.file_path,
                change.new_content,
                message,
                modify=change.operation == CodeOperation.MODIFY,
            )
        logger.info(
            META_CODE_FILE_WRITTEN,
            operation=change.operation.value,
            file_path=change.file_path,
        )

    async def create_draft_pr(
        self,
        *,
        head: str,
        title: str,
        body: str,
    ) -> str:
        """Create a draft pull request.

        Args:
            head: Head branch name.
            title: PR title.
            body: PR body (Markdown).

        Returns:
            URL of the created PR.

        Raises:
            RuntimeError: If the API call fails.
        """
        resp = await self._client.post(
            f"/repos/{self._repo}/pulls",
            json={
                "title": title,
                "body": body,
                "head": head,
                "base": self._base_branch,
                "draft": True,
            },
        )
        _check_response(resp, "create draft PR")
        pr_url: str = resp.json()["html_url"]
        logger.info(
            META_CODE_PR_CREATED,
            pr_url=pr_url,
        )
        return pr_url

    async def delete_branch(self, name: str) -> None:
        """Delete a remote branch.

        Args:
            name: Branch name to delete.

        Raises:
            RuntimeError: If the API call fails.
        """
        resp = await self._client.delete(
            f"/repos/{self._repo}/git/refs/heads/{name}",
        )
        if resp.status_code == 422:  # noqa: PLR2004
            # Only suppress "reference does not exist" -- other 422s
            # (e.g. protected branch) should still raise.
            if not _is_missing_ref(resp):
                _check_response(resp, f"delete branch '{name}'")
        else:
            _check_response(resp, f"delete branch '{name}'")

    # -- Private helpers ---------------------------------------------------

    async def _get_branch_sha(self, branch: str) -> str:
        """Get the HEAD commit SHA of a branch."""
        resp = await self._client.get(
            f"/repos/{self._repo}/git/ref/heads/{branch}",
        )
        _check_response(resp, f"get SHA for branch '{branch}'")
        sha: str = resp.json()["object"]["sha"]
        return sha

    async def _get_file_sha(
        self,
        branch: str,
        path: str,
    ) -> str:
        """Get the blob SHA of a file on a branch."""
        resp = await self._client.get(
            f"/repos/{self._repo}/contents/{path}",
            params={"ref": branch},
        )
        _check_response(resp, f"get SHA for file '{path}'")
        sha: str = resp.json()["sha"]
        return sha

    async def _create_or_update_file(
        self,
        branch: str,
        path: str,
        content: str,
        message: str,
        *,
        modify: bool,
    ) -> None:
        """Create or update a file on a branch."""
        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(
                content.encode("utf-8"),
            ).decode("ascii"),
            "branch": branch,
        }
        if modify:
            payload["sha"] = await self._get_file_sha(branch, path)
        resp = await self._client.put(
            f"/repos/{self._repo}/contents/{path}",
            json=payload,
        )
        _check_response(resp, f"push file '{path}'")

    async def _delete_file(
        self,
        branch: str,
        path: str,
        message: str,
    ) -> None:
        """Delete a file from a branch."""
        sha = await self._get_file_sha(branch, path)
        resp = await self._client.request(
            "DELETE",
            f"/repos/{self._repo}/contents/{path}",
            json={
                "message": message,
                "sha": sha,
                "branch": branch,
            },
        )
        _check_response(resp, f"delete file '{path}'")


def _is_missing_ref(resp: httpx.Response) -> bool:
    """Check if a 422 response indicates a missing git reference.

    Args:
        resp: The 422 response from GitHub.

    Returns:
        True if the error is "Reference does not exist".
    """
    try:
        data = resp.json()
    except ValueError, TypeError:
        return False
    msg = data.get("message", "")
    if "Reference does not exist" in msg:
        return True
    for err in data.get("errors", []):
        if isinstance(err, dict) and err.get("code") == "missing":
            return True
    return False


def _check_response(resp: httpx.Response, action: str) -> None:
    """Raise RuntimeError on non-2xx responses.

    Args:
        resp: The httpx response.
        action: Human-readable action description for the error message.

    Raises:
        RuntimeError: If the response status is not 2xx.
    """
    if resp.is_success:
        return
    body = resp.text[:500] if resp.text else "(empty)"
    msg = f"GitHub API failed to {action}: {resp.status_code} {body}"
    logger.error(
        META_CODE_GITHUB_API_FAILED,
        action=action,
        status_code=resp.status_code,
        response_body=body,
    )
    raise RuntimeError(msg)
