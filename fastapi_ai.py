from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import logging

app = FastAPI()

# ─── CORS Setup ───────────────────────────────────────────────────────────────
# Allows cross-origin requests from any domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Base Context ─────────────────────────────────────────────────────────────
context = (
    "LearnFlow AI is a platform designed to empower educators and learners across Africa. "
    "It supports joyful onboarding, secure resource sharing, and culturally resonant feedback."
)

# ─── Feedback Store (Temporary) ───────────────────────────────────────────────
feedback_log = []

# ─── Lazy Model Loader ────────────────────────────────────────────────────────
# This function loads the model on the first request.
# We're using a more lightweight QA model to fit within the memory
# limitations of free-tier hosting services like Render (typically ~512MB RAM).
# The 'distilbert-base-uncased-distilled-squad' model is fine-tuned
# specifically for extractive question answering and is smaller than the multilingual version.
def get_qa_pipeline():
    # Load model only when needed
    return pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")

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
        try:
            qa = get_qa_pipeline()
            result = qa(question=query, context=context)
            return {"answer": result["answer"]}
        except Exception as e:
            # Added basic error handling to prevent the app from crashing on model load errors.
            logging.error(f"Error processing question-answering request: {e}")
            return {"answer": "I'm sorry, I am currently unable to answer that question."}

# ─── Feedback Endpoint ────────────────────────────────────────────────────────
@app.post("/api/feedback")
async def feedback(request: Request):
    body = await request.json()
    feedback_text = body.get("feedback", "")
    if feedback_text:
        feedback_log.append(feedback_text)
        logging.info(f"New feedback received: {feedback_text}")
    return {"status": "received"}
