import os
import json
from flask import Flask, request, redirect, url_for, render_template, abort, session, flash
from werkzeug.utils import secure_filename
from functools import wraps

# ----------------- FIREBASE -----------------
from firebase_config import db  # Asegúrate que db esté correctamente configurado

# ----------------- CONFIGURACIÓN -----------------
UPLOAD_FOLDER = 'static/modelos_ra'
ALLOWED_EXTENSIONS = {'glb', 'gltf', 'fbx', 'obj'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'GabyssR'  # Cambiar por clave segura en producción

# ----------------- FUNCIONES -----------------
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

def es_admin():
    return session.get('usuario') == 'admin'

# ----------------- RUTAS PÚBLICAS -----------------
@app.route('/')
def index():
    productos = obtener_productos()
    return render_template('index.html', productos=productos)

@app.route('/ver_modelo/<nombre_archivo>')
def ver_modelo(nombre_archivo):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    ruta = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
    if not os.path.exists(ruta):
        abort(404)
    return render_template('visor_modelo.html', nombre_archivo=nombre_archivo)

# ----------------- CARRITO -----------------
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
    carrito = session.get('carrito', [])
    if 0 <= indice < len(carrito):
        carrito.pop(indice)
        session['carrito'] = carrito
        flash('Producto eliminado del carrito.', 'success')
    return redirect(url_for('mostrar_carrito'))

@app.route('/vaciar_carrito', methods=['POST'])
def vaciar_carrito():
    session['carrito'] = []
    flash('Carrito vaciado.', 'success')
    return redirect(url_for('mostrar_carrito'))

# ----------------- LOGIN / LOGOUT -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form.get('correo')
        clave = request.form.get('clave')

        if not correo or not clave:
            flash('Todos los campos son obligatorios.', 'danger')
            return redirect(url_for('login'))

        # Verificar usuario en Firebase
        doc_ref = db.collection('usuarios').document(correo)
        usuario_doc = doc_ref.get()
        if usuario_doc.exists:
            usuario_data = usuario_doc.to_dict()
            if usuario_data.get('clave') == clave:
                session['usuario'] = usuario_data.get('nombre')
                session['rol'] = usuario_data.get('rol', 'user')
                flash('Inicio de sesión exitoso', 'success')
                return redirect(url_for('admin') if usuario_data.get('rol') == 'admin' else url_for('index'))

        flash('Credenciales incorrectas.', 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('rol', None)
    session.pop('carrito', None)
    flash('Sesión cerrada', 'info')
    return redirect(url_for('index'))

# ----------------- ADMIN -----------------
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
            'precio': precio,
            'imagen': imagen,
            'descripcion': descripcion,
            'archivo_ra': nombre_archivo_ra
        }

        guardar_producto_firestore(nuevo_producto)
        flash('Producto creado correctamente.', 'success')
        return redirect(url_for('admin'))

    return render_template('nuevo_producto.html')

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
            return "Faltan datos del formulario", 400

        try:
            precio = float(precio)
        except ValueError:
            return "Precio inválido", 400

        producto['nombre'] = nombre
        producto['precio'] = precio
        producto['imagen'] = imagen
        producto['descripcion'] = descripcion

        if archivo_ra and allowed_file(archivo_ra.filename):
            nombre_archivo_ra = secure_filename(archivo_ra.filename)
            ruta_archivo = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo_ra)
            archivo_ra.save(ruta_archivo)
            producto['archivo_ra'] = nombre_archivo_ra

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

# ----------------- INICIO APP -----------------
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.run(debug=True)  # Cambiar a False en producción
