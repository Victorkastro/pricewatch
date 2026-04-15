-- ============================================
-- PRICE ANALYZER - Schema de Base de Datos
-- (Modificado: categorias → marcas, nuevo campo linea_terapeutica)
-- ============================================

-- Marcas (antes "categorías")
CREATE TABLE IF NOT EXISTS marcas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Líneas terapéuticas
CREATE TABLE IF NOT EXISTS lineas_terapeuticas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(150) NOT NULL UNIQUE,
    descripcion TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Competidores
CREATE TABLE IF NOT EXISTS competidores (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE,
    url_web VARCHAR(255),
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Nuestros productos
CREATE TABLE IF NOT EXISTS nuestros_productos (
    id SERIAL PRIMARY KEY,
    codigo VARCHAR(50) UNIQUE NOT NULL,
    nombre VARCHAR(200) NOT NULL,
    descripcion TEXT,
    marca_id INT REFERENCES marcas(id),
    linea_terapeutica_id INT REFERENCES lineas_terapeuticas(id),
    precio_actual DECIMAL(12,2) NOT NULL,
    costo DECIMAL(12,2),
    unidad VARCHAR(50) DEFAULT 'unidad',
    activo BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Precios de la competencia
CREATE TABLE IF NOT EXISTS precios_competencia (
    id SERIAL PRIMARY KEY,
    producto_id INT REFERENCES nuestros_productos(id) ON DELETE CASCADE,
    competidor_id INT REFERENCES competidores(id) ON DELETE CASCADE,
    precio DECIMAL(12,2) NOT NULL,
    url_producto VARCHAR(500),
    fecha_registro DATE NOT NULL DEFAULT CURRENT_DATE,
    fuente VARCHAR(100) DEFAULT 'manual',
    notas TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Historial de cambios de nuestros precios
CREATE TABLE IF NOT EXISTS historial_precios_propios (
    id SERIAL PRIMARY KEY,
    producto_id INT REFERENCES nuestros_productos(id),
    precio_anterior DECIMAL(12,2),
    precio_nuevo DECIMAL(12,2),
    motivo VARCHAR(200),
    usuario VARCHAR(100),
    fecha_cambio TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Importaciones de Excel (log)
CREATE TABLE IF NOT EXISTS importaciones (
    id SERIAL PRIMARY KEY,
    nombre_archivo VARCHAR(255),
    tipo VARCHAR(50),
    registros_importados INT DEFAULT 0,
    registros_error INT DEFAULT 0,
    usuario VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Vista: Análisis comparativo de precios
CREATE OR REPLACE VIEW v_analisis_precios AS
SELECT
    np.id AS producto_id,
    np.codigo,
    np.nombre AS producto,
    m.nombre AS marca,
    lt.nombre AS linea_terapeutica,
    np.precio_actual AS nuestro_precio,
    np.costo,
    ROUND(((np.precio_actual - np.costo) / NULLIF(np.costo, 0)) * 100, 2) AS margen_porcentaje,
    comp.nombre AS competidor,
    pc.precio AS precio_competidor,
    pc.fecha_registro,
    ROUND(np.precio_actual - pc.precio, 2) AS diferencia_absoluta,
    ROUND(((np.precio_actual - pc.precio) / NULLIF(pc.precio, 0)) * 100, 2) AS diferencia_porcentaje,
    CASE
        WHEN np.precio_actual > pc.precio * 1.05 THEN 'ENCIMA'
        WHEN np.precio_actual < pc.precio * 0.95 THEN 'DEBAJO'
        ELSE 'SIMILAR'
    END AS estado_precio
FROM nuestros_productos np
LEFT JOIN marcas m ON np.marca_id = m.id
LEFT JOIN lineas_terapeuticas lt ON np.linea_terapeutica_id = lt.id
LEFT JOIN precios_competencia pc ON pc.producto_id = np.id
LEFT JOIN competidores comp ON pc.competidor_id = comp.id
WHERE np.activo = TRUE;

-- Vista: Resumen por producto (promedio competencia)
CREATE OR REPLACE VIEW v_resumen_productos AS
SELECT
    np.id,
    np.codigo,
    np.nombre AS producto,
    m.nombre AS marca,
    lt.nombre AS linea_terapeutica,
    np.precio_actual AS nuestro_precio,
    np.costo,
    COUNT(DISTINCT pc.competidor_id) AS num_competidores,
    ROUND(AVG(pc.precio), 2) AS precio_promedio_competencia,
    ROUND(MIN(pc.precio), 2) AS precio_minimo_competencia,
    ROUND(MAX(pc.precio), 2) AS precio_maximo_competencia,
    ROUND(np.precio_actual - AVG(pc.precio), 2) AS diff_vs_promedio,
    ROUND(((np.precio_actual - AVG(pc.precio)) / NULLIF(AVG(pc.precio), 0)) * 100, 2) AS diff_porcentaje_promedio,
    CASE
        WHEN np.precio_actual > AVG(pc.precio) * 1.05 THEN 'ENCIMA'
        WHEN np.precio_actual < AVG(pc.precio) * 0.95 THEN 'DEBAJO'
        ELSE 'SIMILAR'
    END AS estado_precio
FROM nuestros_productos np
LEFT JOIN marcas m ON np.marca_id = m.id
LEFT JOIN lineas_terapeuticas lt ON np.linea_terapeutica_id = lt.id
LEFT JOIN precios_competencia pc ON pc.producto_id = np.id
    AND pc.fecha_registro = (
        SELECT MAX(pc2.fecha_registro)
        FROM precios_competencia pc2
        WHERE pc2.producto_id = np.id AND pc2.competidor_id = pc.competidor_id
    )
WHERE np.activo = TRUE
GROUP BY np.id, np.codigo, np.nombre, m.nombre, lt.nombre, np.precio_actual, np.costo;

-- ============================================
-- DATOS INICIALES DE EJEMPLO
-- ============================================

INSERT INTO marcas (nombre, descripcion) VALUES
('Bayer', 'Productos farmacéuticos Bayer'),
('Pfizer', 'Productos farmacéuticos Pfizer'),
('Roche', 'Productos farmacéuticos Roche'),
('Sanofi', 'Productos farmacéuticos Sanofi'),
('Genéricos', 'Productos genéricos varios')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO lineas_terapeuticas (nombre, descripcion) VALUES
('Analgésicos', 'Medicamentos para el dolor'),
('Antibióticos', 'Medicamentos antibacterianos'),
('Cardiovascular', 'Medicamentos para el corazón y circulación'),
('Dermatología', 'Tratamientos de la piel'),
('Respiratorio', 'Medicamentos para vías respiratorias'),
('Gastrointestinal', 'Medicamentos para el sistema digestivo'),
('Vitaminas y Suplementos', 'Suplementos alimenticios y vitaminas')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO competidores (nombre, url_web) VALUES
('Competidor A', 'https://competidora.com'),
('Competidor B', 'https://competidorb.com'),
('Competidor C', 'https://competidorc.com')
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO nuestros_productos (codigo, nombre, descripcion, marca_id, linea_terapeutica_id, precio_actual, costo, unidad) VALUES
('PROD-001', 'Ibuprofeno 400mg x 20', 'Comprimidos de ibuprofeno 400mg', 1, 1, 350.00, 180.00, 'caja'),
('PROD-002', 'Amoxicilina 500mg x 21', 'Cápsulas de amoxicilina 500mg', 2, 2, 520.00, 280.00, 'caja'),
('PROD-003', 'Losartán 50mg x 30', 'Comprimidos de losartán potásico', 3, 3, 680.00, 350.00, 'caja'),
('PROD-004', 'Crema Hidratante 100ml', 'Crema dermatológica hidratante', 4, 4, 450.00, 200.00, 'unidad'),
('PROD-005', 'Salbutamol Inhalador', 'Aerosol para broncoespasmo', 1, 5, 890.00, 480.00, 'unidad'),
('PROD-006', 'Omeprazol 20mg x 28', 'Cápsulas gastrorresistentes', 5, 6, 320.00, 150.00, 'caja'),
('PROD-007', 'Vitamina C 1000mg x 30', 'Comprimidos efervescentes', 1, 7, 280.00, 120.00, 'tubo'),
('PROD-008', 'Paracetamol 500mg x 20', 'Comprimidos de paracetamol', 5, 1, 180.00, 80.00, 'caja')
ON CONFLICT (codigo) DO NOTHING;

INSERT INTO precios_competencia (producto_id, competidor_id, precio, fecha_registro) VALUES
(1, 1, 330.00, CURRENT_DATE),
(1, 2, 365.00, CURRENT_DATE),
(1, 3, 342.00, CURRENT_DATE),
(2, 1, 540.00, CURRENT_DATE),
(2, 2, 498.00, CURRENT_DATE),
(2, 3, 515.00, CURRENT_DATE),
(3, 1, 700.00, CURRENT_DATE),
(3, 2, 660.00, CURRENT_DATE),
(4, 1, 470.00, CURRENT_DATE),
(4, 2, 430.00, CURRENT_DATE),
(4, 3, 460.00, CURRENT_DATE),
(5, 1, 920.00, CURRENT_DATE),
(5, 2, 860.00, CURRENT_DATE),
(6, 1, 340.00, CURRENT_DATE),
(6, 2, 310.00, CURRENT_DATE),
(6, 3, 330.00, CURRENT_DATE),
(7, 1, 300.00, CURRENT_DATE),
(7, 2, 260.00, CURRENT_DATE),
(8, 1, 190.00, CURRENT_DATE),
(8, 2, 175.00, CURRENT_DATE);
