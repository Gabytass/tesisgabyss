import os
<<<<<<< HEAD
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
=======
from firebase_config import db  # Conexión Firestore ya configurada
from flask import Flask, request, redirect, url_for, render_template, abort, session, flash
from werkzeug.utils import secure_filename
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de

# Configuración
UPLOAD_FOLDER = 'static/modelos_ra'
ALLOWED_EXTENSIONS = {'glb', 'gltf', 'fbx', 'obj'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
<<<<<<< HEAD
app.secret_key = 'GabyssR'

# ----------------- FUNCIONES -----------------

def check_internet():
    """Verifica si Firebase responde"""
    try:
        db.collection("ping").get()
        return True
    except Exception:
        return False

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

@app.route('/')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    productos = []

    if check_internet():
        # Leer productos desde Firebase
        try:
            docs = db.collection("productos").stream()
            for doc in docs:
                productos.append(doc.to_dict())
            # Actualizar respaldo local
            guardar_productos(productos)
        except Exception as e:
            flash("Error al conectar con Firebase, mostrando respaldo local", "warning")
            productos = cargar_productos()
    else:
        # Si no hay internet → cargar local
        productos = cargar_productos()

    return render_template('index.html', productos=productos)

# ----------------- LOGIN / REGISTRO -----------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        clave = request.form.get('clave')

        if not correo or not clave:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('login'))

        if check_internet():
            doc_ref = db.collection('usuarios').document(correo)
            usuario_doc = doc_ref.get()
            if usuario_doc.exists:
                usuario_data = usuario_doc.to_dict()
                if usuario_data['clave'] == clave:
                    session['usuario'] = usuario_data['nombre']
                    session['rol'] = usuario_data.get('rol', 'user')
                    flash('Inicio de sesión exitoso', 'success')
                    return redirect(url_for('index'))
        flash('Credenciales incorrectas o sin conexión.', 'danger')
=======
app.secret_key = 'GabyssR'  # Cambiar en producción por clave segura

# Usuarios para login (ejemplo básico)
USUARIOS = {
    'admin': 'disfaluvid123',
}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def obtener_productos():
    productos = []
    docs = db.collection('productos').stream()
    for doc in docs:
        data = doc.to_dict()
        productos.append({
            'id': doc.id,
            'nombre': data.get('nombre'),
            'precio': data.get('precio'),
            'imagen': data.get('imagen'),
            'descripcion': data.get('descripcion', ''),
            'archivo_ra': data.get('archivo_ra', None)
        })
    return productos

def obtener_producto_por_id(producto_id):
    doc = db.collection('productos').document(producto_id).get()
    if doc.exists:
        producto = doc.to_dict()
        producto['id'] = doc.id
        return producto
    return None

def guardar_producto_firestore(producto, producto_id=None):
    if producto_id:
        db.collection('productos').document(producto_id).set(producto)
    else:
        db.collection('productos').add(producto)

def eliminar_producto_firestore(producto_id):
    db.collection('productos').document(producto_id).delete()

# Rutas públicas
@app.route('/')
def index():
    productos = obtener_productos()
    return render_template('index.html', productos=productos)

@app.route('/ver_modelo/<nombre_archivo>')
def ver_modelo(nombre_archivo):
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
    if not os.path.exists(ruta):
        abort(404)
    return render_template('visor_modelo.html', nombre_archivo=nombre_archivo)

# Carrito
@app.route('/agregar_al_carrito/<producto_id>')
def agregar_al_carrito(producto_id):
    if 'usuario' not in session:
        flash('Debe iniciar sesión para agregar productos al carrito.', 'warning')
        return redirect(url_for('login'))
    carrito = session.get('carrito', [])
    carrito.append(producto_id)
    session['carrito'] = carrito
    flash('Producto agregado al carrito.', 'success')
    return redirect(url_for('index'))

@app.route('/carrito')
def mostrar_carrito():
    if 'usuario' not in session:
        flash('Debe iniciar sesión para ver el carrito.', 'warning')
        return redirect(url_for('login'))
    carrito_ids = session.get('carrito', [])
    productos_carrito = [obtener_producto_por_id(pid) for pid in carrito_ids if obtener_producto_por_id(pid)]
    total = sum(p['precio'] for p in productos_carrito)
    return render_template('carrito.html', productos=productos_carrito, total=total)

@app.route('/eliminar_del_carrito/<int:indice>', methods=['POST'])
def eliminar_del_carrito(indice):
    if 'usuario' not in session:
        flash('Debe iniciar sesión.', 'warning')
        return redirect(url_for('login'))
    carrito = session.get('carrito', [])
    if 0 <= indice < len(carrito):
        carrito.pop(indice)
        session['carrito'] = carrito
        flash('Producto eliminado del carrito.', 'success')
    return redirect(url_for('mostrar_carrito'))

@app.route('/vaciar_carrito', methods=['POST'])
def vaciar_carrito():
    if 'usuario' not in session:
        flash('Debe iniciar sesión.', 'warning')
        return redirect(url_for('login'))
    session['carrito'] = []
    flash('Carrito vaciado.', 'success')
    return redirect(url_for('mostrar_carrito'))

# Login / Logout
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        clave = request.form.get('clave')
        if usuario in USUARIOS and USUARIOS[usuario] == clave:
            session['usuario'] = usuario
            flash('Inicio de sesión exitoso', 'success')
            return redirect(url_for('admin') if usuario == 'admin' else url_for('index'))
        else:
            flash('Credenciales incorrectas', 'danger')
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
<<<<<<< HEAD
    session.pop('rol', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('login'))

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

        if check_internet():
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
        else:
            flash("No hay internet, registro no disponible.", "danger")
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
=======
    session.pop('carrito', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('index'))

# Admin
def es_admin():
    return session.get('usuario') == 'admin'

@app.route('/admin')
def admin():
    if not es_admin():
        flash('Acceso denegado. Solo administrador.', 'danger')
        return redirect(url_for('login'))
    productos = obtener_productos()
    return render_template('admin.html', productos=productos)

@app.route('/admin/nuevo', methods=['GET', 'POST'])
def nuevo_producto():
    if not es_admin():
        flash('Acceso denegado. Solo administrador.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        descripcion = request.form.get('descripcion', '')
        archivo_ra = request.files.get('archivo_ra')

        if not nombre or not precio or not imagen:
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de
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
<<<<<<< HEAD
            'descripcion': descripcion,
            'precio': precio,
            'imagen': imagen,
            'archivo_ra': nombre_archivo_ra
        }

        productos = cargar_productos()
        productos.append(nuevo_producto)
        guardar_productos(productos)

        if check_internet():
            db.collection("productos").add(nuevo_producto)

=======
            'precio': precio,
            'imagen': imagen,
            'descripcion': descripcion,
            'archivo_ra': nombre_archivo_ra
        }

        guardar_producto_firestore(nuevo_producto)
        flash('Producto creado correctamente.', 'success')
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de
        return redirect(url_for('admin'))

    return render_template('nuevo_producto.html')

<<<<<<< HEAD
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
=======
@app.route('/admin/editar/<producto_id>', methods=['GET', 'POST'])
def editar_producto(producto_id):
    if not es_admin():
        flash('Acceso denegado. Solo administrador.', 'danger')
        return redirect(url_for('login'))

    producto = obtener_producto_por_id(producto_id)
    if not producto:
        return "Producto no encontrado", 404

    if request.method == 'POST':
        nombre = request.form.get('nombre')
        precio = request.form.get('precio')
        imagen = request.form.get('imagen')
        descripcion = request.form.get('descripcion', '')
        archivo_ra = request.files.get('archivo_ra')

        if not nombre or not precio or not imagen:
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de
            return "Faltan datos del formulario", 400

        try:
            precio = float(precio)
        except ValueError:
            return "Precio inválido", 400

        producto['nombre'] = nombre
<<<<<<< HEAD
        producto['descripcion'] = descripcion
        producto['precio'] = precio
        producto['imagen'] = imagen
=======
        producto['precio'] = precio
        producto['imagen'] = imagen
        producto['descripcion'] = descripcion
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de

        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra)
            archivo_ra.save(ruta_archivo)
            producto['archivo_ra'] = nombre_archivo_ra

<<<<<<< HEAD
        guardar_productos(productos)

        if check_internet():
            # Actualizar en Firebase: simplificado
            docs = db.collection("productos").where("nombre", "==", producto['nombre']).get()
            for doc in docs:
                db.collection("productos").document(doc.id).set(producto)

        return redirect(url_for('admin'))

    return render_template('editar_producto.html', producto=producto, indice=indice)

@app.route('/admin/eliminar/<int:indice>', methods=['POST'])
@admin_required
def eliminar_producto(indice):
    productos = cargar_productos()
    if 0 <= indice < len(productos):
        producto = productos.pop(indice)
        guardar_productos(productos)

        if check_internet():
            docs = db.collection("productos").where("nombre", "==", producto['nombre']).get()
            for doc in docs:
                db.collection("productos").document(doc.id).delete()

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

    carrito = session.get('carrito', [])
    total = sum(producto['precio'] for producto in carrito)
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
    app.run(debug=True)




=======
        guardar_producto_firestore(producto, producto_id)
        flash('Producto actualizado correctamente.', 'success')
        return redirect(url_for('admin'))

    return render_template('editar_producto.html', producto=producto, producto_id=producto_id)

@app.route('/admin/eliminar/<producto_id>', methods=['POST'])
def eliminar_producto(producto_id):
    if not es_admin():
        flash('Acceso denegado. Solo administrador.', 'danger')
        return redirect(url_for('login'))
    eliminar_producto_firestore(producto_id)
    flash('Producto eliminado.', 'success')
    return redirect(url_for('admin'))

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)  # Cambia a False o elimina en producción
>>>>>>> ebbb7897409d865a94a76559fb667705c74951de
