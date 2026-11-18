import os          # os helps us work with file paths and file names
import sys         # sys lets us read what the user types after the script name
from pypdf import PdfReader   # PdfReader opens a PDF and reads its pages


def load_pdf(file_path):
    """Read a PDF and return a list of pages: [{source, page, text}, ...]"""

    # Open the PDF file; PdfReader loads all its pages
    reader = PdfReader(file_path)

    # Get only the file name (e.g. "sample.pdf") from the full path
    file_name = os.path.basename(file_path)

    # This list will collect one dictionary per page
    pages = []

    # Loop over every page; start=1 so page numbers begin at 1, not 0
    for page_number, page in enumerate(reader.pages, start=1):

        # extract_text() returns the page's text; it can return None, so we use "or ''"
        text = page.extract_text() or ""

        # strip() removes extra spaces and blank lines at the start and end
        text = text.strip()

        # Skip empty pages (for example a page that is only an image)
        if text:
            # Save the text with its source file and page number
            pages.append({
                "source": file_name,
                "page": page_number,
                "text": text,
            })

    # Give the list of pages back to whoever called this function
    return pages


# This block runs only when we run this file directly (not when imported)
if __name__ == "__main__":
    # sys.argv[1] is the first thing typed after the script name (the PDF path)
    path = sys.argv[1]

    # Call our function to read the PDF
    result = load_pdf(path)

    # Show how many pages had text
    print(f"Loaded {len(result)} pages with text")

    # Show a short preview of the first page, if there is one
    if result:
        print("--- Page 1 preview ---")
        print(result[0]["text"][:300])   # [:300] means "first 300 characters"