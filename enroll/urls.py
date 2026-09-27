from django.urls import path
from . import views

app_name = 'enroll'

urlpatterns = [
    path("", views.index, name="index"),
    path("rate_student/",views.rate_student,name="rate_student"),
    path('check-in-out/<int:child_id>/<str:action>/', views.check_in_out, name='check_in_out'),
    path('attendance/', views.attendance, name='attendance'),
    path('participants/', views.participants, name='participants'),
    path('dashboard/', views.dashboard, name='dashboard_activity'),
    path('child/<int:child_id>/', views.child_dashboard, name='child_dashboard'),
    path('child/<int:child_id>/delete/', views.delete_child, name='delete_child'),
    path('child/<int:child_id>/summary/', views.generate_child_summary, name='generate_child_summary'),
    path('child/<int:child_id>/activities/<str:agent>/', views.child_agent_activities, name='child_agent_activities'),
    path('schedule-activity/', views.schedule_activity, name='schedule_activity'),
    path('child/<int:child_id>/calendar/', views.child_calendar, name='child_calendar'),
]