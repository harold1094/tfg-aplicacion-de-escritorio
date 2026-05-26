"""Ventana principal estilo Automalize para escritorio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
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
        text.addWidget(value_label)
        text.addWidget(title_label)
        layout.addLayout(text, 1)


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
        self.setMinimumSize(980, 720)
        self.setMaximumWidth(1180)

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(18)

        form_panel = QFrame()
        form_panel.setObjectName("panel")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setSpacing(16)

        heading_row = QHBoxLayout()
        title = QLabel("Editar factura" if factura else "Nueva factura")
        title.setObjectName("dialogTitle")
        close_btn = QPushButton("Cerrar")
        close_btn.setObjectName("ghostButton")
        close_btn.clicked.connect(self.close_panel)
        heading_row.addWidget(title)
        heading_row.addStretch(1)
        heading_row.addWidget(close_btn)
        form_layout.addLayout(heading_row)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
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

        general = QFormLayout()
        general.setSpacing(10)
        general.addRow("Fecha de emisión", self.date_input)
        general.addRow("Tipo", self.type_input)
        general.addRow("Nombre / razón social", self.client_input)
        general.addRow("NIF / CIF", self.nif_input)
        general.addRow("Dirección", self.address_input)
        general.addRow("Email", self.email_input)
        form_layout.addLayout(general)

        lines_label = QLabel("Líneas de factura")
        lines_label.setObjectName("sectionTitle")
        form_layout.addWidget(lines_label)

        self.lines_table = QTableWidget(0, 5)
        self.lines_table.setHorizontalHeaderLabels(["Descripción", "Cantidad", "Precio", "IVA %", "Subtotal"])
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.lines_table.setMinimumHeight(180)
        form_layout.addWidget(self.lines_table)

        add_line = QPushButton("+ Añadir línea")
        add_line.setObjectName("ghostButton")
        add_line.clicked.connect(lambda: self.add_line())
        form_layout.addWidget(add_line)

        self.notes_input = QPlainTextEdit()
        self.notes_input.setPlaceholderText("Notas adicionales...")
        self.notes_input.setMaximumHeight(80)
        if factura:
            self.notes_input.setPlainText(factura.notas)
        form_layout.addWidget(self.notes_input)

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

        preview_panel = QFrame()
        preview_panel.setObjectName("invoicePreview")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(24, 24, 24, 24)
        self.preview = QLabel()
        self.preview.setObjectName("previewText")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.preview.setWordWrap(True)
        preview_layout.addWidget(self.preview)

        root.addWidget(form_panel, 3)
        root.addWidget(preview_panel, 2)

        if factura:
            for linea in factura.lineas:
                self.add_line(linea)
        else:
            self.add_line()

        self.client_input.textChanged.connect(self.update_preview)
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
        for row, line in enumerate(lines):
            item = self.lines_table.item(row, 4)
            if item:
                item.setText(_money(line.cantidad * line.precio_unitario))
        line_text = "\n".join(
            f"{line.descripcion}  x{line.cantidad}  {_money(line.precio_unitario)}" for line in lines
        )
        self.preview.setText(
            "FACTURA\n"
            f"FAC-XXXX\n\n"
            f"Fecha: {self.date_input.date().toPython().isoformat()}\n"
            f"Receptor: {self.client_input.text() or 'Receptor'}\n\n"
            f"{line_text or 'Añade líneas para ver la previsualización'}\n\n"
            f"Base imponible: {_money(totals.subtotal)}\n"
            f"IVA: {_money(totals.iva)}\n"
            f"TOTAL: {_money(totals.total)}"
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
    def __init__(self, parent: QWidget, panel: InvoiceFormPanel) -> None:
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

        central = QWidget()
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(22, 24, 22, 20)
        side_layout.setSpacing(14)

        logo = QLabel("F  Automalize")
        logo.setObjectName("logo")
        side_layout.addWidget(logo)
        context_label = QLabel("Escritorio profesional de facturacion")
        context_label.setObjectName("sidebarSummary")
        context_label.setWordWrap(True)
        side_layout.addWidget(context_label)
        side_layout.addWidget(self._side_label("Principal"))

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.routes = [
            ("Dashboard", self.show_dashboard),
            ("Facturas", self.show_invoices),
            ("Importar Factura", self.show_import),
            ("Factura por Voz", self.show_voice),
            ("Clientes", lambda: self.set_static_page(4, "Clientes")),
            ("Productos", lambda: self.set_static_page(5, "Productos")),
        ]
        for label, _ in self.routes:
            self.navigation.addItem(QListWidgetItem(label))
        self.navigation.currentRowChanged.connect(self.handle_nav)
        side_layout.addWidget(self.navigation, 1)
        side_layout.addWidget(self._side_label("Sistema"))
        theme = QPushButton("Tema visual")
        theme.setObjectName("sideButton")
        theme.clicked.connect(lambda: QMessageBox.information(self, "Tema", "Tema visual profesional activo."))
        side_layout.addWidget(theme)
        user_card = QFrame()
        user_card.setObjectName("userCard")
        user_layout = QVBoxLayout(user_card)
        user_layout.setContentsMargins(16, 16, 16, 16)
        user_layout.setSpacing(4)
        user_name = QLabel("Admin conectado" if session else "Modo local")
        user_name.setObjectName("userCardTitle")
        user_email = QLabel(session.email if session else "Sin Supabase")
        user_email.setObjectName("userCardText")
        user_layout.addWidget(user_name)
        user_layout.addWidget(user_email)
        side_layout.addWidget(user_card)

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
        nav_layout.setContentsMargins(28, 0, 28, 0)
        nav_layout.addWidget(self.navbar_title)
        nav_layout.addStretch(1)
        self.global_search = QLineEdit()
        self.global_search.setPlaceholderText("Buscar...")
        self.global_search.setObjectName("pillSearch")
        self.global_search.textChanged.connect(self.on_global_search)
        nav_layout.addWidget(self.global_search)

        self.stack = QStackedWidget()
        self.dashboard_page = self._scroll_page()
        self.invoices_page = self._scroll_page()
        self.import_page = self._scroll_page()
        self.voice_page = self._scroll_page()
        self.stack.addWidget(self.dashboard_page)
        self.stack.addWidget(self.invoices_page)
        self.stack.addWidget(self.import_page)
        self.stack.addWidget(self.voice_page)
        self.stack.addWidget(ClientesView(self.cliente_controller))
        self.stack.addWidget(ProductosView(self.producto_controller))

        content_layout.addWidget(navbar)
        content_layout.addWidget(self.stack, 1)
        shell.addWidget(sidebar)
        shell.addWidget(content, 1)
        self.setCentralWidget(central)
        self.setStyleSheet(APP_STYLESHEET)

        self.navigation.setCurrentRow(0)

    def _scroll_page(self) -> QScrollArea:
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        body.setObjectName("page")
        QVBoxLayout(body).setContentsMargins(28, 28, 28, 28)
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
        self.routes[row][1]()

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
        heading = QLabel(title)
        heading.setObjectName("viewTitle")
        sub = QLabel(subtitle)
        sub.setObjectName("viewSubtitle")
        text.addWidget(heading)
        text.addWidget(sub)
        row.addLayout(text, 1)
        for action in actions or []:
            row.addWidget(action)
        layout.addLayout(row)

    def show_dashboard(self) -> None:
        self.navbar_title.setText("Dashboard")
        self.stack.setCurrentWidget(self.dashboard_page)
        layout = self.clear_page(self.dashboard_page)
        new_btn = QPushButton("+ Nueva Factura")
        new_btn.clicked.connect(self.new_invoice)
        self.page_header(layout, "Dashboard y Analítica", "KPIs, proyección simple y últimas facturas.", [new_btn])

        rows = self.factura_controller.list_invoice_rows()
        issued = [r for r in rows if r["estado"] != EstadoFactura.BORRADOR.value]
        cash_flow = sum((Decimal(str(r["total"])) for r in issued), Decimal("0"))
        drafts = [r for r in rows if r["estado"] == EstadoFactura.BORRADOR.value]
        pending = sum((Decimal(str(r["total"])) for r in drafts), Decimal("0"))
        clients = {r["cliente"] for r in rows}
        avg = cash_flow / max(len(clients), 1)
        projected = cash_flow / Decimal(max(len(rows), 1)) * Decimal("1.15")

        grid = QGridLayout()
        grid.setSpacing(16)
        cards = [
            ("EUR", "Flujo de Caja (Emitido)", _money(cash_flow), "purple"),
            ("CLK", f"Borradores ({len(drafts)})", _money(pending), "yellow"),
            ("USR", "Media por Cliente", _money(avg), "blue"),
            ("UP", "Proyección Próx. Mes", _money(projected), "green"),
        ]
        for i, card in enumerate(cards):
            grid.addWidget(StatCard(*card), i // 4, i % 4)
        layout.addLayout(grid)

        actions = QFrame()
        actions.setObjectName("panel")
        actions_layout = QHBoxLayout(actions)
        actions_layout.addWidget(QLabel("Acciones rápidas"))
        for label, slot, name in [
            ("Crear Factura", self.new_invoice, "primaryButton"),
            ("Importar QR/PDF", self.show_import, "accentButton"),
            ("Exportar Todo", self.export_all, "ghostButton"),
        ]:
            btn = QPushButton(label)
            btn.setObjectName(name)
            btn.clicked.connect(slot)
            actions_layout.addWidget(btn)
        actions_layout.addStretch(1)
        layout.addWidget(actions)

        layout.addWidget(self._invoice_table(rows[:5], compact=True))
        layout.addStretch(1)

    def show_invoices(self) -> None:
        self.navbar_title.setText("Facturas")
        self.stack.setCurrentWidget(self.invoices_page)
        self.render_invoices()

    def render_invoices(self) -> None:
        layout = self.clear_page(self.invoices_page)
        export_btn = QPushButton("Exportar")
        export_btn.setObjectName("ghostButton")
        export_btn.clicked.connect(self.export_all)
        new_btn = QPushButton("+ Nueva Factura")
        new_btn.clicked.connect(self.new_invoice)
        self.page_header(layout, "Facturas", "Listado, filtros, búsqueda, acciones y generación de borradores.", [export_btn, new_btn])

        filters = QHBoxLayout()
        for name in ["Todas", "Borrador", "Emitidas", "Anuladas"]:
            btn = QPushButton(name)
            btn.setObjectName("filterActive" if name == self.current_filter else "filterButton")
            btn.clicked.connect(lambda checked=False, value=name: self.set_filter(value))
            filters.addWidget(btn)
        filters.addStretch(1)
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
        columns = ["Nº Factura", "Receptor", "Fecha", "Estado", "Total", "Acciones"]
        table = QTableWidget(0, len(columns))
        table.setObjectName("dataTable")
        table.setHorizontalHeaderLabels(columns)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row["numero"], row["cliente"], row["fecha"], row["estado"], _money(row["total"]), "Ver / Editar"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 4:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_index, column, item)
        table.cellDoubleClicked.connect(lambda row, _col: self.view_invoice(rows[row]["numero"]))
        table.setMinimumHeight(260 if compact else 420)
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

    def on_invoice_saved(self) -> None:
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
        self.page_header(layout, "Importar Factura", "QR, foto de ticket o PDF adaptado al escritorio.")
        panel = QFrame()
        panel.setObjectName("panel")
        inner = QVBoxLayout(panel)
        inner.addWidget(QLabel("Selecciona un archivo para crear un borrador con datos extraídos o revisados."))
        for label, file_filter in [("Subir imagen QR", "Imágenes (*.png *.jpg *.jpeg *.webp)"), ("Subir ticket", "Imágenes (*.png *.jpg *.jpeg *.webp)"), ("Subir PDF", "PDF (*.pdf)")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, flt=file_filter: self.import_file(flt))
            inner.addWidget(btn)
        layout.addWidget(panel)
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
        self.navbar_title.setText("Facturación por Voz")
        self.stack.setCurrentWidget(self.voice_page)
        layout = self.clear_page(self.voice_page)
        self.page_header(layout, "Facturación por Voz", "Dicta tu factura en lenguaje natural con el bot de Telegram.")
        panel = QFrame()
        panel.setObjectName("panel")
        inner = QVBoxLayout(panel)
        for text in [
            "1. Abre el bot de Telegram.",
            "2. Dicta o escribe cliente, concepto, importe y fecha.",
            "3. Revisa la factura generada y guárdala en tu cuenta.",
        ]:
            inner.addWidget(QLabel(text))
        open_bot = QPushButton("Abrir Bot de Facturación")
        open_bot.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://web.telegram.org/k/#@facturacionAutomaticaBot")))
        inner.addWidget(open_bot)
        layout.addWidget(panel)
        layout.addStretch(1)

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
QMainWindow {
    background: #eef0fb;
}
QWidget {
    background: transparent;
    color: #1e2445;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}
QFrame#sidebar {
    background: #20295a;
    border-right: 1px solid #cfd5f5;
    min-width: 260px;
    max-width: 260px;
}
QLabel#logo {
    color: #f6f4ff;
    font-size: 30px;
    font-weight: 800;
    padding: 10px 2px 6px 2px;
}
QLabel#sidebarSummary {
    color: #e3e7ff;
    font-size: 13px;
    line-height: 1.4;
    padding: 0 2px 14px 2px;
}
QLabel#sideSection {
    color: #d9defe;
    font-size: 11px;
    font-weight: 700;
    padding: 12px 8px 6px 8px;
    letter-spacing: 0.12em;
}
QListWidget#navigation {
    background: transparent;
    border: none;
    color: #f5f7ff;
    outline: none;
}
QListWidget#navigation::item {
    padding: 14px 18px;
    border-radius: 14px;
    margin: 4px 0;
    font-weight: 600;
}
QListWidget#navigation::item:selected {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6f5ef1, stop:1 #4b63eb);
    color: #ffffff;
}
QListWidget#navigation::item:hover {
    background: rgba(255, 255, 255, 0.12);
    color: #ffffff;
}
QFrame#content, QScrollArea, QWidget#page, QStackedWidget {
    background: #eef0fb;
}
QFrame#navbar {
    background: rgba(255, 255, 255, 0.88);
    border-bottom: 1px solid #dfe1fb;
    min-height: 76px;
    max-height: 76px;
}
QLabel#navbarTitle {
    font-size: 22px;
    font-weight: 700;
    color: #493ec2;
}
QLabel#viewTitle {
    font-size: 34px;
    font-weight: 800;
    color: #202858;
}
QLabel#viewSubtitle {
    color: #72779a;
    font-size: 15px;
}
QFrame#panel, QFrame#statCard {
    background: #ffffff;
    border: 1px solid #e0e1fb;
    border-radius: 20px;
}
QFrame#invoiceModalCard {
    background: #f5f6ff;
    border: 1px solid #dfe2fa;
    border-radius: 24px;
}
QFrame#invoicePreview {
    background: #f7f6ff;
    color: #23264a;
    border: 1px solid #e0e1fb;
    border-radius: 20px;
}
QLabel#previewText {
    color: #2d315a;
    font-family: "Segoe UI";
    font-size: 13px;
}
QLabel#dialogTitle, QLabel#sectionTitle {
    font-size: 22px;
    font-weight: 700;
    color: #26306c;
}
QLabel#statValue {
    font-size: 28px;
    font-weight: 800;
    color: #202858;
}
QLabel#statTitle {
    color: #787da3;
    font-size: 13px;
}
QLabel#statIcon_purple, QLabel#statIcon_yellow, QLabel#statIcon_blue, QLabel#statIcon_green {
    border-radius: 16px;
    min-width: 54px;
    min-height: 54px;
    qproperty-alignment: AlignCenter;
    font-weight: 800;
}
QLabel#statIcon_purple { background: #ece9ff; color: #5747d9; }
QLabel#statIcon_yellow { background: #fff3d8; color: #b7791f; }
QLabel#statIcon_blue { background: #e4ecff; color: #3658dd; }
QLabel#statIcon_green { background: #ddf8ea; color: #1a8e60; }
QLineEdit, QDateEdit, QComboBox, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #d8dbfa;
    border-radius: 12px;
    color: #202858;
    padding: 10px 12px;
    selection-background-color: #5747d9;
}
QLineEdit#pillSearch {
    border-radius: 22px;
    min-width: 300px;
    min-height: 24px;
    padding-left: 16px;
    background: #ffffff;
}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #5747d9;
}
QPushButton {
    background: #5747d9;
    color: white;
    border: none;
    border-radius: 12px;
    padding: 11px 18px;
    font-weight: 700;
}
QPushButton:hover {
    background: #6657e1;
}
QPushButton#accentButton {
    background: #198163;
}
QPushButton#warningButton {
    background: #e3e8ff;
    color: #4b42c6;
}
QPushButton#ghostButton, QPushButton#sideButton, QPushButton#filterButton {
    background: #ffffff;
    border: 1px solid #d8dbfa;
    color: #4d537a;
}
QPushButton#filterActive {
    background: #ece9ff;
    border: 1px solid #d0cbff;
    color: #4b42c6;
}
QTableWidget#dataTable, QTableWidget {
    background: #ffffff;
    alternate-background-color: #f8f7ff;
    border: 1px solid #e0e1fb;
    border-radius: 18px;
    color: #232a52;
    gridline-color: #ececfb;
    selection-background-color: #ece9ff;
}
QHeaderView::section {
    background: #f4f2ff;
    color: #72779a;
    border: none;
    border-bottom: 1px solid #e0e1fb;
    padding: 13px 12px;
    font-size: 12px;
    font-weight: 800;
}
QTableCornerButton::section {
    background: #f4f2ff;
    border: none;
    border-bottom: 1px solid #e0e1fb;
}
QScrollArea {
    border: none;
}
QFrame#modalOverlay {
    background: rgba(82, 93, 150, 0.22);
}
QFrame#userCard {
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    margin-top: 8px;
}
QLabel#userCardTitle {
    color: #ffffff;
    font-size: 15px;
    font-weight: 700;
}
QLabel#userCardText {
    color: #c7ccf2;
    font-size: 12px;
}
QDialog {
    background: #eef0fb;
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
