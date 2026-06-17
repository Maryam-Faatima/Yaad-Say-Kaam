import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these scopes, delete the file token.pickle.
# Using 'modify' scope to allow reading and marking emails as read.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

def get_gmail_service():
    """
    Authenticates and returns the Gmail API service instance.
    Expects credentials.json in the project root.
    """
    creds = None
    # Resolve the paths relative to the project root
    base_dir = os.path.join(os.path.dirname(__file__), '..')
    token_path = os.path.join(base_dir, 'token.pickle')
    creds_path = os.path.join(base_dir, 'credentials.json')

    # Load existing token if available
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
            
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)

    try:
        service = build('gmail', 'v1', credentials=creds)
        return service
    except Exception as error:
        raise Exception(f"An error occurred during service creation: {error}")

def _get_body_from_payload(payload: dict) -> str:
    """
    Recursively extract the plain-text body from the email payload.
    """
    if 'parts' in payload:
        for part in payload['parts']:
            if part.get('mimeType') == 'text/plain':
                data = part['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8')
            elif 'parts' in part:
                # Recursively search in nested parts
                found = _get_body_from_payload(part)
                if found != "No plain-text body found.":
                    return found
    else:
        # If the email is not multipart and is text/plain
        if payload.get('mimeType') == 'text/plain':
            data = payload['body'].get('data')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8')
    return "No plain-text body found."

def fetch_unread_emails() -> list[dict]:
    """
    Fetches up to 10 unread emails from the user's Gmail inbox.
    Returns a list of dictionaries with id, sender, subject, date, and body.
    """
    try:
        service = get_gmail_service()
        # Fetch message IDs of unread emails
        results = service.users().messages().list(userId='me', q='is:unread', maxResults=10).execute()
        messages = results.get('messages', [])

        email_data = []

        if not messages:
            print("Fetched 0 unread emails.")
            return email_data

        for message in messages:
            msg_id = message['id']
            # Fetch full message
            msg = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
            
            payload = msg.get('payload', {})
            headers = payload.get('headers', [])
            
            subject = "No Subject"
            sender = "Unknown Sender"
            date = "Unknown Date"
            
            # Extract headers
            for header in headers:
                name = header.get('name', '').lower()
                if name == 'subject':
                    subject = header.get('value')
                elif name == 'from':
                    sender = header.get('value')
                elif name == 'date':
                    date = header.get('value')
            
            # Extract body
            body = _get_body_from_payload(payload)
            
            email_data.append({
                'id': msg_id,
                'sender': sender,
                'subject': subject,
                'date': date,
                'body': body
            })
            
        print(f"Fetched {len(email_data)} unread emails.")
        return email_data

    except HttpError as error:
        raise Exception(f"An API error occurred: {error}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {e}")

def mark_as_read(message_id: str):
    """
    Marks the specified email as read by removing the 'UNREAD' label.
    """
    try:
        service = get_gmail_service()
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['UNREAD']}
        ).execute()
        print(f"Message {message_id} marked as read.")
    except HttpError as error:
        raise Exception(f"An API error occurred while marking as read: {error}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred while marking as read: {e}")
