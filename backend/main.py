from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
import io
import os
from datetime import date, datetime
from decimal import Decimal

# ── Config ──────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://priceuser:pricepass@db:5432/pricedb"
)

engine = create_engine(DATABASE_URL)

app = FastAPI(title="PriceWatch API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()

# ── Modelos Pydantic ─────────────────────────────────────────────────────────
class ProductoCreate(BaseModel):
    codigo: str
    nombre: str
    descripcion: Optional[str] = None
    marca_id: Optional[int] = None
    linea_terapeutica_id: Optional[int] = None
    precio_actual: float
    costo: Optional[float] = None
    unidad: str = "unidad"

class ProductoUpdate(BaseModel):
    nombre: Optional[str] = None
    descripcion: Optional[str] = None
    marca_id: Optional[int] = None
    linea_terapeutica_id: Optional[int] = None
    precio_actual: Optional[float] = None
    costo: Optional[float] = None
    unidad: Optional[str] = None

class PrecioCompetenciaCreate(BaseModel):
    producto_id: int
    competidor_id: int
    precio: float
    url_producto: Optional[str] = None
    fecha_registro: Optional[date] = None
    notas: Optional[str] = None

class CompetidorCreate(BaseModel):
    nombre: str
    url_web: Optional[str] = None

class MarcaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class LineaTerapeuticaCreate(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

# ── Helpers ──────────────────────────────────────────────────────────────────
def rows_to_list(result):
    rows = result.fetchall()
    keys = result.keys()
    return [dict(zip(keys, row)) for row in rows]

def serialize(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

def clean_row(row: dict):
    return {k: serialize(v) for k, v in row.items()}

# ── Dashboard ────────────────────────────────────────────────────────────────
@app.get("/api/dashboard")
def dashboard(db=Depends(get_db)):
    total_productos = db.execute(text("SELECT COUNT(*) FROM nuestros_productos WHERE activo=TRUE")).scalar()
    total_competidores = db.execute(text("SELECT COUNT(*) FROM competidores WHERE activo=TRUE")).scalar()
    
    distribucion = db.execute(text("""
        SELECT estado_precio, COUNT(*) as cantidad
        FROM v_resumen_productos
        WHERE precio_promedio_competencia IS NOT NULL
        GROUP BY estado_precio
    """))
    dist_rows = rows_to_list(distribucion)

    encima = next((r["cantidad"] for r in dist_rows if r["estado_precio"] == "ENCIMA"), 0)
    debajo = next((r["cantidad"] for r in dist_rows if r["estado_precio"] == "DEBAJO"), 0)
    similar = next((r["cantidad"] for r in dist_rows if r["estado_precio"] == "SIMILAR"), 0)

    sin_datos = db.execute(text("""
        SELECT COUNT(*) FROM v_resumen_productos WHERE precio_promedio_competencia IS NULL
    """)).scalar()

    top_diff = db.execute(text("""
        SELECT producto, marca, linea_terapeutica, diff_porcentaje_promedio, estado_precio
        FROM v_resumen_productos
        WHERE precio_promedio_competencia IS NOT NULL
        ORDER BY ABS(diff_porcentaje_promedio) DESC
        LIMIT 5
    """))

    ultima_importacion = db.execute(text("""
        SELECT nombre_archivo, created_at FROM importaciones ORDER BY created_at DESC LIMIT 1
    """)).fetchone()

    return {
        "total_productos": total_productos,
        "total_competidores": total_competidores,
        "encima": encima,
        "debajo": debajo,
        "similar": similar,
        "sin_datos": sin_datos,
        "top_diferencias": [clean_row(r) for r in rows_to_list(top_diff)],
        "ultima_importacion": {
            "archivo": ultima_importacion[0],
            "fecha": serialize(ultima_importacion[1])
        } if ultima_importacion else None
    }

# ── Análisis de precios (con filtros avanzados) ─────────────────────────────
@app.get("/api/analisis")
def analisis_precios(
    marca_id: Optional[int] = None,
    linea_terapeutica_id: Optional[int] = None,
    estado: Optional[str] = None,
    buscar: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    competidores_min: Optional[int] = None,
    diff_min: Optional[float] = None,
    diff_max: Optional[float] = None,
    db=Depends(get_db)
):
    where_parts = ["precio_promedio_competencia IS NOT NULL"]
    params = {}
    
    if marca_id:
        where_parts.append("marca = (SELECT nombre FROM marcas WHERE id = :marca_id)")
        params["marca_id"] = marca_id
    if linea_terapeutica_id:
        where_parts.append("linea_terapeutica = (SELECT nombre FROM lineas_terapeuticas WHERE id = :lt_id)")
        params["lt_id"] = linea_terapeutica_id
    if estado and estado in ("ENCIMA", "DEBAJO", "SIMILAR"):
        where_parts.append("estado_precio = :estado")
        params["estado"] = estado
    if buscar:
        where_parts.append("(LOWER(producto) LIKE :buscar OR LOWER(codigo) LIKE :buscar OR LOWER(COALESCE(marca,'')) LIKE :buscar OR LOWER(COALESCE(linea_terapeutica,'')) LIKE :buscar)")
        params["buscar"] = f"%{buscar.lower()}%"
    if precio_min is not None:
        where_parts.append("nuestro_precio >= :precio_min")
        params["precio_min"] = precio_min
    if precio_max is not None:
        where_parts.append("nuestro_precio <= :precio_max")
        params["precio_max"] = precio_max
    if competidores_min is not None:
        where_parts.append("num_competidores >= :comp_min")
        params["comp_min"] = competidores_min
    if diff_min is not None:
        where_parts.append("diff_porcentaje_promedio >= :diff_min")
        params["diff_min"] = diff_min
    if diff_max is not None:
        where_parts.append("diff_porcentaje_promedio <= :diff_max")
        params["diff_max"] = diff_max

    where_clause = " AND ".join(where_parts)
    query = f"SELECT * FROM v_resumen_productos WHERE {where_clause} ORDER BY ABS(diff_porcentaje_promedio) DESC NULLS LAST"
    result = db.execute(text(query), params)
    return [clean_row(r) for r in rows_to_list(result)]

# Endpoint para obtener todos los análisis (incluyendo sin datos de competencia)
@app.get("/api/analisis/todos")
def analisis_todos(
    marca_id: Optional[int] = None,
    linea_terapeutica_id: Optional[int] = None,
    estado: Optional[str] = None,
    buscar: Optional[str] = None,
    db=Depends(get_db)
):
    where_parts = ["1=1"]
    params = {}
    if marca_id:
        where_parts.append("marca = (SELECT nombre FROM marcas WHERE id = :marca_id)")
        params["marca_id"] = marca_id
    if linea_terapeutica_id:
        where_parts.append("linea_terapeutica = (SELECT nombre FROM lineas_terapeuticas WHERE id = :lt_id)")
        params["lt_id"] = linea_terapeutica_id
    if estado and estado in ("ENCIMA", "DEBAJO", "SIMILAR"):
        where_parts.append("estado_precio = :estado")
        params["estado"] = estado
    if buscar:
        where_parts.append("(LOWER(producto) LIKE :buscar OR LOWER(codigo) LIKE :buscar)")
        params["buscar"] = f"%{buscar.lower()}%"

    where_clause = " AND ".join(where_parts)
    query = f"SELECT * FROM v_resumen_productos WHERE {where_clause} ORDER BY producto"
    result = db.execute(text(query), params)
    return [clean_row(r) for r in rows_to_list(result)]


@app.get("/api/analisis/detalle/{producto_id}")
def detalle_producto(producto_id: int, db=Depends(get_db)):
    producto = db.execute(text("""
        SELECT np.*, m.nombre as marca_nombre, lt.nombre as linea_terapeutica_nombre
        FROM nuestros_productos np
        LEFT JOIN marcas m ON m.id = np.marca_id
        LEFT JOIN lineas_terapeuticas lt ON lt.id = np.linea_terapeutica_id
        WHERE np.id = :id
    """), {"id": producto_id}).fetchone()
    if not producto:
        raise HTTPException(404, "Producto no encontrado")
    
    competencia = db.execute(text("""
        SELECT comp.nombre as competidor, pc.precio, pc.fecha_registro,
               pc.url_producto, pc.notas,
               ROUND(np.precio_actual - pc.precio, 2) as diferencia,
               ROUND(((np.precio_actual - pc.precio) / NULLIF(pc.precio,0))*100, 2) as diff_pct,
               CASE WHEN np.precio_actual > pc.precio*1.05 THEN 'ENCIMA'
                    WHEN np.precio_actual < pc.precio*0.95 THEN 'DEBAJO'
                    ELSE 'SIMILAR' END as estado
        FROM precios_competencia pc
        JOIN competidores comp ON comp.id = pc.competidor_id
        JOIN nuestros_productos np ON np.id = pc.producto_id
        WHERE pc.producto_id = :id
        ORDER BY pc.fecha_registro DESC, comp.nombre
    """), {"id": producto_id})

    historial = db.execute(text("""
        SELECT precio_anterior, precio_nuevo, motivo, fecha_cambio
        FROM historial_precios_propios
        WHERE producto_id = :id
        ORDER BY fecha_cambio DESC LIMIT 20
    """), {"id": producto_id})

    keys = ["id","codigo","nombre","descripcion","marca_id","linea_terapeutica_id",
            "precio_actual","costo","unidad","activo","created_at","updated_at",
            "marca_nombre","linea_terapeutica_nombre"]
    prod_dict = clean_row(dict(zip(keys, producto)))

    return {
        "producto": prod_dict,
        "competencia": [clean_row(r) for r in rows_to_list(competencia)],
        "historial": [clean_row(r) for r in rows_to_list(historial)]
    }

# ── Productos (CRUD) ──────────────────────────────────────────────────────────
@app.get("/api/productos")
def listar_productos(db=Depends(get_db)):
    result = db.execute(text("""
        SELECT np.*, m.nombre as marca_nombre, lt.nombre as linea_terapeutica_nombre
        FROM nuestros_productos np
        LEFT JOIN marcas m ON m.id = np.marca_id
        LEFT JOIN lineas_terapeuticas lt ON lt.id = np.linea_terapeutica_id
        WHERE np.activo = TRUE ORDER BY np.nombre
    """))
    return [clean_row(r) for r in rows_to_list(result)]

@app.post("/api/productos")
def crear_producto(producto: ProductoCreate, db=Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO nuestros_productos (codigo, nombre, descripcion, marca_id, linea_terapeutica_id, precio_actual, costo, unidad)
        VALUES (:codigo, :nombre, :descripcion, :marca_id, :linea_terapeutica_id, :precio_actual, :costo, :unidad)
        RETURNING id
    """), producto.model_dump())
    db.commit()
    return {"id": result.scalar(), "message": "Producto creado exitosamente"}

@app.put("/api/productos/{producto_id}")
def actualizar_producto(producto_id: int, datos: ProductoUpdate, db=Depends(get_db)):
    if datos.precio_actual is not None:
        precio_anterior = db.execute(
            text("SELECT precio_actual FROM nuestros_productos WHERE id = :id"),
            {"id": producto_id}
        ).scalar()
        if precio_anterior and float(precio_anterior) != datos.precio_actual:
            db.execute(text("""
                INSERT INTO historial_precios_propios (producto_id, precio_anterior, precio_nuevo, motivo)
                VALUES (:pid, :prev, :new, 'Actualización manual')
            """), {"pid": producto_id, "prev": precio_anterior, "new": datos.precio_actual})

    fields = {k: v for k, v in datos.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No hay datos para actualizar")
    
    set_clause = ", ".join([f"{k} = :{k}" for k in fields])
    fields["id"] = producto_id
    db.execute(text(f"UPDATE nuestros_productos SET {set_clause}, updated_at=NOW() WHERE id = :id"), fields)
    db.commit()
    return {"message": "Producto actualizado"}

@app.delete("/api/productos/{producto_id}")
def eliminar_producto(producto_id: int, db=Depends(get_db)):
    db.execute(text("UPDATE nuestros_productos SET activo=FALSE WHERE id=:id"), {"id": producto_id})
    db.commit()
    return {"message": "Producto eliminado"}

# ── Precios Competencia ───────────────────────────────────────────────────────
@app.post("/api/precios-competencia")
def agregar_precio(precio: PrecioCompetenciaCreate, db=Depends(get_db)):
    datos = precio.model_dump()
    if not datos.get("fecha_registro"):
        datos["fecha_registro"] = date.today()
    
    # Verificar si ya existe un precio para este producto+competidor+fecha
    existing = db.execute(text("""
        SELECT id FROM precios_competencia
        WHERE producto_id = :producto_id AND competidor_id = :competidor_id AND fecha_registro = :fecha_registro
    """), datos).scalar()
    
    if existing:
        # Actualizar el precio existente
        db.execute(text("""
            UPDATE precios_competencia
            SET precio = :precio, url_producto = :url_producto, notas = :notas
            WHERE id = :id
        """), {**datos, "id": existing})
    else:
        # Insertar nuevo precio
        db.execute(text("""
            INSERT INTO precios_competencia (producto_id, competidor_id, precio, url_producto, fecha_registro, notas)
            VALUES (:producto_id, :competidor_id, :precio, :url_producto, :fecha_registro, :notas)
        """), datos)
    
    db.commit()
    return {"message": "Precio registrado"}

# ── Marcas ────────────────────────────────────────────────────────────────────
@app.get("/api/marcas")
def listar_marcas(db=Depends(get_db)):
    result = db.execute(text("SELECT * FROM marcas ORDER BY nombre"))
    return [clean_row(r) for r in rows_to_list(result)]

@app.post("/api/marcas")
def crear_marca(marca: MarcaCreate, db=Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO marcas (nombre, descripcion) VALUES (:nombre, :descripcion) RETURNING id
    """), marca.model_dump())
    db.commit()
    return {"id": result.scalar(), "message": "Marca creada"}

# ── Líneas Terapéuticas ──────────────────────────────────────────────────────
@app.get("/api/lineas-terapeuticas")
def listar_lineas(db=Depends(get_db)):
    result = db.execute(text("SELECT * FROM lineas_terapeuticas ORDER BY nombre"))
    return [clean_row(r) for r in rows_to_list(result)]

@app.post("/api/lineas-terapeuticas")
def crear_linea(linea: LineaTerapeuticaCreate, db=Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO lineas_terapeuticas (nombre, descripcion) VALUES (:nombre, :descripcion) RETURNING id
    """), linea.model_dump())
    db.commit()
    return {"id": result.scalar(), "message": "Línea terapéutica creada"}

# ── Competidores ──────────────────────────────────────────────────────────────
@app.get("/api/competidores")
def listar_competidores(db=Depends(get_db)):
    result = db.execute(text("SELECT * FROM competidores WHERE activo=TRUE ORDER BY nombre"))
    return [clean_row(r) for r in rows_to_list(result)]

@app.post("/api/competidores")
def crear_competidor(comp: CompetidorCreate, db=Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO competidores (nombre, url_web) VALUES (:nombre, :url_web) RETURNING id
    """), comp.model_dump())
    db.commit()
    return {"id": result.scalar(), "message": "Competidor creado"}

# ── Importar Excel ────────────────────────────────────────────────────────────
@app.post("/api/importar/productos")
async def importar_productos_excel(file: UploadFile = File(...), db=Depends(get_db)):
    """Importar nuestros productos desde Excel.
    Columnas requeridas: codigo, nombre, precio_actual
    Opcionales: descripcion, marca, linea_terapeutica, costo, unidad
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx o .xls)")
    
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    except Exception as e:
        raise HTTPException(400, f"Error leyendo Excel: {str(e)}")

    required = {"codigo", "nombre", "precio_actual"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(400, f"Columnas requeridas: {required}. Encontradas: {set(df.columns)}")

    ok, errors = 0, 0
    for _, row in df.iterrows():
        try:
            marca_id = None
            if "marca" in df.columns and pd.notna(row.get("marca")):
                marca = db.execute(text("SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(:n)"),
                                 {"n": str(row["marca"])}).scalar()
                if not marca:
                    db.execute(text("INSERT INTO marcas (nombre) VALUES (:n)"), {"n": str(row["marca"])})
                    db.commit()
                    marca = db.execute(text("SELECT id FROM marcas WHERE LOWER(nombre)=LOWER(:n)"),
                                     {"n": str(row["marca"])}).scalar()
                marca_id = marca

            lt_id = None
            if "linea_terapeutica" in df.columns and pd.notna(row.get("linea_terapeutica")):
                lt = db.execute(text("SELECT id FROM lineas_terapeuticas WHERE LOWER(nombre)=LOWER(:n)"),
                               {"n": str(row["linea_terapeutica"])}).scalar()
                if not lt:
                    db.execute(text("INSERT INTO lineas_terapeuticas (nombre) VALUES (:n)"), {"n": str(row["linea_terapeutica"])})
                    db.commit()
                    lt = db.execute(text("SELECT id FROM lineas_terapeuticas WHERE LOWER(nombre)=LOWER(:n)"),
                                   {"n": str(row["linea_terapeutica"])}).scalar()
                lt_id = lt

            existing = db.execute(text("SELECT id FROM nuestros_productos WHERE codigo=:c"),
                                  {"c": str(row["codigo"])}).scalar()
            if existing:
                db.execute(text("""
                    UPDATE nuestros_productos SET nombre=:n, precio_actual=:p,
                    marca_id=:marca, linea_terapeutica_id=:lt, updated_at=NOW()
                    WHERE codigo=:c
                """), {"n": str(row["nombre"]), "p": float(row["precio_actual"]),
                       "marca": marca_id, "lt": lt_id, "c": str(row["codigo"])})
            else:
                db.execute(text("""
                    INSERT INTO nuestros_productos (codigo, nombre, precio_actual, marca_id, linea_terapeutica_id, costo, unidad)
                    VALUES (:c, :n, :p, :marca, :lt, :cost, :u)
                """), {
                    "c": str(row["codigo"]), "n": str(row["nombre"]),
                    "p": float(row["precio_actual"]), "marca": marca_id, "lt": lt_id,
                    "cost": float(row["costo"]) if "costo" in df.columns and pd.notna(row.get("costo")) else None,
                    "u": str(row["unidad"]) if "unidad" in df.columns and pd.notna(row.get("unidad")) else "unidad"
                })
            db.commit()
            ok += 1
        except Exception:
            errors += 1

    db.execute(text("""
        INSERT INTO importaciones (nombre_archivo, tipo, registros_importados, registros_error)
        VALUES (:f, 'propios', :ok, :err)
    """), {"f": file.filename, "ok": ok, "err": errors})
    db.commit()
    return {"importados": ok, "errores": errors, "archivo": file.filename}

@app.post("/api/importar/competencia")
async def importar_competencia_excel(file: UploadFile = File(...), db=Depends(get_db)):
    """Importar precios de competencia desde Excel.
    Columnas: codigo_producto, competidor, precio
    Opcionales: fecha, url_producto, notas
    Si ya existe un precio para el mismo producto+competidor+fecha, se ACTUALIZA en vez de duplicar.
    """
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Solo se aceptan archivos Excel (.xlsx o .xls)")
    
    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    except Exception as e:
        raise HTTPException(400, f"Error leyendo Excel: {str(e)}")

    required = {"codigo_producto", "competidor", "precio"}
    if not required.issubset(set(df.columns)):
        raise HTTPException(400, f"Columnas requeridas: {required}. Encontradas: {set(df.columns)}")

    ok, errors, actualizados = 0, 0, 0
    for _, row in df.iterrows():
        try:
            prod_id = db.execute(text("SELECT id FROM nuestros_productos WHERE codigo=:c"),
                                 {"c": str(row["codigo_producto"])}).scalar()
            if not prod_id:
                errors += 1
                continue
            
            comp_nombre = str(row["competidor"]).strip()
            comp_id = db.execute(text("SELECT id FROM competidores WHERE LOWER(nombre)=LOWER(:n)"),
                                 {"n": comp_nombre}).scalar()
            if not comp_id:
                res = db.execute(text("INSERT INTO competidores (nombre) VALUES (:n) RETURNING id"),
                                 {"n": comp_nombre})
                db.commit()
                comp_id = res.scalar()

            fecha = date.today()
            if "fecha" in df.columns and pd.notna(row.get("fecha")):
                try:
                    fecha = pd.to_datetime(row["fecha"]).date()
                except Exception:
                    pass

            url = str(row["url_producto"]) if "url_producto" in df.columns and pd.notna(row.get("url_producto")) else None
            notas = str(row["notas"]) if "notas" in df.columns and pd.notna(row.get("notas")) else None

            # Verificar si ya existe un precio para este producto+competidor+fecha
            existing = db.execute(text("""
                SELECT id FROM precios_competencia
                WHERE producto_id = :pid AND competidor_id = :cid AND fecha_registro = :f
            """), {"pid": prod_id, "cid": comp_id, "f": fecha}).scalar()

            if existing:
                # Actualizar el precio existente
                db.execute(text("""
                    UPDATE precios_competencia
                    SET precio = :p, url_producto = :url, notas = :notas
                    WHERE id = :id
                """), {"p": float(row["precio"]), "url": url, "notas": notas, "id": existing})
                actualizados += 1
            else:
                # Insertar nuevo precio
                db.execute(text("""
                    INSERT INTO precios_competencia (producto_id, competidor_id, precio, fecha_registro, url_producto, notas)
                    VALUES (:pid, :cid, :p, :f, :url, :notas)
                """), {
                    "pid": prod_id, "cid": comp_id, "p": float(row["precio"]),
                    "f": fecha, "url": url, "notas": notas
                })

            db.commit()
            ok += 1
        except Exception:
            errors += 1

    db.execute(text("""
        INSERT INTO importaciones (nombre_archivo, tipo, registros_importados, registros_error)
        VALUES (:f, 'competencia', :ok, :err)
    """), {"f": file.filename, "ok": ok, "err": errors})
    db.commit()
    return {"importados": ok, "actualizados": actualizados, "errores": errors, "archivo": file.filename}

# ── Exportar Excel ────────────────────────────────────────────────────────────
@app.get("/api/exportar/analisis")
def exportar_analisis(
    marca_id: Optional[int] = None,
    linea_terapeutica_id: Optional[int] = None,
    estado: Optional[str] = None,
    buscar: Optional[str] = None,
    db=Depends(get_db)
):
    where_parts = ["1=1"]
    params = {}
    if marca_id:
        where_parts.append("marca = (SELECT nombre FROM marcas WHERE id = :marca_id)")
        params["marca_id"] = marca_id
    if linea_terapeutica_id:
        where_parts.append("linea_terapeutica = (SELECT nombre FROM lineas_terapeuticas WHERE id = :lt_id)")
        params["lt_id"] = linea_terapeutica_id
    if estado and estado in ("ENCIMA", "DEBAJO", "SIMILAR"):
        where_parts.append("estado_precio = :estado")
        params["estado"] = estado
    if buscar:
        where_parts.append("(LOWER(producto) LIKE :buscar OR LOWER(codigo) LIKE :buscar)")
        params["buscar"] = f"%{buscar.lower()}%"

    where_clause = " AND ".join(where_parts)
    query = f"SELECT * FROM v_analisis_precios WHERE {where_clause} ORDER BY producto, competidor"
    result = db.execute(text(query), params)
    rows = rows_to_list(result)
    df = pd.DataFrame([clean_row(r) for r in rows])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Análisis de Precios", index=False)
        wb = writer.book
        ws = writer.sheets["Análisis de Precios"]
        
        fmt_header = wb.add_format({"bold": True, "bg_color": "#1e293b", "font_color": "white", "border": 1})
        for col_num, col_name in enumerate(df.columns):
            ws.write(0, col_num, col_name, fmt_header)
            ws.set_column(col_num, col_num, 18)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=analisis_precios_{date.today()}.xlsx"}
    )

@app.get("/api/exportar/plantilla-productos")
def plantilla_productos():
    df = pd.DataFrame(columns=["codigo","nombre","descripcion","precio_actual","costo","unidad","marca","linea_terapeutica"])
    df.loc[0] = ["PROD-001","Producto Ejemplo","Descripción aquí",100.00,60.00,"unidad","Bayer","Analgésicos"]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Plantilla Productos", index=False)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_productos.xlsx"}
    )

@app.get("/api/exportar/plantilla-competencia")
def plantilla_competencia():
    df = pd.DataFrame(columns=["codigo_producto","competidor","precio","fecha","url_producto","notas"])
    df.loc[0] = ["PROD-001","Competidor A",95.00,"2024-01-15","https://ejemplo.com",""]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Plantilla Competencia", index=False)
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=plantilla_competencia.xlsx"}
    )

@app.get("/health")
def health():
    return {"status": "ok"}
