from django.urls import path
from . import views

urlpatterns = [
    path("", views.chat_view, name="chat"),
    path("results/", views.results_view, name="results"),
]
