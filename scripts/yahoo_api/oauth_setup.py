"""One-time (and refresh) OAuth2 setup for the Yahoo Fantasy Sports API.

Usage:
    python -m scripts.yahoo_api.oauth_setup auth-url
        Prints the URL to open in a browser to authorize this app.

    python -m scripts.yahoo_api.oauth_setup exchange <code>
        Exchanges the authorization code (copied from the failed
        localhost redirect's address bar) for an access + refresh token,
        and saves them to data/.credentials/yahoo_tokens.json.

    python -m scripts.yahoo_api.oauth_setup refresh
        Uses the saved refresh token to get a new access token (access
        tokens expire after about an hour; refresh tokens are long-lived).
"""
import base64
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

CREDS_PATH = Path(__file__).resolve().parents[2] / "data" / ".credentials" / "yahoo_oauth.json"
TOKENS_PATH = Path(__file__).resolve().parents[2] / "data" / ".credentials" / "yahoo_tokens.json"

AUTH_URL = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"


def load_creds():
    return json.loads(CREDS_PATH.read_text())


def print_auth_url():
    creds = load_creds()
    params = {
        "client_id": creds["client_id"],
        "redirect_uri": creds["redirect_uri"],
        "response_type": "code",
        "language": "en-us",
        # Yahoo's Fantasy Sports API has, in practice, mostly gated access via
        # the app's "API Permissions" checkbox (developer.yahoo.com/apps) rather
        # than this scope param -- but requesting it explicitly is free and some
        # accounts do need it, so include it on every login.
        "scope": "fspt-r",
    }
    print(f"{AUTH_URL}?{urlencode(params)}")


def _basic_auth_header(creds):
    raw = f"{creds['client_id']}:{creds['client_secret']}".encode()
    return base64.b64encode(raw).decode()


def extract_code(code_or_url):
    """Accepts either a bare code or the full (failed-to-load) redirect URL
    and returns just the code."""
    value = code_or_url.strip()
    if value.startswith("http://") or value.startswith("https://"):
        codes = parse_qs(urlparse(value).query).get("code")
        if not codes:
            raise ValueError(f"No 'code' query parameter found in URL: {value}")
        return codes[0]
    return value


def exchange_code(code_or_url):
    creds = load_creds()
    code = extract_code(code_or_url)
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {_basic_auth_header(creds)}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "redirect_uri": creds["redirect_uri"],
            "code": code,
        },
    )
    resp.raise_for_status()
    TOKENS_PATH.write_text(json.dumps(resp.json(), indent=2))
    print(f"Saved tokens to {TOKENS_PATH}")


def refresh_token():
    creds = load_creds()
    tokens = json.loads(TOKENS_PATH.read_text())
    resp = requests.post(
        TOKEN_URL,
        headers={
            "Authorization": f"Basic {_basic_auth_header(creds)}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "redirect_uri": creds["redirect_uri"],
            "refresh_token": tokens["refresh_token"],
        },
    )
    resp.raise_for_status()
    TOKENS_PATH.write_text(json.dumps(resp.json(), indent=2))
    print(f"Refreshed tokens, saved to {TOKENS_PATH}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "auth-url":
        print_auth_url()
    elif cmd == "exchange":
        exchange_code(sys.argv[2])
    elif cmd == "refresh":
        refresh_token()
    else:
        print(__doc__)
