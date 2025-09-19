import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import code128
import io

# -----------------------
# Inicializar Base de Datos
# -----------------------
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    # Tabla usuarios
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )
    ''')
    # Tabla etiquetas
    c.execute('''
        CREATE TABLE IF NOT EXISTS etiquetas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            pedido_garda TEXT NOT NULL,
            contenido TEXT NOT NULL,
            fecha TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

# -----------------------
# Gestión Usuarios
# -----------------------
def create_user(username, password, is_admin=False):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    hashed = generate_password_hash(password)
    try:
        c.execute(
            "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
            (username, hashed, int(is_admin))
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "El usuario ya existe"
    finally:
        conn.close()

def verify_login(username, password):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, username, password, is_admin FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    if row and check_password_hash(row[2], password):
        return {"id": row[0], "username": row[1], "is_admin": bool(row[3])}
    return None

# -----------------------
# Guardar y obtener etiquetas
# -----------------------
def save_etiquetas(user_id, form_data, tipo):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    for item in form_data:
        pedido = item.get("Nº PEDIDO GARDA")
        contenido = str(item)
        c.execute(
            "INSERT INTO etiquetas (user_id, tipo, pedido_garda, contenido, fecha) VALUES (?, ?, ?, ?, ?)",
            (user_id, tipo, pedido, contenido, fecha)
        )
    conn.commit()
    conn.close()

def get_user_etiquetas(user_id, filtro=""):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    if filtro:
        c.execute(
            "SELECT tipo, pedido_garda, contenido, fecha FROM etiquetas WHERE user_id = ? AND pedido_garda LIKE ? ORDER BY id DESC",
            (user_id, f"%{filtro}%")
        )
    else:
        c.execute(
            "SELECT tipo, pedido_garda, contenido, fecha FROM etiquetas WHERE user_id = ? ORDER BY id DESC",
            (user_id,)
        )
    rows = c.fetchall()
    conn.close()
    etiquetas = [{"tipo": r[0], "pedido_garda": r[1], "contenido": r[2], "fecha": r[3]} for r in rows]
    return etiquetas

# -----------------------
# Validaciones
# -----------------------
def validate_gtin(gtin):
    return gtin.isdigit() and len(gtin) == 14

def validate_sscc(sscc):
    return sscc.isdigit() and len(sscc) == 18

def validate_date(date_str):
    try:
        date_obj = datetime.strptime(date_str, "%d/%m/%Y")
        return date_obj >= datetime.today()
    except:
        return False

def validate_pedido(pedido):
    if not pedido or len(pedido) != 10:
        return False
    if pedido[4:6] != "CP":
        return False
    if not (pedido[:4].isdigit() and pedido[6:].isdigit()):
        return False
    return True

# -----------------------
# Generación AIS para códigos de barras
# -----------------------
def generate_ais(item, tipo):
    ais = ""
    if tipo == "caja":
        ais += f"(01){item['GTIN']}"
        ais += f"(10){item['Lote']}"
        ais += f"(17){datetime.strptime(item['Fecha caducidad'], '%d/%m/%Y').strftime('%y%m%d')}"
        ais += f"(37){item['Cantidad']}"
    elif tipo == "pallet":
        ais += f"(00){item['SSCC']}"
        ais += f"(01){item['GTIN']}"
        ais += f"(10){item['Lote']}"
        ais += f"(17){datetime.strptime(item['Fecha caducidad'], '%d/%m/%Y').strftime('%y%m%d')}"
        ais += f"(37){item['Cantidad de cajas']}"
    return ais

# -----------------------
# Generar PDF con código de barras (NO SE TOCA)
# -----------------------
def generate_pdf(form_data):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y_start = height - 50
    column_a_x = 50
    column_b_x = width/2
    for item in form_data:
        tipo = "caja" if "GTIN" in item and "SSCC" not in item else "pallet"
        y = y_start
        # Columna A
        pedido = item.get("Nº PEDIDO GARDA", "")
        if pedido:
            c.setFont("Helvetica-Bold", 16)
            c.drawString(column_a_x, y, f"Nº PEDIDO GARDA: {pedido}")
        y_b = y - 30
        c.setFont("Helvetica", 12)
        if tipo == "pallet":
            ais_sscc = f"(00){item['SSCC']}"
            barcode1 = code128.Code128(ais_sscc, barHeight=50, barWidth=1.0)
            x_center1 = column_b_x - barcode1.width/2
            barcode1.drawOn(c, x_center1, y_b - 50)
            y_b -= 55
            c.drawCentredString(column_b_x, y_b - 5, ais_sscc)
            y_b -= 26
            ais_gtin = f"(01){item['GTIN']}(10){item['Lote']}(17){datetime.strptime(item['Fecha caducidad'], '%d/%m/%Y').strftime('%y%m%d')}(37){item['Cantidad de cajas']}"
            barcode2 = code128.Code128(ais_gtin, barHeight=50, barWidth=1.0)
            x_center2 = column_b_x - barcode2.width/2
            barcode2.drawOn(c, x_center2, y_b - 50)
            y_b -= 55
            c.drawCentredString(column_b_x, y_b - 5, ais_gtin)
            y_b -= 26
            for key in ["Cantidad de cajas", "Descripción", "Fecha caducidad", "GTIN", "Lote", "Peso neto KG"]:
                val = item.get(key,"")
                if val:
                    c.drawCentredString(column_b_x, y_b-1, f"{key}: {val}")
                    y_b -= 18
        else:
            ais = generate_ais(item, tipo)
            barcode = code128.Code128(ais, barHeight=50, barWidth=1.0)
            x_center = column_b_x - barcode.width/2
            barcode.drawOn(c, x_center, y_b - 50)
            y_b -= 55
            c.drawCentredString(column_b_x, y_b - 5, ais)
            y_b -= 26
            for key in ["Cantidad", "Descripción", "Fecha caducidad", "GTIN", "Lote", "Peso neto KG"]:
                val = item.get(key,"")
                if val:
                    c.drawCentredString(column_b_x, y_b-1, f"{key}: {val}")
                    y_b -= 18
        y_start = y_b - 30
        if y_start < 100:
            c.showPage()
            y_start = height - 50
            c.setFont("Helvetica-Bold", 14)
    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# -----------------------
# Generar ZPL con plantilla fija (nuevo formato)
# -----------------------
def generate_zpl(form_data):
    zpl_full = ""
    max_width = 800  # ancho máximo de la etiqueta en pixels
    for item in form_data:
        tipo = "caja" if "GTIN" in item and "SSCC" not in item else "pallet"
        pedido = item.get("Nº PEDIDO GARDA", "")
        gtin = item.get("GTIN", "")
        lote = item.get("Lote", "")
        fecha = item.get("Fecha caducidad", "")
        cantidad = item.get("Cantidad","") if tipo=="caja" else item.get("Cantidad de cajas","")
        sscc = item.get("SSCC","") if tipo=="pallet" else ""
        descripcion = item.get("Descripción","")
        peso = item.get("Peso neto KG","")

        fecha_ais = datetime.strptime(fecha, "%d/%m/%Y").strftime("%y%m%d") if fecha else ""
        ais = generate_ais(item, tipo)

        # Ajuste dinámico de barWidth
        # Factor aproximado: cada carácter ≈ 11 px con magnificación 2
        estimated_width = len(ais) * 11 * 2
        bar_width = int(max_width / estimated_width * 2)
        if bar_width < 1:
            bar_width = 1

        # Posición inicial
        y_pos = 50
        contenido_zpl = ""
        contenido_zpl += f"^FO50,{y_pos}^A0N,40,40^FDNº PEDIDO GARDA: {pedido}^FS\n"
        y_pos += 50

        if tipo=="pallet" and sscc:
            contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDSSCC: {sscc}^FS\n"
            y_pos += 40
            contenido_zpl += f"^FO50,{y_pos}^BY{bar_width},2,120^BCN,120,Y,N,N^FD{sscc}^FS\n"
            y_pos += 120

        # Datos adicionales
        contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDGTIN: {gtin}^FS\n"
        y_pos += 40
        contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDLote: {lote}^FS\n"
        y_pos += 40
        contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDFecha caducidad: {fecha}^FS\n"
        y_pos += 40
        contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDCantidad: {cantidad}^FS\n"
        y_pos += 40
        if descripcion:
            contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDDescripción: {descripcion}^FS\n"
            y_pos += 40
        if peso:
            contenido_zpl += f"^FO50,{y_pos}^A0N,35,35^FDPeso neto: {peso}^FS\n"
            y_pos += 40

        # Barra AIS completa con barWidth dinámico
        contenido_zpl += f"^FO50,{y_pos}^BY{bar_width},2,120^BCN,120,Y,N,N^FD{ais}^FS\n"

        # Contenedor principal
        zpl_item = f"^XA\n^PW{max_width}\n^LL609\n^LH20,20\n^CI28\n^MNG\n^MMT\n^FT0,0^A0N,0,0\n"
        zpl_item += contenido_zpl
        zpl_item += "^XZ\n"

        zpl_full += zpl_item

    return zpl_full
