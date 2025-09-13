from celery import shared_task
import requests

@shared_task
def ask_learnflow_ai(query):
    response = requests.post("http://localhost:8000/api/chat", json={"query": query})
    return response.json().get("answer")