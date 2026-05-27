"""Ventana principal estilo Automalize para escritorio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, QSettings, Qt, QUrl
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
from app.services.ocr_stub import OcrStubService
from app.services.pdf_service import generate_invoice_pdf
from app.services.verifactu_service import VerifactuService
from app.views.clientes_view import ClientesView
from app.views.productos_view import ProductosView


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
        factura: Factura | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller
        self.on_close = on_close
        self.on_saved = on_saved
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
        self.address_input.textChanged.connect(self.update_preview)
        self.notes_input.textChanged.connect(self.update_preview)
        self.date_input.dateChanged.connect(self.update_preview)
        self.lines_table.itemChanged.connect(self.update_preview)
        self.update_preview()

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
                self.controller.emit_factura(saved.id)
        except Exception as exc:
            QMessageBox.critical(self, "No se pudo guardar", str(exc))
            return
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
        self.ocr_service = OcrStubService()
        self.current_filter = "Todas"
        self.current_search = ""
        self.invoice_overlay: ModalOverlay | None = None
        self.voice_overlay: ModalOverlay | None = None
        self.last_persistent_nav_row = 0
        self.sidebar_collapsed = False
        self.sidebar_width_expanded = 244
        self.settings = QSettings("Automalize", "Desktop")
        saved_accent = str(self.settings.value("theme/accent", "Indigo"))
        self.selected_theme_accent = saved_accent if saved_accent in ACCENT_THEMES else "Indigo"
        self.theme_dark_mode = bool(self.settings.value("theme/darkMode", False, type=bool))

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
        help_button = QPushButton("?")
        help_button.setObjectName("topIconButton")
        nav_layout.addWidget(help_button)
        self.dark_mode_button = QPushButton()
        self.dark_mode_button.setObjectName("topIconButton")
        self.dark_mode_button.setCheckable(True)
        self.dark_mode_button.clicked.connect(self.set_theme_dark_mode)
        nav_layout.addWidget(self.dark_mode_button)
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
        self.apply_theme(save=False)

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

    def apply_theme(self, save: bool = True) -> None:
        self.setStyleSheet(build_app_stylesheet(self.selected_theme_accent, self.theme_dark_mode))
        if save:
            self.settings.setValue("theme/accent", self.selected_theme_accent)
            self.settings.setValue("theme/darkMode", self.theme_dark_mode)
        self._sync_theme_controls()

    def _sync_theme_controls(self) -> None:
        if hasattr(self, "dark_mode_button"):
            self.dark_mode_button.blockSignals(True)
            self.dark_mode_button.setChecked(self.theme_dark_mode)
            self.dark_mode_button.setText("☀" if self.theme_dark_mode else "☾")
            self.dark_mode_button.setToolTip("Cambiar a modo claro" if self.theme_dark_mode else "Cambiar a modo oscuro")
            self.dark_mode_button.blockSignals(False)

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
        theme_surface = "#1b2033" if self.theme_dark_mode else "#ffffff"
        theme_text = "#f4f7ff" if self.theme_dark_mode else "#181a2f"
        theme_border = "#31384f" if self.theme_dark_mode else "#e2e5f1"
        for name, accent in ACCENT_THEMES.items():
            color = accent["primary"]
            button = QPushButton(name + (" (default)" if name == "Indigo" else ""))
            button.setMinimumSize(168, 98)
            button.setCheckable(True)
            button.setChecked(name == self.selected_theme_accent)
            button.setObjectName("themeAccentButton")
            button.clicked.connect(lambda checked=False, selected=name: self.select_theme_accent(selected))
            button.setStyleSheet(
                "QPushButton {"
                f"border: 1px solid {color if name == self.selected_theme_accent else theme_border};"
                "border-radius: 8px; padding: 54px 12px 12px 12px; text-align: left; font-weight: 700;"
                f"background: {theme_surface}; color: {theme_text};"
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
        if accent not in ACCENT_THEMES:
            return
        self.selected_theme_accent = accent
        self.apply_theme()
        self.show_theme_visual()

    def set_theme_dark_mode(self, enabled: bool) -> None:
        self.theme_dark_mode = enabled
        self.apply_theme()
        if self.stack.currentWidget() is self.theme_page:
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
                self.factura_controller.emit_factura(factura.id)
                self.render_invoices()
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

    def register_verifactu(self, factura: Factura) -> None:
        result = self.verifactu_service.create(factura)
        self.factura_controller.attach_verifactu_result(factura.id, result.uuid, result.url, result.qr)
        QMessageBox.information(self, "Verifactu", "Factura registrada en Verifactu.")

    def show_import(self) -> None:
        self.navbar_title.setText("Importar Factura")
        self.stack.setCurrentWidget(self.import_page)
        layout = self.clear_page(self.import_page)
        self.page_header(
            layout,
            "Importar Factura",
            "QR, foto de ticket o PDF adaptado al escritorio. Procesamos los datos y creamos un borrador listo para revisar.",
        )
        panel = QFrame()
        panel.setObjectName("panel")
        inner = QVBoxLayout(panel)
        inner.setContentsMargins(18, 18, 18, 18)
        inner.setSpacing(14)
        header = QHBoxLayout()
        header.setSpacing(12)
        upload_icon = QLabel("↑")
        upload_icon.setObjectName("uploadIcon")
        header_text = QVBoxLayout()
        header_text.setSpacing(4)
        header_title = QLabel("Arrastra un archivo o elige el origen")
        header_title.setObjectName("sectionTitle")
        header_sub = QLabel("PNG, JPG, PDF hasta 15 MB. Tambien admitimos codigos QR VeriFactu directamente.")
        header_sub.setObjectName("viewSubtitle")
        header_sub.setWordWrap(True)
        header_text.addWidget(header_title)
        header_text.addWidget(header_sub)
        browse = QPushButton("Examinar")
        browse.setObjectName("primaryButton")
        browse.setMinimumWidth(120)
        browse.clicked.connect(lambda: self.import_file("PDF e imagenes (*.pdf *.png *.jpg *.jpeg *.webp)"))
        header.addWidget(upload_icon)
        header.addLayout(header_text, 1)
        header.addWidget(browse, 0, Qt.AlignmentFlag.AlignTop)
        inner.addLayout(header)

        cards = QGridLayout()
        cards.setHorizontalSpacing(10)
        cards.setVerticalSpacing(10)
        import_sources = [
            ("▦", "Subir imagen QR", "Lee facturas en formato VeriFactu / Factura-e directamente del codigo.", "purple", "Imágenes (*.png *.jpg *.jpeg *.webp)"),
            ("▧", "Subir ticket", "Foto del ticket: extraemos importes, conceptos y NIF cuando exista.", "orange", "Imágenes (*.png *.jpg *.jpeg *.webp)"),
            ("▣", "Subir PDF", "Adaptamos el PDF al esquema del escritorio y lo convertimos en borrador.", "green", "PDF (*.pdf)"),
        ]
        for index, (icon, title, subtitle, accent, file_filter) in enumerate(import_sources):
            card = QuickActionCard(icon, title, subtitle, accent, lambda flt=file_filter: self.import_file(flt))
            card.setObjectName("importCard")
            cards.addWidget(card, index // 2, index % 2)
        inner.addLayout(cards)
        layout.addWidget(panel)

        layout.addWidget(self.section_label("Importaciones recientes"))
        recent = QFrame()
        recent.setObjectName("panel")
        recent_layout = QVBoxLayout(recent)
        recent_layout.setContentsMargins(16, 12, 16, 12)
        recent_layout.setSpacing(8)
        for name, meta, state in [
            ("ticket-restaurante-26-05.jpg", "1.2 MB · 7 lineas detectadas · hace 4 min", "LISTO"),
            ("factura-telefonica-may26.pdf", "286 KB · 12 lineas detectadas · hace 2 h", "LISTO"),
            ("qr-verifactu-0xa3f1.png", "88 KB · 4 lineas detectadas · ayer", "REVISAR"),
        ]:
            row = QHBoxLayout()
            row.setSpacing(10)
            file_name = QLabel(f"{name}\n{meta}")
            file_name.setObjectName("recentImport")
            file_name.setWordWrap(True)
            badge = QLabel(state)
            badge.setObjectName("successBadge" if state == "LISTO" else "warningBadge")
            open_btn = QPushButton("Abrir")
            open_btn.setObjectName("ghostButton")
            open_btn.setMinimumWidth(80)
            row.addWidget(file_name, 1)
            row.addWidget(badge)
            row.addWidget(open_btn)
            recent_layout.addLayout(row)
        layout.addWidget(recent)
        layout.addStretch(1)

    def import_file(self, file_filter: str) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar factura", str(Path.home()), file_filter)
        if not path:
            return
        draft = self.ocr_service.prepare_import(path)
        self.factura_controller.create_factura(
            cliente_nombre=draft.cliente_nombre,
            fecha=date.today(),
            lineas=[LineaFactura(draft.descripcion, Decimal("1"), Decimal("0.00"))],
            notas=f"OCR pendiente. Archivo origen: {draft.source_path}",
        )
        QMessageBox.information(
            self,
            "Importacion preparada",
            "Se ha creado un borrador revisable. El OCR real queda pendiente de implementar.",
        )
        self.navigation.setCurrentRow(1)

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

ACCENT_THEMES = {
    "Indigo": {
        "primary": "#6256f4",
        "hover": "#7469ff",
        "soft": "#ecebff",
        "border": "#cfcaff",
        "text": "#4b42c6",
    },
    "Esmeralda": {
        "primary": "#1ea97c",
        "hover": "#26bd8d",
        "soft": "#ddf8ef",
        "border": "#9be8cf",
        "text": "#157b5c",
    },
    "Ambar": {
        "primary": "#e4a014",
        "hover": "#f0ae24",
        "soft": "#fff2d4",
        "border": "#f4d184",
        "text": "#9a6800",
    },
    "Coral": {
        "primary": "#e65c74",
        "hover": "#f06f85",
        "soft": "#fff0f3",
        "border": "#f5bbc6",
        "text": "#b83e55",
    },
    "Cielo": {
        "primary": "#3c8dde",
        "hover": "#4d9ded",
        "soft": "#e8f3ff",
        "border": "#b7d8f7",
        "text": "#246fb7",
    },
    "Grafito": {
        "primary": "#5d6284",
        "hover": "#707697",
        "soft": "#eef0f7",
        "border": "#c9cedd",
        "text": "#464b69",
    },
}


def build_app_stylesheet(accent_name: str, dark_mode: bool) -> str:
    accent = ACCENT_THEMES.get(accent_name, ACCENT_THEMES["Indigo"])
    primary = accent["primary"]
    hover = accent["hover"]
    soft = accent["soft"]
    border = accent["border"]
    accent_text = accent["text"]
    common_overrides = f"""
QLabel#brandAvatar, QLabel#clientAvatar, QFrame#chartBarStrong {{
    background: {primary};
    color: #ffffff;
}}
QListWidget#navigation::item:selected {{
    background: {primary};
    color: #ffffff;
}}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {primary};
}}
QPushButton, QPushButton#primaryButton {{
    background: {primary};
    color: #ffffff;
}}
QPushButton:hover, QPushButton#primaryButton:hover {{
    background: {hover};
}}
QPushButton#filterActive, QPushButton#warningButton {{
    background: {soft};
    border: 1px solid {border};
    color: {accent_text};
}}
QFrame#quickActionCard:hover, QFrame#importCard:hover {{
    border: 1px solid {border};
}}
QLabel#voiceRedirectHandle, QLabel#uploadIcon, QLabel#voicePulse {{
    color: {primary};
}}
QLabel#uploadIcon, QLabel#voicePulse, QLabel#statIcon_purple, QLabel#quickIcon_purple {{
    background: {soft};
    color: {primary};
}}
QAbstractItemView {{
    selection-background-color: {soft};
}}
QTableWidget::item:selected {{
    background: {soft};
    color: {accent_text};
}}
QCheckBox#themeDarkToggle::indicator:checked {{
    background: {primary};
    border: 1px solid {primary};
}}
QPushButton#rowEditButton {{
    background: transparent;
    border: 1px solid {border};
    color: {accent_text};
    padding: 6px 10px;
}}
QPushButton#rowEditButton:hover {{
    background: {soft};
}}
"""
    if not dark_mode:
        return APP_STYLESHEET + common_overrides + """
QFrame#clientsToolbar {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
}
QLabel#emptyState {
    background: #ffffff;
    border: 1px solid #e2e5f1;
    border-radius: 8px;
    color: #747894;
    font-size: 15px;
}
"""

    dark_overrides = f"""
QMainWindow {{
    background: #101421;
}}
QWidget {{
    color: #eef2ff;
}}
QFrame#content, QScrollArea, QWidget#page, QStackedWidget, QDialog {{
    background: #101421;
}}
QFrame#sidebar {{
    background: #0a0d18;
    border-right: 1px solid #20263a;
}}
QFrame#navbar, QFrame#panel, QFrame#statCard, QFrame#invoiceModalCard,
QFrame#voiceRedirectCard, QFrame#quickActionCard, QFrame#importCard,
QFrame#clientsToolbar {{
    background: #171c2b;
    border: 1px solid #2c344b;
}}
QLabel#navbarTitle, QLabel#viewTitle, QLabel#dialogTitle, QLabel#voiceRedirectTitle,
QLabel#sectionTitle, QLabel#statValue, QLabel#quickTitle, QLabel#clientName,
QLabel#activityItem, QLabel#recentImport, QLabel#draftLine {{
    color: #f4f7ff;
}}
QLabel#viewSubtitle, QLabel#statTitle, QLabel#quickSubtitle, QLabel#barValue,
QLabel#barMonth, QLabel#clientMeta, QLabel#clientArrow, QLabel#clientFooter,
QLabel#sidebarSummary, QLabel#sideSection, QLabel#userCardText {{
    color: #aab2ca;
}}
QLabel#clientDetail, QLabel#previewText, QLabel#transcriptBox, QLabel#suggestionChip {{
    color: #dbe2f5;
}}
QLineEdit, QDateEdit, QComboBox, QPlainTextEdit {{
    background: #111827;
    border: 1px solid #323a52;
    color: #eef2ff;
    selection-background-color: {primary};
}}
QLineEdit#pillSearch {{
    background: #111827;
}}
QLineEdit#sidebarSearch {{
    background: #080b14;
    color: #dfe6f8;
    border: 1px solid #273047;
}}
QPushButton#navToggleButton, QPushButton#topIconButton,
QPushButton#ghostButton, QPushButton#filterButton {{
    background: #171c2b;
    border: 1px solid #323a52;
    color: #dfe6f8;
}}
QPushButton#navToggleButton:hover, QPushButton#topIconButton:hover,
QPushButton#ghostButton:hover, QPushButton#filterButton:hover {{
    background: #22293d;
}}
QPushButton#sideButton {{
    background: transparent;
    color: #dfe6f8;
}}
QPushButton#sideButton:hover, QListWidget#navigation::item:hover {{
    background: #1a2032;
}}
QListWidget#navigation {{
    color: #dfe6f8;
}}
QFrame#userCard {{
    border-top: 1px solid #20263a;
}}
QTableWidget#dataTable, QTableWidget, QTableWidget#clientsTable {{
    background: #171c2b;
    alternate-background-color: #141a29;
    border: 1px solid #2c344b;
    color: #eef2ff;
    gridline-color: #242c40;
}}
QHeaderView::section, QTableCornerButton::section {{
    background: #121827;
    color: #aab2ca;
    border-bottom: 1px solid #2c344b;
}}
QFrame#invoicePreview, QLabel#transcriptBox, QLabel#suggestionChip,
QLabel#emptyState {{
    background: #141a29;
    border: 1px solid #2c344b;
    color: #dbe2f5;
}}
QFrame#themeDivider, QFrame#clientDivider {{
    background: #2c344b;
}}
QMessageBox {{
    background: #171c2b;
}}
QCheckBox#themeDarkToggle::indicator {{
    background: #2c344b;
    border: 1px solid #3a435c;
}}
"""
    return APP_STYLESHEET + common_overrides + dark_overrides


APP_STYLESHEET = """
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
