# Aplicación de escritorio Qt para facturación

Aplicación de escritorio del TFG desarrollada en `Python + PySide6/Qt` para gestión de clientes, productos/servicios y facturas. Mantiene integración con Supabase cuando está disponible y, si no lo está, funciona en modo local persistente para seguir operando y defender el proyecto sin dependencia externa.

## Capacidades actuales

- Login con Supabase Auth o acceso local de desarrollo cuando Supabase no está configurado.
- Roles de escritorio `administrador` y `contable`, con permisos distintos en la interfaz.
- CRUD de clientes, productos/servicios y facturas.
- Cobros parciales y control de estados `BORRADOR`, `EMITIDA`, `PAGADA`, `PARCIALMENTE_PAGADA`, `CANCELADA`.
- Dashboard con KPIs, evolución mensual, cliente principal y previsión ligera.
- Adjuntos de factura con almacenamiento local y subida a Supabase Storage cuando está disponible.
- Análisis OCR heurístico de adjuntos, clasificación asistida y detección de anomalías.
- Exportación a CSV, Excel, XML y PDF.
- Envío de factura por email con SMTP real o simulación controlada si no hay configuración.
- Auditoría local de acciones y generación de backups del modo escritorio.

## Tecnologías

- Python
- PySide6 / Qt
- Supabase
- python-dotenv
- openpyxl
- pytest

## Instalación

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

## Configuración

Copia `.env.example` a `.env` y rellena lo necesario:

```env
SUPABASE_URL=
SUPABASE_KEY=
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_SENDER=
ADMIN_EMAILS=
ACCOUNTANT_EMAILS=
```

Notas:

- Si `SUPABASE_URL` y `SUPABASE_KEY` están vacíos, la app entra en modo local persistente.
- Si SMTP no está configurado, el envío de email queda simulado para no bloquear el flujo.
- `ADMIN_EMAILS` y `ACCOUNTANT_EMAILS` permiten fijar roles por email en modo local o como fallback.

## Ejecución

```bash
python -m app.main
```

La aplicación guarda sus datos locales en `data/desktop_data.json`, adjuntos en `data/attachments/` y backups en `data/backups/`.

## Integración con Supabase

La aplicación intenta usar:

- `clientesEmisor` para clientes.
- `facturas` para facturas.
- `productos_servicios` para catálogo si existe.
- `roles_usuario` para resolver roles si existe.
- bucket `facturas` en Supabase Storage para adjuntos si existe.

Si alguna de esas piezas no está disponible, la app cae con elegancia a persistencia local sin interrumpir el uso del escritorio.

## Pruebas

```bash
pytest -q
```

La suite cubre cálculo, clasificación, anomalías, previsión y soporte base para el modo escritorio.
