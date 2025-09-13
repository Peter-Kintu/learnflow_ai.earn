from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
from decouple import config
import uvicorn
import logging
import os

app = FastAPI()

# ─── CORS Setup ───────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your Django domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Base Context ─────────────────────────────────────────────────────────────
context = """
LearnFlow AI is a platform designed to empower educators and learners across Africa.
It supports joyful onboarding, secure resource sharing, and culturally resonant feedback.
"""

# ─── Feedback Store (Temporary) ───────────────────────────────────────────────
feedback_log = []

# ─── Lazy Model Loader ────────────────────────────────────────────────────────
qa_pipeline = None

def get_qa_pipeline():
    global qa_pipeline
    if qa_pipeline is None:
        qa_pipeline = pipeline("question-answering", model="distilbert-base-multilingual-cased")
    return qa_pipeline

# ─── Chat Endpoint ────────────────────────────────────────────────────────────
@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    query = body.get("query", "").strip().lower()

    # Intent routing
    if "upload" in query:
        return {"answer": "To upload content, visit your dashboard and click 'Add Resource'."}
    elif "verify" in query:
        return {"answer": "Teacher verification is handled securely—check your profile settings."}
    else:
        qa = get_qa_pipeline()
        result = qa(question=query, context=context)
        return {"answer": result["answer"]}

# ─── Feedback Endpoint ────────────────────────────────────────────────────────
@app.post("/api/feedback")
async def feedback(request: Request):
    body = await request.json()
    feedback_text = body.get("feedback", "")
    if feedback_text:
        feedback_log.append(feedback_text)
        logging.info(f"New feedback received: {feedback_text}")
    return {"status": "received"}

# ─── Uvicorn Entrypoint (Optional for Local Dev) ──────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)