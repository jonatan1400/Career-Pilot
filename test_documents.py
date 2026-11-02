import io
import pytest
from pypdf import PdfWriter
from reportlab.pdfgen import canvas
from docx import Document
from documents import extract_text, DocumentError


def test_valid_pdf():
    buffer = io.BytesIO()
    page = canvas.Canvas(buffer)
    page.drawString(50, 700, 'Student resume: Python, SQL and a machine learning portfolio.')
    page.save()
    assert 'Python, SQL' in extract_text(buffer.getvalue(), 'resume.pdf')


def test_docx_paragraphs_and_tables():
    doc = Document()
    doc.add_paragraph('Student with business analytics experience')
    doc.add_table(rows=1, cols=1).cell(0, 0).text = 'Python and SQL portfolio'
    buffer = io.BytesIO()
    doc.save(buffer)
    text = extract_text(buffer.getvalue(), 'resume.docx')
    assert 'business analytics' in text and 'Python and SQL' in text


def test_blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(DocumentError, match='scanned'):
        extract_text(buffer.getvalue(), 'scan.pdf')


def test_encrypted_pdf():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    writer.encrypt('private')
    buffer = io.BytesIO()
    writer.write(buffer)
    with pytest.raises(DocumentError, match='Password-protected'):
        extract_text(buffer.getvalue(), 'locked.pdf')


@pytest.mark.parametrize('name', ['bad.pdf', 'bad.docx'])
def test_corrupt_file(name):
    with pytest.raises(DocumentError):
        extract_text(b'invalid bytes', name)
