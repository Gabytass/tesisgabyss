import firebase_admin
from firebase_admin import credentials, firestore
import os

# Obtener ruta absoluta al archivo de credenciales JSON
cred_path = os.path.join(os.path.dirname(__file__), "rojasgabriela-bffec-firebase-adminsdk-fbsvc-ef70b41578.json")

# Verificar que el archivo exista
if not os.path.exists(cred_path):
    raise FileNotFoundError(f"No se encontró el archivo de credenciales en {cred_path}")

# Cargar credenciales
cred = credentials.Certificate(cred_path)

# Inicializar Firebase si no está inicializado (previene errores al recargar)
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

# Cliente de Firestore
db = firestore.client()

