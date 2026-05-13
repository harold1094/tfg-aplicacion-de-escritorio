# Documentación técnica inicial

## Arquitectura del proyecto

La aplicación sigue una arquitectura por capas para separar interfaz, reglas de negocio, acceso a datos y documentación. Esta separación facilita explicar el proyecto en la defensa del TFG y permite cambiar el esquema real de Supabase sin rehacer toda la interfaz.

## Estructura de carpetas

```text
tfg-aplicacion-de-escritorio/
├── app/
│   ├── main.py
│   ├── config.py
│   ├── supabase_client.py
│   ├── models/
│   ├── views/
│   ├── controllers/
│   ├── services/
│   └── assets/
├── docs/
├── tests/
├── README.md
├── requirements.txt
├── .env
└── .env.example
```

## Conexión con Supabase

La conexión se configura con `python-dotenv` leyendo el archivo `.env`:

```env
SUPABASE_URL=
SUPABASE_KEY=
```

El módulo `app/supabase_client.py` crea el cliente de Supabase solo si ambas variables existen. Si no están configuradas, la aplicación usa datos de prueba para que la interfaz pueda desarrollarse sin depender todavía del esquema final.

Importante: esta base no crea tablas, no modifica esquemas y no ejecuta operaciones destructivas.

## Esquema de Supabase recibido

La aplicación queda adaptada inicialmente a estas tablas:

- `clientesEmisor`: origen principal para clientes de facturación.
- `facturas`: origen principal para facturas y conceptos facturados.
- `emisores` y `serieFacturacion`: existen en el esquema, pero de momento no se modifican desde la aplicación.

La tabla `cliente` no se usa en las vistas porque contiene credenciales (`password`). En una aplicación de escritorio no conviene cargar ni mostrar ese campo.

No existe en el esquema recibido una tabla independiente de productos/servicios. Por ese motivo, `ProductoController` construye un catálogo temporal leyendo los campos `descripcion_producto_servicio`, `descripcion_general`, `precio_unitario`, `importe_linea` y `subtotal_sin_iva` desde `facturas`.

## Separación por capas

### Models

Contienen las clases de dominio:

- `Cliente`
- `Producto`
- `Factura`
- `LineaFactura`
- `EstadoFactura`

Los estados de factura definidos son:

- `BORRADOR`: editable.
- `EMITIDA`: no editable.
- `PAGADA`: no editable.
- `PARCIALMENTE_PAGADA`: no editable.
- `CANCELADA`: no editable.

### Views

Contienen las pantallas desarrolladas con PySide6:

- `MainWindow`: ventana principal y navegación lateral.
- `DashboardView`: métricas principales.
- `ClientesView`: listado inicial de clientes.
- `ProductosView`: catálogo de productos y servicios.
- `FacturasView`: listado de facturas y exportaciones.

Las vistas no conocen detalles internos de Supabase; consumen datos a través de los controladores.

### Controllers

Preparan la comunicación entre vistas y datos. Actualmente trabajan en modo seguro:

- Si Supabase no está configurado, devuelven datos de muestra.
- Si el esquema real no coincide todavía, mantienen la aplicación funcionando con datos de muestra.
- No realizan inserts, updates ni deletes.

Los controladores ya usan los nombres recibidos:

- `ClienteController`: tabla `clientesEmisor`.
- `FacturaController`: tabla `facturas` y lectura auxiliar de `clientesEmisor`.
- `ProductoController`: catálogo derivado desde `facturas` hasta que exista una tabla propia de productos/servicios.

### Services

Agrupan lógica reutilizable:

- `invoice_calculator.py`: cálculo de subtotal, IVA, total, importe pagado e importe pendiente.
- `export_csv.py`: exportación CSV.
- `export_excel.py`: exportación Excel con `openpyxl`.
- `export_xml.py`: exportación XML con `xml.etree.ElementTree`.

## Funcionalidades del módulo de escritorio

- Navegación entre Dashboard, Clientes, Productos/Servicios y Facturas.
- Datos iniciales de prueba para desarrollo visual.
- Preparación de conexión a Supabase con variables de entorno.
- Cálculo profesional de importes de factura.
- Control de estados de factura y edición limitada a borradores.
- Exportación a CSV, Excel y XML.
- Tests básicos del servicio de cálculo.

## Próximos pasos técnicos

1. Confirmar si la tabla `clientesEmisor` está creada con mayúsculas exactas o si Supabase la expone como `clientesemisor`.
2. Confirmar los valores reales usados en `facturas.estado_pago`.
3. Añadir un campo real de importe pagado si el sistema debe distinguir cobros parciales con precisión.
4. Confirmar si productos/servicios tendrán tabla propia o seguirán incrustados en `facturas`.
5. Crear formularios de alta y edición cuando se validen permisos, políticas RLS y reglas del equipo.
6. Ampliar tests de controladores y exportaciones.
