"""Portable project files for multi-document reading workflows."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


PROJECT_SCHEMA_VERSION = 1
MAX_PROJECT_BYTES = 2_000_000
READING_STATUSES = (
    "Not Read",
    "Reading in Progress",
    "Read",
    "Reviewed",
    "Approved",
    "Needs Attention",
)


class ProjectStateError(ValueError):
    """Controlled error for an invalid or incompatible project file."""


@dataclass(frozen=True, slots=True)
class ProjectDocument:
    path: str
    reading_status: str = "Not Read"


@dataclass(frozen=True, slots=True)
class ProjectState:
    project_name: str
    documents: tuple[ProjectDocument, ...]
    schema_version: int = PROJECT_SCHEMA_VERSION


def normalize_path(path_value: str | Path) -> str:
    return os.path.normcase(str(Path(path_value).resolve()))


def validate_project(project: ProjectState) -> None:
    if project.schema_version != PROJECT_SCHEMA_VERSION:
        raise ProjectStateError("The project file version is not supported.")
    if not project.project_name.strip() or len(project.project_name.strip()) > 160:
        raise ProjectStateError("The project name must contain between 1 and 160 characters.")
    if not project.documents:
        raise ProjectStateError("A project must contain at least one PDF document.")
    identities: set[str] = set()
    for document in project.documents:
        if not document.path.strip() or Path(document.path).suffix.casefold() != ".pdf":
            raise ProjectStateError("Every project document must be a PDF file.")
        if document.reading_status not in READING_STATUSES:
            raise ProjectStateError(f"Invalid reading status: {document.reading_status}")
        identity = normalize_path(document.path)
        if identity in identities:
            raise ProjectStateError("The project contains duplicate PDF documents.")
        identities.add(identity)


def _portable_path(document_path: str, project_directory: Path) -> tuple[str, bool]:
    resolved = Path(document_path).resolve()
    try:
        return os.path.relpath(resolved, project_directory), True
    except ValueError:  # Different Windows drives cannot be represented relatively.
        return str(resolved), False


def save_project(path_value: str | Path, project: ProjectState) -> None:
    validate_project(project)
    destination = Path(path_value)
    project_directory = destination.resolve().parent
    serialized_documents = []
    for document in project.documents:
        stored_path, relative = _portable_path(document.path, project_directory)
        serialized_documents.append(
            {
                "path": stored_path,
                "relative": relative,
                "reading_status": document.reading_status,
            }
        )
    payload = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project_name": project.project_name.strip(),
        "documents": serialized_documents,
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)


def load_project(path_value: str | Path) -> ProjectState:
    source = Path(path_value)
    try:
        if not source.is_file() or source.stat().st_size > MAX_PROJECT_BYTES:
            raise ProjectStateError("The project file is missing or exceeds the 2 MB limit.")
        payload = json.loads(source.read_text(encoding="utf-8"))
        if payload.get("schema_version") != PROJECT_SCHEMA_VERSION:
            raise ProjectStateError("The project file version is not supported.")
        documents = []
        for item in payload.get("documents", []):
            stored_path = Path(item["path"])
            resolved = source.resolve().parent / stored_path if item.get("relative") else stored_path
            documents.append(
                ProjectDocument(
                    path=str(resolved.resolve()),
                    reading_status=item.get("reading_status", "Not Read"),
                )
            )
        project = ProjectState(
            project_name=payload["project_name"],
            documents=tuple(documents),
            schema_version=payload["schema_version"],
        )
        validate_project(project)
        return project
    except ProjectStateError:
        raise
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        raise ProjectStateError("The project file is invalid or corrupted.") from error
