# Manual de usuario inicial

## Inicio de la aplicación

Para abrir la aplicación, ejecuta desde la carpeta principal:

```bash
python -m app.main
```

La ventana principal muestra un menú lateral con cuatro secciones:

- Dashboard
- Clientes
- Productos/Servicios
- Facturas

## Dashboard

El Dashboard muestra un resumen general:

- Total facturado.
- Facturas pendientes.
- Importe cobrado.
- Importe pendiente.
- Número de clientes.
- Número de productos o servicios.

También incluye una tabla con las facturas más recientes.

## Clientes

La pantalla de Clientes permite consultar el listado inicial y buscar por nombre o email. La creación de nuevos clientes está desactivada hasta validar el esquema real de Supabase.

## Productos y servicios

La pantalla de Productos/Servicios muestra un catálogo inicial. Con el esquema actual de Supabase, estos productos o servicios se obtienen a partir de los conceptos ya guardados en facturas, porque todavía no existe una tabla independiente de catálogo.

## Facturas

La pantalla de Facturas muestra:

- Número de factura.
- Cliente.
- Fecha.
- Estado.
- Subtotal.
- IVA.
- Total.
- Importe pendiente.
- Si la factura es editable.

Solo las facturas en estado `BORRADOR` se consideran editables. Las facturas emitidas, pagadas, parcialmente pagadas o canceladas no deben editarse directamente.

## Exportaciones

Desde la pantalla de Facturas se puede exportar el listado actual a:

- CSV
- Excel
- XML

Al pulsar el botón de exportación, selecciona la ubicación y el nombre del archivo.

## Configuración de Supabase

Para conectar con Supabase, rellena el archivo `.env`:

```env
SUPABASE_URL=
SUPABASE_KEY=
```

Si no se configuran estas variables, la aplicación usa datos de prueba.

No introduzcas claves reales en capturas, documentos compartidos o mensajes públicos. Si una clave se comparte por error, debe regenerarse desde Supabase.
