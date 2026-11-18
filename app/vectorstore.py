import os                                   # for working with folders and file paths
import sys                                  # to read what the user types after the script name
import json                                 # to save/load our chunks as a JSON file
import numpy as np                          # FAISS needs numbers in a numpy array
import faiss                                # the vector search library
from sentence_transformers import SentenceTransformer   # the embedding model

from app.loader import load_pdf             # our function that reads a PDF
from app.chunker import chunk_pages         # our function that splits pages into chunks

# Name of the free embedding model; it turns text into 384 numbers
MODEL_NAME = "all-MiniLM-L6-v2"

# Folder where we save the index so we don't rebuild it every time
INDEX_DIR = "faiss_index"

# Paths of the two files we save: the FAISS index and the chunk texts
INDEX_PATH = os.path.join(INDEX_DIR, "index.faiss")
CHUNKS_PATH = os.path.join(INDEX_DIR, "chunks.json")

# We keep the model in this variable so it is loaded only once (loading is slow)
_model = None


def get_model():
    """Load the embedding model the first time, then reuse it."""
    global _model                           # we want to change the variable defined above
    if _model is None:                      # only load if not loaded yet
        _model = SentenceTransformer(MODEL_NAME)   # first run downloads about 90 MB
    return _model                           # give the model back


def build_index(chunks):
    """Turn chunks into embeddings, store them in FAISS, and save to disk."""

    # Take only the text part of every chunk
    texts = [c["text"] for c in chunks]

    # Convert all texts to vectors; normalize_embeddings=True makes each vector length 1
    embeddings = get_model().encode(texts, normalize_embeddings=True)

    # FAISS wants float32 numbers in a numpy array
    embeddings = np.array(embeddings, dtype="float32")

    # dimension = how many numbers each vector has (384 for this model)
    dimension = embeddings.shape[1]

    # Create an empty index that compares vectors using inner product (= cosine here)
    index = faiss.IndexFlatIP(dimension)

    # Put all our chunk vectors into the index
    index.add(embeddings)

    # Make sure the folder to save into exists (does nothing if it already exists)
    os.makedirs(INDEX_DIR, exist_ok=True)

    # Save the FAISS index to disk
    faiss.write_index(index, INDEX_PATH)

    # Save the chunk texts too; FAISS stores only numbers, not the original text
    with open(CHUNKS_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    # Tell the caller how many chunks were indexed
    return len(chunks)


def load_index():
    """Load the saved FAISS index and the chunk texts from disk."""

    # If nothing was saved yet, stop with a clear message
    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError("No index found. Build the index first.")

    # Read the FAISS index from disk
    index = faiss.read_index(INDEX_PATH)

    # Read the chunk texts from disk
    with open(CHUNKS_PATH, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    # Give both back
    return index, chunks


def search(question, k=3):
    """Find the k chunks whose meaning is closest to the question."""

    # Load the saved index and chunks
    index, chunks = load_index()

    # Convert the question into a vector in the same way as the chunks
    q_vec = get_model().encode([question], normalize_embeddings=True)
    q_vec = np.array(q_vec, dtype="float32")

    # Never ask for more results than the number of chunks we have
    k = min(k, len(chunks))

    # Ask FAISS: scores = similarity numbers, ids = positions of the best chunks
    scores, ids = index.search(q_vec, k)

    # Build the result list
    results = []
    for score, i in zip(scores[0], ids[0]):
        chunk = dict(chunks[i])             # copy the chunk so we don't change the original
        chunk["score"] = float(score)       # add the similarity score (higher = closer)
        results.append(chunk)               # add to results

    # Give back the best chunks, best first
    return results


# This block runs only when we run this file directly (for testing)
if __name__ == "__main__":
    pdf_path = sys.argv[1]                  # first argument: path of the PDF
    question = sys.argv[2]                  # second argument: the question in quotes

    pages = load_pdf(pdf_path)              # read the PDF
    chunks = chunk_pages(pages)             # split into chunks
    count = build_index(chunks)             # embed + save the index
    print(f"Indexed {count} chunks")

    # Search and print the top results
    for r in search(question, k=3):
        print(f"\n--- score {r['score']:.3f} | {r['source']} | page {r['page']} | chunk {r['id']} ---")
        print(r["text"])