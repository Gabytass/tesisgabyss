import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# Obtener credenciales desde la variable de entorno
cred_json = os.environ.get("FIREBASE_CREDENTIALS")
if not cred_json:
    raise ValueError("No se encontró la variable de entorno FIREBASE_CREDENTIALS")

cred_dict = json.loads(cred_json)
cred = credentials.Certificate(cred_dict)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()


