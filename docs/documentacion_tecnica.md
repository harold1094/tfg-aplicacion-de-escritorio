# Documentación técnica

## Arquitectura

La aplicación mantiene una arquitectura por capas:

- `views`: interfaz Qt y diálogos.
- `controllers`: coordinación entre UI, persistencia y reglas de negocio.
- `services`: cálculo, analítica, OCR heurístico, anomalías, exportación, email, adjuntos, auditoría, roles y backups.
- `models`: entidades de dominio y seguridad.

El escritorio trabaja en dos modos:

1. `Supabase activo`: intenta leer/escribir en tablas y storage remotos.
2. `Modo local persistente`: usa `data/desktop_data.json` como almacén principal y mantiene adjuntos, auditoría y backups en disco.

## Estructura relevante

```text
app/
├── controllers/
├── models/
├── services/
├── views/
├── main.py
├── config.py
└── supabase_client.py
```

## Seguridad y roles

La aplicación trabaja con dos roles:

- `administrador`: gestión completa, borrado y acceso a auditoría.
- `contable`: operación diaria de facturas y envío de emails, sin mantenimiento maestro ni auditoría.

Resolución del rol:

1. Si existe Supabase y tabla `roles_usuario`, se intenta leer el rol real.
2. Si no, se usa el mapeo por `ADMIN_EMAILS` y `ACCOUNTANT_EMAILS`.
3. Si tampoco hay mapeo, el fallback local es administrador.

## Persistencia

### Local

- `LocalStore` mantiene clientes, productos, facturas y auditoría en JSON.
- `AttachmentService` copia adjuntos a `data/attachments/<invoice_id>/`.
- `BackupService` crea snapshots del almacén local y un ZIP de adjuntos.

### Supabase

La aplicación intenta sincronizar:

- `clientesEmisor`
- `facturas`
- `productos_servicios`
- `roles_usuario`

La ausencia de tablas o columnas no rompe la aplicación; se usa fallback local.

## Servicios principales

- `invoice_calculator.py`: subtotal, IVA, total, cobrado y pendiente.
- `analytics_service.py`: KPIs y evolución para dashboard.
- `forecast_service.py`: previsión ligera por media ponderada reciente.
- `classification_service.py`: sugerencias por histórico y catálogo.
- `anomaly_detection_service.py`: duplicados, importes atípicos, campos incompletos y vencimientos.
- `ocr_service.py`: extracción heurística desde nombre de archivo y contenido legible.
- `attachment_service.py`: copia local y subida opcional a Supabase Storage.
- `email_service.py`: envío SMTP o simulación controlada.
- `audit_service.py`: log de actividad de usuario.
- `backup_service.py`: copia local del modo escritorio.
- `export_csv.py`, `export_excel.py`, `export_xml.py`, `export_pdf.py`: salidas documentales.

## Interfaz Qt

Pantallas principales:

- `DashboardView`
- `ClientesView`
- `ProductosView`
- `FacturasView`
- `AuditView`

Diálogos principales:

- `LoginDialog`
- `ClienteDialog`
- `ProductoDialog`
- `FacturaDialog`
- `PaymentDialog`

Las tareas más pesadas del escritorio se ejecutan en background con `BackgroundRunner`:

- adjuntar documento
- analizar adjunto
- exportar archivos
- enviar email
- generar backup

## Limitaciones actuales

- El OCR es heurístico; no hay motor externo de reconocimiento visual completo.
- La integración con Supabase depende de que existan tablas, políticas y bucket compatibles.
- El envío de email real requiere SMTP configurado.
- No hay sincronización con web, app móvil ni 2FA.

## Validación técnica

- Suite de pruebas: `pytest -q`
- Verificación de sintaxis: `python -m compileall app tests`
