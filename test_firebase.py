from firebase_config import db, bucket

# 🔹 Probar Firestore
if db:
    try:
        docs = db.collection('productos').stream()  # 👈 usa la colección correcta
        print("📦 Productos encontrados en Firestore:")
        for doc in docs:
            print(f"{doc.id} => {doc.to_dict()}")
    except Exception as e:
        print(f"❌ Error al leer Firestore: {e}")
else:
    print("❌ Firestore no inicializado")

# 🔹 Probar Storage
if bucket:
    try:
        blobs = list(bucket.list_blobs())
        print("📂 Archivos en bucket:")
        for b in blobs[:10]:  # mostrar máximo 10
            print("-", b.name)
    except Exception as e:
        print(f"❌ Error al listar Storage: {e}")
else:
    print("❌ Storage no inicializado")
