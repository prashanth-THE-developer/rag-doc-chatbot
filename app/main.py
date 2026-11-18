import os                                        # for folders and file paths
import shutil                                    # to copy the uploaded file to disk
from fastapi import FastAPI, UploadFile, File, HTTPException   # FastAPI building blocks
from fastapi.middleware.cors import CORSMiddleware             # lets a React app call this API
from pydantic import BaseModel                   # defines the shape of the JSON we accept

from app.loader import load_pdf                  # reads a PDF
from app.chunker import chunk_pages              # splits pages into chunks
from app.vectorstore import build_index          # embeds chunks and saves the FAISS index
from app.rag import answer_question              # retrieve + ask Gemini

# Create the app; the title shows up in the auto-generated docs page
app = FastAPI(title="RAG Doc Chatbot")

# CORS: browsers block a frontend on one port from calling an API on another port.
# These origins are where our React app will run later (Vite uses 5173, CRA uses 3000).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Folder where uploaded PDFs are saved
DATA_DIR = "data"


class AskRequest(BaseModel):
    """The JSON body for /ask looks like: {"question": "...", "k": 5}"""
    question: str          # the user's question (required)
    k: int = 5             # how many chunks to retrieve (optional, default 5)


@app.get("/")
def home():
    """Health check: confirms the server is running."""
    return {"status": "ok", "message": "RAG Doc Chatbot API is running"}


@app.post("/upload")
def upload_pdf(file: UploadFile = File(...)):
    """Receive a PDF, read it, split it, embed it, and save the index."""

    # Only accept PDF files
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    # Make sure the data folder exists
    os.makedirs(DATA_DIR, exist_ok=True)

    # basename() removes any folder parts from the name, which is safer
    safe_name = os.path.basename(file.filename)
    save_path = os.path.join(DATA_DIR, safe_name)

    # Save the uploaded file to disk in binary mode
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Read the PDF pages
    pages = load_pdf(save_path)

    # If no text was found (for example a scanned PDF), tell the user
    if not pages:
        raise HTTPException(status_code=400, detail="No text found in this PDF. It may be a scanned PDF.")

    # Split into chunks and build the searchable index
    chunks = chunk_pages(pages)
    count = build_index(chunks)

    # Send a summary back to the client
    return {"message": "PDF indexed successfully", "file": safe_name, "pages": len(pages), "chunks": count}


@app.post("/ask")
def ask(req: AskRequest):
    """Answer a question using the currently indexed PDF."""

    # Reject empty questions
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        # Run the full RAG flow and return {"answer": ..., "sources": [...]}
        return answer_question(req.question, k=req.k)

    except FileNotFoundError:
        # This happens when no PDF has been uploaded/indexed yet
        raise HTTPException(status_code=400, detail="No document indexed yet. Upload a PDF first.")

    except Exception as e:
        # Any other problem (for example a Gemini error) becomes a clear 500 error
        raise HTTPException(status_code=500, detail=str(e))