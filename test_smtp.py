import smtplib
import os

MAIL_USER = os.getenv("MAIL_USER") or "tu_correo@gmail.com"
MAIL_PASS = os.getenv("MAIL_PASS") or "tu_app_password"

try:
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(MAIL_USER, MAIL_PASS)
        print("✅ Conexión SMTP exitosa")
except Exception as e:
    print("❌ Error conectando SMTP:", e)
