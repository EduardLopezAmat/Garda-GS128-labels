# init_db.py
import sqlite3
from werkzeug.security import generate_password_hash

# Conectar a la base de datos (se crea si no existe)
conn = sqlite3.connect("database.db")
c = conn.cursor()

# -----------------------
# Tabla de usuarios
# -----------------------
c.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0
)
''')

# -----------------------
# Tabla de historial de etiquetas
# -----------------------
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

# -----------------------
# Crear usuario admin inicial
# -----------------------
admin_username = "admin"
admin_password = "admin123"  # Cambiar a una contraseña segura
hashed_password = generate_password_hash(admin_password)

try:
    c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, 1)", 
              (admin_username, hashed_password))
    conn.commit()
    print(f"Usuario admin '{admin_username}' creado correctamente con contraseña '{admin_password}'")
except sqlite3.IntegrityError:
    print(f"Usuario admin '{admin_username}' ya existe")

conn.close()
print("Base de datos y tablas creadas correctamente.")
