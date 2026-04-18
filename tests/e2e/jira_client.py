"""Tiny Jira Cloud REST client for the E2E suite.

Covers only what the round-trip tests need: create issue with ADF
description, fetch issue (description in ADF), and transition the issue
to a closed/done status. Issues are never deleted — closing leaves an
audit trail in the project.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx


class JiraError(RuntimeError):
    """Base class for Jira-client failures."""


class JiraAuthError(JiraError):
    """Supplied credentials did not authenticate."""


class JiraClient:
    """Thin wrapper over the Jira Cloud REST API v3."""

    def __init__(self, *, site: str, email: str, api_token: str, timeout: float = 30.0) -> None:
        if not site or not email or not api_token:
            raise ValueError("site, email, and api_token are all required")
        token = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._http = httpx.Client(
            base_url=f"https://{site}",
            headers={
                "Authorization": f"Basic {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "adflux-e2e/0.1",
            },
            timeout=timeout,
        )

    # --------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self._http.close()

    # -------------------------------------------------------------------- auth

    def verify_auth(self) -> dict[str, Any]:
        """Hit a cheap authenticated endpoint; raise on failure."""
        r = self._http.get("/rest/api/3/myself")
        if r.status_code in (401, 403):
            raise JiraAuthError(
                f"HTTP {r.status_code} from /rest/api/3/myself — body: {r.text[:200]}"
            )
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------ issues

    def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        adf_description: dict[str, Any],
        issue_type: str = "Task",
    ) -> dict[str, Any]:
        """Create a Jira issue with an ADF description body."""
        body: dict[str, Any] = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "description": adf_description,
            }
        }
        r = self._http.post("/rest/api/3/issue", json=body)
        if r.status_code >= 400:
            raise JiraError(f"create_issue failed {r.status_code}: {r.text}")
        return r.json()

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        """Fetch an issue's full payload (description as ADF JSON)."""
        r = self._http.get(f"/rest/api/3/issue/{issue_key}")
        if r.status_code >= 400:
            raise JiraError(f"get_issue failed {r.status_code}: {r.text}")
        return r.json()

    def list_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        r = self._http.get(f"/rest/api/3/issue/{issue_key}/transitions")
        if r.status_code >= 400:
            raise JiraError(f"list_transitions failed {r.status_code}: {r.text}")
        results = r.json().get("transitions", [])
        return [dict(t) for t in results]

    def close_issue(
        self,
        issue_key: str,
        *,
        preferred: tuple[str, ...] = ("Done", "Closed", "Resolve", "Resolved"),
    ) -> str:
        """Transition the issue to a terminal status. Returns the chosen transition name."""
        transitions = self.list_transitions(issue_key)
        if not transitions:
            raise JiraError(f"no transitions available for {issue_key}")

        chosen: dict[str, Any] | None = None
        for name in preferred:
            for t in transitions:
                if t.get("name", "").lower() == name.lower():
                    chosen = t
                    break
            if chosen is not None:
                break
        if chosen is None:
            for t in transitions:
                status_category = t.get("to", {}).get("statusCategory", {}).get("key")
                if status_category == "done":
                    chosen = t
                    break
        if chosen is None:
            raise JiraError(
                f"no terminal transition found for {issue_key} "
                f"(available: {[t.get('name') for t in transitions]})"
            )

        r = self._http.post(
            f"/rest/api/3/issue/{issue_key}/transitions",
            json={"transition": {"id": chosen["id"]}},
        )
        if r.status_code >= 400:
            raise JiraError(f"close_issue failed {r.status_code}: {r.text}")
        return str(chosen.get("name", ""))
