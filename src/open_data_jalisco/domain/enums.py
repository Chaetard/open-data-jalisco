from enum import StrEnum


class SourceKind(StrEnum):
    MUNICIPAL_PORTAL = "municipal_portal"
    STATE_TRANSPARENCY_PORTAL = "state_transparency_portal"
    NATIONAL_TRANSPARENCY_PLATFORM = "national_transparency_platform"
    GAZETTE = "gazette"
    OTHER = "other"


class DocumentType(StrEnum):
    CONTRACT = "contract"
    BIDDING = "bidding"
    AWARD = "award"
    REGULATION = "regulation"
    MINUTES = "minutes"
    BUDGET = "budget"
    FINANCIAL_REPORT = "financial_report"
    OTHER = "other"
    UNKNOWN = "unknown"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    EXTRACTED = "extracted"
    CHUNKED = "chunked"
    INDEXED = "indexed"
    FAILED = "failed"
    NEEDS_OCR = "needs_ocr"
