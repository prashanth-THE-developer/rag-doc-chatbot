import { useState, useRef, useEffect } from "react";   // React tools for state and effects
import "./App.css";                                    // our styles

// Address of our FastAPI server (it must be running)
const API_URL = "http://127.0.0.1:8000";

// Quick questions shown as clickable chips
const SUGGESTIONS = [
  "Summarize this document",
  "What skills are mentioned?",
  "Which projects are listed?",
  "What is the education background?",
];

// Small helper that wraps any icon shape in the same SVG settings
const Svg = ({ children }) => (
  <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">{children}</svg>
);

// All icons we use (simple SVG paths, no library needed)
const Icons = {
  Upload: () => <Svg><path d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v3a1 1 0 001 1h14a1 1 0 001-1v-3" /></Svg>,
  File: () => <Svg><path d="M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8l-5-5z" /><path d="M14 3v5h5" /></Svg>,
  Send: () => <Svg><path d="M22 2L11 13" /><path d="M22 2l-7 20-4-9-9-4 20-7z" /></Svg>,
  Copy: () => <Svg><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 012-2h9" /></Svg>,
  Check: () => <Svg><path d="M5 13l4 4L19 7" /></Svg>,
  Sparkle: () => <Svg><path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z" /></Svg>,
};

function App() {
  const [file, setFile] = useState(null);              // the PDF the user picked
  const [dragging, setDragging] = useState(false);     // true while a file is dragged over the box
  const [uploading, setUploading] = useState(false);   // true while uploading
  const [status, setStatus] = useState({ type: "", text: "" });  // upload message + its style
  const [doc, setDoc] = useState(null);                // info about the indexed document
  const [question, setQuestion] = useState("");        // text in the question box
  const [messages, setMessages] = useState([]);        // all chat messages
  const [asking, setAsking] = useState(false);         // true while waiting for an answer
  const [copied, setCopied] = useState(null);          // index of the message just copied

  const chatRef = useRef(null);                        // the scrolling chat area

  // Scroll only the chat box (not the whole page) to the newest message
  useEffect(() => {
    chatRef.current?.scrollTo({ top: chatRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, asking]);

  // Accept a file only if it is a PDF
  const pickFile = (f) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setStatus({ type: "error", text: "Only PDF files are allowed." });
      return;
    }
    setFile(f);
    setStatus({ type: "", text: "" });
  };

  // Handle a file dropped onto the drop zone
  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    pickFile(e.dataTransfer.files[0]);
  };

  // Send the PDF to the backend
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setStatus({ type: "info", text: "Reading, chunking and embedding your PDF..." });
    try {
      const formData = new FormData();
      formData.append("file", file);                   // key "file" must match the backend
      const res = await fetch(`${API_URL}/upload`, { method: "POST", body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Upload failed");
      setDoc({ name: data.file, pages: data.pages, chunks: data.chunks });
      setStatus({ type: "success", text: "Indexed successfully!" });
      setMessages([]);                                 // start a fresh chat for the new document
    } catch (err) {
      setStatus({ type: "error", text: err.message });
    } finally {
      setUploading(false);
    }
  };

  // Send a question; "text" is used when a suggestion chip is clicked
  const ask = async (text) => {
    const q = (text ?? question).trim();
    if (!q || asking) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setQuestion("");
    setAsking(true);

    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Request failed");

      // Hide page info when the answer was "not found"
      const notFound = data.answer.toLowerCase().includes("could not find this in the document");
      const pages = notFound ? [] : [...new Set(data.sources.map((s) => s.page))];
      setMessages((prev) => [...prev, { role: "bot", text: data.answer, pages }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "bot", text: "Error: " + err.message, pages: [] }]);
    } finally {
      setAsking(false);
    }
  };

  // Copy an answer to the clipboard and show "Copied" for 1.5 seconds
  const copyText = async (text, i) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(i);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* clipboard may be blocked; ignore */
    }
  };

  return (
    <div className="page">
      {/* Animated background */}
      <div className="orb orb1" />
      <div className="orb orb2" />
      <div className="grid-bg" />

      {/* Top navigation bar */}
      <header className="nav">
        <div className="brand">
          <div className="logo"><Icons.Sparkle /></div>
          DocuMind AI
        </div>
        <div className="badge">React · FastAPI · FAISS · Gemini</div>
      </header>

      <main className="container">
        {/* Hero heading */}
        <section className="hero">
          <h1>Chat with your <span className="gradient-text">documents</span></h1>
          <p>Upload a PDF and get accurate, source-backed answers powered by Retrieval-Augmented Generation.</p>
        </section>

        <div className="layout">
          {/* Left panel: upload */}
          <aside className="panel">
            <h2 className="panel-title">Your document</h2>

            <div className="steps">
              <div className={`step ${doc ? "done" : "active"}`}><span>{doc ? "✓" : "1"}</span>Upload</div>
              <div className={`step ${doc ? "active" : ""}`}><span>2</span>Ask</div>
            </div>

            <label
              className={`dropzone ${dragging ? "dragging" : ""}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
            >
              <input
                type="file"
                accept=".pdf"
                hidden
                onClick={(e) => (e.target.value = null)}
                onChange={(e) => pickFile(e.target.files[0])}
              />
              <Icons.Upload />
              <strong>Drop your PDF here</strong>
              <small>or click to browse</small>
            </label>

            {file && (
              <div className="file-chip">
                <Icons.File />
                <span>{file.name}</span>
              </div>
            )}

            <button className="btn full" onClick={handleUpload} disabled={!file || uploading}>
              {uploading ? <><div className="spinner" /> Indexing...</> : <><Icons.Upload /> Upload and index</>}
            </button>

            {status.text && (
              <p className={`status ${status.type}`}>
                {status.type === "success" && <Icons.Check />}
                {status.text}
              </p>
            )}

            {doc && (
              <div className="doc-card">
                <b>{doc.name}</b>
                <small>{doc.pages} page(s) · {doc.chunks} chunks indexed</small>
              </div>
            )}
          </aside>

          {/* Right panel: chat */}
          <section className="panel chat-panel">
            <h2 className="panel-title">
              Conversation
              {messages.length > 0 && (
                <button className="ghost" onClick={() => setMessages([])}>Clear chat</button>
              )}
            </h2>

            <div className="chat" ref={chatRef}>
              {messages.length === 0 && (
                <div className="empty">
                  <div className="big-icon"><Icons.Sparkle /></div>
                  <h3>{doc ? "Ready! Ask anything" : "Upload a PDF to begin"}</h3>
                  <p>{doc ? "Try one of these questions:" : "Then ask questions about it here."}</p>
                  {doc && (
                    <div className="chips">
                      {SUGGESTIONS.map((s) => (
                        <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {messages.map((m, i) => (
                <div key={i} className={`msg ${m.role}`}>
                  <div className="avatar">{m.role === "user" ? "You" : <Icons.Sparkle />}</div>
                  <div className="msg-body">
                    <div className="bubble">{m.text}</div>
                    {m.role === "bot" && (
                      <div className="meta">
                        {m.pages && m.pages.length > 0 && <span className="tag">Pages searched: {m.pages.join(", ")}</span>}
                        <button className="copy" onClick={() => copyText(m.text, i)}>
                          {copied === i ? <><Icons.Check /> Copied</> : <><Icons.Copy /> Copy</>}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}

              {asking && (
                <div className="msg bot">
                  <div className="avatar"><Icons.Sparkle /></div>
                  <div className="bubble typing"><i /><i /><i /></div>
                </div>
              )}
            </div>

            <div className="ask-row">
              <input
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && ask()}
                placeholder="Ask a question about your document..."
              />
              <button className="btn" onClick={() => ask()} disabled={asking || !question.trim()}>
                <Icons.Send /> Ask
              </button>
            </div>
          </section>
        </div>
      </main>

      <footer className="footer">Built with React, FastAPI, FAISS and Gemini</footer>
    </div>
  );
}

export default App;