"""Ventana principal estilo Automalize para escritorio."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

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
from app.services.export_csv import export_rows_to_csv
from app.services.export_excel import export_rows_to_excel
from app.services.export_xml import export_rows_to_xml
from app.services.invoice_calculator import calculate_invoice
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


class InvoiceFormDialog(QDialog):
    def __init__(self, parent: QWidget, controller: FacturaController, factura: Factura | None = None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.factura = factura
        self.setWindowTitle("Editar factura" if factura else "Nueva factura")
        self.resize(980, 720)

        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)

        form_panel = QFrame()
        form_panel.setObjectName("panel")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setSpacing(16)

        title = QLabel("Editar factura" if factura else "Nueva factura")
        title.setObjectName("dialogTitle")
        form_layout.addWidget(title)

        self.date_input = QDateEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDate(QDate(factura.fecha if factura else date.today()))
        self.type_input = QComboBox()
        self.type_input.addItems(["Factura", "Factura simplificada", "Factura rectificativa"])
        self.client_input = QLineEdit(factura.cliente_nombre if factura else "")
        self.client_input.setPlaceholderText("Cliente S.A.")
        self.nif_input = QLineEdit()
        self.nif_input.setPlaceholderText("NIF / CIF")
        self.address_input = QLineEdit()
        self.address_input.setPlaceholderText("Dirección")
        self.email_input = QLineEdit()
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
        form_layout.addWidget(self.notes_input)

        actions = QHBoxLayout()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("ghostButton")
        cancel.clicked.connect(self.reject)
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
        if self.factura:
            saved = self.controller.update_factura(self.factura.id, self.client_input.text().strip(), fecha, lines)
        else:
            saved = self.controller.create_factura(self.client_input.text().strip(), fecha, lines)
        if emit:
            self.controller.emit_factura(saved.id)
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Automalize - Escritorio")
        self.resize(1320, 820)
        self.setMinimumSize(1100, 680)

        self.cliente_controller = ClienteController()
        self.producto_controller = ProductoController()
        self.factura_controller = FacturaController()
        self.current_filter = "Todas"
        self.current_search = ""

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
        side_layout.addWidget(self._side_label("Principal"))

        self.navigation = QListWidget()
        self.navigation.setObjectName("navigation")
        self.navigation.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.routes = [
            ("Dashboard", self.show_dashboard),
            ("Facturas", self.show_invoices),
            ("Nueva Factura", self.new_invoice),
            ("Importar Factura", self.show_import),
            ("Factura por Voz", self.show_voice),
            ("Clientes", lambda: self.set_static_page(5, "Clientes")),
            ("Productos", lambda: self.set_static_page(6, "Productos")),
        ]
        for label, _ in self.routes:
            self.navigation.addItem(QListWidgetItem(label))
        self.navigation.currentRowChanged.connect(self.handle_nav)
        side_layout.addWidget(self.navigation, 1)
        side_layout.addWidget(self._side_label("Sistema"))
        theme = QPushButton("Modo oscuro")
        theme.setObjectName("sideButton")
        theme.clicked.connect(lambda: QMessageBox.information(self, "Tema", "El tema oscuro de Automalize está activo."))
        side_layout.addWidget(theme)

        content = QFrame()
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
        self.stack.addWidget(self._placeholder("Nueva Factura"))
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
        emit = detail.addButton("Emitir/Revertir", QMessageBox.ButtonRole.ActionRole)
        delete = detail.addButton("Eliminar", QMessageBox.ButtonRole.DestructiveRole)
        detail.addButton("PDF", QMessageBox.ButtonRole.ActionRole)
        detail.addButton("Cerrar", QMessageBox.ButtonRole.RejectRole)
        detail.exec()
        clicked = detail.clickedButton()
        try:
            if clicked == edit:
                self.edit_invoice(factura)
            elif clicked == emit:
                if factura.editable:
                    self.factura_controller.emit_factura(factura.id)
                else:
                    self.factura_controller.revert_to_draft(factura.id)
                self.render_invoices()
            elif clicked == delete:
                self.factura_controller.delete_factura(factura.id)
                self.render_invoices()
        except Exception as exc:
            QMessageBox.warning(self, "Acción no disponible", str(exc))

    def new_invoice(self) -> None:
        dialog = InvoiceFormDialog(self, self.factura_controller)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.navigation.setCurrentRow(1)
            self.render_invoices()

    def edit_invoice(self, factura: Factura) -> None:
        dialog = InvoiceFormDialog(self, self.factura_controller, factura)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.render_invoices()

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
        name = Path(path).stem.replace("_", " ").replace("-", " ").title()
        self.factura_controller.create_factura(
            cliente_nombre=name or "Cliente importado",
            fecha=date.today(),
            lineas=[LineaFactura(f"Importado desde {Path(path).name}", Decimal("1"), Decimal("100.00"))],
        )
        QMessageBox.information(self, "Importación preparada", "Se ha creado un borrador para revisar.")
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
QMainWindow, QWidget {
    background: #0f0f1a;
    color: #f0f0f5;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
}
QFrame#sidebar {
    background: #1a1a2e;
    border-right: 1px solid #2d2d50;
    min-width: 260px;
    max-width: 260px;
}
QLabel#logo {
    color: #a5b4fc;
    font-size: 23px;
    font-weight: 800;
    padding: 8px 0 20px 0;
}
QLabel#sideSection {
    color: #6b6b8d;
    font-size: 11px;
    font-weight: 700;
    padding: 14px 10px 4px 10px;
}
QListWidget#navigation {
    background: transparent;
    border: none;
    color: #a0a0c0;
    outline: none;
}
QListWidget#navigation::item {
    padding: 12px 14px;
    border-radius: 10px;
    margin: 3px 0;
}
QListWidget#navigation::item:selected {
    background: rgba(99, 102, 241, 0.16);
    color: #818cf8;
}
QListWidget#navigation::item:hover {
    background: #2a2a4a;
    color: #f0f0f5;
}
QFrame#content, QScrollArea, QWidget#page {
    background: #0f0f1a;
}
QFrame#navbar {
    background: rgba(15, 15, 26, 0.92);
    border-bottom: 1px solid #2d2d50;
    min-height: 64px;
    max-height: 64px;
}
QLabel#navbarTitle {
    font-size: 18px;
    font-weight: 700;
}
QLabel#viewTitle {
    font-size: 30px;
    font-weight: 800;
}
QLabel#viewSubtitle {
    color: #a0a0c0;
}
QFrame#panel, QFrame#statCard {
    background: #1a1a2e;
    border: 1px solid #2d2d50;
    border-radius: 14px;
}
QFrame#invoicePreview {
    background: #ffffff;
    color: #1a1a2e;
    border-radius: 14px;
}
QLabel#previewText {
    color: #1a1a2e;
    font-family: "Segoe UI";
    font-size: 13px;
}
QLabel#dialogTitle, QLabel#sectionTitle {
    font-size: 18px;
    font-weight: 700;
}
QLabel#statValue {
    font-size: 24px;
    font-weight: 800;
}
QLabel#statTitle {
    color: #a0a0c0;
}
QLabel#statIcon_purple, QLabel#statIcon_yellow, QLabel#statIcon_blue, QLabel#statIcon_green {
    border-radius: 12px;
    min-width: 48px;
    min-height: 48px;
    qproperty-alignment: AlignCenter;
    font-weight: 800;
}
QLabel#statIcon_purple { background: rgba(99, 102, 241, 0.18); color: #818cf8; }
QLabel#statIcon_yellow { background: rgba(245, 158, 11, 0.18); color: #fbbf24; }
QLabel#statIcon_blue { background: rgba(14, 165, 233, 0.18); color: #38bdf8; }
QLabel#statIcon_green { background: rgba(16, 185, 129, 0.18); color: #34d399; }
QLineEdit, QDateEdit, QComboBox, QPlainTextEdit {
    background: #1e1e35;
    border: 1px solid #2d2d50;
    border-radius: 10px;
    color: #f0f0f5;
    padding: 9px 12px;
}
QLineEdit#pillSearch {
    border-radius: 18px;
    min-width: 240px;
}
QLineEdit:focus, QDateEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #818cf8;
}
QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6366f1, stop:1 #4f46e5);
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton:hover {
    background: #818cf8;
}
QPushButton#accentButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
}
QPushButton#warningButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
    color: #0f0f1a;
}
QPushButton#ghostButton, QPushButton#sideButton, QPushButton#filterButton {
    background: transparent;
    border: 1px solid #2d2d50;
    color: #a0a0c0;
}
QPushButton#filterActive {
    background: #6366f1;
    border: 1px solid #6366f1;
}
QTableWidget#dataTable, QTableWidget {
    background: #1a1a2e;
    alternate-background-color: #20203a;
    border: 1px solid #2d2d50;
    border-radius: 14px;
    color: #f0f0f5;
    gridline-color: #2d2d50;
    selection-background-color: rgba(99, 102, 241, 0.28);
}
QHeaderView::section {
    background: #222240;
    color: #a0a0c0;
    border: none;
    padding: 11px 12px;
    font-size: 12px;
    font-weight: 800;
}
"""
