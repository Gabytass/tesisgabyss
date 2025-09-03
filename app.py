import os
import json
import uuid
import smtplib
from email.mime.text import MIMEText
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
from flask_bcrypt import Bcrypt
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from dotenv import load_dotenv
load_dotenv()  # Carga variables de .env



# Verificamos si se están leyendo las variables de entorno
print("📧 MAIL_USER:", os.getenv("MAIL_USER"))
print("🔑 MAIL_PASS:", os.getenv("MAIL_PASS"))


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'clave_secreta_local')  # Importante para sesiones



# -------- Firebase opcional --------
db = None
bucket = None
try:
    from firebase_config import db as _db, bucket as _bucket
    db = _db
    bucket = _bucket
    print("✅ Firebase disponible")
except Exception as e:
    print(f"⚠️  Firebase no disponible (modo offline): {e}")

# -------- Config básica --------
UPLOAD_FOLDER = 'static/modelos_ra'
ALLOWED_EXTENSIONS = {'glb', 'gltf', 'fbx', 'obj'}

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-local')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -------- Seguridad --------
bcrypt = Bcrypt(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# -------- Función de envío de correo (smtplib) --------
# Usaremos SMTP SSL (puerto 465). Usa variables de entorno MAIL_USER y MAIL_PASS.
MAIL_USER = os.environ.get('MAIL_USER')  # tu correo
MAIL_PASS = os.environ.get('MAIL_PASS')  # app password de Google o contraseña SMTP

def enviar_email(destino: str, asunto: str, html_mensaje: str) -> bool:
    """
    Envía correo usando SMTP SSL. Devuelve True si se envió correctamente.
    """
    remitente = MAIL_USER
    if not remitente or not MAIL_PASS:
        print("⚠️ Mail no configurado: configura MAIL_USER y MAIL_PASS como variables de entorno.")
        return False

    msg = MIMEText(html_mensaje, 'html', 'utf-8')
    msg['Subject'] = asunto
    msg['From'] = remitente
    msg['To'] = destino

    try:
        # conectar con SMTP SSL (Gmail)
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(remitente, MAIL_PASS)
            server.sendmail(remitente, [destino], msg.as_string())
        print(f"✅ Correo enviado a {destino}")
        return True
    except Exception as e:
        print(f"❌ Error enviando correo a {destino}: {e}")
        return False

# -------- Helpers --------
def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(f):
    @wraps(f)
    def _wrap(*args, **kwargs):
        if not session.get('usuario'):
            flash('Debes iniciar sesión.', 'warning')
            return redirect(url_for('login'))
        if session.get('rol') != 'admin':
            flash('No tienes permisos para acceder.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return _wrap

# ---- Utilidades de contraseñas ----
def _looks_like_bcrypt(s: str) -> bool:
    return isinstance(s, str) and s.startswith("$2")

def verify_password(plain: str, stored: str) -> bool:
    """Valida contra hash bcrypt si corresponde. Si es texto plano, compara directo (legacy)."""
    if not stored:
        return False
    if _looks_like_bcrypt(stored):
        try:
            return bcrypt.check_password_hash(stored, plain)
        except Exception:
            return False
    # compatibilidad con usuarios antiguos en texto plano
    return stored == plain

# -------- Archivos JSON locales --------
PRODUCTOS_JSON = 'productos.json'
USUARIOS_JSON = 'usuarios.json'

# -------- Funciones de normalización --------
def _normalize_product(p, idx):
    prod = dict(p) if isinstance(p, dict) else {}
    prod['id'] = str(prod.get('id', str(idx + 1)))
    prod.setdefault('nombre', 'Producto')
    prod.setdefault('descripcion', '')
    try:
        prod['precio'] = float(prod.get('precio', 0))
    except Exception:
        prod['precio'] = 0.0
    prod.setdefault('imagen', '')
    prod.setdefault('archivo_ra', '')
    return prod

def _normalize_user(u):
    d = dict(u) if isinstance(u, dict) else {}
    d.setdefault('nombre', '')
    d.setdefault('correo', '')
    if 'password' in d and 'clave' not in d:
        d['clave'] = d['password']
    d.setdefault('clave', '')
    d.setdefault('rol', d.get('rol', 'user') or 'user')
    return d

# -------- Utilidades de sesión en templates --------
@app.context_processor
def inject_cart_totals():
    carrito = session.get('carrito', [])
    total_items = sum(int(i.get('cantidad', 1)) for i in carrito)
    return dict(carrito_cant=total_items, carrito_dist=len(carrito))

# -------- Cargar/guardar productos --------
def _leer_local_productos():
    if os.path.exists(PRODUCTOS_JSON):
        try:
            with open(PRODUCTOS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [_normalize_product(p, i) for i, p in enumerate(data)]
        except Exception as e:
            print(f"⚠️  Error leyendo {PRODUCTOS_JSON}: {e}")
    return []

def cargar_productos():
    """Mezcla productos de Firebase (si hay) + locales."""
    cloud = []
    try:
        if db:
            docs = list(db.collection('productos').stream())
            for i, d in enumerate(docs):
                prod = d.to_dict() or {}
                prod['id'] = str(prod.get('id', d.id))
                cloud.append(_normalize_product(prod, i))
    except Exception as e:
        print(f"⚠️  Error leyendo productos de Firebase: {e}")

    local = _leer_local_productos()
    merged = {p['id']: p for p in cloud}
    for p in local:
        if p['id'] not in merged:
            merged[p['id']] = p

    resultado = cloud + [p for pid, p in merged.items() if all(pid != c['id'] for c in cloud)]
    return resultado

def guardar_productos(productos):
    try:
        with open(PRODUCTOS_JSON, 'w', encoding='utf-8') as f:
            json.dump(productos, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error guardando {PRODUCTOS_JSON}: {e}")
        return False

# -------- Cargar/guardar usuarios --------
def cargar_usuarios():
    try:
        if db:
            docs = db.collection('usuarios').stream()
            users = [_normalize_user(d.to_dict()) for d in docs]
            if users:
                return users
    except Exception as e:
        print(f"⚠️  Error leyendo usuarios de Firebase: {e}")

    if os.path.exists(USUARIOS_JSON):
        try:
            with open(USUARIOS_JSON, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [_normalize_user(u) for u in data]
        except Exception as e:
            print(f"⚠️  Error leyendo {USUARIOS_JSON}: {e}")
    return []

def guardar_usuario_local(nuevo):
    usuarios = cargar_usuarios()
    usuarios.append(_normalize_user(nuevo))
    try:
        with open(USUARIOS_JSON, 'w', encoding='utf-8') as f:
            json.dump(usuarios, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"❌ Error guardando {USUARIOS_JSON}: {e}")
        return False

# -------- Rutas --------
@app.route('/')
def index():
    productos = cargar_productos()
    productos = [_normalize_product(p, i) for i, p in enumerate(productos)]
    return render_template('index.html', productos=productos)

@app.route('/ver_modelo/<nombre_archivo>')
def ver_modelo(nombre_archivo):
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
    if not os.path.exists(ruta):
        abort(404)
    return render_template('visor_modelo.html', nombre_archivo=nombre_archivo)

# -------- Auth --------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo', '').strip().lower()
        clave = request.form.get('clave', '')
        if not correo or not clave:
            flash('Completa correo y contraseña.', 'warning')
            return redirect(url_for('login'))

        ok, rol, nombre = False, 'user', ''
        try:
            # --- Firebase ---
            if db:
                doc_ref = db.collection('usuarios').document(correo)
                doc = doc_ref.get()
                if doc.exists:
                    u = _normalize_user(doc.to_dict())
                    stored = u.get('clave', '')
                    if verify_password(clave, stored):
                        ok, rol, nombre = True, u.get('rol', 'user'), u.get('nombre', correo)
                        # Auto-upgrade a hash si estaba en texto plano
                        if not _looks_like_bcrypt(stored):
                            try:
                                hashed = bcrypt.generate_password_hash(clave).decode('utf-8')
                                doc_ref.update({'clave': hashed})
                            except Exception as _e:
                                print(f"⚠️ No se pudo auto-encriptar en Firebase: {_e}")
        except Exception as e:
            print(f"⚠️  Error Firebase login: {e}")

        # --- Local JSON como fallback ---
        if not ok:
            users = cargar_usuarios()
            for u in users:
                if u.get('correo', '').lower() == correo:
                    stored = u.get('clave', '')
                    if verify_password(clave, stored):
                        ok, rol, nombre = True, u.get('rol', 'user'), u.get('nombre', correo)
                        # Auto-upgrade local si estaba en texto plano
                        if not _looks_like_bcrypt(stored):
                            try:
                                for uu in users:
                                    if uu.get('correo', '').lower() == correo:
                                        uu['clave'] = bcrypt.generate_password_hash(clave).decode('utf-8')
                                        break
                                with open(USUARIOS_JSON, 'w', encoding='utf-8') as f:
                                    json.dump(users, f, ensure_ascii=False, indent=2)
                            except Exception as _e:
                                print(f"⚠️ No se pudo auto-encriptar localmente: {_e}")
                        break

        if ok:
            session['usuario'] = nombre
            session['rol'] = rol
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('index'))
        else:
            flash('Credenciales incorrectas.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('rol', None)
    session.pop('carrito', None)
    flash('Sesión cerrada.', 'info')
    return redirect(url_for('index'))

@app.route('/registro', methods=['GET','POST'])
def registro_usuario():
    if request.method=='POST':
        nombre = request.form.get('nombre','').strip()
        correo = request.form.get('correo','').strip().lower()
        clave = request.form.get('clave','')
        if not (nombre and correo and clave):
            flash('Todos los campos son obligatorios.', 'warning')
            return redirect(url_for('registro_usuario'))

        existentes = cargar_usuarios()
        for u in existentes:
            if u.get('correo','').lower()==correo:
                flash('El correo ya está registrado.', 'warning')
                return redirect(url_for('registro_usuario'))

        # Encriptar contraseña antes de guardar
        hashed = bcrypt.generate_password_hash(clave).decode('utf-8')

        creado = False
        try:
            if db:
                db.collection('usuarios').document(correo).set({
                    'nombre': nombre,
                    'correo': correo,
                    'clave': hashed,  # ahora guardamos hash
                    'rol': 'user'
                })
                creado = True
        except Exception as e:
            print(f"⚠️  Error registrando en Firebase: {e}")

        if not creado:
            creado = guardar_usuario_local({'nombre': nombre, 'correo': correo, 'clave': hashed, 'rol': 'user'})

        if creado:
            flash('Usuario registrado correctamente. Inicia sesión.', 'success')
            return redirect(url_for('login'))
        else:
            flash('No se pudo registrar el usuario.', 'danger')
            return redirect(url_for('registro_usuario'))
    return render_template('registro.html')

# -------- Carrito --------
@app.route('/agregar_al_carrito/<id_producto>')
def agregar_al_carrito(id_producto):
    if not session.get('usuario'):
        flash('Inicia sesión para usar el carrito.', 'warning')
        return redirect(url_for('login'))

    productos = cargar_productos()
    prod = next((p for p in productos if str(p.get('id',''))==str(id_producto)), None)
    if not prod:
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('index'))

    carrito = session.get('carrito', [])
    found = False
    for item in carrito:
        if str(item['id']) == str(prod['id']):
            item['cantidad'] = int(item.get('cantidad',1)) + 1
            found = True
            break
    if not found:
        prod_copy = dict(prod)
        prod_copy['cantidad'] = 1
        carrito.append(prod_copy)

    session['carrito'] = carrito
    session.modified = True
    flash('Producto agregado al carrito.', 'success')
    return redirect(url_for('index'))

@app.route('/carrito/aumentar/<id_producto>')
def carrito_aumentar(id_producto):
    carrito = session.get('carrito', [])
    for item in carrito:
        if str(item['id']) == str(id_producto):
            item['cantidad'] = int(item.get('cantidad',1)) + 1
            break
    session['carrito'] = carrito
    session.modified = True
    return redirect(url_for('mostrar_carrito'))

@app.route('/carrito/disminuir/<id_producto>')
def carrito_disminuir(id_producto):
    carrito = session.get('carrito', [])
    for item in carrito:
        if str(item['id']) == str(id_producto):
            item['cantidad'] = int(item.get('cantidad',1)) - 1
            if item['cantidad'] <= 0:
                carrito.remove(item)
            break
    session['carrito'] = carrito
    session.modified = True
    return redirect(url_for('mostrar_carrito'))

@app.route('/carrito')
def mostrar_carrito():
    if not session.get('usuario'):
        flash('Inicia sesión para ver el carrito.', 'warning')
        return redirect(url_for('login'))
    carrito = session.get('carrito', [])
    total = sum(float(p.get('precio',0))*int(p.get('cantidad',1)) for p in carrito)
    return render_template('carrito.html', carrito=carrito, total=total)

@app.route('/carrito/eliminar/<id_producto>', methods=['POST'])
def eliminar_del_carrito(id_producto):
    carrito = session.get('carrito', [])
    carrito = [item for item in carrito if str(item['id']) != str(id_producto)]
    session['carrito'] = carrito
    session.modified = True
    flash('Producto eliminado.', 'info')
    return redirect(url_for('mostrar_carrito'))

@app.route('/carrito/vaciar', methods=['POST'])
def vaciar_carrito():
    session['carrito'] = []
    session.modified = True
    flash('Carrito vaciado.', 'info')
    return redirect(url_for('mostrar_carrito'))

@app.route('/finalizar_compra')
def finalizar_compra():
    if not session.get('usuario'):
        flash('Inicia sesión para finalizar la compra.', 'warning')
        return redirect(url_for('login'))

    carrito = session.get('carrito', [])
    if not carrito:
        flash('El carrito está vacío.', 'info')
        return redirect(url_for('index'))

    # Aquí podrías enviar los datos a Firebase, email o generar PDF
    session['carrito'] = []  # Vaciar carrito al finalizar
    flash('Compra finalizada correctamente. Gracias por tu compra!', 'success')
    return redirect(url_for('index'))

# -------- Admin --------
@app.route('/admin')
@admin_required
def admin():
    productos = cargar_productos()
    return render_template('admin.html', productos=productos)

@app.route('/admin/nuevo', methods=['GET','POST'])
@admin_required
def nuevo_producto():
    if request.method=='POST':
        nombre = request.form.get('nombre','').strip()
        descripcion = request.form.get('descripcion','').strip()
        precio = request.form.get('precio','0').strip()
        imagen = request.form.get('imagen','').strip()
        archivo_ra = request.files.get('archivo_ra')

        if not (nombre and descripcion and precio and imagen):
            flash('Faltan datos del formulario.', 'warning')
            return redirect(url_for('nuevo_producto'))

        try:
            precio = float(precio)
        except:
            flash('Precio inválido.', 'danger')
            return redirect(url_for('nuevo_producto'))

        nombre_archivo_ra = ''
        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            archivo_ra.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra))

        productos = cargar_productos()

        new_id = str(uuid.uuid4())
        nuevo = {
            'id': new_id,
            'nombre': nombre,
            'descripcion': descripcion,
            'precio': precio,
            'imagen': imagen,
            'archivo_ra': nombre_archivo_ra
        }

        # Guardar local (offline)
        productos.append(nuevo)
        ok_local = guardar_productos(productos)

        # Guardar en Firestore si existe
        ok_cloud = True
        if db:
            try:
                db.collection('productos').document(new_id).set(nuevo)
            except Exception as e:
                ok_cloud = False
                print(f"⚠️  No se pudo guardar en Firebase: {e}")

        if ok_local and ok_cloud:
            flash('Producto agregado.', 'success')
            return redirect(url_for('admin'))

        if ok_local and not ok_cloud:
            flash('Producto guardado localmente. (Sincronización con Firebase falló)', 'warning')
            return redirect(url_for('admin'))

        flash('No se pudo guardar el producto.', 'danger')
        return redirect(url_for('nuevo_producto'))
    return render_template('nuevo_producto.html')

@app.route('/admin/editar/<int:indice>', methods=['GET','POST'])
@admin_required
def editar_producto(indice):
    productos = cargar_productos()
    if not (0 <= indice < len(productos)):
        flash('Producto no encontrado.', 'danger')
        return redirect(url_for('admin'))

    if request.method=='POST':
        nombre = request.form.get('nombre','').strip()
        descripcion = request.form.get('descripcion','').strip()
        precio = request.form.get('precio','0').strip()
        imagen = request.form.get('imagen','').strip()
        archivo_ra = request.files.get('archivo_ra')

        try:
            precio = float(precio)
        except:
            flash('Precio inválido.', 'danger')
            return redirect(url_for('editar_producto', indice=indice))

        productos[indice].update({
            'nombre': nombre,
            'descripcion': descripcion,
            'precio': precio,
            'imagen': imagen
        })
        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            archivo_ra.save(os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra))
            productos[indice]['archivo_ra'] = nombre_archivo_ra

        ok_local = guardar_productos(productos)

        # Sincronizar con Firebase
        ok_cloud = True
        if db:
            try:
                pid = str(productos[indice]['id'])
                db.collection('productos').document(pid).set(productos[indice], merge=True)
            except Exception as e:
                ok_cloud = False
                print(f"⚠️  No se pudo actualizar en Firebase: {e}")

        if ok_local and ok_cloud:
            flash('Producto actualizado.', 'success')
            return redirect(url_for('admin'))
        if ok_local and not ok_cloud:
            flash('Actualizado localmente (Firebase falló).', 'warning')
            return redirect(url_for('admin'))

        flash('No se pudo guardar.', 'danger')
        return redirect(url_for('editar_producto', indice=indice))
    return render_template('editar_producto.html', producto=productos[indice], indice=indice)

@app.route('/admin/eliminar/<int:indice>', methods=['POST'])
@admin_required
def eliminar_producto(indice):
    productos = cargar_productos()
    if 0 <= indice < len(productos):
        pid = str(productos[indice]['id'])
        productos.pop(indice)
        ok_local = guardar_productos(productos)

        ok_cloud = True
        if db:
            try:
                db.collection('productos').document(pid).delete()
            except Exception as e:
                ok_cloud = False
                print(f"⚠️  No se pudo eliminar en Firebase: {e}")

        if ok_local and ok_cloud:
            flash('Producto eliminado.', 'success')
        elif ok_local and not ok_cloud:
            flash('Eliminado localmente (Firebase falló).', 'warning')
        else:
            flash('No se pudo guardar.', 'danger')
    return redirect(url_for('admin'))
@app.route('/admin/nuevo_admin', methods=['GET', 'POST'])
@admin_required  # Solo un admin existente puede crear otro
def nuevo_admin():
    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        correo = request.form.get('correo', '').strip().lower()
        clave = request.form.get('clave', '')

        if not (nombre and correo and clave):
            flash('Todos los campos son obligatorios.', 'warning')
            return redirect(url_for('nuevo_admin'))

        # Verificar si ya existe
        usuarios = cargar_usuarios()
        for u in usuarios:
            if u.get('correo','').lower() == correo:
                flash('El correo ya está registrado.', 'warning')
                return redirect(url_for('nuevo_admin'))

        # Encriptar contraseña
        hashed = bcrypt.generate_password_hash(clave).decode('utf-8')

        # Crear usuario admin
        nuevo = {
            'nombre': nombre,
            'correo': correo,
            'clave': hashed,
            'rol': 'admin'
        }

        # Guardar en Firebase si existe
        ok_cloud = True
        try:
            if db:
                db.collection('usuarios').document(correo).set(nuevo)
        except Exception as e:
            ok_cloud = False
            print(f"⚠️ No se pudo guardar en Firebase: {e}")

        # Guardar local
        ok_local = guardar_usuario_local(nuevo)

        if ok_local and ok_cloud:
            flash('Administrador creado correctamente.', 'success')
        elif ok_local and not ok_cloud:
            flash('Administrador creado localmente (Firebase falló).', 'warning')
        else:
            flash('No se pudo crear el administrador.', 'danger')

        return redirect(url_for('admin'))

    return render_template('nuevo_admin.html')


# -------- Recuperación y reseteo de contraseña (envío real) --------
@app.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "POST":
        correo = request.form["correo"].strip().lower()
        try:
            # Verificamos si el correo existe (Firebase o local)
            usuarios = cargar_usuarios()
            user_exists = any(u.get("correo") == correo for u in usuarios)
            if db:
                try:
                    doc = db.collection("usuarios").document(correo).get()
                    user_exists = user_exists or doc.exists
                except Exception as e:
                    print(f"⚠️ Error comprobando usuario en Firebase: {e}")

            if not user_exists:
                flash("El correo no está registrado.", "warning")
                return redirect(url_for("recuperar"))

            # Generar token válido por 1 hora
            token = serializer.dumps(correo, salt="recuperar-clave")
            reset_url = url_for("reset_password", token=token, _external=True)

            # Construir mensaje HTML
            html_mensaje = f"""
                <p>Hola,</p>
                <p>Haz clic en el siguiente enlace para restablecer tu contraseña (válido por 1 hora):</p>
                <p><a href="{reset_url}">Restablecer contraseña</a></p>
                <p>Si no solicitaste este cambio, ignora este correo.</p>
            """

            # Enviar correo real
            sent = enviar_email(correo, "Recuperación de contraseña - Disfaluvid", html_mensaje)
            if sent:
                flash("Se ha enviado un enlace de recuperación a tu correo.", "success")
            else:
                flash("No se pudo enviar el enlace. Verifica la configuración de tu correo.", "danger")

        except Exception as e:
            print(f"⚠️ Error generando token de recuperación: {e}")
            flash("Error: no se pudo enviar el enlace. Intenta de nuevo.", "danger")
        return redirect(url_for("login"))

    return render_template("recuperar.html")

@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        correo = serializer.loads(token, salt="recuperar-clave", max_age=3600)  # 1 hora
    except SignatureExpired:
        flash("El enlace de recuperación ha caducado.", "danger")
        return redirect(url_for("recuperar"))
    except BadSignature:
        flash("El enlace de recuperación es inválido.", "danger")
        return redirect(url_for("recuperar"))

    if request.method == "POST":
        nueva_password = request.form["password"]
        confirmar_password = request.form["confirm_password"]

        if not nueva_password or not confirmar_password:
            flash("Completa ambos campos.", "warning")
            return redirect(request.url)

        if nueva_password != confirmar_password:
            flash("Las contraseñas no coinciden.", "danger")
            return redirect(request.url)

        hashed = bcrypt.generate_password_hash(nueva_password).decode("utf-8")

        try:
            if db:
                doc_ref = db.collection("usuarios").document(correo)
                if doc_ref.get().exists:
                    doc_ref.update({"clave": hashed})
                else:
                    flash("El usuario no existe.", "danger")
                    return redirect(url_for("recuperar"))
            else:
                usuarios = cargar_usuarios()
                found = False
                for u in usuarios:
                    if u.get("correo") == correo:
                        u["clave"] = hashed
                        found = True
                        break
                if not found:
                    flash("El usuario no existe.", "danger")
                    return redirect(url_for("recuperar"))
                with open(USUARIOS_JSON, "w", encoding="utf-8") as f:
                    json.dump(usuarios, f, ensure_ascii=False, indent=2)

            flash("Tu contraseña ha sido restablecida con éxito. Ahora puedes iniciar sesión.", "success")
            return redirect(url_for("login"))

        except Exception as e:
            print(f"❌ Error actualizando contraseña: {e}")
            flash("No se pudo actualizar la contraseña. Intenta nuevamente.", "danger")
            return redirect(request.url)

    return render_template("reset_password.html", token=token)

# -------- Run --------
if __name__=='__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)

