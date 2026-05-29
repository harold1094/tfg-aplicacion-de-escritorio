"""Ventana principal estilo Automalize para escritorio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, Qt, QThread, QTimer, QUrl
from PySide6.QtCore import Signal as QtSignal
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.controllers.cliente_controller import ClienteController
from app.controllers.factura_controller import FacturaController
from app.controllers.producto_controller import ProductoController
from app.models.factura import EstadoFactura, Factura, LineaFactura
from app.services.auth_service import AuthSession
from app.services.email_service import EmailService
from app.services.export_csv import export_rows_to_csv
from app.services.export_excel import export_rows_to_excel
from app.services.export_xml import export_rows_to_xml
from app.services.invoice_calculator import calculate_invoice
from app.services.ocr_service import OcrService
from app.services.pdf_service import generate_invoice_pdf
from app.services.verifactu_service import VerifactuService
from app.views.clientes_view import ClientesView
from app.views.productos_view import ProductosView


# ============================================================
# OCR Worker — runs in background thread so UI stays alive
# ============================================================
class OcrWorker(QThread):
    finished: QtSignal = QtSignal(object)  # emits OcrDraft
    error: QtSignal = QtSignal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:  # noqa: D401
        try:
            draft = OcrService().prepare_import(self.path)
            self.finished.emit(draft)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class DropZoneFrame(QFrame):
    fileDropped = QtSignal(str)

    def __init__(self, source_type: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.source_type = source_type
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                ext = Path(path).suffix.lower()
                if self.source_type == "PDF" and ext == ".pdf":
                    event.acceptProposedAction()
                    self.setProperty("dragOver", True)
                    self.style().unpolish(self)
                    self.style().polish(self)
                elif self.source_type == "Ticket" and ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                    event.acceptProposedAction()
                    self.setProperty("dragOver", True)
                    self.style().unpolish(self)
                    self.style().polish(self)

    def dragLeaveEvent(self, event) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event) -> None:
        self.setProperty("dragOver", False)
        self.style().unpolish(self)
        self.style().polish(self)
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                self.fileDropped.emit(path)
                event.acceptProposedAction()


def _money(value: Decimal | int | float | str) -> str:
    return f"{Decimal(str(value)):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class StatCard(QFrame):
    def __init__(self, icon: str, title: str, value: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("statCard")
        icon_label = QLabel(icon)
        icon_label.setObjectName(f"statIcon_{accent}")
        value_label = QLabel(value)
        value_label.setObjectName("statValue")
        title_label = QLabel(title)
        title_label.setObjectName("statTitle")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(icon_label)
        text = QVBoxLayout()
        text.addWidget(title_label)
        text.addWidget(value_label)
        layout.addLayout(text, 1)


class QuickActionCard(QFrame):
    def __init__(self, icon: str, title: str, subtitle: str, accent: str, slot: Callable[[], None]) -> None:
        super().__init__()
        self.setObjectName("quickActionCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.slot = slot

        icon_label = QLabel(icon)
        icon_label.setObjectName(f"quickIcon_{accent}")
        title_label = QLabel(title)
        title_label.setObjectName("quickTitle")
        title_label.setWordWrap(True)
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("quickSubtitle")
        subtitle_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.slot()
        super().mousePressEvent(event)


class InvoiceFormPanel(QFrame):
    # Tipos de IVA — igual que IVA_RATES en constants.js de la referencia
    IVA_RATES = [
        ("21% (General)", 21),
        ("10% (Reducido)", 10),
        ("4% (Super reducido)", 4),
        ("0% (Exento)", 0),
    ]
    # Plantillas PDF — igual que PDF_TEMPLATES en constants.js
    PDF_TEMPLATES = [
        ("classic",  "Clásica",       "Formal y corporativa",       "📄"),
        ("modern",   "Moderna",        "Diseño actual con colores",  "🎨"),
        ("minimal",  "Minimalista",    "Limpia y sencilla",           "✨"),
    ]

    def __init__(
        self,
        parent: QWidget,
        controller: FacturaController,
        on_close: Callable[[], None],
        on_saved: Callable[[], None],
        email_service: EmailService | None = None,
        factura: Factura | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.on_close = on_close
        self.on_saved = on_saved
        self.email_service = email_service
        self.factura = factura
        self.setObjectName("invoiceModalCard")
        self.setMinimumSize(900, 680)
        self.setMaximumWidth(1320)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(20)

        form_scroll = QScrollArea()
        form_scroll.setObjectName("invoiceFormScroll")
        form_scroll.setWidgetResizable(True)
        form_scroll.setFrameShape(QFrame.Shape.NoFrame)

        form_panel = QWidget()
        form_panel.setObjectName("invoiceFormBody")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(0, 0, 10, 0)
        form_layout.setSpacing(18)
        form_scroll.setWidget(form_panel)

        # ── Encabezado ──────────────────────────────────────────────────────────
        heading_row = QHBoxLayout()
        title = QLabel("Editar factura" if factura else "Nueva factura")
        title.setObjectName("dialogTitle")
        subtitle = QLabel("Completa los datos del receptor y revisa el resumen antes de emitir.")
        subtitle.setObjectName("viewSubtitle")
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("ghostButton")
        close_btn.clicked.connect(self.close_panel)
        title_block = QVBoxLayout()
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        heading_row.addLayout(title_block)
        heading_row.addStretch(1)
        heading_row.addWidget(close_btn)
        form_layout.addLayout(heading_row)

        # ── Datos de la Factura ─────────────────────────────────────────────────
        details_card = QFrame()
        details_card.setObjectName("panel")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(20, 20, 20, 20)
        details_layout.setSpacing(16)
        details_title = QLabel("📋  Datos de la Factura")
        details_title.setObjectName("sectionTitle")
        details_layout.addWidget(details_title)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setDate(QDate(factura.fecha if factura else date.today()))
        self.type_input = QComboBox()
        self.type_input.addItems(["Factura", "Factura simplificada", "Factura rectificativa"])

        document_form = QFormLayout()
        document_form.setSpacing(12)
        document_form.setHorizontalSpacing(18)
        document_form.addRow("Fecha de emisión", self.date_input)
        document_form.addRow("Tipo", self.type_input)
        details_layout.addLayout(document_form)
        form_layout.addWidget(details_card)

        # ── Datos del Receptor ───────────────────────────────────────────────────
        receptor_card = QFrame()
        receptor_card.setObjectName("panel")
        receptor_layout = QVBoxLayout(receptor_card)
        receptor_layout.setContentsMargins(20, 20, 20, 20)
        receptor_layout.setSpacing(14)
        receptor_title = QLabel("👤  Datos del Receptor")
        receptor_title.setObjectName("sectionTitle")
        receptor_layout.addWidget(receptor_title)

        # Selector de cliente existente (igual que cliente-select en create-invoice.js)
        self._clientes_cache: list[dict] = []
        self.cliente_combo = QComboBox()
        self.cliente_combo.addItem("-- Introducir manualmente --", None)
        self._load_clientes_into_combo()
        receptor_layout.addWidget(QLabel("Seleccionar Cliente Existente"))
        receptor_layout.addWidget(self.cliente_combo)

        self.client_input = QLineEdit(factura.cliente_nombre if factura else "")
        self.client_input.setPlaceholderText("Cliente S.A.")
        self.nif_input = QLineEdit(factura.cliente_nif if factura else "")
        self.nif_input.setPlaceholderText("NIF / CIF")
        self.address_input = QLineEdit(factura.cliente_direccion if factura else "")
        self.address_input.setPlaceholderText("Dirección")
        self.email_input = QLineEdit(factura.cliente_email if factura else "")
        self.email_input.setPlaceholderText("correo@cliente.es")

        client_form = QFormLayout()
        client_form.setSpacing(12)
        client_form.setHorizontalSpacing(18)
        client_form.addRow("Nombre / razón social", self.client_input)
        client_form.addRow("NIF / CIF", self.nif_input)
        client_form.addRow("Dirección", self.address_input)
        client_form.addRow("Email", self.email_input)
        receptor_layout.addLayout(client_form)
        form_layout.addWidget(receptor_card)
        self.cliente_combo.currentIndexChanged.connect(self._on_cliente_selected)

        # ── Líneas de Factura ──────────────────────────────────────────────────────
        lines_card = QFrame()
        lines_card.setObjectName("panel")
        lines_layout = QVBoxLayout(lines_card)
        lines_layout.setContentsMargins(20, 20, 20, 20)
        lines_layout.setSpacing(14)
        lines_label = QLabel("📦  Líneas de Factura")
        lines_label.setObjectName("sectionTitle")
        lines_layout.addWidget(lines_label)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setHorizontalHeaderLabels(["Descripción", "Cantidad", "Precio", "IVA %", "Subtotal"])
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lines_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setMinimumHeight(220)
        self.lines_table.setAlternatingRowColors(True)
        lines_layout.addWidget(self.lines_table)

        line_actions = QHBoxLayout()
        add_line = QPushButton("+ Añadir línea")
        add_line.setObjectName("ghostButton")
        add_line.clicked.connect(lambda: self.add_line())
        remove_line = QPushButton("Eliminar línea")
        remove_line.setObjectName("ghostButton")
        remove_line.clicked.connect(self.remove_selected_line)
        line_actions.addWidget(add_line)
        line_actions.addWidget(remove_line)
        line_actions.addStretch(1)
        lines_layout.addLayout(line_actions)
        form_layout.addWidget(lines_card)

        # ── Plantilla PDF ──────────────────────────────────────────────────────────
        # Cargar plantilla guardada de QSettings si existe para esta factura (equivalente a localStorage de la web)
        self._selected_template = "classic"
        if factura:
            from PySide6.QtCore import QSettings
            qsettings = QSettings("Automalize", "DesktopApp")
            self._selected_template = qsettings.value(f"invoice_template_{factura.id}", "classic")

        self._template_buttons: dict[str, QPushButton] = {}
        template_card = QFrame()
        template_card.setObjectName("panel")
        template_layout = QVBoxLayout(template_card)
        template_layout.setContentsMargins(20, 20, 20, 20)
        template_layout.setSpacing(14)
        template_title = QLabel("🎨  Plantilla PDF")
        template_title.setObjectName("sectionTitle")
        template_layout.addWidget(template_title)
        template_sub = QLabel("Elige el estilo visual del PDF generado.")
        template_sub.setObjectName("viewSubtitle")
        template_layout.addWidget(template_sub)
        templates_row = QHBoxLayout()
        templates_row.setSpacing(10)
        for tmpl_id, tmpl_name, tmpl_desc, tmpl_icon in self.PDF_TEMPLATES:
            is_sel = tmpl_id == self._selected_template
            btn = QPushButton(f"{tmpl_icon}\n{tmpl_name}\n{tmpl_desc}")
            btn.setCheckable(True)
            btn.setChecked(is_sel)
            btn.setMinimumSize(130, 90)
            btn.setStyleSheet(
                f"QPushButton {{ background: {'#ece9ff' if is_sel else '#ffffff'}; "
                f"border: {'2px solid #5a50ee' if is_sel else '1px solid #e2e5f1'}; "
                "border-radius: 8px; padding: 10px 8px; font-size: 12px; "
                "color: #181a2f; text-align: center; white-space: pre; }}"
                "QPushButton:hover { background: #f0efff; border: 1px solid #bfc5ff; }"
            )
            btn.clicked.connect(lambda checked=False, tid=tmpl_id: self._select_template(tid))
            self._template_buttons[tmpl_id] = btn
            templates_row.addWidget(btn)
        templates_row.addStretch(1)
        template_layout.addLayout(templates_row)
        form_layout.addWidget(template_card)

        # ── Notas ─────────────────────────────────────────────────────────────────
        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Notas adicionales...")
        self.notes_input.setMinimumHeight(90)
        self.notes_input.setMaximumHeight(130)
        if factura:
            self.notes_input.setPlainText(factura.notes if hasattr(factura, 'notes') else factura.notas)
        notes_card = QFrame()
        notes_card.setObjectName("panel")
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(20, 20, 20, 20)
        notes_layout.setSpacing(12)
        notes_title = QLabel("📝  Notas")
        notes_title.setObjectName("sectionTitle")
        notes_layout.addWidget(notes_title)
        notes_layout.addWidget(self.notes_input)
        form_layout.addWidget(notes_card)

        # ── Opciones al emitir ──────────────────────────────────────────────────
        emit_opts_card = QFrame()
        emit_opts_card.setObjectName("panel")
        emit_opts_layout = QVBoxLayout(emit_opts_card)
        emit_opts_layout.setContentsMargins(20, 20, 20, 20)
        emit_opts_layout.setSpacing(12)
        emit_opts_title = QLabel("📤  Opciones al emitir")
        emit_opts_title.setObjectName("sectionTitle")
        emit_opts_layout.addWidget(emit_opts_title)

        self.verifactu_check = QCheckBox("Enviar a Verifactu (AEAT)")
        self.verifactu_check.setChecked(True)
        vf_sub = QLabel("Registra la factura en la Agencia Tributaria al emitir.")
        vf_sub.setObjectName("viewSubtitle")
        vf_sub.setWordWrap(True)
        self.vf_box = QFrame()
        self.vf_box.setObjectName("vf_box")
        self.vf_box.setStyleSheet("QFrame#vf_box { border: 2px solid #5a50ee; border-radius: 8px; background-color: #f4f3ff; }")
        vf_inner = QVBoxLayout(self.vf_box)
        vf_inner.setContentsMargins(12, 10, 12, 10)
        vf_inner.setSpacing(4)
        vf_row = QHBoxLayout()
        vf_row.addWidget(self.verifactu_check)
        vf_row.addStretch(1)
        vf_inner.addLayout(vf_row)
        vf_inner.addWidget(vf_sub)
        emit_opts_layout.addWidget(self.vf_box)

        self.auto_email_check = QCheckBox("Enviar email al cliente")
        em_sub = QLabel("Envía la factura por email al emitir.")
        em_sub.setObjectName("viewSubtitle")
        em_sub.setWordWrap(True)
        self.em_box = QFrame()
        self.em_box.setObjectName("em_box")
        self.em_box.setStyleSheet("QFrame#em_box { border: 1px solid #e2e5f1; border-radius: 8px; background: #fff; }")
        em_inner = QVBoxLayout(self.em_box)
        em_inner.setContentsMargins(12, 10, 12, 10)
        em_inner.setSpacing(6)
        em_row = QHBoxLayout()
        em_row.addWidget(self.auto_email_check)
        em_row.addStretch(1)
        em_inner.addLayout(em_row)
        em_inner.addWidget(em_sub)

        # Campo dinámico para introducir/editar el correo del cliente
        self.auto_email_input = QLineEdit()
        self.auto_email_input.setPlaceholderText("Introduce el email de envío (ej: correo@cliente.com)...")
        self.auto_email_input.setObjectName("dynamicEmailInput")
        self.auto_email_input.setStyleSheet(
            "QLineEdit#dynamicEmailInput { padding: 8px; border: 1px solid #c5c9f0; "
            "border-radius: 6px; background-color: #ffffff; color: #181a2f; }"
        )
        self.auto_email_input.setVisible(False)
        em_inner.addWidget(self.auto_email_input)
        
        emit_opts_layout.addWidget(self.em_box)
        form_layout.addWidget(emit_opts_card)

        # Conectar los estados de los checkboxes
        self.verifactu_check.toggled.connect(self._on_verifactu_toggled)
        self.auto_email_check.toggled.connect(self._on_email_toggled)
        self.auto_email_input.textChanged.connect(self.update_preview)

        # Permitir alternar los checkboxes haciendo clic en cualquier parte de la tarjeta
        def on_vf_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                self.verifactu_check.toggle()
        self.vf_box.mousePressEvent = on_vf_click
        self.vf_box.setCursor(Qt.CursorShape.PointingHandCursor)

        # Al hacer clic en la tarjeta del email, se alterna el checkbox, excepto si se hace clic sobre el campo de texto.
        def on_em_click(event):
            if event.button() == Qt.MouseButton.LeftButton:
                pos = event.position().toPoint()
                child = self.em_box.childAt(pos)
                if child is not self.auto_email_input:
                    self.auto_email_check.toggle()
        self.em_box.mousePressEvent = on_em_click
        self.em_box.setCursor(Qt.CursorShape.PointingHandCursor)

        # ── Botones de acción ─────────────────────────────────────────────────────
        actions = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghostButton")
        cancel.clicked.connect(self.close_panel)
        save_btn = QPushButton("Guardar borrador")
        save_btn.setObjectName("warningButton")
        save_btn.clicked.connect(self.save)
        emit_btn = QPushButton("Emitir factura")
        emit_btn.setObjectName("accentButton")
        emit_btn.clicked.connect(lambda: self.save(emit=True))
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(save_btn)
        actions.addWidget(emit_btn)
        form_layout.addLayout(actions)
        form_layout.addStretch(1)

        # ── Vista previa ───────────────────────────────────────────────────────────
        preview_panel = QFrame()
        preview_panel.setObjectName("invoicePreview")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(24, 24, 24, 24)
        preview_layout.setSpacing(14)
        preview_header = QLabel("👁  Vista previa")
        preview_header.setObjectName("sectionTitle")
        preview_layout.addWidget(preview_header)
        self.preview = QTextBrowser()
        self.preview.setObjectName("previewText")
        self.preview.setFrameShape(QFrame.Shape.NoFrame)
        self.preview.setStyleSheet(
            "QTextBrowser { background-color: #ffffff; border: 1.5px solid #e2e5f1; "
            "border-radius: 8px; padding: 16px; }"
        )
        preview_layout.addWidget(self.preview)
        preview_layout.addStretch(1)

        root.addWidget(form_scroll, 3)
        root.addWidget(preview_panel, 2)

        if factura:
            for linea in factura.lineas:
                self.add_line(linea)
        else:
            self.add_line()

        self.client_input.textChanged.connect(self.update_preview)
        self.nif_input.textChanged.connect(self.update_preview)
        self.email_input.textChanged.connect(self.update_preview)
        self.email_input.textChanged.connect(self.update_auto_email_state)
        self.address_input.textChanged.connect(self.update_preview)
        self.notes_input.textChanged.connect(self.update_preview)
        self.date_input.dateChanged.connect(self.update_preview)
        self.lines_table.itemChanged.connect(self.update_preview)
        self.update_auto_email_state()
        self.update_preview()

    def _on_verifactu_toggled(self, checked: bool) -> None:
        if checked:
            self.vf_box.setStyleSheet("QFrame#vf_box { border: 2px solid #5a50ee; border-radius: 8px; background-color: #f4f3ff; }")
        else:
            self.vf_box.setStyleSheet("QFrame#vf_box { border: 1px solid #e2e5f1; border-radius: 8px; background-color: #ffffff; }")
        self.vf_box.style().unpolish(self.vf_box)
        self.vf_box.style().polish(self.vf_box)
        self.vf_box.update()
        self.update_preview()

    def _on_email_toggled(self, checked: bool) -> None:
        self.auto_email_input.setVisible(checked)
        if checked:
            self.em_box.setStyleSheet("QFrame#em_box { border: 2px solid #5a50ee; border-radius: 8px; background-color: #f4f3ff; }")
            if not self.auto_email_input.text().strip() and self.email_input.text().strip():
                self.auto_email_input.setText(self.email_input.text().strip())
        else:
            self.em_box.setStyleSheet("QFrame#em_box { border: 1px solid #e2e5f1; border-radius: 8px; background-color: #ffffff; }")
        self.em_box.style().unpolish(self.em_box)
        self.em_box.style().polish(self.em_box)
        self.em_box.update()
        self.update_preview()

    # ── Selector de plantilla ──────────────────────────────────────────────────
    def _select_template(self, template_id: str) -> None:
        self._selected_template = template_id
        for tid, btn in self._template_buttons.items():
            is_sel = tid == template_id
            btn.setChecked(is_sel)
            btn.setStyleSheet(
                f"QPushButton {{ background: {'#ece9ff' if is_sel else '#ffffff'}; "
                f"border: {'2px solid #5a50ee' if is_sel else '1px solid #e2e5f1'}; "
                "border-radius: 8px; padding: 10px 8px; font-size: 12px; "
                "color: #181a2f; text-align: center; white-space: pre; }}"
                "QPushButton:hover { background: #f0efff; border: 1px solid #bfc5ff; }"
            )
        self.update_preview()

    # ── Selector de cliente existente ─────────────────────────────────────────
    def _load_clientes_into_combo(self) -> None:
        try:
            if not hasattr(self.controller, 'supabase') or self.controller.supabase is None:
                return
            # Cargamos de la tabla de clientes de supabase (clientesEmisor)
            resp = self.controller.supabase.table("clientesEmisor").select(
                "id,nombre,cif_nif_nie,direccion_completa,correo_electronico"
            ).order("nombre").execute()
            self._clientes_cache = resp.data or []
            for row in self._clientes_cache:
                nombre = str(row.get("nombre") or "").strip()
                if not nombre or nombre == "null":
                    continue
                nif = row.get("cif_nif_nie") or ""
                label = f"{nombre} - {nif}" if nif else nombre
                self.cliente_combo.addItem(label, row)
        except Exception:
            pass

    def _on_cliente_selected(self, index: int) -> None:
        data = self.cliente_combo.itemData(index)
        if not data:
            return
        self.client_input.setText(str(data.get("nombre") or ""))
        self.nif_input.setText(str(data.get("cif_nif_nie") or ""))
        self.address_input.setText(str(data.get("direccion_completa") or ""))
        self.email_input.setText(str(data.get("correo_electronico") or ""))
        self.update_preview()

    # ── Activar/desactivar el email de forma inteligente ─────────────────────
    def update_auto_email_state(self) -> None:
        # Habilitamos siempre la casilla para que el usuario pueda activarla y rellenar el correo manualmente.
        self.auto_email_check.setEnabled(True)
        self.auto_email_check.setToolTip("Envía la factura por email al cliente al emitir.")
        
        # Sincronización proactiva: si ya está marcado y el campo está vacío, copiamos el correo principal del receptor
        if self.auto_email_check.isChecked() and not self.auto_email_input.text().strip():
            self.auto_email_input.setText(self.email_input.text().strip())

    # ── Gestión de líneas ─────────────────────────────────────────────────────
    def add_line(self, line: LineaFactura | None = None) -> None:
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)
        # Descripción
        self.lines_table.setItem(row, 0, QTableWidgetItem(line.descripcion if line else ""))
        # Cantidad
        self.lines_table.setItem(row, 1, QTableWidgetItem(str(line.cantidad if line else 1)))
        # Precio
        self.lines_table.setItem(row, 2, QTableWidgetItem(str(line.precio_unitario if line else "0.00")))
        # IVA — QComboBox con 4 tipos
        iva_combo = QComboBox()
        for lbl, val in self.IVA_RATES:
            iva_combo.addItem(lbl, val)
        current_iva = 21
        if line:
            current_iva = int(float(line.iva * 100) if line.iva <= 1 else float(line.iva))
        for i in range(iva_combo.count()):
            if iva_combo.itemData(i) == current_iva:
                iva_combo.setCurrentIndex(i)
                break
        iva_combo.currentIndexChanged.connect(self.update_preview)
        self.lines_table.setCellWidget(row, 3, iva_combo)
        # Subtotal (no editable)
        item_sub = QTableWidgetItem("")
        item_sub.setFlags(item_sub.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.lines_table.setItem(row, 4, item_sub)
        self.update_preview()

    def remove_selected_line(self) -> None:
        selected_rows = sorted({index.row() for index in self.lines_table.selectedIndexes()}, reverse=True)
        if not selected_rows and self.lines_table.rowCount():
            selected_rows = [self.lines_table.rowCount() - 1]
        for row in selected_rows:
            self.lines_table.removeRow(row)
        if self.lines_table.rowCount() == 0:
            self.add_line()
            return
        self.update_preview()

    def read_lines(self) -> list[LineaFactura]:
        # 1. Sincronizar de forma proactiva el editor de celda activo para evitar pérdidas por retraso del event loop de Qt
        editors = self.lines_table.findChildren(QLineEdit)
        for editor in editors:
            if editor.isVisible():
                r = self.lines_table.currentRow()
                c = self.lines_table.currentColumn()
                if r >= 0 and c >= 0:
                    item = self.lines_table.item(r, c)
                    if item:
                        item.setText(editor.text())

        # 2. Forzar el foco fuera de la tabla para cerrar formalmente el editor
        self.client_input.setFocus()
        self.lines_table.setCurrentCell(-1, -1)
        
        lines: list[LineaFactura] = []
        for row in range(self.lines_table.rowCount()):
            item_desc = self.lines_table.item(row, 0)
            desc = (item_desc.text().strip() if item_desc else "").strip()
            
            # Si la descripción está vacía, ignoramos la línea de forma limpia
            if not desc:
                continue
                
            # Leer cantidad con un fallback seguro a 1
            item_qty = self.lines_table.item(row, 1)
            qty_text = item_qty.text().strip() if item_qty else ""
            try:
                # Soporte para comas de decimales comunes en España
                qty_text = qty_text.replace(",", ".")
                qty = Decimal(qty_text if qty_text else "1")
            except Exception:
                qty = Decimal("1")
                
            # Leer precio con un fallback seguro a 0.00
            item_price = self.lines_table.item(row, 2)
            price_text = item_price.text().strip() if item_price else ""
            try:
                price_text = price_text.replace(",", ".")
                price = Decimal(price_text if price_text else "0.00")
            except Exception:
                price = Decimal("0.00")
                
            # Leer IVA
            iva_widget = self.lines_table.cellWidget(row, 3)
            if isinstance(iva_widget, QComboBox):
                iva = Decimal(str(iva_widget.currentData() or 21)) / Decimal("100")
            else:
                iva_item = self.lines_table.item(row, 3)
                iva_text = iva_item.text().strip() if iva_item else ""
                try:
                    iva_text = iva_text.replace(",", ".").replace("%", "")
                    iva = Decimal(iva_text if iva_text else "21") / Decimal("100")
                except Exception:
                    iva = Decimal("0.21")
                    
            lines.append(LineaFactura(desc, qty, price, iva))
        return lines

    def update_preview(self) -> None:
        try:
            lines = self.read_lines()
        except Exception:
            return
        totals = calculate_invoice(lines)
        self.lines_table.blockSignals(True)
        for row in range(self.lines_table.rowCount()):
            item = self.lines_table.item(row, 4)
            if item:
                subtotal = (
                    _money(lines[row].cantidad * lines[row].precio_unitario)
                    if row < len(lines)
                    else _money("0.00")
                )
                item.setText(subtotal)
        self.lines_table.blockSignals(False)
        
        # Obtener emisor dinámico para la vista previa
        em_details = self.controller.get_emisor_details()
        em_nombre = em_details.get("nombre") or "Mi Empresa S.L."
        em_nif = em_details.get("cif_nif") or "B12345678"
        em_dir = em_details.get("direccion_fiscal") or "Calle Principal 1"
        em_cp = em_details.get("codigo_postal") or "28001"
        em_ciudad = em_details.get("ciudad") or "Madrid"
        em_correo = em_details.get("correo_contacto") or "contacto@miempresa.es"

        # Generar tabla HTML de artículos
        table_rows_html = ""
        for line in lines:
            iva_pct = float(line.iva * 100) if line.iva <= 1 else float(line.iva)
            table_rows_html += f"""
            <tr>
                <td style="padding: 6px 0; border-bottom: 1px solid #eee;">{line.descripcion}</td>
                <td style="padding: 6px 0; text-align: center; border-bottom: 1px solid #eee;">{line.cantidad}</td>
                <td style="padding: 6px 0; text-align: right; border-bottom: 1px solid #eee;">{_money(line.precio_unitario)}</td>
                <td style="padding: 6px 0; text-align: center; border-bottom: 1px solid #eee;">{iva_pct:.0f}%</td>
                <td style="padding: 6px 0; text-align: right; border-bottom: 1px solid #eee;">{_money(line.cantidad * line.precio_unitario)}</td>
            </tr>
            """
        if not table_rows_html:
            table_rows_html = "<tr><td colspan='5' style='text-align: center; color: #999; padding: 12px;'>Añade líneas a la factura</td></tr>"

        notas = self.notes_input.toPlainText().strip()
        notas_html = f"<div style='margin-top: 14px; padding: 8px; background: #fafafa; border-left: 3px solid #ccc; font-style: italic;'><b>Notas:</b><br/>{notas}</div>" if notas else ""

        # Renderizar en función de la plantilla
        template = self._selected_template
        num_factura = self.factura.numero if self.factura else "BOR-XXXX"

        # Checkboxes indicados en la vista previa
        vf_active = "Sí (AEAT Verifactu)" if self.verifactu_check.isChecked() else "No"
        em_target = self.auto_email_input.text().strip() or self.email_input.text().strip() or 'cliente'
        em_active = f"Sí (enviar a {em_target})" if self.auto_email_check.isChecked() else "No"

        # Determinar badge de estado y color para paridad total con el PDF clásico
        estado_val = self.factura.estado.value.upper() if self.factura else 'BORRADOR'
        is_emitted = (self.factura.estado != EstadoFactura.BORRADOR) if self.factura else False
        badge_bg = "#09a06b" if is_emitted else "#d48c00"

        if template == "modern":
            html = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #181a2f; padding: 0; background-color: #ffffff; border: 1px solid #e2e5f1; border-radius: 8px;">
                <!-- Barra de estado decorativa -->
                <div style="background-color: #24083a; height: 10px; border-radius: 6px 6px 0 0;"></div>
                <!-- Cabecera moderna morada -->
                <div style="background-color: #582ec2; color: white; padding: 18px 20px;">
                    <table width="100%" cellspacing="0" cellpadding="0" style="color: white; border: none;">
                        <tr>
                            <td><b style="font-size: 20px; letter-spacing: 0.5px;">FACTURA</b></td>
                            <td style="text-align: right;"><b style="font-size: 14px;">{num_factura}</b></td>
                        </tr>
                        <tr>
                            <td></td>
                            <td style="text-align: right; font-size: 10px; opacity: 0.8; padding-top: 4px;">Fecha: {self.date_input.date().toPython().strftime('%d/%m/%Y')}</td>
                        </tr>
                    </table>
                </div>
                <!-- Línea de acento lila claro -->
                <div style="background-color: #af8afe; height: 3px;"></div>

                <div style="padding: 16px;">
                    <!-- Cards Emisor / Receptor en columnas side-by-side -->
                    <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 18px; border: none;">
                        <tr>
                            <td width="48%" valign="top" style="background-color: #f6f5ff; border: 1px solid #e8e6ff; border-radius: 6px; padding: 12px;">
                                <b style="color: #582ec2; font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px;">DE EMISOR</b>
                                <div style="font-size: 13px; font-weight: bold; color: #181a2f; margin-top: 4px;">{em_nombre}</div>
                                <div style="font-size: 10px; color: #5d617d; margin-top: 4px;"><b>NIF:</b> {em_nif}</div>
                                <div style="font-size: 10px; color: #5d617d;"><b>Dir:</b> {em_dir}</div>
                                <div style="font-size: 10px; color: #5d617d;"><b>Email:</b> {em_correo}</div>
                            </td>
                            <td width="4%"></td>
                            <td width="48%" valign="top" style="background-color: #f5fcf8; border: 1px solid #dcf3e7; border-radius: 6px; padding: 12px;">
                                <b style="color: #069c6e; font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px;">PARA RECEPTOR</b>
                                <div style="font-size: 13px; font-weight: bold; color: #181a2f; margin-top: 4px;">{self.client_input.text() or 'Receptor'}</div>
                                <div style="font-size: 10px; color: #5d617d; margin-top: 4px;"><b>NIF:</b> {self.nif_input.text() or '-'}</div>
                                <div style="font-size: 10px; color: #5d617d;"><b>Dir:</b> {self.address_input.text() or '-'}</div>
                                <div style="font-size: 10px; color: #5d617d;"><b>Email:</b> {self.email_input.text() or '-'}</div>
                            </td>
                        </tr>
                    </table>

                    <!-- Tabla de artículos -->
                    <table width="100%" cellspacing="0" cellpadding="0" style="font-size: 11px; margin-bottom: 18px; border-collapse: collapse;">
                        <thead>
                            <tr style="background-color: #6366f1; color: white;">
                                <th align="left" style="padding: 6px 8px; border-radius: 4px 0 0 4px;">Concepto</th>
                                <th align="center" style="padding: 6px 8px; width: 40px;">Uds.</th>
                                <th align="right" style="padding: 6px 8px; width: 75px;">Precio</th>
                                <th align="center" style="padding: 6px 8px; width: 40px;">IVA</th>
                                <th align="right" style="padding: 6px 8px; width: 80px; border-radius: 0 4px 4px 0;">Importe</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>

                    <!-- Totales modernos en caja morada -->
                    <div style="background-color: #582ec2; border-radius: 8px; padding: 12px; color: white; width: 45%; margin-left: 55%;">
                        <table width="100%" cellspacing="0" cellpadding="0" style="font-size: 11px; color: #e8dbff;">
                            <tr>
                                <td>Base Imponible:</td>
                                <td align="right" style="color: white;">{_money(totals.subtotal)}</td>
                            </tr>
                            <tr>
                                <td style="padding-top: 4px;">IVA:</td>
                                <td align="right" style="color: white; padding-top: 4px;">{_money(totals.iva)}</td>
                            </tr>
                            <tr style="font-weight: bold; font-size: 13px; color: white;">
                                <td style="padding-top: 8px; border-top: 1px solid #7d5cd7;">TOTAL:</td>
                                <td align="right" style="padding-top: 8px; border-top: 1px solid #7d5cd7;">{_money(totals.total)}</td>
                            </tr>
                        </table>
                    </div>

                    <div style="font-size: 8px; color: #747894; margin-top: 18px; border-top: 1px dashed #ddd; padding-top: 6px;">
                        <b>AEAT Registro:</b> {vf_active} | <b>Email automático:</b> {em_active}
                    </div>
                    {notas_html}
                </div>
            </div>
            """
        elif template == "minimal":
            html = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; color: #222; padding: 18px; background-color: #ffffff; border: 1px solid #e2e5f1; border-radius: 8px;">
                <!-- Título minimalista -->
                <table width="100%" cellspacing="0" cellpadding="0" style="border-bottom: 2px solid #222; padding-bottom: 8px; margin-bottom: 18px;">
                    <tr>
                        <td><span style="font-size: 22px; font-weight: bold; letter-spacing: 0.5px; color: #111;">Factura</span></td>
                        <td align="right" style="font-size: 11px; color: #555;">Nº {num_factura}</td>
                    </tr>
                </table>

                <table width="100%" cellspacing="0" cellpadding="0" style="font-size: 11px; margin-bottom: 18px; line-height: 1.4; border: none;">
                    <tr>
                        <td width="48%" valign="top">
                            <b style="color: #666; font-size: 9px;">EMISOR</b><br/>
                            <div style="font-weight: bold; font-size: 12px; color: #222; margin-top: 3px;">{em_nombre}</div>
                            <div style="color: #555; margin-top: 2px;">NIF: {em_nif}</div>
                            <div style="color: #555;">{em_dir}</div>
                            <div style="color: #555;">{em_cp} {em_ciudad}</div>
                        </td>
                        <td width="4%"></td>
                        <td width="48%" align="right" valign="top">
                            <b style="color: #666; font-size: 9px;">RECEPTOR</b><br/>
                            <div style="font-weight: bold; font-size: 12px; color: #222; margin-top: 3px;">{self.client_input.text() or 'Receptor'}</div>
                            <div style="color: #555; margin-top: 2px;">NIF: {self.nif_input.text() or '—'}</div>
                            <div style="color: #555;">{self.address_input.text() or '—'}</div>
                            <div style="color: #555;">{self.email_input.text() or '—'}</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding-top: 8px;"><b>Fecha:</b> {self.date_input.date().toPython().strftime('%d/%m/%Y')}</td>
                        <td align="right" style="padding-top: 8px;"><b>AEAT:</b> {vf_active}</td>
                    </tr>
                </table>

                <table width="100%" cellspacing="0" cellpadding="0" style="font-size: 11px; margin-bottom: 18px; border-top: 1px solid #111; border-bottom: 1px solid #111; border-collapse: collapse;">
                    <thead>
                        <tr style="font-weight: bold; background-color: #fcfcfc;">
                            <th align="left" style="padding: 6px 8px; border-bottom: 1px solid #ccc;">DESCRIPCIÓN</th>
                            <th align="center" style="padding: 6px 8px; width: 40px; border-bottom: 1px solid #ccc;">CANT</th>
                            <th align="right" style="padding: 6px 8px; width: 75px; border-bottom: 1px solid #ccc;">PRECIO</th>
                            <th align="center" style="padding: 6px 8px; width: 40px; border-bottom: 1px solid #ccc;">IVA</th>
                            <th align="right" style="padding: 6px 8px; width: 80px; border-bottom: 1px solid #ccc;">TOTAL</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows_html}
                    </tbody>
                </table>

                <table width="45%" cellspacing="0" cellpadding="0" align="right" style="font-size: 11px; line-height: 1.5;">
                    <tr>
                        <td style="color: #666;">Subtotal:</td>
                        <td align="right" style="color: #222;">{_money(totals.subtotal)}</td>
                    </tr>
                    <tr>
                        <td style="color: #666;">IVA:</td>
                        <td align="right" style="color: #222;">{_money(totals.iva)}</td>
                    </tr>
                    <tr style="font-weight: bold; font-size: 12px;">
                        <td style="padding-top: 5px; border-top: 1px dashed #111;">Total:</td>
                        <td align="right" style="padding-top: 5px; border-top: 1px dashed #111;">{_money(totals.total)}</td>
                    </tr>
                </table>
                <div style="clear: both;"></div>

                <div style="font-size: 8px; color: #777; margin-top: 18px; border-top: 1px solid #eee; padding-top: 6px;">
                    AEAT: {vf_active} | Email Automático: {em_active}
                </div>
                {notas_html}
            </div>
            """
        else:  # classic (Clásica)
            html = f"""
            <div style="font-family: Arial, Helvetica, sans-serif; color: #2c3e50; padding: 0; background-color: #ffffff; border: 1px solid #e2e5f1; border-radius: 8px;">
                <!-- Cabecera clásica Navy Blue -->
                <div style="background-color: #1b2a5a; color: white; padding: 20px; border-radius: 6px 6px 0 0;">
                    <table width="100%" cellspacing="0" cellpadding="0" style="color: white; border: none;">
                        <tr>
                            <td><b style="font-size: 22px; font-weight: bold; letter-spacing: 1px;">FACTURA</b></td>
                            <td style="text-align: right;"><b style="font-size: 14px;">{num_factura}</b></td>
                        </tr>
                        <tr>
                            <td></td>
                            <td style="text-align: right; font-size: 10px; opacity: 0.8; padding-top: 4px;">Fecha: {self.date_input.date().toPython().strftime('%d/%m/%Y')}</td>
                        </tr>
                    </table>
                </div>
                <!-- Línea de acento dorada -->
                <div style="background-color: #d4af37; height: 4px;"></div>

                <div style="padding: 16px;">
                    <!-- Badge de Estado que coincide exactamente con el del PDF -->
                    <div style="display: inline-block; background-color: {badge_bg}; color: white; padding: 4px 12px; border-radius: 4px; font-weight: bold; font-size: 10px; margin-bottom: 12px; text-transform: uppercase;">
                        {estado_val}
                    </div>

                    <!-- Emisor / Receptor en columnas side-by-side -->
                    <table width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 18px; border: none; font-size: 11px;">
                        <tr>
                            <td width="48%" valign="top">
                                <b style="color: #1b2a5a; font-size: 9px; letter-spacing: 0.5px;">EMISOR</b><br/>
                                <div style="font-weight: bold; font-size: 12px; color: #1b2a5a; margin-top: 3px;">{em_nombre}</div>
                                <div style="color: #555; margin-top: 2px;">NIF: {em_nif}</div>
                                <div style="color: #555;">{em_dir}</div>
                                <div style="color: #555;">{em_cp} {em_ciudad}</div>
                                <div style="color: #555;">{em_correo}</div>
                            </td>
                            <td width="4%"></td>
                            <td width="48%" valign="top">
                                <b style="color: #1b2a5a; font-size: 9px; letter-spacing: 0.5px;">RECEPTOR</b><br/>
                                <div style="font-weight: bold; font-size: 12px; color: #1b2a5a; margin-top: 3px;">{self.client_input.text() or 'Receptor'}</div>
                                <div style="color: #555; margin-top: 2px;">NIF: {self.nif_input.text() or '—'}</div>
                                <div style="color: #555;">{self.address_input.text() or '—'}</div>
                                <div style="color: #555;">{self.email_input.text() or '—'}</div>
                            </td>
                        </tr>
                    </table>

                    <table width="100%" cellspacing="0" cellpadding="0" style="font-size: 11px; margin-bottom: 18px; border-collapse: collapse;">
                        <thead>
                            <tr style="background-color: #1b2a5a; color: white;">
                                <th align="left" style="padding: 6px 8px;">Concepto</th>
                                <th align="center" style="padding: 6px 8px; width: 60px;">Cantidad</th>
                                <th align="right" style="padding: 6px 8px; width: 80px;">Precio Unit.</th>
                                <th align="center" style="padding: 6px 8px; width: 40px;">IVA</th>
                                <th align="right" style="padding: 6px 8px; width: 80px;">Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows_html}
                        </tbody>
                    </table>

                    <table width="45%" cellspacing="0" cellpadding="0" align="right" style="font-size: 11px; margin-top: 10px;">
                        <tr>
                            <td style="padding: 3px 0; color: #7f8c8d;">Base Imponible:</td>
                            <td align="right" style="color: #2c3e50;">{_money(totals.subtotal)}</td>
                        </tr>
                        <tr>
                            <td style="padding: 3px 0; color: #7f8c8d;">Impuestos (IVA):</td>
                            <td align="right" style="color: #2c3e50;">{_money(totals.iva)}</td>
                        </tr>
                        <tr style="font-weight: bold; color: #1b2a5a; font-size: 12px;">
                            <td style="padding-top: 6px; border-top: 1px solid #1b2a5a;">TOTAL:</td>
                            <td align="right" style="padding-top: 6px; border-top: 1px solid #1b2a5a;">{_money(totals.total)}</td>
                        </tr>
                    </table>
                    <div style="clear: both;"></div>

                    <div style="font-size: 8px; color: #7f8c8d; margin-top: 18px; border-top: 1px solid #eee; padding-top: 6px;">
                        <b>Registro AEAT (Verifactu):</b> {vf_active} | <b>Envío automático:</b> {em_active}
                    </div>
                    {notas_html}
                </div>
            </div>
            """

        self.preview.setHtml(html)

    def save(self, emit: bool = False) -> None:
        if not self.client_input.text().strip():
            QMessageBox.warning(self, "Faltan datos", "El nombre del receptor es obligatorio.")
            return
        try:
            lines = self.read_lines()
        except Exception as exc:
            QMessageBox.warning(self, "Líneas no válidas", f"Revisa cantidades, precios e IVA.\n{exc}")
            return
        if not lines:
            QMessageBox.warning(self, "Faltan líneas", "Añade al menos una línea válida.")
            return
        fecha = self.date_input.date().toPython()
        use_verifactu = emit and self.verifactu_check.isChecked()
        try:
            if self.factura:
                saved = self.controller.update_factura(
                    self.factura.id,
                    self.client_input.text().strip(),
                    fecha,
                    lines,
                    cliente_email=self.email_input.text().strip(),
                    cliente_nif=self.nif_input.text().strip(),
                    cliente_direccion=self.address_input.text().strip(),
                    notas=self.notes_input.toPlainText().strip(),
                )
            else:
                saved = self.controller.create_factura(
                    self.client_input.text().strip(),
                    fecha,
                    lines,
                    cliente_email=self.email_input.text().strip(),
                    cliente_nif=self.nif_input.text().strip(),
                    cliente_direccion=self.address_input.text().strip(),
                    notas=self.notes_input.toPlainText().strip(),
                )
            if emit:
                saved = self.controller.emit_factura(saved.id, use_verifactu=use_verifactu)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return

        # Guardar en local storage (QSettings) para paridad total con localStorage de la web de referencia
        from PySide6.QtCore import QSettings
        qsettings = QSettings("Automalize", "DesktopApp")
        qsettings.setValue(f"invoice_template_{saved.id}", self._selected_template)

        if emit:
            try:
                emisor_details = self.controller.get_emisor_details()
                pdf_path = generate_invoice_pdf(
                    saved,
                    Path.cwd() / "exports" / "pdf",
                    template=self._selected_template,
                    emisor_details=emisor_details,
                )
            except Exception:
                pdf_path = None
            if self.auto_email_check.isChecked():
                dest_email = self.auto_email_input.text().strip() or saved.cliente_email
                if not dest_email:
                    QMessageBox.warning(self, "Email no enviado", "No se especificó ninguna dirección de correo para enviar la factura.")
                elif self.email_service is not None and self.email_service.is_configured():
                    try:
                        if pdf_path:
                            saved.cliente_email = dest_email
                            self.email_service.send_invoice(saved, pdf_path)
                    except Exception as exc:
                        QMessageBox.warning(
                            self, "Factura emitida",
                            f"La factura se emitió, pero no se pudo enviar el email real:\n{exc}",
                        )
                    else:
                        QMessageBox.information(
                            self, "Email enviado", f"Factura enviada a {dest_email}.",
                        )
                else:
                    # SIMULACIÓN DE ENVÍO DE EMAIL PARA DESARROLLO / TFG
                    QMessageBox.information(
                        self, "📧 Email Enviado (Simulación TFG)",
                        f"¡Envío simulado correctamente!\nSe habría enviado la factura PDF (Estilo: {self._selected_template.upper()}) al correo del cliente: {dest_email}.\n\n(Configura las variables SMTP en tu .env para envíos reales).",
                    )
            vf_msg = " y registrada en la AEAT (Verifactu)" if use_verifactu else ""
            QMessageBox.information(
                self, "✅ Factura emitida",
                f"Factura emitida{vf_msg}.\nPDF generado ({self._selected_template.upper()}): {pdf_path or 'no disponible'}",
            )
        self.on_saved()
        self.close_panel()

    def close_panel(self) -> None:
        self.on_close()


class ModalOverlay(QFrame):
    def __init__(self, parent: QWidget, panel: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("modalOverlay")
        self.panel = panel
        self.panel.setParent(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.panel, 0, Qt.AlignmentFlag.AlignCenter)
        row.addStretch(1)
        layout.addLayout(row)
        layout.addStretch(1)


class VoiceRedirectPanel(QFrame):
    BOT_URL = "https://t.me/facturacionAutomaticaBot"

    def __init__(self, on_close: Callable[[], None], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.on_close = on_close
        self.setObjectName("voiceRedirectCard")
        self.setMinimumWidth(460)
        self.setMaximumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(18)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Cerrar")
        close_button.setObjectName("ghostButton")
        close_button.clicked.connect(self.on_close)
        close_row.addWidget(close_button)
        layout.addLayout(close_row)

        orb = QLabel("◉")
        orb.setObjectName("voiceRedirectOrb")
        orb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(orb, 0, Qt.AlignmentFlag.AlignHCenter)

        title = QLabel("Factura por voz")
        title.setObjectName("voiceRedirectTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel("Te llevamos a Telegram para grabarla.")
        subtitle.setObjectName("voiceRedirectSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        handle = QLabel("@facturacionAutomaticaBot")
        handle.setObjectName("voiceRedirectHandle")
        handle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(handle)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        back = QPushButton("Quedarme aqui")
        back.setObjectName("ghostButton")
        back.clicked.connect(self.on_close)
        open_bot = QPushButton("Ir a Telegram")
        open_bot.setObjectName("primaryButton")
        open_bot.clicked.connect(self.open_bot)
        actions.addWidget(back)
        actions.addWidget(open_bot)
        layout.addLayout(actions)

    def open_bot(self) -> None:
        QDesktopServices.openUrl(QUrl(self.BOT_URL))
        self.on_close()


class InvoiceDetailDialog(QDialog):
    def __init__(self, parent: QWidget, factura: Factura, controller: FacturaController) -> None:
        super().__init__(parent)
        self.factura = factura
        self.controller = controller
        self.action_to_take = None
        
        self.setWindowTitle(f"Detalle de Factura - {factura.numero}")
        self.resize(720, 640)
        self.setMinimumSize(660, 560)
        
        self.setStyleSheet("""
            QDialog {
                background-color: #f4f5fb;
            }
            QLabel#dialogHeaderTitle {
                font-size: 20px;
                font-weight: 800;
                color: #181a2f;
            }
            QLabel#dialogHeaderSub {
                font-size: 13px;
                color: #747894;
            }
            QFrame#detailPanel {
                background-color: #ffffff;
                border: 1px solid #e2e5f1;
                border-radius: 12px;
            }
            QLabel#sectionTitle {
                font-size: 14px;
                font-weight: 800;
                color: #181a2f;
                margin-top: 10px;
            }
            QLabel#detailLabel {
                font-size: 10px;
                font-weight: 700;
                color: #747894;
            }
            QLabel#detailValue {
                font-size: 13px;
                font-weight: 600;
                color: #181a2f;
            }
            QLabel#statusBadge_borrador {
                background-color: #fff2d4;
                color: #d28a00;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel#statusBadge_emitida {
                background-color: #ddf8ef;
                color: #168a68;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            QLabel#statusBadge_anulada {
                background-color: #fff5f7;
                color: #df3d56;
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 800;
            }
            QTableWidget#linesTable {
                background-color: #ffffff;
                border: 1px solid #e2e5f1;
                border-radius: 8px;
                gridline-color: #edf0f7;
            }
            QHeaderView::section {
                background-color: #fafbff;
                color: #747894;
                font-weight: 800;
                border: none;
                border-bottom: 1px solid #e2e5f1;
                font-size: 11px;
                padding: 6px;
            }
            QFrame#totalsBox {
                background-color: #f8f9ff;
                border: 1px solid #e2e5f1;
                border-radius: 8px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(14)
        
        # ── Cabecera ──
        header_row = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        
        title_lbl = QLabel(f"Factura {factura.numero}", self)
        title_lbl.setObjectName("dialogHeaderTitle")
        
        sub_lbl = QLabel(f"Visualización detallada y operaciones de la factura", self)
        sub_lbl.setObjectName("dialogHeaderSub")
        
        header_text.addWidget(title_lbl)
        header_text.addWidget(sub_lbl)
        header_row.addLayout(header_text)
        header_row.addStretch(1)
        
        # Badge de estado
        state_str = factura.estado.value.upper()
        badge_lbl = QLabel(state_str, self)
        if "BORRADOR" in state_str:
            badge_lbl.setObjectName("statusBadge_borrador")
        elif "CANCELADA" in state_str or "ANULADA" in state_str:
            badge_lbl.setObjectName("statusBadge_anulada")
        else:
            badge_lbl.setObjectName("statusBadge_emitida")
        badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_row.addWidget(badge_lbl)
        main_layout.addLayout(header_row)
        
        # ── Panel de Datos (Emisor / Receptor) ──
        data_panel = QFrame(self)
        data_panel.setObjectName("detailPanel")
        panel_layout = QGridLayout(data_panel)
        panel_layout.setContentsMargins(16, 16, 16, 16)
        panel_layout.setHorizontalSpacing(24)
        panel_layout.setVerticalSpacing(10)
        
        # Columna Emisor
        emisor_details = controller.get_emisor_details()
        self._add_field(panel_layout, 0, 0, "EMISOR", emisor_details.get("nombre", "Mi Empresa S.L."))
        self._add_field(panel_layout, 1, 0, "NIF EMISOR", emisor_details.get("cif_nif", "B12345678"))
        self._add_field(panel_layout, 2, 0, "FECHA EMISIÓN", factura.fecha.strftime("%d/%m/%Y"))
        
        # Columna Receptor
        self._add_field(panel_layout, 0, 1, "RECEPTOR", factura.cliente_nombre or "—")
        self._add_field(panel_layout, 1, 1, "NIF RECEPTOR", factura.cliente_nif or "—")
        self._add_field(panel_layout, 2, 1, "EMAIL CLIENTE", factura.cliente_email or "—")
        
        main_layout.addWidget(data_panel)
        
        # ── Tabla de Líneas de Factura ──
        table_lbl = QLabel("ARTÍCULOS / SERVICIOS", self)
        table_lbl.setObjectName("sectionTitle")
        main_layout.addWidget(table_lbl)
        
        self.lines_table = QTableWidget(len(factura.lineas), 4, self)
        self.lines_table.setObjectName("linesTable")
        self.lines_table.setHorizontalHeaderLabels(["Descripción", "Cant.", "Precio Unit.", "Subtotal"])
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setShowGrid(False)
        self.lines_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lines_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.lines_table.setMinimumHeight(140)
        self.lines_table.setAlternatingRowColors(True)
        
        for idx, line in enumerate(factura.lineas):
            self.lines_table.setItem(idx, 0, QTableWidgetItem(line.descripcion))
            qty_item = QTableWidgetItem(str(line.cantidad))
            qty_item.setTextAlignment(int(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter))
            self.lines_table.setItem(idx, 1, qty_item)
            
            price_item = QTableWidgetItem(_money(line.precio_unitario))
            price_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self.lines_table.setItem(idx, 2, price_item)
            
            sub = line.cantidad * line.precio_unitario
            sub_item = QTableWidgetItem(_money(sub))
            sub_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
            self.lines_table.setItem(idx, 3, sub_item)
            self.lines_table.setRowHeight(idx, 32)
            
        main_layout.addWidget(self.lines_table)
        
        # ── Bloque de Totales ──
        totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
        totals_row = QHBoxLayout()
        totals_row.addStretch(1)
        
        totals_box = QFrame(self)
        totals_box.setObjectName("totalsBox")
        totals_layout = QGridLayout(totals_box)
        totals_layout.setContentsMargins(14, 8, 14, 8)
        totals_layout.setHorizontalSpacing(20)
        totals_layout.setVerticalSpacing(4)
        
        def _add_total(row: int, label: str, value: str, bold: bool = False):
            lbl = QLabel(label, self)
            lbl.setStyleSheet(f"font-size: 11px; color: {'#181a2f' if bold else '#747894'}; font-weight: {'bold' if bold else 'normal'};")
            val = QLabel(value, self)
            val.setStyleSheet(f"font-size: {'13px' if bold else '11px'}; color: {'#5a50ee' if bold else '#181a2f'}; font-weight: bold;")
            totals_layout.addWidget(lbl, row, 0)
            totals_layout.addWidget(val, row, 1, Qt.AlignmentFlag.AlignRight)
            
        _add_total(0, "Base Imponible", _money(totals.subtotal))
        _add_total(1, "IVA", _money(totals.iva))
        _add_total(2, "TOTAL FACTURA", _money(totals.total), bold=True)
        
        totals_row.addWidget(totals_box)
        main_layout.addLayout(totals_row)
        
        # Divider sutil
        div = QFrame(self)
        div.setObjectName("themeDivider")
        main_layout.addWidget(div)
        
        # ── Botones de Acciones ──
        actions_grid = QGridLayout()
        actions_grid.setSpacing(6)
        
        btn_edit = QPushButton("✏️ Editar", self)
        btn_edit.setObjectName("warningButton")
        btn_edit.clicked.connect(lambda: self._set_action("edit"))
        
        btn_emit = QPushButton("📤 Emitir", self)
        btn_emit.setObjectName("accentButton")
        btn_emit.clicked.connect(lambda: self._set_action("emit"))
        
        btn_pay = QPushButton("💳 Registrar Cobro", self)
        btn_pay.setObjectName("ghostButton")
        btn_pay.clicked.connect(lambda: self._set_action("pay"))
        
        btn_email = QPushButton("📧 Enviar Email", self)
        btn_email.setObjectName("ghostButton")
        btn_email.clicked.connect(lambda: self._set_action("email"))
        
        btn_verifactu = QPushButton("🏛️ Verifactu", self)
        btn_verifactu.setObjectName("ghostButton")
        btn_verifactu.clicked.connect(lambda: self._set_action("verifactu"))
        
        btn_pdf = QPushButton("📄 Descargar PDF", self)
        btn_pdf.setObjectName("primaryButton")
        btn_pdf.clicked.connect(lambda: self._set_action("pdf"))
        
        btn_cancel = QPushButton("🚫 Anular", self)
        btn_cancel.setObjectName("dangerButton")
        btn_cancel.clicked.connect(lambda: self._set_action("cancel"))
        
        btn_delete = QPushButton("🗑️ Eliminar", self)
        btn_delete.setObjectName("dangerButton")
        btn_delete.clicked.connect(lambda: self._set_action("delete"))
        
        btn_close = QPushButton("Cerrar", self)
        btn_close.setObjectName("ghostButton")
        btn_close.clicked.connect(self.reject)
        
        # Visibilidad inteligente basada en estado
        is_borrador = "BORRADOR" in state_str
        is_anulada = "CANCELADA" in state_str or "ANULADA" in state_str
        
        btn_edit.setVisible(is_borrador)
        btn_emit.setVisible(is_borrador)
        btn_pay.setVisible(not is_borrador and not is_anulada)
        btn_email.setVisible(not is_borrador)
        btn_verifactu.setVisible(not is_borrador)
        btn_cancel.setVisible(not is_borrador and not is_anulada)
        btn_delete.setVisible(is_borrador)
        
        # Organizar botones en rejilla responsiva
        actions_grid.addWidget(btn_pdf, 0, 0)
        actions_grid.addWidget(btn_email, 0, 1)
        actions_grid.addWidget(btn_verifactu, 0, 2)
        
        actions_grid.addWidget(btn_edit, 1, 0)
        if is_borrador:
            actions_grid.addWidget(btn_emit, 1, 1)
        else:
            actions_grid.addWidget(btn_pay, 1, 1)
        actions_grid.addWidget(btn_cancel, 1, 2)
        
        actions_grid.addWidget(btn_delete, 2, 0)
        actions_grid.addWidget(btn_close, 2, 2)
        
        main_layout.addLayout(actions_grid)
        
    def _add_field(self, layout: QGridLayout, row: int, col: int, label: str, value: str):
        cell_layout = QVBoxLayout()
        cell_layout.setSpacing(2)
        
        lbl = QLabel(label, self)
        lbl.setObjectName("detailLabel")
        val = QLabel(value, self)
        val.setObjectName("detailValue")
        val.setWordWrap(True)
        
        cell_layout.addWidget(lbl)
        cell_layout.addWidget(val)
        layout.addLayout(cell_layout, row, col)
        
    def _set_action(self, action: str):
        self.action_to_take = action
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, session: AuthSession | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Automalize - Escritorio")
        self.resize(1320, 820)
        self.setMinimumSize(1100, 680)
        self.session = session

        emisor_id = session.emisor_id if session else ""
        self.cliente_controller = ClienteController(emisor_id=emisor_id)
        self.producto_controller = ProductoController(emisor_id=emisor_id)
        self.factura_controller = FacturaController(emisor_id=emisor_id)
        self.email_service = EmailService()
        self.verifactu_service = VerifactuService()
        self.ocr_service = OcrService()
        self.current_filter = "Todas"
        self.current_search = ""
        self.invoice_overlay: ModalOverlay | None = None
        self.voice_overlay: ModalOverlay | None = None
        self.last_persistent_nav_row = 0
        self.sidebar_collapsed = False
        self.sidebar_width_expanded = 244
        self.selected_theme_accent = "Indigo"
        self.theme_dark_mode = False

        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(self.sidebar_width_expanded)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(14, 18, 14, 14)
        side_layout.setSpacing(12)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        avatar = QLabel("A")
        avatar.setObjectName("brandAvatar")
        self.logo = QLabel("Automalize")
        self.logo.setObjectName("logo")
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand_text.addWidget(self.logo)
        self.context_label = QLabel("Escritorio profesional")
        self.context_label.setObjectName("sidebarSummary")
        brand_text.addWidget(self.context_label)
        brand.addWidget(avatar)
        brand.addLayout(brand_text, 1)
        side_layout.addLayout(brand)

        self.sidebar_search = QLineEdit()
        self.sidebar_search.setObjectName("sidebarSearch")
        self.sidebar_search.setPlaceholderText("Buscar todo...")
        self.sidebar_search.textChanged.connect(self.on_global_search)
        side_layout.addWidget(self.sidebar_search)
        self.primary_section = self._side_label("Principal")
        side_layout.addWidget(self.primary_section)

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.routes = [
            ("⌂  Dashboard", "DB", self.show_dashboard),
            ("▤  Facturas", "FC", self.show_invoices),
            ("↑  Importar Factura", "IM", self.show_import),
            ("◌  Factura por Voz", "VZ", self.show_voice),
            ("♧  Clientes", "CL", lambda: self.set_static_page(5, "Clientes")),
            ("◇  Productos", "PR", lambda: self.set_static_page(6, "Productos")),
        ]
        for label, _compact, _handler in self.routes:
            self.navigation.addItem(QListWidgetItem(label))
        self.navigation.currentRowChanged.connect(self.handle_nav)
        side_layout.addWidget(self.navigation, 1)
        self.system_section = self._side_label("Sistema")
        side_layout.addWidget(self.system_section)
        self.theme_button = QPushButton("☼  Tema visual")
        self.theme_button.setObjectName("sideButton")
        self.theme_button.clicked.connect(self.show_theme_visual)
        side_layout.addWidget(self.theme_button)
        self.user_card = QFrame()
        self.user_card.setObjectName("userCard")
        user_layout = QVBoxLayout(self.user_card)
        user_layout.setContentsMargins(16, 16, 16, 16)
        user_layout.setSpacing(4)
        self.user_name = QLabel("MR   Admin")
        self.user_name.setObjectName("userCardTitle")
        self.user_email = QLabel(session.email if session else "Sin Supabase")
        self.user_email.setObjectName("userCardText")
        user_layout.addWidget(self.user_name)
        user_layout.addWidget(self.user_email)
        side_layout.addWidget(self.user_card)

        content = QFrame()
        self.content_frame = content
        content.setObjectName("content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.navbar_title = QLabel("Dashboard")
        self.navbar_title.setObjectName("navbarTitle")
        navbar = QFrame()
        navbar.setObjectName("navbar")
        nav_layout = QHBoxLayout(navbar)
        nav_layout.setContentsMargins(24, 0, 20, 0)
        self.navbar_menu_button = QPushButton("☰")
        self.navbar_menu_button.setObjectName("navToggleButton")
        self.navbar_menu_button.clicked.connect(self.toggle_sidebar)
        nav_layout.addWidget(self.navbar_menu_button)
        nav_layout.addWidget(self.navbar_title)
        nav_layout.addStretch(1)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Buscar facturas, clientes...")
        self.global_search.setObjectName("pillSearch")
        self.global_search.textChanged.connect(self.on_global_search)
        nav_layout.addWidget(self.global_search)
        for text, name in [("?", "topIconButton"), ("☾", "topIconButton")]:
            button = QPushButton(text)
            button.setObjectName(name)
            nav_layout.addWidget(button)
        top_new = QPushButton("+ Nueva factura")
        top_new.setObjectName("primaryButton")
        top_new.clicked.connect(self.new_invoice)
        nav_layout.addWidget(top_new)

        self.stack = QStackedWidget()
        self.dashboard_page = self._scroll_page()
        self.invoices_page = self._scroll_page()
        self.import_page = self._scroll_page()
        self.voice_page = self._scroll_page()
        self.theme_page = self._scroll_page()
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.invoices_page)
        self.stack.addWidget(self.import_page)
        self.stack.addWidget(self.voice_page)
        self.stack.addWidget(self.theme_page)
        self.stack.addWidget(ClientesView(self.cliente_controller))
        self.stack.addWidget(ProductosView(self.producto_controller))

        content_layout.addWidget(navbar)
        content_layout.addWidget(self.stack, 1)
        shell.addWidget(self.sidebar)
        shell.addWidget(content, 1)
        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLESHEET)

        self.navigation.setCurrentRow(0)
        self._apply_sidebar_state()

    def _scroll_page(self) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("page")
        QVBoxLayout(body).setContentsMargins(18, 18, 18, 18)
        area.setWidget(body)
        return area

    def _placeholder(self, title: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        label = QLabel(title)
        label.setObjectName("viewTitle")
        layout.addWidget(label)
        return widget

    def _side_label(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setObjectName("sideSection")
        return label

    def handle_nav(self, row: int) -> None:
        if row < 0:
            return
        if row == 3:
            self.show_voice()
            self.navigation.blockSignals(True)
            self.navigation.setCurrentRow(self.last_persistent_nav_row)
            self.navigation.blockSignals(False)
            return
        self.last_persistent_nav_row = row
        self.routes[row][2]()

    def on_global_search(self, text: str) -> None:
        self.current_search = text
        if self.stack.currentWidget() is self.invoices_page:
            self.render_invoices()

    def set_static_page(self, index: int, title: str) -> None:
        self.navbar_title.setText(title)
        self.stack.setCurrentIndex(index)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.invoice_overlay is not None:
            self.invoice_overlay.setGeometry(self.content_frame.rect())
        if self.voice_overlay is not None:
            self.voice_overlay.setGeometry(self.content_frame.rect())

    def clear_page(self, area: QScrollArea) -> QVBoxLayout:
        body = area.widget()
        old = body.layout()
        while old.count():
            item = old.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
        return old

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def page_header(self, layout: QVBoxLayout, title: str, subtitle: str, actions: list[QPushButton] | None = None) -> None:
        row = QHBoxLayout()
        text = QVBoxLayout()
        text.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("viewTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("viewSubtitle")
        sub.setWordWrap(True)
        text.addWidget(heading)
        text.addWidget(sub)
        row.addLayout(text, 1)
        for action in actions or []:
            row.addWidget(action)
        layout.addLayout(row)

    def section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionTitle")
        return label

    def show_theme_visual(self) -> None:
        self.navbar_title.setText("Tema visual")
        self.stack.setCurrentWidget(self.theme_page)
        layout = self.clear_page(self.theme_page)
        self.page_header(layout, "Tema visual", "Elige el color y el modo del escritorio. Los cambios se aplican en directo.")

        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(20, 20, 20, 20)
        panel_layout.setSpacing(18)

        accent_title = QLabel("Acento de la marca")
        accent_title.setObjectName("sectionTitle")
        panel_layout.addWidget(accent_title)

        accents = QHBoxLayout()
        accents.setSpacing(10)
        for name, color in [
            ("Indigo", "#6256f4"),
            ("Esmeralda", "#1ea97c"),
            ("Ambar", "#e4a014"),
            ("Coral", "#e65c74"),
            ("Cielo", "#3c8dde"),
            ("Grafito", "#5d6284"),
        ]:
            button = QPushButton(name + (" (default)" if name == "Indigo" else ""))
            button.setMinimumSize(168, 98)
            button.setCheckable(True)
            button.setChecked(name == self.selected_theme_accent)
            button.setObjectName("themeAccentButton")
            button.clicked.connect(lambda checked=False, selected=name: self.select_theme_accent(selected))
            button.setStyleSheet(
                "QPushButton {"
                f"border: 1px solid {'#6256f4' if name == self.selected_theme_accent else '#e2e5f1'};"
                "border-radius: 8px; padding: 54px 12px 12px 12px; text-align: left; font-weight: 700;"
                "background: #ffffff; color: #181a2f;"
                "}"
                f"QPushButton {{ background-image: none; }}"
            )
            swatch = QLabel(button)
            swatch.setGeometry(12, 12, 144, 52)
            swatch.setStyleSheet(f"background: {color}; border-radius: 8px;")
            accents.addWidget(button)
        panel_layout.addLayout(accents)

        divider = QFrame()
        divider.setObjectName("themeDivider")
        panel_layout.addWidget(divider)

        dark_row = QHBoxLayout()
        dark_text = QVBoxLayout()
        dark_title = QLabel("Modo oscuro")
        dark_title.setObjectName("sectionTitle")
        dark_subtitle = QLabel("Sigue el modo del sistema. Si lo activas, todo el escritorio cambia a oscuro.")
        dark_subtitle.setObjectName("viewSubtitle")
        dark_subtitle.setWordWrap(True)
        dark_text.addWidget(dark_title)
        dark_text.addWidget(dark_subtitle)
        dark_toggle = QCheckBox()
        dark_toggle.setObjectName("themeDarkToggle")
        dark_toggle.setChecked(self.theme_dark_mode)
        dark_toggle.toggled.connect(self.set_theme_dark_mode)
        dark_row.addLayout(dark_text, 1)
        dark_row.addWidget(dark_toggle, 0, Qt.AlignmentFlag.AlignVCenter)
        panel_layout.addLayout(dark_row)

        layout.addWidget(panel)
        layout.addStretch(1)

    def select_theme_accent(self, accent: str) -> None:
        self.selected_theme_accent = accent
        self.show_theme_visual()

    def set_theme_dark_mode(self, enabled: bool) -> None:
        self.theme_dark_mode = enabled
        self.show_theme_visual()

    def toggle_sidebar(self) -> None:
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._apply_sidebar_state()

    def _apply_sidebar_state(self) -> None:
        collapsed = self.sidebar_collapsed
        self.sidebar.setVisible(not collapsed)
        self.sidebar.setFixedWidth(self.sidebar_width_expanded)
        self.logo.setText("Automalize")
        self.logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.context_label.setVisible(True)
        self.primary_section.setVisible(True)
        self.system_section.setVisible(True)
        self.user_card.setVisible(True)
        self.theme_button.setText("☼  Tema visual")
        self.navbar_menu_button.setText("☰")

        for index, (label, _compact_label, _handler) in enumerate(self.routes):
            item = self.navigation.item(index)
            item.setText(label)
            item.setTextAlignment(int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter))
        self.navigation.setSpacing(4)

    def show_dashboard(self) -> None:
        self.navbar_title.setText("Dashboard")
        self.stack.setCurrentWidget(self.dashboard_page)
        layout = self.clear_page(self.dashboard_page)
        new_btn = QPushButton("+ Nueva Factura")
        new_btn.setObjectName("primaryButton")
        new_btn.clicked.connect(self.new_invoice)
        import_btn = QPushButton("Importar")
        import_btn.setObjectName("ghostButton")
        import_btn.clicked.connect(self.show_import)

        rows = self.factura_controller.list_invoice_rows()
        issued = [r for r in rows if r["estado"] != EstadoFactura.BORRADOR.value]
        cash_flow = sum((Decimal(str(r["total"])) for r in issued), Decimal("0"))
        drafts = [r for r in rows if r["estado"] == EstadoFactura.BORRADOR.value]
        pending = sum((Decimal(str(r["total"])) for r in drafts), Decimal("0"))
        clients = {r["cliente"] for r in rows}
        avg = cash_flow / max(len(clients), 1)
        projected = cash_flow / Decimal(max(len(rows), 1)) * Decimal("1.15")

        user_name = "Martin"
        if self.session and self.session.email:
            user_name = self.session.email.split("@")[0].split(".")[0].title()
        self.page_header(
            layout,
            f"Buenas tardes, {user_name}",
            f"Resumen de tu actividad. Tienes {len(issued)} facturas emitidas y {len(drafts)} borradores pendientes de revision.",
            [import_btn, new_btn],
        )

        grid = QGridLayout()
        grid.setSpacing(12)
        cards = [
            ("EUR", "Flujo de caja (emitido)", _money(cash_flow), "purple"),
            ("BRR", "Borradores pendientes", _money(pending), "yellow"),
            ("AVG", "Media por cliente", _money(avg), "blue"),
            ("PRX", "Proyeccion prox. mes", _money(projected), "green"),
        ]
        for i, card in enumerate(cards):
            grid.addWidget(StatCard(*card), i // 4, i % 4)
        layout.addLayout(grid)

        middle = QHBoxLayout()
        middle.setSpacing(14)
        chart = QFrame()
        chart.setObjectName("panel")
        chart_layout = QVBoxLayout(chart)
        chart_layout.setContentsMargins(18, 18, 18, 18)
        chart_layout.addWidget(self.section_label("Facturacion ultimos 7 meses"))
        chart_layout.addWidget(QLabel("Total emitido por mes en euros"))
        bars = QHBoxLayout()
        bars.setSpacing(14)
        sample = [1200, 2100, 1800, 2900, 2200, 3580, int(projected)]
        months = ["Dic", "Ene", "Feb", "Mar", "Abr", "May", "Jun"]
        max_value = max(sample) or 1
        for month, value in zip(months, sample):
            column = QVBoxLayout()
            column.addStretch(1)
            value_label = QLabel(str(value))
            value_label.setObjectName("barValue")
            value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            bar = QFrame()
            bar.setObjectName("chartBarStrong" if month == "May" else "chartBar")
            bar.setFixedHeight(max(34, int(170 * value / max_value)))
            bar.setMinimumWidth(54)
            month_label = QLabel(month)
            month_label.setObjectName("barMonth")
            month_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            column.addWidget(value_label)
            column.addWidget(bar)
            column.addWidget(month_label)
            bars.addLayout(column)
        chart_layout.addLayout(bars)

        activity = QFrame()
        activity.setObjectName("panel")
        activity_layout = QVBoxLayout(activity)
        activity_layout.setContentsMargins(18, 18, 18, 18)
        activity_layout.setSpacing(10)
        activity_layout.addWidget(self.section_label("Actividad reciente"))
        recent_rows = rows[:5]
        if not recent_rows:
            activity_layout.addWidget(QLabel("Sin actividad reciente."))
        for row in recent_rows:
            item = QLabel(f"• {row['numero']} · {row['cliente']} · {_money(row['total'])}")
            item.setObjectName("activityItem")
            activity_layout.addWidget(item)
        activity_layout.addStretch(1)
        middle.addWidget(chart, 2)
        middle.addWidget(activity, 1)
        layout.addLayout(middle)

        layout.addWidget(self.section_label("Acciones rapidas"))
        actions_grid = QGridLayout()
        actions_grid.setSpacing(12)
        quick_actions = [
            ("+", "Crear factura", "Manual o desde plantilla", "purple", self.new_invoice),
            ("◌", "Factura por voz", "Habla y la generamos", "orange", self.show_voice),
            ("▦", "Importar QR/PDF", "QR, ticket o PDF", "green", self.show_import),
            ("↑", "Exportar todo", "CSV / FacturaE", "blue", self.export_all),
        ]
        for index, action in enumerate(quick_actions):
            actions_grid.addWidget(QuickActionCard(*action), 0, index)
        layout.addLayout(actions_grid)

        layout.addWidget(self.section_label("Ultimas facturas"))
        layout.addWidget(self._invoice_table(rows[:5], compact=True))
        layout.addStretch(1)

    def show_invoices(self) -> None:
        self.navbar_title.setText("Facturas")
        self.stack.setCurrentWidget(self.invoices_page)
        self.render_invoices()

    def render_invoices(self) -> None:
        layout = self.clear_page(self.invoices_page)
        filter_btn = QPushButton("Filtros")
        filter_btn.setObjectName("ghostButton")
        export_btn = QPushButton("Exportar")
        export_btn.setObjectName("ghostButton")
        export_btn.clicked.connect(self.export_all)
        new_btn = QPushButton("+ Nueva Factura")
        new_btn.setObjectName("primaryButton")
        new_btn.clicked.connect(self.new_invoice)
        self.page_header(
            layout,
            "Facturas",
            "Listado, filtros, busqueda, acciones y generacion de borradores. Click en una factura para ver el detalle lateral.",
            [filter_btn, export_btn, new_btn],
        )

        all_rows = self.factura_controller.list_invoice_rows()
        counts = {
            "Todas": len(all_rows),
            "Borrador": sum(1 for row in all_rows if row["estado"] == EstadoFactura.BORRADOR.value),
            "Emitidas": sum(
                1
                for row in all_rows
                if row["estado"]
                in {EstadoFactura.EMITIDA.value, EstadoFactura.PAGADA.value, EstadoFactura.PARCIALMENTE_PAGADA.value}
            ),
            "Anuladas": sum(1 for row in all_rows if row["estado"] == EstadoFactura.CANCELADA.value),
        }
        filters = QHBoxLayout()
        for name in ["Todas", "Borrador", "Emitidas", "Anuladas"]:
            btn = QPushButton(f"{name} {counts[name]}")
            btn.setObjectName("filterActive" if name == self.current_filter else "filterButton")
            btn.clicked.connect(lambda checked=False, value=name: self.set_filter(value))
            filters.addWidget(btn)
        filters.addStretch(1)
        period = QPushButton("Ultimos 30 dias")
        period.setObjectName("ghostButton")
        order = QPushButton("Ordenar")
        order.setObjectName("ghostButton")
        filters.addWidget(period)
        filters.addWidget(order)
        layout.addLayout(filters)

        rows = self.filtered_rows()
        layout.addWidget(self._invoice_table(rows))
        layout.addStretch(1)

    def set_filter(self, value: str) -> None:
        self.current_filter = value
        self.render_invoices()

    def filtered_rows(self) -> list[dict[str, object]]:
        rows = self.factura_controller.list_invoice_rows()
        if self.current_filter == "Borrador":
            rows = [r for r in rows if r["estado"] == EstadoFactura.BORRADOR.value]
        elif self.current_filter == "Emitidas":
            rows = [r for r in rows if r["estado"] in {EstadoFactura.EMITIDA.value, EstadoFactura.PAGADA.value, EstadoFactura.PARCIALMENTE_PAGADA.value}]
        elif self.current_filter == "Anuladas":
            rows = [r for r in rows if r["estado"] == EstadoFactura.CANCELADA.value]
        query = self.current_search.strip().lower()
        if query:
            rows = [r for r in rows if query in str(r["numero"]).lower() or query in str(r["cliente"]).lower()]
        return rows

    def _invoice_table(self, rows: list[dict[str, object]], compact: bool = False) -> QTableWidget:
        columns = ["Nº Factura", "Receptor", "Fecha", "Estado", "Líneas", "Total", "Acciones"]
        table = QTableWidget(0, len(columns))
        table.setObjectName("dataTable")
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [
                row["numero"],
                row["cliente"],
                row["fecha"],
                row["estado"],
                "1",
                _money(row["total"]),
                "Ver / Editar",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                if column == 3:
                    item.setText(f"• {value}")
                    state = str(value).upper()
                    if "PAGADA" in state:
                        item.setForeground(QColor("#2f6fed"))
                    elif "BORRADOR" in state:
                        item.setForeground(QColor("#d58b05"))
                    elif "CANCEL" in state or "ANUL" in state:
                        item.setForeground(QColor("#e54b65"))
                    else:
                        item.setForeground(QColor("#17a77a"))
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                if column == 5:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    font = QFont()
                    font.setBold(True)
                    item.setFont(font)
                table.setItem(row_index, column, item)
            table.setRowHeight(row_index, 46 if compact else 56)
        table.cellDoubleClicked.connect(lambda row, _col: self.view_invoice(rows[row]["numero"]))
        table.setMinimumHeight(280 if compact else 560)
        return table

    def view_invoice(self, numero: object) -> None:
        factura = next((f for f in self.factura_controller.list_facturas() if f.numero == numero), None)
        if factura is None:
            return
        
        dialog = InvoiceDetailDialog(self, factura, self.factura_controller)
        dialog.exec()
        
        clicked = dialog.action_to_take
        if not clicked:
            return
            
        try:
            if clicked == "edit":
                self.edit_invoice(factura)
            elif clicked == "emit":
                self.emit_invoice(factura)
            elif clicked == "pay":
                self.register_payment(factura)
            elif clicked == "email":
                self.send_invoice_email(factura)
            elif clicked == "verifactu":
                self.register_verifactu(factura)
            elif clicked == "pdf":
                self.generate_pdf(factura)
            elif clicked == "cancel":
                self.factura_controller.cancel_factura(factura.id)
                self.render_invoices()
            elif clicked == "delete":
                self.factura_controller.delete_factura(factura.id)
                self.render_invoices()
        except Exception as exc:
            QMessageBox.warning(self, "Acción no disponible", str(exc))

    def new_invoice(self) -> None:
        self.open_invoice_overlay()

    def edit_invoice(self, factura: Factura) -> None:
        self.open_invoice_overlay(factura)

    def open_invoice_overlay(self, factura: Factura | None = None) -> None:
        self.close_invoice_overlay()
        panel = InvoiceFormPanel(
            self.content_frame,
            self.factura_controller,
            on_close=self.close_invoice_overlay,
            on_saved=self.on_invoice_saved,
            email_service=self.email_service,
            factura=factura,
        )
        self.invoice_overlay = ModalOverlay(self.content_frame, panel)
        self.invoice_overlay.setGeometry(self.content_frame.rect())
        self.invoice_overlay.show()
        self.invoice_overlay.raise_()

    def close_invoice_overlay(self) -> None:
        if self.invoice_overlay is None:
            return
        self.invoice_overlay.hide()
        self.invoice_overlay.deleteLater()
        self.invoice_overlay = None

    def open_voice_overlay(self) -> None:
        self.close_voice_overlay()
        panel = VoiceRedirectPanel(on_close=self.close_voice_overlay, parent=self.content_frame)
        self.voice_overlay = ModalOverlay(self.content_frame, panel)
        self.voice_overlay.setGeometry(self.content_frame.rect())
        self.voice_overlay.show()
        self.voice_overlay.raise_()

    def close_voice_overlay(self) -> None:
        if self.voice_overlay is None:
            return
        self.voice_overlay.hide()
        self.voice_overlay.deleteLater()
        self.voice_overlay = None

    def on_invoice_saved(self) -> None:
        self.last_persistent_nav_row = 1
        self.navigation.setCurrentRow(1)
        self.render_invoices()

    def register_payment(self, factura: Factura) -> None:
        totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
        amount, ok = QInputDialog.getDouble(
            self,
            "Registrar cobro",
            f"Importe cobrado acumulado. Pendiente actual: {_money(totals.importe_pendiente)}",
            float(totals.total),
            0,
            float(totals.total),
            2,
        )
        if not ok:
            return
        self.factura_controller.register_payment(factura.id, Decimal(str(amount)))
        self.render_invoices()

    def generate_pdf(self, factura: Factura) -> Path:
        from PySide6.QtCore import QSettings
        qsettings = QSettings("Automalize", "DesktopApp")
        template = qsettings.value(f"invoice_template_{factura.id}", "classic")
        emisor_details = self.factura_controller.get_emisor_details()
        path = generate_invoice_pdf(factura, Path.cwd() / "exports" / "pdf", template=template, emisor_details=emisor_details)
        QMessageBox.information(self, "PDF generado", f"Archivo generado:\n{path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        return path

    def send_invoice_email(self, factura: Factura) -> None:
        from PySide6.QtCore import QSettings
        qsettings = QSettings("Automalize", "DesktopApp")
        template = qsettings.value(f"invoice_template_{factura.id}", "classic")
        emisor_details = self.factura_controller.get_emisor_details()
        path = generate_invoice_pdf(factura, Path.cwd() / "exports" / "pdf", template=template, emisor_details=emisor_details)
        self.email_service.send_invoice(factura, path)
        QMessageBox.information(self, "Email enviado", f"Factura enviada a {factura.cliente_email}.")

    def emit_invoice(self, factura: Factura) -> None:
        emitted = self.factura_controller.emit_factura(factura.id)
        self.render_invoices()
        if not emitted.cliente_email or not self.email_service.is_configured():
            return
        answer = QMessageBox.question(
            self,
            "Enviar email",
            f"Factura emitida. Quieres enviarla ahora a {emitted.cliente_email}?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.send_invoice_email(emitted)

    def register_verifactu(self, factura: Factura) -> None:
        result = self.verifactu_service.create(factura)
        self.factura_controller.attach_verifactu_result(factura.id, result.uuid, result.url, result.qr)
        QMessageBox.information(self, "Verifactu", "Factura registrada en Verifactu.")

    # ------------------------------------------------------------------
    # Importar Factura — replica exacta de scan-qr.js (referencia)
    # ------------------------------------------------------------------
    def show_import(self) -> None:
        self.navbar_title.setText("Importar Factura")
        self.stack.setCurrentWidget(self.import_page)
        layout = self.clear_page(self.import_page)
        self._ocr_worker: OcrWorker | None = None
        self._ocr_current_source: str = ""  # "Ticket" or "PDF"

        # ── Header (centrado, igual que la referencia) ──────────────────
        header_wrapper = QWidget()
        hw_layout = QVBoxLayout(header_wrapper)
        hw_layout.setContentsMargins(0, 8, 0, 8)
        hw_layout.setSpacing(6)
        hw_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        h1 = QLabel("Importar Factura")
        h1.setObjectName("importPageTitle")
        h1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub = QLabel("Importa datos de una foto de ticket o archivo PDF")
        sub.setObjectName("importPageSub")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hw_layout.addWidget(h1)
        hw_layout.addWidget(sub)
        layout.addWidget(header_wrapper)

        # ── Tabs ─────────────────────────────────────────────────────────
        tabs_frame = QFrame()
        tabs_frame.setObjectName("scanTabBar")
        tabs_layout = QHBoxLayout(tabs_frame)
        tabs_layout.setContentsMargins(6, 6, 6, 6)
        tabs_layout.setSpacing(6)

        self._tab_ticket = QPushButton("📷  Foto de Ticket")
        self._tab_ticket.setObjectName("scanTabActive")
        self._tab_ticket.setCheckable(True)
        self._tab_ticket.setChecked(True)

        self._tab_pdf = QPushButton("📄  Archivo PDF")
        self._tab_pdf.setObjectName("scanTab")
        self._tab_pdf.setCheckable(True)
        self._tab_pdf.setChecked(False)

        tabs_layout.addWidget(self._tab_ticket)
        tabs_layout.addWidget(self._tab_pdf)
        layout.addWidget(tabs_frame)

        # ── Mode stack (Ticket / PDF) ─────────────────────────────────────
        self._mode_stack = QStackedWidget()

        # — Panel Ticket —
        ticket_page = QWidget()
        t_layout = QVBoxLayout(ticket_page)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_card = QFrame()
        t_card.setObjectName("scanCard")
        t_card_l = QVBoxLayout(t_card)
        t_card_l.setContentsMargins(24, 24, 24, 24)
        t_card_l.setSpacing(12)
        t_title = QLabel("📷  Foto de Ticket / Factura")
        t_title.setObjectName("scanCardTitle")
        t_desc = QLabel(
            "Sube una foto de un ticket de compra o factura y extraeremos "
            "los datos automáticamente mediante OCR."
        )
        t_desc.setObjectName("scanCardDesc")
        t_desc.setWordWrap(True)
        t_card_l.addWidget(t_title)
        t_card_l.addWidget(t_desc)

        t_zone = DropZoneFrame("Ticket")
        t_zone.setObjectName("dropZone")
        t_zone.fileDropped.connect(lambda path: self._process_file(path, "Ticket"))
        t_zone_l = QVBoxLayout(t_zone)
        t_zone_l.setContentsMargins(24, 32, 24, 32)
        t_zone_l.setSpacing(10)
        t_zone_l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        t_zone_icon = QLabel("📷")
        t_zone_icon.setObjectName("dropZoneIcon")
        t_zone_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_zone_text = QLabel("Haz clic para seleccionar una foto del ticket")
        t_zone_text.setObjectName("dropZoneText")
        t_zone_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_zone_hint = QLabel("JPG, PNG, WebP — Máx. 10 MB")
        t_zone_hint.setObjectName("dropZoneHint")
        t_zone_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_select_btn = QPushButton("Seleccionar Foto")
        t_select_btn.setObjectName("primaryButton")
        t_select_btn.setMinimumHeight(48)
        t_select_btn.clicked.connect(lambda: self._pick_file("Ticket"))
        t_zone_l.addWidget(t_zone_icon)
        t_zone_l.addWidget(t_zone_text)
        t_zone_l.addWidget(t_zone_hint)
        t_zone_l.addWidget(t_select_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        t_card_l.addWidget(t_zone)
        t_layout.addWidget(t_card)
        self._mode_stack.addWidget(ticket_page)  # index 0

        # — Panel PDF —
        pdf_page = QWidget()
        p_layout = QVBoxLayout(pdf_page)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_card = QFrame()
        p_card.setObjectName("scanCard")
        p_card_l = QVBoxLayout(p_card)
        p_card_l.setContentsMargins(24, 24, 24, 24)
        p_card_l.setSpacing(12)
        p_title = QLabel("📄  Importar desde PDF")
        p_title.setObjectName("scanCardTitle")
        p_desc = QLabel(
            "Sube un PDF de una factura o ticket y extraeremos el texto "
            "para generar la factura."
        )
        p_desc.setObjectName("scanCardDesc")
        p_desc.setWordWrap(True)
        p_card_l.addWidget(p_title)
        p_card_l.addWidget(p_desc)

        p_zone = DropZoneFrame("PDF")
        p_zone.setObjectName("dropZone")
        p_zone.fileDropped.connect(lambda path: self._process_file(path, "PDF"))
        p_zone_l = QVBoxLayout(p_zone)
        p_zone_l.setContentsMargins(24, 32, 24, 32)
        p_zone_l.setSpacing(10)
        p_zone_l.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        p_zone_icon = QLabel("📄")
        p_zone_icon.setObjectName("dropZoneIcon")
        p_zone_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_zone_text = QLabel("Haz clic para seleccionar un archivo PDF")
        p_zone_text.setObjectName("dropZoneText")
        p_zone_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_zone_hint = QLabel("Archivos .pdf — Máx. 20 MB")
        p_zone_hint.setObjectName("dropZoneHint")
        p_zone_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        p_select_btn = QPushButton("Seleccionar PDF")
        p_select_btn.setObjectName("primaryButton")
        p_select_btn.setMinimumHeight(48)
        p_select_btn.clicked.connect(lambda: self._pick_file("PDF"))
        p_zone_l.addWidget(p_zone_icon)
        p_zone_l.addWidget(p_zone_text)
        p_zone_l.addWidget(p_zone_hint)
        p_zone_l.addWidget(p_select_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        p_card_l.addWidget(p_zone)
        p_layout.addWidget(p_card)
        self._mode_stack.addWidget(pdf_page)  # index 1

        layout.addWidget(self._mode_stack)

        # ── Panel Procesando ──────────────────────────────────────────────
        self._proc_panel = QFrame()
        self._proc_panel.setObjectName("processingCard")
        self._proc_panel.setVisible(False)
        proc_l = QVBoxLayout(self._proc_panel)
        proc_l.setContentsMargins(24, 36, 24, 36)
        proc_l.setSpacing(14)
        proc_l.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self._proc_title = QLabel("Procesando...")
        self._proc_title.setObjectName("processingTitle")
        self._proc_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._proc_detail = QLabel("Extrayendo texto del documento")
        self._proc_detail.setObjectName("processingDetail")
        self._proc_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._proc_bar = QProgressBar()
        self._proc_bar.setObjectName("scanProgressBar")
        self._proc_bar.setRange(0, 0)  # indeterminate / pulsing
        self._proc_bar.setMinimumWidth(320)
        self._proc_bar.setMaximumWidth(480)
        self._proc_bar.setFixedHeight(8)
        self._proc_bar.setTextVisible(False)

        proc_l.addWidget(self._proc_title)
        proc_l.addWidget(self._proc_detail)
        proc_l.addWidget(self._proc_bar, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._proc_panel)

        # ── Panel Resultado ───────────────────────────────────────────────
        self._result_panel = QFrame()
        self._result_panel.setObjectName("resultCard")
        self._result_panel.setVisible(False)
        self._result_layout = QVBoxLayout(self._result_panel)
        self._result_layout.setContentsMargins(24, 24, 24, 24)
        self._result_layout.setSpacing(18)
        layout.addWidget(self._result_panel)

        layout.addStretch(1)

        # ── Tab switching logic ───────────────────────────────────────────
        def _switch_tab(mode: int) -> None:
            self._mode_stack.setCurrentIndex(mode)
            self._result_panel.setVisible(False)
            self._proc_panel.setVisible(False)
            if mode == 0:
                self._tab_ticket.setObjectName("scanTabActive")
                self._tab_ticket.setChecked(True)
                self._tab_pdf.setObjectName("scanTab")
                self._tab_pdf.setChecked(False)
            else:
                self._tab_pdf.setObjectName("scanTabActive")
                self._tab_pdf.setChecked(True)
                self._tab_ticket.setObjectName("scanTab")
                self._tab_ticket.setChecked(False)
            # Force style refresh
            self._tab_ticket.setStyle(self._tab_ticket.style())
            self._tab_pdf.setStyle(self._tab_pdf.style())

        self._tab_ticket.clicked.connect(lambda: _switch_tab(0))
        self._tab_pdf.clicked.connect(lambda: _switch_tab(1))

    def _process_file(self, path: str, source: str) -> None:
        self._ocr_current_source = source
        self._show_processing(source)

        worker = OcrWorker(path)
        worker.finished.connect(self._on_ocr_done)
        worker.error.connect(self._on_ocr_error)
        self._ocr_worker = worker
        worker.start()

    def _pick_file(self, source: str) -> None:
        """Open file dialog and start OCR processing."""
        if source == "PDF":
            file_filter = "PDF (*.pdf)"
        else:
            file_filter = "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"

        path, _ = QFileDialog.getOpenFileName(
            self, "Importar factura", str(Path.home()), file_filter
        )
        if not path:
            return

        self._process_file(path, source)

    def _show_processing(self, source: str) -> None:
        self._mode_stack.setVisible(False)
        self._result_panel.setVisible(False)
        self._proc_panel.setVisible(True)
        if source == "PDF":
            self._proc_title.setText("Extrayendo texto del PDF...")
            self._proc_detail.setText("Leyendo las páginas del documento")
        else:
            self._proc_title.setText("Procesando imagen con OCR...")
            self._proc_detail.setText(
                "Esto puede tardar unos segundos dependiendo de la calidad de la imagen"
            )
        self._proc_bar.setRange(0, 0)  # indeterminate pulse

    def _on_ocr_done(self, draft: object) -> None:  # draft: OcrDraft
        self._proc_panel.setVisible(False)
        self._mode_stack.setVisible(True)

        if not draft.raw_text or not draft.raw_text.strip():
            QMessageBox.warning(
                self,
                "Sin texto",
                "No se pudo extraer texto del documento. Prueba con una imagen más nítida.",
            )
            return

        self._show_result(draft)

    def _on_ocr_error(self, message: str) -> None:
        self._proc_panel.setVisible(False)
        self._mode_stack.setVisible(True)
        QMessageBox.critical(self, "Error al procesar", message)

    def _show_result(self, draft: object) -> None:  # draft: OcrDraft
        """Populate and show the result panel — mirrors showResult() in scan-qr.js."""
        # Clear previous result content
        while self._result_layout.count():
            item = self._result_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        source = self._ocr_current_source

        # ─ Header row: ✅ Datos Extraídos ─
        result_header = QHBoxLayout()
        result_header.setSpacing(10)
        check_icon = QLabel("✅")
        check_icon.setObjectName("resultCheckIcon")
        result_h_label = QLabel(f"Datos Extraídos — {source}")
        result_h_label.setObjectName("resultTitle")
        result_header.addWidget(check_icon)
        result_header.addWidget(result_h_label)
        result_header.addStretch(1)
        self._result_layout.addLayout(result_header)

        # ─ Data grid ─
        grid_frame = QFrame()
        grid_frame.setObjectName("resultGridFrame")
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(32)
        grid.setVerticalSpacing(12)

        def _add_field(row: int, col: int, label: str, value: str, big: bool = False) -> None:
            lbl = QLabel(label.upper())
            lbl.setObjectName("resultLabel")
            val = QLabel(value or "—")
            val.setObjectName("resultValueBig" if big else "resultValue")
            val.setWordWrap(True)
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(lbl)
            cell.addWidget(val)
            grid.addLayout(cell, row, col)

        _add_field(0, 0, "Proveedor", draft.cliente_nombre)
        _add_field(0, 1, "NIF / CIF", draft.cliente_nif)
        _add_field(1, 0, "Fecha", draft.fecha.isoformat() if draft.fecha else "—")

        # Calcular total desde líneas
        from app.services.invoice_calculator import calculate_invoice
        if draft.lineas:
            totals = calculate_invoice(draft.lineas)
            _add_field(1, 1, "Total", _money(totals.total), big=True)
            if totals.subtotal:
                _add_field(2, 0, "Base Imponible", _money(totals.subtotal))
            if totals.iva:
                _add_field(2, 1, "IVA", _money(totals.iva))
        self._result_layout.addWidget(grid_frame)

        # ─ Tabla de artículos detectados ─
        if draft.lineas:
            items_label = QLabel("ARTÍCULOS DETECTADOS")
            items_label.setObjectName("resultSectionLabel")
            self._result_layout.addWidget(items_label)

            items_table = QTableWidget(len(draft.lineas), 3)
            items_table.setObjectName("resultItemsTable")
            items_table.setHorizontalHeaderLabels(["Descripción", "Uds.", "Precio"])
            items_table.verticalHeader().setVisible(False)
            items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            items_table.setShowGrid(False)
            items_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
            items_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            items_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            items_table.setAlternatingRowColors(True)
            items_table.setMaximumHeight(min(40 + len(draft.lineas) * 36, 260))

            for i, linea in enumerate(draft.lineas):
                items_table.setItem(i, 0, QTableWidgetItem(linea.descripcion))
                qty_item = QTableWidgetItem(str(linea.cantidad))
                qty_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                items_table.setItem(i, 1, qty_item)
                price_item = QTableWidgetItem(_money(linea.precio_unitario))
                price_item.setTextAlignment(int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter))
                items_table.setItem(i, 2, price_item)
                items_table.setRowHeight(i, 36)

            self._result_layout.addWidget(items_table)

        # ─ Texto extraído (colapsable) ─
        if draft.raw_text:
            raw_group = QGroupBox("Ver texto extraído")
            raw_group.setObjectName("rawTextGroup")
            raw_group.setCheckable(True)
            raw_group.setChecked(False)
            raw_l = QVBoxLayout(raw_group)
            raw_l.setContentsMargins(10, 10, 10, 10)
            raw_edit = QPlainTextEdit()
            raw_edit.setObjectName("rawTextBox")
            raw_edit.setPlainText(draft.raw_text)
            raw_edit.setReadOnly(True)
            raw_edit.setMaximumHeight(180)
            raw_l.addWidget(raw_edit)

            def _toggle_raw(checked: bool) -> None:
                raw_edit.setVisible(checked)

            raw_group.toggled.connect(_toggle_raw)
            raw_edit.setVisible(False)
            self._result_layout.addWidget(raw_group)

        # ─ Botones de acción ─
        actions_row = QHBoxLayout()
        actions_row.setSpacing(12)

        create_btn = QPushButton("+ Crear Factura con estos datos")
        create_btn.setObjectName("primaryButton")
        create_btn.setMinimumHeight(48)
        create_btn.clicked.connect(lambda: self._create_from_draft(draft))

        again_btn = QPushButton("↺  Importar Otro")
        again_btn.setObjectName("ghostButton")
        again_btn.setMinimumHeight(48)
        again_btn.clicked.connect(self._reset_import)

        actions_row.addWidget(create_btn, 1)
        actions_row.addWidget(again_btn)
        self._result_layout.addLayout(actions_row)

        self._result_panel.setVisible(True)

    def _create_from_draft(self, draft: object) -> None:  # draft: OcrDraft
        """Create invoice from OCR draft and open edit overlay — mirrors createInvoiceFromData()."""
        try:
            from app.services.invoice_calculator import calculate_invoice
            notes = f"Importado automáticamente mediante OCR. Archivo origen: {draft.source_path}"
            if draft.raw_text:
                notes += f"\n\nTexto extraído:\n{draft.raw_text[:2000]}"
            created = self.factura_controller.create_factura(
                cliente_nombre=draft.cliente_nombre,
                fecha=draft.fecha,
                lineas=draft.lineas,
                cliente_email=draft.cliente_email,
                cliente_nif=draft.cliente_nif,
                cliente_direccion=draft.cliente_direccion,
                notas=notes,
            )
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo crear la factura", str(exc))
            return

        # Navigate to invoices and open the edit overlay (= edit-invoice in reference)
        self.last_persistent_nav_row = 1
        self.navigation.setCurrentRow(1)
        self.render_invoices()
        self.open_invoice_overlay(created)

    def _reset_import(self) -> None:
        """Hide result panel and show the import UI again."""
        self._result_panel.setVisible(False)
        self._proc_panel.setVisible(False)
        self._mode_stack.setVisible(True)

    # kept for backwards compat (called by dashboard quick-action)
    def import_file(self, file_filter: str) -> None:
        self.show_import()
        # Pick the right tab based on filter hint
        if "pdf" in file_filter.lower():
            self._tab_pdf.click()
        self._pick_file("PDF" if "pdf" in file_filter.lower() else "Ticket")

    def show_voice(self) -> None:
        self.open_voice_overlay()

    def export_all(self) -> None:
        rows = self.factura_controller.list_invoice_rows()
        path, selected = QFileDialog.getSaveFileName(
            self,
            "Exportar facturas",
            str(Path.home() / "facturas"),
            "Excel (*.xlsx);;CSV (*.csv);;XML (*.xml)",
        )
        if not path:
            return
        try:
            if selected.startswith("CSV") or path.endswith(".csv"):
                export_rows_to_csv(rows, path)
            elif selected.startswith("XML") or path.endswith(".xml"):
                export_rows_to_xml(rows, path)
            else:
                if not path.endswith(".xlsx"):
                    path += ".xlsx"
                export_rows_to_excel(rows, path)
        except Exception as exc:
            QMessageBox.critical(self, "Error de exportación", str(exc))
            return
        QMessageBox.information(self, "Exportación completada", "Archivo generado correctamente.")


APP_STYLESHEET = """
/* ── Importar Factura — scan-qr styles ────────────────────────── */
QLabel#importPageTitle {
    font-size: 28px;
    font-weight: 800;
    color: #181a2f;
}
QLabel#importPageSub {
    color: #747894;
    font-size: 14px;
}
QFrame#scanTabBar {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 10px;
}
QPushButton#scanTab {
    background: transparent;
    border: none;
    color: #5d617d;
    border-radius: 7px;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: 600;
}
QPushButton#scanTab:hover {
    background: #f4f5fb;
    color: #202238;
}
QPushButton#scanTabActive {
    background: #5a50ee;
    border: none;
    color: #ffffff;
    border-radius: 7px;
    padding: 12px 20px;
    font-size: 15px;
    font-weight: 700;
}
QFrame#scanCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 10px;
}
QLabel#scanCardTitle {
    font-size: 16px;
    font-weight: 800;
    color: #181a2f;
}
QLabel#scanCardDesc {
    color: #747894;
    font-size: 13px;
}
QFrame#dropZone {
    background: #f8f9ff;
    border: 2px dashed #c5c9f0;
    border-radius: 10px;
    min-height: 180px;
}
QFrame#dropZone[dragOver="true"] {
    background: #ece9ff;
    border: 2px dashed #5a50ee;
}
QLabel#dropZoneIcon {
    font-size: 48px;
    background: transparent;
}
QLabel#dropZoneText {
    color: #202238;
    font-size: 15px;
    font-weight: 600;
    background: transparent;
}
QLabel#dropZoneHint {
    color: #747894;
    font-size: 12px;
    background: transparent;
}
QFrame#processingCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 10px;
    min-height: 160px;
}
QLabel#processingTitle {
    font-size: 18px;
    font-weight: 700;
    color: #181a2f;
}
QLabel#processingDetail {
    color: #747894;
    font-size: 13px;
}
QProgressBar#scanProgressBar {
    background: #e8ebf7;
    border: none;
    border-radius: 4px;
}
QProgressBar#scanProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7d73ff, stop:1 #5449ef);
    border-radius: 4px;
}
QFrame#resultCard {
    background: #ffffff;
    border: 1px solid #c8f5e4;
    border-radius: 10px;
}
QLabel#resultCheckIcon {
    font-size: 22px;
    background: transparent;
}
QLabel#resultTitle {
    font-size: 18px;
    font-weight: 700;
    color: #181a2f;
}
QLabel#resultLabel {
    color: #747894;
    font-size: 11px;
    font-weight: 700;
    background: transparent;
}
QLabel#resultValue {
    color: #202238;
    font-size: 14px;
    font-weight: 600;
    background: transparent;
}
QLabel#resultValueBig {
    color: #5a50ee;
    font-size: 18px;
    font-weight: 800;
    background: transparent;
}
QLabel#resultSectionLabel {
    color: #747894;
    font-size: 11px;
    font-weight: 700;
}
QTableWidget#resultItemsTable {
    background: #fafbff;
    alternate-background-color: #f4f5fb;
    border: 1px solid #e2e5f1;
    border-radius: 7px;
    font-size: 13px;
}
QGroupBox#rawTextGroup {
    color: #747894;
    font-size: 12px;
    border: 1px solid #e2e5f1;
    border-radius: 7px;
    margin-top: 8px;
    padding-top: 10px;
}
QGroupBox#rawTextGroup::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    color: #747894;
}
QPlainTextEdit#rawTextBox {
    background: #f4f5fb;
    border: none;
    font-size: 12px;
    color: #4a4e6d;
    font-family: "Consolas", monospace;
}
/* ────────────────────────────────────────────────────────────── */

QMainWindow {
    background: #f4f5fb;
}
QWidget {
    background: transparent;
    color: #17192f;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}
QFrame#sidebar {
    background: #111326;
    border-right: 1px solid #24263c;
}
QLabel#brandAvatar {
    background: #6157f4;
    color: #ffffff;
    border-radius: 8px;
    min-width: 34px;
    min-height: 34px;
    max-width: 34px;
    max-height: 34px;
    qproperty-alignment: AlignCenter;
    font-size: 18px;
    font-weight: 800;
}
QLabel#logo {
    color: #ffffff;
    font-size: 18px;
    font-weight: 800;
}
QLabel#sidebarSummary {
    color: #8f93b4;
    font-size: 12px;
}
QLabel#sideSection {
    color: #747894;
    font-size: 10px;
    font-weight: 700;
    padding: 14px 6px 4px 6px;
}
QListWidget#navigation {
    background: transparent;
    border: none;
    color: #dfe2f5;
    outline: none;
}
QListWidget#navigation::item {
    padding: 10px 12px;
    border-radius: 7px;
    margin: 2px 0;
    font-weight: 600;
    min-height: 22px;
}
QListWidget#navigation::item:selected {
    background: #5a50ee;
    color: #ffffff;
}
QListWidget#navigation::item:hover {
    background: #1f2238;
    color: #ffffff;
}
QFrame#content, QScrollArea, QWidget#page, QStackedWidget {
    background: #f4f5fb;
}
QFrame#navbar {
    background: #ffffff;
    border-bottom: 1px solid #e4e6f0;
    min-height: 62px;
    max-height: 62px;
}
QLabel#navbarTitle {
    font-size: 14px;
    font-weight: 700;
    color: #202238;
}
QPushButton#navToggleButton, QPushButton#topIconButton {
    background: #ffffff;
    color: #747894;
    border: 1px solid #e0e3f1;
    border-radius: 7px;
    padding: 8px 10px;
}
QPushButton#navToggleButton:hover, QPushButton#topIconButton:hover {
    background: #f4f5fb;
}
QLabel#viewTitle {
    font-size: 28px;
    font-weight: 800;
    color: #181a2f;
}
QLabel#viewSubtitle {
    color: #747894;
    font-size: 14px;
}
QFrame#panel, QFrame#statCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
}
QFrame#statCard {
    min-height: 72px;
}
QFrame#invoiceModalCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 10px;
}
QFrame#voiceRedirectCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 18px;
}
QFrame#invoicePreview {
    background: #f8f9ff;
    color: #23264a;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
}
QLabel#previewText {
    color: #252742;
    font-family: "Segoe UI";
    font-size: 14px;
}
QLabel#dialogTitle {
    font-size: 24px;
    font-weight: 700;
    color: #181a2f;
}
QLabel#voiceRedirectTitle {
    font-size: 30px;
    font-weight: 800;
    color: #181a2f;
}
QLabel#voiceRedirectSubtitle {
    color: #6c718d;
    font-size: 16px;
}
QLabel#voiceRedirectHandle {
    color: #6256f4;
    font-size: 18px;
    font-weight: 700;
}
QLabel#sectionTitle {
    font-size: 16px;
    font-weight: 800;
    color: #181a2f;
}
QLabel#statValue {
    font-size: 24px;
    font-weight: 800;
    color: #17192f;
}
QLabel#statTitle {
    color: #747894;
    font-size: 12px;
}
QLabel#statIcon_purple, QLabel#statIcon_yellow, QLabel#statIcon_blue, QLabel#statIcon_green {
    border-radius: 8px;
    min-width: 42px;
    min-height: 42px;
    max-width: 42px;
    max-height: 42px;
    qproperty-alignment: AlignCenter;
    font-weight: 800;
}
QLabel#statIcon_purple { background: #ecebff; color: #5a50ee; }
QLabel#statIcon_yellow { background: #fff2d4; color: #d28a00; }
QLabel#statIcon_blue { background: #e8f0ff; color: #3678f6; }
QLabel#statIcon_green { background: #ddf8ef; color: #18a879; }
QLabel#quickIcon_purple, QLabel#quickIcon_orange, QLabel#quickIcon_green, QLabel#quickIcon_blue {
    border-radius: 7px;
    min-width: 36px;
    min-height: 36px;
    max-width: 36px;
    max-height: 36px;
    qproperty-alignment: AlignCenter;
    font-size: 17px;
    font-weight: 800;
}
QLabel#quickIcon_purple { background: #ecebff; color: #6256f4; }
QLabel#quickIcon_orange { background: #fff1df; color: #e07c22; }
QLabel#quickIcon_green { background: #ddf8ef; color: #18a879; }
QLabel#quickIcon_blue { background: #e8f0ff; color: #3678f6; }
QLabel#quickTitle {
    color: #181a2f;
    font-weight: 800;
}
QLabel#quickSubtitle {
    color: #747894;
    font-size: 12px;
}
QFrame#quickActionCard, QFrame#importCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
    min-height: 96px;
}
QFrame#quickActionCard:hover, QFrame#importCard:hover {
    border: 1px solid #bfc5ff;
}
QLineEdit, QDateEdit, QComboBox, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #dfe3f0;
    border-radius: 7px;
    color: #202238;
    padding: 8px 12px;
    min-height: 22px;
    selection-background-color: #5a50ee;
}
QDateEdit::drop-down, QComboBox::drop-down {
    border: none;
    width: 28px;
}
QAbstractItemView {
    selection-background-color: #ece9ff;
}
QWidget#invoiceFormBody {
    background: transparent;
}
QLineEdit#pillSearch {
    border-radius: 7px;
    min-width: 300px;
    min-height: 24px;
    padding-left: 16px;
    background: #ffffff;
}
QLineEdit#sidebarSearch {
    background: #0c0e1d;
    color: #dfe2f5;
    border: 1px solid #292c46;
    border-radius: 7px;
    padding: 8px 10px;
}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #5a50ee;
}
QPushButton {
    background: #5a50ee;
    color: white;
    border: none;
    border-radius: 7px;
    padding: 9px 14px;
    font-weight: 700;
}
QPushButton:hover {
    background: #6a61f6;
}
QPushButton#primaryButton {
    background: #5a50ee;
    color: #ffffff;
    border: none;
}
QPushButton#accentButton {
    background: #168a68;
}
QPushButton#warningButton {
    background: #ecebff;
    color: #4b42c6;
}
QPushButton#ghostButton, QPushButton#sideButton, QPushButton#filterButton {
    background: #ffffff;
    border: 1px solid #dfe3f0;
    color: #202238;
}
QPushButton#sideButton {
    background: transparent;
    color: #dfe2f5;
    border: none;
    text-align: left;
    padding: 10px 12px;
}
QPushButton#sideButton:hover {
    background: #1f2238;
}
QPushButton#filterActive {
    background: #ecebff;
    border: 1px solid #cfcaff;
    color: #4b42c6;
}
QPushButton#dangerButton {
    background: #fff5f7;
    border: 1px solid #ffd4dc;
    color: #df3d56;
}
QTableWidget#dataTable, QTableWidget {
    background: #ffffff;
    alternate-background-color: #fbfcff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
    color: #202238;
    gridline-color: #edf0f7;
    selection-background-color: #f0efff;
}
QHeaderView::section {
    background: #fafbff;
    color: #747894;
    border: none;
    border-bottom: 1px solid #e2e5f1;
    padding: 11px 12px;
    font-size: 12px;
    font-weight: 800;
}
QTableCornerButton::section {
    background: #fafbff;
    border: none;
    border-bottom: 1px solid #e2e5f1;
}
QScrollArea {
    border: none;
}
QFrame#modalOverlay {
    background: rgba(20, 23, 44, 0.24);
}
QFrame#userCard {
    background: transparent;
    border-top: 1px solid #24263c;
    border-radius: 0px;
    margin-top: 8px;
}
QLabel#userCardTitle {
    color: #ffffff;
    font-size: 13px;
    font-weight: 700;
}
QLabel#userCardText {
    color: #747894;
    font-size: 12px;
}
QFrame#chartBar {
    background: #dcd9ff;
    border-radius: 6px;
}
QFrame#chartBarStrong {
    background: #6256f4;
    border-radius: 6px;
}
QLabel#barValue, QLabel#barMonth {
    color: #747894;
    font-size: 11px;
}
QLabel#activityItem, QLabel#recentImport, QLabel#draftLine {
    color: #202238;
    font-size: 13px;
}
QLabel#uploadIcon, QLabel#voicePulse {
    background: #ecebff;
    color: #6256f4;
    border-radius: 8px;
    qproperty-alignment: AlignCenter;
    font-size: 30px;
    min-width: 54px;
    min-height: 54px;
}
QLabel#voiceRedirectOrb {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #7d73ff, stop:1 #5449ef);
    color: #ffffff;
    border-radius: 54px;
    font-size: 44px;
    min-width: 108px;
    min-height: 108px;
    max-width: 108px;
    max-height: 108px;
}
QLabel#voicePulse {
    border-radius: 80px;
    font-size: 110px;
    min-width: 180px;
    min-height: 180px;
}
QLabel#transcriptBox, QLabel#suggestionChip {
    background: #fafbff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
    padding: 14px;
    color: #202238;
}
QLabel#successBadge {
    background: #ddf8ef;
    color: #168a68;
    border-radius: 8px;
    padding: 4px 10px;
    font-weight: 800;
}
QLabel#warningBadge {
    background: #fff2d4;
    color: #d28a00;
    border-radius: 8px;
    padding: 4px 10px;
    font-weight: 800;
}
QFrame#themeDivider {
    background: #e8ebf4;
    min-height: 1px;
    max-height: 1px;
}
QCheckBox#themeDarkToggle::indicator {
    width: 34px;
    height: 20px;
    border-radius: 10px;
    background: #d8dcef;
    border: 1px solid #d8dcef;
}
QCheckBox#themeDarkToggle::indicator:checked {
    background: #6256f4;
    border: 1px solid #6256f4;
}
QFrame#clientCard {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
    min-height: 220px;
}
QLabel#clientAvatar {
    background: #5a50ee;
    color: #ffffff;
    border-radius: 8px;
    min-width: 46px;
    min-height: 46px;
    max-width: 46px;
    max-height: 46px;
    qproperty-alignment: AlignCenter;
    font-weight: 800;
    font-size: 18px;
}
QLabel#clientName {
    color: #181a2f;
    font-weight: 800;
    font-size: 18px;
}
QLabel#clientMeta {
    color: #747894;
    font-size: 13px;
}
QLabel#clientDetail {
    color: #2c3047;
    font-size: 15px;
    min-height: 22px;
}
QLabel#clientArrow {
    color: #747894;
    font-size: 18px;
    font-weight: 700;
}
QFrame#clientDivider {
    background: #edf0f7;
    min-height: 1px;
    max-height: 1px;
}
QLabel#clientFooter {
    color: #5d617d;
    font-size: 13px;
    line-height: 1.4;
}
QDialog {
    background: #f4f5fb;
}
QDialog QFrame#panel {
    background: #ffffff;
}
QLabel {
    background: transparent;
}
QCheckBox {
    spacing: 10px;
    font-size: 13px;
    font-weight: 600;
    color: #181a2f;
    background: transparent;
}
QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border: 2px solid #c5c9f0;
    border-radius: 6px;
    background-color: #ffffff;
}
QCheckBox::indicator:hover {
    border: 2px solid #5a50ee;
    background-color: #f4f3ff;
}
QCheckBox::indicator:checked {
    background-color: #5a50ee;
    border: 2px solid #5a50ee;
    image: url(app/assets/checkmark.png);
}
QCheckBox::indicator:disabled {
    border: 2px solid #e2e5f1;
    background-color: #f4f5fb;
}
QMessageBox {
    background: #ffffff;
}
"""
