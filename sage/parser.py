"""
Document parser — reads receipts, PDFs, images, CSVs, and text files.
Supports:
- Grocery item extraction and categorization
- RAG (Retrieval-Augmented Generation) chunk extraction
- KG (Knowledge Graph) entity and relationship extraction
"""
import csv
import io
import json
import re
from typing import Optional, Dict, List, Any

import pytesseract
from PIL import Image

from materalleapp.agent_base import get_anthropic_response

VALID_CATEGORIES = ["VEGETABLE", "FRUIT", "GRAIN", "PROTEIN", "DRINK", "OTHER"]

CATEGORIZE_PROMPT = (
    "You are a grocery item categorizer. "
    "Categorize each item into EXACTLY one of: VEGETABLE, FRUIT, GRAIN, PROTEIN, DRINK, OTHER.\n\n"
    "Rules:\n"
    "- Ignore prices, quantities, totals, tax lines, store names, dates, and non-food items.\n"
    "- Only include actual food/grocery items.\n"
    "- If an item could belong to multiple categories, pick the BEST one and also list it under \"CONFLICTS\" with possible categories.\n"
    "- Respond with ONLY a JSON object, no other text.\n\n"
    "Example response:\n"
    '{{"VEGETABLE": ["carrots", "broccoli"], "FRUIT": ["apples"], '
    '"GRAIN": ["bread"], "PROTEIN": ["chicken"], "DRINK": ["orange juice"], "OTHER": ["salt"], '
    '"CONFLICTS": [{{"name": "tomato paste", "suggested": "VEGETABLE", "alternatives": ["OTHER"]}}]}}\n\n'
    "Items:\n{items_text}"
)


# ============================================================================
# Image/PDF/Text Extraction
# ============================================================================

def extract_text_from_image(file) -> str:
    """OCR an image file (receipt photo, scanned list) into raw text."""
    image = Image.open(file)
    image = image.convert("L")  # Grayscale for better OCR accuracy
    text = pytesseract.image_to_string(image)
    return text


def extract_text_from_pdf(file) -> str:
    """Extract text from a PDF file. Uses pdfplumber if available, falls back to PyPDF2."""
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        return "\n".join(pages)
    except ImportError:
        pass

    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(file)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages)
    except ImportError:
        raise ImportError("Install pdfplumber or PyPDF2 to parse PDF files: pip install pdfplumber")


def extract_text_from_pdf_with_metadata(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract text from PDF with per-page metadata for RAG chunking."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("Install pdfplumber: pip install pdfplumber")

    pages_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            page_data = {
                "page": page_num + 1,
                "text": text,
                "source": pdf_path,
                "tables": page.extract_tables() or [],
                "width": page.width,
                "height": page.height,
            }
            pages_data.append(page_data)
    return pages_data


def extract_section_header(page_text: str) -> Optional[str]:
    """Extract section header from page text (first non-empty line or capitalized phrase)."""
    lines = page_text.split('\n')
    for line in lines:
        line = line.strip()
        if line and len(line) > 3 and line[0].isupper():
            return line[:100]  # First 100 chars as section
    return None


def convert_tables_to_text(tables: List) -> str:
    """Convert extracted tables to readable text format for RAG."""
    if not tables:
        return ""

    result = []
    for table_idx, table in enumerate(tables):
        result.append(f"\nTable {table_idx + 1}:")
        for row in table:
            row_text = " | ".join(str(cell or "") for cell in row)
            result.append(row_text)
    return "\n".join(result)


def tables_to_relationships(table: List, page_num: int) -> List[Dict]:
    """Convert table rows to entity relationships for KG."""
    relationships = []
    if not table or len(table) < 2:
        return relationships

    headers = table[0]
    for row_idx, row in enumerate(table[1:], 1):
        for col_idx, (header, cell) in enumerate(zip(headers, row)):
            if header and cell:
                relationships.append({
                    "subject": str(header).strip(),
                    "predicate": "has_value",
                    "object": str(cell).strip(),
                    "page": page_num,
                    "table_row": row_idx,
                })
    return relationships


def extract_entities(text: str, page_num: int) -> List[Dict]:
    """Extract named entities from text for KG."""
    entities = []

    # Simple regex-based entity extraction
    # Find capitalized phrases (likely entities)
    entity_pattern = r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b'
    matches = re.finditer(entity_pattern, text)

    seen = set()
    for match in matches:
        entity_text = match.group(0)
        if entity_text not in seen and len(entity_text) > 2:
            entities.append({
                "text": entity_text,
                "type": "UNKNOWN",  # Would be classified by NER model in production
                "page": page_num,
                "position": match.start(),
            })
            seen.add(entity_text)

    return entities


# ============================================================================
# CSV Parsing
# ============================================================================

def parse_csv_file(file) -> dict[str, list[str]]:
    """
    Parse a CSV into categorized items.
    Supports two formats:
    1. Columnar: headers like Vegetables, Fruits, Proteins, Grains, Drinks
    2. Row-based: columns for item name + category
    """
    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    file.seek(0)

    reader = csv.reader(io.StringIO(raw))
    headers = next(reader, None)
    if not headers:
        return {}

    normalized = [h.strip().upper().rstrip("S") for h in headers]
    category_cols = {}
    for i, col in enumerate(normalized):
        if col in VALID_CATEGORIES:
            category_cols[col] = i

    result = {cat: [] for cat in VALID_CATEGORIES}

    if category_cols:
        # Columnar format
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            for cat, idx in category_cols.items():
                if idx < len(row) and row[idx].strip():
                    result[cat].append(row[idx].strip())
    else:
        # Row-based format
        cat_idx = None
        name_idx = 0
        for i, h in enumerate(normalized):
            if h in ("CATEGORY", "TYPE", "GROUP"):
                cat_idx = i
            if h in ("NAME", "ITEM", "PRODUCT", "DESCRIPTION"):
                name_idx = i

        uncategorized = []
        for row in reader:
            if not any(cell.strip() for cell in row):
                continue
            name = row[name_idx].strip() if name_idx < len(row) else ""
            if not name:
                continue
            if cat_idx is not None and cat_idx < len(row):
                cat = row[cat_idx].strip().upper().rstrip("S")
                if cat not in VALID_CATEGORIES:
                    cat = "OTHER"
                result[cat].append(name)
            else:
                uncategorized.append(name)

        if uncategorized:
            return {"_uncategorized": uncategorized}

    return result


# ============================================================================
# Text Item Parsing
# ============================================================================

def parse_text_items(text: str) -> list[str]:
    """Extract individual item names from raw text (receipt OCR, plain text list)."""
    lines = text.strip().splitlines()
    items = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if re.match(
            r"^(total|subtotal|tax|change|cash|card|visa|mastercard|receipt|thank|"
            r"date|time|store|tel|phone|fax|www\.|http|address|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|"
            r"\*+|---+|===+)",
            line,
            re.IGNORECASE,
        ):
            continue
        cleaned = re.sub(r"^[\s\-\*•·]+", "", line).strip()
        # Quantity prefix must be stripped before bare digits, or "2x Apples" loses its 2
        cleaned = re.sub(r"^\d+\s*[xX]\s+", "", cleaned).strip()
        cleaned = re.sub(r"^[\d\.\)]+\s*", "", cleaned).strip()
        cleaned = re.sub(r"\s*\$?\d+\.\d{2}\s*[A-Z]?\s*$", "", cleaned).strip()
        if len(cleaned) < 2 or re.match(r"^\d+$", cleaned):
            continue
        items.append(cleaned)
    return items


# ============================================================================
# LLM-based Categorization
# ============================================================================

def categorize_with_llm(items: list[str]) -> dict:
    """
    Use the configured LLM backend to categorize item names.
    Returns categorized items with conflict resolution.
    """
    if not items:
        result = {cat: [] for cat in VALID_CATEGORIES}
        result["CONFLICTS"] = []
        return result

    prompt = CATEGORIZE_PROMPT.format(items_text="\n".join(items))
    messages = [{"role": "user", "content": prompt}]
    response = get_anthropic_response(messages)

    json_match = re.search(r"\{[\s\S]*\}", response)
    if not json_match:
        return {"OTHER": items, "CONFLICTS": []}

    try:
        parsed = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {"OTHER": items, "CONFLICTS": []}

    conflicts = []
    raw_conflicts = parsed.pop("CONFLICTS", [])
    if isinstance(raw_conflicts, list):
        conflict_names = set()
        for c in raw_conflicts:
            if isinstance(c, dict) and "name" in c:
                name = c["name"].strip().title()
                suggested = c.get("suggested", "OTHER").upper().rstrip("S")
                if suggested not in VALID_CATEGORIES:
                    suggested = "OTHER"
                alts = [
                    a.upper().rstrip("S") for a in c.get("alternatives", [])
                    if a.upper().rstrip("S") in VALID_CATEGORIES
                ]
                all_options = [suggested] + [a for a in alts if a != suggested]
                conflicts.append({
                    "name": name,
                    "suggested": suggested,
                    "alternatives": all_options,
                })
                conflict_names.add(name.lower())

    result = {cat: [] for cat in VALID_CATEGORIES}
    conflict_names_lower = {c["name"].lower() for c in conflicts}

    for raw_key, values in parsed.items():
        key = raw_key.strip().upper().rstrip("S")
        if key not in VALID_CATEGORIES:
            key = "OTHER"
        if isinstance(values, list):
            for v in values:
                if v.strip().title().lower() not in conflict_names_lower:
                    result[key].append(v)

    result["CONFLICTS"] = conflicts
    return result


# ============================================================================
# RAG + KG Parsing
# ============================================================================

def parse_for_rag_and_kg(pdf_path: str) -> Dict[str, Any]:
    """
    Extract content optimized for both RAG and KG from a PDF.

    Returns:
        {
            "rag": [
                {"content": "...", "page": 0, "section": "...", "source": "..."},
                ...
            ],
            "kg": {
                "entities": [{"text": "...", "type": "...", "page": 0}, ...],
                "relationships": [{"subject": "...", "predicate": "...", "object": "...", "page": 0}, ...]
            }
        }
    """
    rag_chunks = []
    kg_data = {"entities": [], "relationships": []}

    try:
        pages_data = extract_text_from_pdf_with_metadata(pdf_path)
    except ImportError:
        return {"rag": [], "kg": kg_data, "error": "pdfplumber required"}

    for page_data in pages_data:
        text = page_data["text"]
        page_num = page_data["page"]

        # RAG chunk
        chunk = {
            "content": text,
            "page": page_num,
            "source": pdf_path,
            "section": extract_section_header(text),
        }

        # Add tables as text for RAG
        if page_data["tables"]:
            table_text = convert_tables_to_text(page_data["tables"])
            chunk["content"] += "\n" + table_text

        # KG: Extract relationships from tables
        for table in page_data["tables"]:
            rels = tables_to_relationships(table, page_num)
            kg_data["relationships"].extend(rels)

        # Extract entities
        entities = extract_entities(text, page_num)
        kg_data["entities"].extend(entities)

        rag_chunks.append(chunk)

    return {
        "rag": rag_chunks,
        "kg": kg_data
    }


# ============================================================================
# Main Entry Points
# ============================================================================

def parse_document(file, filename: str) -> dict[str, list[str]]:
    """
    Main entry point: parse any supported document for grocery items.

    Supported formats:
      - .csv — parsed structurally
      - .txt — lines as items, LLM categorizes
      - .jpg/.jpeg/.png/.bmp/.tiff — OCR + LLM
      - .pdf — text extraction + LLM
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "csv":
        result = parse_csv_file(file)
        if "_uncategorized" in result:
            return categorize_with_llm(result["_uncategorized"])
        return result

    if ext in ("jpg", "jpeg", "png", "bmp", "tiff", "webp"):
        raw_text = extract_text_from_image(file)
        items = parse_text_items(raw_text)
        return categorize_with_llm(items)

    if ext == "pdf":
        raw_text = extract_text_from_pdf(file)
        items = parse_text_items(raw_text)
        return categorize_with_llm(items)

    # Default: treat as plain text
    raw = file.read()
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    items = parse_text_items(raw)
    return categorize_with_llm(items)


def parse_document_rag_kg(file_path: str) -> Dict[str, Any]:
    """
    Parse a document for RAG and KG extraction.
    Currently optimized for PDFs; image/text support can be added.
    """
    import os
    ext = os.path.splitext(file_path)[-1].lower()

    if ext == ".pdf":
        return parse_for_rag_and_kg(file_path)
    else:
        return {
            "rag": [],
            "kg": {"entities": [], "relationships": []},
            "error": f"RAG/KG parsing not yet supported for {ext} files"
        }
