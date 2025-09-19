from flask import Flask, render_template, request, redirect, url_for, session, send_file
from utils import (
    validate_gtin, validate_sscc, validate_date, generate_pdf, generate_zpl,
    validate_pedido, init_db, create_user, verify_login, save_etiquetas,
    get_user_etiquetas
)
from translations import translations
import io
import sqlite3

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Inicializar DB
init_db()

# ------------------- Rutas Login/Logout -------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = verify_login(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = user["is_admin"]
            return redirect(url_for("pedido"))
        else:
            error = "Usuario o contraseña incorrectos"

    lang = session.get("lang", "ES")  # por defecto español
    return render_template("login.html", translations=translations, lang=lang, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ------------------- Nuevo Nivel: Pedido GARDA -------------------
@app.route("/pedido", methods=["GET", "POST"])
def pedido():
    if "user_id" not in session:
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        inicio = request.form.get("pedido_inicio")
        fin = request.form.get("pedido_fin")
        pedido_full = f"{inicio}CP{fin}"
        if not validate_pedido(pedido_full):
            error = "Formato Nº PEDIDO GARDA inválido (xxxxCPxxxx)"
        else:
            session['pedido_garda'] = pedido_full
            return redirect(url_for("index"))  # siguiente nivel: selección unidad
    lang = session.get("lang", "ES")
    return render_template("pedido.html", translations=translations, lang=lang, error=error)

# ------------------- Index: Selección de unidad logística -------------------
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))
    if "pedido_garda" not in session:
        return redirect(url_for("pedido"))  # obligamos a pasar por nuevo nivel
    if request.method == "POST":
        session['tipo_unidad'] = request.form['tipo_unidad']
        return redirect(url_for("form_unidad"))
    lang = session.get('lang', 'ES')
    return render_template("index.html", translations=translations, lang=lang)

@app.route("/set_lang/<lang>")
def set_lang(lang):
    session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

# ------------------- Formulario de Caja/Pallet -------------------
@app.route("/form", methods=["GET", "POST"])
def form_unidad():
    if "user_id" not in session or "pedido_garda" not in session:
        return redirect(url_for("login"))
    tipo = session.get('tipo_unidad')
    lang = session.get('lang', 'ES')
    pedido = session.get('pedido_garda')

    if request.method == "POST":
        form_data = []
        if tipo == "caja":
            item = {
                "Nº PEDIDO GARDA": pedido,
                "GTIN": request.form["gtin"],
                "Lote": request.form["lote"],
                "Fecha caducidad": request.form["fecha"],
                "Cantidad": request.form["cantidad"],
                "Peso neto KG": f"{request.form.get('peso','')} KG" if request.form.get('peso') else "",
                "Descripción": request.form.get("descripcion", "")
            }
        else:
            item = {
                "Nº PEDIDO GARDA": pedido,
                "SSCC": request.form["sscc"],
                "GTIN": request.form["gtin"],
                "Lote": request.form["lote"],
                "Fecha caducidad": request.form["fecha"],
                "Cantidad de cajas": request.form["cantidad"],
                "Peso neto KG": f"{request.form.get('peso','')} KG" if request.form.get('peso') else "",
                "Descripción": request.form.get("descripcion", "")
            }
        form_data.append(item)
        session['form_data'] = form_data

        # Guardar en DB
        save_etiquetas(session["user_id"], form_data, tipo)
        return redirect(url_for("preview"))
    
    if tipo == "caja":
        return render_template("form_caja.html", translations=translations, lang=lang, pedido_garda=pedido)
    else:
        return render_template("form_pallet.html", translations=translations, lang=lang, pedido_garda=pedido)

# ------------------- Preview -------------------
@app.route("/preview")
def preview():
    if "user_id" not in session:
        return redirect(url_for("login"))
    form_data = session.get('form_data', [])
    lang = session.get('lang', 'ES')
    tipo = session.get('tipo_unidad')
    return render_template("preview.html", form_data=form_data, translations=translations, lang=lang, tipo=tipo)

# ------------------- Download -------------------
@app.route("/download/<file_type>")
def download(file_type):
    if "user_id" not in session:
        return redirect(url_for("login"))
    form_data = session.get('form_data', [])
    if file_type == "pdf":
        pdf = generate_pdf(form_data)
        return send_file(io.BytesIO(pdf), mimetype='application/pdf', as_attachment=True, download_name="etiquetas.pdf")
    elif file_type == "zpl":
        zpl = generate_zpl(form_data)
        return send_file(io.BytesIO(zpl.encode()), mimetype='text/plain', as_attachment=True, download_name="etiquetas.zpl")
    return redirect(url_for("preview"))

# ------------------- Historial -------------------
@app.route("/historial", methods=["GET", "POST"])
def historial():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user_id = session["user_id"]
    filtro = request.form.get("filtro", "")
    etiquetas = get_user_etiquetas(user_id, filtro)
    return render_template("historial.html", etiquetas=etiquetas, filtro=filtro)

# ------------------- Registro de usuario (solo admin) -------------------
@app.route("/register_user", methods=["GET", "POST"])
def register_user():
    if "user_id" not in session or not session.get("is_admin"):
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        is_admin = True if request.form.get("is_admin") == "on" else False
        success, error = create_user(username, password, is_admin)
        if success:
            return redirect(url_for("register_user"))
    return render_template("register_user.html", error=error)

if __name__ == "__main__":
    app.run(debug=True)
