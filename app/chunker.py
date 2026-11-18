import sys                       # sys lets us read what the user types after the script name
from app.loader import load_pdf  # reuse the function we wrote in loader.py


def split_text(text, chunk_size=500, overlap=100):
    """Split one long text into overlapping chunks (list of strings)."""

    # Turn all newlines/tabs/multiple spaces into single spaces so text is clean
    text = " ".join(text.split())

    # This list will collect our chunks
    chunks = []

    # 'start' is where the current chunk begins; we begin at the first character
    start = 0

    # Total number of characters in the text
    total = len(text)

    # Keep going until we have covered the whole text
    while start < total:

        # 'end' is where the chunk should stop; min() makes sure we don't go past the text
        end = min(start + chunk_size, total)

        # If we are not at the very end, try not to cut a word in half
        if end < total:
            # Find the last space inside this window
            last_space = text.rfind(" ", start, end)
            # Use that space as the cut point, but only if it is not too early in the chunk
            if last_space > start + chunk_size // 2:
                end = last_space

        # Take the piece of text and remove spaces at both ends
        chunk = text[start:end].strip()

        # Save the chunk only if it is not empty
        if chunk:
            chunks.append(chunk)

        # If we reached the end of the text, stop the loop
        if end >= total:
            break

        # Move 'start' back by 'overlap' characters so the next chunk repeats a little
        # max(...) guarantees we always move forward, so the loop can never get stuck
        start = max(end - overlap, start + 1)

    # Give the list of chunks back
    return chunks


def chunk_pages(pages, chunk_size=500, overlap=100):
    """Take pages from load_pdf() and return chunks that remember source and page."""

    # This list will collect one dictionary per chunk
    all_chunks = []

    # A counter so every chunk gets its own unique id number
    chunk_id = 0

    # Go through each page one by one
    for page in pages:

        # Split this page's text into smaller pieces
        pieces = split_text(page["text"], chunk_size, overlap)

        # Go through each piece of this page
        for piece in pieces:
            # Save the chunk with its id, source file and page number
            all_chunks.append({
                "id": chunk_id,
                "source": page["source"],
                "page": page["page"],
                "text": piece,
            })
            # Increase the counter for the next chunk
            chunk_id += 1

    # Give the full list of chunks back
    return all_chunks


# This block runs only when we run this file directly
if __name__ == "__main__":
    # The first thing typed after the script name is the PDF path
    path = sys.argv[1]

    # Step 1: read the PDF into pages
    pages = load_pdf(path)

    # Step 2: split the pages into chunks
    chunks = chunk_pages(pages)

    # Show how many pages and chunks we got
    print(f"{len(pages)} page(s) became {len(chunks)} chunk(s)")

    # Show the first 3 chunks (or fewer if there are fewer)
    for c in chunks[:3]:
        print(f"\n--- Chunk {c['id']} | {c['source']} | page {c['page']} | {len(c['text'])} chars ---")
        print(c["text"])