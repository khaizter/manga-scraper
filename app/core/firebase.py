import os

import firebase_admin
from firebase_admin import credentials, firestore

_app: firebase_admin.App | None = None
_db: firestore.Client | None = None


def initialize_firebase_app() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK.

    Credentials (pick one):
      - GOOGLE_APPLICATION_CREDENTIALS: path to service account JSON
      - FIREBASE_CREDENTIALS_PATH: same, explicit override
      - Application Default Credentials (Cloud Functions / gcloud auth)

    Optional:
      - FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT
    """
    global _app
    if _app is not None:
        return _app

    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    project_id = os.getenv('FIREBASE_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')

    options: dict[str, str] = {}
    if project_id:
        options['projectId'] = project_id

    if cred_path:
        cred = credentials.Certificate(cred_path)
        _app = firebase_admin.initialize_app(cred, options or None)
    else:
        _app = firebase_admin.initialize_app(options=options or None)

    return _app


def get_firestore_client() -> firestore.Client:
    global _db
    if _db is None:
        initialize_firebase_app()
        _db = firestore.client()
    return _db
