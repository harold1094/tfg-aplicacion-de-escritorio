# Automalize Escritorio

Aplicación de escritorio del TFG orientada a facturación profesional con `Python`, `PySide6` y `Supabase`.

El proyecto ya no es solo una maqueta visual: incluye autenticación real contra Supabase, controladores por dominio, servicios separados para tareas técnicas y reglas de negocio para el ciclo de vida de una factura.

## Qué hace la aplicación

La app permite trabajar desde escritorio con los módulos principales del sistema:

- Dashboard con métricas rápidas.
- Gestión de facturas con estados y reglas de edición.
- Gestión de clientes.
- Gestión de productos.
- Exportación a `CSV`, `Excel` y `XML`.
- Generación de `PDF`.
- Envío de factura por correo mediante `SMTP`.
- Importación OCR de PDF o imagen para crear borradores revisables.
- Preparación de integración con `Verifactu`.

## Stack tecnológico

- `Python`
- `PySide6 / Qt`
- `Supabase`
- `python-dotenv`
- `openpyxl`
- `reportlab`
- `pytest`

## Arquitectura

La aplicación está organizada por capas para evitar mezclar interfaz, reglas de negocio y acceso a datos.

### 1. Vistas

Están en `app/views/` y se encargan solo de la interfaz:

- `main_window.py`: ventana principal, navegación, dashboard, facturas, importación y modal interno de factura.
- `login_dialog.py`: login inicial contra Supabase.
- `clientes_view.py`: vista de clientes.
- `productos_view.py`: vista de productos.

### 2. Controladores

Están en `app/controllers/` y actúan como capa de orquestación:

- `factura_controller.py`
- `cliente_controller.py`
- `producto_controller.py`

Su función es decidir cuándo leer desde Supabase, cuándo usar datos locales de respaldo y cómo aplicar reglas de negocio antes de devolver datos a la interfaz.

### 3. Servicios

Están en `app/services/` y encapsulan tareas técnicas concretas:

- `auth_service.py`: autenticación con Supabase.
- `invoice_calculator.py`: subtotal, IVA, total, cobrado y pendiente.
- `email_service.py`: envío por correo mediante SMTP.
- `pdf_service.py`: generación de PDF.
- `export_csv.py`, `export_excel.py`, `export_xml.py`: exportaciones.
- `verifactu_service.py`: integración preparada con Verifactu.
- `ocr_service.py`: extracción OCR/PDF y parser de tickets o facturas.

### 4. Modelos

Están en `app/models/` y representan las entidades del dominio:

- `factura.py`
- `cliente.py`
- `producto.py`

La lógica importante aquí es que una factura conoce su estado, sus líneas y si sigue siendo editable o no.

## Flujo de arranque

El arranque está definido en `app/main.py`.

La lógica es esta:

1. Se crea la `QApplication`.
2. Se inicializa `AuthService`.
3. Si Supabase está configurado, se abre `LoginDialog`.
4. Si el usuario no se autentica correctamente, la aplicación no entra.
5. Si el login va bien, se abre `MainWindow` con una sesión autenticada.
6. Si Supabase no está configurado, la app puede arrancar en modo local para desarrollo de interfaz.

## Cómo funciona el login

La autenticación está conectada con Supabase Auth.

El servicio `AuthService`:

- valida email y contraseña contra `supabase.auth.sign_in_with_password`
- comprueba que Supabase devuelve un usuario válido
- intenta obtener el `id_emisor` del `user_metadata`
- si no existe ahí, intenta resolverlo buscando en la tabla `emisores` por `correo_contacto`

Esto permite que la sesión no solo diga "quién eres", sino también "qué emisor te corresponde", que es lo necesario para filtrar facturas, clientes y productos del emisor correcto.

## Lógica de facturas

La lógica principal vive en `app/controllers/factura_controller.py`.

### Modos de trabajo

El controlador trabaja en dos modos:

- `Modo Supabase`: si hay cliente y `emisor_id`, lee y escribe contra las tablas reales.
- `Modo local`: si no hay Supabase configurado, usa datos de muestra para no bloquear el desarrollo de la UI.

### Tablas utilizadas

Actualmente la app está preparada para trabajar con estas tablas:

- `facturas`
- `clientesEmisor`
- `serieFacturacion`
- `emisores`

### Operaciones soportadas

El controlador ya contempla:

- listar facturas
- obtener una factura concreta
- crear factura
- editar factura
- eliminar factura
- emitir factura
- registrar cobro
- cancelar factura
- adjuntar resultado de Verifactu
- calcular filas preparadas para tablas y dashboard

### Regla de negocio importante

Una factura en borrador se puede editar.

Una factura emitida deja de ser editable.

Una factura anulada no se puede emitir.

Esto está implementado tanto a nivel de lógica como a nivel de flujo de UI.

### Estados de factura

El modelo maneja estos estados:

- `BORRADOR`
- `EMITIDA`
- `PAGADA`
- `PARCIALMENTE_PAGADA`
- `CANCELADA`

Además, el controlador traduce estados de Supabase al modelo interno para que la interfaz trabaje con una convención consistente aunque en la base se usen valores como `pendiente`, `pagada`, `parcial` o `anulada`.

## Crear una factura: cómo funciona ahora

La creación de factura ya no abre una vista nueva de navegación.

Ahora se hace mediante un modal interno superpuesto dentro de la propia ventana principal.

Esto se resuelve con:

- `InvoiceFormPanel`
- `ModalOverlay`
- `MainWindow.open_invoice_overlay()`

El flujo es:

1. El usuario pulsa `+ Nueva Factura`.
2. Se abre un modal interno sobre la misma ventana.
3. El usuario rellena datos del receptor y líneas.
4. La previsualización se recalcula en tiempo real.
5. Puede guardar como borrador o emitir.
6. Si emite, el controlador bloquea futuras ediciones.

## Cálculo de importes

La lógica de cálculo está desacoplada en `app/services/invoice_calculator.py`.

Ese servicio calcula:

- base imponible
- IVA
- total
- importe cobrado
- importe pendiente
- estado resultante según lo ya pagado

La interfaz no calcula importes por su cuenta: delega en ese servicio para evitar inconsistencias.

## Clientes y productos

Los controladores `ClienteController` y `ProductoController` están adaptados al mismo patrón:

- intentan trabajar con Supabase si existe configuración válida
- si no, ofrecen un modo de respaldo local
- devuelven datos ya preparados para que la vista no tenga que conocer detalles de la base

Esto hace que el cambio entre entorno demo y entorno real no obligue a rehacer toda la interfaz.

## PDF, correo y exportaciones

### PDF

`pdf_service.py` genera el documento de factura en PDF usando `reportlab`.

### Correo

`email_service.py` usa SMTP. La factura se puede generar y adjuntar al correo saliente desde escritorio sin depender de un servicio frontend como EmailJS. Al emitir una factura desde el modal, la app permite enviar el email automáticamente si el cliente tiene correo y SMTP está configurado.

### Exportaciones

Están separadas por formato:

- `export_csv.py`
- `export_excel.py`
- `export_xml.py`

Desde la vista de facturas se puede exportar el conjunto de filas preparadas por el controlador.

## OCR e importación

El OCR ya está integrado en el flujo de importación.

Actualmente:

- el usuario puede subir imagen o PDF
- `ocr_service.py` extrae texto de PDF con `pypdf`
- las imágenes se procesan con `pytesseract` y Tesseract OCR instalado en el sistema
- el parser detecta proveedor, NIF/CIF, dirección, fecha, líneas, IVA y total cuando aparecen en el texto
- se crea un borrador revisable y se abre el modal de edición

Esto mantiene la importación dentro del flujo normal: primero se extrae, luego se revisa y finalmente se guarda o emite.

## Verifactu

La integración está encapsulada en `verifactu_service.py`.

El comportamiento previsto es:

- validar que exista `VERIFACTI_API_KEY`
- enviar los datos de la factura
- guardar `uuid`, `url` y `qr` de respuesta

Si la clave no está configurada, el servicio falla de forma explícita para que no parezca que la integración existe cuando en realidad está incompleta.

## Variables de entorno

El archivo `.env` no se sube al repositorio.

Usa `.env.example` como plantilla.

Variables actuales:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_DEMO_EMAIL=
SUPABASE_DEMO_PASSWORD=

SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
SMTP_USE_TLS=true

VERIFACTI_API_BASE=https://api.verifacti.com
VERIFACTI_API_KEY=
```

### Qué hace cada bloque

- `SUPABASE_*`: acceso a autenticación y datos reales.
- `SMTP_*`: envío de correos desde la app de escritorio.
- `VERIFACTI_*`: integración preparada con API externa.

## Instalación

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecución

```bash
python -m app.main
```

## Tests

Los tests actuales comprueban especialmente la lógica crítica del dominio y varios servicios nuevos.

Ejecutar:

```bash
pytest -q
```

Cobertura actual relevante:

- bloqueo de edición tras emitir
- actualización de estado al registrar cobro
- generación de borrador a partir de OCR y parser de ticket/factura
- generación de PDF
- validación de configuración de Verifactu

## Estructura resumida del proyecto

```text
app/
  config.py
  main.py
  supabase_client.py
  controllers/
  models/
  services/
  views/
data/
tests/
```

## Estado actual del proyecto

Ahora mismo el proyecto ya tiene:

- arquitectura por capas
- autenticación real contra Supabase
- resolución de emisor
- gestión de facturas con reglas de negocio
- modal interno para crear o editar factura
- exportación multi-formato
- generación de PDF
- envío por SMTP y opción de email automático al emitir
- OCR integrado para PDF e imágenes
- Verifactu preparado por servicio

## Limitaciones actuales

Sigue habiendo puntos pendientes o parcialmente preparados:

- el OCR de imágenes requiere Tesseract instalado en el sistema
- Verifactu depende de credenciales reales
- algunas adaptaciones visuales todavía pueden requerir refinado
- la cobertura de tests está centrada en la lógica crítica, no en toda la UI
- la integración exacta depende del esquema real y de las políticas RLS de Supabase

## Archivos de apoyo incluidos en el repositorio

Además del código, este repositorio contiene material de apoyo generado durante el desarrollo y la preparación del TFG, como:

- guiones de presentación
- datos locales de desarrollo
- capturas de interfaz usadas como referencia visual

## Recomendación de trabajo en equipo

Para seguir evolucionando el proyecto sin romper la mantenibilidad:

- mantener la UI en `views`
- no meter lógica de negocio en los botones
- concentrar el acceso a Supabase en controladores y servicios
- añadir tests cada vez que se toque el flujo de facturas
- tratar el estado `BORRADOR -> EMITIDA -> PAGADA/CANCELADA` como la pieza más sensible del sistema
