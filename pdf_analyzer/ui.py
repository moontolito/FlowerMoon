"""Native PySide6 interface for the local PDF reader."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, QRunnable, QSize, QThreadPool, QTimer, Qt, Signal, Slot
from PySide6.QtGui import (
    QColor,
    QCloseEvent,
    QContextMenuEvent,
    QImage,
    QIcon,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
    QWheelEvent,
)
from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSplitter,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .annotations import HighlightStore
from .area_masks import (
    AreaMask,
    AreaMaskError,
    AreaMaskStore,
    apply_masks_to_document,
    copy_mask_to_page,
    create_area_mask,
    create_path_mask,
    load_mask_profile,
    mask_geometry_identity,
    save_mask_profile,
)
from .analysis_state import AnalysisStateError, load_analysis_state, save_analysis_state
from .analysis_annotations import (
    category_evidence_drafts,
    standard_evidence_drafts,
)
from .bilingual_dictionary import BilingualDictionaryStore
from .bilingual_editor import BilingualDictionaryEditorDialog
from .bookmarks import (
    BookmarkStore,
    PersonalBookmark,
    create_bookmark,
    delete_bookmark_tree,
    indent_bookmark,
    move_bookmark,
    outdent_bookmark,
    rename_bookmark,
)
from .categories import CategoryProfileStore
from .category_editor import CategoryEditorDialog
from .category_engine import analyze_categories
from .consolidated_export import (
    ConsolidatedExportResult,
    ManagementAnalysisReportResult,
    export_consolidated_package,
    export_management_analysis_report,
)
from .engine import PdfSession
from .evidence import EvidenceBatchResult, EvidenceDraft, EvidenceStore
from .models import (
    CategoryMatch,
    DocumentInfo,
    DocumentText,
    Evidence,
    Highlight,
    PageLayout,
    PageText,
    RenderedPage,
    SearchHit,
    StandardMatch,
    TextRect,
)
from .mask_similarity import find_similar_pages, parse_page_selection
from .note_editor import NoteDialog
from .noise_filter import (
    SearchNoiseOptions,
    SearchNoiseReport,
    filter_document_for_analysis,
)
from .pdf_export import PdfExportResult, export_annotated_pdf
from .project_state import (
    READING_STATUSES,
    ProjectDocument,
    ProjectState,
    ProjectStateError,
    load_project,
    normalize_path,
    save_project,
)
from .search_engine import parse_keywords, search_document
from .search_expansion import expand_keywords
from .standards_engine import analyze_standards
from .text_selection import normalized_range, selected_text, selection_rects, word_index_at
from .text_engine import TextEngine
from .view_math import calculate_fit_scale, clamp, next_zoom_scale
from .workspace_analysis import (
    WorkspaceSummary,
    analyze_workspace,
    select_workspace_documents,
    update_workspace_status,
)
from .workspace_batch_analysis import (
    WorkspaceBatchAnalysisResult,
    analyze_workspace_documents,
)
from .workspace_dashboard import WorkspaceDashboardDialog
from .workspace_report import (
    WorkspaceReportResult,
    export_workspace_report,
)
from .workspace_excel import (
    WorkspaceExcelResult,
    export_workspace_excel,
)


BASE_RENDER_WIDTH = 1100
PRELOAD_DISTANCE = 3
KEEP_DISTANCE = 8
MAX_SCREEN_RENDER_WIDTH = 3600


class TaskSignals(QObject):
    completed = Signal(object)
    failed = Signal(object)


class BackgroundTask(QRunnable):
    def __init__(self, callback, *args) -> None:
        super().__init__()
        self.callback = callback
        self.args = args
        self.signals = TaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.callback(*self.args)
        except Exception as exc:  # transported to the GUI thread
            self.signals.failed.emit(exc)
        else:
            self.signals.completed.emit(result)


class PageCanvas(QWidget):
    """Paint a PDF page plus selectable text and persistent overlays."""

    highlightRequested = Signal(int, str, object)
    evidenceRequested = Signal(int, str, object)
    removeHighlightRequested = Signal(str)
    maskDrawn = Signal(int, object)

    def __init__(self, page_index: int, page_width: float, page_height: float) -> None:
        super().__init__()
        self.page_index = page_index
        self.page_width = max(page_width, 1.0)
        self.page_height = max(page_height, 1.0)
        self._pixmap: QPixmap | None = None
        self._rendered_width = 0
        self._page_text: PageText | None = None
        self._highlights: tuple[Highlight, ...] = ()
        self._area_masks: tuple[AreaMask, ...] = ()
        self._mask_mode: str | None = None
        self._mask_shape = "rectangle"
        self._mask_start: tuple[float, float] | None = None
        self._mask_active: tuple[float, float] | None = None
        self._mask_points: list[tuple[float, float]] = []
        self._selection_anchor: int | None = None
        self._selection_active: int | None = None
        self._flash_rects: tuple[TextRect, ...] = ()
        self._flash_revision = 0
        self.rotation = 0
        self.setObjectName("pageCanvas")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

    @property
    def loaded(self) -> bool:
        return self._pixmap is not None

    def needs_render(self, target_width: int) -> bool:
        return self._pixmap is None or self._rendered_width < target_width * 0.88

    def set_display_size(self, width: int, height: int) -> None:
        self.setFixedSize(max(1, width), max(1, height))
        self.update()

    def set_pixmap(self, pixmap: QPixmap, rendered_width: int) -> None:
        if self._pixmap is not None and rendered_width < self._rendered_width:
            return
        self._pixmap = pixmap
        self._rendered_width = rendered_width
        self.update()

    def unload(self) -> None:
        self._pixmap = None
        self._rendered_width = 0
        self.update()

    def set_page_text(self, page_text: PageText | None) -> None:
        self._page_text = page_text
        self.clear_selection()
        cursor = (
            Qt.CursorShape.CrossCursor
            if self._mask_mode
            else Qt.CursorShape.IBeamCursor
            if page_text and page_text.words
            else Qt.CursorShape.ArrowCursor
        )
        self.setCursor(cursor)

    def set_highlights(self, highlights: tuple[Highlight, ...]) -> None:
        self._highlights = tuple(
            highlight for highlight in highlights if highlight.page_index == self.page_index
        )
        self.update()

    def set_area_masks(self, masks: tuple[AreaMask, ...]) -> None:
        self._area_masks = tuple(
            mask
            for mask in masks
            if mask.page_index is None or mask.page_index == self.page_index
        )
        self.update()

    def set_mask_mode(self, mode: str | None, shape: str = "rectangle") -> None:
        self._mask_mode = mode if mode in {"ignore", "keep"} else None
        self._mask_shape = (
            shape if shape in {"rectangle", "freehand", "polygon"} else "rectangle"
        )
        self._mask_start = None
        self._mask_active = None
        self._mask_points = []
        if self._mask_mode:
            self.clear_selection()
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(
                Qt.CursorShape.IBeamCursor
                if self._page_text and self._page_text.words
                else Qt.CursorShape.ArrowCursor
            )
        self.update()

    def set_rotation(self, rotation: int) -> None:
        self.rotation = int(rotation) % 360
        self.clear_selection()
        self.unload()

    def _display_page_size(self) -> tuple[float, float]:
        return (
            (self.page_height, self.page_width)
            if self.rotation in (90, 270)
            else (self.page_width, self.page_height)
        )

    def _source_to_display(self, x: float, y: float) -> tuple[float, float]:
        if self.rotation == 90:
            return self.page_height - y, x
        if self.rotation == 180:
            return self.page_width - x, self.page_height - y
        if self.rotation == 270:
            return y, self.page_width - x
        return x, y

    def clear_selection(self) -> None:
        self._selection_anchor = None
        self._selection_active = None
        self.update()

    def flash_evidence(self, rects: tuple[TextRect, ...], duration_ms: int = 2200) -> None:
        self._flash_revision += 1
        revision = self._flash_revision
        self._flash_rects = rects
        self.update()
        QTimer.singleShot(duration_ms, lambda: self._clear_flash(revision))

    def _clear_flash(self, revision: int) -> None:
        if revision != self._flash_revision:
            return
        self._flash_rects = ()
        self.update()

    def selection(self) -> tuple[str, tuple[TextRect, ...]]:
        if self._page_text is None or self._selection_anchor is None or self._selection_active is None:
            return "", ()
        start, end = normalized_range(self._selection_anchor, self._selection_active)
        return (
            selected_text(self._page_text.words, start, end),
            selection_rects(self._page_text.words, start, end),
        )

    def _page_point(self, position) -> tuple[float, float]:
        display_width, display_height = self._display_page_size()
        x = clamp(position.x() / max(self.width(), 1) * display_width, 0.0, display_width)
        y = clamp(position.y() / max(self.height(), 1) * display_height, 0.0, display_height)
        if self.rotation == 90:
            return y, self.page_height - x
        if self.rotation == 180:
            return self.page_width - x, self.page_height - y
        if self.rotation == 270:
            return self.page_width - y, x
        return x, y

    def _word_at(self, position, wider_tolerance: bool = False) -> int | None:
        if self._page_text is None:
            return None
        x, y = self._page_point(position)
        display_width, _ = self._display_page_size()
        scale = self.width() / display_width
        tolerance_pixels = 14.0 if wider_tolerance else 5.0
        return word_index_at(
            self._page_text.words,
            x,
            y,
            tolerance=tolerance_pixels / max(scale, 0.01),
        )

    def _display_rect(self, rect: TextRect) -> QRectF:
        display_width, display_height = self._display_page_size()
        points = (
            self._source_to_display(rect.x0, rect.y0),
            self._source_to_display(rect.x1, rect.y0),
            self._source_to_display(rect.x0, rect.y1),
            self._source_to_display(rect.x1, rect.y1),
        )
        x0 = min(point[0] for point in points)
        y0 = min(point[1] for point in points)
        x1 = max(point[0] for point in points)
        y1 = max(point[1] for point in points)
        return QRectF(
            x0 / display_width * self.width(),
            y0 / display_height * self.height(),
            (x1 - x0) / display_width * self.width(),
            (y1 - y0) / display_height * self.height(),
        )

    def _display_point(self, x: float, y: float) -> QPointF:
        display_width, display_height = self._display_page_size()
        display_x, display_y = self._source_to_display(x, y)
        return QPointF(
            display_x / display_width * self.width(),
            display_y / display_height * self.height(),
        )

    def _source_path(
        self,
        points: tuple[tuple[float, float], ...] | list[tuple[float, float]],
        close: bool = True,
    ) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        first = self._display_point(*points[0])
        path.moveTo(first)
        for point in points[1:]:
            path.lineTo(self._display_point(*point))
        if close and len(points) >= 3:
            path.closeSubpath()
        return path

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        if self._pixmap is not None:
            painter.drawPixmap(self.rect(), self._pixmap)
        else:
            painter.setPen(QColor("#9aa4ad"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"Page {self.page_index + 1}")

        painter.setPen(Qt.PenStyle.NoPen)
        for highlight in self._highlights:
            color = QColor(highlight.color)
            color.setAlpha(105)
            painter.setBrush(color)
            for rect in highlight.rects:
                painter.drawRoundedRect(self._display_rect(rect), 1.5, 1.5)

        text, rects = self.selection()
        if text:
            painter.setBrush(QColor(45, 126, 216, 95))
            for rect in rects:
                painter.drawRect(self._display_rect(rect))

        if self._flash_rects:
            painter.setBrush(QColor(36, 107, 158, 28))
            painter.setPen(QPen(QColor("#246b9e"), 2.5))
            for rect in self._flash_rects:
                painter.drawRoundedRect(self._display_rect(rect), 2.0, 2.0)

        for mask in self._area_masks:
            color = QColor("#218739" if mask.kind == "keep" else "#c43b35")
            fill = QColor(color)
            fill.setAlpha(35)
            painter.setBrush(fill)
            painter.setPen(QPen(color, 2, Qt.PenStyle.DashLine))
            if mask.shape == "rectangle":
                painter.drawRect(
                    self._display_rect(
                        TextRect(
                            mask.x0_ratio * self.page_width,
                            mask.y0_ratio * self.page_height,
                            mask.x1_ratio * self.page_width,
                            mask.y1_ratio * self.page_height,
                        )
                    )
                )
            else:
                points = tuple(
                    (x * self.page_width, y * self.page_height)
                    for x, y in mask.points
                )
                painter.drawPath(self._source_path(points))

        if self._mask_mode and (
            (self._mask_start is not None and self._mask_active is not None)
            or self._mask_points
        ):
            color = QColor("#218739" if self._mask_mode == "keep" else "#c43b35")
            fill = QColor(color)
            fill.setAlpha(45)
            painter.setBrush(fill)
            painter.setPen(QPen(color, 2))
            if (
                self._mask_shape == "rectangle"
                and self._mask_start is not None
                and self._mask_active is not None
            ):
                x0, y0 = self._mask_start
                x1, y1 = self._mask_active
                painter.drawRect(
                    self._display_rect(
                        TextRect(
                            min(x0, x1),
                            min(y0, y1),
                            max(x0, x1),
                            max(y0, y1),
                        )
                    )
                )
            else:
                points = list(self._mask_points)
                if self._mask_shape == "polygon" and self._mask_active is not None:
                    points.append(self._mask_active)
                painter.drawPath(
                    self._source_path(
                        points,
                        close=self._mask_shape == "freehand",
                    )
                )

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor("#c9d0d6"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            if self._mask_mode:
                point = self._page_point(event.position())
                if self._mask_shape == "polygon":
                    if not self._mask_points or self._mask_points[-1] != point:
                        self._mask_points.append(point)
                    self._mask_active = point
                elif self._mask_shape == "freehand":
                    self._mask_start = point
                    self._mask_active = point
                    self._mask_points = [point]
                else:
                    self._mask_start = point
                    self._mask_active = point
                self.update()
                event.accept()
                return
            index = self._word_at(event.position())
            if index is None:
                self.clear_selection()
            else:
                self._selection_anchor = index
                self._selection_active = index
                self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (
            self._mask_mode
            and self._mask_shape == "polygon"
            and self._mask_points
        ):
            self._mask_active = self._page_point(event.position())
            self.update()
            event.accept()
            return
        if (
            event.buttons() & Qt.MouseButton.LeftButton
            and self._mask_mode
            and self._mask_start is not None
        ):
            self._mask_active = self._page_point(event.position())
            if self._mask_shape == "freehand":
                last_x, last_y = self._mask_points[-1]
                if (
                    (self._mask_active[0] - last_x) ** 2
                    + (self._mask_active[1] - last_y) ** 2
                    >= 4.0
                ):
                    self._mask_points.append(self._mask_active)
            self.update()
            event.accept()
            return
        if event.buttons() & Qt.MouseButton.LeftButton and self._selection_anchor is not None:
            index = self._word_at(event.position(), wider_tolerance=True)
            if index is not None and index != self._selection_active:
                self._selection_active = index
                self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._mask_mode
            and self._mask_start is not None
        ):
            active = self._page_point(event.position())
            start = self._mask_start
            self._mask_start = None
            self._mask_active = None
            if self._mask_shape == "freehand":
                self._mask_points.append(active)
                self._finish_path_mask()
            else:
                self.maskDrawn.emit(
                    self.page_index,
                    (start[0], start[1], active[0], active[1]),
                )
                self.update()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._mask_mode
            and self._mask_shape == "polygon"
        ):
            point = self._page_point(event.position())
            if not self._mask_points or self._mask_points[-1] != point:
                self._mask_points.append(point)
            self._finish_path_mask()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _finish_path_mask(self) -> None:
        points: list[tuple[float, float]] = []
        for point in self._mask_points:
            if not points or point != points[-1]:
                points.append(point)
        self._mask_points = []
        self._mask_start = None
        self._mask_active = None
        self.update()
        self.maskDrawn.emit(
            self.page_index,
            {"shape": self._mask_shape, "points": tuple(points)},
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy_selection()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self._mask_start is not None or self._mask_points:
                self._mask_start = None
                self._mask_active = None
                self._mask_points = []
                self.update()
                event.accept()
                return
            self.clear_selection()
            event.accept()
            return
        if (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and self._mask_mode
            and self._mask_shape == "polygon"
            and self._mask_points
        ):
            self._finish_path_mask()
            event.accept()
            return
        super().keyPressEvent(event)

    def copy_selection(self) -> None:
        text, _ = self.selection()
        if text:
            QApplication.clipboard().setText(text)

    def _highlight_at(self, position) -> Highlight | None:
        x, y = self._page_point(position)
        for highlight in reversed(self._highlights):
            if any(rect.x0 <= x <= rect.x1 and rect.y0 <= y <= rect.y1 for rect in highlight.rects):
                return highlight
        return None

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = QMenu(self)
        text, rects = self.selection()
        if text:
            copy_action = menu.addAction("Copy")
            copy_action.triggered.connect(self.copy_selection)
            highlight_action = menu.addAction("Highlight")
            highlight_action.triggered.connect(
                lambda: self.highlightRequested.emit(self.page_index, text, rects)
            )
            evidence_action = menu.addAction("Create note")
            evidence_action.triggered.connect(
                lambda: self.evidenceRequested.emit(self.page_index, text, rects)
            )
        existing = self._highlight_at(event.pos())
        if existing is not None:
            if text:
                menu.addSeparator()
            remove_action = menu.addAction("Remove highlight")
            remove_action.triggered.connect(
                lambda: self.removeHighlightRequested.emit(existing.highlight_id)
            )
        if menu.actions():
            menu.exec(event.globalPos())


class PageWidget(QFrame):
    """A page placeholder which can release its expensive bitmap."""

    def __init__(self, page_layout: PageLayout) -> None:
        super().__init__()
        self.page_number = page_layout.page_number
        self._display_width = 1
        self._display_height = 1
        self.setObjectName("pageContainer")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        self.image = PageCanvas(
            page_layout.page_index,
            page_layout.width_points,
            page_layout.height_points,
        )
        self.image.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.image, 0, Qt.AlignmentFlag.AlignHCenter)

        self.caption = QLabel(f"Page {self.page_number}")
        self.caption.setObjectName("pageCaption")
        self.caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.caption)

    @property
    def loaded(self) -> bool:
        return self.image.loaded

    def needs_render(self, target_width: int) -> bool:
        return self.image.needs_render(target_width)

    def set_display_size(self, width: int, height: int) -> None:
        self._display_width = max(1, width)
        self._display_height = max(1, height)
        self.image.set_display_size(self._display_width, self._display_height)

    def set_pixmap(self, pixmap: QPixmap, rendered_width: int) -> None:
        self.image.set_pixmap(pixmap, rendered_width)

    def unload(self) -> None:
        self.image.unload()

    def set_page_text(self, page_text: PageText | None) -> None:
        self.image.set_page_text(page_text)

    def set_highlights(self, highlights: tuple[Highlight, ...]) -> None:
        self.image.set_highlights(highlights)

    def set_area_masks(self, masks: tuple[AreaMask, ...]) -> None:
        self.image.set_area_masks(masks)

    def set_mask_mode(self, mode: str | None, shape: str = "rectangle") -> None:
        self.image.set_mask_mode(mode, shape)


@dataclass(frozen=True)
class ZoomAnchor:
    page_index: int
    ratio_x: float
    ratio_y: float
    viewport_x: int
    viewport_y: int


class MainWindow(QMainWindow):
    def __init__(self, version: str = "") -> None:
        super().__init__()
        self.version = version
        self.session = PdfSession()
        self.text_engine = TextEngine()
        self.highlight_store = HighlightStore()
        self.evidence_store = EvidenceStore()
        self.bookmark_store = BookmarkStore()
        self.area_mask_store = AreaMaskStore()
        self.category_store = CategoryProfileStore()
        self.category_profile = self.category_store.load()
        self.bilingual_store = BilingualDictionaryStore()
        self.bilingual_dictionary = self.bilingual_store.load()
        self.document_info: DocumentInfo | None = None
        self.document_text: DocumentText | None = None
        self.highlights: tuple[Highlight, ...] = ()
        self.evidence: tuple[Evidence, ...] = ()
        self.personal_bookmarks: tuple[PersonalBookmark, ...] = ()
        self.area_masks: tuple[AreaMask, ...] = ()
        self._mask_undo_stack: list[tuple[AreaMask, ...]] = []
        self._mask_redo_stack: list[tuple[AreaMask, ...]] = []
        self._mask_replacing_id: str | None = None
        self.search_hits: tuple[SearchHit, ...] = ()
        self._search_keywords: tuple[str, ...] = ()
        self._search_expanded = False
        self._search_bilingual = False
        self._search_task: BackgroundTask | None = None
        self._last_noise_report: SearchNoiseReport | None = None
        self.category_matches: tuple[CategoryMatch, ...] = ()
        self._category_task: BackgroundTask | None = None
        self.standard_matches: tuple[StandardMatch, ...] = ()
        self._standards_task: BackgroundTask | None = None
        self.workspace_paths: list[str] = []
        self.project_name = "Untitled Project"
        self.current_project_path: str | None = None
        self.reading_statuses: dict[str, str] = {}
        self._merge_task: BackgroundTask | None = None
        self._export_task: BackgroundTask | None = None
        self._save_copy_task: BackgroundTask | None = None
        self._workspace_task: BackgroundTask | None = None
        self._workspace_batch_task: BackgroundTask | None = None
        self._workspace_export_task: BackgroundTask | None = None
        self._workspace_summary: WorkspaceSummary | None = None
        self._workspace_dashboard: WorkspaceDashboardDialog | None = None
        self.rotation = 0
        self._view_revision = 0
        self._thumbnail_pending: set[int] = set()
        self.layouts: list[PageLayout] = []
        self.pages: list[PageWidget] = []
        self.current_page = 0
        self.zoom_scale = 1.0
        self.fit_mode = True
        self._generation = 0
        self._zoom_revision = 0
        self._opening = False
        self._render_pending: set[int] = set()
        self._tasks: set[BackgroundTask] = set()
        self._text_tasks: set[BackgroundTask] = set()
        self._text_cancel = Event()

        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.text_pool = QThreadPool(self)
        self.text_pool.setMaxThreadCount(1)
        self.thumbnail_pool = QThreadPool(self)
        self.thumbnail_pool.setMaxThreadCount(1)
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setSingleShot(True)
        self._scroll_timer.setInterval(70)
        self._scroll_timer.timeout.connect(self._refresh_viewport)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(80)
        self._resize_timer.timeout.connect(self._refit_after_resize)
        self._quality_timer = QTimer(self)
        self._quality_timer.setSingleShot(True)
        self._quality_timer.setInterval(180)
        self._quality_timer.timeout.connect(self._refresh_viewport)

        self._build_interface()
        self._apply_style()
        self._set_empty_state()

    def _build_interface(self) -> None:
        self.setWindowTitle("PDF Analyzer")
        self.resize(1360, 880)
        self.setMinimumSize(900, 620)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 12, 18, 12)
        title = QLabel("PDF ANALYZER")
        title.setObjectName("brand")
        header_layout.addWidget(title)
        self.header_file = QLabel("No document open")
        self.header_file.setObjectName("headerFile")
        header_layout.addWidget(self.header_file)
        self.document_picker = QComboBox()
        self.document_picker.setObjectName("documentPicker")
        self.document_picker.setMinimumWidth(230)
        self.document_picker.setMaximumWidth(390)
        self.document_picker.currentIndexChanged.connect(self._workspace_document_changed)
        self.document_picker.hide()
        header_layout.addWidget(self.document_picker)
        header_layout.addStretch()
        self.reading_status_label = QLabel("Reading status")
        self.reading_status_label.setObjectName("toolLabel")
        header_layout.addWidget(self.reading_status_label)
        self.reading_status_combo = QComboBox()
        self.reading_status_combo.addItems(READING_STATUSES)
        self.reading_status_combo.setToolTip("Reading status for the active PDF")
        self.reading_status_combo.currentTextChanged.connect(self._reading_status_changed)
        self.reading_status_combo.setEnabled(False)
        header_layout.addWidget(self.reading_status_combo)
        header_layout.addStretch()
        self.load_project_button = QPushButton("Open Project")
        self.load_project_button.setToolTip("Open a PDF Analyzer project")
        self.load_project_button.clicked.connect(self.load_project_file)
        header_layout.addWidget(self.load_project_button)
        self.save_project_button = QPushButton("Save Project")
        self.save_project_button.setToolTip("Save the PDF list and reading statuses")
        self.save_project_button.clicked.connect(self.save_project_file)
        header_layout.addWidget(self.save_project_button)
        self.merge_button = QPushButton("Combine")
        self.merge_button.setToolTip("Combine the workspace documents into a new PDF")
        self.merge_button.clicked.connect(self.merge_workspace_documents)
        self.merge_button.hide()
        header_layout.addWidget(self.merge_button)
        self.open_button = QPushButton("Open PDFs")
        self.open_button.setObjectName("primaryButton")
        self.open_button.clicked.connect(self.choose_pdf)
        header_layout.addWidget(self.open_button)
        root_layout.addWidget(header)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(245)
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(20, 22, 20, 20)
        side_layout.setSpacing(8)
        section = QLabel("DOCUMENT")
        section.setObjectName("sectionTitle")
        side_layout.addWidget(section)
        self.document_name = QLabel("—")
        self.document_name.setObjectName("documentName")
        self.document_name.setWordWrap(True)
        side_layout.addWidget(self.document_name)
        self.document_path = QLabel("")
        self.document_path.setObjectName("muted")
        self.document_path.setWordWrap(True)
        side_layout.addWidget(self.document_path)
        side_layout.addSpacing(16)
        self.page_info = QLabel("Pages\n—")
        self.page_info.setObjectName("infoValue")
        side_layout.addWidget(self.page_info)
        self.size_info = QLabel("Size\n—")
        self.size_info.setObjectName("infoValue")
        side_layout.addWidget(self.size_info)
        side_layout.addSpacing(14)
        text_section = QLabel("TEXT AND OCR")
        text_section.setObjectName("sectionTitle")
        side_layout.addWidget(text_section)
        self.text_info = QLabel("Open a document")
        self.text_info.setObjectName("textInfo")
        self.text_info.setWordWrap(True)
        side_layout.addWidget(self.text_info)
        self.ocr_button = QPushButton("Run OCR")
        self.ocr_button.setToolTip("Process only pages without text, entirely offline")
        self.ocr_button.clicked.connect(self.run_ocr)
        self.ocr_button.setEnabled(False)
        side_layout.addStretch()
        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)
        side_layout.addWidget(self.status_label)
        if self.version:
            version_label = QLabel(self.version)
            version_label.setObjectName("version")
            side_layout.addWidget(version_label)
        body_layout.addWidget(self.sidebar)
        self.sidebar.hide()

        workspace = QWidget()
        workspace.setObjectName("workspace")
        workspace_layout = QVBoxLayout(workspace)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        toolbar = QFrame()
        toolbar.setObjectName("toolbar")
        toolbar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        toolbar.setFixedHeight(48)
        tools = QHBoxLayout(toolbar)
        tools.setContentsMargins(14, 8, 14, 8)
        tools.setSpacing(6)
        self.previous_button = QPushButton("‹")
        self.previous_button.setToolTip("Previous page")
        self.previous_button.clicked.connect(lambda: self.go_to_page(self.current_page - 1))
        tools.addWidget(self.previous_button)
        self.page_spin = QSpinBox()
        self.page_spin.setRange(0, 0)
        self.page_spin.setPrefix("Page ")
        self.page_spin.valueChanged.connect(lambda value: self.go_to_page(value - 1))
        tools.addWidget(self.page_spin)
        self.page_total = QLabel("of —")
        self.page_total.setObjectName("toolLabel")
        tools.addWidget(self.page_total)
        self.next_button = QPushButton("›")
        self.next_button.setToolTip("Next page")
        self.next_button.clicked.connect(lambda: self.go_to_page(self.current_page + 1))
        tools.addWidget(self.next_button)
        self.evidence_button = QPushButton("Analysis (0)")
        self.evidence_button.setCheckable(True)
        self.evidence_button.setToolTip("Show or hide notes, tags and search tools")
        self.evidence_button.toggled.connect(self._toggle_evidence_panel)
        tools.addWidget(self.evidence_button)
        self.dashboard_button = QPushButton("Dashboard")
        self.dashboard_button.setToolTip(
            "Open the consolidated multi-document analysis dashboard"
        )
        self.dashboard_button.clicked.connect(self.show_workspace_dashboard)
        tools.addWidget(self.dashboard_button)
        self.ocr_button.setText("OCR")
        tools.addWidget(self.ocr_button)
        self.details_button = QPushButton("Details")
        self.details_button.setCheckable(True)
        self.details_button.setToolTip("Show document information and text status")
        self.details_button.toggled.connect(self.sidebar.setVisible)
        tools.addWidget(self.details_button)
        self.navigation_button = QPushButton("Pages")
        self.navigation_button.setCheckable(True)
        self.navigation_button.setToolTip("Show page thumbnails and PDF bookmarks")
        self.navigation_button.toggled.connect(self._toggle_navigation_panel)
        tools.addWidget(self.navigation_button)
        self.mask_button = QPushButton("Masks")
        self.mask_button.setToolTip("Draw keep or ignore areas over PDF pages")
        self.mask_button.clicked.connect(self._show_masks_tab)
        tools.addWidget(self.mask_button)
        self.rotate_button = QPushButton("Rotate")
        self.rotate_button.setToolTip("Rotate the document clockwise")
        self.rotate_button.clicked.connect(self.rotate_clockwise)
        tools.addWidget(self.rotate_button)
        self.print_button = QPushButton("Print")
        self.print_button.clicked.connect(self.print_document)
        tools.addWidget(self.print_button)
        self.save_copy_button = QPushButton("Save")
        self.save_copy_button.setToolTip("Save an unchanged copy of the active PDF")
        self.save_copy_button.clicked.connect(self.save_document_as)
        tools.addWidget(self.save_copy_button)
        self.export_button = QPushButton("Export")
        self.export_button.setToolTip("Create a PDF with a tag report, highlights and comments")
        self.export_button.clicked.connect(self.export_annotated_document)
        tools.addWidget(self.export_button)
        tools.addStretch()
        self.fit_button = QPushButton("Fit Page")
        self.fit_button.setToolTip("Fit one complete page in the window")
        self.fit_button.clicked.connect(self.fit_current_page)
        tools.addWidget(self.fit_button)
        self.zoom_out_button = QPushButton("−")
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_out_button.clicked.connect(lambda: self.zoom_from_center(-1))
        tools.addWidget(self.zoom_out_button)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoomLabel")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label.setFixedWidth(58)
        tools.addWidget(self.zoom_label)
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_in_button.clicked.connect(lambda: self.zoom_from_center(1))
        tools.addWidget(self.zoom_in_button)
        self.fullscreen_button = QPushButton("Full")
        self.fullscreen_button.setToolTip("Enter or exit fullscreen mode (F11)")
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        tools.addWidget(self.fullscreen_button)
        workspace_layout.addWidget(toolbar)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("viewer")
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self.scroll.viewport().installEventFilter(self)
        self.scroll.verticalScrollBar().valueChanged.connect(self._on_scrolled)
        self.scroll.horizontalScrollBar().valueChanged.connect(self._on_scrolled)
        self.page_host = QWidget()
        self.page_host.setObjectName("pageHost")
        self.page_layout = QVBoxLayout(self.page_host)
        self.page_layout.setContentsMargins(24, 24, 24, 24)
        self.page_layout.setSpacing(22)
        self.page_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.empty_label = QLabel("Open a PDF document to begin")
        self.empty_label.setObjectName("emptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_layout.addWidget(self.empty_label)
        self.scroll.setWidget(self.page_host)

        self.evidence_panel = QFrame()
        self.evidence_panel.setObjectName("evidencePanel")
        self.evidence_panel.setMinimumWidth(320)
        self.evidence_panel.setMaximumWidth(500)
        evidence_layout = QVBoxLayout(self.evidence_panel)
        evidence_layout.setContentsMargins(14, 14, 14, 14)
        evidence_layout.setSpacing(9)
        evidence_header = QHBoxLayout()
        evidence_title = QLabel("DOCUMENT ANALYSIS")
        evidence_title.setObjectName("sectionTitle")
        evidence_header.addWidget(evidence_title)
        evidence_header.addStretch()
        self.close_evidence_button = QPushButton("×")
        self.close_evidence_button.setObjectName("compactButton")
        self.close_evidence_button.setToolTip("Close panel")
        self.close_evidence_button.clicked.connect(lambda: self.evidence_button.setChecked(False))
        evidence_header.addWidget(self.close_evidence_button)
        evidence_layout.addLayout(evidence_header)
        self.analysis_tabs = QTabWidget()
        self.analysis_tabs.setObjectName("analysisTabs")

        evidence_tab = QWidget()
        evidence_tab_layout = QVBoxLayout(evidence_tab)
        evidence_tab_layout.setContentsMargins(4, 10, 4, 4)
        evidence_tab_layout.setSpacing(9)
        evidence_hint = QLabel("Check tags to filter notes and select report content. Click a note to open its source.")
        evidence_hint.setObjectName("muted")
        evidence_hint.setWordWrap(True)
        evidence_tab_layout.addWidget(evidence_hint)
        tag_label = QLabel("REPORT TAGS")
        tag_label.setObjectName("sectionTitle")
        evidence_tab_layout.addWidget(tag_label)
        self.tag_list = QListWidget()
        self.tag_list.setObjectName("tagList")
        self.tag_list.setMaximumHeight(125)
        self.tag_list.itemChanged.connect(self._tag_selection_changed)
        evidence_tab_layout.addWidget(self.tag_list)
        notes_label = QLabel("NOTES")
        notes_label.setObjectName("sectionTitle")
        evidence_tab_layout.addWidget(notes_label)
        self.evidence_list = QListWidget()
        self.evidence_list.setObjectName("evidenceList")
        self.evidence_list.setWordWrap(True)
        self.evidence_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.evidence_list.itemClicked.connect(self._evidence_item_clicked)
        self.evidence_list.currentItemChanged.connect(self._evidence_selection_changed)
        evidence_tab_layout.addWidget(self.evidence_list, 1)
        evidence_actions = QHBoxLayout()
        self.copy_evidence_button = QPushButton("Copy")
        self.copy_evidence_button.clicked.connect(self._copy_selected_evidence)
        evidence_actions.addWidget(self.copy_evidence_button)
        self.remove_evidence_button = QPushButton("Remove")
        self.remove_evidence_button.clicked.connect(self._remove_selected_evidence)
        evidence_actions.addWidget(self.remove_evidence_button)
        evidence_tab_layout.addLayout(evidence_actions)
        self.analysis_tabs.addTab(evidence_tab, "Tags")

        search_tab = QWidget()
        search_tab_layout = QVBoxLayout(search_tab)
        search_tab_layout.setContentsMargins(4, 10, 4, 4)
        search_tab_layout.setSpacing(9)
        search_hint = QLabel("Enter one term per line or paste a Markdown list.")
        search_hint.setObjectName("muted")
        search_hint.setWordWrap(True)
        search_tab_layout.addWidget(search_hint)
        self.search_mode = QComboBox()
        self.search_mode.addItems(
            ("Exact Search", "Expanded Search", "Bilingual Search RO/EN")
        )
        self.search_mode.setToolTip(
            "Expanded Search adds visible grammatical variants, technical synonyms and "
            "abbreviations. Bilingual Search also adds controlled Romanian-English equivalents."
        )
        self.search_mode.currentIndexChanged.connect(self._refresh_search_expansion_preview)
        search_mode_row = QHBoxLayout()
        search_mode_row.addWidget(self.search_mode, 1)
        self.edit_dictionary_button = QPushButton("Edit Dictionary")
        self.edit_dictionary_button.setToolTip(
            "Edit the local Romanian-English search equivalents"
        )
        self.edit_dictionary_button.clicked.connect(self.edit_bilingual_dictionary)
        search_mode_row.addWidget(self.edit_dictionary_button)
        search_tab_layout.addLayout(search_mode_row)
        self.keyword_input = QTextEdit()
        self.keyword_input.setObjectName("keywordInput")
        self.keyword_input.setPlaceholderText(
            "Deadline\nDelivery schedule\nLead time\nPenalty for delay"
        )
        self.keyword_input.setMaximumHeight(150)
        self.keyword_input.textChanged.connect(self._refresh_search_expansion_preview)
        search_tab_layout.addWidget(self.keyword_input)
        self.search_expansion_preview = QLabel("Exact Search · no terms")
        self.search_expansion_preview.setObjectName("muted")
        self.search_expansion_preview.setWordWrap(True)
        search_tab_layout.addWidget(self.search_expansion_preview)
        filter_label = QLabel("SEARCH NOISE FILTERS")
        filter_label.setObjectName("sectionTitle")
        search_tab_layout.addWidget(filter_label)
        filter_row_one = QHBoxLayout()
        self.ignore_headers_check = QCheckBox("Headers")
        self.ignore_headers_check.setToolTip("Ignore text in the top 8% of every page")
        self.ignore_headers_check.setChecked(True)
        filter_row_one.addWidget(self.ignore_headers_check)
        self.ignore_footers_check = QCheckBox("Footers")
        self.ignore_footers_check.setToolTip("Ignore text in the bottom 8% of every page")
        self.ignore_footers_check.setChecked(True)
        filter_row_one.addWidget(self.ignore_footers_check)
        search_tab_layout.addLayout(filter_row_one)
        filter_row_two = QHBoxLayout()
        self.ignore_page_numbers_check = QCheckBox("Page numbers")
        self.ignore_page_numbers_check.setToolTip(
            "Ignore page-number-only lines near page edges"
        )
        self.ignore_page_numbers_check.setChecked(True)
        filter_row_two.addWidget(self.ignore_page_numbers_check)
        self.hide_repeated_text_check = QCheckBox("Repeated text")
        self.hide_repeated_text_check.setToolTip(
            "Ignore identical short blocks found on most pages"
        )
        self.hide_repeated_text_check.setChecked(True)
        filter_row_two.addWidget(self.hide_repeated_text_check)
        search_tab_layout.addLayout(filter_row_two)
        for checkbox in (
            self.ignore_headers_check,
            self.ignore_footers_check,
            self.ignore_page_numbers_check,
            self.hide_repeated_text_check,
        ):
            checkbox.stateChanged.connect(self._noise_options_changed)
        self.search_button = QPushButton("Search Document")
        self.search_button.setObjectName("primaryButton")
        self.search_button.setEnabled(False)
        self.search_button.clicked.connect(self.run_keyword_search)
        search_tab_layout.addWidget(self.search_button)
        self.search_summary = QLabel("No search has been run")
        self.search_summary.setObjectName("muted")
        self.search_summary.setWordWrap(True)
        search_tab_layout.addWidget(self.search_summary)
        self.search_tree = QTreeWidget()
        self.search_tree.setObjectName("searchTree")
        self.search_tree.setHeaderHidden(True)
        self.search_tree.setUniformRowHeights(False)
        self.search_tree.itemClicked.connect(self._search_item_clicked)
        self.search_tree.currentItemChanged.connect(self._search_selection_changed)
        search_tab_layout.addWidget(self.search_tree, 1)
        self.add_search_evidence_button = QPushButton("Create Note")
        self.add_search_evidence_button.setEnabled(False)
        self.add_search_evidence_button.clicked.connect(self._add_selected_search_to_evidence)
        search_tab_layout.addWidget(self.add_search_evidence_button)
        self.analysis_tabs.addTab(search_tab, "Search")

        category_tab = QWidget()
        category_layout = QVBoxLayout(category_tab)
        category_layout.setContentsMargins(4, 10, 4, 4)
        category_layout.setSpacing(9)
        self.category_profile_label = QLabel(self._category_profile_text())
        self.category_profile_label.setObjectName("muted")
        self.category_profile_label.setWordWrap(True)
        category_layout.addWidget(self.category_profile_label)
        category_actions = QHBoxLayout()
        self.edit_categories_button = QPushButton("Edit")
        self.edit_categories_button.setToolTip("Edit search categories and profile terms")
        self.edit_categories_button.clicked.connect(self.edit_categories)
        category_actions.addWidget(self.edit_categories_button)
        self.category_button = QPushButton("Analyze")
        self.category_button.setObjectName("primaryButton")
        self.category_button.setToolTip(
            "Analyze and automatically save every result as a tagged note"
        )
        self.category_button.setEnabled(False)
        self.category_button.clicked.connect(self.run_category_analysis)
        category_actions.addWidget(self.category_button, 1)
        category_layout.addLayout(category_actions)
        state_actions = QHBoxLayout()
        self.load_state_button = QPushButton("Load Profile")
        self.load_state_button.setToolTip("Load categories and search terms from a file")
        self.load_state_button.clicked.connect(self.load_analysis_state_file)
        state_actions.addWidget(self.load_state_button)
        self.save_state_button = QPushButton("Save Profile")
        self.save_state_button.setToolTip("Share categories and search terms with a colleague")
        self.save_state_button.clicked.connect(self.save_analysis_state_file)
        state_actions.addWidget(self.save_state_button)
        category_layout.addLayout(state_actions)
        self.category_summary = QLabel(
            "Analyze automatically saves every result as a tagged note."
        )
        self.category_summary.setObjectName("muted")
        self.category_summary.setWordWrap(True)
        category_layout.addWidget(self.category_summary)
        self.category_tree = QTreeWidget()
        self.category_tree.setObjectName("categoryTree")
        self.category_tree.setHeaderHidden(True)
        self.category_tree.itemClicked.connect(self._category_item_clicked)
        self.category_tree.currentItemChanged.connect(self._category_selection_changed)
        category_layout.addWidget(self.category_tree, 1)
        self.add_category_evidence_button = QPushButton("Create Custom Note")
        self.add_category_evidence_button.setEnabled(False)
        self.add_category_evidence_button.clicked.connect(self._add_selected_category_to_evidence)
        category_layout.addWidget(self.add_category_evidence_button)
        self.analysis_tabs.addTab(category_tab, "Categories")

        standards_tab = QWidget()
        standards_layout = QVBoxLayout(standards_tab)
        standards_layout.setContentsMargins(4, 10, 4, 4)
        standards_layout.setSpacing(9)
        standards_hint = QLabel(
            "Detect standards, material certificates and technical document codes with obligation context."
        )
        standards_hint.setObjectName("muted")
        standards_hint.setWordWrap(True)
        standards_layout.addWidget(standards_hint)
        self.standards_button = QPushButton("Analyze Standards")
        self.standards_button.setObjectName("primaryButton")
        self.standards_button.setToolTip(
            "Analyze and automatically save every result as a tagged note"
        )
        self.standards_button.setEnabled(False)
        self.standards_button.clicked.connect(self.run_standards_analysis)
        standards_layout.addWidget(self.standards_button)
        self.standards_summary = QLabel(
            "Analyze Standards automatically saves every result as a tagged note."
        )
        self.standards_summary.setObjectName("muted")
        self.standards_summary.setWordWrap(True)
        standards_layout.addWidget(self.standards_summary)
        self.standards_tree = QTreeWidget()
        self.standards_tree.setHeaderHidden(True)
        self.standards_tree.itemClicked.connect(self._standard_item_clicked)
        self.standards_tree.currentItemChanged.connect(self._standard_selection_changed)
        standards_layout.addWidget(self.standards_tree, 1)
        self.add_standard_note_button = QPushButton("Create Custom Note")
        self.add_standard_note_button.setEnabled(False)
        self.add_standard_note_button.clicked.connect(self._add_selected_standard_to_evidence)
        standards_layout.addWidget(self.add_standard_note_button)
        self.analysis_tabs.addTab(standards_tab, "Standards")

        masks_tab = QWidget()
        masks_layout = QVBoxLayout(masks_tab)
        masks_layout.setContentsMargins(4, 10, 4, 4)
        masks_layout.setSpacing(9)
        masks_hint = QLabel(
            "Draw red Ignore areas or green Keep areas. Masks affect analysis only."
        )
        masks_hint.setObjectName("muted")
        masks_hint.setWordWrap(True)
        masks_layout.addWidget(masks_hint)
        mask_settings = QHBoxLayout()
        self.mask_kind_combo = QComboBox()
        self.mask_kind_combo.addItem("Ignore area", "ignore")
        self.mask_kind_combo.addItem("Keep area", "keep")
        self.mask_kind_combo.currentIndexChanged.connect(self._refresh_mask_drawing_mode)
        mask_settings.addWidget(self.mask_kind_combo, 1)
        self.mask_shape_combo = QComboBox()
        self.mask_shape_combo.addItem("Rectangle", "rectangle")
        self.mask_shape_combo.addItem("Freehand", "freehand")
        self.mask_shape_combo.addItem("Polygon", "polygon")
        self.mask_shape_combo.currentIndexChanged.connect(self._mask_shape_changed)
        mask_settings.addWidget(self.mask_shape_combo, 1)
        masks_layout.addLayout(mask_settings)
        mask_scope_row = QHBoxLayout()
        self.mask_scope_combo = QComboBox()
        self.mask_scope_combo.addItem("Current page", "page")
        self.mask_scope_combo.addItem("All pages", "all")
        mask_scope_row.addWidget(self.mask_scope_combo, 1)
        self.draw_mask_button = QPushButton("Draw Rectangle")
        self.draw_mask_button.setCheckable(True)
        self.draw_mask_button.setObjectName("primaryButton")
        self.draw_mask_button.toggled.connect(self._mask_drawing_toggled)
        mask_scope_row.addWidget(self.draw_mask_button, 1)
        masks_layout.addLayout(mask_scope_row)
        self.mask_summary = QLabel("No visual masks")
        self.mask_summary.setObjectName("muted")
        self.mask_summary.setWordWrap(True)
        masks_layout.addWidget(self.mask_summary)
        self.mask_list = QListWidget()
        self.mask_list.itemClicked.connect(self._mask_item_clicked)
        self.mask_list.currentItemChanged.connect(self._mask_selection_changed)
        masks_layout.addWidget(self.mask_list, 1)
        mask_actions = QHBoxLayout()
        self.redraw_mask_button = QPushButton("Redraw")
        self.redraw_mask_button.clicked.connect(self.redraw_selected_mask)
        mask_actions.addWidget(self.redraw_mask_button)
        self.remove_mask_button = QPushButton("Remove")
        self.remove_mask_button.clicked.connect(self.remove_selected_mask)
        mask_actions.addWidget(self.remove_mask_button)
        self.clear_masks_button = QPushButton("Clear All")
        self.clear_masks_button.clicked.connect(self.clear_all_masks)
        mask_actions.addWidget(self.clear_masks_button)
        masks_layout.addLayout(mask_actions)
        mask_apply_actions = QHBoxLayout()
        self.copy_mask_pages_button = QPushButton("Copy Pages")
        self.copy_mask_pages_button.clicked.connect(self.copy_mask_to_pages)
        mask_apply_actions.addWidget(self.copy_mask_pages_button)
        self.similar_pages_button = QPushButton("Apply Similar")
        self.similar_pages_button.clicked.connect(self.apply_mask_to_similar_pages)
        mask_apply_actions.addWidget(self.similar_pages_button)
        masks_layout.addLayout(mask_apply_actions)
        mask_history_actions = QHBoxLayout()
        self.undo_mask_button = QPushButton("Undo")
        self.undo_mask_button.clicked.connect(self.undo_mask_change)
        mask_history_actions.addWidget(self.undo_mask_button)
        self.redo_mask_button = QPushButton("Redo")
        self.redo_mask_button.clicked.connect(self.redo_mask_change)
        mask_history_actions.addWidget(self.redo_mask_button)
        masks_layout.addLayout(mask_history_actions)
        mask_profile_actions = QHBoxLayout()
        self.load_masks_button = QPushButton("Load Profile")
        self.load_masks_button.clicked.connect(self.load_mask_profile_file)
        mask_profile_actions.addWidget(self.load_masks_button)
        self.save_masks_button = QPushButton("Save Profile")
        self.save_masks_button.clicked.connect(self.save_mask_profile_file)
        mask_profile_actions.addWidget(self.save_masks_button)
        masks_layout.addLayout(mask_profile_actions)
        self.analysis_tabs.addTab(masks_tab, "Masks")
        evidence_layout.addWidget(self.analysis_tabs, 1)
        self.evidence_panel.hide()

        self.navigation_panel = QFrame()
        self.navigation_panel.setObjectName("navigationPanel")
        self.navigation_panel.setMinimumWidth(180)
        self.navigation_panel.setMaximumWidth(280)
        navigation_layout = QVBoxLayout(self.navigation_panel)
        navigation_layout.setContentsMargins(8, 8, 8, 8)
        self.navigation_tabs = QTabWidget()
        self.thumbnail_list = QListWidget()
        self.thumbnail_list.setIconSize(QSize(120, 170))
        self.thumbnail_list.setSpacing(6)
        self.thumbnail_list.currentRowChanged.connect(self._thumbnail_selected)
        self.thumbnail_list.verticalScrollBar().valueChanged.connect(self._refresh_visible_thumbnails)
        self.navigation_tabs.addTab(self.thumbnail_list, "Pages")
        self.outline_tree = QTreeWidget()
        self.outline_tree.setHeaderHidden(True)
        self.outline_tree.itemClicked.connect(self._outline_selected)
        self.outline_tree.currentItemChanged.connect(self._bookmark_selection_changed)
        self.navigation_tabs.addTab(self.outline_tree, "Bookmarks")
        navigation_layout.addWidget(self.navigation_tabs)
        bookmark_actions = QHBoxLayout()
        self.add_bookmark_button = QPushButton("Add")
        self.add_bookmark_button.clicked.connect(self.add_personal_bookmark)
        bookmark_actions.addWidget(self.add_bookmark_button)
        self.rename_bookmark_button = QPushButton("Rename")
        self.rename_bookmark_button.clicked.connect(self.rename_personal_bookmark)
        bookmark_actions.addWidget(self.rename_bookmark_button)
        self.delete_bookmark_button = QPushButton("Delete")
        self.delete_bookmark_button.clicked.connect(self.delete_personal_bookmark)
        bookmark_actions.addWidget(self.delete_bookmark_button)
        navigation_layout.addLayout(bookmark_actions)
        hierarchy_actions = QHBoxLayout()
        self.bookmark_up_button = QPushButton("Up")
        self.bookmark_up_button.clicked.connect(
            lambda: self.move_personal_bookmark(-1)
        )
        hierarchy_actions.addWidget(self.bookmark_up_button)
        self.bookmark_down_button = QPushButton("Down")
        self.bookmark_down_button.clicked.connect(
            lambda: self.move_personal_bookmark(1)
        )
        hierarchy_actions.addWidget(self.bookmark_down_button)
        self.bookmark_indent_button = QPushButton("Indent")
        self.bookmark_indent_button.clicked.connect(self.indent_personal_bookmark)
        hierarchy_actions.addWidget(self.bookmark_indent_button)
        self.bookmark_outdent_button = QPushButton("Outdent")
        self.bookmark_outdent_button.clicked.connect(self.outdent_personal_bookmark)
        hierarchy_actions.addWidget(self.bookmark_outdent_button)
        navigation_layout.addLayout(hierarchy_actions)
        self.bookmarks_from_notes_button = QPushButton("Generate from Notes and Tags")
        self.bookmarks_from_notes_button.clicked.connect(
            self.generate_bookmarks_from_notes
        )
        navigation_layout.addWidget(self.bookmarks_from_notes_button)
        self.navigation_panel.hide()

        self.viewer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.viewer_splitter.setObjectName("viewerSplitter")
        self.viewer_splitter.setChildrenCollapsible(False)
        self.viewer_splitter.addWidget(self.navigation_panel)
        self.viewer_splitter.addWidget(self.evidence_panel)
        self.viewer_splitter.addWidget(self.scroll)
        self.viewer_splitter.setStretchFactor(0, 0)
        self.viewer_splitter.setStretchFactor(1, 0)
        self.viewer_splitter.setStretchFactor(2, 1)
        self.viewer_splitter.setSizes([220, 390, 900])
        workspace_layout.addWidget(self.viewer_splitter, 1)
        body_layout.addWidget(workspace, 1)
        root_layout.addWidget(body, 1)
        self.setCentralWidget(root)

        QShortcut(QKeySequence.StandardKey.Open, self, activated=self.choose_pdf)
        QShortcut(QKeySequence.StandardKey.SaveAs, self, activated=self.save_document_as)
        QShortcut(QKeySequence.StandardKey.Print, self, activated=self.print_document)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.fit_current_page)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self.rotate_clockwise)
        QShortcut(QKeySequence("F11"), self, activated=self.toggle_fullscreen)

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            * { font-family: "Segoe UI"; font-size: 13px; color: #25313d; }
            QMainWindow, QDialog, QWidget { background-color: #ffffff; color: #25313d; }
            QMainWindow, QWidget#workspace { background: #eef1f4; }
            QFrame#header { background: #ffffff; border-bottom: 1px solid #d8dee5; }
            QLabel#brand { font-size: 14px; font-weight: 700; letter-spacing: 1px; color: #17212b; }
            QLabel#headerFile { color: #7a8794; padding-left: 12px; }
            QFrame#sidebar { background: #f8fafb; border-right: 1px solid #d8dee5; }
            QLabel#sectionTitle { color: #7a8794; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
            QLabel#documentName { color: #17212b; font-size: 14px; font-weight: 600; }
            QLabel#muted, QLabel#version { color: #8a96a3; font-size: 11px; }
            QLabel#infoValue { color: #667482; line-height: 1.5; }
            QLabel#textInfo { color: #536273; background: #ffffff; border: 1px solid #dbe1e6; border-radius: 4px; padding: 9px; }
            QLabel#status { color: #536273; background: #edf1f5; border-radius: 4px; padding: 9px; }
            QFrame#toolbar { background: #ffffff; border-bottom: 1px solid #d8dee5; }
            QFrame#evidencePanel { background: #f8fafb; border-right: 1px solid #cfd7df; }
            QListWidget#evidenceList, QListWidget#tagList { background: #ffffff; border: 1px solid #d8dee5; border-radius: 4px; outline: none; padding: 4px; }
            QListWidget#evidenceList::item { border-bottom: 1px solid #e5e9ed; padding: 10px 8px; }
            QListWidget#evidenceList::item:selected { background: #e5f0f8; color: #17212b; }
            QTreeWidget#searchTree, QTreeWidget#categoryTree { background: #ffffff; border: 1px solid #d8dee5; border-radius: 4px; outline: none; padding: 3px; }
            QTreeWidget#searchTree::item, QTreeWidget#categoryTree::item { padding: 5px 3px; }
            QTreeWidget#searchTree::item:selected, QTreeWidget#categoryTree::item:selected { background: #e5f0f8; color: #17212b; }
            QLineEdit, QTextEdit, QComboBox, QListWidget, QTreeWidget, QSpinBox {
                background-color: #ffffff; color: #25313d; border: 1px solid #cbd3dc;
                selection-background-color: #2d7ed8; selection-color: #ffffff;
            }
            QTextEdit#keywordInput { background: #ffffff; border: 1px solid #cbd3dc; border-radius: 4px; padding: 7px; selection-background-color: #2d7ed8; }
            QTabWidget#analysisTabs::pane { border: none; }
            QTabBar::tab { background: #edf1f4; border: 1px solid #d5dce3; padding: 7px 13px; }
            QTabBar::tab:selected { background: #ffffff; color: #17212b; }
            QLabel#toolLabel { color: #71808e; }
            QLabel#zoomLabel { color: #475563; font-weight: 600; }
            QPushButton { background: #ffffff; border: 1px solid #cbd3dc; border-radius: 4px; min-height: 30px; padding: 0 11px; }
            QPushButton:hover { background: #f2f5f7; border-color: #aeb9c4; }
            QPushButton:pressed { background: #e8edf1; }
            QPushButton:disabled { color: #aab3bc; background: #f5f6f7; }
            QPushButton#primaryButton { color: #ffffff; background: #246b9e; border-color: #246b9e; font-weight: 600; padding: 0 16px; }
            QPushButton#primaryButton:hover { background: #1d5d8b; }
            QPushButton#compactButton { min-width: 28px; max-width: 28px; padding: 0; }
            QSpinBox { background: #ffffff; border: 1px solid #cbd3dc; border-radius: 4px; min-height: 30px; padding-left: 7px; }
            QScrollArea#viewer { border: none; background: #dfe4e8; }
            QWidget#pageHost { background: #dfe4e8; }
            QFrame#pageContainer { background: transparent; border: none; }
            QWidget#pageCanvas { background: #ffffff; }
            QLabel#pageCaption { color: #677582; font-size: 11px; }
            QLabel#emptyState { color: #73808c; font-size: 15px; padding: 80px; }
            QScrollBar:vertical { background: #edf0f2; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #aeb8c1; min-height: 35px; border-radius: 5px; margin: 2px; }
            QScrollBar:horizontal { background: #edf0f2; height: 12px; margin: 0; }
            QScrollBar::handle:horizontal { background: #aeb8c1; min-width: 35px; border-radius: 5px; margin: 2px; }
            QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
        """)

    def _set_empty_state(self) -> None:
        self._set_document_controls(False)

    def _set_document_controls(self, enabled: bool) -> None:
        for control in (
            self.previous_button,
            self.next_button,
            self.page_spin,
            self.evidence_button,
            self.dashboard_button,
            self.details_button,
            self.export_button,
            self.fit_button,
            self.zoom_out_button,
            self.zoom_in_button,
            self.reading_status_combo,
            self.navigation_button,
            self.mask_button,
            self.draw_mask_button,
            self.mask_kind_combo,
            self.mask_shape_combo,
            self.mask_scope_combo,
            self.load_masks_button,
            self.save_masks_button,
            self.remove_mask_button,
            self.redraw_mask_button,
            self.clear_masks_button,
            self.copy_mask_pages_button,
            self.similar_pages_button,
            self.undo_mask_button,
            self.redo_mask_button,
            self.add_bookmark_button,
            self.rename_bookmark_button,
            self.delete_bookmark_button,
            self.bookmark_up_button,
            self.bookmark_down_button,
            self.bookmark_indent_button,
            self.bookmark_outdent_button,
            self.bookmarks_from_notes_button,
            self.rotate_button,
            self.print_button,
            self.save_copy_button,
        ):
            control.setEnabled(enabled)
        if enabled:
            self._bookmark_selection_changed(self.outline_tree.currentItem(), None)
            self._refresh_mask_list()

    @Slot()
    def choose_pdf(self) -> None:
        if self._opening:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Open one or more PDFs", "", "PDF documents (*.pdf)"
        )
        if paths:
            self.add_workspace_documents(tuple(paths), open_first=True)

    def add_workspace_documents(self, paths: tuple[str, ...], open_first: bool = True) -> None:
        normalized = [str(Path(path).resolve()) for path in paths]
        first = normalized[0] if normalized else None
        for path in normalized:
            if path not in self.workspace_paths:
                self.workspace_paths.append(path)
            self.reading_statuses.setdefault(normalize_path(path), "Not Read")
        self._workspace_summary = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.mark_stale()
        self._refresh_document_picker(first if open_first else None)
        if open_first and first:
            self.open_path(first)

    def _reading_status_changed(self, status: str) -> None:
        if self.document_info is None or status not in READING_STATUSES:
            return
        path = self.document_info.path
        self.reading_statuses[normalize_path(path)] = status
        if self._workspace_summary is not None:
            self._workspace_summary = update_workspace_status(
                self._workspace_summary,
                path,
                status,
            )
            if self._workspace_dashboard is not None:
                self._workspace_dashboard.set_summary(self._workspace_summary)

    def _sync_reading_status(self, path: str) -> None:
        status = self.reading_statuses.setdefault(normalize_path(path), "Not Read")
        self.reading_status_combo.blockSignals(True)
        self.reading_status_combo.setCurrentText(status)
        self.reading_status_combo.blockSignals(False)

    def _project_state(self, project_name: str | None = None) -> ProjectState:
        return ProjectState(
            project_name=(project_name or self.project_name).strip(),
            documents=tuple(
                ProjectDocument(
                    path,
                    self.reading_statuses.get(normalize_path(path), "Not Read"),
                )
                for path in self.workspace_paths
            ),
        )

    def save_project_file(self) -> None:
        if not self.workspace_paths:
            QMessageBox.information(
                self,
                "Empty project",
                "Open at least one PDF before saving a project.",
            )
            return
        suggested = self.current_project_path or "PDF Analyzer Project.pdfanalyzer-project.json"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF Analyzer project",
            suggested,
            "PDF Analyzer Project (*.pdfanalyzer-project.json);;JSON files (*.json)",
        )
        if not path:
            return
        if not path.casefold().endswith(".json"):
            path += ".pdfanalyzer-project.json"
        name = Path(path).name
        suffix = ".pdfanalyzer-project.json"
        project_name = name[: -len(suffix)] if name.casefold().endswith(suffix) else Path(path).stem
        try:
            save_project(path, self._project_state(project_name))
        except (OSError, ValueError, ProjectStateError) as error:
            QMessageBox.warning(self, "Project not saved", str(error))
            return
        self.current_project_path = str(Path(path).resolve())
        self.project_name = project_name
        self.status_label.setText(f"Project saved: {Path(path).name}")

    def load_project_file(self) -> None:
        if self._opening:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF Analyzer project",
            "",
            "PDF Analyzer Project (*.pdfanalyzer-project.json *.json)",
        )
        if not path:
            return
        try:
            project = load_project(path)
        except (OSError, ValueError, ProjectStateError) as error:
            QMessageBox.warning(self, "Invalid project", str(error))
            return
        existing = [document.path for document in project.documents if Path(document.path).is_file()]
        missing = [document.path for document in project.documents if not Path(document.path).is_file()]
        if not existing:
            QMessageBox.warning(
                self,
                "Project PDFs not found",
                "None of the PDFs referenced by this project can be found. Move the project file "
                "together with its PDF files or restore the original paths.",
            )
            return
        self.project_name = project.project_name
        self.current_project_path = str(Path(path).resolve())
        self.workspace_paths = [document.path for document in project.documents]
        self.reading_statuses = {
            normalize_path(document.path): document.reading_status
            for document in project.documents
        }
        self._workspace_summary = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.mark_stale()
        self._refresh_document_picker(existing[0])
        self.open_path(existing[0])
        if missing:
            preview = "\n".join(f"• {item}" for item in missing[:8])
            extra = f"\n…and {len(missing) - 8} more" if len(missing) > 8 else ""
            QMessageBox.warning(
                self,
                "Some project PDFs are missing",
                f"The project was loaded, but these files could not be found:\n\n{preview}{extra}",
            )

    def _refresh_document_picker(self, selected_path: str | None = None) -> None:
        selected = selected_path or (self.document_info.path if self.document_info else None)
        self.document_picker.blockSignals(True)
        self.document_picker.clear()
        selected_index = 0
        for index, path in enumerate(self.workspace_paths):
            missing = not Path(path).is_file()
            label = f"{index + 1}. {Path(path).name}" + (" [missing]" if missing else "")
            self.document_picker.addItem(label, path)
            self.document_picker.setItemData(index, path, Qt.ItemDataRole.ToolTipRole)
            if selected and path == str(Path(selected).resolve()):
                selected_index = index
        if self.workspace_paths:
            self.document_picker.setCurrentIndex(selected_index)
        self.document_picker.blockSignals(False)
        multiple = len(self.workspace_paths) > 1
        self.document_picker.setVisible(multiple)
        self.header_file.setVisible(not multiple)
        self.merge_button.setVisible(multiple)
        self.merge_button.setEnabled(multiple and self._merge_task is None and not self._opening)

    def _workspace_document_changed(self, index: int) -> None:
        path = self.document_picker.itemData(index)
        if (
            isinstance(path, str)
            and Path(path).is_file()
            and not self._opening
            and (self.document_info is None or path != self.document_info.path)
        ):
            self.open_path(path)

    def show_workspace_dashboard(self) -> None:
        if not self.workspace_paths or self._workspace_task is not None:
            return
        self.dashboard_button.setEnabled(False)
        self.dashboard_button.setText("Loading…")
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(True)
        task = BackgroundTask(
            analyze_workspace,
            tuple(self.workspace_paths),
            dict(self.reading_statuses),
            self.evidence_store.storage_dir,
            self.project_name,
        )
        self._workspace_task = task
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task: self._workspace_analysis_finished(task, result)
        )
        task.signals.failed.connect(
            lambda error, task=task: self._workspace_analysis_failed(task, error)
        )
        self.pool.start(task)

    def _workspace_analysis_finished(self, task: BackgroundTask, result: object) -> None:
        self._tasks.discard(task)
        if task is self._workspace_task:
            self._workspace_task = None
        self.dashboard_button.setText("Dashboard")
        self.dashboard_button.setEnabled(bool(self.workspace_paths))
        if not isinstance(result, WorkspaceSummary):
            return
        self._workspace_summary = result
        if self._workspace_dashboard is None:
            dialog = WorkspaceDashboardDialog(result, self)
            dialog.open_document.connect(self._open_dashboard_document)
            dialog.status_changed.connect(self._dashboard_status_changed)
            dialog.refresh_requested.connect(self.show_workspace_dashboard)
            dialog.analyze_requested.connect(self.analyze_workspace_selection)
            dialog.export_requested.connect(self.export_workspace_overview)
            dialog.excel_export_requested.connect(self.export_workspace_excel_report)
            self._workspace_dashboard = dialog
        else:
            self._workspace_dashboard.set_summary(result)
        self._workspace_dashboard.set_busy(False)
        self._workspace_dashboard.show()
        self._workspace_dashboard.raise_()
        self._workspace_dashboard.activateWindow()
        self.status_label.setText(
            f"Workspace analyzed: {len(result.documents)} documents, "
            f"{result.total_pages} pages"
        )

    def _workspace_analysis_failed(self, task: BackgroundTask, error: object) -> None:
        self._tasks.discard(task)
        if task is self._workspace_task:
            self._workspace_task = None
        self.dashboard_button.setText("Dashboard")
        self.dashboard_button.setEnabled(bool(self.workspace_paths))
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(False)
        QMessageBox.warning(self, "Dashboard failed", str(error))

    def _open_dashboard_document(self, path: str) -> None:
        if not Path(path).is_file():
            QMessageBox.warning(
                self,
                "Document unavailable",
                "The selected PDF is missing or cannot be accessed.",
            )
            return
        if not self._opening:
            self.open_path(path)

    def _dashboard_status_changed(self, path: str, status: str) -> None:
        if status not in READING_STATUSES:
            return
        self.reading_statuses[normalize_path(path)] = status
        if self._workspace_summary is not None:
            self._workspace_summary = update_workspace_status(
                self._workspace_summary,
                path,
                status,
            )
        if (
            self.document_info is not None
            and normalize_path(self.document_info.path) == normalize_path(path)
        ):
            self._sync_reading_status(path)
        self.status_label.setText(f"Reading status updated: {Path(path).name} · {status}")

    def analyze_workspace_selection(self) -> None:
        if (
            self._workspace_dashboard is None
            or self._workspace_batch_task is not None
            or self._workspace_task is not None
        ):
            return
        selected_paths = self._workspace_dashboard.selected_paths()
        if not selected_paths:
            QMessageBox.information(
                self,
                "No documents selected",
                "Check at least one available document in the dashboard.",
            )
            return
        self._workspace_dashboard.set_busy(True)
        self._workspace_dashboard.analysis_result.setText(
            f"Analyzing {len(selected_paths)} selected PDFs locally..."
        )
        task = BackgroundTask(
            analyze_workspace_documents,
            selected_paths,
            self.category_profile,
            self._noise_options(),
            self.text_engine.cache_dir,
            self.evidence_store.storage_dir,
            self.area_mask_store.storage_dir,
        )
        self._workspace_batch_task = task
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task: self._workspace_batch_finished(task, result)
        )
        task.signals.failed.connect(
            lambda error, task=task: self._workspace_batch_failed(task, error)
        )
        self.pool.start(task)

    def _workspace_batch_finished(self, task: BackgroundTask, result: object) -> None:
        self._tasks.discard(task)
        if task is self._workspace_batch_task:
            self._workspace_batch_task = None
        if not isinstance(result, WorkspaceBatchAnalysisResult):
            return
        if self.document_info is not None:
            self.evidence = self.evidence_store.load(self.document_info.document_id)
            self._refresh_evidence_list()
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(False)
            self._workspace_dashboard.set_analysis_result(
                result.analyzed_count,
                result.category_count,
                result.standard_count,
                result.added_note_count,
                result.empty_page_count,
                result.failed_count,
            )
        self.status_label.setText(
            f"Batch analysis complete: {result.analyzed_count} documents, "
            f"{result.added_note_count} new notes"
        )
        self.show_workspace_dashboard()

    def _workspace_batch_failed(self, task: BackgroundTask, error: object) -> None:
        self._tasks.discard(task)
        if task is self._workspace_batch_task:
            self._workspace_batch_task = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(False)
            self._workspace_dashboard.analysis_result.setText(
                f"Batch analysis failed: {error}"
            )
        QMessageBox.warning(self, "Batch analysis failed", str(error))

    def export_workspace_excel_report(self) -> None:
        if (
            self._workspace_summary is None
            or self._workspace_export_task is not None
            or self._workspace_dashboard is None
        ):
            return
        selected_paths = self._workspace_dashboard.selected_paths()
        if not selected_paths:
            QMessageBox.information(
                self,
                "No documents selected",
                "Check at least one available document in the dashboard.",
            )
            return
        try:
            selected_summary = select_workspace_documents(
                self._workspace_summary,
                selected_paths,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid selection", str(error))
            return
        base = Path(self.workspace_paths[0])
        safe_project_name = "".join(
            "_" if character in '<>:"/\\|?*' else character
            for character in self.project_name
        ).strip() or "PDF Analyzer Project"
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export editable Excel report",
            str(base.with_name(f"{safe_project_name} - reading report.xlsx")),
            "Excel workbooks (*.xlsx)",
        )
        if not destination:
            return
        if not destination.casefold().endswith(".xlsx"):
            destination += ".xlsx"
        self._workspace_dashboard.set_busy(True)
        task = BackgroundTask(
            export_workspace_excel,
            selected_summary,
            destination,
            self.evidence_store.storage_dir,
            self._workspace_dashboard.selected_tags(),
        )
        self._workspace_export_task = task
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task: self._workspace_export_finished(task, result)
        )
        task.signals.failed.connect(
            lambda error, task=task: self._workspace_export_failed(task, error)
        )
        self.pool.start(task)

    def export_workspace_overview(self) -> None:
        if (
            self._workspace_summary is None
            or self._workspace_export_task is not None
            or self._workspace_dashboard is None
        ):
            return
        selected_paths = self._workspace_dashboard.selected_paths()
        if not selected_paths:
            QMessageBox.information(
                self,
                "No documents selected",
                "Check at least one available document in the dashboard.",
            )
            return
        try:
            selected_summary = select_workspace_documents(
                self._workspace_summary,
                selected_paths,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid selection", str(error))
            return
        mode = self._workspace_dashboard.export_mode_value()
        selected_tags = (
            None
            if mode == "management"
            else self._workspace_dashboard.selected_tags()
        )
        base = Path(self.workspace_paths[0])
        safe_project_name = "".join(
            "_" if character in '<>:"/\\|?*' else character
            for character in self.project_name
        ).strip() or "PDF Analyzer Project"
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export consolidated PDF",
            str(
                base.with_name(
                    f"{safe_project_name} - "
                    f"{'annotated package' if mode == 'full' else 'management analysis report' if mode == 'management' else 'overview'}.pdf"
                )
            ),
            "PDF documents (*.pdf)",
        )
        if not destination:
            return
        if not destination.casefold().endswith(".pdf"):
            destination += ".pdf"
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(True)
        if mode == "full":
            task = BackgroundTask(
                export_consolidated_package,
                selected_summary,
                destination,
                self.evidence_store.storage_dir,
                self.highlight_store.storage_dir,
                self.bookmark_store.storage_dir,
                selected_tags,
            )
        elif mode == "management":
            task = BackgroundTask(
                export_management_analysis_report,
                selected_summary,
                destination,
                self.evidence_store.storage_dir,
                selected_tags,
            )
        else:
            task = BackgroundTask(
                export_workspace_report,
                selected_summary,
                destination,
            )
        self._workspace_export_task = task
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task: self._workspace_export_finished(task, result)
        )
        task.signals.failed.connect(
            lambda error, task=task: self._workspace_export_failed(task, error)
        )
        self.pool.start(task)

    def _workspace_export_finished(self, task: BackgroundTask, result: object) -> None:
        self._tasks.discard(task)
        if task is self._workspace_export_task:
            self._workspace_export_task = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(False)
        if isinstance(result, WorkspaceExcelResult):
            self.status_label.setText(
                f"Excel report exported: {Path(result.path).name}"
            )
            QMessageBox.information(
                self,
                "Excel export complete",
                f"The editable workbook was saved:\n{result.path}\n\n"
                f"Documents: {result.document_count}\n"
                f"Pages analyzed: {result.page_count}\n"
                f"Notes: {result.note_count}\n"
                f"Tags: {result.tag_count}",
            )
            return
        if isinstance(result, ManagementAnalysisReportResult):
            self.status_label.setText(
                f"Management report exported: {Path(result.path).name}"
            )
            QMessageBox.information(
                self,
                "Management report complete",
                f"The review-ready report was saved:\n{result.path}\n\n"
                f"Documents: {result.document_count}\n"
                f"Source pages analyzed: {result.source_page_count}\n"
                f"Findings: {result.note_count}\n"
                f"Report pages: {result.report_page_count}",
            )
            return
        if not isinstance(result, WorkspaceReportResult):
            if not isinstance(result, ConsolidatedExportResult):
                return
            self.status_label.setText(
                f"Annotated package exported: {Path(result.path).name}"
            )
            QMessageBox.information(
                self,
                "Annotated package complete",
                f"The consolidated package was saved:\n{result.path}\n\n"
                f"Documents: {result.document_count}\n"
                f"Source pages: {result.source_page_count}\n"
                f"Report pages: {result.report_page_count}\n"
                f"Highlights: {result.highlight_count}\n"
                f"Notes: {result.note_count}",
            )
            return
        self.status_label.setText(
            f"Workspace overview exported: {Path(result.path).name}"
        )
        QMessageBox.information(
            self,
            "Overview export complete",
            f"The consolidated report was saved:\n{result.path}\n\n"
            f"Documents: {result.document_count}\n"
            f"Pages analyzed: {result.page_count}\n"
            f"Notes: {result.note_count}\n"
            f"Report pages: {result.report_page_count}",
        )

    def _workspace_export_failed(self, task: BackgroundTask, error: object) -> None:
        self._tasks.discard(task)
        if task is self._workspace_export_task:
            self._workspace_export_task = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.set_busy(False)
        QMessageBox.warning(self, "Workspace export failed", str(error))

    def merge_workspace_documents(self) -> None:
        if len(self.workspace_paths) < 2 or self._merge_task is not None:
            return
        base = Path(self.workspace_paths[0])
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Save combined PDF",
            str(base.with_name(f"{base.stem} - combinat.pdf")),
            "PDF documents (*.pdf)",
        )
        if not destination:
            return
        if not destination.casefold().endswith(".pdf"):
            destination += ".pdf"
        self.merge_button.setEnabled(False)
        self.merge_button.setText("Combining…")
        self.status_label.setText("Combining documents locally…")
        task = BackgroundTask(
            PdfSession.merge_documents, tuple(self.workspace_paths), destination
        )
        self._merge_task = task
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task: self._merge_finished(task, result)
        )
        task.signals.failed.connect(
            lambda error, task=task: self._merge_failed(task, error)
        )
        self.pool.start(task)

    def _merge_finished(self, task: BackgroundTask, result: object) -> None:
        self._tasks.discard(task)
        if task is self._merge_task:
            self._merge_task = None
        self.merge_button.setText("Combine")
        if not isinstance(result, str):
            return
        self.status_label.setText("Combined PDF added to the workspace")
        self.add_workspace_documents((result,), open_first=True)

    def _merge_failed(self, task: BackgroundTask, error: object) -> None:
        self._tasks.discard(task)
        if task is self._merge_task:
            self._merge_task = None
        self.merge_button.setText("Combine")
        self._refresh_document_picker()
        QMessageBox.warning(self, "Combine failed", str(error))

    def export_annotated_document(self) -> None:
        if self.document_info is None or self._export_task is not None:
            return
        if not self.highlights and not self.evidence:
            QMessageBox.information(
                self,
                "No annotations",
                "Add at least one highlight or note before exporting.",
            )
            return
        selected_tags = self._selected_export_tags()
        if self.evidence and not selected_tags:
            QMessageBox.information(
                self,
                "No tags selected",
                "Select at least one tag in the Tags tab for the report.",
            )
            return
        source = Path(self.document_info.path)
        destination, _ = QFileDialog.getSaveFileName(
            self,
            "Export annotated PDF",
            str(source.with_name(f"{source.stem} - annotated.pdf")),
            "PDF documents (*.pdf)",
        )
        if not destination:
            return
        if not destination.casefold().endswith(".pdf"):
            destination += ".pdf"
        if Path(destination).resolve() == source.resolve():
            QMessageBox.warning(
                self,
                "Invalid destination",
                "Choose a different name. The original document cannot be overwritten.",
            )
            return
        self.export_button.setEnabled(False)
        self.export_button.setText("Exporting…")
        self.status_label.setText("Creating the annotated PDF copy…")
        task = BackgroundTask(
            export_annotated_pdf,
            self.document_info.path,
            destination,
            self.highlights,
            self.evidence,
            selected_tags,
            self.personal_bookmarks,
        )
        self._export_task = task
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task: self._export_finished(task, result)
        )
        task.signals.failed.connect(
            lambda error, task=task: self._export_failed(task, error)
        )
        self.pool.start(task)

    def _export_finished(self, task: BackgroundTask, result: object) -> None:
        self._tasks.discard(task)
        if task is self._export_task:
            self._export_task = None
        self.export_button.setText("Export")
        self.export_button.setEnabled(self.document_info is not None)
        if not isinstance(result, PdfExportResult):
            return
        self.status_label.setText(
            f"PDF exported: {result.highlight_count} highlights and "
            f"{result.evidence_count} notes"
        )
        QMessageBox.information(
            self,
            "Export complete",
            f"The annotated PDF was saved:\n{result.path}\n\n"
            f"Highlights: {result.highlight_count}\n"
            f"Notes: {result.evidence_count}\n"
            f"Report pages: {result.index_page_count}",
        )

    def _export_failed(self, task: BackgroundTask, error: object) -> None:
        self._tasks.discard(task)
        if task is self._export_task:
            self._export_task = None
        self.export_button.setText("Export")
        self.export_button.setEnabled(self.document_info is not None)
        QMessageBox.warning(self, "Export failed", str(error))

    def open_path(self, path: str) -> None:
        if self._opening:
            return
        self._opening = True
        self._generation += 1
        generation = self._generation
        self.pool.clear()
        self._render_pending.clear()
        self._thumbnail_pending.clear()
        self.thumbnail_pool.clear()
        self.open_button.setEnabled(False)
        self.merge_button.setEnabled(False)
        self.status_label.setText("Validating document…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        task = BackgroundTask(self.session.open, path)
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation: self._document_opened(task, generation, result)
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation: self._document_failed(task, generation, error)
        )
        self.pool.start(task)

    def _finish_open(self, task: BackgroundTask) -> None:
        self._tasks.discard(task)
        self._opening = False
        self.open_button.setEnabled(True)
        self._refresh_document_picker()
        if QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def _document_opened(self, task: BackgroundTask, generation: int, result: object) -> None:
        self._finish_open(task)
        if generation != self._generation:
            return
        info, layouts = result
        if info.path not in self.workspace_paths:
            self.workspace_paths.append(info.path)
        self._refresh_document_picker(info.path)
        self._sync_reading_status(info.path)
        self._text_cancel.set()
        self._text_cancel = Event()
        self.text_pool.clear()
        self.document_text = None
        self.search_hits = ()
        self._search_keywords = ()
        self._search_expanded = False
        self._search_bilingual = False
        self._search_task = None
        self.category_matches = ()
        self._category_task = None
        self.standard_matches = ()
        self._standards_task = None
        self.search_tree.clear()
        self.category_tree.clear()
        self.standards_tree.clear()
        self.search_summary.setText("No search has been run")
        self.category_summary.setText(
            "Analyze automatically saves every result as a tagged note."
        )
        self.standards_summary.setText(
            "Analyze Standards automatically saves every result as a tagged note."
        )
        self.search_button.setEnabled(False)
        self.category_button.setEnabled(False)
        self.standards_button.setEnabled(False)
        self.standards_button.setEnabled(False)
        self.add_search_evidence_button.setEnabled(False)
        self.add_category_evidence_button.setEnabled(False)
        self.add_standard_note_button.setEnabled(False)
        self.text_info.setText("Checking the text layer…")
        self.ocr_button.setEnabled(False)
        self.document_info = info
        self.rotation = 0
        self.highlights = self.highlight_store.load(info.document_id)
        self.evidence = self.evidence_store.load(info.document_id)
        self.personal_bookmarks = self.bookmark_store.load(
            info.document_id,
            info.page_count,
        )
        self.area_masks = self.area_mask_store.load(
            info.document_id,
            info.page_count,
        )
        self._mask_undo_stack = []
        self._mask_redo_stack = []
        self._mask_replacing_id = None
        self.draw_mask_button.setChecked(False)
        self._refresh_mask_list()
        self._refresh_evidence_list()
        self.evidence_button.setChecked(bool(self.evidence))
        self.layouts = layouts
        self.current_page = 0
        self._populate_document(info)
        self._rebuild_pages()
        self._populate_navigation(info.page_count)
        self._set_document_controls(True)
        self.page_spin.setRange(1, info.page_count)
        self.page_spin.setValue(1)
        self.page_total.setText(f"of {info.page_count}")
        self.status_label.setText("Document loaded")
        QTimer.singleShot(0, self.fit_current_page)
        self._start_text_audit(info, generation)

    def _document_failed(self, task: BackgroundTask, generation: int, error: object) -> None:
        self._finish_open(task)
        if generation != self._generation:
            return
        self.status_label.setText("The document could not be opened")
        QMessageBox.warning(self, "Invalid PDF", str(error))

    def _populate_document(self, info: DocumentInfo) -> None:
        self.header_file.setText(info.name)
        self.document_name.setText(info.title or info.name)
        path = Path(info.path)
        self.document_path.setText(str(path.parent))
        self.document_path.setToolTip(info.path)
        self.page_info.setText(f"Pages\n{info.page_count}")
        self.size_info.setText(f"Size\n{self._format_size(info.size_bytes)}")

    def _start_text_audit(self, info: DocumentInfo, generation: int) -> None:
        self.text_info.setText("Checking the text layer…")
        task = BackgroundTask(
            self.text_engine.audit_document,
            info.path,
            info.document_id,
            self._text_cancel,
        )
        self._text_tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation: self._text_audit_finished(
                task, generation, result
            )
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation: self._text_task_failed(
                task, generation, error
            )
        )
        self.text_pool.start(task)

    def _text_audit_finished(self, task: BackgroundTask, generation: int, result: object) -> None:
        self._text_tasks.discard(task)
        if generation != self._generation or not isinstance(result, DocumentText):
            return
        self.document_text = result
        self._apply_text_layers()
        self._show_text_summary(result)

    def _show_text_summary(self, result: DocumentText) -> None:
        audit = result.audit
        lines = [
            f"Native text: {audit.native_pages} pages",
            f"OCR: {audit.ocr_pages} pages",
            f"Words: {audit.word_count}",
        ]
        if audit.empty_pages:
            lines.append(f"Needs OCR: {len(audit.empty_pages)} pages")
        elif not audit.unreadable_pages:
            lines.append("All pages contain text")
        if audit.unreadable_pages:
            lines.append(f"No text after OCR: {len(audit.unreadable_pages)} pages")
        if self.text_engine.ocr.available:
            lines.append(f"OCR languages: {self.text_engine.ocr.language_label}")
        else:
            lines.append("OCR engine unavailable")
        self.text_info.setText("\n".join(lines))
        self.ocr_button.setEnabled(bool(audit.empty_pages) and self.text_engine.ocr.available)
        self.search_button.setEnabled(audit.word_count > 0 and self._search_task is None)
        self.category_button.setEnabled(audit.word_count > 0 and self._category_task is None)
        self.standards_button.setEnabled(audit.word_count > 0 and self._standards_task is None)

    def run_ocr(self) -> None:
        if not self.document_info or not self.document_text or not self.document_text.audit.empty_pages:
            return
        info = self.document_info
        generation = self._generation
        self.ocr_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.category_button.setEnabled(False)
        self.ocr_button.setText("Running OCR…")
        self.text_info.setText(
            f"Running local OCR on {len(self.document_text.audit.empty_pages)} pages…\nThe reader remains available."
        )
        task = BackgroundTask(
            self.text_engine.ocr_pages,
            info.path,
            info.document_id,
            self.document_text.audit.empty_pages,
            self._text_cancel,
        )
        self._text_tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation: self._ocr_finished(task, generation, result)
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation: self._text_task_failed(
                task, generation, error
            )
        )
        self.text_pool.start(task)

    def _ocr_finished(self, task: BackgroundTask, generation: int, result: object) -> None:
        self._text_tasks.discard(task)
        self.ocr_button.setText("Run OCR")
        if generation != self._generation or not isinstance(result, DocumentText):
            return
        self.document_text = result
        self._apply_text_layers()
        self.search_hits = ()
        self._search_keywords = ()
        self.search_tree.clear()
        self.add_search_evidence_button.setEnabled(False)
        self.search_summary.setText("The text changed after OCR. Run the search again.")
        self.category_matches = ()
        self.category_tree.clear()
        self.add_category_evidence_button.setEnabled(False)
        self.category_summary.setText("The text changed after OCR. Run the analysis again.")
        self.standard_matches = ()
        self.standards_tree.clear()
        self.add_standard_note_button.setEnabled(False)
        self.standards_summary.setText("The text changed after OCR. Run the standards analysis again.")
        self._show_text_summary(result)

    def _text_task_failed(self, task: BackgroundTask, generation: int, error: object) -> None:
        self._text_tasks.discard(task)
        if generation != self._generation:
            return
        self.ocr_button.setText("Run OCR")
        self.ocr_button.setEnabled(
            bool(self.document_text and self.document_text.audit.empty_pages)
            and self.text_engine.ocr.available
        )
        self.text_info.setText(f"Text analysis failed:\n{error}")
        self.search_button.setEnabled(bool(self.document_text and self.document_text.audit.word_count))
        self.category_button.setEnabled(bool(self.document_text and self.document_text.audit.word_count))
        self.standards_button.setEnabled(bool(self.document_text and self.document_text.audit.word_count))

    def _refresh_search_expansion_preview(self, *args) -> None:
        keywords = parse_keywords(self.keyword_input.toPlainText())
        bilingual = self.search_mode.currentIndex() == 2
        expanded = self.search_mode.currentIndex() != 0
        mode_name = "Bilingual" if bilingual else "Expanded" if expanded else "Exact"
        forms = expand_keywords(
            keywords,
            expanded=expanded,
            bilingual=bilingual,
            dictionary=self.bilingual_dictionary,
        )
        if not keywords:
            self.search_expansion_preview.setText(
                f"{mode_name} Search · no terms"
            )
            self.search_expansion_preview.setToolTip("")
            return
        extra = max(0, len(forms) - len(keywords))
        self.search_expansion_preview.setText(
            f"{mode_name} Search · "
            f"{len(keywords)} requested · {len(forms)} search forms"
            + (f" · {extra} generated" if extra else "")
        )
        grouped = []
        for keyword in keywords:
            values = [item.term for item in forms if item.original == keyword]
            grouped.append(f"{keyword}: {', '.join(values)}")
        self.search_expansion_preview.setToolTip("\n".join(grouped[:30]))

    def _noise_options(self) -> SearchNoiseOptions:
        return SearchNoiseOptions(
            ignore_headers=self.ignore_headers_check.isChecked(),
            ignore_footers=self.ignore_footers_check.isChecked(),
            ignore_page_numbers=self.ignore_page_numbers_check.isChecked(),
            hide_repeated_text=self.hide_repeated_text_check.isChecked(),
        )

    def _set_noise_options(self, options: SearchNoiseOptions) -> None:
        controls = (
            (self.ignore_headers_check, options.ignore_headers),
            (self.ignore_footers_check, options.ignore_footers),
            (self.ignore_page_numbers_check, options.ignore_page_numbers),
            (self.hide_repeated_text_check, options.hide_repeated_text),
        )
        for checkbox, checked in controls:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

    def _noise_options_changed(self) -> None:
        self._last_noise_report = None
        if self.search_hits:
            self.search_summary.setText("Noise filters changed. Run the search again.")
        if self.category_matches:
            self.category_summary.setText("Noise filters changed. Run the analysis again.")
        if self.standard_matches:
            self.standards_summary.setText("Noise filters changed. Run the analysis again.")

    def _filtered_analysis_document(
        self,
    ) -> tuple[DocumentText, SearchNoiseReport]:
        if self.document_text is None:
            raise ValueError("Document text is not available.")
        heights = tuple(layout.height_points for layout in self.layouts)
        filtered, report = filter_document_for_analysis(
            self.document_text,
            heights,
            self._noise_options(),
        )
        page_sizes = tuple(
            (layout.width_points, layout.height_points) for layout in self.layouts
        )
        masked, mask_words = apply_masks_to_document(
            filtered,
            page_sizes,
            self.area_masks,
        )
        return (
            masked,
            replace(
                report,
                retained_word_count=masked.audit.word_count,
                mask_words=mask_words,
            ),
        )

    @staticmethod
    def _noise_summary(report: SearchNoiseReport) -> str:
        if not report.excluded_word_count:
            return "0 words filtered"
        details = []
        if report.header_words:
            details.append(f"{report.header_words} header")
        if report.footer_words:
            details.append(f"{report.footer_words} footer")
        if report.page_number_words:
            details.append(f"{report.page_number_words} page number")
        if report.repeated_words:
            details.append(f"{report.repeated_words} repeated")
        if report.mask_words:
            details.append(f"{report.mask_words} masked")
        return f"{report.excluded_word_count} words filtered ({', '.join(details)})"

    def _show_masks_tab(self) -> None:
        self.evidence_button.setChecked(True)
        for index in range(self.analysis_tabs.count()):
            if self.analysis_tabs.tabText(index) == "Masks":
                self.analysis_tabs.setCurrentIndex(index)
                break

    def _mask_drawing_toggled(self, checked: bool) -> None:
        shape = str(self.mask_shape_combo.currentData())
        if checked:
            instruction = (
                "Click vertices - double-click to finish"
                if shape == "polygon"
                else "Drawing - drag on a page"
            )
            self.draw_mask_button.setText(instruction)
        else:
            self.draw_mask_button.setText(
                {
                    "rectangle": "Draw Rectangle",
                    "freehand": "Draw Freehand",
                    "polygon": "Draw Polygon",
                }[shape]
            )
            if self._mask_replacing_id is not None:
                self._mask_replacing_id = None
                self.status_label.setText("Mask redraw cancelled")
        self._refresh_mask_drawing_mode()

    def _mask_shape_changed(self, *args) -> None:
        if self.draw_mask_button.isChecked():
            self.draw_mask_button.setChecked(False)
        else:
            self._mask_drawing_toggled(False)

    def _refresh_mask_drawing_mode(self, *args) -> None:
        mode = (
            str(self.mask_kind_combo.currentData())
            if self.draw_mask_button.isChecked()
            else None
        )
        shape = str(self.mask_shape_combo.currentData())
        for page in self.pages:
            page.set_mask_mode(mode, shape)

    def _mask_drawn(self, page_index: int, coordinates: object) -> None:
        if (
            self.document_info is None
            or not 0 <= page_index < len(self.layouts)
        ):
            return
        layout = self.layouts[page_index]
        scope_page = (
            None if self.mask_scope_combo.currentData() == "all" else page_index
        )
        try:
            if isinstance(coordinates, tuple) and len(coordinates) == 4:
                x0, y0, x1, y1 = (float(value) for value in coordinates)
                mask = create_area_mask(
                    self.document_info.document_id,
                    str(self.mask_kind_combo.currentData()),
                    scope_page,
                    x0 / layout.width_points,
                    y0 / layout.height_points,
                    x1 / layout.width_points,
                    y1 / layout.height_points,
                )
            elif isinstance(coordinates, dict):
                points = tuple(
                    (
                        float(point[0]) / layout.width_points,
                        float(point[1]) / layout.height_points,
                    )
                    for point in coordinates.get("points", ())
                )
                mask = create_path_mask(
                    self.document_info.document_id,
                    str(self.mask_kind_combo.currentData()),
                    scope_page,
                    str(coordinates.get("shape", "")),
                    points,
                )
            else:
                return
        except (OSError, ValueError, AreaMaskError) as error:
            QMessageBox.warning(self, "Mask not saved", str(error))
            return
        if self._mask_replacing_id is None:
            updated = self.area_masks + (mask,)
            status = "Mask saved"
        else:
            updated = tuple(
                mask if item.mask_id == self._mask_replacing_id else item
                for item in self.area_masks
            )
            self._mask_replacing_id = None
            status = "Mask redrawn"
            self.draw_mask_button.setChecked(False)
        self._commit_masks(updated, status)

    def _commit_masks(
        self,
        updated: tuple[AreaMask, ...],
        status: str,
        record_history: bool = True,
    ) -> bool:
        if self.document_info is None or updated == self.area_masks:
            return False
        try:
            self.area_mask_store.save(
                self.document_info.document_id,
                updated,
                self.document_info.page_count,
            )
        except (OSError, ValueError, AreaMaskError) as error:
            QMessageBox.warning(self, "Masks not saved", str(error))
            return False
        previous = self.area_masks
        if record_history:
            self._mask_undo_stack.append(previous)
            self._mask_undo_stack = self._mask_undo_stack[-50:]
            self._mask_redo_stack = []
        self.area_masks = updated
        self._masks_changed(status)
        return True

    def _masks_changed(self, status: str) -> None:
        self._last_noise_report = None
        if self.search_hits:
            self.search_summary.setText("Visual masks changed. Run the search again.")
        if self.category_matches:
            self.category_summary.setText("Visual masks changed. Run the analysis again.")
        if self.standard_matches:
            self.standards_summary.setText("Visual masks changed. Run the analysis again.")
        self._refresh_mask_list()
        self.status_label.setText(status)

    def _refresh_mask_list(self) -> None:
        if not hasattr(self, "mask_list"):
            return
        selected_id = (
            self.mask_list.currentItem().data(Qt.ItemDataRole.UserRole)
            if self.mask_list.currentItem()
            else None
        )
        self.mask_list.clear()
        selected_item = None
        for mask in self.area_masks:
            scope = "ALL PAGES" if mask.page_index is None else f"PAGE {mask.page_index + 1}"
            width = round((mask.x1_ratio - mask.x0_ratio) * 100)
            height = round((mask.y1_ratio - mask.y0_ratio) * 100)
            item = QListWidgetItem(
                f"{mask.kind.upper()} · {mask.shape.upper()} · {scope} · "
                f"{round(mask.x0_ratio * 100)}%, {round(mask.y0_ratio * 100)}% · "
                f"{width}% × {height}%"
            )
            item.setData(Qt.ItemDataRole.UserRole, mask.mask_id)
            item.setForeground(QColor("#218739" if mask.kind == "keep" else "#a82f2a"))
            self.mask_list.addItem(item)
            if mask.mask_id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.mask_list.setCurrentItem(selected_item)
        for page in self.pages:
            page.set_area_masks(self.area_masks)
        keep_count = sum(mask.kind == "keep" for mask in self.area_masks)
        ignore_count = len(self.area_masks) - keep_count
        self.mask_summary.setText(
            f"{len(self.area_masks)} masks · {ignore_count} ignore · {keep_count} keep"
            if self.area_masks
            else "No visual masks"
        )
        has_masks = bool(self.area_masks)
        selected = self.mask_list.currentItem() is not None
        self.remove_mask_button.setEnabled(selected)
        self.redraw_mask_button.setEnabled(selected)
        self.copy_mask_pages_button.setEnabled(selected)
        self.similar_pages_button.setEnabled(selected)
        self.clear_masks_button.setEnabled(has_masks)
        self.save_masks_button.setEnabled(
            has_masks and self.document_info is not None
        )
        self.undo_mask_button.setEnabled(bool(self._mask_undo_stack))
        self.redo_mask_button.setEnabled(bool(self._mask_redo_stack))

    def _selected_mask(self) -> AreaMask | None:
        item = self.mask_list.currentItem()
        if item is None:
            return None
        mask_id = item.data(Qt.ItemDataRole.UserRole)
        return next(
            (mask for mask in self.area_masks if mask.mask_id == mask_id),
            None,
        )

    def _mask_selection_changed(self, current, previous) -> None:
        selected = self._selected_mask() is not None
        self.remove_mask_button.setEnabled(selected)
        self.redraw_mask_button.setEnabled(selected)
        self.copy_mask_pages_button.setEnabled(selected)
        self.similar_pages_button.setEnabled(selected)

    def _mask_item_clicked(self, item: QListWidgetItem) -> None:
        mask_id = item.data(Qt.ItemDataRole.UserRole)
        mask = next(
            (candidate for candidate in self.area_masks if candidate.mask_id == mask_id),
            None,
        )
        if mask is None:
            return
        page_index = self.current_page if mask.page_index is None else mask.page_index
        layout = self.layouts[page_index]
        self._navigate_to_location(
            page_index,
            (
                TextRect(
                    mask.x0_ratio * layout.width_points,
                    mask.y0_ratio * layout.height_points,
                    mask.x1_ratio * layout.width_points,
                    mask.y1_ratio * layout.height_points,
                ),
            ),
            f"{mask.kind.title()} mask · page {page_index + 1}",
        )

    def remove_selected_mask(self) -> None:
        mask = self._selected_mask()
        if mask is None:
            return
        updated = tuple(
            candidate
            for candidate in self.area_masks
            if candidate.mask_id != mask.mask_id
        )
        self._commit_masks(updated, "Mask removed")

    def clear_all_masks(self) -> None:
        if self.document_info is None or not self.area_masks:
            return
        answer = QMessageBox.question(
            self,
            "Clear visual masks",
            f"Remove all {len(self.area_masks)} masks from this document?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._commit_masks((), "All masks removed")

    def redraw_selected_mask(self) -> None:
        mask = self._selected_mask()
        if mask is None:
            return
        self.mask_kind_combo.setCurrentIndex(0 if mask.kind == "ignore" else 1)
        shape_index = self.mask_shape_combo.findData(mask.shape)
        self.mask_shape_combo.setCurrentIndex(max(shape_index, 0))
        self.mask_scope_combo.setCurrentIndex(1 if mask.page_index is None else 0)
        if mask.page_index is not None:
            self.go_to_page(mask.page_index)
        self._mask_replacing_id = mask.mask_id
        self.draw_mask_button.setChecked(True)
        self.status_label.setText(
            "Redraw active - the old mask remains until a valid replacement is completed"
        )

    def copy_mask_to_pages(self) -> None:
        mask = self._selected_mask()
        if mask is None or self.document_info is None:
            return
        value, accepted = QInputDialog.getText(
            self,
            "Copy mask to pages",
            f"Pages (1-{self.document_info.page_count}), e.g. 2, 4-7:",
        )
        if not accepted:
            return
        try:
            pages = parse_page_selection(value, self.document_info.page_count)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid pages", str(error))
            return
        self._copy_mask_to_page_indexes(mask, pages, "Mask copied to selected pages")

    def _copy_mask_to_page_indexes(
        self,
        mask: AreaMask,
        pages: tuple[int, ...],
        status: str,
    ) -> int:
        existing = {mask_geometry_identity(item) for item in self.area_masks}
        additions = []
        for page_index in pages:
            candidate = copy_mask_to_page(mask, page_index)
            identity = mask_geometry_identity(candidate)
            if identity not in existing:
                existing.add(identity)
                additions.append(candidate)
        if additions:
            self._commit_masks(self.area_masks + tuple(additions), status)
        else:
            self.status_label.setText("No new masks were required")
        return len(additions)

    def apply_mask_to_similar_pages(self) -> None:
        mask = self._selected_mask()
        if mask is None or self.document_info is None or self.document_text is None:
            return
        if mask.page_index is None:
            QMessageBox.information(
                self,
                "All pages mask",
                "This mask already applies to all pages.",
            )
            return
        page_sizes = tuple(
            (layout.width_points, layout.height_points) for layout in self.layouts
        )
        try:
            similar = find_similar_pages(
                self.document_text,
                page_sizes,
                mask.page_index,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Similarity failed", str(error))
            return
        if not similar:
            QMessageBox.information(
                self,
                "No similar pages",
                "No pages passed the controlled layout-similarity threshold.",
            )
            return
        preview = "\n".join(
            f"Page {item.page_index + 1}: {round(item.score * 100)}%"
            for item in similar[:30]
        )
        answer = QMessageBox.question(
            self,
            "Apply mask to similar pages",
            f"Source page: {mask.page_index + 1}\n\n"
            f"Detected pages:\n{preview}\n\n"
            "Create one copy of this mask on every listed page?",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._copy_mask_to_page_indexes(
            mask,
            tuple(item.page_index for item in similar),
            "Mask applied to similar pages",
        )

    def undo_mask_change(self) -> None:
        if not self._mask_undo_stack:
            return
        previous = self._mask_undo_stack.pop()
        current = self.area_masks
        if self._commit_masks(previous, "Mask change undone", record_history=False):
            self._mask_redo_stack.append(current)
            self._refresh_mask_list()

    def redo_mask_change(self) -> None:
        if not self._mask_redo_stack:
            return
        following = self._mask_redo_stack.pop()
        current = self.area_masks
        if self._commit_masks(following, "Mask change redone", record_history=False):
            self._mask_undo_stack.append(current)
            self._refresh_mask_list()

    def save_mask_profile_file(self) -> None:
        if not self.area_masks:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save mask profile",
            "PDF Analyzer Masks.pdfanalyzer-mask.json",
            "PDF Analyzer Mask Profile (*.pdfanalyzer-mask.json);;JSON files (*.json)",
        )
        if not path:
            return
        if not path.casefold().endswith(".json"):
            path += ".pdfanalyzer-mask.json"
        try:
            save_mask_profile(path, self.area_masks)
        except (OSError, ValueError, AreaMaskError) as error:
            QMessageBox.warning(self, "Mask profile not saved", str(error))
            return
        self.status_label.setText(f"Mask profile saved: {Path(path).name}")

    def load_mask_profile_file(self) -> None:
        if self.document_info is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load mask profile",
            "",
            "PDF Analyzer Mask Profile (*.pdfanalyzer-mask.json *.json)",
        )
        if not path:
            return
        try:
            masks = load_mask_profile(
                path,
                self.document_info.document_id,
                self.document_info.page_count,
            )
        except (OSError, ValueError, AreaMaskError) as error:
            QMessageBox.warning(self, "Invalid mask profile", str(error))
            return
        self._commit_masks(
            masks,
            f"Mask profile loaded: {Path(path).name}",
        )

    def run_keyword_search(self) -> None:
        if (
            self.document_text is None
            or self._search_task is not None
            or self._category_task is not None
            or self._standards_task is not None
        ):
            return
        keywords = parse_keywords(self.keyword_input.toPlainText())
        if not keywords:
            self.search_summary.setText("Enter at least one valid term.")
            return
        generation = self._generation
        bilingual = self.search_mode.currentIndex() == 2
        expanded = self.search_mode.currentIndex() != 0
        analysis_document, noise_report = self._filtered_analysis_document()
        self._last_noise_report = noise_report
        self.search_button.setEnabled(False)
        self.category_button.setEnabled(False)
        self.standards_button.setEnabled(False)
        self.ocr_button.setEnabled(False)
        self.search_button.setText("Searching…")
        self.search_summary.setText(f"Searching {len(keywords)} terms locally…")
        task = BackgroundTask(
            search_document,
            analysis_document,
            keywords,
            expanded,
            bilingual,
            self.bilingual_dictionary,
        )
        self._search_task = task
        self._text_tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation, keywords=keywords, expanded=expanded, bilingual=bilingual, noise_report=noise_report: self._search_finished(
                task, generation, keywords, expanded, bilingual, noise_report, result
            )
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation: self._search_failed(
                task, generation, error
            )
        )
        self.text_pool.start(task)

    def _search_finished(
        self,
        task: BackgroundTask,
        generation: int,
        keywords: tuple[str, ...],
        expanded: bool,
        bilingual: bool,
        noise_report: SearchNoiseReport,
        result: object,
    ) -> None:
        self._text_tasks.discard(task)
        if task is self._search_task:
            self._search_task = None
        self.search_button.setText("Search Document")
        if generation != self._generation or not isinstance(result, tuple):
            return
        self._search_keywords = keywords
        self._search_expanded = expanded
        self._search_bilingual = bilingual
        self.search_hits = tuple(hit for hit in result if isinstance(hit, SearchHit))
        self._refresh_search_tree()
        pages_without_text = (
            len(self.document_text.audit.empty_pages) + len(self.document_text.audit.unreadable_pages)
            if self.document_text
            else 0
        )
        warning = f" · {pages_without_text} pages without text" if pages_without_text else ""
        mode_name = "Bilingual" if bilingual else "Expanded" if expanded else "Exact"
        self.search_summary.setText(
            f"{mode_name} Search · "
            f"{len(keywords)} terms · {len(self.search_hits)} results · "
            f"{self._noise_summary(noise_report)}{warning}"
        )
        self.search_button.setEnabled(True)
        self.category_button.setEnabled(True)
        self.standards_button.setEnabled(True)
        self.ocr_button.setEnabled(
            bool(self.document_text and self.document_text.audit.empty_pages)
            and self.text_engine.ocr.available
        )

    def _search_failed(self, task: BackgroundTask, generation: int, error: object) -> None:
        self._text_tasks.discard(task)
        if task is self._search_task:
            self._search_task = None
        if generation != self._generation:
            return
        self.search_button.setText("Search Document")
        self.search_button.setEnabled(bool(self.document_text and self.document_text.audit.word_count))
        self.category_button.setEnabled(bool(self.document_text and self.document_text.audit.word_count))
        self.standards_button.setEnabled(bool(self.document_text and self.document_text.audit.word_count))
        self.ocr_button.setEnabled(
            bool(self.document_text and self.document_text.audit.empty_pages)
            and self.text_engine.ocr.available
        )
        self.search_summary.setText(f"Search failed: {error}")

    def _refresh_search_tree(self) -> None:
        self.search_tree.clear()
        selected_item = None
        for keyword in self._search_keywords:
            matching = [hit for hit in self.search_hits if hit.keyword == keyword]
            group = QTreeWidgetItem([f"{keyword} ({len(matching)})"])
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.search_tree.addTopLevelItem(group)
            for hit in matching:
                context = hit.context
                if len(context) > 190:
                    context = context[:187].rstrip() + "…"
                matched = hit.matched_term or hit.keyword
                variant = f" [{matched}]" if matched.casefold() != hit.keyword.casefold() else ""
                child = QTreeWidgetItem([f"p. {hit.page_index + 1}{variant} · {context}"])
                child.setData(0, Qt.ItemDataRole.UserRole, hit.hit_id)
                child.setToolTip(
                    0,
                    f"Requested term: {hit.keyword}\nMatched form: {matched}\n"
                    f"Reason: {hit.match_reason}\n\n{hit.context}",
                )
                group.addChild(child)
                if selected_item is None:
                    selected_item = child
            group.setExpanded(True)
        if selected_item is not None:
            self.search_tree.setCurrentItem(selected_item)
        self.add_search_evidence_button.setEnabled(selected_item is not None)

    def _find_search_hit(self, hit_id: str | None) -> SearchHit | None:
        return next((hit for hit in self.search_hits if hit.hit_id == hit_id), None)

    def _selected_search_hit(self) -> SearchHit | None:
        item = self.search_tree.currentItem()
        if item is None:
            return None
        return self._find_search_hit(item.data(0, Qt.ItemDataRole.UserRole))

    def _search_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        hit = self._find_search_hit(item.data(0, Qt.ItemDataRole.UserRole))
        if hit is not None:
            self._navigate_to_location(
                hit.page_index,
                hit.rects,
                f"{hit.keyword} · page {hit.page_index + 1}",
            )

    def _search_selection_changed(self, current: QTreeWidgetItem | None, previous) -> None:
        hit = (
            self._find_search_hit(current.data(0, Qt.ItemDataRole.UserRole))
            if current is not None
            else None
        )
        self.add_search_evidence_button.setEnabled(hit is not None)

    def _add_selected_search_to_evidence(self) -> None:
        hit = self._selected_search_hit()
        if hit is None:
            return
        self._create_evidence(
            hit.page_index,
            hit.context or hit.matched_text,
            hit.rects,
            (hit.keyword,),
        )

    def _category_profile_text(self) -> str:
        active = sum(category.enabled for category in self.category_profile.categories)
        return f"{self.category_profile.name} · {active} active categories"

    def edit_bilingual_dictionary(self) -> None:
        if self._search_task is not None:
            return
        dialog = BilingualDictionaryEditorDialog(self.bilingual_dictionary, self)
        if dialog.exec() != BilingualDictionaryEditorDialog.DialogCode.Accepted:
            return
        dictionary = dialog.dictionary()
        try:
            self.bilingual_store.save(dictionary)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Dictionary not saved", str(error))
            return
        self.bilingual_dictionary = dictionary
        self.search_hits = ()
        self._search_keywords = ()
        self.search_tree.clear()
        self.add_search_evidence_button.setEnabled(False)
        self.search_summary.setText("Dictionary updated. Run the search again.")
        self._refresh_search_expansion_preview()

    def edit_categories(self) -> None:
        if self._category_task is not None:
            return
        dialog = CategoryEditorDialog(self.category_profile, self)
        if dialog.exec() != CategoryEditorDialog.DialogCode.Accepted:
            return
        profile = dialog.profile()
        try:
            self.category_store.save(profile)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Profile not saved", str(error))
            return
        self.category_profile = profile
        self.category_profile_label.setText(self._category_profile_text())
        self.category_matches = ()
        self.category_tree.clear()
        self.add_category_evidence_button.setEnabled(False)
        self.category_summary.setText("Profile updated. Run the analysis again.")

    def save_analysis_state_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save analysis profile",
            "PDF Analyzer State.pdfanalyzer-state.json",
            "PDF Analyzer Profile (*.pdfanalyzer-state.json);;JSON files (*.json)",
        )
        if not path:
            return
        if not path.casefold().endswith(".json"):
            path += ".pdfanalyzer-state.json"
        try:
            save_analysis_state(
                path,
                self.category_profile,
                self.keyword_input.toPlainText(),
                self.bilingual_dictionary,
                self._noise_options(),
            )
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Profile not saved", str(error))
            return
        self.category_summary.setText(f"Profile saved: {Path(path).name}")

    def load_analysis_state_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load analysis profile",
            "",
            "PDF Analyzer Profile (*.pdfanalyzer-state.json *.json)",
        )
        if not path:
            return
        try:
            state = load_analysis_state(path)
            self.category_store.save(state.profile)
            self.bilingual_store.save(state.bilingual_dictionary)
        except (OSError, ValueError, AnalysisStateError) as error:
            QMessageBox.warning(self, "Invalid profile", str(error))
            return
        self.category_profile = state.profile
        self.bilingual_dictionary = state.bilingual_dictionary
        self._set_noise_options(state.noise_options)
        self.keyword_input.setPlainText(state.keyword_text)
        self._refresh_search_expansion_preview()
        self.category_profile_label.setText(self._category_profile_text())
        self.category_matches = ()
        self.category_tree.clear()
        self.add_category_evidence_button.setEnabled(False)
        self.search_hits = ()
        self._search_keywords = ()
        self.search_tree.clear()
        self.add_search_evidence_button.setEnabled(False)
        self.search_summary.setText("Profile loaded. Run the search again.")
        self.category_summary.setText(
            f"Profile loaded: {Path(path).name}. Run the analysis again."
        )

    def run_category_analysis(self) -> None:
        if (
            self.document_text is None
            or self._category_task is not None
            or self._search_task is not None
            or self._standards_task is not None
        ):
            return
        generation = self._generation
        analysis_document, noise_report = self._filtered_analysis_document()
        self._last_noise_report = noise_report
        self.category_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.standards_button.setEnabled(False)
        self.ocr_button.setEnabled(False)
        self.edit_categories_button.setEnabled(False)
        self.category_button.setText("Analyzing…")
        self.category_summary.setText("Searching terms, paragraphs and nearby context locally…")
        task = BackgroundTask(analyze_categories, analysis_document, self.category_profile)
        self._category_task = task
        self._text_tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation, noise_report=noise_report: self._category_finished(
                task, generation, noise_report, result
            )
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation: self._category_failed(
                task, generation, error
            )
        )
        self.text_pool.start(task)

    def _category_finished(
        self,
        task: BackgroundTask,
        generation: int,
        noise_report: SearchNoiseReport,
        result: object,
    ) -> None:
        self._text_tasks.discard(task)
        if task is self._category_task:
            self._category_task = None
        self.category_button.setText("Analyze")
        self.edit_categories_button.setEnabled(True)
        if generation != self._generation or not isinstance(result, tuple):
            return
        self.category_matches = tuple(
            match for match in result if isinstance(match, CategoryMatch)
        )
        self._refresh_category_tree()
        note_batch = self._save_analysis_notes(
            category_evidence_drafts(self.category_matches)
        )
        categories_found = len({match.category_id for match in self.category_matches})
        high = sum(match.strength == "high" for match in self.category_matches)
        self.category_summary.setText(
            f"{categories_found} categories · {len(self.category_matches)} results · "
            f"{high} high relevance · {self._automatic_note_summary(note_batch)} · "
            f"{self._noise_summary(noise_report)}"
        )
        self.category_button.setEnabled(True)
        self.search_button.setEnabled(True)
        self.standards_button.setEnabled(True)
        self.ocr_button.setEnabled(
            bool(self.document_text and self.document_text.audit.empty_pages)
            and self.text_engine.ocr.available
        )

    def _category_failed(self, task: BackgroundTask, generation: int, error: object) -> None:
        self._text_tasks.discard(task)
        if task is self._category_task:
            self._category_task = None
        if generation != self._generation:
            return
        self.category_button.setText("Analyze")
        self.edit_categories_button.setEnabled(True)
        enabled = bool(self.document_text and self.document_text.audit.word_count)
        self.category_button.setEnabled(enabled)
        self.search_button.setEnabled(enabled)
        self.standards_button.setEnabled(enabled)
        self.category_summary.setText(f"Analysis failed: {error}")

    def _refresh_category_tree(self) -> None:
        self.category_tree.clear()
        first_result = None
        groups: dict[str, QTreeWidgetItem] = {}
        categories: dict[str, QTreeWidgetItem] = {}
        profile_order = {category.category_id: index for index, category in enumerate(self.category_profile.categories)}
        matches = sorted(
            self.category_matches,
            key=lambda match: (
                profile_order.get(match.category_id, 9999),
                -match.score,
                match.page_index,
            ),
        )
        for match in matches:
            if match.group not in groups:
                group_item = QTreeWidgetItem([match.group])
                group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.category_tree.addTopLevelItem(group_item)
                groups[match.group] = group_item
            if match.category_id not in categories:
                count = sum(item.category_id == match.category_id for item in matches)
                category_item = QTreeWidgetItem([f"{match.category_name} ({count})"])
                category_item.setFlags(category_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                groups[match.group].addChild(category_item)
                categories[match.category_id] = category_item
            context = match.context if len(match.context) <= 170 else match.context[:167].rstrip() + "…"
            child = QTreeWidgetItem(
                [f"p. {match.page_index + 1} · {match.strength} ({match.score}) · {context}"]
            )
            child.setData(0, Qt.ItemDataRole.UserRole, match.match_id)
            child.setToolTip(0, match.context + "\n\n" + "\n".join(match.reasons))
            categories[match.category_id].addChild(child)
            if first_result is None:
                first_result = child
        for group in groups.values():
            group.setExpanded(True)
        for category in categories.values():
            category.setExpanded(True)
        if first_result is not None:
            self.category_tree.setCurrentItem(first_result)
        self.add_category_evidence_button.setEnabled(first_result is not None)

    def _find_category_match(self, match_id: str | None) -> CategoryMatch | None:
        return next((match for match in self.category_matches if match.match_id == match_id), None)

    def _selected_category_match(self) -> CategoryMatch | None:
        item = self.category_tree.currentItem()
        return (
            self._find_category_match(item.data(0, Qt.ItemDataRole.UserRole))
            if item is not None
            else None
        )

    def _category_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        match = self._find_category_match(item.data(0, Qt.ItemDataRole.UserRole))
        if match is not None:
            self._navigate_to_location(
                match.page_index,
                match.rects,
                f"{match.category_name} · page {match.page_index + 1} · relevance {match.strength}",
            )

    def _category_selection_changed(self, current: QTreeWidgetItem | None, previous) -> None:
        match = (
            self._find_category_match(current.data(0, Qt.ItemDataRole.UserRole))
            if current is not None
            else None
        )
        self.add_category_evidence_button.setEnabled(match is not None)

    def _add_selected_category_to_evidence(self) -> None:
        match = self._selected_category_match()
        if match is not None:
            self._create_evidence(
                match.page_index,
                match.context,
                match.rects,
                (match.category_name,),
            )

    def run_standards_analysis(self) -> None:
        if (
            self.document_text is None
            or self._standards_task is not None
            or self._search_task is not None
            or self._category_task is not None
        ):
            return
        generation = self._generation
        analysis_document, noise_report = self._filtered_analysis_document()
        self._last_noise_report = noise_report
        self.standards_button.setEnabled(False)
        self.search_button.setEnabled(False)
        self.category_button.setEnabled(False)
        self.ocr_button.setEnabled(False)
        self.standards_button.setText("Analyzing…")
        self.standards_summary.setText("Detecting standards and technical document references locally…")
        task = BackgroundTask(analyze_standards, analysis_document)
        self._standards_task = task
        self._text_tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation, noise_report=noise_report: self._standards_finished(
                task, generation, noise_report, result
            )
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation: self._standards_failed(
                task, generation, error
            )
        )
        self.text_pool.start(task)

    def _standards_finished(
        self,
        task: BackgroundTask,
        generation: int,
        noise_report: SearchNoiseReport,
        result: object,
    ) -> None:
        self._text_tasks.discard(task)
        if task is self._standards_task:
            self._standards_task = None
        self.standards_button.setText("Analyze Standards")
        if generation != self._generation or not isinstance(result, tuple):
            return
        self.standard_matches = tuple(item for item in result if isinstance(item, StandardMatch))
        self._refresh_standards_tree()
        note_batch = self._save_analysis_notes(
            standard_evidence_drafts(self.standard_matches)
        )
        classifications = len({item.classification for item in self.standard_matches})
        self.standards_summary.setText(
            f"{len(self.standard_matches)} references · {classifications} classifications · "
            f"{self._automatic_note_summary(note_batch)} · "
            f"{self._noise_summary(noise_report)}"
        )
        enabled = bool(self.document_text and self.document_text.audit.word_count)
        self.standards_button.setEnabled(enabled)
        self.search_button.setEnabled(enabled)
        self.category_button.setEnabled(enabled)
        self.ocr_button.setEnabled(
            bool(self.document_text and self.document_text.audit.empty_pages)
            and self.text_engine.ocr.available
        )

    def _standards_failed(self, task: BackgroundTask, generation: int, error: object) -> None:
        self._text_tasks.discard(task)
        if task is self._standards_task:
            self._standards_task = None
        if generation != self._generation:
            return
        self.standards_button.setText("Analyze Standards")
        enabled = bool(self.document_text and self.document_text.audit.word_count)
        self.standards_button.setEnabled(enabled)
        self.search_button.setEnabled(enabled)
        self.category_button.setEnabled(enabled)
        self.standards_summary.setText(f"Standards analysis failed: {error}")

    def _refresh_standards_tree(self) -> None:
        self.standards_tree.clear()
        groups: dict[str, QTreeWidgetItem] = {}
        first = None
        for match in self.standard_matches:
            if match.classification not in groups:
                count = sum(
                    item.classification == match.classification for item in self.standard_matches
                )
                group = QTreeWidgetItem([f"{match.classification} ({count})"])
                group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
                self.standards_tree.addTopLevelItem(group)
                groups[match.classification] = group
            context = match.context if len(match.context) <= 150 else match.context[:147].rstrip() + "…"
            child = QTreeWidgetItem([f"p. {match.page_index + 1} · {match.reference} · {context}"])
            child.setData(0, Qt.ItemDataRole.UserRole, match.match_id)
            child.setToolTip(0, match.context + "\n\n" + "\n".join(match.reasons))
            groups[match.classification].addChild(child)
            first = first or child
        for group in groups.values():
            group.setExpanded(True)
        if first is not None:
            self.standards_tree.setCurrentItem(first)
        self.add_standard_note_button.setEnabled(first is not None)

    def _find_standard_match(self, match_id: str | None) -> StandardMatch | None:
        return next((item for item in self.standard_matches if item.match_id == match_id), None)

    def _selected_standard_match(self) -> StandardMatch | None:
        item = self.standards_tree.currentItem()
        return self._find_standard_match(item.data(0, Qt.ItemDataRole.UserRole)) if item else None

    def _standard_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        match = self._find_standard_match(item.data(0, Qt.ItemDataRole.UserRole))
        if match:
            self._navigate_to_location(
                match.page_index, match.rects,
                f"{match.reference} · page {match.page_index + 1} · {match.classification}",
            )

    def _standard_selection_changed(self, current: QTreeWidgetItem | None, previous) -> None:
        match = self._find_standard_match(current.data(0, Qt.ItemDataRole.UserRole)) if current else None
        self.add_standard_note_button.setEnabled(match is not None)

    def _add_selected_standard_to_evidence(self) -> None:
        match = self._selected_standard_match()
        if match:
            self._create_evidence(
                match.page_index, match.context, match.rects,
                (match.classification, match.reference),
            )

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for suffix in ("B", "KB", "MB", "GB"):
            if value < 1024 or suffix == "GB":
                return f"{value:.0f} {suffix}" if suffix == "B" else f"{value:.1f} {suffix}"
            value /= 1024
        return f"{value:.1f} GB"

    def _rebuild_pages(self) -> None:
        while self.page_layout.count():
            item = self.page_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.pages = []
        for layout in self.layouts:
            page = PageWidget(layout)
            page.image.highlightRequested.connect(self._create_highlight)
            page.image.evidenceRequested.connect(self._create_evidence)
            page.image.removeHighlightRequested.connect(self._remove_highlight)
            page.image.maskDrawn.connect(self._mask_drawn)
            page.set_highlights(self.highlights)
            page.set_area_masks(self.area_masks)
            page.set_mask_mode(
                self.mask_kind_combo.currentData()
                if self.draw_mask_button.isChecked()
                else None,
                str(self.mask_shape_combo.currentData()),
            )
            self.pages.append(page)
            self.page_layout.addWidget(page, 0, Qt.AlignmentFlag.AlignHCenter)
        self._apply_page_sizes()

    def _apply_text_layers(self) -> None:
        if self.document_text is None:
            return
        by_page = {page.page_index: page for page in self.document_text.pages}
        for page_index, page_widget in enumerate(self.pages):
            page_widget.set_page_text(by_page.get(page_index))

    def _create_highlight(self, page_index: int, text: str, rects: object) -> None:
        if self.document_info is None or not isinstance(rects, tuple):
            return
        try:
            highlight = self.highlight_store.create(
                self.document_info.document_id,
                page_index,
                text,
                rects,
            )
            updated = self.highlights + (highlight,)
            self.highlight_store.save(self.document_info.document_id, updated)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Highlight not saved", str(error))
            return
        self.highlights = updated
        self.pages[page_index].set_highlights(self.highlights)
        self.pages[page_index].image.clear_selection()
        self.status_label.setText("Highlight saved locally")

    def _remove_highlight(self, highlight_id: str) -> None:
        if self.document_info is None:
            return
        updated = tuple(
            highlight for highlight in self.highlights if highlight.highlight_id != highlight_id
        )
        if len(updated) == len(self.highlights):
            return
        try:
            self.highlight_store.save(self.document_info.document_id, updated)
        except OSError as error:
            QMessageBox.warning(self, "Highlight not updated", str(error))
            return
        self.highlights = updated
        for page in self.pages:
            page.set_highlights(self.highlights)
        self.status_label.setText("Highlight removed")

    def _toggle_evidence_panel(self, visible: bool) -> None:
        self.evidence_panel.setVisible(visible)
        if visible:
            navigation = 220 if self.navigation_panel.isVisible() else 0
            self.viewer_splitter.setSizes(
                [navigation, 330, max(self.viewer_splitter.width() - navigation - 330, 500)]
            )
        if self.fit_mode and self.layouts:
            self._resize_timer.start()

    def _toggle_navigation_panel(self, visible: bool) -> None:
        self.navigation_panel.setVisible(visible)
        if visible:
            evidence = 330 if self.evidence_panel.isVisible() else 0
            self.viewer_splitter.setSizes(
                [220, evidence, max(self.viewer_splitter.width() - evidence - 220, 500)]
            )
            QTimer.singleShot(0, self._refresh_visible_thumbnails)
        if self.fit_mode and self.layouts:
            self._resize_timer.start()

    def _populate_navigation(self, page_count: int) -> None:
        self.thumbnail_list.blockSignals(True)
        self.thumbnail_list.clear()
        for index in range(page_count):
            item = QListWidgetItem(f"Page {index + 1}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.thumbnail_list.addItem(item)
        self.thumbnail_list.setCurrentRow(0)
        self.thumbnail_list.blockSignals(False)
        self.outline_tree.clear()
        original_outline = self.session.outline()
        pdf_root = QTreeWidgetItem([f"PDF Bookmarks ({len(original_outline)})"])
        pdf_root.setFlags(pdf_root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.outline_tree.addTopLevelItem(pdf_root)
        parents: list[QTreeWidgetItem] = []
        for level, title, page_index in original_outline:
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.ItemDataRole.UserRole, ("pdf", page_index))
            while len(parents) >= level:
                parents.pop()
            if parents:
                parents[-1].addChild(item)
            else:
                pdf_root.addChild(item)
            parents.append(item)
        personal_root = QTreeWidgetItem(
            [f"My Bookmarks ({len(self.personal_bookmarks)})"]
        )
        personal_root.setFlags(personal_root.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        self.outline_tree.addTopLevelItem(personal_root)
        self._append_personal_bookmark_items(personal_root, None)
        pdf_root.setExpanded(True)
        personal_root.setExpanded(True)
        self.outline_tree.expandToDepth(1)
        self._bookmark_selection_changed(self.outline_tree.currentItem(), None)
        if self.navigation_panel.isVisible():
            QTimer.singleShot(0, self._refresh_visible_thumbnails)

    def _append_personal_bookmark_items(
        self,
        parent_item: QTreeWidgetItem,
        parent_id: str | None,
    ) -> None:
        for bookmark in self.personal_bookmarks:
            if bookmark.parent_id != parent_id:
                continue
            item = QTreeWidgetItem(
                [f"{bookmark.title} · p. {bookmark.page_index + 1}"]
            )
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                ("personal", bookmark.bookmark_id),
            )
            item.setToolTip(
                0,
                f"Page {bookmark.page_index + 1} · zoom {round(bookmark.zoom * 100)}%",
            )
            parent_item.addChild(item)
            self._append_personal_bookmark_items(item, bookmark.bookmark_id)

    def _thumbnail_selected(self, row: int) -> None:
        if 0 <= row < len(self.pages) and row != self.current_page:
            self.go_to_page(row)

    def _outline_selected(self, item: QTreeWidgetItem, column: int) -> None:
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not isinstance(data, tuple) or len(data) != 2:
            return
        kind, identity = data
        if kind == "pdf" and isinstance(identity, int):
            self.go_to_page(identity)
        elif kind == "personal" and isinstance(identity, str):
            bookmark = self._find_personal_bookmark(identity)
            if bookmark is not None:
                self._navigate_to_personal_bookmark(bookmark)

    def _selected_personal_bookmark(self) -> PersonalBookmark | None:
        item = self.outline_tree.currentItem()
        data = item.data(0, Qt.ItemDataRole.UserRole) if item is not None else None
        if (
            isinstance(data, tuple)
            and len(data) == 2
            and data[0] == "personal"
            and isinstance(data[1], str)
        ):
            return self._find_personal_bookmark(data[1])
        return None

    def _find_personal_bookmark(
        self,
        bookmark_id: str,
    ) -> PersonalBookmark | None:
        return next(
            (
                bookmark
                for bookmark in self.personal_bookmarks
                if bookmark.bookmark_id == bookmark_id
            ),
            None,
        )

    def _bookmark_selection_changed(
        self,
        current: QTreeWidgetItem | None,
        previous,
    ) -> None:
        selected = self._selected_personal_bookmark()
        enabled = selected is not None and self.document_info is not None
        for button in (
            self.rename_bookmark_button,
            self.delete_bookmark_button,
            self.bookmark_up_button,
            self.bookmark_down_button,
            self.bookmark_indent_button,
            self.bookmark_outdent_button,
        ):
            button.setEnabled(enabled)
        self.add_bookmark_button.setEnabled(self.document_info is not None)
        self.bookmarks_from_notes_button.setEnabled(
            self.document_info is not None and bool(self.evidence)
        )

    def _current_bookmark_position(self) -> tuple[int, float, float, float] | None:
        if not self.pages or not 0 <= self.current_page < len(self.pages):
            return None
        canvas = self.pages[self.current_page].image
        viewport = self.scroll.viewport()
        target = QPoint(viewport.width() // 2, round(viewport.height() * 0.30))
        canvas_point = canvas.mapFrom(viewport, target)
        source_x, source_y = canvas._page_point(canvas_point)
        return (
            self.current_page,
            clamp(source_x / canvas.page_width, 0.0, 1.0),
            clamp(source_y / canvas.page_height, 0.0, 1.0),
            clamp(self.zoom_scale, 0.25, 2.50),
        )

    def add_personal_bookmark(self) -> None:
        if self.document_info is None:
            return
        position = self._current_bookmark_position()
        if position is None:
            return
        page_index, x_ratio, y_ratio, zoom = position
        title, accepted = QInputDialog.getText(
            self,
            "Add bookmark",
            "Bookmark title",
            text=f"Page {page_index + 1}",
        )
        if not accepted or not title.strip():
            return
        bookmark = create_bookmark(
            self.document_info.document_id,
            title,
            page_index,
            x_ratio,
            y_ratio,
            zoom,
        )
        self._save_personal_bookmarks(
            self.personal_bookmarks + (bookmark,),
            bookmark.bookmark_id,
        )

    def rename_personal_bookmark(self) -> None:
        bookmark = self._selected_personal_bookmark()
        if bookmark is None:
            return
        title, accepted = QInputDialog.getText(
            self,
            "Rename bookmark",
            "Bookmark title",
            text=bookmark.title,
        )
        if not accepted:
            return
        try:
            updated = rename_bookmark(
                self.personal_bookmarks,
                bookmark.bookmark_id,
                title,
            )
        except ValueError as error:
            QMessageBox.warning(self, "Invalid bookmark", str(error))
            return
        self._save_personal_bookmarks(updated, bookmark.bookmark_id)

    def delete_personal_bookmark(self) -> None:
        bookmark = self._selected_personal_bookmark()
        if bookmark is None:
            return
        descendants = self._bookmark_descendant_count(bookmark.bookmark_id)
        suffix = (
            f" and its {descendants} nested bookmark(s)" if descendants else ""
        )
        answer = QMessageBox.question(
            self,
            "Delete bookmark",
            f'Delete "{bookmark.title}"{suffix}?',
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._save_personal_bookmarks(
            delete_bookmark_tree(self.personal_bookmarks, bookmark.bookmark_id)
        )

    def _bookmark_descendant_count(self, bookmark_id: str) -> int:
        removed = delete_bookmark_tree(self.personal_bookmarks, bookmark_id)
        return max(0, len(self.personal_bookmarks) - len(removed) - 1)

    def move_personal_bookmark(self, direction: int) -> None:
        bookmark = self._selected_personal_bookmark()
        if bookmark is None:
            return
        self._save_personal_bookmarks(
            move_bookmark(self.personal_bookmarks, bookmark.bookmark_id, direction),
            bookmark.bookmark_id,
        )

    def indent_personal_bookmark(self) -> None:
        bookmark = self._selected_personal_bookmark()
        if bookmark is None:
            return
        self._save_personal_bookmarks(
            indent_bookmark(self.personal_bookmarks, bookmark.bookmark_id),
            bookmark.bookmark_id,
        )

    def outdent_personal_bookmark(self) -> None:
        bookmark = self._selected_personal_bookmark()
        if bookmark is None:
            return
        self._save_personal_bookmarks(
            outdent_bookmark(self.personal_bookmarks, bookmark.bookmark_id),
            bookmark.bookmark_id,
        )

    def _save_personal_bookmarks(
        self,
        bookmarks: tuple[PersonalBookmark, ...],
        selected_id: str | None = None,
    ) -> None:
        if self.document_info is None:
            return
        try:
            self.bookmark_store.save(
                self.document_info.document_id,
                bookmarks,
                self.document_info.page_count,
            )
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Bookmarks not saved", str(error))
            return
        self.personal_bookmarks = bookmarks
        self._populate_navigation(self.document_info.page_count)
        if selected_id:
            self._select_personal_bookmark_item(selected_id)
        self.navigation_button.setChecked(True)
        self.navigation_tabs.setCurrentIndex(1)
        self.status_label.setText(f"{len(bookmarks)} personal bookmarks saved")

    def _select_personal_bookmark_item(self, bookmark_id: str) -> None:
        def visit(item: QTreeWidgetItem) -> QTreeWidgetItem | None:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data == ("personal", bookmark_id):
                return item
            for index in range(item.childCount()):
                found = visit(item.child(index))
                if found is not None:
                    return found
            return None

        for index in range(self.outline_tree.topLevelItemCount()):
            found = visit(self.outline_tree.topLevelItem(index))
            if found is not None:
                self.outline_tree.setCurrentItem(found)
                return

    def _navigate_to_personal_bookmark(
        self,
        bookmark: PersonalBookmark,
    ) -> None:
        if not 0 <= bookmark.page_index < len(self.pages):
            return
        self.zoom_scale = clamp(bookmark.zoom, 0.25, 2.50)
        self.fit_mode = False
        self._apply_page_sizes()
        self._set_current_page(bookmark.page_index)

        def restore() -> None:
            if bookmark.page_index >= len(self.pages):
                return
            canvas = self.pages[bookmark.page_index].image
            source_x = bookmark.x_ratio * canvas.page_width
            source_y = bookmark.y_ratio * canvas.page_height
            display_x, display_y = canvas._source_to_display(source_x, source_y)
            display_width, display_height = canvas._display_page_size()
            origin = canvas.mapTo(self.page_host, QPoint(0, 0))
            target_x = origin.x() + display_x / display_width * canvas.width()
            target_y = origin.y() + display_y / display_height * canvas.height()
            self.scroll.horizontalScrollBar().setValue(
                round(target_x - self.scroll.viewport().width() * 0.5)
            )
            self.scroll.verticalScrollBar().setValue(
                round(target_y - self.scroll.viewport().height() * 0.30)
            )

        restore()
        QTimer.singleShot(0, restore)
        QTimer.singleShot(20, restore)
        self._request_render(bookmark.page_index)
        self.status_label.setText(
            f"Bookmark: {bookmark.title} · page {bookmark.page_index + 1}"
        )

    def generate_bookmarks_from_notes(self) -> None:
        if self.document_info is None or not self.evidence or not self.layouts:
            return
        updated = list(self.personal_bookmarks)
        roots_by_title = {
            item.title.casefold(): item
            for item in updated
            if item.parent_id is None and item.title.startswith("Tag: ")
        }
        created = 0
        tags = sorted(
            {tag for note in self.evidence for tag in (note.tags or ("Untagged",))},
            key=str.casefold,
        )
        for tag in tags:
            notes = tuple(
                note
                for note in self.evidence
                if tag in (note.tags or ("Untagged",))
            )
            first = notes[0]
            rect = first.rects[0]
            layout = self.layouts[first.page_index]
            root_title = f"Tag: {tag}"
            root = roots_by_title.get(root_title.casefold())
            if root is None:
                root = create_bookmark(
                    self.document_info.document_id,
                    root_title,
                    first.page_index,
                    clamp(rect.x0 / layout.width_points, 0.0, 1.0),
                    clamp(rect.y0 / layout.height_points, 0.0, 1.0),
                    1.0,
                )
                updated.append(root)
                roots_by_title[root_title.casefold()] = root
                created += 1
            existing_children = {
                (item.title.casefold(), item.page_index)
                for item in updated
                if item.parent_id == root.bookmark_id
            }
            for note in sorted(notes, key=lambda item: (item.page_index, item.citation_number)):
                title = f"[{note.citation_number}] {note.comment or note.text}"
                title = " ".join(title.split())
                if len(title) > 150:
                    title = title[:147].rstrip() + "..."
                if (title.casefold(), note.page_index) in existing_children:
                    continue
                rect = note.rects[0]
                layout = self.layouts[note.page_index]
                updated.append(
                    create_bookmark(
                        self.document_info.document_id,
                        title,
                        note.page_index,
                        clamp(rect.x0 / layout.width_points, 0.0, 1.0),
                        clamp(rect.y0 / layout.height_points, 0.0, 1.0),
                        1.0,
                        root.bookmark_id,
                    )
                )
                created += 1
        if not created:
            QMessageBox.information(
                self,
                "Bookmarks already generated",
                "All notes and tags already have personal bookmarks.",
            )
            return
        self._save_personal_bookmarks(tuple(updated))

    def _refresh_visible_thumbnails(self) -> None:
        if not self.navigation_panel.isVisible() or not self.document_info:
            return
        viewport = self.thumbnail_list.viewport()
        top = self.thumbnail_list.indexAt(QPoint(2, 2)).row()
        bottom = self.thumbnail_list.indexAt(QPoint(2, max(2, viewport.height() - 2))).row()
        if top < 0:
            top = max(0, self.current_page - 2)
        if bottom < 0:
            bottom = min(len(self.pages) - 1, top + 8)
        for page_index in range(max(0, top - 2), min(len(self.pages), bottom + 3)):
            item = self.thumbnail_list.item(page_index)
            if item is None or not item.icon().isNull() or page_index in self._thumbnail_pending:
                continue
            self._thumbnail_pending.add(page_index)
            generation = self._generation
            view_revision = self._view_revision
            task = BackgroundTask(self.session.render, page_index, 180, self.rotation)
            task.signals.completed.connect(
                lambda result, task=task, generation=generation, view_revision=view_revision: self._thumbnail_finished(
                    task, generation, view_revision, result
                )
            )
            task.signals.failed.connect(
                lambda error, task=task, index=page_index: self._thumbnail_failed(task, index)
            )
            self.thumbnail_pool.start(task)

    def _thumbnail_finished(
        self, task: BackgroundTask, generation: int, view_revision: int, result: object
    ) -> None:
        if isinstance(result, RenderedPage):
            self._thumbnail_pending.discard(result.page_index)
        if (
            generation != self._generation
            or view_revision != self._view_revision
            or not isinstance(result, RenderedPage)
        ):
            return
        item = self.thumbnail_list.item(result.page_index)
        image = QImage.fromData(result.png_bytes, "PNG")
        if item is not None and not image.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(image)))
        QTimer.singleShot(0, self._refresh_visible_thumbnails)

    def _thumbnail_failed(self, task: BackgroundTask, page_index: int) -> None:
        self._thumbnail_pending.discard(page_index)

    def rotate_clockwise(self) -> None:
        if not self.pages:
            return
        self.rotation = (self.rotation + 90) % 360
        self._view_revision += 1
        self._render_pending.clear()
        self._thumbnail_pending.clear()
        self.thumbnail_pool.clear()
        for index in range(self.thumbnail_list.count()):
            self.thumbnail_list.item(index).setIcon(QIcon())
        for page in self.pages:
            page.image.set_rotation(self.rotation)
        self._apply_page_sizes()
        if self.fit_mode:
            self.fit_current_page()
        else:
            self._scroll_page_into_view(self.current_page)
            self._refresh_viewport()
        self.status_label.setText(f"Document rotation: {self.rotation}°")
        self._refresh_visible_thumbnails()

    def save_document_as(self) -> None:
        if self.document_info is None or self._save_copy_task is not None:
            return
        source = Path(self.document_info.path)
        destination, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", str(source.with_name(f"{source.stem} - copy.pdf")),
            "PDF documents (*.pdf)",
        )
        if not destination:
            return
        if not destination.casefold().endswith(".pdf"):
            destination += ".pdf"
        self.save_copy_button.setEnabled(False)
        task = BackgroundTask(PdfSession.copy_document, source, destination)
        self._save_copy_task = task
        task.signals.completed.connect(lambda result, task=task: self._save_copy_finished(task, result))
        task.signals.failed.connect(lambda error, task=task: self._save_copy_failed(task, error))
        self.pool.start(task)

    def _save_copy_finished(self, task: BackgroundTask, result: object) -> None:
        if task is self._save_copy_task:
            self._save_copy_task = None
        self.save_copy_button.setEnabled(self.document_info is not None)
        if isinstance(result, str):
            self.status_label.setText(f"PDF copy saved: {Path(result).name}")

    def _save_copy_failed(self, task: BackgroundTask, error: object) -> None:
        if task is self._save_copy_task:
            self._save_copy_task = None
        self.save_copy_button.setEnabled(self.document_info is not None)
        QMessageBox.warning(self, "Save As failed", str(error))

    def print_document(self) -> None:
        if self.document_info is None:
            return
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return
        painter = QPainter(printer)
        try:
            for page_index in range(self.document_info.page_count):
                if page_index:
                    printer.newPage()
                rendered = self.session.render(page_index, 2200, self.rotation)
                image = QImage.fromData(rendered.png_bytes, "PNG")
                target = printer.pageRect(QPrinter.Unit.DevicePixel)
                scaled = image.size().scaled(target.size().toSize(), Qt.AspectRatioMode.KeepAspectRatio)
                x = target.x() + (target.width() - scaled.width()) / 2
                y = target.y() + (target.height() - scaled.height()) / 2
                painter.drawImage(QRectF(x, y, scaled.width(), scaled.height()), image)
        finally:
            painter.end()

    def toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_button.setText("Full")
        else:
            self.showFullScreen()
            self.fullscreen_button.setText("Exit Fullscreen")

    def _refresh_tag_list(self) -> None:
        checked = {
            str(self.tag_list.item(index).data(Qt.ItemDataRole.UserRole)).casefold()
            for index in range(self.tag_list.count())
            if self.tag_list.item(index).checkState() == Qt.CheckState.Checked
        }
        known = {
            str(self.tag_list.item(index).data(Qt.ItemDataRole.UserRole)).casefold()
            for index in range(self.tag_list.count())
        }
        tags = {tag for note in self.evidence for tag in note.tags}
        if any(not note.tags for note in self.evidence):
            tags.add("")
        ordered = sorted(tags, key=lambda value: (not value, value.casefold()))
        self.tag_list.blockSignals(True)
        self.tag_list.clear()
        for tag in ordered:
            item = QListWidgetItem(tag or "Untagged")
            item.setData(Qt.ItemDataRole.UserRole, tag)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            identity = tag.casefold()
            item.setCheckState(
                Qt.CheckState.Checked
                if not known or identity in checked or identity not in known
                else Qt.CheckState.Unchecked
            )
            self.tag_list.addItem(item)
        self.tag_list.blockSignals(False)

    def _selected_export_tags(self) -> tuple[str, ...]:
        return tuple(
            str(self.tag_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.tag_list.count())
            if self.tag_list.item(index).checkState() == Qt.CheckState.Checked
        )

    def _tag_selection_changed(self, item: QListWidgetItem) -> None:
        self._refresh_evidence_list(refresh_tags=False)

    def _refresh_evidence_list(self, refresh_tags: bool = True) -> None:
        selected_id = None
        current = self.evidence_list.currentItem()
        if current is not None:
            selected_id = current.data(Qt.ItemDataRole.UserRole)
        if refresh_tags:
            self._refresh_tag_list()
        selected_tags = {tag.casefold() for tag in self._selected_export_tags()}
        self.evidence_list.clear()
        selected_item = None
        for evidence in self.evidence:
            note_tags = {tag.casefold() for tag in evidence.tags} or {""}
            if not note_tags.intersection(selected_tags):
                continue
            excerpt = " ".join(evidence.text.split())
            if len(excerpt) > 125:
                excerpt = excerpt[:122].rstrip() + "…"
            comment = " ".join(evidence.comment.split()) or "No personal comment"
            if len(comment) > 120:
                comment = comment[:117].rstrip() + "…"
            tags = ", ".join(evidence.tags) or "Untagged"
            item = QListWidgetItem(
                f"[{evidence.citation_number}] {comment}\n"
                f"p. {evidence.page_index + 1} · {tags}\n{excerpt}"
            )
            item.setData(Qt.ItemDataRole.UserRole, evidence.evidence_id)
            item.setToolTip(
                f"Comment: {evidence.comment or '—'}\n"
                f"Tags: {tags}\n\nSelected text:\n{evidence.text}"
            )
            self.evidence_list.addItem(item)
            if evidence.evidence_id == selected_id:
                selected_item = item
        if selected_item is not None:
            self.evidence_list.setCurrentItem(selected_item)
        elif self.evidence_list.count():
            self.evidence_list.setCurrentRow(0)
        self.evidence_button.setText(f"Analysis ({len(self.evidence)})")
        has_selection = self.evidence_list.currentItem() is not None
        self.copy_evidence_button.setEnabled(has_selection)
        self.remove_evidence_button.setEnabled(has_selection)

    def _save_analysis_notes(
        self,
        drafts: tuple[EvidenceDraft, ...],
    ) -> EvidenceBatchResult | None:
        if self.document_info is None:
            return None
        try:
            batch = self.evidence_store.add_many(
                self.document_info.document_id,
                self.evidence,
                drafts,
            )
        except (OSError, ValueError) as error:
            QMessageBox.warning(
                self,
                "Automatic notes not saved",
                str(error),
            )
            return None
        if batch.added:
            self.evidence = batch.evidence
            self._workspace_summary = None
            if self._workspace_dashboard is not None:
                self._workspace_dashboard.mark_stale()
            self._refresh_evidence_list()
            self.status_label.setText(
                f"{len(batch.added)} analysis notes saved locally"
            )
        return batch

    @staticmethod
    def _automatic_note_summary(batch: EvidenceBatchResult | None) -> str:
        if batch is None:
            return "automatic notes not saved"
        added = len(batch.added)
        return f"{added} notes added · {batch.skipped_count} already present"

    def _create_evidence(
        self,
        page_index: int,
        text: str,
        rects: object,
        default_tags: tuple[str, ...] = (),
    ) -> None:
        if self.document_info is None or not isinstance(rects, tuple):
            return
        existing_tags = tuple(sorted({tag for item in self.evidence for tag in item.tags}, key=str.casefold))
        note_data = NoteDialog.get_note(self, text, existing_tags, default_tags)
        if note_data is None:
            return
        comment, tags = note_data
        try:
            evidence = self.evidence_store.create(
                self.document_info.document_id,
                self.evidence,
                page_index,
                text,
                rects,
                comment,
                tags,
            )
            updated = self.evidence + (evidence,)
            self.evidence_store.save(self.document_info.document_id, updated)
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Note not saved", str(error))
            return
        self.evidence = updated
        self._workspace_summary = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.mark_stale()
        self._refresh_evidence_list()
        self.analysis_tabs.setCurrentIndex(0)
        self.evidence_button.setChecked(True)
        for index in range(self.evidence_list.count()):
            item = self.evidence_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == evidence.evidence_id:
                self.evidence_list.setCurrentItem(item)
                break
        self.pages[page_index].image.clear_selection()
        self.status_label.setText(f"Note [{evidence.citation_number}] saved locally")
        QTimer.singleShot(100, lambda: self._navigate_to_evidence(evidence))

    def _find_evidence(self, evidence_id: str | None) -> Evidence | None:
        return next((item for item in self.evidence if item.evidence_id == evidence_id), None)

    def _evidence_item_clicked(self, item: QListWidgetItem) -> None:
        evidence = self._find_evidence(item.data(Qt.ItemDataRole.UserRole))
        self.copy_evidence_button.setEnabled(evidence is not None)
        self.remove_evidence_button.setEnabled(evidence is not None)
        if evidence is not None:
            self._navigate_to_evidence(evidence)

    def _evidence_selection_changed(self, current: QListWidgetItem | None, previous) -> None:
        evidence = (
            self._find_evidence(current.data(Qt.ItemDataRole.UserRole))
            if current is not None
            else None
        )
        self.copy_evidence_button.setEnabled(evidence is not None)
        self.remove_evidence_button.setEnabled(evidence is not None)

    def _navigate_to_evidence(self, evidence: Evidence) -> None:
        self._navigate_to_location(
            evidence.page_index,
            evidence.rects,
            f"Note [{evidence.citation_number}] · page {evidence.page_index + 1}",
        )

    def _navigate_to_location(
        self,
        page_index: int,
        rects: tuple[TextRect, ...],
        status: str,
    ) -> None:
        if not 0 <= page_index < len(self.pages) or not rects:
            return
        self._set_current_page(page_index)
        page = self.pages[page_index]
        canvas = page.image
        first_rect = rects[0]
        canvas_origin = canvas.mapTo(self.page_host, QPoint(0, 0))
        target_x = canvas_origin.x() + (first_rect.x0 + first_rect.x1) / 2 / canvas.page_width * canvas.width()
        target_y = canvas_origin.y() + first_rect.y0 / canvas.page_height * canvas.height()
        horizontal = self.scroll.horizontalScrollBar()
        vertical = self.scroll.verticalScrollBar()
        horizontal.setValue(round(target_x - self.scroll.viewport().width() * 0.5))
        vertical.setValue(round(target_y - self.scroll.viewport().height() * 0.30))
        canvas.flash_evidence(rects)
        self._request_render(page_index)
        self.status_label.setText(status)

    def _selected_evidence(self) -> Evidence | None:
        item = self.evidence_list.currentItem()
        if item is None:
            return None
        return self._find_evidence(item.data(Qt.ItemDataRole.UserRole))

    def _copy_selected_evidence(self) -> None:
        evidence = self._selected_evidence()
        if evidence is None:
            return
        QApplication.clipboard().setText(
            f"[{evidence.citation_number}] {evidence.comment or evidence.text}\n"
            f"Tags: {', '.join(evidence.tags) or 'Untagged'}\n"
            f"Selected text: {evidence.text}\nPage {evidence.page_index + 1}"
        )

    def _remove_selected_evidence(self) -> None:
        evidence = self._selected_evidence()
        if evidence is None or self.document_info is None:
            return
        updated = tuple(item for item in self.evidence if item.evidence_id != evidence.evidence_id)
        try:
            self.evidence_store.save(self.document_info.document_id, updated)
        except OSError as error:
            QMessageBox.warning(self, "Note not updated", str(error))
            return
        self.evidence = updated
        self._workspace_summary = None
        if self._workspace_dashboard is not None:
            self._workspace_dashboard.mark_stale()
        self._refresh_evidence_list()
        self.status_label.setText(f"Note [{evidence.citation_number}] removed")

    def _base_size(self, page_index: int) -> tuple[float, float]:
        layout = self.layouts[page_index]
        ratio = (
            layout.width_points / max(layout.height_points, 1.0)
            if self.rotation in (90, 270)
            else layout.height_points / max(layout.width_points, 1.0)
        )
        return float(BASE_RENDER_WIDTH), BASE_RENDER_WIDTH * ratio

    def _apply_page_sizes(self) -> None:
        if not self.pages:
            return
        maximum_width = 0
        total_height = 48 + max(0, len(self.pages) - 1) * self.page_layout.spacing()
        for index, page in enumerate(self.pages):
            base_width, base_height = self._base_size(index)
            width = round(base_width * self.zoom_scale)
            height = round(base_height * self.zoom_scale)
            page.set_display_size(width, height)
            maximum_width = max(maximum_width, width)
            total_height += page.sizeHint().height()
        self.page_host.setMinimumWidth(maximum_width + 48)
        self.page_host.setMinimumHeight(total_height)
        self.page_host.updateGeometry()
        self.page_layout.invalidate()
        self.page_layout.activate()
        QApplication.sendPostedEvents(self.page_host, QEvent.Type.LayoutRequest)
        self.zoom_label.setText(f"{round(self.zoom_scale * 100)}%")

    def fit_current_page(self) -> None:
        if not self.layouts:
            return
        base_width, base_height = self._base_size(self.current_page)
        viewport = self.scroll.viewport().size()
        self.zoom_scale = calculate_fit_scale(
            viewport.width(), viewport.height(), base_width, base_height, padding=48
        )
        self.fit_mode = True
        self._apply_page_sizes()
        self._scroll_page_into_view(self.current_page)
        self._refresh_viewport()

    def _refit_after_resize(self) -> None:
        if self.fit_mode and self.layouts:
            self.fit_current_page()

    def _capture_anchor(self, point: QPoint) -> ZoomAnchor | None:
        if not self.pages:
            return None
        best_index = self.current_page
        best_distance = float("inf")
        for index, page in enumerate(self.pages):
            top_left = page.image.mapTo(self.scroll.viewport(), QPoint(0, 0))
            right = top_left.x() + page.image.width()
            bottom = top_left.y() + page.image.height()
            if top_left.x() <= point.x() <= right and top_left.y() <= point.y() <= bottom:
                best_index = index
                break
            nearest_x = clamp(point.x(), top_left.x(), right)
            nearest_y = clamp(point.y(), top_left.y(), bottom)
            distance = (point.x() - nearest_x) ** 2 + (point.y() - nearest_y) ** 2
            if distance < best_distance:
                best_distance = distance
                best_index = index
        image = self.pages[best_index].image
        top_left = image.mapTo(self.scroll.viewport(), QPoint(0, 0))
        ratio_x = clamp((point.x() - top_left.x()) / max(image.width(), 1), 0.0, 1.0)
        ratio_y = clamp((point.y() - top_left.y()) / max(image.height(), 1), 0.0, 1.0)
        return ZoomAnchor(best_index, ratio_x, ratio_y, point.x(), point.y())

    def _restore_anchor(self, anchor: ZoomAnchor) -> None:
        if anchor.page_index >= len(self.pages):
            return
        image = self.pages[anchor.page_index].image
        top_left = image.mapTo(self.scroll.viewport(), QPoint(0, 0))
        new_x = top_left.x() + anchor.ratio_x * image.width()
        new_y = top_left.y() + anchor.ratio_y * image.height()
        horizontal = self.scroll.horizontalScrollBar()
        vertical = self.scroll.verticalScrollBar()
        horizontal.setValue(round(horizontal.value() + new_x - anchor.viewport_x))
        vertical.setValue(round(vertical.value() + new_y - anchor.viewport_y))

    def _restore_anchor_after_layout(self, anchor: ZoomAnchor, revision: int) -> None:
        """Compensate again after QScrollArea finishes its deferred relayout."""
        if revision != self._zoom_revision:
            return
        self.page_layout.activate()
        self._restore_anchor(anchor)

    def _set_zoom(self, direction: int, point: QPoint) -> None:
        anchor = self._capture_anchor(point)
        new_scale = next_zoom_scale(self.zoom_scale, direction)
        if anchor is None or new_scale == self.zoom_scale:
            return
        self.zoom_scale = new_scale
        self.fit_mode = False
        self._zoom_revision += 1
        revision = self._zoom_revision
        self._apply_page_sizes()
        # The first correction gives immediate feedback. Qt can subsequently move
        # the centered content while updating scroll ranges, so the same anchor is
        # corrected again after both deferred layout passes. Older corrections are
        # ignored when the user zooms rapidly.
        self._restore_anchor(anchor)
        QTimer.singleShot(0, lambda: self._restore_anchor_after_layout(anchor, revision))
        QTimer.singleShot(20, lambda: self._restore_anchor_after_layout(anchor, revision))
        # Keep the interaction immediate, then request a high-resolution render
        # only after the wheel has settled.
        self._quality_timer.start()

    def zoom_from_center(self, direction: int) -> None:
        viewport = self.scroll.viewport()
        self._set_zoom(direction, QPoint(viewport.width() // 2, viewport.height() // 2))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Wheel:
            wheel = event
            if isinstance(wheel, QWheelEvent) and wheel.modifiers() & Qt.KeyboardModifier.ControlModifier:
                delta = wheel.angleDelta().y() or wheel.pixelDelta().y()
                if delta:
                    self._set_zoom(1 if delta > 0 else -1, wheel.position().toPoint())
                wheel.accept()
                return True
        return super().eventFilter(watched, event)

    def _on_scrolled(self) -> None:
        self._scroll_timer.start()

    def _refresh_viewport(self) -> None:
        if not self.pages:
            return
        viewport_height = self.scroll.viewport().height()
        visible: list[int] = []
        center_distances: list[tuple[float, int]] = []
        target_y = viewport_height * 0.35
        for index, page in enumerate(self.pages):
            top = page.image.mapTo(self.scroll.viewport(), QPoint(0, 0)).y()
            bottom = top + page.image.height()
            if bottom >= -viewport_height and top <= viewport_height * 2:
                visible.append(index)
            center_distances.append((abs((top + bottom) / 2 - target_y), index))
        if center_distances:
            self._set_current_page(min(center_distances)[1])
        wanted: set[int] = set()
        preload_distance = 1 if self.zoom_scale > 1.25 else PRELOAD_DISTANCE
        for index in visible or [self.current_page]:
            wanted.update(
                range(max(0, index - preload_distance), min(len(self.pages), index + preload_distance + 1))
            )
        for index in sorted(wanted, key=lambda item: abs(item - self.current_page)):
            self._request_render(index)
        keep_distance = 4 if self.zoom_scale > 1.25 else KEEP_DISTANCE
        for index, page in enumerate(self.pages):
            if abs(index - self.current_page) > keep_distance:
                page.unload()

    def _render_target_width(self) -> int:
        device_ratio = max(1.0, self.devicePixelRatioF())
        return round(clamp(BASE_RENDER_WIDTH * self.zoom_scale * device_ratio, 600, MAX_SCREEN_RENDER_WIDTH))

    def _request_render(self, page_index: int) -> None:
        target_width = self._render_target_width()
        if not self.pages[page_index].needs_render(target_width) or page_index in self._render_pending:
            return
        self._render_pending.add(page_index)
        generation = self._generation
        view_revision = self._view_revision
        task = BackgroundTask(self.session.render, page_index, target_width, self.rotation)
        self._tasks.add(task)
        task.signals.completed.connect(
            lambda result, task=task, generation=generation, view_revision=view_revision: self._render_finished(
                task, generation, view_revision, result
            )
        )
        task.signals.failed.connect(
            lambda error, task=task, generation=generation, index=page_index: self._render_failed(
                task, generation, index, error
            )
        )
        self.pool.start(task)

    def _render_finished(
        self, task: BackgroundTask, generation: int, view_revision: int, result: object
    ) -> None:
        self._tasks.discard(task)
        page = result
        if isinstance(page, RenderedPage):
            self._render_pending.discard(page.page_index)
        if (
            generation != self._generation
            or view_revision != self._view_revision
            or not isinstance(page, RenderedPage)
        ):
            return
        if page.page_index >= len(self.pages):
            return
        image = QImage.fromData(page.png_bytes, "PNG")
        if image.isNull():
            self.status_label.setText(f"Page {page.page_number} could not be displayed")
            return
        page_widget = self.pages[page.page_index]
        page_widget.set_pixmap(QPixmap.fromImage(image), page.image_width)
        if page_widget.needs_render(self._render_target_width()):
            self._quality_timer.start()

    def _render_failed(self, task: BackgroundTask, generation: int, page_index: int, error: object) -> None:
        self._tasks.discard(task)
        self._render_pending.discard(page_index)
        if generation == self._generation:
            self.status_label.setText(f"Page {page_index + 1} error: {error}")

    def _set_current_page(self, page_index: int) -> None:
        page_index = max(0, min(page_index, len(self.pages) - 1))
        self.current_page = page_index
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page_index + 1)
        self.page_spin.blockSignals(False)
        self.previous_button.setEnabled(page_index > 0)
        self.next_button.setEnabled(page_index + 1 < len(self.pages))
        if self.thumbnail_list.currentRow() != page_index:
            self.thumbnail_list.blockSignals(True)
            self.thumbnail_list.setCurrentRow(page_index)
            self.thumbnail_list.blockSignals(False)

    def go_to_page(self, page_index: int) -> None:
        if not self.pages or not 0 <= page_index < len(self.pages):
            return
        self._set_current_page(page_index)
        self._scroll_page_into_view(page_index)
        self._refresh_viewport()

    def _scroll_page_into_view(self, page_index: int) -> None:
        page = self.pages[page_index]
        y = page.mapTo(self.page_host, QPoint(0, 0)).y()
        self.scroll.verticalScrollBar().setValue(max(0, y - 18))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.fit_mode and self.layouts:
            self._resize_timer.start()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._generation += 1
        self._text_cancel.set()
        self.pool.clear()
        self.text_pool.clear()
        self.thumbnail_pool.clear()
        self.pool.waitForDone(2500)
        self.text_pool.waitForDone(2500)
        self.thumbnail_pool.waitForDone(2500)
        self.session.close()
        super().closeEvent(event)
