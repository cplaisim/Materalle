from django.urls import path

from .views import HealthCheckView, OllamaTestView
from .auth_views import RegisterView, LoginView, RefreshTokenView, MeView
from .agent_views import GraceChatView, PatienceChatView, SagesseChatView
from .session_views import SessionListView, SessionDetailView
from .grocery_views import GroceryUploadView, GroceryListView
from .children_views import ChildrenListView, ChildDashboardView, CheckInOutView, AttendanceListView, ChildActivitiesView, GenerateReportView
from .dashboard_views import ActivityDashboardView, RateActivityView, WeeklyScheduleView
from .enroll_views import EnrollChildView
from .settings_views import LLMSettingsView, SystemHealthView

urlpatterns = [
    # Health
    path("", HealthCheckView.as_view(), name="api-health"),
    path("test/ollama/", OllamaTestView.as_view(), name="api-test-ollama"),

    # Auth
    path("auth/register/", RegisterView.as_view(), name="api-register"),
    path("auth/login/", LoginView.as_view(), name="api-login"),
    path("auth/refresh/", RefreshTokenView.as_view(), name="api-refresh"),
    path("auth/me/", MeView.as_view(), name="api-me"),

    # Agent chat
    path("agents/grace/chat/", GraceChatView.as_view(), name="api-grace-chat"),
    path("agents/patience/chat/", PatienceChatView.as_view(), name="api-patience-chat"),
    path("agents/sagesse/chat/", SagesseChatView.as_view(), name="api-sagesse-chat"),

    # Sessions
    path("sessions/", SessionListView.as_view(), name="api-sessions"),
    path("sessions/<int:pk>/", SessionDetailView.as_view(), name="api-session-detail"),

    # Grocery
    path("grocery/", GroceryListView.as_view(), name="api-grocery-list"),
    path("grocery/upload/", GroceryUploadView.as_view(), name="api-grocery-upload"),

    # Enroll
    path("enroll/", EnrollChildView.as_view(), name="api-enroll"),

    # Children
    path("children/", ChildrenListView.as_view(), name="api-children-list"),
    path("children/<int:child_id>/", ChildDashboardView.as_view(), name="api-child-dashboard"),
    path("children/<int:child_id>/summary/", GenerateReportView.as_view(), name="api-generate-report"),
    path("children/<int:child_id>/activities/<str:agent>/", ChildActivitiesView.as_view(), name="api-child-activities"),
    path("children/<int:child_id>/<str:action>/", CheckInOutView.as_view(), name="api-check-in-out"),
    path("attendance/", AttendanceListView.as_view(), name="api-attendance"),

    # Dashboard & Schedule
    path("dashboard/", ActivityDashboardView.as_view(), name="api-activity-dashboard"),
    path("dashboard/rate/", RateActivityView.as_view(), name="api-rate-activity"),
    path("schedule/weekly/", WeeklyScheduleView.as_view(), name="api-weekly-schedule"),

    # Settings & Health
    path("settings/llm/", LLMSettingsView.as_view(), name="api-llm-settings"),
    path("settings/health/", SystemHealthView.as_view(), name="api-system-health"),
]