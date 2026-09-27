# grace/urls.py
from django.urls import path
from . import views

app_name = 'grace'


urlpatterns = [
    path('', views.index, name='index'),
    path('conversation/<int:conversation_id>/', views.chat_view, name='conversation'),
    path('send_message/', views.send_message, name='send_message'),
    path('get_conversation/<int:conversation_id>/', views.get_conversation, name='get_conversation'),
    path('handle_interaction/', views.handle_interaction, name='handle_interaction'),
    path('conversation/<int:conversation_id>/delete/', views.delete_conversation, name='delete_conversation'),
]