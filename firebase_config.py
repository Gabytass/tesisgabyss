import firebase_admin
from firebase_admin import credentials, firestore, storage, auth
import os
import tempfile
import json

db = None
bucket = None

try:
    # ----------------------------
    # 🔹 PRODUCCIÓN (Heroku)
    # ----------------------------
    firebase_key_json = os.environ.get("FIREBASE_CONFIG")  # ✅ cambiado aquí
    storage_bucket = os.environ.get("FIREBASE_STORAGE_BUCKET")

    if firebase_key_json and storage_bucket:
        try:
            # Si viene como string JSON bien formateado
            if firebase_key_json.strip().startswith("{"):
                cred_dict = json.loads(firebase_key_json)
                cred = credentials.Certificate(cred_dict)
            else:
                # Si vino como texto escapado, lo guardamos en archivo temporal
                with tempfile.NamedTemporaryFile(mode="w+", delete=False) as cred_file:
                    cred_file.write(firebase_key_json)
                    cred_file.flush()
                    cred = credentials.Certificate(cred_file.name)

            firebase_admin.initialize_app(cred, {"storageBucket": storage_bucket})
            db = firestore.client()
            bucket = storage.bucket()
            print("✅ Firebase inicializado en producción")
        except Exception as e:
            print(f"❌ Error usando FIREBASE_CONFIG: {e}")

    # ----------------------------
    # 🔹 DESARROLLO (local)
    # ----------------------------
    elif os.path.exists("rojasgabriela-bffec-firebase-adminsdk-fbsvc-0456a7442f.json"):
        cred = credentials.Certificate("rojasgabriela-bffec-firebase-adminsdk-fbsvc-0456a7442f.json")
        firebase_admin.initialize_app(cred, {"storageBucket": "rojasgabriela-bffec.appspot.com"})
        db = firestore.client()
        bucket = storage.bucket()
        print("✅ Firebase inicializado desde archivo local (desarrollo)")

    # ----------------------------
    # 🔹 MODO OFFLINE
    # ----------------------------
    else:
        print("⚠️ No se encontraron credenciales. Modo offline activado.")

except Exception as e:
    print(f"❌ Error inicializando Firebase: {e}")


# =====================================================
# 🔹 FUNCIONES DE USO GENERAL
# =====================================================

# ----------------------------
# PRODUCTOS
# ----------------------------
def agregar_producto(nombre, precio, imagen_local_path=None):
    """Agrega un producto a Firestore y opcionalmente sube la imagen a Storage"""
    if not db:
        print("❌ Firebase no está inicializado. No se puede agregar producto.")
        return None

    try:
        doc_ref = db.collection("productos").document()
        data = {
            "nombre": nombre,
            "precio": precio
        }

        # Subir imagen a Storage si existe
        if imagen_local_path and bucket:
            imagen_blob = bucket.blob(f"productos/{os.path.basename(imagen_local_path)}")
            imagen_blob.upload_from_filename(imagen_local_path)
            imagen_blob.make_public()
            data["imagen"] = imagen_blob.public_url

        doc_ref.set(data)
        print(f"✅ Producto '{nombre}' agregado con ID: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        print(f"❌ Error agregando producto: {e}")
        return None


def obtener_productos():
    """Obtiene todos los productos de Firestore"""
    try:
        productos = []
        docs = db.collection("productos").stream()
        for d in docs:
            prod = d.to_dict()
            prod["id"] = d.id
            productos.append(prod)
        return productos
    except Exception as e:
        print(f"❌ Error obteniendo productos: {e}")
        return []


def eliminar_producto(producto_id):
    """Elimina un producto de Firestore"""
    try:
        db.collection("productos").document(producto_id).delete()
        print(f"✅ Producto {producto_id} eliminado")
    except Exception as e:
        print(f"❌ Error eliminando producto: {e}")


# ----------------------------
# USUARIOS
# ----------------------------
def registrar_usuario(nombre, correo, clave, rol="user"):
    """Crea un usuario en Firebase Authentication y lo guarda en Firestore"""
    if not db:
        print("❌ Firebase no inicializado.")
        return None

    try:
        # Crear usuario en Authentication
        user = auth.create_user(
            email=correo,
            password=clave,
            display_name=nombre
        )

        # Guardar datos extra en Firestore
        db.collection("usuarios").document(user.uid).set({
            "nombre": nombre,
            "correo": correo,
            "rol": rol
        })

        print(f"✅ Usuario '{nombre}' creado con UID: {user.uid}")
        return user.uid

    except Exception as e:
        print(f"❌ Error registrando usuario: {e}")
        return None


def obtener_usuarios():
    """Obtiene todos los usuarios guardados en Firestore"""
    try:
        usuarios = []
        docs = db.collection("usuarios").stream()
        for d in docs:
            u = d.to_dict()
            u["id"] = d.id
            usuarios.append(u)
        return usuarios
    except Exception as e:
        print(f"❌ Error obteniendo usuarios: {e}")
        return []


def eliminar_usuario(uid):
    """Elimina un usuario de Authentication y Firestore"""
    try:
        auth.delete_user(uid)
        db.collection("usuarios").document(uid).delete()
        print(f"✅ Usuario {uid} eliminado")
    except Exception as e:
        print(f"❌ Error eliminando usuario: {e}")




