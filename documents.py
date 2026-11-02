"""In-memory extraction, bounded documents, and transparent lexical retrieval."""
import io
import re
import zipfile
from pathlib import Path

MAX_BYTES = 5 * 1024 * 1024
MAX_CHARS = 40000
MAX_PAGES = 20


class DocumentError(ValueError):
    pass


def clean_text(text):
    text = text.replace('\x00', '').strip()
    if not text:
        raise DocumentError('The document has no readable text. Paste text or upload a text-based PDF/DOCX. Scanned PDFs require OCR before uploading.')
    if len(text) > MAX_CHARS:
        raise DocumentError('The document is too long. Limit each document to 40,000 characters.')
    return text


def extract_text(data, filename):
    if not data or len(data) > MAX_BYTES:
        raise DocumentError('Upload a nonempty file smaller than 5 MB.')
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == '.pdf':
            from pypdf import PdfReader
            if not data.startswith(b'%PDF-'):
                raise DocumentError('This file is not a valid PDF.')
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise DocumentError('Password-protected PDFs are not supported. Upload an unlocked copy.')
            if len(reader.pages) > MAX_PAGES:
                raise DocumentError('Please use a document with at most 20 pages.')
            parts = []
            for page in reader.pages:
                content = page.get_contents()
                if content and len(content.get_data()) > 5 * 1024 * 1024:
                    raise DocumentError('This PDF page is too complex. Export a simpler text-based PDF.')
                text = page.extract_text() or ''
                if len(text.strip()) < 20:
                    raise DocumentError('A PDF page has little or no readable text and may be scanned. Paste the complete text or upload a text-based PDF so no information is missed.')
                parts.append(text)
            return clean_text('\n\n'.join(parts))
        if suffix == '.docx':
            from docx import Document
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                if sum(i.file_size for i in archive.infolist()) > 20 * 1024 * 1024:
                    raise DocumentError('The expanded Word document is too large.')
                if 'word/document.xml' not in archive.namelist():
                    raise DocumentError('This file is not a valid DOCX.')
            doc = Document(io.BytesIO(data))
            parts = [p.text for p in doc.paragraphs]
            for table in doc.tables:
                parts.extend(' | '.join(c.text for c in row.cells) for row in table.rows)
            for section in doc.sections:
                parts.extend(p.text for p in section.header.paragraphs)
                parts.extend(p.text for p in section.footer.paragraphs)
            return clean_text('\n'.join(parts))
        raise DocumentError('Only PDF and DOCX uploads are supported.')
    except DocumentError:
        raise
    except Exception:
        raise DocumentError('The file could not be read. It may be damaged or unsupported. Try exporting it again or paste its text.') from None


def ground_document(text, query, prefix, budget=18000):
    """Keep complete short documents; rank longer chunks by query-term overlap."""
    chunks = [text[i:i + 1800] for i in range(0, len(text), 1600)]
    if not chunks:
        return {'sections': [], 'partial': False}
    selected = list(range(len(chunks)))
    if sum(map(len, chunks)) > budget:
        terms = set(re.findall(r'\w+', query.lower()))
        ranked = sorted(selected, key=lambda i: (-len(terms & set(re.findall(r'\w+', chunks[i].lower()))), i))
        # Preserve introductory education/profile context alongside relevant sections.
        selected = sorted(set([0] + [i for i in ranked if i != 0][:budget // 1800 - 1]))
    return {'sections': [{'id': f'{prefix}{i+1}', 'text': chunks[i]} for i in selected], 'partial': len(selected) < len(chunks)}
