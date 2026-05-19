"""Vista de dashboard."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
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
    def __init__(self, title: str, value: str) -> None:
        super().__init__()
        self.setObjectName("metricCard")

        title_label = QLabel(title)
        title_label.setObjectName("metricTitle")
        value_label = QLabel(value)
        value_label.setObjectName("metricValue")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(8)
        layout.addWidget(title_label)
        layout.addWidget(value_label)


class MonthlyBarChart(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.series: list[dict[str, object]] = []
        self.setMinimumHeight(220)

    def set_series(self, series: list[dict[str, object]]) -> None:
        self.series = series
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(20, 20, -20, -36)

        painter.fillRect(self.rect(), QColor("#ffffff"))
        if not self.series:
            painter.setPen(QColor("#6b7280"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Sin datos todavía")
            return

        max_value = max(Decimal(str(item["value"])) for item in self.series) or Decimal("1")
        bar_width = max(int(rect.width() / max(len(self.series), 1)) - 12, 24)

        for index, item in enumerate(self.series):
            value = Decimal(str(item["value"]))
            label = str(item["label"])
            x = rect.left() + index * (bar_width + 12)
            height = 0 if max_value == 0 else int((value / max_value) * rect.height())
            y = rect.bottom() - height
            painter.setBrush(QColor("#2563eb"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(x, y, bar_width, height), 6, 6)
            painter.setPen(QColor("#374151"))
            painter.drawText(QRectF(x - 8, rect.bottom() + 8, bar_width + 16, 18), Qt.AlignmentFlag.AlignCenter, label)


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
        subtitle = QLabel("KPIs, evolución temporal y estado actual de cobros.")
        subtitle.setObjectName("viewSubtitle")

        self.metrics_grid = QGridLayout()
        self.metrics_grid.setSpacing(14)

        chart_title = QLabel("Evolución mensual")
        chart_title.setObjectName("sectionTitle")
        self.chart = MonthlyBarChart()

        self.context_label = QLabel("")
        self.context_label.setObjectName("viewSubtitle")

        recent_title = QLabel("Últimas facturas")
        recent_title.setObjectName("sectionTitle")
        self.recent_table = QTableWidget(0, 6)
        self.recent_table.setHorizontalHeaderLabels(["Número", "Cliente", "Estado", "Categoría", "Total", "Pendiente"])
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setAlternatingRowColors(True)
        self.recent_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.recent_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.recent_table.setMinimumHeight(300)
        self.recent_table.setShowGrid(False)
        header = self.recent_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.layout.addWidget(title)
        self.layout.addWidget(subtitle)
        self.layout.addLayout(self.metrics_grid)
        self.layout.addWidget(chart_title)
        self.layout.addWidget(self.chart)
        self.layout.addWidget(self.context_label)
        self.layout.addWidget(recent_title)
        self.layout.addWidget(self.recent_table)

        self.refresh_data()

    def refresh_data(self) -> None:
        while self.metrics_grid.count():
            item = self.metrics_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        snapshot = self.factura_controller.dashboard_snapshot()
        cards = [
            ("Total facturado", _money(snapshot["total_facturado"])),
            ("Importe cobrado", _money(snapshot["importe_cobrado"])),
            ("Importe pendiente", _money(snapshot["importe_pendiente"])),
            ("Facturas pendientes", str(snapshot["facturas_pendientes"])),
            ("Facturas vencidas", str(snapshot["facturas_vencidas"])),
            ("Clientes", str(self.cliente_controller.count_clientes())),
            ("Productos/servicios", str(self.producto_controller.count_productos())),
            ("Previsión", _money(snapshot["forecast_next_month"])),
        ]

        for index, (title, value) in enumerate(cards):
            self.metrics_grid.addWidget(MetricCard(title, value), index // 4, index % 4)

        self.chart.set_series(snapshot["monthly_series"])
        top_cliente = snapshot["top_cliente"] or "Sin datos"
        self.context_label.setText(
            f"Cliente principal: {top_cliente} | Previsión {snapshot['forecast_label']}: {_money(snapshot['forecast_next_month'])}"
        )

        rows = self.factura_controller.list_invoice_rows()
        self.recent_table.setRowCount(len(rows))
        for row_index, row in enumerate(rows):
            values = [row["numero"], row["cliente"], row["estado"], row["categoria"], _money(row["total"]), _money(row["importe_pendiente"])]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column >= 4:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.recent_table.setItem(row_index, column, item)
