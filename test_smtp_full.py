import smtplib
import os
from email.mime.text import MIMEText

# --- Configuración ---
MAIL_USER = os.getenv("MAIL_USER") or "tu_correo@gmail.com"
MAIL_PASS = os.getenv("MAIL_PASS") or "tu_app_password"

msg = MIMEText("Este es un correo de prueba", 'html', 'utf-8')
msg['Subject'] = "Prueba SMTP"
msg['From'] = MAIL_USER
msg['To'] = MAIL_USER

# --- Función de prueba SSL ---
def probar_ssl():
    try:
        print("🔹 Probando SSL (puerto 465)...")
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(MAIL_USER, MAIL_PASS)
            server.sendmail(MAIL_USER, [MAIL_USER], msg.as_string())
        print("✅ SSL funciona correctamente!")
    except Exception as e:
        print("❌ SSL falla:", e)

# --- Función de prueba TLS ---
def probar_tls():
    try:
        print("🔹 Probando TLS (puerto 587)...")
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(MAIL_USER, MAIL_PASS)
            server.sendmail(MAIL_USER, [MAIL_USER], msg.as_string())
        print("✅ TLS funciona correctamente!")
    except Exception as e:
        print("❌ TLS falla:", e)

if __name__ == "__main__":
    probar_ssl()
    print("\n---\n")
    probar_tls()
