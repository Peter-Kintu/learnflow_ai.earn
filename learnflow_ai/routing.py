from django.urls import path, re_path

from .consumers import LiveTeacherConsumer

websocket_urlpatterns = [
    re_path(r'^ws/live-teacher/?$', LiveTeacherConsumer.as_asgi()),
]
