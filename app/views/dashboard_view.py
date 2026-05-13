"""Vista de dashboard."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.controllers.cliente_controller import ClienteController
from app.controllers.factura_controller import FacturaController
from app.controllers.producto_controller import ProductoController


def _money(value: Decimal | int | str) -> str:
    return f"{Decimal(str(value)):,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


class MetricCard(QFrame):
    def __init__(self, title: str, value: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")
        self.setProperty("accent", accent)

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        layout.addWidget(title_label)
        layout.addWidget(value_label)


class DashboardView(QWidget):
    def __init__(
        self,
        factura_controller: FacturaController,
        cliente_controller: ClienteController,
        producto_controller: ProductoController,
    ) -> None:
        super().__init__()
        self.factura_controller = factura_controller
        self.cliente_controller = cliente_controller
        self.producto_controller = producto_controller

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(24, 24, 24, 24)
        self.layout.setSpacing(18)

        title = QLabel("Dashboard")
        title.setObjectName("viewTitle")
        subtitle = QLabel("Resumen inicial de actividad comercial y estado de cobros.")
        subtitle.setObjectName("viewSubtitle")

        self.metrics_grid = QGridLayout()
        self.metrics_grid.setSpacing(14)

        recent_title = QLabel("Últimas facturas")
        recent_title.setObjectName("sectionTitle")
        self.recent_table = QTableWidget(0, 5)
        self.recent_table.setHorizontalHeaderLabels(["Número", "Cliente", "Estado", "Total", "Pendiente"])
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.horizontalHeader().setStretchLastSection(True)

        self.layout.addWidget(title)
        self.layout.addWidget(subtitle)
        self.layout.addLayout(self.metrics_grid)
        self.layout.addWidget(recent_title)
        self.layout.addWidget(self.recent_table)

        self.refresh_data()

    def refresh_data(self) -> None:
        while self.metrics_grid.count():
            item = self.metrics_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        metrics = self.factura_controller.dashboard_metrics()
        cards = [
            ("Total facturado", _money(metrics["total_facturado"]), "blue"),
            ("Facturas pendientes", str(metrics["facturas_pendientes"]), "amber"),
            ("Importe cobrado", _money(metrics["importe_cobrado"]), "green"),
            ("Importe pendiente", _money(metrics["importe_pendiente"]), "red"),
            ("Clientes", str(self.cliente_controller.count_clientes()), "slate"),
            ("Productos/servicios", str(self.producto_controller.count_productos()), "slate"),
        ]

        for index, (title, value, accent) in enumerate(cards):
            self.metrics_grid.addWidget(MetricCard(title, value, accent), index // 3, index % 3)

        rows = self.factura_controller.list_invoice_rows()
        self.recent_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row["numero"], row["cliente"], row["estado"], _money(row["total"]), _money(row["importe_pendiente"])]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column >= 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.recent_table.setItem(row_index, column, item)

        self.recent_table.resizeColumnsToContents()
