import os, json
from firebase_config import db  # usa la conexión que ya tienes
from app import _normalize_product, _normalize_user, PRODUCTOS_JSON, USUARIOS_JSON

def sync_productos():
    if not db:
        print("⚠️ Firebase no disponible, no se puede sincronizar productos.")
        return

    if not os.path.exists(PRODUCTOS_JSON):
        print("⚠️ No hay archivo local de productos.")
        return

    with open(PRODUCTOS_JSON, "r", encoding="utf-8") as f:
        productos_local = json.load(f)

    for i, p in enumerate(productos_local):
        p = _normalize_product(p, i)
        pid = str(p["id"])
        doc_ref = db.collection("productos").document(pid)
        doc = doc_ref.get()

        if not doc.exists:
            doc_ref.set(p)
            print(f"⬆️ Producto subido a Firebase: {p['nombre']}")
        else:
            # 🔹 Si ya existe, actualizamos con los cambios locales
            doc_ref.update(p)
            print(f"🔄 Producto actualizado en Firebase: {p['nombre']}")

def sync_usuarios():
    if not db:
        print("⚠️ Firebase no disponible, no se puede sincronizar usuarios.")
        return

    if not os.path.exists(USUARIOS_JSON):
        print("⚠️ No hay archivo local de usuarios.")
        return

    with open(USUARIOS_JSON, "r", encoding="utf-8") as f:
        usuarios_local = json.load(f)

    for u in usuarios_local:
        u = _normalize_user(u)
        correo = u["correo"].lower()
        if not correo:
            continue
        doc_ref = db.collection("usuarios").document(correo)
        doc = doc_ref.get()
        if not doc.exists:
            doc_ref.set(u)
            print(f"⬆️ Usuario subido a Firebase: {u['correo']}")
        else:
            doc_ref.update(u)  # 🔹 Actualizar también usuarios
            print(f"🔄 Usuario actualizado en Firebase: {u['correo']}")

if __name__ == "__main__":
    print("🔄 Sincronizando productos...")
    sync_productos()
    print("🔄 Sincronizando usuarios...")
    sync_usuarios()
    print("🎉 Sincronización terminada.")


