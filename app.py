import os
import json
import uuid
from functools import wraps
from flask import Flask, render_template, redirect, url_for, request, session, flash, abort
from werkzeug.utils import secure_filename

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
    """Mezcla productos de Firebase (si hay) + locales.
       Si un ID existe en Firebase se prioriza, y se agregan los locales que no estén."""
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

    # mantener orden estable: primero cloud, luego los locales que no estaban
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
            if db:
                doc = db.collection('usuarios').document(correo).get()
                if doc.exists:
                    u = _normalize_user(doc.to_dict())
                    if u.get('correo','').lower()==correo and u.get('clave')==clave:
                        ok, rol, nombre = True, u.get('rol','user'), u.get('nombre', correo)
        except Exception as e:
            print(f"⚠️  Error Firebase login: {e}")

        if not ok:
            for u in cargar_usuarios():
                if u.get('correo','').lower()==correo and u.get('clave')==clave:
                    ok, rol, nombre = True, u.get('rol','user'), u.get('nombre', correo)
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

        creado = False
        try:
            if db:
                db.collection('usuarios').document(correo).set({
                    'nombre': nombre,
                    'correo': correo,
                    'clave': clave,
                    'rol': 'user'
                })
                creado = True
        except Exception as e:
            print(f"⚠️  Error registrando en Firebase: {e}")

        if not creado:
            creado = guardar_usuario_local({'nombre':nombre,'correo':correo,'clave':clave,'rol':'user'})

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

# -------- Run --------
if __name__=='__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
