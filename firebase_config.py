import firebase_admin
from firebase_admin import credentials, firestore, storage
import os

db = None
bucket = None

try:
    if os.path.exists("rojasgabriela-bffec-firebase-adminsdk-fbsvc-0456a7442f.json"):
        cred = credentials.Certificate("rojasgabriela-bffec-firebase-adminsdk-fbsvc-0456a7442f.json")
        firebase_admin.initialize_app(cred, {
            "storageBucket": "TU-PROYECTO.appspot.com"
        })
        db = firestore.client()
        bucket = storage.bucket()
    else:
        print("⚠️ Advertencia: No se encontró rojasgabriela-bffec-firebase-adminsdk-fbsvc-0456a7442f.json. Modo offline activado.")
except Exception as e:
    print(f"❌ Error inicializando Firebase: {e}")

