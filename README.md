# 🏷️ PriceWatch — Análisis de Precios vs Competencia

Sistema completo para comparar tus precios con la competencia, con indicadores visuales de si estás **por encima**, **por debajo** o **similar** al mercado.

**Campos principales:** Código, Nombre, **Marca**, **Línea Terapéutica**, Precio, Costo, Unidad.

---

## 🚀 Inicio Rápido (Local con Docker)

### Requisitos
- Docker Desktop instalado (https://www.docker.com/products/docker-desktop)
- Docker Compose v2+

### Arrancar la aplicación

```bash
# 1. Entra a la carpeta del proyecto
cd price-analyzer

# 2. Construye y arranca todos los servicios
docker compose up --build -d

# 3. Espera ~30 segundos y abre en tu navegador:
# http://localhost:3000
```

### Detener la aplicación
```bash
docker compose down
```

### Ver logs
```bash
docker compose logs -f
```

---

## 📋 Estructura del Proyecto

```
price-analyzer/
├── docker-compose.yml          # Orquestación Docker
├── database/
│   └── init.sql                # Tablas + datos de ejemplo
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py                 # API FastAPI
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    └── index.html              # Interfaz web
```

---

## 🗄️ Tablas de la Base de Datos

| Tabla | Descripción |
|-------|-------------|
| `marcas` | Marcas de productos (antes "categorías") |
| `lineas_terapeuticas` | Líneas terapéuticas de productos |
| `competidores` | Lista de competidores |
| `nuestros_productos` | Tus productos con precios y costos |
| `precios_competencia` | Precios relevados de competidores |
| `historial_precios_propios` | Auditoría de cambios de precio |
| `importaciones` | Log de archivos importados |

### Vistas
- `v_analisis_precios` — Comparativa por producto y competidor
- `v_resumen_productos` — Resumen consolidado con promedios

---

## 📊 Filtros Disponibles

### En la pantalla de Análisis puedes filtrar por:
- **Búsqueda de texto** — busca en nombre, código, marca y línea terapéutica
- **Estado** — ENCIMA, SIMILAR, DEBAJO
- **Marca** — dropdown con todas las marcas
- **Línea terapéutica** — dropdown con todas las líneas
- **Precio mínimo / máximo** — rango de nuestro precio
- **Diferencia % mínima / máxima** — rango de diferencia porcentual
- **Cantidad mínima de competidores** — filtra productos con N o más competidores
- **Ordenar por cualquier columna** — clic en el encabezado de la tabla

---

## 📥 Importar desde Excel

### Plantilla de Mis Productos

| codigo | nombre | precio_actual | costo | unidad | marca | linea_terapeutica | descripcion |
|--------|--------|--------------|-------|--------|-------|-------------------|-------------|
| PROD-001 | Ibuprofeno 400mg | 350 | 180 | caja | Bayer | Analgésicos | ... |

### Plantilla de Competencia

| codigo_producto | competidor | precio | fecha | url_producto | notas |
|----------------|------------|--------|-------|--------------|-------|
| PROD-001 | Competidor A | 330 | 2024-01-15 | https://... | |

---

## 🔌 API Endpoints

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/dashboard` | Resumen general |
| GET | `/api/analisis` | Análisis con filtros avanzados |
| GET | `/api/analisis/detalle/{id}` | Detalle por producto |
| GET/POST | `/api/productos` | Gestión de productos |
| PUT/DELETE | `/api/productos/{id}` | Editar/eliminar producto |
| POST | `/api/precios-competencia` | Agregar precio manual |
| GET/POST | `/api/competidores` | Gestión competidores |
| GET/POST | `/api/marcas` | Gestión marcas |
| GET/POST | `/api/lineas-terapeuticas` | Gestión líneas terapéuticas |
| POST | `/api/importar/productos` | Importar Excel productos |
| POST | `/api/importar/competencia` | Importar Excel competencia |
| GET | `/api/exportar/analisis` | Exportar análisis a Excel (con filtros) |

### Parámetros de filtro en `/api/analisis`:
```
?marca_id=1&linea_terapeutica_id=2&estado=ENCIMA&buscar=texto
&precio_min=100&precio_max=5000&diff_min=-20&diff_max=50&competidores_min=2
```

---

## 🌐 Cómo Publicar Online (Gratis)

### Opción 1: Render.com (Recomendada — Más fácil)

Render ofrece hosting gratuito con PostgreSQL incluido.

**Paso 1: Crear cuenta**
- Ve a https://render.com y crea una cuenta gratis con GitHub.

**Paso 2: Subir código a GitHub**
```bash
# En tu computadora, dentro de la carpeta price-analyzer:
git init
git add .
git commit -m "PriceWatch v2"
# Crea un repositorio nuevo en github.com y luego:
git remote add origin https://github.com/TU_USUARIO/pricewatch.git
git branch -M main
git push -u origin main
```

**Paso 3: Crear base de datos PostgreSQL en Render**
1. En Render Dashboard → **New** → **PostgreSQL**
2. Nombre: `pricewatch-db`
3. Plan: **Free**
4. Clic en **Create Database**
5. Copia la **Internal Database URL** (la necesitas para el backend)
6. Ve a la pestaña **Shell** de tu base de datos y ejecuta el contenido de `database/init.sql`

**Paso 4: Desplegar el Backend**
1. **New** → **Web Service**
2. Conecta tu repo de GitHub
3. Configuración:
   - **Name:** `pricewatch-api`
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
4. **Environment Variables:**
   - `DATABASE_URL` = (pega la Internal Database URL del paso 3)
5. Clic en **Create Web Service**

**Paso 5: Desplegar el Frontend**
1. **New** → **Static Site**
2. Conecta el mismo repo
3. Configuración:
   - **Name:** `pricewatch-app`
   - **Root Directory:** `frontend`
   - **Build Command:** (dejar vacío)
   - **Publish Directory:** `.`
4. Crea un archivo `frontend/_redirects` con:
   ```
   /api/*  https://pricewatch-api.onrender.com/api/:splat  200
   ```
5. Clic en **Create Static Site**

Tu app estará en: `https://pricewatch-app.onrender.com` 🎉

---

### Opción 2: Railway.app (Más rápida de configurar)

Railway despliega Docker directamente y da $5 USD/mes gratis.

**Paso 1:** Ve a https://railway.app y crea cuenta con GitHub.

**Paso 2:** Sube tu código a GitHub (mismo procedimiento de arriba).

**Paso 3:** En Railway:
1. **New Project** → **Deploy from GitHub repo**
2. Selecciona tu repositorio
3. Railway detectará el `docker-compose.yml` automáticamente
4. Agrega un servicio de **PostgreSQL** desde el marketplace
5. Conecta la variable `DATABASE_URL` del PostgreSQL al servicio backend

**Paso 4:** En Settings del servicio frontend:
- Genera un **dominio público** (ej: `pricewatch-production.up.railway.app`)

Tu app estará lista con el dominio que Railway te asigne.

---

### Opción 3: Fly.io

Fly.io ofrece máquinas gratuitas pequeñas.

```bash
# Instalar flyctl
curl -L https://fly.io/install.sh | sh

# Login
fly auth signup  # o fly auth login

# Desde la carpeta del proyecto:
fly launch  # Sigue las instrucciones interactivas

# Crear base de datos PostgreSQL
fly postgres create --name pricewatch-db

# Conectar la base de datos
fly postgres attach pricewatch-db

# Desplegar
fly deploy
```

---

### Opción 4: VPS barato (DigitalOcean, Hetzner)

Si prefieres un servidor completo (~$4-5/mes):

```bash
# En el servidor (Ubuntu):
# 1. Instalar Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Clonar tu repo
git clone https://github.com/TU_USUARIO/pricewatch.git
cd pricewatch

# 3. Arrancar
docker compose up --build -d

# 4. (Opcional) Configurar HTTPS con Caddy
# Instalar Caddy y crear Caddyfile:
# tudominio.com {
#   reverse_proxy localhost:3000
# }
```

---

## 🛠️ Configuración Avanzada

### Cambiar credenciales de base de datos
Edita `docker-compose.yml` y actualiza `DATABASE_URL` en el servicio backend.

### Conectar con pgAdmin o DBeaver (local)
- Host: `localhost`
- Puerto: `5432`
- Base de datos: `pricedb`
- Usuario: `priceuser`
- Contraseña: `pricepass`

---

## 📞 Soporte

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Base de datos:** localhost:5432
