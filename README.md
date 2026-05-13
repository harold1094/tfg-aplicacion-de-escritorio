# Aplicación de escritorio para sistema de facturación

Módulo de escritorio del TFG orientado a la gestión visual de clientes, productos/servicios y facturas. La aplicación está preparada para conectarse a una base de datos existente en Supabase, sin crear tablas, modificar esquemas ni realizar operaciones destructivas.

## Objetivo del módulo

El objetivo es proporcionar una aplicación profesional en Python y Qt para:

- Consultar clientes, productos/servicios y facturas.
- Preparar la creación y edición de facturas según el estado de cada factura.
- Calcular subtotal, IVA, total, importe pagado e importe pendiente.
- Exportar información a CSV, Excel y XML.
- Servir como base mantenible para adaptar el proyecto al esquema real de Supabase.

## Tecnologías usadas

- Python
- PySide6 / Qt
- Supabase
- python-dotenv
- openpyxl
- csv
- xml.etree.ElementTree
- pytest
- GitHub

## Instalación

Desde la carpeta del proyecto:

```bash
cd tfg-aplicacion-de-escritorio
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

En macOS o Linux:

```bash
cd tfg-aplicacion-de-escritorio
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Se recomienda usar Python 3.10 o superior.

## Configuración del entorno

Copia `.env.example` a `.env` y rellena las credenciales reales de Supabase:

```env
SUPABASE_URL=
SUPABASE_KEY=
```

No subas `.env` a GitHub. El archivo está incluido en `.gitignore` para evitar exponer credenciales.

## Ejecución

Desde la raíz del proyecto:

```bash
python -m app.main
```

Si las variables de Supabase no están configuradas, la aplicación arranca con datos de prueba para facilitar el desarrollo de la interfaz.

## Funcionalidades actuales

- Ventana principal con navegación entre Dashboard, Clientes, Productos/Servicios y Facturas.
- Dashboard inicial con métricas de facturación.
- Pantallas iniciales con tablas y datos de muestra.
- Controladores adaptados al esquema recibido de Supabase en modo solo lectura.
- Servicio de cálculo de facturas.
- Exportación de datos a CSV, Excel y XML.
- Estados profesionales de factura: BORRADOR, EMITIDA, PAGADA, PARCIALMENTE_PAGADA y CANCELADA.
- Tests básicos del cálculo de facturas.

## Adaptación actual a Supabase

La aplicación usa estas tablas del esquema recibido:

- `clientesEmisor`: clientes de facturación. Se usan `id`, `nombre`, `cif_nif_nie`, `direccion_completa`, `correo_electronico` y `telefono`.
- `facturas`: facturas y línea principal de producto/servicio.

La tabla `cliente` no se usa en la interfaz porque contiene `password`. El catálogo de productos/servicios se muestra de forma derivada desde los campos de `facturas`, ya que en el esquema recibido no aparece una tabla independiente de productos o servicios.

## Funcionalidades previstas

- Adaptar nombres reales de tablas y columnas de Supabase.
- Activar creación y edición de clientes, productos/servicios y facturas cuando el esquema esté validado.
- Incorporar autenticación si el alcance final del TFG lo requiere.
- Añadir filtros avanzados, búsqueda y validaciones de formularios.
- Ampliar pruebas automatizadas de controladores, servicios y reglas de negocio.

## Restricciones actuales

Esta base no crea SQLite, no modifica Supabase, no crea tablas y no ejecuta inserts, updates ni deletes. Para activar altas y ediciones habrá que validar antes permisos, políticas RLS y columnas definitivas.
