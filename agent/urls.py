from django.urls import path
from . import views

app_name = 'agent'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('conversation/<int:conversation_id>/', views.chat_view, name='conversation'),
    path('send_message/', views.send_message, name='send_message'),
]
