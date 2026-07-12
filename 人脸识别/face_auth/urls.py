from django.urls import path

from . import views

urlpatterns = [
    path('', views.auth_demo),
    path('register', views.register),
    path('login', views.login),
    path('logout', views.logout),
    path('user/profile/', views.current_user_profile),
    path('face_recognition', views.face_recognition),
    path('face_verify_one_to_one/', views.face_verify_one_to_one),
]
