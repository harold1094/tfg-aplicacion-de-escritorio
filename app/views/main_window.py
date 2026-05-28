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
        self.setMinimumSize(860, 620)
        self.setMaximumWidth(1280)
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

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy")
        self.date_input.setDate(QDate(factura.fecha if factura else date.today()))
        self.type_input = QComboBox()
        self.type_input.addItems(["Factura", "Factura simplificada", "Factura rectificativa"])
        self.client_input = QLineEdit(factura.cliente_nombre if factura else "")
        self.client_input.setPlaceholderText("Cliente S.A.")
        self.nif_input = QLineEdit(factura.cliente_nif if factura else "")
        self.nif_input.setPlaceholderText("NIF / CIF")
        self.address_input = QLineEdit(factura.cliente_direccion if factura else "")
        self.address_input.setPlaceholderText("Dirección")
        self.email_input = QLineEdit(factura.cliente_email if factura else "")
        self.email_input.setPlaceholderText("correo@cliente.es")

        details_card = QFrame()
        details_card.setObjectName("panel")
        details_layout = QVBoxLayout(details_card)
        details_layout.setContentsMargins(20, 20, 20, 20)
        details_layout.setSpacing(16)

        details_title = QLabel("Datos principales")
        details_title.setObjectName("sectionTitle")
        details_layout.addWidget(details_title)

        document_form = QFormLayout()
        document_form.setSpacing(12)
        document_form.setHorizontalSpacing(18)
        document_form.addRow("Fecha de emisión", self.date_input)
        document_form.addRow("Tipo", self.type_input)
        details_layout.addLayout(document_form)

        client_form = QFormLayout()
        client_form.setSpacing(12)
        client_form.setHorizontalSpacing(18)
        client_form.addRow("Nombre / razón social", self.client_input)
        client_form.addRow("NIF / CIF", self.nif_input)
        client_form.addRow("Dirección", self.address_input)
        client_form.addRow("Email", self.email_input)
        details_layout.addLayout(client_form)

        self.auto_email_check = QCheckBox("Enviar email al cliente al emitir")
        self.auto_email_check.setToolTip(
            "Genera el PDF y envia la factura automaticamente al emitir, si SMTP esta configurado."
        )
        details_layout.addWidget(self.auto_email_check)
        form_layout.addWidget(details_card)

        lines_label = QLabel("Líneas de factura")
        lines_label.setObjectName("sectionTitle")
        lines_card = QFrame()
        lines_card.setObjectName("panel")
        lines_layout = QVBoxLayout(lines_card)
        lines_layout.setContentsMargins(20, 20, 20, 20)
        lines_layout.setSpacing(14)
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
        self.lines_table.setMinimumHeight(250)
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

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Notas adicionales...")
        self.notes_input.setMinimumHeight(110)
        self.notes_input.setMaximumHeight(140)
        if factura:
            self.notes_input.setPlainText(factura.notas)
        notes_card = QFrame()
        notes_card.setObjectName("panel")
        notes_layout = QVBoxLayout(notes_card)
        notes_layout.setContentsMargins(20, 20, 20, 20)
        notes_layout.setSpacing(12)
        notes_title = QLabel("Notas y contexto")
        notes_title.setObjectName("sectionTitle")
        notes_layout.addWidget(notes_title)
        notes_layout.addWidget(self.notes_input)
        form_layout.addWidget(notes_card)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghostButton")
        cancel.clicked.connect(self.close_panel)
        save = QPushButton("Guardar borrador")
        save.setObjectName("warningButton")
        save.clicked.connect(self.save)
        emit = QPushButton("Emitir factura")
        emit.setObjectName("accentButton")
        emit.clicked.connect(lambda: self.save(emit=True))
        actions.addStretch(1)
        actions.addWidget(cancel)
        actions.addWidget(save)
        actions.addWidget(emit)
        form_layout.addLayout(actions)
        form_layout.addStretch(1)

        preview_panel = QFrame()
        preview_panel.setObjectName("invoicePreview")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(24, 24, 24, 24)
        preview_layout.setSpacing(14)
        preview_header = QLabel("Vista previa")
        preview_header.setObjectName("sectionTitle")
        preview_layout.addWidget(preview_header)
        self.preview = QLabel()
        self.preview.setObjectName("previewText")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview.setWordWrap(True)
        self.preview.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
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

    def update_auto_email_state(self) -> None:
        configured = self.email_service is not None and self.email_service.is_configured()
        has_email = bool(self.email_input.text().strip())
        self.auto_email_check.setEnabled(configured and has_email)
        if not configured:
            self.auto_email_check.setToolTip("Configura SMTP en .env para enviar emails automaticamente.")
        elif not has_email:
            self.auto_email_check.setToolTip("Indica el email del cliente para activar el envio automatico.")
        else:
            self.auto_email_check.setToolTip("Genera el PDF y envia la factura automaticamente al emitir.")
        if not self.auto_email_check.isEnabled():
            self.auto_email_check.setChecked(False)

    def add_line(self, line: LineaFactura | None = None) -> None:
        row = self.lines_table.rowCount()
        self.lines_table.insertRow(row)
        values = [
            line.descripcion if line else "",
            str(line.cantidad if line else 1),
            str(line.precio_unitario if line else "0.00"),
            str((line.iva * 100) if line and line.iva <= 1 else (line.iva if line else 21)),
            "",
        ]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            if column == 4:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.lines_table.setItem(row, column, item)
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
        lines: list[LineaFactura] = []
        for row in range(self.lines_table.rowCount()):
            desc = (self.lines_table.item(row, 0).text() if self.lines_table.item(row, 0) else "").strip()
            qty = Decimal(self.lines_table.item(row, 1).text() if self.lines_table.item(row, 1) else "0")
            price = Decimal(self.lines_table.item(row, 2).text() if self.lines_table.item(row, 2) else "0")
            iva = Decimal(self.lines_table.item(row, 3).text() if self.lines_table.item(row, 3) else "21") / Decimal("100")
            if desc and qty > 0 and price >= 0:
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
        line_text = "\n".join(
            f"- {line.descripcion} | {line.cantidad} ud. | {_money(line.precio_unitario)}"
            for line in lines
        )
        notas = self.notes_input.toPlainText().strip()
        self.preview.setText(
            "FACTURA\n"
            f"{self.factura.numero if self.factura else 'FAC-XXXX'}\n\n"
            f"Fecha: {self.date_input.date().toPython().isoformat()}\n"
            f"Receptor: {self.client_input.text() or 'Receptor'}\n\n"
            f"NIF/CIF: {self.nif_input.text() or '-'}\n"
            f"Email: {self.email_input.text() or '-'}\n"
            f"Direccion: {self.address_input.text() or '-'}\n\n"
            f"{line_text or 'Añade líneas para ver la previsualización'}\n\n"
            f"Base imponible: {_money(totals.subtotal)}\n"
            f"IVA: {_money(totals.iva)}\n"
            f"TOTAL: {_money(totals.total)}"
            f"{f'\\n\\nNotas:\\n{notas}' if notas else ''}"
        )

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
                saved = self.controller.emit_factura(saved.id)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return
        if emit and self.auto_email_check.isChecked() and self.email_service is not None:
            try:
                path = generate_invoice_pdf(saved, Path.cwd() / "exports" / "pdf")
                self.email_service.send_invoice(saved, path)
            except Exception as exc:
                QMessageBox.warning(
                    self,
                    "Factura emitida",
                    f"La factura se emitio, pero no se pudo enviar el email:\n{exc}",
                )
            else:
                QMessageBox.information(
                    self,
                    "Email enviado",
                    f"Factura enviada a {saved.cliente_email}.",
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
        totals = calculate_invoice(factura.lineas, amount_paid=factura.importe_pagado)
        detail = QMessageBox(self)
        detail.setWindowTitle(f"Factura {factura.numero}")
        detail.setText(
            f"{factura.numero}\n\n"
            f"Cliente: {factura.cliente_nombre}\n"
            f"Fecha: {factura.fecha.isoformat()}\n"
            f"Estado: {factura.estado.value}\n\n"
            f"Base imponible: {_money(totals.subtotal)}\n"
            f"IVA: {_money(totals.iva)}\n"
            f"Total: {_money(totals.total)}"
        )
        edit = detail.addButton("Editar", QMessageBox.ButtonRole.ActionRole)
        emit = detail.addButton("Emitir", QMessageBox.ButtonRole.ActionRole)
        pay = detail.addButton("Registrar cobro", QMessageBox.ButtonRole.ActionRole)
        email = detail.addButton("Enviar email", QMessageBox.ButtonRole.ActionRole)
        verifactu = detail.addButton("Verifactu", QMessageBox.ButtonRole.ActionRole)
        pdf = detail.addButton("PDF", QMessageBox.ButtonRole.ActionRole)
        cancel = detail.addButton("Anular", QMessageBox.ButtonRole.DestructiveRole)
        delete = detail.addButton("Eliminar", QMessageBox.ButtonRole.DestructiveRole)
        detail.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
        detail.exec()
        clicked = detail.clickedButton()
        try:
            if clicked == edit:
                self.edit_invoice(factura)
            elif clicked == emit:
                self.emit_invoice(factura)
            elif clicked == pay:
                self.register_payment(factura)
            elif clicked == email:
                self.send_invoice_email(factura)
            elif clicked == verifactu:
                self.register_verifactu(factura)
            elif clicked == pdf:
                self.generate_pdf(factura)
            elif clicked == cancel:
                self.factura_controller.cancel_factura(factura.id)
                self.render_invoices()
            elif clicked == delete:
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
        path = generate_invoice_pdf(factura, Path.cwd() / "exports" / "pdf")
        QMessageBox.information(self, "PDF generado", f"Archivo generado:\n{path}")
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        return path

    def send_invoice_email(self, factura: Factura) -> None:
        path = generate_invoice_pdf(factura, Path.cwd() / "exports" / "pdf")
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

        t_zone = QFrame()
        t_zone.setObjectName("dropZone")
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

        p_zone = QFrame()
        p_zone.setObjectName("dropZone")
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

        self._ocr_current_source = source
        self._show_processing(source)

        worker = OcrWorker(path)
        worker.finished.connect(self._on_ocr_done)
        worker.error.connect(self._on_ocr_error)
        self._ocr_worker = worker
        worker.start()

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
QLabel, QCheckBox {
    background: transparent;
}
QMessageBox {
    background: #ffffff;
}
"""
