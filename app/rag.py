import os                                   # to read environment variables
import sys                                  # to read what the user types after the script name
from dotenv import load_dotenv              # reads the .env file
from google import genai                    # the Gemini SDK

from app.vectorstore import search          # our function that finds the closest chunks

# Read .env and put GEMINI_API_KEY and GEMINI_MODEL into the environment
load_dotenv()


def get_client():
    """Create the Gemini client using the key from .env."""

    # Read the key; os.getenv returns None if it is missing
    api_key = os.getenv("GEMINI_API_KEY")

    # Stop early with a clear message if the key is missing
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found. Check your .env file.")

    # Create and return the client
    return genai.Client(api_key=api_key)


def build_prompt(question, chunks):
    """Combine rules + retrieved chunks + question into one prompt text."""

    # This list will hold each chunk written in a labeled format
    parts = []

    # Go through every retrieved chunk
    for c in chunks:
        # Label each chunk with its file and page so the LLM can cite it
        parts.append(f"[Source: {c['source']}, page {c['page']}]\n{c['text']}")

    # Join all chunks with a blank line between them
    context = "\n\n".join(parts)

    # The final prompt: rules first, then context, then the question
    prompt = f"""You are a helpful assistant. Answer the question using ONLY the context below.

Rules:
- If the answer is not in the context, reply with ONLY this sentence and nothing else: "I could not find this in the document."
- Otherwise, answer using ONLY the context. Do not use any outside knowledge.
- Keep the answer short and clear.
- At the end of a found answer, mention the source page number(s) you used.

CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

    # Give the prompt back
    return prompt


def answer_question(question, k=5):
    """Full RAG flow: retrieve chunks, ask Gemini, return answer + sources."""

    # Step 1 (Retrieve): find the k most relevant chunks
    chunks = search(question, k=k)

    # Step 2 (Augment): build the prompt with those chunks
    prompt = build_prompt(question, chunks)

    # Create the Gemini client
    client = get_client()

    # Read the model name from .env; use flash-lite if it is not set
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    # Step 3 (Generate): ask Gemini to answer
    response = client.models.generate_content(model=model, contents=prompt)

    # Collect which chunks were used, so the user can verify the answer
    sources = [
        {"source": c["source"], "page": c["page"], "chunk_id": c["id"], "score": round(c["score"], 3)}
        for c in chunks
    ]

    # response.text can be None if nothing came back, so we add a fallback
    return {"answer": response.text or "No answer was returned.", "sources": sources}


# This block runs only when we run this file directly (for testing)
if __name__ == "__main__":
    # The question is the first thing typed after the script name
    question = sys.argv[1]

    try:
        # Run the full RAG flow
        result = answer_question(question)

        # Print the answer
        print("\nANSWER:")
        print(result["answer"])

        # Print the chunks that were sent to Gemini
        print("\nSOURCES USED:")
        for s in result["sources"]:
            print(f"- {s['source']} | page {s['page']} | chunk {s['chunk_id']} | score {s['score']}")

    except Exception as e:
        # Show the real error so we can fix it
        print("Something went wrong:", e)