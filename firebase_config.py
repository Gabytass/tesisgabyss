import firebase_admin
from firebase_admin import credentials, firestore
import os
import json

# Leer credenciales desde la variable de entorno
cred_json = os.environ.get("FIREBASE_CREDENTIALS")
if not cred_json:
    raise ValueError("No se encontró la variable de entorno FIREBASE_CREDENTIALS")

cred_dict = json.loads(cred_json)
cred = credentials.Certificate(cred_dict)

# Inicializar Firebase si no está inicializado
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Cliente de Firestore
db = firestore.client()


