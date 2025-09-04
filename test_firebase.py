from firebase_config import db, bucket

# Probar Firestore
if db:
    docs = db.collection('productos_tesisgaby').stream()
    for doc in docs:
        print(doc.id, doc.to_dict())
else:
    print("❌ Firestore no inicializado")

# Probar Storage
if bucket:
    blobs = list(bucket.list_blobs())
    print(f"Archivos en bucket: {[b.name for b in blobs]}")
else:
    print("❌ Storage no inicializado")
