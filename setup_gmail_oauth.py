"""
Gmail OAuth2 Credentials Setup Script

This script helps you obtain the necessary Gmail credentials for the CEO Outreach Tool.
It will guide you through the OAuth2 authentication flow and output the credentials
in the format needed for your .env file.

Usage:
1. Download your OAuth2 credentials from Google Cloud Console as 'credentials.json'
2. Place credentials.json in the same directory as this script
3. Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
4. Run: python setup_gmail_oauth.py
5. Follow the browser authentication flow
6. Copy the output to your .env file
"""

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import json
import os
import pickle

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.compose']

def get_gmail_credentials():
    """Get Gmail OAuth2 credentials through browser flow"""
    creds = None
    
    # Check if we have existing credentials
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If credentials don't exist or are invalid, run OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("ERROR: credentials.json not found!")
                print("\nPlease follow these steps:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create/select your project")
                print("3. Enable Gmail API")
                print("4. Create OAuth 2.0 credentials (Desktop app)")
                print("5. Download credentials.json and place it in this directory")
                return None
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', 
                SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        # Save credentials for future use
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds

def format_credentials_for_env(creds):
    """Format credentials for .env file"""
    creds_data = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    
    return json.dumps(creds_data)

def main():
    print("=" * 70)
    print("Gmail OAuth2 Setup for CEO Outreach Tool")
    print("=" * 70)
    print()
    
    print("This script will help you set up Gmail API access.")
    print("You'll need to authenticate with a Google account that has Gmail access.")
    print()
    input("Press Enter to continue...")
    print()
    
    # Get credentials
    creds = get_gmail_credentials()
    
    if not creds:
        return
    
    print("\n" + "=" * 70)
    print("SUCCESS! Authentication complete.")
    print("=" * 70)
    print()
    
    # Format credentials
    creds_json = format_credentials_for_env(creds)
    
    print("Add this line to your backend/.env file:")
    print()
    print(f"GMAIL_CREDENTIALS='{creds_json}'")
    print()
    
    # Save to file for easy copy-paste
    with open('gmail_credentials_output.txt', 'w') as f:
        f.write(f"GMAIL_CREDENTIALS='{creds_json}'")
    
    print("This has also been saved to 'gmail_credentials_output.txt'")
    print()
    print("IMPORTANT SECURITY NOTES:")
    print("- Keep this credential string secret")
    print("- Never commit it to Git")
    print("- Use environment variables in production")
    print("- Rotate credentials regularly")
    print()
    print("Next steps:")
    print("1. Copy the GMAIL_CREDENTIALS line to your backend/.env file")
    print("2. Make sure your .env file is in .gitignore")
    print("3. For Render deployment, add it as an environment variable in the dashboard")
    print()

if __name__ == '__main__':
    main()
