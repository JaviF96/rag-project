import io
from pypdf import PdfReader


def extract_text_from_pdf(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages.append(page_text.strip())
    # Join on a newline rather than concatenating: without a separator the last
    # word of one page fuses to the first word of the next ("annually.Employees"),
    # which corrupts both the chunk text and its embedding.
    return "\n".join(pages)
