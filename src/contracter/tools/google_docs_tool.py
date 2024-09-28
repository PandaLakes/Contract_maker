from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os

class GoogleDocsTool:
    SCOPES = ['https://www.googleapis.com/auth/documents']

    def __init__(self):
        self.creds = None
        self.token_path = os.path.join(os.path.dirname(__file__), 'token_docs.json')
        self.credentials_path = os.path.join(os.path.dirname(__file__), 'credentials.json')
        self.service = None
        self.google_doc_id = None

    def authenticate_google_docs(self):
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
        self.service = build('docs', 'v1', credentials=self.creds)

    def create_document(self, title):
        if self.service is None:
            self.authenticate_google_docs()
        document = self.service.documents().create(body={'title': title}).execute()
        self.google_doc_id = document['documentId']
        if self.google_doc_id:
            print(f"Document created with ID: {self.google_doc_id}")
        return self.google_doc_id

    def write_to_document(self, document_id, content):
        if not document_id:
            raise ValueError("Google Doc ID is not set.")
        if self.service is None:
            self.authenticate_google_docs()

        requests = []
        index = 1  # Start after the title

        for line in content.split('\n'):
            if line.strip().startswith('**') and line.strip().endswith('**'):
                text = line.strip('**').strip()
                if text:
                    requests.append({
                        'insertText': {
                            'location': {
                                'index': index,
                            },
                            'text': text + '\n'
                        }
                    })
                    requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': index,
                                'endIndex': index + len(text)
                            },
                            'paragraphStyle': {
                                'namedStyleType': 'HEADING_1',
                                'alignment': 'START'
                            },
                            'fields': 'namedStyleType,alignment'
                        }
                    })
                    index += len(text) + 1
            else:
                parts = line.split('**')
                for i, part in enumerate(parts):
                    if i % 2 == 0:
                        if part:
                            requests.append({
                                'insertText': {
                                    'location': {
                                        'index': index,
                                    },
                                    'text': part
                                }
                            })
                            requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': index,
                                        'endIndex': index + len(part)
                                    },
                                    'textStyle': {
                                        'fontSize': {
                                            'magnitude': 11,
                                            'unit': 'PT'
                                        }
                                    },
                                    'fields': 'fontSize'
                                }
                            })
                            index += len(part)
                    else:
                        if part:
                            requests.append({
                                'insertText': {
                                    'location': {
                                        'index': index,
                                    },
                                    'text': part
                                }
                            })
                            requests.append({
                                'updateTextStyle': {
                                    'range': {
                                        'startIndex': index,
                                        'endIndex': index + len(part)
                                    },
                                    'textStyle': {
                                        'bold': True,
                                        'fontSize': {
                                            'magnitude': 11,
                                            'unit': 'PT'
                                        }
                                    },
                                    'fields': 'bold,fontSize'
                                }
                            })
                            index += len(part)
                requests.append({
                    'insertText': {
                        'location': {
                            'index': index,
                        },
                        'text': '\n'
                    }
                })
                if index > 1:
                    requests.append({
                        'updateParagraphStyle': {
                            'range': {
                                'startIndex': index - len(line) - 1,
                                'endIndex': index
                            },
                            'paragraphStyle': {
                                'alignment': 'JUSTIFIED'
                            },
                            'fields': 'alignment'
                        }
                    })
                index += 1

        # Remove invalid updateParagraphStyle requests for first section break
        requests = [req for req in requests if not (req.get('updateParagraphStyle') and req['updateParagraphStyle']['range']['startIndex'] == 0)]

        result = self.service.documents().batchUpdate(
            documentId=document_id, body={'requests': requests}).execute()
        print(f"Content written to Google Doc with ID: {document_id}")
        return result
