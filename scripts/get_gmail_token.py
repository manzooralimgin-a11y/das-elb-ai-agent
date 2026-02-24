"""
One-time script to obtain Gmail OAuth2 refresh_token for rezeption@das-elb.de.

USAGE:
  1. Go to https://console.cloud.google.com
  2. Create a project and enable the Gmail API
  3. Create OAuth2 credentials (type: Desktop App)
  4. Download the credentials JSON
  5. Set GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET in your environment
  6. Run: python scripts/get_gmail_token.py
  7. Follow the browser prompt to authorize Das ELB's Gmail account
  8. Copy the printed refresh_token into your .env file

The refresh_token never expires as long as the app keeps making requests.
Store it securely in your production environment variables.
"""
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://mail.google.com/"]

CLIENT_CONFIG = {
    "installed": {
        "client_id": os.environ["GMAIL_CLIENT_ID"],
        "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
        "redirect_uris": ["http://localhost"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}

flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, scopes=SCOPES)
creds = flow.run_local_server(port=0)

print("\n" + "=" * 60)
print("SUCCESS! Copy the following into your .env file:")
print("=" * 60)
print(f"GMAIL_REFRESH_TOKEN={creds.refresh_token}")
print("=" * 60 + "\n")
