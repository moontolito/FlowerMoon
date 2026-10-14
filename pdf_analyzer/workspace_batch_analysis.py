"""Deterministic Categories and Standards analysis for a PDF workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .analysis_annotations import category_evidence_drafts, standard_evidence_drafts
from .area_masks import AreaMaskStore, apply_masks_to_document
from .categories import CategoryProfile
from .category_engine import analyze_categories
from .engine import PdfSession
from .evidence import EvidenceStore
from .noise_filter import SearchNoiseOptions, filter_document_for_analysis
from .standards_engine import analyze_standards
from .text_engine import TextEngine


@dataclass(frozen=True, slots=True)
class WorkspaceDocumentAnalysis:
    path: str
    name: str
    document_id: str
    page_count: int
    word_count: int
    empty_page_count: int
    category_count: int
    standard_count: int
    added_note_count: int
    existing_note_count: int
    error: str = ""


@dataclass(frozen=True, slots=True)
class WorkspaceBatchAnalysisResult:
    documents: tuple[WorkspaceDocumentAnalysis, ...]

    @property
    def analyzed_count(self) -> int:
        return sum(not item.error for item in self.documents)

    @property
    def failed_count(self) -> int:
        return sum(bool(item.error) for item in self.documents)

    @property
    def category_count(self) -> int:
        return sum(item.category_count for item in self.documents)

    @property
    def standard_count(self) -> int:
        return sum(item.standard_count for item in self.documents)

    @property
    def added_note_count(self) -> int:
        return sum(item.added_note_count for item in self.documents)

    @property
    def empty_page_count(self) -> int:
        return sum(item.empty_page_count for item in self.documents)


def analyze_workspace_documents(
    paths: tuple[str, ...],
    profile: CategoryProfile,
    noise_options: SearchNoiseOptions,
    text_cache_dir: str | Path,
    evidence_storage_dir: str | Path,
    mask_storage_dir: str | Path,
) -> WorkspaceBatchAnalysisResult:
    """Analyze every selected PDF and atomically persist findings per document."""
    if not paths:
        raise ValueError("Select at least one workspace document.")
    text_engine = TextEngine(cache_dir=text_cache_dir)
    evidence_store = EvidenceStore(evidence_storage_dir)
    mask_store = AreaMaskStore(mask_storage_dir)
    results: list[WorkspaceDocumentAnalysis] = []

    for path_value in paths:
        path = Path(path_value).resolve()
        session = PdfSession()
        try:
            info, layouts = session.open(path)
            document = text_engine.audit_document(path, info.document_id)
            heights = tuple(layout.height_points for layout in layouts)
            filtered, _ = filter_document_for_analysis(
                document,
                heights,
                noise_options,
            )
            page_sizes = tuple(
                (layout.width_points, layout.height_points) for layout in layouts
            )
            masks = mask_store.load(info.document_id, info.page_count)
            filtered, _ = apply_masks_to_document(filtered, page_sizes, masks)
            category_matches = analyze_categories(filtered, profile)
            standard_matches = analyze_standards(filtered)
            existing = evidence_store.load(info.document_id)
            drafts = (
                category_evidence_drafts(category_matches)
                + standard_evidence_drafts(standard_matches)
            )
            batch = evidence_store.add_many(
                info.document_id,
                existing,
                drafts,
            )
            results.append(
                WorkspaceDocumentAnalysis(
                    path=str(path),
                    name=info.name,
                    document_id=info.document_id,
                    page_count=info.page_count,
                    word_count=filtered.audit.word_count,
                    empty_page_count=len(document.audit.empty_pages),
                    category_count=len(category_matches),
                    standard_count=len(standard_matches),
                    added_note_count=len(batch.added),
                    existing_note_count=len(batch.evidence) - len(batch.added),
                )
            )
        except (OSError, ValueError, RuntimeError) as error:
            results.append(
                WorkspaceDocumentAnalysis(
                    path=str(path),
                    name=path.name,
                    document_id="",
                    page_count=0,
                    word_count=0,
                    empty_page_count=0,
                    category_count=0,
                    standard_count=0,
                    added_note_count=0,
                    existing_note_count=0,
                    error=str(error),
                )
            )
        finally:
            session.close()

    return WorkspaceBatchAnalysisResult(tuple(results))
