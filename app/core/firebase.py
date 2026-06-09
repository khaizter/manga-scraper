import os

import firebase_admin
from firebase_admin import credentials, firestore, storage
from google.cloud.storage import Bucket

_app: firebase_admin.App | None = None
_db: firestore.Client | None = None
_bucket: Bucket | None = None


def _resolve_project_id() -> str | None:
    return os.getenv('FIREBASE_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')


def _resolve_storage_bucket_name() -> str | None:
    explicit = os.getenv('FIREBASE_STORAGE_BUCKET')
    if explicit:
        return explicit

    project_id = _resolve_project_id()
    if project_id:
        return f'{project_id}.firebasestorage.app'

    return None


def initialize_firebase_app() -> firebase_admin.App:
    """
    Initialize Firebase Admin SDK.

    Credentials (pick one):
      - GOOGLE_APPLICATION_CREDENTIALS: path to service account JSON
      - FIREBASE_CREDENTIALS_PATH: same, explicit override
      - Application Default Credentials (Cloud Functions / gcloud auth)

    Optional:
      - FIREBASE_PROJECT_ID or GOOGLE_CLOUD_PROJECT
      - FIREBASE_STORAGE_BUCKET (defaults to {projectId}.firebasestorage.app)
    """
    global _app
    if _app is not None:
        return _app

    cred_path = os.getenv('FIREBASE_CREDENTIALS_PATH') or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    project_id = _resolve_project_id()
    storage_bucket = _resolve_storage_bucket_name()

    options: dict[str, str] = {}
    if project_id:
        options['projectId'] = project_id
    if storage_bucket:
        options['storageBucket'] = storage_bucket

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


def get_storage_bucket() -> Bucket:
    """Return the configured Firebase Storage bucket."""
    global _bucket
    if _bucket is None:
        initialize_firebase_app()
        bucket_name = os.getenv('FIREBASE_STORAGE_BUCKET')
        _bucket = storage.bucket(bucket_name) if bucket_name else storage.bucket()
    return _bucket
