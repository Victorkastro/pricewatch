"""
Script para inicializar la base de datos en Render.com (o cualquier servidor remoto).
Ejecutar UNA SOLA VEZ después del primer despliegue.

Uso local:
  DATABASE_URL="postgresql://user:pass@host:5432/pricedb" python init_db.py

En Render:
  1. Ve a tu servicio backend → Shell
  2. Ejecuta: python init_db.py
"""
import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: Variable DATABASE_URL no encontrada.")
    print("Uso: DATABASE_URL='postgresql://...' python init_db.py")
    sys.exit(1)

# Render usa postgres:// pero SQLAlchemy necesita postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

# Leer el archivo SQL
script_dir = os.path.dirname(os.path.abspath(__file__))
sql_path = os.path.join(script_dir, "..", "database", "init.sql")

if not os.path.exists(sql_path):
    # Intentar ruta alternativa (si se ejecuta desde backend/)
    sql_path = os.path.join(script_dir, "init.sql")

if not os.path.exists(sql_path):
    print("ERROR: No se encontró init.sql")
    print(f"Buscado en: {sql_path}")
    sys.exit(1)

with open(sql_path, "r", encoding="utf-8") as f:
    sql_content = f.read()

print("Conectando a la base de datos...")
with engine.connect() as conn:
    # Ejecutar cada statement por separado
    statements = sql_content.split(";")
    executed = 0
    for stmt in statements:
        stmt = stmt.strip()
        if stmt and not stmt.startswith("--"):
            try:
                conn.execute(text(stmt))
                executed += 1
            except Exception as e:
                print(f"  ⚠️  Advertencia en statement: {str(e)[:80]}")
    conn.commit()
    print(f"✅ Base de datos inicializada correctamente ({executed} statements ejecutados)")
    print("   Tablas: marcas, lineas_terapeuticas, competidores, nuestros_productos, etc.")
    print("   Datos de ejemplo cargados.")
