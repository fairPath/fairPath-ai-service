"""extract_resume_document carries the text and the page count the Checks read."""
from conftest import SYNTHETIC_RESUME_LINES, make_multipage_pdf, make_pdf
from extraction import extract_resume_document, extract_resume_text


def test_page_count_comes_from_the_pdf():
    pdf = make_multipage_pdf([SYNTHETIC_RESUME_LINES] * 3)

    document = extract_resume_document(pdf, "c-1")

    assert document.page_count == 3


def test_a_single_page_pdf_has_page_count_one():
    document = extract_resume_document(make_pdf(SYNTHETIC_RESUME_LINES), "c-1")

    assert document.page_count == 1


def test_document_text_holds_every_line_of_every_page_in_order():
    pdf = make_multipage_pdf([SYNTHETIC_RESUME_LINES, SYNTHETIC_RESUME_LINES])

    document = extract_resume_document(pdf, "c-1")

    assert document.text.splitlines() == SYNTHETIC_RESUME_LINES * 2


def test_extract_resume_text_still_returns_a_plain_string():
    # Job comparison calls this and uses the result as a str.
    text = extract_resume_text(make_pdf(SYNTHETIC_RESUME_LINES), "c-1")

    assert isinstance(text, str)
    assert text.splitlines() == SYNTHETIC_RESUME_LINES
