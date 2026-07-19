"""Read-only millimetre scene rendering for generated layouts."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

from debbie.domain import Layout, Orientation, Work
from debbie.geometry import effective_placement_region, usable_stock_rectangle


class StockBoundaryItem(QGraphicsRectItem):
    pass


class UsableRegionItem(QGraphicsRectItem):
    pass


class EffectiveRegionItem(QGraphicsRectItem):
    pass


class PartGraphicsItem(QGraphicsRectItem):
    def __init__(
        self, rect: QRectF, label: str, orientation: Orientation, color_index: int
    ) -> None:
        super().__init__(rect)
        self.orientation = orientation
        colors = ("#5b8ff9", "#61d9a3", "#f6bd16", "#7262fd", "#78d3f8")
        self.setBrush(QBrush(QColor(colors[color_index % len(colors)])))
        self.setPen(QPen(QColor("#24364b"), 0.8))
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemClipsChildrenToShape, True)
        self.setAcceptHoverEvents(True)
        if rect.width() >= 35 and rect.height() >= 15:
            text = QGraphicsSimpleTextItem(label, self)
            text.setBrush(QColor("#102030"))
            text.setPos(rect.x() + 2, rect.y() + 1)


class LayoutScene(QGraphicsScene):
    def render_layout(self, work: Work | None, layout: Layout | None) -> None:
        self.clear()
        if work is None or layout is None:
            self.setSceneRect(QRectF())
            return
        stock_instance = next(
            item for item in work.stock_instances if item.id == layout.stock_instance_id
        )
        stock = next(
            item for item in work.stock_specifications if item.id == stock_instance.specification_id
        )
        profile = layout.process_profile
        full = stock.dimensions
        trim = profile.trim
        full_rect = QRectF(0, 0, full.length, full.width)
        boundary = StockBoundaryItem(full_rect)
        boundary.setPen(QPen(QColor("#172b4d"), 1.5))
        boundary.setBrush(QBrush(QColor("#d8dde5")))
        boundary.setZValue(-4)
        self.addItem(boundary)

        usable = usable_stock_rectangle(stock, profile)
        usable_item = UsableRegionItem(QRectF(trim.left, trim.top, usable.length, usable.width))
        usable_item.setPen(QPen(QColor("#60758a"), 0.8, Qt.PenStyle.DashLine))
        usable_item.setBrush(QBrush(QColor("#f6f8fa")))
        usable_item.setZValue(-3)
        self.addItem(usable_item)

        effective = effective_placement_region(stock, profile)
        effective_item = EffectiveRegionItem(
            QRectF(
                trim.left + effective.x,
                trim.top + effective.y,
                effective.length,
                effective.width,
            )
        )
        effective_item.setPen(QPen(QColor("#1f7a5a"), 0.8, Qt.PenStyle.DotLine))
        effective_item.setBrush(QBrush(Qt.BrushStyle.NoBrush))
        effective_item.setZValue(-2)
        self.addItem(effective_item)

        instances = {item.id: item for item in work.part_instances}
        part_types = {item.id: item for item in work.part_types}
        for index, placement in enumerate(layout.placements):
            instance = instances[placement.part_instance_id]
            part = part_types[instance.part_type_id]
            dimensions = part.oriented_dimensions(placement.orientation)
            item = PartGraphicsItem(
                QRectF(
                    trim.left + placement.x,
                    trim.top + placement.y,
                    dimensions.length,
                    dimensions.width,
                ),
                part.name,
                placement.orientation,
                index,
            )
            self.addItem(item)
        self.setSceneRect(full_rect.adjusted(-5, -5, 5, 5))


class LayoutView(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.layout_scene = LayoutScene(self)
        self.setScene(self.layout_scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QColor("#eef1f5"))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self._zoom = 1.0

    def fit_layout(self) -> None:
        rect = self.scene().sceneRect()
        if rect.isEmpty():
            self.resetTransform()
            self._zoom = 1.0
            return
        self.fitInView(rect.adjusted(-8, -8, 8, 8), Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        proposed = self.transform().m11() * factor
        if 0.02 <= proposed <= 100:
            self.scale(factor, factor)
            self._zoom = proposed
        event.accept()
