"""One-time helper: obtain a YouTube OAuth refresh token for the pipeline.

Prereq (in Google Cloud Console, your account):
  1. Create a project, enable "YouTube Data API v3".
  2. Configure the OAuth consent screen (External; add yourself as a Test user).
  3. Create an OAuth client of type "Desktop app" -> get Client ID + Client Secret.

Then run locally:
  pip install google-auth-oauthlib
  python scripts/get_youtube_token.py <CLIENT_ID> <CLIENT_SECRET>

A browser opens; approve access. The script prints the THREE values to set as
GitHub secrets: YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN.
"""
from __future__ import annotations

import sys

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: python scripts/get_youtube_token.py <CLIENT_ID> <CLIENT_SECRET>")
        return 2
    client_id, client_secret = sys.argv[1], sys.argv[2]

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("Install first:  pip install google-auth-oauthlib")
        return 1

    cfg = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(cfg, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    if not creds.refresh_token:
        print("No refresh token returned. Revoke prior access and retry with prompt=consent.")
        return 1
    print("\n=== Set these as GitHub repo secrets ===")
    print("YOUTUBE_CLIENT_ID    =", client_id)
    print("YOUTUBE_CLIENT_SECRET=", client_secret)
    print("YOUTUBE_REFRESH_TOKEN=", creds.refresh_token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
