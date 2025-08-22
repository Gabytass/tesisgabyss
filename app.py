import os
import json
from flask import Flask, request, redirect, url_for, render_template, abort, session, flash
from werkzeug.utils import secure_filename
from functools import wraps

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# ✅ INICIALIZACIÓN CORREGIDA DE FIREBASE
if not firebase_admin._apps:
    firebase_config = os.environ.get('FIREBASE_CONFIG')
    if firebase_config:
        try:
            # Para Heroku: el JSON viene como string, necesitamos convertirlo a dict
            if isinstance(firebase_config, str):
                cred_dict = json.loads(firebase_config)
            else:
                cred_dict = firebase_config
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            print("✅ Firebase inicializado desde variable de entorno")
        except Exception as e:
            print(f"❌ Error inicializando Firebase desde variable: {e}")
    else:
        print("⚠️  FIREBASE_CONFIG no encontrada - Modo sin Firebase")
        # Crear un cliente dummy para evitar errores
        db = None

# Solo crear db si Firebase se inicializó correctamente
try:
    db = firestore.client()
    print("✅ Cliente Firestore inicializado")
except:
    print("❌ No se pudo inicializar Firestore")
    db = None

# Configuración
UPLOAD_FOLDER = 'static/modelos_ra'
ALLOWED_EXTENSIONS = {'glb', 'gltf', 'fbx', 'obj'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.environ.get('SECRET_KEY', 'GabyssR')  # ✅ Mejor usar variable de entorno

# Decorador para rutas solo de admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        if session.get('rol') != 'admin':
            flash('No tienes permisos para acceder a esta página.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Validar archivos permitidos
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Leer productos desde JSON
def cargar_productos():
    try:
        if os.path.exists('productos.json'):
            with open('productos.json', 'r', encoding='utf-8') as archivo:
                return json.load(archivo)
        return []
    except:
        return []

# Guardar productos en JSON
def guardar_productos(productos):
    try:
        with open('productos.json', 'w', encoding='utf-8') as archivo:
            json.dump(productos, archivo, indent=2, ensure_ascii=False)
        return True
    except:
        return False

# ----------------- RUTAS -----------------

# Ruta principal: catálogo
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    productos = cargar_productos()
    return render_template('index.html', productos=productos)

# Login con Firebase - ✅ CORREGIDO para modo sin Firebase
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        clave = request.form.get('clave')

        if not correo or not clave:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('login'))

        # ✅ MODO EMERGENCIA: Si Firebase no funciona, usa usuario hardcodeado
        if db is None:
            if correo == 'admin@disfaluvid.com' and clave == 'admin123':
                session['usuario'] = 'Administrador'
                session['rol'] = 'admin'
                flash('Modo emergencia - Inicio de sesión exitoso', 'success')
                return redirect(url_for('index'))
            else:
                flash('Credenciales incorrectas (Modo emergencia)', 'danger')
                return redirect(url_for('login'))

        # Modo normal con Firebase
        try:
            doc_ref = db.collection('usuarios').document(correo)
            usuario_doc = doc_ref.get()
            if usuario_doc.exists:
                usuario_data = usuario_doc.to_dict()
                if usuario_data['clave'] == clave:
                    session['usuario'] = usuario_data['nombre']
                    session['rol'] = usuario_data.get('rol', 'user')
                    flash('Inicio de sesión exitoso', 'success')
                    return redirect(url_for('index'))
            flash('Credenciales incorrectas', 'danger')
        except Exception as e:
            flash(f'Error de conexión: {str(e)}', 'danger')
    
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('rol', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# Registro de usuario - ✅ MANTENIDO Y MEJORADO
@app.route('/registro', methods=['GET', 'POST'])
def registro_usuario():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        correo = request.form.get('correo')
        clave = request.form.get('clave')
        rol = request.form.get('rol', 'user')

        if not nombre or not correo or not clave:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('registro_usuario'))

        # ✅ Verificar si Firebase está disponible
        if db is None:
            flash('Error: Servicio de registro no disponible temporalmente', 'danger')
            return redirect(url_for('registro_usuario'))

        try:
            doc_ref = db.collection('usuarios').document(correo)
            if doc_ref.get().exists:
                flash('El correo ya está registrado.', 'warning')
                return redirect(url_for('registro_usuario'))

            doc_ref.set({
                'nombre': nombre,
                'correo': correo,
                'clave': clave,
                'rol': rol
            })
            flash('Usuario registrado correctamente.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash(f'Error al registrar usuario: {str(e)}', 'danger')
            return redirect(url_for('registro_usuario'))

    return render_template('registro.html')

# ----------------- ADMIN -----------------

@app.route('/admin')
@admin_required
def admin():
    productos = cargar_productos()
    return render_template('admin.html', productos=productos)

@app.route('/admin/nuevo', methods=['GET', 'POST'])
@admin_required
def nuevo_producto():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        archivo_ra = request.files.get('archivo_ra')

        if not nombre or not precio or not imagen or not descripcion:
            flash('Faltan datos del formulario', 'danger')
            return redirect(url_for('nuevo_producto'))

        try:
            precio = float(precio)
        except ValueError:
            flash('Precio inválido', 'danger')
            return redirect(url_for('nuevo_producto'))

        nombre_archivo_ra = ''
        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra)
            try:
                archivo_ra.save(ruta_archivo)
            except:
                flash('Error al guardar archivo', 'danger')
                return redirect(url_for('nuevo_producto'))

        nuevo_producto = {
            'nombre': nombre,
            'descripcion': descripcion,
            'precio': precio,
            'imagen': imagen,
            'archivo_ra': nombre_archivo_ra
        }

        productos = cargar_productos()
        productos.append(nuevo_producto)
        if guardar_productos(productos):
            flash('Producto agregado correctamente', 'success')
        else:
            flash('Error al guardar producto', 'danger')

        return redirect(url_for('admin'))

    return render_template('nuevo_producto.html')

@app.route('/admin/editar/<int:indice>', methods=['GET', 'POST'])
@admin_required
def editar_producto(indice):
    productos = cargar_productos()
    if indice < 0 or indice >= len(productos):
        flash('Producto no encontrado', 'danger')
        return redirect(url_for('admin'))

    producto = productos[indice]

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        archivo_ra = request.files.get('archivo_ra')

        if not nombre or not precio or not imagen or not descripcion:
            flash('Faltan datos del formulario', 'danger')
            return redirect(url_for('editar_producto', indice=indice))

        try:
            precio = float(precio)
        except ValueError:
            flash('Precio inválido', 'danger')
            return redirect(url_for('editar_producto', indice=indice))

        producto['nombre'] = nombre
        producto['descripcion'] = descripcion
        producto['precio'] = precio
        producto['imagen'] = imagen

        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra)
            try:
                archivo_ra.save(ruta_archivo)
                producto['archivo_ra'] = nombre_archivo_ra
            except:
                flash('Error al guardar archivo', 'danger')

        if guardar_productos(productos):
            flash('Producto actualizado correctamente', 'success')
        else:
            flash('Error al guardar cambios', 'danger')

        return redirect(url_for('admin'))

    return render_template('editar_producto.html', producto=producto, indice=indice)

@app.route('/admin/eliminar/<int:indice>', methods=['POST'])
@admin_required
def eliminar_producto(indice):
    productos = cargar_productos()
    if 0 <= indice < len(productos):
        del productos[indice]
        if guardar_productos(productos):
            flash('Producto eliminado correctamente', 'success')
        else:
            flash('Error al eliminar producto', 'danger')
    return redirect(url_for('admin'))

# ----------------- MODELOS 3D -----------------
@app.route('/ver_modelo/<nombre_archivo>')
def ver_modelo(nombre_archivo):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
    if not os.path.exists(ruta):
        abort(404)
    return render_template('visor_modelo.html', nombre_archivo=nombre_archivo)

# ----------------- CARRITO -----------------
@app.route('/agregar_al_carrito/<int:indice>')
def agregar_al_carrito(indice):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    productos = cargar_productos()
    if 0 <= indice < len(productos):
        carrito = session.get('carrito', [])
        carrito.append(productos[indice])
        session['carrito'] = carrito
        flash('Producto agregado al carrito', 'success')
    return redirect(url_for('index'))

@app.route('/carrito/eliminar/<int:indice>', methods=['POST'])
def eliminar_del_carrito(indice):
    if 'usuario' not in session:
        return redirect(url_for('login'))

    carrito = session.get('carrito', [])
    if 0 <= indice < len(carrito):
        carrito.pop(indice)
        session['carrito'] = carrito
        flash('Producto eliminado del carrito.', 'info')
    return redirect(url_for('mostrar_carrito'))

@app.route('/carrito')
def mostrar_carrito():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    carrito = []
    for item in session.get('carrito', []):
        if isinstance(item, dict):
            carrito.append(item)
        else:
            try:
                carrito.append(json.loads(item) if item else {})
            except (json.JSONDecodeError, TypeError):
                carrito.append({})

    total = sum(float(producto.get('precio', 0)) for producto in carrito if isinstance(producto, dict))

    return render_template('carrito.html', carrito=carrito, total=total)

@app.route('/carrito/vaciar', methods=['POST'])
def vaciar_carrito():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    session['carrito'] = []
    flash('Carrito vaciado correctamente.', 'info')
    return redirect(url_for('mostrar_carrito'))

# ----------------- INICIO APP -----------------
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)




