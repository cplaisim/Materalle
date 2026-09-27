from datetime import timedelta

from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from enroll.models import Child, StudentRating
from sage.models import WeeklyPlanEntry, Schedule

from .response import api_response


class ActivityDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        day_offset = int(request.GET.get('day', 0))
        today = timezone.now().date()
        # Week starts Monday
        monday = today - timedelta(days=today.weekday())
        selected = monday + timedelta(days=day_offset)

        # Day tabs
        day_tabs = []
        for i in range(5):
            d = monday + timedelta(days=i)
            day_tabs.append({
                'offset': i,
                'short': d.strftime('%a'),
                'date': d.strftime('%b %d'),
                'is_active': i == day_offset,
                'is_today': d == today,
            })

        # Activities for selected day
        entries = WeeklyPlanEntry.objects.filter(
            scheduled_date=selected,
            week_start_date=monday,
        ).order_by('start_time')

        children = Child.objects.filter(is_checked_in=True).order_by('child_name')
        children_data = [{'child_id': c.child_id, 'child_name': c.child_name} for c in children]

        activities = []
        for entry in entries:
            # Get ratings for this entry
            from django.contrib.contenttypes.models import ContentType
            ct = ContentType.objects.get_for_model(WeeklyPlanEntry)
            ratings = StudentRating.objects.filter(content_type=ct, object_id=entry.id)
            ratings_json = {}
            for r in ratings:
                ratings_json[str(r.child_id)] = {'rating': r.rating}

            activities.append({
                'id': entry.id,
                'title': entry.title,
                'description': entry.description or '',
                'activity_type': entry.activity_type or '',
                'agent': entry.agent,
                'start_time': entry.start_time.strftime('%I:%M %p') if entry.start_time else '',
                'child_ratings_json': ratings_json,
            })

        return api_response(data={
            'day_tabs': day_tabs,
            'all_activities': activities,
            'children': children_data,
            'has_schedule': len(activities) > 0,
            'selected_date': str(selected),
            'week_start': str(monday),
            'checked_in_count': children.count(),
        })


class RateActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        entry_id = request.data.get('entry_id')
        child_id = request.data.get('child_id')
        rating = request.data.get('rating')

        if not all([entry_id, child_id, rating]):
            return api_response(message="Missing fields.", status_code=status.HTTP_400_BAD_REQUEST)

        try:
            entry = WeeklyPlanEntry.objects.get(id=entry_id)
            child = Child.objects.get(child_id=child_id)
        except (WeeklyPlanEntry.DoesNotExist, Child.DoesNotExist):
            return api_response(message="Not found.", status_code=status.HTTP_404_NOT_FOUND)

        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(WeeklyPlanEntry)
        obj, created = StudentRating.objects.update_or_create(
            child=child,
            content_type=ct,
            object_id=entry.id,
            defaults={'rating': int(rating)},
        )
        return api_response(data={'success': True, 'rating': obj.rating}, message="Rating saved.")


class WeeklyScheduleView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        monday = today - timedelta(days=today.weekday())
        entries = WeeklyPlanEntry.objects.filter(
            week_start_date=monday,
        ).order_by('scheduled_date', 'start_time')

        data = [{
            'id': e.id,
            'title': e.title,
            'description': e.description or '',
            'agent': e.agent,
            'start_time': e.start_time.strftime('%I:%M %p') if e.start_time else '',
            'scheduled_date': str(e.scheduled_date),
            'activity_type': e.activity_type or '',
            'is_static': e.is_static,
        } for e in entries]

        return api_response(data=data)
