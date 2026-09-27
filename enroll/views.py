# enroll/views.py
from django.shortcuts import render, redirect, get_object_or_404
from .forms import StudentEnrollmentForm, ChildForm, StudentRatingForm, AttendanceLogForm
from .models import Student, StudentRating, Child, AttendanceLog, ChildActivity
from sage.models import WeeklyPlanEntry
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.contrib.contenttypes.models import ContentType
from sage.models import Dish
from patience.models import MotorCurriculum
from grace.models import SocialCurriculum
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db import transaction
from datetime import date
import csv

from django.contrib.auth.models import User
from website.models import UserProfile
from materalleapp.user_utils import get_role, is_parent, is_staff_role

@login_required
def index(request):
    role = get_role(request.user)
    if request.method == "POST":
        if role not in ('ADMINISTRATOR', 'CAREGIVER'):
            messages.error(request, 'Only administrators and caregivers can enroll students.')
            return redirect('enroll:index')

        form = StudentEnrollmentForm(request.POST, request.FILES)
        if form.is_valid():
            student = form.save(commit=False)
            student.enrolled_by = request.user
            student.save()
            messages.success(request, 'Student enrolled successfully!')
            return redirect('enroll:child_dashboard', child_id=student.pk)
        else:
            messages.error(request, 'Please correct the errors in the form.')
    else:
        form = StudentEnrollmentForm()

    student_list = Student.objects.all()
    context = {
        "student_list": student_list,
        "form": form,
        "can_enroll": role in ('ADMINISTRATOR', 'CAREGIVER'),
    }
    return render(request, "enroll/index.html", context)

def rate_student(request):
    if request.method == "POST":
        page = request.POST.get("page")
        child_id = request.POST.get("child_id")
        rate_value = request.POST.get("rate_value")
        object_id = request.POST.get("object_id")

        child = Child.objects.get(child_id=child_id)

        if page == "sage":
            content_type = ContentType.objects.get_for_model(Dish)
        elif page == "patience":
            content_type = ContentType.objects.get_for_model(MotorCurriculum)
        elif page == "grace":
            content_type = ContentType.objects.get_for_model(SocialCurriculum)
        else:
            return JsonResponse({"status": "error", "message": "Invalid page type"}, status=400)

        if not object_id:
            return JsonResponse({"status": "error", "message": "No activity to rate yet. Send a chat message first."}, status=400)

        # Map string rate values to integers
        rate_map = {'like': 3, 'normal': 2, 'dislike': 1}
        try:
            rating_int = int(rate_value)
        except (ValueError, TypeError):
            rating_int = rate_map.get(rate_value, 2)

        rating_entry, created = StudentRating.objects.update_or_create(
            child=child,
            content_type=content_type,
            object_id=object_id,
            defaults={"rating": rating_int}
        )

        return JsonResponse({
            "status": "success",
            "message": "Rating submitted successfully!",
            "page": page,
            "child_id": child_id,
            "rate_value": rate_value
        })

    return JsonResponse({"status": "error", "message": "Invalid request method"}, status=400)

@login_required
def check_in_out(request, child_id, action):
    if request.method == 'POST':
        child = get_object_or_404(Child, child_id=child_id)
        now = timezone.now()
        
        if action == 'in':
            AttendanceLog.objects.create(
                child=child,
                check_in=now,
                recorded_by=request.user
            )
            child.is_checked_in = True
            child.check_in_time = now
        else:
            log = AttendanceLog.objects.filter(
                child=child,
                check_out__isnull=True
            ).first()
            if log:
                log.check_out = now
                log.save()
            child.is_checked_in = False
            child.check_in_time = None
        
        child.save()
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False})

@login_required
def attendance(request):
    students = Child.objects.all()
    context = {
        'students': students,
        'children': students,
        'checked_in_count': students.filter(is_checked_in=True).count(),
        'attendance_logs': AttendanceLog.objects.filter(
            check_in__date=timezone.now().date()
        ).order_by('-check_in')
    }
    return render(request, 'enroll/attendance.html', context)


@login_required
def child_dashboard(request, child_id):
    child = get_object_or_404(Child, child_id=child_id)
    ratings = StudentRating.objects.filter(child=child)

    # Map content types to app names
    sage_ct = ContentType.objects.get_for_model(Dish)
    patience_ct = ContentType.objects.get_for_model(MotorCurriculum)
    grace_ct = ContentType.objects.get_for_model(SocialCurriculum)
    weekly_ct = ContentType.objects.get_for_model(WeeklyPlanEntry)

    def summarize(qs):
        if not qs.exists():
            return {'count': 0, 'likes': 0, 'normals': 0, 'dislikes': 0}
        return {
            'count': qs.count(),
            'likes': qs.filter(rating__gte=3).count(),
            'normals': qs.filter(rating=2).count(),
            'dislikes': qs.filter(rating__lte=1).count(),
        }

    sage_ratings = ratings.filter(content_type=sage_ct)
    grace_ratings = ratings.filter(content_type=grace_ct)
    patience_ratings = ratings.filter(content_type=patience_ct)

    # Weekly schedule ratings by agent
    weekly_ratings = ratings.filter(content_type=weekly_ct)
    weekly_sage_ids = WeeklyPlanEntry.objects.filter(agent='sage').values_list('pk', flat=True)
    weekly_grace_ids = WeeklyPlanEntry.objects.filter(agent='grace').values_list('pk', flat=True)
    weekly_patience_ids = WeeklyPlanEntry.objects.filter(agent='patience').values_list('pk', flat=True)

    # Merge weekly ratings into agent totals
    sage_all = sage_ratings | weekly_ratings.filter(object_id__in=weekly_sage_ids)
    grace_all = grace_ratings | weekly_ratings.filter(object_id__in=weekly_grace_ids)
    patience_all = patience_ratings | weekly_ratings.filter(object_id__in=weekly_patience_ids)

    # Recent attendance logs
    recent_logs = AttendanceLog.objects.filter(child=child).order_by('-check_in')[:10]

    # All children for cycling navigation
    all_children = list(Child.objects.all().order_by('child_name').values_list('child_id', flat=True))
    current_idx = all_children.index(child.child_id) if child.child_id in all_children else 0
    prev_id = all_children[(current_idx - 1) % len(all_children)] if all_children else child_id
    next_id = all_children[(current_idx + 1) % len(all_children)] if all_children else child_id

    context = {
        'child': child,
        'sage': summarize(sage_all),
        'grace': summarize(grace_all),
        'patience': summarize(patience_all),
        'total_ratings': ratings.count(),
        'recent_logs': recent_logs,
        'prev_child_id': prev_id,
        'next_child_id': next_id,
        'child_index': current_idx + 1,
        'child_total': len(all_children),
    }
    return render(request, 'enroll/child_dashboard.html', context)

@login_required
def child_agent_activities(request, child_id, agent):
    """Show activities and ratings for a specific child filtered by agent."""
    child = get_object_or_404(Child, child_id=child_id)
    ratings = StudentRating.objects.filter(child=child)
    weekly_ct = ContentType.objects.get_for_model(WeeklyPlanEntry)

    RATING_LABELS = {3: '😄 Liked', 2: '😐 Okay', 1: '😞 Disliked'}
    AGENT_META = {
        'sage': {'label': 'Sage', 'subtitle': 'Nutrition & Meals', 'color': '#198754'},
        'grace': {'label': 'Grace', 'subtitle': 'Social-Emotional Development', 'color': '#d63384'},
        'patience': {'label': 'Patience', 'subtitle': 'Motor & Physical Development', 'color': '#0d6efd'},
    }
    meta = AGENT_META.get(agent, AGENT_META['sage'])

    activities = []

    # Weekly activities for this agent
    weekly_ratings = ratings.filter(content_type=weekly_ct)
    weekly_ids_rated = {r.object_id: r.rating for r in weekly_ratings}
    child_weekly = WeeklyPlanEntry.objects.filter(
        children=child, agent=agent
    ).order_by('-scheduled_date', 'start_time')
    for act in child_weekly:
        r = weekly_ids_rated.get(act.pk)
        activities.append({
            'date': act.scheduled_date,
            'title': act.title,
            'description': act.description,
            'activity_type': act.activity_type,
            'rating': r,
            'rating_label': RATING_LABELS.get(r, '—'),
        })

    # Curriculum entries for this agent
    if agent == 'grace':
        grace_ct = ContentType.objects.get_for_model(SocialCurriculum)
        for r in ratings.filter(content_type=grace_ct):
            try:
                entry = SocialCurriculum.objects.get(pk=r.object_id)
                activities.append({
                    'date': entry.created_at.date() if entry.created_at else None,
                    'title': entry.title,
                    'description': entry.description,
                    'activity_type': entry.activity_type,
                    'rating': r.rating,
                    'rating_label': RATING_LABELS.get(r.rating, '—'),
                })
            except SocialCurriculum.DoesNotExist:
                pass
    elif agent == 'patience':
        patience_ct = ContentType.objects.get_for_model(MotorCurriculum)
        for r in ratings.filter(content_type=patience_ct):
            try:
                entry = MotorCurriculum.objects.get(pk=r.object_id)
                activities.append({
                    'date': entry.created_at.date() if entry.created_at else None,
                    'title': entry.title,
                    'description': entry.description,
                    'activity_type': entry.activity_type,
                    'rating': r.rating,
                    'rating_label': RATING_LABELS.get(r.rating, '—'),
                })
            except MotorCurriculum.DoesNotExist:
                pass
    elif agent == 'sage':
        sage_ct = ContentType.objects.get_for_model(Dish)
        for r in ratings.filter(content_type=sage_ct):
            try:
                entry = Dish.objects.get(pk=r.object_id)
                activities.append({
                    'date': entry.created_at.date() if entry.created_at else None,
                    'title': entry.title or 'Meal',
                    'description': f"{entry.vegetable or ''}, {entry.fruit or ''}, {entry.grain or ''}, {entry.protein or ''}".strip(', '),
                    'activity_type': 'MEAL',
                    'rating': r.rating,
                    'rating_label': RATING_LABELS.get(r.rating, '—'),
                })
            except Dish.DoesNotExist:
                pass

    activities.sort(key=lambda x: x['date'] or date.min, reverse=True)

    # Compute summary counts
    total = len(activities)
    likes = sum(1 for a in activities if a['rating'] and a['rating'] >= 3)
    normals = sum(1 for a in activities if a['rating'] == 2)
    dislikes = sum(1 for a in activities if a['rating'] and a['rating'] <= 1)

    agents_order = ['sage', 'patience', 'grace']
    current_idx = agents_order.index(agent) if agent in agents_order else 0
    prev_agent = agents_order[(current_idx - 1) % len(agents_order)]
    next_agent = agents_order[(current_idx + 1) % len(agents_order)]

    return render(request, 'enroll/child_agent_activities.html', {
        'child': child,
        'agent': agent,
        'meta': meta,
        'activities': activities,
        'total': total,
        'likes': likes,
        'normals': normals,
        'dislikes': dislikes,
        'prev_agent': prev_agent,
        'next_agent': next_agent,
        'prev_meta': AGENT_META[prev_agent],
        'next_meta': AGENT_META[next_agent],
    })


@login_required
def generate_child_summary(request, child_id):
    """Use the LLM to generate a developmental milestone summary for a child."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    from materalleapp.agent_base import get_anthropic_response

    child = get_object_or_404(Child, child_id=child_id)
    ratings = StudentRating.objects.filter(child=child)
    weekly_ct = ContentType.objects.get_for_model(WeeklyPlanEntry)

    RATING_WORDS = {3: 'liked', 2: 'neutral', 1: 'disliked'}

    # Build activity summaries per agent
    agent_data = {'sage': [], 'grace': [], 'patience': []}

    # Weekly activities
    weekly_ratings = ratings.filter(content_type=weekly_ct)
    for r in weekly_ratings:
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
    from datetime import date as _date
    today = _date.today()
    age_months = (today.year - child.date_of_birth.year) * 12 + (today.month - child.date_of_birth.month)
    age_str = f"{age_months // 12} years, {age_months % 12} months"

    # Build LLM prompt
    sections = []
    if agent_data['sage']:
        sections.append("**Sage (Nutrition & Wellness):**\n" + "\n".join(agent_data['sage'][:15]))
    if agent_data['grace']:
        sections.append("**Grace (Social-Emotional Development):**\n" + "\n".join(agent_data['grace'][:15]))
    if agent_data['patience']:
        sections.append("**Patience (Motor & Physical Development):**\n" + "\n".join(agent_data['patience'][:15]))

    if not sections:
        return JsonResponse({
            'success': True,
            'summary': 'Not enough activity data to generate a developmental summary yet. Continue scheduling and rating activities to build this child\'s profile.',
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
        f"1. **Nutrition & Wellness** (Sage) — food preferences, eating patterns, nutritional observations\n"
        f"2. **Social-Emotional Development** (Grace) — social skills, emotional regulation, communication, "
        f"empathy, strengths and areas for growth\n"
        f"3. **Motor & Physical Development** (Patience) — fine motor, gross motor, coordination, "
        f"sensory preferences, strengths and areas for growth\n"
        f"4. **Developmental Milestones** — based on the child's age ({age_str}), note which "
        f"age-appropriate milestones appear to be met, emerging, or needing attention\n"
        f"5. **Recommendations for Parent/Caretaker** — practical suggestions for home activities "
        f"that reinforce strengths and support growth areas\n\n"
        f"Keep the tone warm, supportive, and professional. This report should be useful for "
        f"a parent to share with the child's pediatrician."
    )

    try:
        summary = get_anthropic_response(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=(
                "You are an early childhood development specialist. "
                "Write clear, evidence-based developmental summaries suitable for medical checkup discussions. "
                "Be specific about observed strengths and growth areas based on the activity data provided."
            ),
            max_tokens=2048,
        )
        return JsonResponse({'success': True, 'summary': summary})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def participants(request):
    context = {
        'students': Child.objects.all()
    }
    return render(request, 'enroll/participants.html', context)

@login_required
def delete_child(request, child_id):
    if request.method == 'DELETE':
        child = get_object_or_404(Child, child_id=child_id)
        child.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)

def dashboard(request):
    context = {
        'students': Child.objects.all()
    }
    return render(request, 'enroll/dashboard_activity.html', context)

@login_required
def schedule_activity(request):
    """Schedule an activity from a chat response for a child on a specific date."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        import json
        data = json.loads(request.body)
        child_id = data.get('child_id')
        title = data.get('title', '')
        activity_type = data.get('activity_type', '')
        agent = data.get('agent', '')
        scheduled_date = data.get('scheduled_date')  # YYYY-MM-DD
        description = data.get('description', '')
        entry_id = data.get('entry_id')

        if not child_id or not title or not scheduled_date:
            return JsonResponse({'error': 'child_id, title, and scheduled_date are required'}, status=400)

        child = get_object_or_404(Child, child_id=child_id)

        content_type_obj = None
        if entry_id and agent:
            if agent == 'grace':
                content_type_obj = ContentType.objects.get_for_model(SocialCurriculum)
            elif agent == 'patience':
                content_type_obj = ContentType.objects.get_for_model(MotorCurriculum)

        activity = ChildActivity.objects.create(
            child=child,
            title=title[:200],
            activity_type=activity_type,
            agent=agent,
            scheduled_date=scheduled_date,
            description=description,
            content_type=content_type_obj,
            object_id=entry_id if entry_id else None,
            created_by=request.user,
        )

        return JsonResponse({
            'success': True,
            'activity_id': activity.pk,
            'message': f'"{title}" scheduled for {child.child_name} on {scheduled_date}',
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def child_calendar(request, child_id):
    """Return scheduled activities for a child in a given month."""
    child = get_object_or_404(Child, child_id=child_id)
    year = int(request.GET.get('year', date.today().year))
    month = int(request.GET.get('month', date.today().month))

    activities = ChildActivity.objects.filter(
        child=child,
        scheduled_date__year=year,
        scheduled_date__month=month,
    )

    return JsonResponse({
        'child': child.child_name,
        'year': year,
        'month': month,
        'activities': [{
            'id': a.pk,
            'title': a.title,
            'activity_type': a.activity_type,
            'agent': a.agent,
            'scheduled_date': a.scheduled_date.isoformat(),
            'description': a.description,
        } for a in activities],
    })


class StudentListView(LoginRequiredMixin, View):
    """View for listing all students."""
    def get(self, request):
        if is_parent(request.user):
            students = Student.objects.filter(enrolled_by=request.user)
        else:
            students = Student.objects.all()
        return render(request, 'enroll/student_list.html', {'students': students})

class StudentDetailView(LoginRequiredMixin, View):
    """View for displaying student details."""
    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        if is_parent(request.user) and student.enrolled_by != request.user:
            return HttpResponseForbidden("You don't have permission to view this student's details.")
        return render(request, 'enroll/student_detail.html', {'student': student})

class CheckInCheckOutView(LoginRequiredMixin, View):
    """Handle student check-in and check-out."""
    def post(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        if is_parent(request.user) and student.enrolled_by != request.user:
            return HttpResponseForbidden("You don't have permission to check this student in/out.")

        today = date.today()
        attendance, created = AttendanceLog.objects.get_or_create(
            student=student,
            date=today,
            defaults={'recorded_by': request.user}
        )

        if attendance.check_in is None:
            attendance.check_in = timezone.now()
            messages.success(request, f'{student.name} has been checked in.')
        elif attendance.check_out is None:
            attendance.check_out = timezone.now()
            messages.success(request, f'{student.name} has been checked out.')

        attendance.save()
        return redirect('enroll:student-list')

class GenerateAttendanceReport(LoginRequiredMixin, View):
    """Generate CSV attendance report."""
    def get(self, request):
        if not is_staff_role(request.user):
            return HttpResponseForbidden("You don't have permission to generate attendance reports.")

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

        writer = csv.writer(response)
        header = ['Name', 'Date of Birth'] + [f'Day {i}' for i in range(1, 32)]
        writer.writerow(header)

        if is_parent(request.user):
            students = Student.objects.filter(enrolled_by=request.user)
        else:
            students = Student.objects.all()

        today = date.today()
        for student in students:
            row = [student.name, student.date_of_birth.strftime('%Y-%m-%d')]

            for day in range(1, 32):
                try:
                    day_date = date(today.year, today.month, day)
                    attendance = AttendanceLog.objects.get(student=student, date=day_date)
                    if attendance.check_in:
                        row.append('Present')
                    else:
                        row.append('Absent')
                except (AttendanceLog.DoesNotExist, ValueError):
                    row.append('Absent')

            writer.writerow(row)

        return response

@login_required
def enroll_request(request):
    """Handle student enrollment requests."""
    if not is_parent(request.user):
        messages.error(request, 'Only parents can enroll new students.')
        return redirect('website:home')

    if request.method == "POST":
        form = StudentEnrollmentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    student = form.save(commit=False)
                    student.enrolled_by = request.user
                    student.save()
                    messages.success(request, f'Student {student.name} has been enrolled successfully!')
                    return redirect('enroll:student-list')
            except Exception as e:
                messages.error(request, 'An error occurred during enrollment. Please try again.')
                return render(request, "enroll/enroll.html", {'form': form})
    else:
        form = StudentEnrollmentForm()
    
    return render(request, "enroll/enroll.html", {'form': form})

@login_required
def student_edit(request, student_id):
    """Edit student information."""
    student = get_object_or_404(Student, id=student_id)
    
    if is_parent(request.user) and student.enrolled_by != request.user:
        return HttpResponseForbidden("You don't have permission to edit this student's information.")
    
    if request.method == 'POST':
        form = StudentEnrollmentForm(request.POST, instance=student)
        if form.is_valid():
            try:
                with transaction.atomic():
                    student = form.save(commit=False)
                    student.last_modified_by = request.user
                    student.save()
                    messages.success(request, f'Student {student.name}\'s information has been updated.')
                    return redirect('enroll:student-detail', student_id=student.id)
            except Exception as e:
                messages.error(request, 'An error occurred while updating student information.')
    else:
        form = StudentEnrollmentForm(instance=student)
    
    return render(request, 'enroll/student_edit.html', {
        'form': form,
        'student': student
    })

@login_required
def attendance_history(request, student_id):
    """View attendance history for a student."""
    student = get_object_or_404(Student, id=student_id)
    
    if is_parent(request.user) and student.enrolled_by != request.user:
        return HttpResponseForbidden("You don't have permission to view this student's attendance.")
    
    attendance_logs = AttendanceLog.objects.filter(student=student).order_by('-date')
    return render(request, 'enroll/attendance_history.html', {
        'student': student,
        'attendance_logs': attendance_logs
    })

@login_required
def student_search(request):
    """Search for students."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    try:
        if is_parent(request.user):
            students = Student.objects.filter(
                enrolled_by=request.user,
                name__icontains=query
            )[:5]
        else:
            students = Student.objects.filter(
                name__icontains=query
            )[:5]

        results = [{
            'id': student.id,
            'name': student.name,
            'date_of_birth': student.date_of_birth.strftime('%Y-%m-%d'),
            'enrolled_by': student.enrolled_by.get_full_name(),
            'url': f'/enroll/student/{student.id}/'
        } for student in students]
        
        return JsonResponse({
            'success': True,
            'results': results
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
