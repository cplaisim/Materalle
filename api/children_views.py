from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from enroll.models import Child, AttendanceLog, StudentRating
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .response import api_response


class ChildrenListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        children = Child.objects.all().order_by('child_name')
        data = []
        for child in children:
            data.append({
                'child_id': child.child_id,
                'child_name': child.child_name,
                'date_of_birth': str(child.date_of_birth) if child.date_of_birth else '',
                'is_checked_in': child.is_checked_in,
                'allergies': child.child_allergies or '',
                'parent_name': child.parent_name or '',
                'parent_email': child.parent_email or '',
                'parent_phone': child.parent_phone or '',
            })
        return api_response(data=data)


class ChildDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, child_id):
        try:
            child = Child.objects.get(child_id=child_id)
        except Child.DoesNotExist:
            return api_response(message="Child not found.", status_code=status.HTTP_404_NOT_FOUND)

        def get_agent_stats(child_obj, page_type):
            ratings = StudentRating.objects.filter(child=child_obj)
            likes = ratings.filter(rating__gte=3).count()
            normals = ratings.filter(rating=2).count()
            dislikes = ratings.filter(rating__lte=1).count()
            total = ratings.count()
            return {'likes': likes, 'normals': normals, 'dislikes': dislikes, 'total': total}

        logs = AttendanceLog.objects.filter(child=child).order_by('-check_in')[:10]
        attendance = [{
            'date': str(log.check_in.date()) if log.check_in else '',
            'check_in': log.check_in.strftime('%I:%M %p') if log.check_in else '',
            'check_out': log.check_out.strftime('%I:%M %p') if log.check_out else None,
        } for log in logs]

        data = {
            'child_id': child.child_id,
            'child_name': child.child_name,
            'date_of_birth': str(child.date_of_birth) if child.date_of_birth else '',
            'is_checked_in': child.is_checked_in,
            'allergies': child.child_allergies or '',
            'parent_name': child.parent_name or '',
            'parent_email': child.parent_email or '',
            'parent_phone': child.parent_phone or '',
            'sage_stats': get_agent_stats(child, 'sage'),
            'grace_stats': get_agent_stats(child, 'grace'),
            'patience_stats': get_agent_stats(child, 'patience'),
            'recent_attendance': attendance,
        }
        return api_response(data=data)


class CheckInOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, child_id, action):
        try:
            child = Child.objects.get(child_id=child_id)
        except Child.DoesNotExist:
            return api_response(message="Child not found.", status_code=status.HTTP_404_NOT_FOUND)

        now = timezone.now()

        if action == 'in':
            child.is_checked_in = True
            child.check_in_time = now
            child.save()
            AttendanceLog.objects.create(child=child, check_in=now, recorded_by=request.user)
            return api_response(data={'is_checked_in': True}, message='Checked in.')
        elif action == 'out':
            child.is_checked_in = False
            child.save()
            log = AttendanceLog.objects.filter(child=child, check_out__isnull=True).last()
            if log:
                log.check_out = now
                log.save()
            return api_response(data={'is_checked_in': False}, message='Checked out.')
        else:
            return api_response(message="Invalid action.", status_code=status.HTTP_400_BAD_REQUEST)


class ChildActivitiesView(APIView):
    """Return activities for a child filtered by agent (sage, grace, patience)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, child_id, agent):
        try:
            child = Child.objects.get(child_id=child_id)
        except Child.DoesNotExist:
            return api_response(message="Child not found.", status_code=status.HTTP_404_NOT_FOUND)

        agent = agent.lower()
        if agent not in ('sage', 'grace', 'patience'):
            return api_response(message="Invalid agent.", status_code=status.HTTP_400_BAD_REQUEST)

        from sage.models import Dish, WeeklyPlanEntry
        from grace.models import SocialCurriculum
        from patience.models import MotorCurriculum

        RATING_LABELS = {3: 'Liked', 2: 'Okay', 1: 'Disliked'}
        activities = []

        ratings = StudentRating.objects.filter(child=child)

        # Weekly plan entries for this agent
        weekly_ct = ContentType.objects.get_for_model(WeeklyPlanEntry)
        for r in ratings.filter(content_type=weekly_ct):
            try:
                entry = WeeklyPlanEntry.objects.get(pk=r.object_id)
                if entry.agent == agent:
                    activities.append({
                        'id': r.id,
                        'title': entry.title,
                        'description': entry.description[:200] if entry.description else '',
                        'activity_type': entry.activity_type or '',
                        'agent': agent,
                        'date': '',
                        'rating': r.rating,
                        'rating_label': RATING_LABELS.get(r.rating, 'Unrated'),
                    })
            except WeeklyPlanEntry.DoesNotExist:
                pass

        # Agent-specific curriculum entries
        if agent == 'grace':
            ct = ContentType.objects.get_for_model(SocialCurriculum)
            for r in ratings.filter(content_type=ct):
                try:
                    entry = SocialCurriculum.objects.get(pk=r.object_id)
                    activities.append({
                        'id': r.id,
                        'title': entry.title,
                        'description': entry.description[:200] if entry.description else '',
                        'activity_type': entry.activity_type or '',
                        'agent': 'grace',
                        'date': '',
                        'rating': r.rating,
                        'rating_label': RATING_LABELS.get(r.rating, 'Unrated'),
                    })
                except SocialCurriculum.DoesNotExist:
                    pass
        elif agent == 'patience':
            ct = ContentType.objects.get_for_model(MotorCurriculum)
            for r in ratings.filter(content_type=ct):
                try:
                    entry = MotorCurriculum.objects.get(pk=r.object_id)
                    activities.append({
                        'id': r.id,
                        'title': entry.title,
                        'description': entry.description[:200] if entry.description else '',
                        'activity_type': entry.activity_type or '',
                        'agent': 'patience',
                        'date': '',
                        'rating': r.rating,
                        'rating_label': RATING_LABELS.get(r.rating, 'Unrated'),
                    })
                except MotorCurriculum.DoesNotExist:
                    pass
        elif agent == 'sage':
            ct = ContentType.objects.get_for_model(Dish)
            for r in ratings.filter(content_type=ct):
                try:
                    entry = Dish.objects.get(pk=r.object_id)
                    activities.append({
                        'id': r.id,
                        'title': entry.title or 'Meal',
                        'description': '',
                        'activity_type': 'meal',
                        'agent': 'sage',
                        'date': '',
                        'rating': r.rating,
                        'rating_label': RATING_LABELS.get(r.rating, 'Unrated'),
                    })
                except Dish.DoesNotExist:
                    pass

        return api_response(data=activities)


class GenerateReportView(APIView):
    """Generate a developmental summary report for a child using LLM."""
    permission_classes = [IsAuthenticated]

    def post(self, request, child_id):
        try:
            child = Child.objects.get(child_id=child_id)
        except Child.DoesNotExist:
            return api_response(message="Child not found.", status_code=status.HTTP_404_NOT_FOUND)

        from materalleapp.agent_base import get_anthropic_response
        from sage.models import Dish, WeeklyPlanEntry
        from grace.models import SocialCurriculum
        from patience.models import MotorCurriculum
        from datetime import date as _date

        ratings = StudentRating.objects.filter(child=child)
        weekly_ct = ContentType.objects.get_for_model(WeeklyPlanEntry)

        RATING_WORDS = {3: 'liked', 2: 'neutral', 1: 'disliked'}

        agent_data = {'sage': [], 'grace': [], 'patience': []}

        # Weekly plan entries
        for r in ratings.filter(content_type=weekly_ct):
            try:
                entry = WeeklyPlanEntry.objects.get(pk=r.object_id)
                agent_data[entry.agent].append(
                    f"- {entry.title} ({entry.activity_type}): {RATING_WORDS.get(r.rating, 'unrated')} — {entry.description[:100]}"
                )
            except WeeklyPlanEntry.DoesNotExist:
                pass

        # Grace curriculum
        grace_ct = ContentType.objects.get_for_model(SocialCurriculum)
        for r in ratings.filter(content_type=grace_ct):
            try:
                entry = SocialCurriculum.objects.get(pk=r.object_id)
                agent_data['grace'].append(
                    f"- {entry.title} ({entry.activity_type}): {RATING_WORDS.get(r.rating, 'unrated')} — {entry.description[:100]}"
                )
            except SocialCurriculum.DoesNotExist:
                pass

        # Patience curriculum
        patience_ct = ContentType.objects.get_for_model(MotorCurriculum)
        for r in ratings.filter(content_type=patience_ct):
            try:
                entry = MotorCurriculum.objects.get(pk=r.object_id)
                agent_data['patience'].append(
                    f"- {entry.title} ({entry.activity_type}): {RATING_WORDS.get(r.rating, 'unrated')} — {entry.description[:100]}"
                )
            except MotorCurriculum.DoesNotExist:
                pass

        # Sage meals
        sage_ct = ContentType.objects.get_for_model(Dish)
        for r in ratings.filter(content_type=sage_ct):
            try:
                entry = Dish.objects.get(pk=r.object_id)
                agent_data['sage'].append(
                    f"- {entry.title or 'Meal'}: {RATING_WORDS.get(r.rating, 'unrated')}"
                )
            except Dish.DoesNotExist:
                pass

        # Calculate age
        today = _date.today()
        if child.date_of_birth:
            age_months = (today.year - child.date_of_birth.year) * 12 + (today.month - child.date_of_birth.month)
            age_str = f"{age_months // 12} years, {age_months % 12} months"
        else:
            age_str = "Unknown"

        # Build LLM prompt
        sections = []
        if agent_data['sage']:
            sections.append("**Sage (Nutrition & Wellness):**\n" + "\n".join(agent_data['sage'][:15]))
        if agent_data['grace']:
            sections.append("**Grace (Social-Emotional Development):**\n" + "\n".join(agent_data['grace'][:15]))
        if agent_data['patience']:
            sections.append("**Patience (Motor & Physical Development):**\n" + "\n".join(agent_data['patience'][:15]))

        if not sections:
            return api_response(data={
                'summary': (
                    'Not enough activity data to generate a developmental summary yet. '
                    'Continue scheduling and rating activities to build this child\'s profile.'
                )
            })

        activity_text = "\n\n".join(sections)

        prompt = (
            f"You are a child development specialist preparing a developmental milestone report "
            f"for a parent or caretaker to share at a pediatric checkup.\n\n"
            f"**Child:** {child.child_name}\n"
            f"**Age:** {age_str}\n"
            f"**Date of Birth:** {child.date_of_birth}\n"
            f"**Allergies:** {child.child_allergies or 'None reported'}\n\n"
            f"Below are the child's recent activities across three developmental domains, "
            f"along with whether the child liked, was neutral, or disliked each activity:\n\n"
            f"{activity_text}\n\n"
            f"Based on this data, write a concise developmental summary organized into these sections:\n\n"
            f"1. **Nutrition & Wellness** (Sage)\n"
            f"2. **Social-Emotional Development** (Grace)\n"
            f"3. **Motor & Physical Development** (Patience)\n"
            f"4. **Developmental Milestones** — based on age ({age_str})\n"
            f"5. **Recommendations for Parent/Caretaker**\n\n"
            f"Keep the tone warm, supportive, and professional."
        )

        try:
            summary = get_anthropic_response(
                messages=[{"role": "user", "content": prompt}],
                system_prompt=(
                    "You are an early childhood development specialist. "
                    "Write clear, evidence-based developmental summaries suitable for medical checkup discussions."
                ),
                max_tokens=2048,
            )
            return api_response(data={'summary': summary})
        except Exception as e:
            return api_response(
                message=f"Report generation failed: {str(e)}",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AttendanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        logs = AttendanceLog.objects.filter(
            check_in__date=today
        ).select_related('child').order_by('-check_in')
        data = [{
            'id': log.id,
            'child_id': log.child.child_id,
            'child_name': log.child.child_name,
            'check_in': log.check_in.strftime('%I:%M %p') if log.check_in else '',
            'check_out': log.check_out.strftime('%I:%M %p') if log.check_out else None,
            'date': str(log.check_in.date()) if log.check_in else '',
        } for log in logs]
        return api_response(data=data)
