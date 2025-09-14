import io
import json
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import logging
import uvicorn
from typing import Dict, Any, List

# ─── Configure Logging ────────────────────────────────────────────────────────
# This sets up basic logging to show INFO level messages and above.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ─── File-Based Persistence Setup ─────────────────────────────────────────────
# This is a temporary solution for persistence. For production, consider using
# a proper database like PostgreSQL, MongoDB, or Firestore.
FEEDBACK_FILE = "feedback_log.json"

def load_feedback() -> List[str]:
    """Loads feedback from the JSON file."""
    try:
        with open(FEEDBACK_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return an empty list if the file doesn't exist or is invalid.
        logging.warning(f"Feedback file '{FEEDBACK_FILE}' not found or is empty/invalid. Starting with an empty log.")
        return []

def save_feedback(feedback_list: List[str]):
    """Saves feedback to the JSON file."""
    try:
        with open(FEEDBACK_FILE, "w") as f:
            json.dump(feedback_list, f)
    except IOError as e:
        logging.error(f"Error saving feedback to file: {e}")

# ─── FastAPI Application Initialization ───────────────────────────────────────
app = FastAPI(
    title="LearnFlow AI Chat API",
    description="An API for a question-answering chatbot for the LearnFlow AI platform.",
    version="1.0.0"
)

# Initialize feedback log from file
FEEDBACK_LOG: list[str] = load_feedback()

# ─── CORS Middleware Setup ────────────────────────────────────────────────────
# Allows cross-origin requests from any domain, which is useful for development
# and for a separate frontend application.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Application Context ──────────────────────────────────────────────────────
# This context provides the factual basis for the chatbot's answers.
# In a real-world scenario, this would likely be fetched from a dynamic
# knowledge base or a database.
CONTEXT = (
    "LearnFlow AI is a platform designed to empower educators and learners across Africa. "
    "It supports joyful onboarding, secure resource sharing, and culturally resonant feedback."
)

# ─── Lazy Model Loading ───────────────────────────────────────────────────────
# The model is loaded only when the first request to the chat endpoint is made.
# This saves memory and speeds up application startup, which is critical for
# platforms with limited resources (e.g., free-tier cloud hosting).
# The 'distilbert-base-uncased-distilled-squad' model is a lightweight and
# effective choice for extractive question-answering.
qa_pipeline = None

def get_qa_pipeline():
    """Loads the question-answering model if it hasn't been loaded yet."""
    global qa_pipeline
    if qa_pipeline is None:
        logging.info("Loading question-answering model...")
        qa_pipeline = pipeline("question-answering", model="distilbert-base-uncased-distilled-squad")
        logging.info("Model loaded successfully.")
    return qa_pipeline

# ─── API Endpoints ────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=Dict[str, str])
async def chat(request: Request) -> Dict[str, str]:
    """
    Handles user queries by routing based on intent or using a
    question-answering model.
    """
    try:
        body: Dict[str, Any] = await request.json()
        query: str = body.get("query", "").strip().lower()

        if not query:
            return {"answer": "Please provide a query."}

        # Simple keyword-based intent routing.
        if "upload" in query:
            return {"answer": "To upload content, visit your dashboard and click 'Add Resource'."}
        elif "verify" in query:
            return {"answer": "Teacher verification is handled securely—check your profile settings."}
        else:
            # Use the QA model for general questions.
            qa = get_qa_pipeline()
            result = qa(question=query, context=CONTEXT)
            return {"answer": result["answer"]}
            
    except Exception as e:
        logging.error(f"Error processing question-answering request: {e}", exc_info=True)
        return {"answer": "I'm sorry, I am currently unable to answer that question. Please try again later."}

@app.post("/api/feedback", response_model=Dict[str, str])
async def feedback(request: Request) -> Dict[str, str]:
    """
    Receives and logs user feedback.
    """
    try:
        body: Dict[str, Any] = await request.json()
        feedback_text: str = body.get("feedback", "").strip()
        
        if feedback_text:
            FEEDBACK_LOG.append(feedback_text)
            save_feedback(FEEDBACK_LOG)
            logging.info(f"New feedback received: '{feedback_text}'")
        
        return {"status": "received"}

    except Exception as e:
        logging.error(f"Error receiving feedback: {e}", exc_info=True)
        return {"status": "error", "message": "Failed to process feedback."}

# ─── Main Application Runner ──────────────────────────────────────────────────
# This block allows the script to be run directly using 'python main.py'
# The app will be served by Uvicorn.
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
