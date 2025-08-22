import os
import json
from flask import Flask, request, redirect, url_for, render_template, abort, session, flash
from werkzeug.utils import secure_filename
from functools import wraps

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# Inicializar Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate("rojasgabriela-bffec-firebase-adminsdk-fbsvc-c0e6f8a181.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# Configuración
UPLOAD_FOLDER = 'static/modelos_ra'
ALLOWED_EXTENSIONS = {'glb', 'gltf', 'fbx', 'obj'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'GabyssR'

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
    if os.path.exists('productos.json'):
        with open('productos.json', 'r', encoding='utf-8') as archivo:
            return json.load(archivo)
    return []

# Guardar productos en JSON
def guardar_productos(productos):
    with open('productos.json', 'w', encoding='utf-8') as archivo:
        json.dump(productos, archivo, indent=2, ensure_ascii=False)

# ----------------- RUTAS -----------------

# Ruta principal: catálogo
@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    productos = cargar_productos()
    return render_template('index.html', productos=productos)

# Login con Firebase
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        clave = request.form.get('clave')

        if not correo or not clave:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('login'))

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
    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('rol', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

# Registro de usuario
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
            return "Faltan datos del formulario", 400

        try:
            precio = float(precio)
        except ValueError:
            return "Precio inválido", 400

        nombre_archivo_ra = ''
        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra)
            archivo_ra.save(ruta_archivo)

        nuevo_producto = {
            'nombre': nombre,
            'descripcion': descripcion,
            'precio': precio,
            'imagen': imagen,
            'archivo_ra': nombre_archivo_ra
        }

        productos = cargar_productos()
        productos.append(nuevo_producto)
        guardar_productos(productos)

        return redirect(url_for('admin'))

    return render_template('nuevo_producto.html')

@app.route('/admin/editar/<int:indice>', methods=['GET', 'POST'])
@admin_required
def editar_producto(indice):
    productos = cargar_productos()
    if indice < 0 or indice >= len(productos):
        return "Producto no encontrado", 404

    producto = productos[indice]

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        descripcion = request.form.get('descripcion')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        archivo_ra = request.files.get('archivo_ra')

        if not nombre or not precio or not imagen or not descripcion:
            return "Faltan datos del formulario", 400

        try:
            precio = float(precio)
        except ValueError:
            return "Precio inválido", 400

        producto['nombre'] = nombre
        producto['descripcion'] = descripcion
        producto['precio'] = precio
        producto['imagen'] = imagen

        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra)
            archivo_ra.save(ruta_archivo)
            producto['archivo_ra'] = nombre_archivo_ra

        guardar_productos(productos)
        return redirect(url_for('admin'))

    return render_template('editar_producto.html', producto=producto, indice=indice)

@app.route('/admin/eliminar/<int:indice>', methods=['POST'])
@admin_required
def eliminar_producto(indice):
    productos = cargar_productos()
    if 0 <= indice < len(productos):
        del productos[indice]
        guardar_productos(productos)
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
    return redirect(url_for('mostrar_carrito'))

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
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))




