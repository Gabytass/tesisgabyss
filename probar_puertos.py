import socket

puertos = [25, 465, 587, 2525, 1025]  # puertos comunes de SMTP
host = "smtp.gmail.com"               # prueba con Gmail primero

for puerto in puertos:
    try:
        sock = socket.create_connection((host, puerto), timeout=5)
        print(f"✅ Conectado a {host}:{puerto}")
        sock.close()
    except Exception as e:
        print(f"❌ No se pudo conectar a {host}:{puerto}: {e}")
