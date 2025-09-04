import json
from firebase_admin import credentials, firestore, initialize_app

# Inicializar Firebase
cred = credentials.Certificate("rojasgabriela-bffec-firebase-adminsdk-fbsvc-0456a7442f.json")  # Pon tu credencial real
initialize_app(cred)

db = firestore.client()

# Datos del administrador
admin_data = {
    "nombre": "Rojas Benavides Gabriela Maribel",
    "correo": "rojasgabriela633@gmail.com",
    "clave": "$2b$12$gmD917DrMvwSw4zVVIoWH.Cu3ZLfcgSL7rqLPfmWeNgKA0gjl7DZK",  # El hash que generaste
    "rol": "admin"
}

# Guardar en Firebase
doc_ref = db.collection("usuarios").document(admin_data["correo"])
doc_ref.set(admin_data)

print("Administrador creado correctamente ✅")

# Guardar también en JSON local
usuarios_json = "usuarios.json"
try:
    with open(usuarios_json, "r", encoding="utf-8") as f:
        usuarios = json.load(f)
except FileNotFoundError:
    usuarios = []

# Revisar si ya existe
if not any(u.get("correo") == admin_data["correo"] for u in usuarios):
    usuarios.append(admin_data)
    with open(usuarios_json, "w", encoding="utf-8") as f:
        json.dump(usuarios, f, ensure_ascii=False, indent=2)
    print("Administrador agregado al JSON local ✅")
