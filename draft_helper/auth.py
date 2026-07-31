"""Yahoo OAuth2 login without a running web server.

Yahoo's app-registration form rejects the classic "oob" (out-of-band)
redirect_uri as an invalid URI, so this uses a redirect_uri that doesn't need
to actually resolve to anything (default: https://localhost:8080 — must
exactly match whatever URI you registered the app with, set YAHOO_REDIRECT_URI
in .env if you used something else). After approving access, Yahoo sends the
browser to that URI with ?code=... in the query string; the page itself will
fail to load (nothing is listening on localhost), but the code is still
sitting right there in the address bar to copy — or just paste the whole URL,
see extract_code() below.
"""
from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

AUTHORIZE_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
DEFAULT_REDIRECT_URI = "https://localhost:8080"

DEFAULT_TOKEN_PATH = Path("data/.credentials/token.json")

# Refresh a bit before actual expiry to avoid racing a 401 mid-request.
EXPIRY_SAFETY_MARGIN_SECONDS = 60


class YahooAuthError(RuntimeError):
    pass


def extract_code(code_or_url: str) -> str:
    """Accepts either a bare verifier code or the full redirected URL
    (e.g. https://localhost:8080/?code=XXXX&...) and returns just the code."""
    value = code_or_url.strip()
    if value.startswith("http://") or value.startswith("https://"):
        params = parse_qs(urlparse(value).query)
        codes = params.get("code")
        if not codes:
            raise YahooAuthError(f"No 'code' query parameter found in URL: {value}")
        return codes[0]
    return value


@dataclass
class Token:
    access_token: str
    refresh_token: str
    expires_at: float  # unix timestamp

    def is_expired(self) -> bool:
        return time.time() >= (self.expires_at - EXPIRY_SAFETY_MARGIN_SECONDS)

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Token":
        return cls(
            access_token=d["access_token"],
            refresh_token=d["refresh_token"],
            expires_at=d["expires_at"],
        )


class YahooOAuth:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_path: Path = DEFAULT_TOKEN_PATH,
        redirect_uri: Optional[str] = None,
    ):
        if not client_id or not client_secret:
            raise YahooAuthError(
                "YAHOO_CLIENT_ID / YAHOO_CLIENT_SECRET are not set. "
                "Copy .env.example to .env and fill them in "
                "(register an app at https://developer.yahoo.com/apps/)."
            )
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_path = Path(token_path)
        self.redirect_uri = redirect_uri or os.environ.get("YAHOO_REDIRECT_URI", DEFAULT_REDIRECT_URI)
        self._token: Optional[Token] = self._load_token()

    # -- persistence --------------------------------------------------

    def _load_token(self) -> Optional[Token]:
        if not self.token_path.exists():
            return None
        try:
            return Token.from_dict(json.loads(self.token_path.read_text()))
        except (json.JSONDecodeError, KeyError):
            return None

    def _save_token(self, token: Token) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token.to_dict(), indent=2))
        self._token = token

    # -- authorize/exchange flow -----------------------------------

    def authorize_url(self) -> str:
        return (
            f"{AUTHORIZE_URL}?client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}&response_type=code&language=en-us"
        )

    def _basic_auth_header(self) -> str:
        raw = f"{self.client_id}:{self.client_secret}".encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    def exchange_code(self, code_or_url: str) -> Token:
        code = extract_code(code_or_url)
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {self._basic_auth_header()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri,
                "code": code,
            },
            timeout=30,
        )
        return self._token_from_response(resp)

    def refresh(self) -> Token:
        if not self._token:
            raise YahooAuthError("No token to refresh; run `draft-helper auth` first.")
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {self._basic_auth_header()}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "redirect_uri": self.redirect_uri,
                "refresh_token": self._token.refresh_token,
            },
            timeout=30,
        )
        return self._token_from_response(resp)

    def _token_from_response(self, resp: requests.Response) -> Token:
        if resp.status_code != 200:
            raise YahooAuthError(
                f"Yahoo token request failed ({resp.status_code}): {resp.text}"
            )
        body = resp.json()
        token = Token(
            access_token=body["access_token"],
            refresh_token=body["refresh_token"],
            expires_at=time.time() + float(body.get("expires_in", 3600)),
        )
        self._save_token(token)
        return token

    # -- public API -----------------------------------------------------

    def has_token(self) -> bool:
        return self._token is not None

    def get_valid_access_token(self) -> str:
        if not self._token:
            raise YahooAuthError(
                "Not authenticated. Run `python -m draft_helper.cli auth` first."
            )
        if self._token.is_expired():
            self.refresh()
        return self._token.access_token

    def interactive_login(self, code_input=input) -> None:
        """Prints the authorize URL and prompts the user to paste back the code (or full redirect URL)."""
        print("Open this URL in a browser, log in, and approve access:\n")
        print(f"  {self.authorize_url()}\n")
        code = code_input("Paste the verifier code (or the full redirected URL): ")
        self.exchange_code(code)
        print("Login successful — token saved.")
