from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from transformers import pipeline
import uvicorn
import os

app = FastAPI()

# Allow Django frontend to access FastAPI endpoints
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your Django domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load multilingual QA model
qa_pipeline = pipeline("question-answering", model="distilbert-base-multilingual-cased")

# Base context (can be expanded per language)
context = """
LearnFlow AI is a platform designed to empower educators and learners across Africa.
It supports joyful onboarding, secure resource sharing, and culturally resonant feedback.
"""

# Feedback store (in-memory for now)
feedback_log = []

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
        result = qa_pipeline(question=query, context=context)
        return {"answer": result["answer"]}

@app.post("/api/feedback")
async def feedback(request: Request):
    body = await request.json()
    feedback_text = body.get("feedback", "")
    if feedback_text:
        feedback_log.append(feedback_text)
        print("New feedback received:", feedback_text)
    return {"status": "received"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)