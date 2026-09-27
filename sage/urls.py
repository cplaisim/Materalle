# sage/urls.py
from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt
from asgiref.sync import async_to_sync

app_name = 'sage'

urlpatterns = [
    path('', views.index, name='index'),
    path('chat/', views.sage_chat, name='chat'),
    path('interaction/', async_to_sync(views.sage_interaction), name='sage_interaction'),
   
    path('meal-planner/', views.meal_planner, name='meal_planner'),
    path('schedule/', views.schedule, name='schedule'),
    path('weekly-schedule/', views.weekly_schedule, name='weekly_schedule'),
    path('generate-weekly-schedule/', views.generate_weekly_schedule, name='generate_weekly_schedule'),
    path('apply-menu-to-schedule/', views.apply_menu_to_schedule, name='apply_menu_to_schedule'),
    path('rate-weekly-activity/', views.rate_weekly_activity, name='rate_weekly_activity'),
    path('record-meal/', views.record_meal, name='record_meal'),
    path('generate-menu/', views.generate_menu, name='generate_menu'),
    path('current-menu/', views.current_menu, name='current_menu'),
    path('add-dish/', views.add_dish, name='add_dish'),
    path('upload-grocery-list/', views.upload_grocery_list, name='upload_grocery_list'),
    path('grocery-list/', views.grocery_list, name='grocery_list'),
    path('add-item/', views.add_item, name='add_item'),
    path('remove-items/', views.remove_items, name="remove_items"),
    path('clear-grocery-list/', views.clear_grocery_list, name='clear_grocery_list'),
    path('resolve-conflicts/', views.resolve_grocery_conflicts, name='resolve_conflicts'),
 
    path('upload-documents/', views.upload_documents, name='upload_documents'),
    path('upload-grocery-documents/', async_to_sync(views.upload_grocery_documents), name='upload_grocery_documents'),
    path('delete-file/<int:file_id>/', views.delete_file, name='delete_file'),
      
    
    path('dashboard/', views.sage_dashboard, name='dashboard'),
    path('activity-dashboard/', views.activity_dashboard, name='activity_dashboard'),
    path("generate-attendance/", views.generate_attendance, name="generate_attendance"),
    #path("attendance-report/", views.attendance_report, name="attendance_report"),
    #path("generate-report/", views.generate_report, name="generate_report"),
    #path ("download_menu/", views.download_menu, name="download_menu"),
    path('search/', views.search, name='search'),
]