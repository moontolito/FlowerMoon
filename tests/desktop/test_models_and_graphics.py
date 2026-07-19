from openpyxl import load_workbook
from PySide6.QtCore import Qt

from debbie.desktop.graphics import (
    EffectiveRegionItem,
    LayoutScene,
    PartGraphicsItem,
    StockBoundaryItem,
    UsableRegionItem,
)
from debbie.desktop.models import (
    DiagnosticsTableModel,
    PartsTableModel,
    StocksTableModel,
    UnplacedTableModel,
)
from debbie.importers.excel import ImportDiagnostic, ImportDiagnosticCode, ImportSeverity
from debbie.domain import (
    DemandItem,
    DemandItemId,
    Dimensions,
    Layout,
    LayoutId,
    PartType,
    PartTypeId,
    Placement,
    ProcessProfile,
    StockInstance,
    StockInstanceId,
    StockSpecification,
    StockSpecificationId,
    Work,
    WorkId,
)
from debbie.nesting import ResultStatus, nest_work
from debbie.importers.excel import import_canonical_workbook

from .conftest import make_import_result, make_work


def displayed(model, row: int, column: int):
    return model.data(model.index(row, column), Qt.ItemDataRole.DisplayRole)


def test_parts_model_columns_rounding_provenance_and_read_only() -> None:
    work = make_work()
    result = make_import_result(work)
    model = PartsTableModel()
    resets = []
    model.modelReset.connect(lambda: resets.append(True))
    original_length = work.part_types[0].dimensions.length
    model.set_work(work, result.records)
    assert model.rowCount() == 1
    assert model.columnCount() == 8
    assert displayed(model, 0, 1) == "P-0"
    assert displayed(model, 0, 2) == "DWG-0"
    assert displayed(model, 0, 3) == "40.00"
    assert displayed(model, 0, 6) == 4
    assert displayed(model, 0, 7) == "0° / 90°"
    assert not model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
    alignment = model.data(model.index(0, 3), Qt.ItemDataRole.TextAlignmentRole)
    assert alignment & int(Qt.AlignmentFlag.AlignRight)
    text_alignment = model.data(model.index(0, 0), Qt.ItemDataRole.TextAlignmentRole)
    assert text_alignment & int(Qt.AlignmentFlag.AlignLeft)
    assert work.part_types[0].dimensions.length == original_length
    assert resets


def test_provenance_joins_use_stable_ids_when_display_names_are_duplicated() -> None:
    first = make_work("A", "Duplicate")
    second = make_work("B", "Duplicate")
    result = make_import_result(first, second)
    model = PartsTableModel()
    model.set_work(second, result.records)
    assert displayed(model, 0, 2) == "DWG-1"


def test_stocks_model_reports_full_usable_effective_and_quantity() -> None:
    work = make_work(stock_quantity=2)
    model = StocksTableModel()
    model.set_work(work, make_import_result(work).records)
    assert model.columnCount() == 13
    assert displayed(model, 0, 2) == 2
    assert displayed(model, 0, 3) == "100.00"
    assert displayed(model, 0, 5) == "100.00"
    assert displayed(model, 0, 7) == "100.00%"
    assert displayed(model, 0, 8) == "100.00%"
    assert displayed(model, 0, 9) == "93.00"
    assert displayed(model, 0, 10) == "49.00"
    assert displayed(model, 0, 11) == "89.00"
    assert displayed(model, 0, 12) == "45.00"


def test_diagnostics_and_unplaced_models_preserve_structured_codes() -> None:
    diagnostics = DiagnosticsTableModel()
    diagnostics.set_diagnostics(
        (
            ImportDiagnostic(
                ImportSeverity.ERROR,
                ImportDiagnosticCode.EMPTY_REQUIRED_VALUE,
                "Value is required",
                worksheet="Parts",
                row=4,
                header="Quantity",
            ),
        )
    )
    assert [displayed(diagnostics, 0, column) for column in range(5)] == [
        "Error", "EMPTY_REQUIRED_VALUE", "Parts", 4, "Quantity"
    ]

    work = make_work(stock_quantity=0)
    result = nest_work(work)
    assert result.status is ResultStatus.PARTIAL
    unplaced = UnplacedTableModel()
    unplaced.set_unplaced(work, result.unplaced_demand)
    assert displayed(unplaced, 0, 2) == 4
    assert displayed(unplaced, 0, 3) == "INSUFFICIENT_STOCK_QUANTITY"
    assert not unplaced.flags(unplaced.index(0, 0)) & Qt.ItemFlag.ItemIsEditable


def test_layout_scene_renders_regions_parts_orientation_and_is_read_only(qt_app) -> None:
    work = make_work()
    result = nest_work(work)
    layout = result.layouts[0]
    scene = LayoutScene()
    original = tuple(layout.placements)
    scene.render_layout(work, layout)
    items = scene.items()
    assert sum(isinstance(item, StockBoundaryItem) for item in items) == 1
    assert sum(isinstance(item, UsableRegionItem) for item in items) == 1
    assert sum(isinstance(item, EffectiveRegionItem) for item in items) == 1
    stock_boundary = next(item for item in items if isinstance(item, StockBoundaryItem))
    usable_region = next(item for item in items if isinstance(item, UsableRegionItem))
    effective_region = next(item for item in items if isinstance(item, EffectiveRegionItem))
    assert stock_boundary.rect().getRect() == (0.0, 0.0, 100.0, 60.0)
    assert usable_region.rect().getRect() == (3.0, 5.0, 93.0, 49.0)
    assert effective_region.rect().getRect() == (5.0, 7.0, 89.0, 45.0)
    parts = [item for item in items if isinstance(item, PartGraphicsItem)]
    assert len(parts) == len(layout.placements)
    expected_origins = {
        (
            work.process_profile.trim.left + placement.x,
            work.process_profile.trim.top + placement.y,
        )
        for placement in layout.placements
    }
    assert {(item.rect().x(), item.rect().y()) for item in parts} == expected_origins
    assert not parts[0].flags() & parts[0].GraphicsItemFlag.ItemIsMovable
    assert parts[0].flags() & parts[0].GraphicsItemFlag.ItemClipsChildrenToShape
    assert tuple(layout.placements) == original


def test_empty_scene_is_safe(qt_app) -> None:
    scene = LayoutScene()
    scene.render_layout(None, None)
    assert scene.items() == []


def test_rotated_part_uses_oriented_scene_dimensions(qt_app, canonical_workbook) -> None:
    workbook = load_workbook(canonical_workbook)
    workbook["Parts"]["D2"] = 40
    workbook["Parts"]["E2"] = 80
    workbook.save(canonical_workbook)
    workbook.close()
    imported = import_canonical_workbook(canonical_workbook)
    result = nest_work(imported.works[0])
    placement = result.layouts[0].placements[0]
    assert placement.orientation.value == 90
    scene = LayoutScene()
    scene.render_layout(imported.works[0], result.layouts[0])
    item = next(item for item in scene.items() if isinstance(item, PartGraphicsItem))
    assert item.rect().width() == 80
    assert item.rect().height() == 40


def test_rendering_few_hundred_rectangles_has_no_timing_threshold(qt_app) -> None:
    owner = WorkId("render-work")
    part = PartType(PartTypeId("render-part"), "Panel", Dimensions(40, 20))
    demand = DemandItem(DemandItemId("render-demand"), owner, part.id, 300)
    stock = StockSpecification(
        StockSpecificationId("render-stock"), "Long sheet", Dimensions(8500, 100)
    )
    stock_instance = StockInstance(
        StockInstanceId("render-sheet"), owner, stock.id, 1
    )
    work = Work.from_inputs(
        id=owner,
        name="Render fixture",
        batch_multiplier=1,
        process_profile=ProcessProfile(minimum_part_clearance=1),
        part_types=(part,),
        demand_items=(demand,),
        stock_specifications=(stock,),
        stock_instances=(stock_instance,),
    )
    placements = tuple(
        Placement(instance.id, (index % 200) * 41, (index // 200) * 21)
        for index, instance in enumerate(work.part_instances)
    )
    layout = Layout(
        LayoutId("render-layout"),
        owner,
        stock_instance.id,
        work.process_profile,
        placements,
    )
    scene = LayoutScene()
    scene.render_layout(work, layout)
    assert sum(isinstance(item, PartGraphicsItem) for item in scene.items()) == 300
    assert scene.sceneRect().contains(stock.dimensions.length, stock.dimensions.width)
