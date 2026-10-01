# sage/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.template import loader
from django.views import View
from django.conf import settings
from .forms import DishForm, GroceryItemForm
from .models import Dish, Menu, Meal, MealAttendance, GroceryItem, Schedule, Document, Attendance, WeeklyPlanEntry

from .agents import SageAgent
from grace.agents import GraceAgent
from patience.agents import PatienceAgent
from website.models import LearningSession
from agent.models import Conversation as AgentConversation, Message as AgentMessage
from materalleapp.agent_base import get_anthropic_response
from asgiref.sync import sync_to_async
import json

import csv
from datetime import date, datetime, timedelta
from enroll.models import Student, Child, AttendanceLog, StudentRating
from django.contrib.contenttypes.models import ContentType

import random
from typing import Dict, List, Optional
import io
import asyncio
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse

@login_required
def add_dish(request):
    """AJAX endpoint to create a Dish."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        dish = Dish.objects.create(
            meal_type=data.get('meal_type', ''),
            vegetable=data.get('vegetable', ''),
            fruit=data.get('fruit', ''),
            grain=data.get('grain', ''),
            protein=data.get('protein', ''),
            drink=data.get('drink', ''),
        )
        return JsonResponse({'success': True, 'id': dish.pk, 'title': dish.title})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


def index(request):
    if request.method == "POST":
        form = DishForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect("/sage")
    else:
        form = DishForm()

    food_list = Dish.objects.all()
    students = Child.objects.all()

    # Build per-child rating summaries for Sage activities
    sage_ct = ContentType.objects.get_for_model(Dish)
    children_data = []
    for child in students:
        ratings = StudentRating.objects.filter(child=child, content_type=sage_ct)
        likes = ratings.filter(rating__gte=3).count()
        normals = ratings.filter(rating=2).count()
        dislikes = ratings.filter(rating__lte=1).count()
        children_data.append({
            'child': child,
            'likes': likes,
            'normals': normals,
            'dislikes': dislikes,
            'total_ratings': ratings.count(),
        })

    context = {
        "food_list": food_list,
        "form": form,
        "students": students,
        "children_data": children_data,
        "current_activity_id": Dish.objects.order_by('-created_at').values_list('pk', flat=True).first() or '',
        "page": "sage",
    }
    return render(request, "sage/index.html", context)

def sage_chat(request):
    return render(request, "sage/chat.html")

async def sage_interaction(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        message = data.get('message')
        session_id = data.get('session_id',None)
        
        if session_id:
            session = await sync_to_async(LearningSession.objects.get)(id=session_id, user=request.user)
        else:
                # Create a new session if session_id is not provided
                user = request.user
                session = await sync_to_async(LearningSession.objects.create)(user=user)
            
        agent = SageAgent()
        rag_context = await sync_to_async(get_rag_context)(request.user, query=message)
        if rag_context:
            agent.system_prompt += rag_context

        conversation, _ = await sync_to_async(AgentConversation.objects.get_or_create)(
            user=request.user,
            title=f'Sage - Session {session.pk}',
        )
        await sync_to_async(AgentMessage.objects.create)(
            conversation=conversation,
            content=message,
            is_user=True,
        )
        recent_messages = await sync_to_async(list)(
            AgentMessage.objects.filter(conversation=conversation).order_by('-timestamp')[:11]
        )
        context = [
            {'role': 'user' if item.is_user else 'assistant', 'content': item.content}
            for item in reversed(recent_messages[:-1])
        ]
        
        response = await agent.get_response(message, context)

        await sync_to_async(AgentMessage.objects.create)(
            conversation=conversation,
            content=response,
            is_user=False,
        )

        # Create a Dish entry from this chat response
        dish = await sync_to_async(Dish.objects.create)(
            title=message[:200],
        )

        return JsonResponse({'response': response, 'entry_id': dish.pk})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=400)
 
class StudentListView(View):
    def get(self, request):
        students = Student.objects.all()
        return render(request, 'sage/student_list.html', {'students': students})    
    
class CheckInCheckOutView(View):
    def post(self, request, student_id):
        student = Student.objects.get(id=student_id)
        today = date.today()

        attendance, created = Attendance.objects.get_or_create(student=student, date=today)

        if attendance.check_in is None:
            attendance.check_in = datetime.now()
        elif attendance.check_out is None:
            attendance.check_out = datetime.now()

        attendance.save()
        return redirect('student-list')    
    
class GenerateAttendanceReport(View):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

        writer = csv.writer(response)
        header = ['Name', 'Date of Birth'] + [f'Day {i}' for i in range(1, 32)]
        writer.writerow(header)

        students = Student.objects.all()
        today = date.today()
        for student in students:
            row = [student.name, student.date_of_birth.strftime('%Y-%m-%d')]

            for day in range(1, 32):
                try:
                    day_date = date(today.year, today.month, day)
                    attendance = Attendance.objects.get(student=student, date=day_date)
                    if attendance.check_in:
                        row.append('Present')
                    else:
                        row.append('Absent')
                except (Attendance.DoesNotExist, ValueError):
                    row.append('Absent')

            writer.writerow(row)

        return response
    
@login_required
def sage_dashboard(request):
    today = timezone.now().date()
    context = {
        'daily_schedule': Schedule.objects.filter(day_of_week=today.weekday()),
        'recent_documents': Document.objects.all().order_by('-uploaded_at')[:5],
        'checked_in_children': Child.objects.filter(is_checked_in=True),
        'checked_in_count': Child.objects.filter(is_checked_in=True).count(),
        'total_children': Child.objects.count(),
        'todays_meals': Meal.objects.filter(date=today)
    }
    return render(request, 'sage/dashboard.html', context)


@login_required
def activity_dashboard(request):
    """Dashboard showing participants and daily activities grouped by agent for rating."""
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=4)

    # Support cycling through days via ?day=0..4 (0=Monday)
    day_offset_param = request.GET.get('day')
    if day_offset_param is not None:
        try:
            day_offset = max(0, min(4, int(day_offset_param)))
        except ValueError:
            day_offset = today.weekday() if today.weekday() < 5 else 0
    else:
        day_offset = today.weekday() if today.weekday() < 5 else 0

    selected_date = week_start + timedelta(days=day_offset)

    # Build day tabs for navigation
    DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    day_tabs = []
    for i, name in enumerate(DAY_NAMES):
        dt = week_start + timedelta(days=i)
        day_tabs.append({
            'offset': i,
            'name': name,
            'short': name[:3],
            'date': dt,
            'is_active': i == day_offset,
            'is_today': dt == today,
        })

    students = Child.objects.all()
    children = students.order_by('child_name')
    checked_in_count = students.filter(is_checked_in=True).count()

    # Get entries for the selected day
    day_entries = WeeklyPlanEntry.objects.filter(
        week_start_date=week_start,
        scheduled_date=selected_date,
    ).order_by('start_time')

    # Build flat activity list (for the "select and rate all" feature)
    weekly_ct = ContentType.objects.get_for_model(WeeklyPlanEntry)
    RATING_LABELS = {3: '\U0001f604 Liked', 2: '\U0001f610 Okay', 1: '\U0001f61e Disliked'}
    AGENT_META = {
        'sage': {'label': 'Sage', 'subtitle': 'Nutrition & Meals', 'color': '#198754'},
        'grace': {'label': 'Grace', 'subtitle': 'Social-Emotional Development', 'color': '#d63384'},
        'patience': {'label': 'Patience', 'subtitle': 'Motor & Physical Development', 'color': '#0d6efd'},
    }

    agent_groups = {}
    all_activities = []
    for entry in day_entries:
        agent = entry.agent or 'sage'
        if agent not in agent_groups:
            agent_groups[agent] = []

        ratings_qs = StudentRating.objects.filter(
            content_type=weekly_ct, object_id=entry.pk
        )
        child_ratings = {}
        for r in ratings_qs:
            child_ratings[r.child_id] = {
                'rating': r.rating,
                'label': RATING_LABELS.get(r.rating, ''),
            }

        act_data = {
            'id': entry.pk,
            'title': entry.title,
            'description': entry.description,
            'activity_type': entry.activity_type,
            'start_time': entry.start_time,
            'agent': agent,
            'is_static': entry.is_static,
            'child_ratings': child_ratings,
            'child_ratings_json': json.dumps({str(k): v for k, v in child_ratings.items()}),
        }
        agent_groups[agent].append(act_data)
        all_activities.append(act_data)

    agent_sections = []
    for agent_key in ['sage', 'grace', 'patience']:
        if agent_key in agent_groups:
            agent_sections.append({
                'key': agent_key,
                'meta': AGENT_META.get(agent_key, {}),
                'activities': agent_groups[agent_key],
            })

    # Serialize children list for JS bulk-rating
    children_json = json.dumps([
        {'child_id': c.child_id, 'child_name': c.child_name}
        for c in children
    ])

    context = {
        'students': students,
        'children': children,
        'children_json': children_json,
        'checked_in_count': checked_in_count,
        'agent_sections': agent_sections,
        'all_activities': all_activities,
        'today': today,
        'selected_date': selected_date,
        'day_offset': day_offset,
        'day_tabs': day_tabs,
        'week_start': week_start,
        'week_end': week_end,
        'has_schedule': day_entries.exists(),
    }
    return render(request, 'sage/activity_dashboard.html', context)


@login_required
def meal_planner(request):
    # Get all meals for the current month
    today = timezone.now().date()
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Get all meals for the month
    monthly_meals = Meal.objects.filter(
        date__range=[month_start, month_end]
    ).prefetch_related('mealattendance_set')
    
    # Structure the meals data for the calendar
    meals_data = {}
    for meal in monthly_meals:
        date_str = meal.date.isoformat()
        if date_str not in meals_data:
            meals_data[date_str] = {}
        
        if meal.meal_type not in meals_data[date_str]:
            meals_data[date_str][meal.meal_type] = []
            
        meals_data[date_str][meal.meal_type].append({
            'id': meal.id,
            'name': meal.name,
            'attendance_count': meal.mealattendance_set.filter(attended=True).count()
        })
    
    context = {
        'current_month': today,
        'meals_json': json.dumps(meals_data),
    }
    return render(request, 'sage/meal_planner.html', context)

@login_required
def record_meal(request):
    if request.method == 'POST':
        meal = Meal.objects.create(
            name=request.POST.get('name'),
            meal_type=request.POST.get('meal_type'),
            date=timezone.now().date(),
            created_by=request.user
        )
        
        for child_id in request.POST.getlist('children'):
            MealAttendance.objects.create(
                meal=meal,
                child_id=child_id,
                attended=True,
                recorded_by=request.user
            )
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False}) 

@login_required
def grocery_list(request):
    form = GroceryItemForm()
    items = GroceryItem.objects.filter(added_by=request.user)
    return render(request, 'sage/grocery_list.html', {'form': form, 'items': items})

@login_required
def upload_grocery_list(request):
    from .parser import VALID_CATEGORIES, parse_document, categorize_with_llm, parse_text_items

    if request.method == 'POST':
        try:
            grocery_text = request.POST.get('grocery_list', '').strip()
            uploaded_file = request.FILES.get('grocery_file')

            # Route: uploaded file (any format) or pasted text
            if uploaded_file:
                uploaded_file.seek(0)
                categorized = parse_document(uploaded_file, uploaded_file.name)
            elif grocery_text:
                items = parse_text_items(grocery_text)
                categorized = categorize_with_llm(items)
            else:
                return JsonResponse({'success': False, 'error': 'No grocery list provided'})

            valid_categories = set(VALID_CATEGORIES)

            # Pull out conflicts before processing categories
            conflicts = categorized.pop('CONFLICTS', [])

            existing_names = set(
                GroceryItem.objects.filter(added_by=request.user).values_list('name', flat=True)
            )
            existing_lower = {n.lower() for n in existing_names}

            created_items = []
            items_by_category = {}

            for raw_cat, items in categorized.items():
                cat = raw_cat.upper().rstrip('S')
                if cat not in valid_categories:
                    continue
                if cat not in items_by_category:
                    items_by_category[cat] = []

                for item_name in items:
                    name = item_name.strip().title()
                    if not name or name.lower() in existing_lower:
                        continue
                    existing_lower.add(name.lower())
                    created_items.append(
                        GroceryItem(name=name, category=cat, added_by=request.user)
                    )
                    items_by_category[cat].append(name)

            if created_items:
                GroceryItem.objects.bulk_create(created_items)

            # Return IDs for newly created items
            all_items = list(
                GroceryItem.objects.filter(added_by=request.user).values('id', 'name', 'category')
            )
            new_names = {item for cat_items in items_by_category.values() for item in cat_items}
            new_items_with_ids = [
                {'id': it['id'], 'name': it['name'], 'category': it['category']}
                for it in all_items if it['name'] in new_names
            ]

            # Filter conflicts: skip items that already exist
            conflicts = [
                c for c in conflicts
                if c['name'].lower() not in existing_lower
            ]

            return JsonResponse({
                'success': True,
                'categories': items_by_category,
                'newItems': new_items_with_ids,
                'createdCount': len(created_items),
                'conflicts': conflicts,
            })

        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            })

    return render(request, 'sage/upload_grocery_list.html', {})

@require_http_methods(["POST"])
def add_item(request):
    try:
        form = GroceryItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.added_by = request.user
            item.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'Invalid form data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
@require_http_methods(["POST"])
def remove_items(request):
    try:
        items = request.POST.getlist('items') or request.POST.getlist('items[]')
        GroceryItem.objects.filter(id__in=items).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@require_http_methods(["POST"])
def clear_grocery_list(request):
    try:
        GroceryItem.objects.filter(added_by=request.user).delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_http_methods(["POST"])
def resolve_grocery_conflicts(request):
    """Save conflict items with user-chosen categories."""
    try:
        from .parser import VALID_CATEGORIES

        data = json.loads(request.body)
        resolved = data.get('resolved', [])  # [{"name": "...", "category": "PROTEIN"}, ...]
        if not resolved:
            return JsonResponse({'success': True, 'created': 0})

        valid_categories = set(VALID_CATEGORIES)
        existing_lower = {
            n.lower() for n in
            GroceryItem.objects.filter(added_by=request.user).values_list('name', flat=True)
        }

        to_create = []
        for item in resolved:
            name = item.get('name', '').strip().title()
            cat = item.get('category', 'OTHER').upper().rstrip('S')
            if cat not in valid_categories:
                continue
            if name and name.lower() not in existing_lower:
                existing_lower.add(name.lower())
                to_create.append(GroceryItem(name=name, category=cat, added_by=request.user))

        if to_create:
            GroceryItem.objects.bulk_create(to_create)

        # Return created items with IDs
        created_names = {obj.name for obj in to_create}
        new_items = list(
            GroceryItem.objects.filter(added_by=request.user, name__in=created_names)
            .values('id', 'name', 'category')
        )

        return JsonResponse({'success': True, 'created': len(to_create), 'newItems': new_items})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def _extract_document_text(file, ext):
    """Extract text content from an uploaded file for RAG."""
    from .parser import extract_text_from_image, extract_text_from_pdf
    try:
        if ext in ('jpg', 'jpeg', 'png', 'bmp', 'tiff', 'webp'):
            return extract_text_from_image(file)
        elif ext == 'pdf':
            return extract_text_from_pdf(file)
        else:
            raw = file.read()
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', errors='ignore')
            file.seek(0)
            return raw
    except Exception as e:
        return ''


def get_rag_context(user, query=None):
    """Build RAG context string from parsed documents using semantic search if available."""
    docs = Document.objects.filter(uploaded_by=user).exclude(analysis__isnull=True).exclude(analysis='')
    if not docs.exists():
        return ''

    sections = []

    if query and getattr(settings, 'ENABLE_RAG_VECTORDB', False):
        try:
            from .rag_vectordb import search_documents
            results = search_documents(query, limit=3)
            if results:
                for result in results:
                    text = result.get('text', '')[:3000]
                    score = result.get('score', 0)
                    sections.append(f"--- Document: {result.get('title')} (relevance: {score:.2f}) ---\n{text}")
        except Exception as e:
            import logging
            logging.warning(f"Vector search failed, falling back to simple concatenation: {e}")

    if not sections:
        for doc in docs[:10]:
            text = doc.analysis[:3000]
            sections.append(f"--- Document: {doc.title} ---\n{text}")

    if not sections:
        return ''

    return (
        "\n\nYou have access to the following reference documents uploaded by the user. "
        "Use them to inform your responses when relevant:\n\n"
        + "\n\n".join(sections)
    )


@login_required
def upload_documents(request):
    """Upload resource documents, extract text for RAG, and display the library."""
    if request.method == 'POST':
        files = request.FILES.getlist('documents')
        uploaded_files = []
        try:
            for file in files:
                ext = file.name.rsplit('.', 1)[-1].lower() if '.' in file.name else ''
                content_text = _extract_document_text(file, ext)
                file.seek(0)

                doc = Document.objects.create(
                    title=file.name,
                    file=file,
                    uploaded_by=request.user,
                    analysis=content_text,
                )
                uploaded_files.append({
                    'name': doc.title,
                    'size': doc.file_size,
                    'type': doc.file_type,
                    'id': doc.id,
                    'parsed': bool(content_text),
                })
            return JsonResponse({
                'success': True,
                'message': f'Uploaded {len(uploaded_files)} document(s)',
                'files': uploaded_files,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    documents = Document.objects.filter(uploaded_by=request.user).order_by('-uploaded_at')
    return render(request, 'sage/upload_documents.html', {'documents': documents})


@login_required
async def upload_grocery_documents(request):
    """Upload and parse grocery documents (receipts, CSVs, etc.)."""
    from .parser import VALID_CATEGORIES, parse_document

    if request.method == 'POST':
        files = request.FILES.getlist('documents')
        uploaded_files = []

        try:
            for file in files:
                # Save the document record
                doc = await sync_to_async(Document.objects.create)(
                    title=file.name,
                    file=file,
                    uploaded_by=request.user,
                    file_type=file.name.split('.')[-1].lower(),
                    file_size=file.size
                )

                categorized_items = {}
                grocery_items = []

                try:
                    # Use the unified parser for all file types
                    # (csv, txt, jpg/png receipts, pdf)
                    file.seek(0)
                    categorized_items = await sync_to_async(parse_document)(file, file.name)
                    conflicts = categorized_items.pop('CONFLICTS', [])

                    # Deduplicate against existing items
                    existing_lower = set(
                        await sync_to_async(list)(
                            GroceryItem.objects.filter(
                                added_by=request.user
                            ).values_list('name', flat=True)
                        )
                    )
                    existing_lower = {n.lower() for n in existing_lower}

                    for category, items in categorized_items.items():
                        cat = category.upper().rstrip('S')
                        if cat not in VALID_CATEGORIES:
                            continue
                        for item in items:
                            name = item.strip().title()
                            if name and name.lower() not in existing_lower:
                                existing_lower.add(name.lower())
                                grocery_items.append(
                                    GroceryItem(name=name, category=cat, added_by=request.user)
                                )

                    if grocery_items:
                        await sync_to_async(GroceryItem.objects.bulk_create)(grocery_items)

                    doc.analysis = json.dumps({
                        'categories': categorized_items,
                        'conflicts': conflicts,
                        'total_items': len(grocery_items),
                        'processed': True
                    })
                    await sync_to_async(doc.save)()

                except Exception as e:
                    import traceback
                    print(f"Error processing {file.name}: {traceback.format_exc()}")
                    doc.analysis = json.dumps({
                        'error': str(e),
                        'processed': False
                    })
                    await sync_to_async(doc.save)()

                uploaded_files.append({
                    'name': doc.title,
                    'size': doc.file_size,
                    'type': doc.file_type,
                    'id': doc.id,
                    'categories': categorized_items,
                    'items_count': len(grocery_items),
                })

            return JsonResponse({
                'success': True,
                'message': f'Successfully processed {len(uploaded_files)} file(s)',
                'files': uploaded_files
            })

        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': f'Error processing files: {str(e)}',
                'traceback': traceback.format_exc()
            })

    # GET — redirect to grocery list (this view is POST-only from the grocery page)
    from django.shortcuts import redirect as _redirect
    return _redirect('sage:grocery_list')

@login_required
def delete_file(request, file_id):
    if request.method == 'DELETE':
        try:
            doc = Document.objects.get(id=file_id, uploaded_by=request.user)
            doc.delete()
            return JsonResponse({'success': True})
        except Document.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'File not found'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def schedule(request):
    """
    GET  — redirect to weekly schedule if one exists for the current week,
           otherwise render the schedule grid (loads default schedule if it exists).
    POST — save the full schedule grid (all time slots × days).
    """
    import json as _json
    TIME_SLOTS = list(range(7, 18))  # 7 AM to 5 PM

    if request.method == 'GET':
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        if WeeklyPlanEntry.objects.filter(week_start_date=week_start).exists():
            return redirect('sage:weekly_schedule')

    if request.method == 'POST':
        try:
            data = _json.loads(request.body)
            action = data.get('action', 'save')

            if action == 'set_default':
                Schedule.objects.filter(is_default=True).delete()
                for entry in Schedule.objects.filter(is_default=False, day_of_week=0):
                    Schedule.objects.create(
                        start_time=entry.start_time,
                        end_time=entry.end_time,
                        activity=entry.activity,
                        agent=entry.agent,
                        day_of_week=0,
                        is_default=True,
                    )
                return JsonResponse({'success': True, 'message': 'Default schedule saved'})

            if action == 'load_default':
                defaults = Schedule.objects.filter(is_default=True)
                if not defaults.exists():
                    return JsonResponse({'success': False, 'error': 'No default schedule set'})
                Schedule.objects.filter(is_default=False, day_of_week=0).delete()
                for entry in defaults:
                    Schedule.objects.create(
                        start_time=entry.start_time,
                        end_time=entry.end_time,
                        activity=entry.activity,
                        agent=entry.agent,
                        day_of_week=0,
                        is_default=False,
                    )
                return JsonResponse({'success': True, 'message': 'Default schedule loaded'})

            if action == 'generate_week':
                # Read the guideline schedule and generate a week of activities
                entries = Schedule.objects.filter(is_default=False, day_of_week=0).order_by('start_time')
                if not entries.exists():
                    return JsonResponse({'success': False, 'error': 'Save a guideline schedule first'})

                weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
                agent_prompts = {
                    'grace': GraceAgent().get_system_prompt(),
                    'patience': PatienceAgent().get_system_prompt(),
                    'sage': SageAgent().get_system_prompt(),
                }

                # Group slots by agent
                agent_slots = {}
                for entry in entries:
                    agent = entry.agent or 'sage'
                    if agent not in agent_slots:
                        agent_slots[agent] = []
                    agent_slots[agent].append({
                        'hour': entry.start_time.hour,
                        'label': entry.start_time.strftime('%I:%M %p').lstrip('0'),
                        'activity': entry.activity,
                    })

                weekly = {}  # {hour: {day: response_text, ...}, ...}

                for agent_name, slots_list in agent_slots.items():
                    system = agent_prompts.get(agent_name, '')
                    rag = get_rag_context(request.user) if hasattr(request, 'user') and request.user.is_authenticated else ''
                    if rag:
                        system += rag

                    # Build one prompt per agent with all its slots × 5 days
                    slot_descriptions = []
                    for s in slots_list:
                        slot_descriptions.append(f"- {s['label']}: {s['activity']}")

                    prompt = (
                        f"Generate a weekly schedule (Monday through Friday) of activities. "
                        f"For each day and each time slot below, suggest a DIFFERENT specific activity.\n\n"
                        f"Time slots assigned to you:\n" + "\n".join(slot_descriptions) + "\n\n"
                        f"Format your response EXACTLY like this for EACH activity:\n"
                        f"### [Day] — [Time]\n"
                        f"**Title:** [Activity name]\n"
                        f"**Activity Type:** [Type]\n"
                        f"**Age Range:** [Range]\n"
                        f"**Description:** [Brief 1-2 sentence description]\n"
                        f"**Duration:** [Minutes]\n\n"
                        f"Generate all 5 days × {len(slots_list)} slot(s) = {5 * len(slots_list)} activities total. "
                        f"Make each day's activities unique and varied."
                    )

                    try:
                        response_text = get_anthropic_response(
                            messages=[{"role": "user", "content": prompt}],
                            system_prompt=system,
                            max_tokens=4096,
                        )
                    except Exception as e:
                        response_text = f"Error generating activities: {str(e)}"

                    # Parse the response into day/time buckets
                    import re
                    # Split by ### Day — Time headers
                    blocks = re.split(r'###\s+', response_text)
                    for block in blocks:
                        block = block.strip()
                        if not block:
                            continue
                        # Match "Monday — 8:00 AM" or "Monday - 8:00 AM"
                        header_match = re.match(r'(\w+)\s*[—–-]\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])', block)
                        if not header_match:
                            continue
                        day_name = header_match.group(1).strip().title()
                        time_str = header_match.group(2).strip()
                        # Parse hour from time_str
                        time_match = re.match(r'(\d{1,2}):(\d{2})\s*([AaPp][Mm])', time_str)
                        if not time_match:
                            continue
                        hr = int(time_match.group(1))
                        ampm = time_match.group(3).upper()
                        if ampm == 'PM' and hr != 12:
                            hr += 12
                        elif ampm == 'AM' and hr == 12:
                            hr = 0

                        content = block[header_match.end():].strip()
                        if hr not in weekly:
                            weekly[hr] = {}
                        weekly[hr][day_name] = {
                            'content': content,
                            'agent': agent_name,
                        }

                # Build final grid
                result_grid = []
                for entry in entries:
                    hour = entry.start_time.hour
                    label = entry.start_time.strftime('%I:%M %p').lstrip('0')
                    days = {}
                    for day in weekdays:
                        cell = weekly.get(hour, {}).get(day, None)
                        if cell:
                            days[day] = cell
                        else:
                            days[day] = {'content': '', 'agent': entry.agent or ''}
                    result_grid.append({
                        'hour': hour,
                        'label': label,
                        'activity': entry.activity,
                        'agent': entry.agent,
                        'days': days,
                    })

                return JsonResponse({'success': True, 'weekly': result_grid, 'weekdays': weekdays})

            # action == 'save': full daily schedule save
            slots = data.get('slots', [])
            Schedule.objects.filter(is_default=False, day_of_week=0).delete()
            created = 0
            for slot in slots:
                hour = int(slot['hour'])
                activity = slot.get('activity', '').strip()
                agent = slot.get('agent', '').strip()
                if not activity:
                    continue
                Schedule.objects.create(
                    start_time=f"{hour}:00",
                    end_time=f"{hour + 1}:00",
                    activity=activity,
                    agent=agent,
                    day_of_week=0,
                    is_default=False,
                )
                created += 1
            return JsonResponse({'success': True, 'message': f'{created} slot(s) saved'})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    # GET: build the daily schedule
    entries = Schedule.objects.filter(is_default=False, day_of_week=0)
    lookup = {}
    for e in entries:
        lookup[e.start_time.hour] = {
            'activity': e.activity,
            'agent': e.agent,
        }

    grid = []
    for hour in TIME_SLOTS:
        cell = lookup.get(hour, {'activity': '', 'agent': ''})
        grid.append({
            'hour': hour,
            'label': f"{hour % 12 or 12}:00 {'AM' if hour < 12 else 'PM'}",
            'activity': cell['activity'],
            'agent': cell['agent'],
        })

    has_default = Schedule.objects.filter(is_default=True).exists()

    return render(request, 'sage/schedule.html', {
        'grid': grid,
        'has_default': has_default,
    })


def _parse_activity_field(text, field_name):
    """Extract a field value from structured LLM response like **Field:** value"""
    import re as _re
    pattern = rf'\*\*{field_name}:\*\*\s*(.+?)(?=\n\*\*|\Z)'
    match = _re.search(pattern, text, _re.DOTALL)
    return match.group(1).strip() if match else ''


def _get_menu_for_day(user, day_name, meal_type_key):
    """Pull meal description from the current (or most recent) generated Menu for a given day and meal type."""
    latest_menu = Menu.objects.filter(created_by=user, is_current=True).first()
    if not latest_menu:
        latest_menu = Menu.objects.filter(created_by=user).order_by('-created_at').first()
    if not latest_menu:
        return f"{meal_type_key} (no menu generated yet)"
    try:
        data = latest_menu.menu_data
        # Use Week 1 as the template
        week = data.get('Week 1', {})
        meal_data = week.get(meal_type_key, {})
        components = meal_data.get('components', [])
        items = []
        for comp in components:
            item = comp.get('items', {}).get(day_name, '')
            if item:
                items.append(item)
        return ', '.join(items) if items else meal_type_key
    except Exception:
        return meal_type_key


SAGE_STATIC_ACTIVITIES = {
    'drop off': {
        'title': 'Morning Greeting',
        'description': 'Welcome children and families as they arrive. Greet each child by name, check in on how they are feeling, and help them transition into the classroom with a warm, calm routine.',
        'activity_type': 'ADMIN',
    },
    'pick up': {
        'title': 'Evening Reflection',
        'description': 'Gather children for a brief reflection on the day. Share highlights, celebrate achievements, and prepare for a smooth transition home with positive closure.',
        'activity_type': 'ADMIN',
    },
}

SAGE_MEAL_MAP = {
    'breakfast': 'BREAKFAST',
    'am snack': 'A.M. SNACK',
    'lunch': 'LUNCH',
    'pm snack': 'P.M. SNACK',
    'supper': 'SUPPER',
}


def _normalize_activity(activity):
    """Lower-case a slot label and drop periods so 'A.M. Snack' matches 'am snack'."""
    return ' '.join(activity.lower().replace('.', '').split())


@login_required
def weekly_schedule(request):
    """Display the generated weekly schedule as its own page."""
    today = date.today()
    # Find Monday of current week
    week_start = today - timedelta(days=today.weekday())

    entries = WeeklyPlanEntry.objects.filter(week_start_date=week_start)
    children = Child.objects.filter(is_checked_in=True)

    # Build per-child rating summaries
    sage_ct = ContentType.objects.get_for_model(Dish)
    children_data = []
    for child in children:
        ratings = StudentRating.objects.filter(child=child, content_type=sage_ct)
        children_data.append({
            'child': child,
            'likes': ratings.filter(rating__gte=3).count(),
            'normals': ratings.filter(rating=2).count(),
            'dislikes': ratings.filter(rating__lte=1).count(),
            'total_ratings': ratings.count(),
        })

    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    weekday_dates = [(week_start + timedelta(days=i)) for i in range(5)]

    # Build grid: {hour: {day_name: entry}}
    time_slots = sorted(set(e.start_time.hour for e in entries)) if entries.exists() else []
    grid = []
    for hour in time_slots:
        label = f"{hour % 12 or 12}:00 {'AM' if hour < 12 else 'PM'}"
        days = {}
        for i, day in enumerate(weekdays):
            entry = entries.filter(
                scheduled_date=weekday_dates[i],
                start_time__hour=hour,
            ).first()
            if entry:
                days[day] = {
                    'id': entry.pk,
                    'title': entry.title,
                    'description': entry.description,
                    'agent': entry.agent,
                    'activity_type': entry.activity_type,
                    'is_static': entry.is_static,
                    'guideline': entry.guideline_activity,
                }
            else:
                days[day] = None
        grid.append({
            'hour': hour,
            'label': label,
            'days': days,
        })

    # Check if there's a current menu and whether meals are already in the schedule
    current_menu = Menu.objects.filter(created_by=request.user, is_current=True).first()
    if not current_menu:
        current_menu = Menu.objects.filter(created_by=request.user).order_by('-created_at').first()
    menu_week = _menu_week_for_date(current_menu.menu_data, week_start) if current_menu else None
    has_meal_entries = entries.filter(activity_type='MEAL').exists()

    return render(request, 'sage/weekly_schedule.html', {
        'grid': grid,
        'weekdays': weekdays,
        'weekday_dates': zip(weekdays, weekday_dates),
        'week_start': week_start,
        'children': children,
        'children_data': children_data,
        'has_schedule': entries.exists(),
        'has_current_menu': menu_week is not None,
        'has_meal_entries': has_meal_entries,
        'current_menu_title': f'{current_menu.title} — Week of {week_start:%b %d}' if current_menu and menu_week else '',
    })


@login_required
def default_schedule_slots(request):
    slots = Schedule.objects.filter(is_default=True, day_of_week=0).order_by('start_time')
    return JsonResponse({
        'slots': [{
            'id': slot.pk,
            'time': slot.start_time.strftime('%I:%M %p').lstrip('0'),
            'activity': slot.activity,
        } for slot in slots],
    })


@login_required
def assign_chat_activity_to_schedule(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        agent = data.get('agent')
        entry_id = data.get('entry_id')
        day_of_week = int(data.get('day_of_week', -1))
        slot = get_object_or_404(
            Schedule,
            pk=data.get('schedule_slot_id'),
            is_default=True,
            day_of_week=0,
        )

        if day_of_week < 0 or day_of_week > 4:
            return JsonResponse({'error': 'Choose a weekday from the schedule.'}, status=400)

        if agent == 'grace':
            from grace.models import SocialCurriculum
            activity = get_object_or_404(SocialCurriculum, pk=entry_id)
            activity_type = activity.activity_type
        elif agent == 'patience':
            from patience.models import MotorCurriculum
            activity = get_object_or_404(MotorCurriculum, pk=entry_id)
            activity_type = activity.activity_type
        else:
            return JsonResponse({'error': 'Only Grace and Patience activities can be assigned here.'}, status=400)

        today = timezone.localdate()
        week_start = today - timedelta(days=today.weekday())
        if today.weekday() > 4:
            week_start += timedelta(days=7)
        scheduled_date = week_start + timedelta(days=day_of_week)
        if scheduled_date < today:
            return JsonResponse({'error': 'Choose today or a later day this week.'}, status=400)

        existing_entry = WeeklyPlanEntry.objects.filter(
            week_start_date=week_start,
            scheduled_date=scheduled_date,
            start_time=slot.start_time,
        ).order_by('-created_at').first()
        if existing_entry and existing_entry.activity_type == 'MEAL':
            return JsonResponse({
                'error': 'A menu meal already occupies this time. Choose another default time slot.'
            }, status=409)

        values = {
            'agent': agent,
            'title': activity.title[:200],
            'activity_type': activity_type,
            'description': activity.description,
            'is_static': False,
            'guideline_activity': slot.activity,
            'created_by': request.user,
        }
        if existing_entry:
            for field, value in values.items():
                setattr(existing_entry, field, value)
            existing_entry.save()
            entry = existing_entry
        else:
            entry = WeeklyPlanEntry.objects.create(
                week_start_date=week_start,
                scheduled_date=scheduled_date,
                start_time=slot.start_time,
                **values,
            )

        return JsonResponse({
            'success': True,
            'entry_id': entry.pk,
            'message': f'{activity.title} added to {scheduled_date:%A} at {slot.start_time.strftime("%I:%M %p").lstrip("0")}.',
        })
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        return JsonResponse({'error': str(exc) or 'Invalid schedule request.'}, status=400)


@login_required
def apply_menu_to_schedule(request):
    """Apply the current menu's meals into the weekly schedule without regenerating other activities."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        weekday_dates = [(week_start + timedelta(days=i)) for i in range(5)]

        current_menu = Menu.objects.filter(created_by=request.user, is_current=True).first()
        if not current_menu:
            current_menu = Menu.objects.filter(created_by=request.user).order_by('-created_at').first()
        if not current_menu:
            return JsonResponse({'success': False, 'error': 'No menu found. Generate a menu first.'})

        menu_data = current_menu.menu_data
        menu_week = _menu_week_for_date(menu_data, week_start)
        if not menu_week:
            return JsonResponse({
                'success': False,
                'error': 'No accepted menu is saved for this schedule week.',
            }, status=404)

        # Remove existing MEAL entries for this week
        WeeklyPlanEntry.objects.filter(
            week_start_date=week_start,
            activity_type='MEAL',
        ).delete()

        # Map display names back to schedule times via SAGE_MEAL_MAP
        meal_display_to_key = {
            'BREAKFAST': 'breakfast',
            'A.M. SNACK': 'am snack',
            'LUNCH': 'lunch',
            'P.M. SNACK': 'pm snack',
            'SUPPER': 'supper',
        }
        # Default meal times if no guideline slots exist
        default_meal_times = {
            'BREAKFAST': 8,
            'A.M. SNACK': 10,
            'LUNCH': 12,
            'P.M. SNACK': 15,
            'SUPPER': 17,
        }

        # Try to get meal times from guideline schedule
        guideline_slots = Schedule.objects.filter(is_default=False, day_of_week=0).order_by('start_time')
        meal_times = {}
        for entry in guideline_slots:
            activity_lower = _normalize_activity(entry.activity)
            for key, meal_type in SAGE_MEAL_MAP.items():
                if key in activity_lower:
                    # Find the display name for this meal_type
                    for display_name, _key in meal_display_to_key.items():
                        if SAGE_MEAL_MAP.get(_key) == meal_type:
                            meal_times[display_name] = entry.start_time.hour
                            break
                    break

        created = 0
        for meal_display, meal_data in menu_week.items():
            hour = meal_times.get(meal_display, default_meal_times.get(meal_display))
            if hour is None:
                continue

            components = meal_data.get('components', [])
            titles = meal_data.get('titles', {})

            for i, day in enumerate(weekdays):
                items = []
                for comp in components:
                    item = comp.get('items', {}).get(day, '')
                    if item:
                        items.append(item)
                description = ', '.join(items) if items else meal_display
                title = titles.get(day, meal_display)

                from datetime import time as dt_time
                WeeklyPlanEntry.objects.create(
                    week_start_date=week_start,
                    scheduled_date=weekday_dates[i],
                    start_time=dt_time(hour, 0),
                    agent='sage',
                    title=f"{meal_display} — {day}",
                    activity_type='MEAL',
                    description=description,
                    is_static=True,
                    guideline_activity=meal_display,
                    created_by=request.user,
                )
                created += 1

        return JsonResponse({'success': True, 'message': f'Applied {created} meal slots from current menu.'})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def generate_weekly_schedule(request):
    """Generate a full week of activities from the guideline schedule and save to DB."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        guideline = Schedule.objects.filter(is_default=False, day_of_week=0).order_by('start_time')
        if not guideline.exists():
            return JsonResponse({'success': False, 'error': 'Save a guideline schedule first'})

        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        weekday_dates = [(week_start + timedelta(days=i)) for i in range(5)]

        # Clear existing entries for this week
        WeeklyPlanEntry.objects.filter(week_start_date=week_start).delete()

        checked_in_children = Child.objects.filter(is_checked_in=True)

        agent_prompts = {
            'grace': GraceAgent().get_system_prompt(),
            'patience': PatienceAgent().get_system_prompt(),
        }
        rag = get_rag_context(request.user) if request.user.is_authenticated else ''

        # Group guideline slots by agent for LLM batch calls
        agent_slots = {}
        sage_slots = []
        for entry in guideline:
            agent = entry.agent or 'sage'
            if agent == 'sage':
                sage_slots.append(entry)
            else:
                if agent not in agent_slots:
                    agent_slots[agent] = []
                agent_slots[agent].append(entry)

        created_entries = []

        # --- Sage static activities ---
        for entry in sage_slots:
            activity_lower = _normalize_activity(entry.activity)

            # Check if it's a known static activity
            static_match = None
            for key, static in SAGE_STATIC_ACTIVITIES.items():
                if key in activity_lower:
                    static_match = static
                    break

            # Check if it's a meal
            meal_match = None
            for key, meal_type in SAGE_MEAL_MAP.items():
                if key in activity_lower:
                    meal_match = meal_type
                    break

            for i, day in enumerate(weekdays):
                sched_date = weekday_dates[i]
                if static_match:
                    wp = WeeklyPlanEntry.objects.create(
                        week_start_date=week_start,
                        scheduled_date=sched_date,
                        start_time=entry.start_time,
                        agent='sage',
                        title=static_match['title'],
                        activity_type=static_match['activity_type'],
                        description=static_match['description'],
                        is_static=True,
                        guideline_activity=entry.activity,
                        created_by=request.user,
                    )
                elif meal_match:
                    meal_desc = _get_menu_for_day(request.user, day, meal_match)
                    wp = WeeklyPlanEntry.objects.create(
                        week_start_date=week_start,
                        scheduled_date=sched_date,
                        start_time=entry.start_time,
                        agent='sage',
                        title=f"{entry.activity} — {day}",
                        activity_type='MEAL',
                        description=meal_desc,
                        is_static=True,
                        guideline_activity=entry.activity,
                        created_by=request.user,
                    )
                else:
                    # Generic sage admin task
                    wp = WeeklyPlanEntry.objects.create(
                        week_start_date=week_start,
                        scheduled_date=sched_date,
                        start_time=entry.start_time,
                        agent='sage',
                        title=entry.activity,
                        activity_type='ADMIN',
                        description=entry.activity,
                        is_static=True,
                        guideline_activity=entry.activity,
                        created_by=request.user,
                    )
                wp.children.set(checked_in_children)
                created_entries.append(wp)

        # --- Grace / Patience: LLM-generated activities ---
        import re as _re
        for agent_name, slots_list in agent_slots.items():
            system = agent_prompts.get(agent_name, '')
            if rag:
                system += rag

            slot_descriptions = []
            for s in slots_list:
                slot_descriptions.append(f"- {s.start_time.strftime('%I:%M %p').lstrip('0')}: {s.activity}")

            prompt = (
                f"Generate a weekly schedule (Monday through Friday) of activities. "
                f"For each day and each time slot below, suggest a DIFFERENT specific activity.\n\n"
                f"Time slots assigned to you:\n" + "\n".join(slot_descriptions) + "\n\n"
                f"Format your response EXACTLY like this for EACH activity:\n"
                f"### [Day] — [Time]\n"
                f"**Title:** [Activity name]\n"
                f"**Activity Type:** [Type]\n"
                f"**Age Range:** [Range]\n"
                f"**Description:** [Brief 1-2 sentence description]\n"
                f"**Duration:** [Minutes]\n\n"
                f"Generate all 5 days × {len(slots_list)} slot(s) = {5 * len(slots_list)} activities total. "
                f"Make each day's activities unique and varied."
            )

            try:
                response_text = get_anthropic_response(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt=system,
                    max_tokens=4096,
                )
            except Exception as e:
                response_text = ''

            # Parse response into day/time buckets
            blocks = _re.split(r'###\s+', response_text)
            parsed = {}  # {(day_name, hour): content}
            for block in blocks:
                block = block.strip()
                if not block:
                    continue
                header_match = _re.match(r'(\w+)\s*[—–-]\s*(\d{1,2}:\d{2}\s*[AaPp][Mm])', block)
                if not header_match:
                    continue
                day_name = header_match.group(1).strip().title()
                time_str = header_match.group(2).strip()
                time_match = _re.match(r'(\d{1,2}):(\d{2})\s*([AaPp][Mm])', time_str)
                if not time_match:
                    continue
                hr = int(time_match.group(1))
                ampm = time_match.group(3).upper()
                if ampm == 'PM' and hr != 12:
                    hr += 12
                elif ampm == 'AM' and hr == 12:
                    hr = 0
                content = block[header_match.end():].strip()
                parsed[(day_name, hr)] = content

            # Create entries
            for slot_entry in slots_list:
                hour = slot_entry.start_time.hour
                for i, day in enumerate(weekdays):
                    sched_date = weekday_dates[i]
                    content = parsed.get((day, hour), '')
                    title = _parse_activity_field(content, 'Title') if content else f"{slot_entry.activity} — {day}"
                    act_type = _parse_activity_field(content, 'Activity Type') if content else ''
                    desc = _parse_activity_field(content, 'Description') if content else ''

                    wp = WeeklyPlanEntry.objects.create(
                        week_start_date=week_start,
                        scheduled_date=sched_date,
                        start_time=slot_entry.start_time,
                        agent=agent_name,
                        title=title[:200] if title else slot_entry.activity,
                        activity_type=act_type[:50] if act_type else '',
                        description=desc,
                        is_static=False,
                        guideline_activity=slot_entry.activity,
                        created_by=request.user,
                    )
                    wp.children.set(checked_in_children)
                    created_entries.append(wp)

        return JsonResponse({
            'success': True,
            'message': f'Generated {len(created_entries)} activities for the week',
            'redirect': '/sage/weekly-schedule/',
        })

    except Exception as e:
        import traceback
        return JsonResponse({'success': False, 'error': str(e), 'traceback': traceback.format_exc()})


@login_required
def rate_weekly_activity(request):
    """Rate a WeeklyPlanEntry for a specific child."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        entry_id = data.get('entry_id')
        child_id = data.get('child_id')
        rating_value = int(data.get('rating', 0))

        from django.contrib.contenttypes.models import ContentType
        from enroll.models import StudentRating

        entry = WeeklyPlanEntry.objects.get(pk=entry_id)
        child = Child.objects.get(child_id=child_id)
        ct = ContentType.objects.get_for_model(WeeklyPlanEntry)

        rating, created = StudentRating.objects.update_or_create(
            child=child,
            content_type=ct,
            object_id=entry.pk,
            defaults={'rating': rating_value},
        )
        return JsonResponse({'success': True, 'rating_id': rating.pk})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def generate_attendance(request):
    checked_in_children = Child.objects.filter(is_checked_in=True)
    if checked_in_children.count() == 0:
        return render(request, 'sage/generate_attendance.html', {'error': 'No children are currently checked in.'})
    return render(request, 'sage/generate_attendance.html')

def send_report(request):
    return render(request, 'sage/send_report.html')


def _menu_week_keys(menu_data):
    return sorted(
        (key for key in menu_data if key.startswith('Week ') and key[5:].isdigit()),
        key=lambda key: int(key[5:]),
    )


def _menu_week_for_date(menu_data, week_start):
    start_value = menu_data.get('_workflow', {}).get('start_date')
    if start_value:
        menu_start = date.fromisoformat(start_value)
        days_from_start = (week_start - menu_start).days
        if days_from_start < 0 or days_from_start % 7:
            return None
        week_number = days_from_start // 7 + 1
    else:
        week_number = 1

    if week_number > 4:
        return None
    return menu_data.get(f'Week {week_number}')


def _menu_page_context(user):
    menu_record = Menu.objects.filter(created_by=user, is_current=True).first()
    if not menu_record:
        menu_record = Menu.objects.filter(created_by=user).order_by('-created_at').first()

    stored_data = menu_record.menu_data if menu_record else {}
    accepted_keys = _menu_week_keys(stored_data)
    return {
        'dishes': Dish.objects.all().order_by('-created_at'),
        'grocery_items': GroceryItem.objects.filter(added_by=user).order_by('category', 'name'),
        'initial_menu': {key: stored_data[key] for key in accepted_keys},
        'pending_week': stored_data.get('_pending_week'),
        'accepted_week_count': len(accepted_keys),
        'menu_complete': len(accepted_keys) >= 4,
        'next_week_number': min(len(accepted_keys) + 1, 4),
    }


COMPONENT_TO_CATEGORY = {
    'Vegetable': 'VEGETABLE',
    'Fruit': 'FRUIT',
    'Grain': 'GRAIN',
    'Protein': 'PROTEIN',
    'Drink': 'DRINK',
}
_MENU_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def _edit_pending_week_items(request, current_menu, stored_menu, accepted_keys, data):
    """Reroll only the specific meal/day/component cells the caller picked out,
    leaving the rest of the already-generated pending week untouched."""
    if not current_menu or '_pending_week' not in stored_menu:
        return JsonResponse({
            'error': "Generate this week's menu first, then you can change individual items."
        }, status=400)

    targets = data.get('targets', [])
    if not targets:
        return JsonResponse({'error': 'No items selected to change.'}, status=400)

    selected_item_ids = data.get('grocery_item_ids', [])
    if selected_item_ids:
        items = GroceryItem.objects.filter(added_by=request.user, id__in=selected_item_ids)
    else:
        items = GroceryItem.objects.filter(added_by=request.user)
    items_by_cat = {
        cat_code: list(items.filter(category=cat_code).values_list('name', flat=True))
        for cat_code, _ in GroceryItem.CATEGORIES
    }

    def reroll(category, current_value):
        pool = items_by_cat.get(category, [])
        if not pool:
            return ""
        choices = [v for v in pool if v != current_value] or pool
        return random.choice(choices)

    pending = stored_menu['_pending_week']
    week_menu = pending['menu']
    changed = []

    for target in targets:
        meal_type = target.get('meal_type')
        day = target.get('day')
        component_name = target.get('component')
        category = COMPONENT_TO_CATEGORY.get(component_name)
        meal_data = week_menu.get(meal_type)
        if not meal_data or not category or day not in _MENU_WEEKDAYS:
            continue
        component = next((c for c in meal_data['components'] if c['name'] == component_name), None)
        if component is None:
            continue

        new_value = reroll(category, component['items'].get(day, ''))
        component['items'][day] = new_value
        changed.append({'meal_type': meal_type, 'day': day, 'component': component_name, 'value': new_value})

        if component_name in ('Protein', 'Grain'):
            protein_comp = next((c for c in meal_data['components'] if c['name'] == 'Protein'), None)
            grain_comp = next((c for c in meal_data['components'] if c['name'] == 'Grain'), None)
            protein_val = protein_comp['items'].get(day, '') if protein_comp else ''
            grain_val = grain_comp['items'].get(day, '') if grain_comp else ''
            parts = [p for p in [protein_val, grain_val] if p]
            meal_data['titles'][day] = " and ".join(parts) if parts else "Untitled"

    if not changed:
        return JsonResponse({'error': 'None of the selected items could be changed.'}, status=400)

    stored_menu['_pending_week']['menu'] = week_menu
    current_menu.menu_data = stored_menu
    current_menu.save(update_fields=['menu_data_json', 'updated_at'])

    week_key = f"Week {pending['week_number']}"
    return JsonResponse({
        'menu': {week_key: week_menu},
        'menu_id': current_menu.pk,
        'week_number': pending['week_number'],
        'accepted_week_count': len(accepted_keys),
        'date_range': pending['date_range'],
        'changed': changed,
    })


@login_required
def generate_menu(request):
    if request.method == 'GET':
        return render(request, 'sage/generate_menu.html', _menu_page_context(request.user))

    if request.method == 'POST':
        try:
            data = json.loads(request.body.decode('utf-8'))
            selected_item_ids = data.get('grocery_item_ids', [])
            action = data.get('action', 'generate')
            if action not in ('generate', 'regenerate', 'edit_items'):
                return JsonResponse({'error': 'Invalid menu action.'}, status=400)

            today = timezone.now().date()
            default_start_date = today + timedelta(days=(7 - today.weekday()) % 7)
            current_menu = Menu.objects.filter(created_by=request.user, is_current=True).first()
            if current_menu:
                stored_menu = current_menu.menu_data
                accepted_keys = _menu_week_keys(stored_menu)
            else:
                stored_menu = {}
                accepted_keys = []

            if action == 'edit_items':
                return _edit_pending_week_items(request, current_menu, stored_menu, accepted_keys, data)

            if len(accepted_keys) >= 4:
                if current_menu and current_menu.month_year == default_start_date.strftime('%b-%y'):
                    return JsonResponse({
                        'error': 'All four weeks are accepted for this month. The monthly menu report is complete.'
                    }, status=400)
                if current_menu:
                    current_menu.is_current = False
                    current_menu.save(update_fields=['is_current'])
                current_menu = None
                stored_menu = {}
                accepted_keys = []

            if current_menu:
                workflow = stored_menu.get('_workflow', {})
                start_date = date.fromisoformat(workflow['start_date']) if workflow.get('start_date') else default_start_date
            else:
                start_date = default_start_date
                month_year = start_date.strftime('%b-%y')
                Menu.objects.filter(created_by=request.user, is_current=True).update(is_current=False)
                current_menu = Menu.objects.create(
                    title=f'Menu {month_year}',
                    provider_name=data.get('provider_name', ''),
                    provider_address=data.get('provider_address', ''),
                    month_year=month_year,
                    menu_data_json=json.dumps({}),
                    created_by=request.user,
                    is_current=True,
                )
                stored_menu = {}

            week_number = len(accepted_keys) + 1
            start_date += timedelta(weeks=week_number - 1)
            stored_menu['_workflow'] = {
                'start_date': (start_date - timedelta(weeks=week_number - 1)).isoformat(),
            }

            # Get selected grocery items grouped by category
            if selected_item_ids:
                items = GroceryItem.objects.filter(added_by=request.user, id__in=selected_item_ids)
            else:
                items = GroceryItem.objects.filter(added_by=request.user)

            if not items.exists():
                return JsonResponse({"error": "No grocery items selected. Add items to your grocery list first."}, status=400)

            items_by_cat = {}
            for cat_code, _ in GroceryItem.CATEGORIES:
                items_by_cat[cat_code] = list(items.filter(category=cat_code).values_list('name', flat=True))

            # CACFP meal pattern requirements per meal type
            # Each defines required component categories
            cacfp_patterns = {
                'BREAKFAST': {
                    'required': ['GRAIN', 'DRINK'],
                    'fruit_or_veg': True,  # 1 fruit OR vegetable
                    'protein_optional': False,
                },
                'AM_SNACK': {
                    'pick_two': ['VEGETABLE', 'FRUIT', 'GRAIN', 'PROTEIN', 'DRINK'],
                },
                'LUNCH': {
                    'required': ['PROTEIN', 'GRAIN', 'DRINK'],
                    'fruit_required': True,
                    'veg_required': True,
                },
                'PM_SNACK': {
                    'pick_two': ['VEGETABLE', 'FRUIT', 'GRAIN', 'PROTEIN', 'DRINK'],
                },
                'SUPPER': {
                    'required': ['PROTEIN', 'GRAIN', 'DRINK'],
                    'fruit_required': True,
                    'veg_required': True,
                },
            }

            meal_type_display = {
                'BREAKFAST': 'BREAKFAST',
                'AM_SNACK': 'A.M. SNACK',
                'LUNCH': 'LUNCH',
                'PM_SNACK': 'P.M. SNACK',
                'SUPPER': 'SUPPER',
            }
            meal_types_order = ['BREAKFAST', 'AM_SNACK', 'LUNCH', 'PM_SNACK', 'SUPPER']
            weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

            def pick(category):
                """Pick a random item from a category, fallback to empty string."""
                pool = items_by_cat.get(category, [])
                return random.choice(pool) if pool else ""

            week_key = f'Week {week_number}'
            week_menu = {}

            for mt in meal_types_order:
                display_name = meal_type_display[mt]
                pattern = cacfp_patterns[mt]

                meal_data = {
                    "components": [
                        {"name": "Vegetable", "items": {}},
                        {"name": "Fruit", "items": {}},
                        {"name": "Grain", "items": {}},
                        {"name": "Protein", "items": {}},
                        {"name": "Drink", "items": {}},
                    ],
                    "titles": {},
                }

                for day in weekdays:
                    veg, fruit, grain, protein, drink = "", "", "", "", ""

                    if 'pick_two' in pattern:
                        available = [c for c in pattern['pick_two'] if items_by_cat.get(c)]
                        chosen = random.sample(available, min(2, len(available))) if available else []
                        for cat in chosen:
                            val = pick(cat)
                            if cat == 'VEGETABLE': veg = val
                            elif cat == 'FRUIT': fruit = val
                            elif cat == 'GRAIN': grain = val
                            elif cat == 'PROTEIN': protein = val
                            elif cat == 'DRINK': drink = val
                    else:
                        if 'GRAIN' in pattern.get('required', []):
                            grain = pick('GRAIN')
                        if 'PROTEIN' in pattern.get('required', []):
                            protein = pick('PROTEIN')
                        if 'DRINK' in pattern.get('required', []):
                            drink = pick('DRINK') or "1% MILK"
                        if pattern.get('veg_required'):
                            veg = pick('VEGETABLE')
                        if pattern.get('fruit_required'):
                            fruit = pick('FRUIT')
                        if pattern.get('fruit_or_veg'):
                            if items_by_cat.get('FRUIT') and items_by_cat.get('VEGETABLE'):
                                if random.random() < 0.5:
                                    fruit = pick('FRUIT')
                                else:
                                    veg = pick('VEGETABLE')
                            elif items_by_cat.get('FRUIT'):
                                fruit = pick('FRUIT')
                            else:
                                veg = pick('VEGETABLE')

                    parts = [p for p in [protein, grain] if p]
                    title = " and ".join(parts) if parts else "Untitled"
                    meal_data["titles"][day] = title
                    meal_data["components"][0]["items"][day] = veg
                    meal_data["components"][1]["items"][day] = fruit
                    meal_data["components"][2]["items"][day] = grain
                    meal_data["components"][3]["items"][day] = protein
                    meal_data["components"][4]["items"][day] = drink

                week_menu[display_name] = meal_data

            end_date = start_date + timedelta(days=4)
            draft_menu = {week_key: week_menu}
            date_range = {
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
                'weeks': 1,
                'week_number': week_number,
            }
            stored_menu['_pending_week'] = {
                'week_number': week_number,
                'menu': week_menu,
                'date_range': date_range,
            }
            current_menu.menu_data = stored_menu
            current_menu.save(update_fields=['menu_data_json', 'updated_at'])

            return JsonResponse({
                'menu': draft_menu,
                'menu_id': current_menu.pk,
                'week_number': week_number,
                'accepted_week_count': len(accepted_keys),
                'date_range': date_range,
            })

        except json.JSONDecodeError as e:
            return JsonResponse({"error": f"Invalid JSON: {str(e)}"}, status=400)
        except Exception as e:
            return JsonResponse({"error": f"Error generating menu: {str(e)}"}, status=500)

@login_required
@require_http_methods(['POST'])
def accept_menu_week(request):
    menu_record = Menu.objects.filter(created_by=request.user, is_current=True).first()
    if not menu_record:
        return JsonResponse({'error': 'No menu draft is available to accept.'}, status=400)

    menu_data = menu_record.menu_data
    pending = menu_data.get('_pending_week')
    if not pending:
        return JsonResponse({'error': 'Generate a weekly menu before accepting it.'}, status=400)

    accepted_keys = _menu_week_keys(menu_data)
    week_number = int(pending.get('week_number', 0))
    if week_number != len(accepted_keys) + 1 or week_number > 4:
        return JsonResponse({'error': 'This week is not the next week awaiting acceptance.'}, status=409)

    week_menu = pending['menu']
    meal_type_codes = {
        'BREAKFAST': 'BREAKFAST',
        'A.M. SNACK': 'AM_SNACK',
        'LUNCH': 'LUNCH',
        'P.M. SNACK': 'PM_SNACK',
        'SUPPER': 'SUPPER',
    }
    component_fields = {
        'vegetable': 'vegetable',
        'fruit': 'fruit',
        'grain': 'grain',
        'protein': 'protein',
        'drink': 'drink',
    }

    from django.db import transaction

    with transaction.atomic():
        for meal_name, meal_data in week_menu.items():
            component_items = {
                component.get('name', '').lower(): component.get('items', {})
                for component in meal_data.get('components', [])
            }
            for day in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'):
                fields = {
                    field: component_items.get(component, {}).get(day, '')
                    for component, field in component_fields.items()
                }
                Dish.objects.create(meal_type=meal_type_codes[meal_name], **fields)

        menu_data[f'Week {week_number}'] = week_menu
        menu_data.pop('_pending_week', None)
        menu_record.menu_data = menu_data
        menu_record.save(update_fields=['menu_data_json', 'updated_at'])

    accepted_count = len(_menu_week_keys(menu_data))
    return JsonResponse({
        'success': True,
        'accepted_week': week_number,
        'accepted_week_count': accepted_count,
        'complete': accepted_count == 4,
        'next_week_number': min(accepted_count + 1, 4),
    })


@login_required
def current_menu(request):
    """Show accepted weeks and any pending weekly draft."""
    return render(request, 'sage/generate_menu.html', _menu_page_context(request.user))


def attendance_report(request):
    """
    Monthly attendance report per Little Steps PRD (Sage — Administration & Holistic Monitoring).
    Smart Attendance Dashboard: check-in/check-out, absence pattern visibility, family-friendly summary.
    """
    import calendar
    today = date.today()
    year, month = today.year, today.month
    last_day = calendar.monthrange(year, month)[1]
    date_range = list(range(1, last_day + 1))

    # Sage tracks attendance per Child (check-in/check-out per day)
    children = Child.objects.all().order_by('child_name')
    student_list = []
    for child in children:
        # Sage.Attendance: student=Child, date, check_in, check_out
        month_attendances = Attendance.objects.filter(
            student=child,
            date__year=year,
            date__month=month
        ).values_list('date', 'check_in')
        present_dates = {d.day for d, check_in in month_attendances if check_in}
        attendance_by_day = [day in present_dates for day in date_range]
        student_list.append({
            'name': child.child_name,
            'date_of_birth': child.date_of_birth,
            'attendance_by_day': attendance_by_day,
        })

    context = {
        'title': f'Monthly Attendance Report — {today.strftime("%B %Y")}',
        'name_header': 'Child',
        'dob_header': 'Date of Birth',
        'date_range': date_range,
        'student_list': student_list,
        'present_symbol': '✓',
        'absent_symbol': '—',
    }
    return render(request, 'sage/attendance_report.html', context)



@login_required
def search(request):
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    try:
        # Search across multiple models
        results = {
            'meals': [],
            'groceries': [],
            'documents': [],
            'students': []
        }
        
        # Search meals
        meals = Meal.objects.filter(
            name__icontains=query
        )[:5]
        for meal in meals:
            results['meals'].append({
                'id': meal.id,
                'name': meal.name,
                'type': meal.meal_type,
                'date': meal.date.strftime('%Y-%m-%d'),
                'url': reverse('sage:meal_planner')
            })
        
        # Search grocery items
        groceries = GroceryItem.objects.filter(
            name__icontains=query
        )[:5]
        for item in groceries:
            results['groceries'].append({
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'url': reverse('sage:grocery_list')
            })
        
        # Search documents
        documents = Document.objects.filter(
            title__icontains=query
        )[:5]
        for doc in documents:
            results['documents'].append({
                'id': doc.id,
                'title': doc.title,
                'type': doc.file_type,
                'url': reverse('sage:upload_documents')
            })
        
        # Search students
        students = Student.objects.filter(
            name__icontains=query
        )[:5]
        for student in students:
            results['students'].append({
                'id': student.id,
                'name': student.name,
                'url': reverse('sage:student-list')
            })
        
        return JsonResponse({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })
