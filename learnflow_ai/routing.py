from django.urls import path

from .consumers import LiveTeacherConsumer

websocket_urlpatterns = [
    path('ws/live-teacher/', LiveTeacherConsumer.as_asgi()),
]
