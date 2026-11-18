import os                                   # for folders and file paths
import sys                                  # to read what the user types after the script name
import json                                 # to save/load our chunks as a JSON file
import time                                 # to wait a little when the API says "slow down"
import numpy as np                          # FAISS needs numbers in a numpy array
import faiss                                # the vector search library
from dotenv import load_dotenv              # reads the .env file
from google import genai                    # the Gemini SDK
from google.genai import types              # settings objects for the embedding call

from app.loader import load_pdf             # our function that reads a PDF
from app.chunker import chunk_pages         # our function that splits pages into chunks

# Read .env so GEMINI_API_KEY and GEMINI_EMBED_MODEL are available
load_dotenv()

# Embedding model name comes from .env, so we can change it without touching the code
EMBED_MODEL = os.getenv("GEMINI_EMBED_MODEL", "gemini-embedding-001")

# We ask Gemini for 768 numbers per text: smaller and faster than the default 3072
EMBED_DIM = 768

# How many texts we send to Gemini in one request
BATCH_SIZE = 50

# Folder where we save the index so we don't rebuild it every time
INDEX_DIR = "faiss_index"

# Paths of the two files we save: the FAISS index and the chunk texts
INDEX_PATH = os.path.join(INDEX_DIR, "index.faiss")
CHUNKS_PATH = os.path.join(INDEX_DIR, "chunks.json")

# We keep the client here so it is created only once
_client = None


def get_client():
    """Create the Gemini client the first time, then reuse it."""
    global _client                                   # we want to change the variable above
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")        # read the key from .env
        if not api_key:                              # stop early with a clear message
            raise ValueError("GEMINI_API_KEY not found. Check your .env file.")
        _client = genai.Client(api_key=api_key)
    return _client


def embed_texts(texts, task_type):
    """Turn a list of texts into normalized vectors using the Gemini embedding API.
    task_type is RETRIEVAL_DOCUMENT for chunks and RETRIEVAL_QUERY for questions."""

    vectors = []                                     # all vectors will be collected here

    # Go through the texts in batches so one request is not too big
    for start in range(0, len(texts), BATCH_SIZE):
        batch = texts[start:start + BATCH_SIZE]      # the current group of texts

        # Try up to 4 times, because the free tier can say "too many requests"
        for attempt in range(4):
            try:
                result = get_client().models.embed_content(
                    model=EMBED_MODEL,
                    contents=batch,
                    config=types.EmbedContentConfig(
                        task_type=task_type,                 # tells Gemini how we will use the vectors
                        output_dimensionality=EMBED_DIM,     # 768 numbers per text
                    ),
                )
                break                                        # success: stop retrying
            except Exception as e:
                too_many = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)
                # Give up on the last attempt or on any error that is not a rate limit
                if attempt == 3 or not too_many:
                    raise
                time.sleep(5 * (2 ** attempt))               # wait 5s, 10s, 20s, then retry

        # Collect the numbers of each embedding in this batch
        vectors.extend([emb.values for emb in result.embeddings])

    # Convert to a float32 numpy array, which FAISS needs
    arr = np.array(vectors, dtype="float32")

    # Gemini does not normalize vectors when we use fewer than 3072 dimensions,
    # so we do it ourselves: make every vector length 1
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    arr = arr / np.maximum(norms, 1e-12)                     # max() avoids dividing by zero

    return arr


def build_index(chunks):
    """Turn chunks into embeddings, store them in FAISS, and save to disk."""

    # Take only the text part of every chunk
    texts = [c["text"] for c in chunks]

    # Convert all chunk texts to vectors
    embeddings = embed_texts(texts, "RETRIEVAL_DOCUMENT")

    # dimension = how many numbers each vector has (768 here)
    dimension = embeddings.shape[1]

    # Create an empty index that compares vectors using inner product (= cosine for normalized vectors)
    index = faiss.IndexFlatIP(dimension)

    # Put all our chunk vectors into the index
    index.add(embeddings)

    # Make sure the folder to save into exists
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

    # Convert the question into a vector, marked as a QUERY
    q_vec = embed_texts([question], "RETRIEVAL_QUERY")

    # Never ask for more results than the number of chunks we have
    k = min(k, len(chunks))

    # Ask FAISS: scores = similarity numbers, ids = positions of the best chunks
    scores, ids = index.search(q_vec, k)

    # Build the result list
    results = []
    for score, i in zip(scores[0], ids[0]):
        chunk = dict(chunks[i])             # copy the chunk so we don't change the original
        chunk["score"] = float(score)       # add the similarity score (higher = closer)
        results.append(chunk)

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