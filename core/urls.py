from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('discover/', views.home, name='home'),
    path('matches/', views.matches_list, name='matches_list'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('register/', views.register, name='register'),
    path('like/<int:user_id>/', views.like_user, name='like_user'),
    path('skip/<int:user_id>/', views.skip_user, name='skip_user'),

    # CHAT SYSTEM PATHS
    path('chat/<str:username>/', views.chat_room, name='chat_room'),
    path('chat/<str:username>/send/', views.send_message, name='send_message'),
    path('chat/<str:username>/get/', views.get_messages, name='get_messages'),
]