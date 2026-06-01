from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from ...ports.repositories import ChunkRepository, DocumentRepository
from ..deps import get_chunk_repository, get_document_repository
from ..schemas import ChunkOut, DocumentOut, chunk_to_out, document_to_out

router = APIRouter()


@router.get("", response_model=list[DocumentOut])
def list_documents(
    source_id: UUID | None = None,
    municipality: str | None = None,
    document_type: str | None = None,
    year: int | None = None,
    current_only: bool = True,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    repo: DocumentRepository = Depends(get_document_repository),
) -> list[DocumentOut]:
    docs = repo.list_documents(
        source_id=source_id,
        municipality=municipality,
        document_type=document_type,
        year=year,
        current_only=current_only,
        limit=limit,
        offset=offset,
    )
    return [document_to_out(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: UUID,
    repo: DocumentRepository = Depends(get_document_repository),
) -> DocumentOut:
    doc = repo.get_by_id(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return document_to_out(doc)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def list_chunks(
    document_id: UUID,
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    doc_repo: DocumentRepository = Depends(get_document_repository),
) -> list[ChunkOut]:
    if doc_repo.get_by_id(document_id) is None:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")
    return [chunk_to_out(c) for c in chunk_repo.list_by_document(document_id)]
