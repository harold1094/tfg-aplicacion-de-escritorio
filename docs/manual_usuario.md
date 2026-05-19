# Manual de usuario

## Inicio de la aplicación

Ejecuta:

```bash
python -m app.main
```

Si Supabase está configurado, el login intentará autenticar contra Supabase Auth. Si no lo está, la aplicación permite acceso local para seguir trabajando en modo escritorio.

## Roles

- `administrador`: puede gestionar clientes, productos, facturas, backups y auditoría.
- `contable`: puede trabajar con facturas y envíos, pero no modificar maestros ni ver auditoría.

## Menú principal

La aplicación puede mostrar estas secciones:

- Dashboard
- Clientes
- Productos/Servicios
- Facturas
- Actividad

La sección `Actividad` puede ocultarse según el rol.

## Dashboard

Muestra:

- total facturado
- importe cobrado
- importe pendiente
- facturas pendientes
- facturas vencidas
- número de clientes
- número de productos/servicios
- previsión del siguiente mes
- evolución mensual

## Clientes

Permite:

- buscar clientes
- crear cliente
- editar cliente
- eliminar cliente

Estas acciones dependen del rol.

## Productos y servicios

Permite:

- consultar catálogo
- crear producto o servicio
- editarlo
- eliminarlo

Estas acciones dependen del rol.

## Facturas

Desde esta vista puedes:

- crear facturas
- editar borradores
- eliminar borradores si tu rol lo permite
- registrar cobros parciales
- adjuntar PDF o imagen
- analizar el último adjunto
- exportar a CSV, Excel, XML o PDF
- enviar la factura por email
- generar backup local

Solo las facturas en estado `BORRADOR` son editables o eliminables.

## Adjuntos y análisis

Al adjuntar un documento, la aplicación:

1. guarda una copia local
2. intenta subirla a Supabase Storage si está disponible
3. permite lanzar un análisis heurístico para sugerir proveedor, número, fecha e importe

## Email

Si SMTP está configurado, el envío será real. Si no, la aplicación simula el envío y lo notifica en pantalla.

## Datos locales

La aplicación usa estas rutas:

- `data/desktop_data.json`
- `data/attachments/`
- `data/backups/`

## Recomendación

Si trabajas en modo local y después migras a Supabase, valida primero nombres de tablas, bucket de storage y políticas antes de asumir sincronización completa.
