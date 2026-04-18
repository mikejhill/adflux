"""Tiny Confluence Cloud REST client for the E2E suite.

Intentionally minimal — we only need create / get / delete on pages plus a
space-key→id lookup. Uses the v2 REST API exclusively so we get
`atlas_doc_format` body content without HTML transcoding.
"""

from __future__ import annotations

import base64
from typing import Any

import httpx


class ConfluenceError(RuntimeError):
    """Base class for Confluence-client failures."""


class ConfluenceAuthError(ConfluenceError):
    """The supplied credentials did not authenticate."""


class ConfluenceClient:
    """Thin wrapper over the Confluence Cloud v2 REST API."""

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
        self.default_space_id: str | None = None

    # --------------------------------------------------------------- lifecycle

    def close(self) -> None:
        self._http.close()

    # -------------------------------------------------------------------- auth

    def verify_auth(self) -> dict[str, Any]:
        """Hit a cheap authenticated endpoint; raise on failure."""
        r = self._http.get("/wiki/api/v2/spaces", params={"limit": 1})
        if r.status_code in (401, 403):
            raise ConfluenceAuthError(
                f"HTTP {r.status_code} from /wiki/api/v2/spaces — body: {r.text[:200]}"
            )
        r.raise_for_status()
        return r.json()

    def resolve_space_id(self, space_key: str) -> str:
        r = self._http.get("/wiki/api/v2/spaces", params={"keys": space_key, "limit": 5})
        r.raise_for_status()
        results = r.json().get("results", [])
        for space in results:
            if space.get("key") == space_key:
                return str(space["id"])
        raise ConfluenceError(f"Space with key '{space_key}' not found")

    # ------------------------------------------------------------------- pages

    def create_page(
        self,
        *,
        title: str,
        adf_value: str,
        space_id: str | None = None,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "spaceId": space_id or self._require_space(),
            "status": "current",
            "title": title,
            "body": {"representation": "atlas_doc_format", "value": adf_value},
        }
        if parent_id is not None:
            body["parentId"] = parent_id
        r = self._http.post("/wiki/api/v2/pages", json=body)
        if r.status_code >= 400:
            raise ConfluenceError(f"create_page failed {r.status_code}: {r.text}")
        return r.json()

    def get_page_adf(self, page_id: str) -> dict[str, Any]:
        r = self._http.get(
            f"/wiki/api/v2/pages/{page_id}",
            params={"body-format": "atlas_doc_format"},
        )
        if r.status_code >= 400:
            raise ConfluenceError(f"get_page failed {r.status_code}: {r.text}")
        return r.json()

    def find_page_by_title(
        self,
        *,
        title: str,
        space_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Return the first page matching ``title`` in the space, or ``None``."""
        space = space_id or self._require_space()
        r = self._http.get(
            "/wiki/api/v2/pages",
            params={"title": title, "space-id": space, "limit": 5},
        )
        if r.status_code >= 400:
            raise ConfluenceError(f"find_page_by_title failed {r.status_code}: {r.text}")
        for result in r.json().get("results", []):
            if result.get("title") == title:
                return dict(result)
        return None

    def ensure_parent_page(
        self,
        *,
        title: str,
        adf_value: str,
        space_id: str | None = None,
    ) -> str:
        """Return the page id for ``title``, creating it if it does not exist."""
        existing = self.find_page_by_title(title=title, space_id=space_id)
        if existing is not None:
            return str(existing["id"])
        page = self.create_page(title=title, adf_value=adf_value, space_id=space_id)
        return str(page["id"])

    def delete_page(self, page_id: str) -> None:
        r = self._http.delete(f"/wiki/api/v2/pages/{page_id}")
        if r.status_code >= 400 and r.status_code != 404:
            raise ConfluenceError(f"delete_page failed {r.status_code}: {r.text}")

    # --------------------------------------------------------------- internals

    def _require_space(self) -> str:
        if not self.default_space_id:
            raise ConfluenceError("default_space_id is not set on this client")
        return self.default_space_id
