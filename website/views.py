from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView, TemplateView, View
from django.urls import reverse_lazy, reverse
from django.contrib.auth.views import LoginView
from django.http import HttpResponseRedirect, HttpResponseForbidden, JsonResponse, HttpResponse
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from .forms import CustomUserCreationForm
from enroll.forms import StudentEnrollmentForm
from enroll.models import Student, Child, AttendanceLog
from .serializers import UserSerializer, CustomTokenObtainPairSerializer
from .models import LearningSession, Interaction, Document, UserProfile, LLMSettings
from materalleapp.user_utils import get_role, is_parent, is_staff_role
from django.utils import timezone
from datetime import date, datetime
import csv
import json
from asgiref.sync import sync_to_async
from django.contrib.auth.models import User
from django.db.models import Q
import os

# Create your views here.
class LandingPageView(TemplateView):
    """Landing page view for the website."""
    template_name = 'landing.html'

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

class HomeView(LoginRequiredMixin, TemplateView):
    """Home page view for authenticated users."""
    template_name = 'website/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_session'] = LearningSession.objects.filter(
            user=self.request.user,
            end_time__isnull=True
        ).first()
        return context

class StudentListView(LoginRequiredMixin, View):
    """View for listing all students."""
    def get(self, request):
        if is_parent(request.user):
            students = Student.objects.filter(enrolled_by=request.user)
        else:
            students = Student.objects.all()
        return render(request, 'website/student_list.html', {'students': students})

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
        elif attendance.check_out is None:
            attendance.check_out = timezone.now()

        attendance.save()
        return redirect('website:student-list')

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
async def upload_documents(request):
    """Handle document uploads and processing."""
    if request.method == 'POST':
        files = request.FILES.getlist('documents')
        uploaded_files = []
        
        try:
            for file in files:
                doc = await sync_to_async(Document.objects.create)(
                    title=file.name,
                    file=file,
                    uploaded_by=request.user,
                    file_type=file.name.split('.')[-1].lower(),
                    file_size=file.size
                )
                
                uploaded_files.append({
                    'name': doc.title,
                    'size': doc.file_size,
                    'type': doc.file_type,
                    'id': doc.id
                })
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully uploaded {len(uploaded_files)} files',
                'files': uploaded_files
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error uploading files: {str(e)}'
            })
    
    # For GET requests, show uploaded documents
    documents = await sync_to_async(list)(Document.objects.filter(uploaded_by=request.user).order_by('-uploaded_at'))
    return await sync_to_async(render)(
        request, 
        'website/upload_documents.html',
        {'documents': documents}
    )

@login_required
def delete_file(request, file_id):
    """Delete a document."""
    if request.method == 'DELETE':
        try:
            doc = get_object_or_404(Document, id=file_id, uploaded_by=request.user)
            doc.delete()
            return JsonResponse({'success': True})
        except Document.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'File not found'})
    return JsonResponse({'success': False, 'error': 'Invalid method'})

@login_required
def search(request):
    """Global search functionality across multiple models."""
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'results': []})
    
    try:
        results = {
            'students': [],
            'documents': []
        }
        
        # Filter students based on user role
        if is_parent(request.user):
            students = Student.objects.filter(
                Q(enrolled_by=request.user) & 
                (Q(first_name__icontains=query) | Q(last_name__icontains=query))
            )
        else:
            students = Student.objects.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query)
            )

        for student in students:
            results['students'].append({
                'id': student.id,
                'name': f"{student.first_name} {student.last_name}",
                'url': reverse('website:student-detail', args=[student.id])
            })
        
        # Search documents
        documents = Document.objects.filter(
            uploaded_by=request.user,
            title__icontains=query
        )[:5]
        for doc in documents:
            results['documents'].append({
                'id': doc.id,
                'title': doc.title,
                'type': doc.file_type,
                'url': reverse('website:document-detail', args=[doc.id])
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

@ensure_csrf_cookie
@csrf_protect
def register(request):
    """Handle user registration with role-based redirections."""
    if request.user.is_authenticated:
        messages.info(request, 'You are already registered and logged in.')
        return redirect('website:home')

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    # Remove automatic login
                    # login(request, user)
                    
                    # Create initial learning session
                    LearningSession.objects.create(user=user)
                    
                    # Update success message to inform about login
                    messages.success(request, f'Account for {user.first_name} has been created successfully! Please log in to continue.')
                    
                    # Redirect to login page instead of role-based redirect
                    return redirect('website:login')
            except Exception as e:
                messages.error(request, f'An error occurred during registration: {str(e)}. Please try again.')
                return render(request, 'register.html', {'form': form})
        else:
            # Form validation failed - errors are in form.errors
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'register.html', {'form': form})

class CustomLoginView(LoginView):
    """Custom login view with role-based redirections and session management."""
    template_name = 'login.html'

    def post(self, request, *args, **kwargs):
        import logging
        logger = logging.getLogger('django.request')
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Login POST failed: {e}", exc_info=True)
            messages.error(request, "An error occurred during login. Please try again.")
            return redirect('website:login')

    def form_valid(self, form):
        response = super().form_valid(form)
        # Create new learning session on login
        try:
            if not hasattr(self.request.user, 'userprofile'):
                UserProfile.objects.create(user=self.request.user)
            LearningSession.objects.create(user=self.request.user)
        except Exception as e:
            import logging
            logging.getLogger('django.request').error(f"Login post-auth error: {e}", exc_info=True)
        return response

    def get_success_url(self):
        """Determine redirect URL based on user role."""
        role = get_role(self.request.user)
        if role == 'ADMINISTRATOR':
            return reverse_lazy('admin:index')
        elif role == 'CAREGIVER':
            return reverse_lazy('sage:index')
        else:  # PARENT or default
            return reverse_lazy('enroll:index')

@login_required
def enroll_request(request):
    """Handle student enrollment requests."""
    if not is_staff_role(request.user):
        messages.error(request, 'Only administrators and caregivers can enroll students.')
        return redirect('website:home')

    if request.method == "POST":
        form = StudentEnrollmentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    student = form.save(commit=False)
                    student.enrolled_by = request.user
                    student.save()
                    messages.success(request, f'Student {student.child_name} has been enrolled successfully!')
                    return redirect('enroll:index')
            except Exception as e:
                messages.error(request, 'An error occurred during enrollment. Please try again.')
                return render(request, "enroll/enroll.html", {'form': form})
    else:
        form = StudentEnrollmentForm()
    
    return render(request, "enroll/enroll.html", {'form': form})

@login_required
def end_session(request):
    """End the current learning session."""
    try:
        current_session = LearningSession.objects.filter(
            user=request.user,
            end_time__isnull=True
        ).latest('start_time')
        current_session.end_time = timezone.now()
        current_session.save()
        messages.info(request, 'Your session has been ended.')
    except LearningSession.DoesNotExist:
        pass
    
    logout(request)
    return redirect('website:landing')

class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom token view for JWT authentication."""
    serializer_class = CustomTokenObtainPairSerializer

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    """API endpoint for user registration."""
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        try:
            with transaction.atomic():
                user = serializer.save()
                LearningSession.objects.create(user=user)
                return Response(
                    {
                        'message': 'User registered successfully',
                        'user': serializer.data
                    },
                    status=status.HTTP_201_CREATED
                )
        except Exception as e:
            return Response(
                {'error': 'An error occurred during registration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_info(request):
    """API endpoint to get current user information."""
    user = request.user
    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': get_role(user),
    })

@login_required
def profile(request):
    """View and edit user profile."""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, instance=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    user = form.save()
                    messages.success(request, 'Your profile has been updated successfully.')
                    return redirect('website:profile')
            except Exception as e:
                messages.error(request, 'An error occurred while updating your profile.')
    else:
        form = CustomUserCreationForm(instance=request.user)
    
    return render(request, 'website/profile.html', {'form': form})

@login_required
def session_history(request):
    """View learning session history."""
    sessions = LearningSession.objects.filter(user=request.user).order_by('-start_time')
    return render(request, 'website/session_history.html', {'sessions': sessions})

@login_required
def interaction_history(request):
    """View user interaction history."""
    interactions = Interaction.objects.filter(user=request.user).order_by('-timestamp')
    return render(request, 'website/interaction_history.html', {'interactions': interactions})

@login_required
def home(request):
    role = get_role(request.user)
    context = {
        'user': request.user,
        'is_parent': role == 'PARENT',
        'is_admin': role == 'ADMINISTRATOR',
        'is_caregiver': role == 'CAREGIVER',
    }
    return render(request, 'website/home.html', context)


@login_required
def toggle_llm_backend(request):
    """Toggle the LLM backend between Anthropic and Ollama."""
    from materalleapp.agent_base import get_llm_backend, set_llm_backend, get_ollama_model, DEFAULT_ANTHROPIC_MODEL

    if request.method == 'POST':
        current = get_llm_backend()
        new_backend = 'anthropic' if current == 'ollama' else 'ollama'
        set_llm_backend(new_backend)
        model = get_ollama_model() if new_backend == 'ollama' else DEFAULT_ANTHROPIC_MODEL
        return JsonResponse({'success': True, 'backend': new_backend, 'model': model})

    backend = get_llm_backend()
    model = get_ollama_model() if backend == 'ollama' else DEFAULT_ANTHROPIC_MODEL
    return JsonResponse({'backend': backend, 'model': model})


@login_required
def llm_settings(request):
    """LLM settings page — choose backend, Ollama model, or Anthropic API key."""
    if not is_staff_role(request.user):
        return HttpResponseForbidden("Only administrators and caregivers can access settings.")

    settings_obj = LLMSettings.get_settings()

    if request.method == 'POST':
        backend = request.POST.get('backend', 'anthropic')
        anthropic_api_key = request.POST.get('anthropic_api_key', '').strip()
        ollama_base_url = request.POST.get('ollama_base_url', 'http://localhost:11434').strip()
        ollama_model = request.POST.get('ollama_model', 'llama3').strip()
        local_api_url = request.POST.get('local_api_url', '').strip()
        local_model = request.POST.get('local_model', '').strip()

        settings_obj.backend = backend
        settings_obj.anthropic_api_key = anthropic_api_key
        settings_obj.ollama_base_url = ollama_base_url
        settings_obj.ollama_model = ollama_model
        settings_obj.local_api_url = local_api_url
        settings_obj.local_model = local_model
        settings_obj.save()

        from materalleapp.agent_base import set_llm_backend
        set_llm_backend(backend)

        messages.success(request, 'LLM settings updated.')
        return redirect('website:llm_settings')

    # Try to fetch available Ollama models
    ollama_models = []
    try:
        import httpx
        resp = httpx.get(f"{settings_obj.ollama_base_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            ollama_models = [m['name'] for m in resp.json().get('models', [])]
    except Exception:
        pass

    # System health checks
    health = _run_health_checks(settings_obj)
    health_rows = [
        ('django', 'Django Server', health.get('django', 'error')),
        ('database', 'Database (PostgreSQL)', health.get('database', 'error')),
        ('llm', f'LLM — {health.get("llm_backend", settings_obj.backend)}', health.get('llm', 'error')),
    ]

    return render(request, 'website/llm_settings.html', {
        'settings': settings_obj,
        'ollama_models': ollama_models,
        'health_rows': health_rows,
    })


@login_required
def system_health_detail(request):
    """Troubleshoot page for a specific service."""
    if not is_staff_role(request.user):
        return HttpResponseForbidden("Only administrators and caregivers can access this page.")

    service = request.GET.get('service', 'django')
    diagnostics = _run_diagnostics(service)
    settings_obj = LLMSettings.get_settings()
    health = _run_health_checks(settings_obj)
    status_val = health.get(service, 'error')

    SERVICE_META = {
        'django': {
            'title': 'Django Server',
            'description': 'The Django application server handles all API requests, agent chat, and business logic.',
            'tips': [
                'Ensure the Django server is running: python manage.py runserver 8000',
                'Check that DJANGO_SETTINGS_MODULE is set correctly',
                'Verify .env has valid DB credentials and ANTHROPIC_API_KEY',
                'Check the terminal for Django error output',
            ],
        },
        'database': {
            'title': 'Database (PostgreSQL)',
            'description': 'PostgreSQL stores user accounts, children, attendance, grocery lists, schedules, and chat sessions.',
            'tips': [
                'Ensure PostgreSQL is running: pg_isready or docker ps',
                'Verify DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD in .env',
                'Try connecting manually: psql -h localhost -U postgres -d materalle_db',
                'If using Docker: docker-compose up db',
                'Check for pending migrations: python manage.py showmigrations',
            ],
        },
        'llm': {
            'title': f'LLM — {settings_obj.backend}',
            'description': 'The language model backend powers all AI agent conversations (Grace, Patience, Sage).',
            'tips': [
                'For Ollama: ensure it is running (ollama serve) and the model is pulled (ollama pull llama3)',
                'For LM Studio: start the local server and load a model',
                'For vLLM: start with vllm serve <model>',
                'For Anthropic: verify your API key is set in Settings or .env',
                'Check the URL and port match your local server configuration',
            ],
        },
    }

    meta = SERVICE_META.get(service, SERVICE_META['django'])
    all_passing = all(d['ok'] for d in diagnostics)
    fail_count = sum(1 for d in diagnostics if not d['ok'])
    status_colors = {'ok': '#22c55e', 'warning': '#eab308', 'error': '#ef4444'}
    status_labels = {'ok': 'Operational', 'warning': 'Degraded', 'error': 'Offline'}

    return render(request, 'website/system_health_detail.html', {
        'service': service,
        'meta': meta,
        'diagnostics': diagnostics,
        'all_passing': all_passing,
        'fail_count': fail_count,
        'status_color': status_colors.get(status_val, status_colors['error']),
        'status_label': status_labels.get(status_val, 'Unknown'),
    })


def _run_health_checks(settings_obj):
    """Run system health checks — mirrors api/settings_views.py."""
    import httpx as _httpx
    from django.db import connection as _conn
    from django.conf import settings as _django_settings

    checks = {}

    try:
        _conn.ensure_connection()
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'error'

    checks['django'] = 'ok'

    backend = settings_obj.backend
    checks['llm_backend'] = backend
    try:
        if backend == 'anthropic':
            if not settings_obj.anthropic_api_key and not getattr(_django_settings, 'ANTHROPIC_API_KEY', ''):
                checks['llm'] = 'warning'
            else:
                checks['llm'] = 'ok'
        elif backend == 'ollama':
            url = settings_obj.ollama_base_url or 'http://localhost:11434'
            r = _httpx.get(f'{url}/api/tags', timeout=3.0)
            checks['llm'] = 'ok' if r.status_code == 200 else 'error'
        else:
            url = settings_obj.local_api_url or 'http://localhost:1234'
            r = _httpx.get(f'{url}/v1/models', timeout=3.0)
            checks['llm'] = 'ok' if r.status_code == 200 else 'error'
    except Exception:
        checks['llm'] = 'error'

    return checks


def _run_diagnostics(service):
    """Run detailed diagnostics for a service."""
    from django.db import connection as _conn
    results = []

    if service == 'django':
        results.append({'name': 'Server responding', 'ok': True, 'detail': 'Django is handling this request'})
        try:
            from django.conf import settings as s
            results.append({'name': 'DEBUG mode', 'ok': True, 'detail': f'DEBUG={s.DEBUG}'})
        except Exception as e:
            results.append({'name': 'Settings accessible', 'ok': False, 'detail': str(e)})
        try:
            _conn.ensure_connection()
            results.append({'name': 'Database connection', 'ok': True, 'detail': 'Django can connect to the database'})
        except Exception as e:
            results.append({'name': 'Database connection', 'ok': False, 'detail': str(e)})
        try:
            LLMSettings.get_settings()
            results.append({'name': 'ORM query', 'ok': True, 'detail': 'LLMSettings table readable'})
        except Exception as e:
            results.append({'name': 'ORM query', 'ok': False, 'detail': str(e)})

    elif service == 'database':
        try:
            _conn.ensure_connection()
            results.append({'name': 'Connection', 'ok': True, 'detail': 'PostgreSQL connection established'})
        except Exception as e:
            results.append({'name': 'Connection', 'ok': False, 'detail': str(e)})
        try:
            count = User.objects.count()
            results.append({'name': 'Users table', 'ok': True, 'detail': f'{count} user(s) in database'})
        except Exception as e:
            results.append({'name': 'Users table', 'ok': False, 'detail': str(e)})
        try:
            count = LearningSession.objects.count()
            results.append({'name': 'Sessions table', 'ok': True, 'detail': f'{count} session(s)'})
        except Exception as e:
            results.append({'name': 'Sessions table', 'ok': False, 'detail': str(e)})
        try:
            from django.core.management import call_command
            from io import StringIO
            out = StringIO()
            call_command('showmigrations', '--list', stdout=out)
            unapplied = out.getvalue().count('[ ]')
            if unapplied:
                results.append({'name': 'Migrations', 'ok': False, 'detail': f'{unapplied} unapplied migration(s)'})
            else:
                results.append({'name': 'Migrations', 'ok': True, 'detail': 'All migrations applied'})
        except Exception as e:
            results.append({'name': 'Migrations', 'ok': False, 'detail': str(e)})

    elif service == 'llm':
        s = LLMSettings.get_settings()
        results.append({'name': 'Settings loaded', 'ok': True, 'detail': f'Backend: {s.backend}'})
        health = _run_health_checks(s)
        llm_ok = health.get('llm') == 'ok'
        results.append({
            'name': 'Server reachable',
            'ok': llm_ok,
            'detail': f'{s.backend} is responding' if llm_ok else f'{s.backend} is not reachable',
        })
        try:
            from materalleapp.agent_base import get_anthropic_response
            reply = get_anthropic_response(
                [{"role": "user", "content": "Say OK"}],
                max_tokens=10,
                system_prompt="Reply with only OK",
            )
            results.append({'name': 'Test inference', 'ok': bool(reply), 'detail': f'Response: {reply[:80]}'})
        except Exception as e:
            results.append({'name': 'Test inference', 'ok': False, 'detail': str(e)})

    return results