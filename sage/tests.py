import json
from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from enroll.models import Child, ChildActivity, StudentRating
from grace.models import SocialCurriculum
from materalleapp.agent_base import get_agent_response
from patience.models import MotorCurriculum
from sage.models import Dish, Document, GroceryItem, Menu, Schedule, WeeklyPlanEntry
from sage.parser import VALID_CATEGORIES, categorize_with_llm


class ActivityDashboardTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='dashboard-test', password='test-password')
		self.client.force_login(self.user)

	def create_child(self, name, is_checked_in):
		return Child.objects.create(
			child_name=name,
			date_of_birth=date(2023, 1, 1),
			child_address='1 Test Street',
			parent_name='Test Parent',
			parent_address='1 Test Street',
			parent_phone='555-0100',
			parent_email='parent@example.com',
			date_of_enrollment=date(2025, 1, 1),
			date_of_withdrawal=date(2027, 1, 1),
			child_physician='Test Physician',
			child_physician_phone='555-0101',
			preferred_hospital='Test Hospital',
			hospital_phone='555-0102',
			child_dentist='Test Dentist',
			dentist_phone='555-0103',
			child_allergies='',
			signature='Test Signature',
			date_signed=date(2025, 1, 1),
			enrolled_by=self.user,
			is_checked_in=is_checked_in,
		)

	def test_attendance_and_activity_rating_include_all_children(self):
		present_child = self.create_child('Present Child', True)
		absent_child = self.create_child('Absent Child', False)
		today = date.today()
		week_start = today - timedelta(days=today.weekday())
		day_offset = today.weekday() if today.weekday() < 5 else 0
		selected_date = week_start + timedelta(days=day_offset)
		activity = WeeklyPlanEntry.objects.create(
			week_start_date=week_start,
			scheduled_date=selected_date,
			start_time=time(9, 0),
			agent='sage',
			title='Current Activity',
			created_by=self.user,
		)

		response = self.client.get(reverse('sage:activity_dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Today's Attendance")
		self.assertContains(response, 'Present Child')
		self.assertContains(response, 'Absent Child')
		self.assertContains(response, 'Current Activity')
		rating_response = self.client.post(
			reverse('sage:rate_weekly_activity'),
			data=json.dumps({
				'entry_id': activity.pk,
				'child_id': absent_child.child_id,
				'rating': 3,
			}),
			content_type='application/json',
		)

		self.assertEqual(rating_response.status_code, 200)
		self.assertTrue(rating_response.json()['success'])
		self.assertEqual(
			StudentRating.objects.get(child=absent_child, object_id=activity.pk).rating,
			3,
		)

	def test_agent_dashboards_render_roster_and_rating_actions(self):
		child = self.create_child('Roster Child', False)
		agent_activities = (
			('grace:index', 'grace', SocialCurriculum.objects.create(title='Grace activity')),
			('patience:index', 'patience', MotorCurriculum.objects.create(title='Patience activity')),
			('sage:index', 'sage', Dish.objects.create(title='Sage activity')),
		)
		for route_name, page, activity in agent_activities:
			with self.subTest(route_name=route_name):
				response = self.client.get(reverse(route_name))
				self.assertEqual(response.status_code, 200)
				self.assertContains(response, 'Roster Child')
				self.assertContains(response, 'participant-checkin')
				self.assertContains(response, 'participant-rate')
				if page in ('grace', 'patience'):
					self.assertContains(response, 'schedule-activity-dialog')
					self.assertContains(response, 'agentActivityGenerated')
				else:
					self.assertNotContains(response, 'schedule-activity-dialog')
				self.assertContains(response, 'participant-row')
				self.assertNotContains(response, 'Activity ratings')
				self.assertNotContains(response, 'childCarousel')
				self.assertEqual(response.context['current_activity_id'], activity.pk)

		checkin_response = self.client.post(reverse(
			'enroll:check_in_out', kwargs={'child_id': child.child_id, 'action': 'in'}
		))
		self.assertEqual(checkin_response.status_code, 200)
		self.assertTrue(checkin_response.json()['success'])

		for _, page, activity in agent_activities:
			with self.subTest(page=page):
				rating_response = self.client.post(reverse('enroll:rate_student'), {
					'page': page,
					'child_id': child.child_id,
					'rate_value': 'like',
					'object_id': activity.pk,
				})
				self.assertEqual(rating_response.status_code, 200)
				self.assertEqual(rating_response.json()['status'], 'success')
				self.assertTrue(StudentRating.objects.filter(
					child=child,
					content_type=ContentType.objects.get_for_model(activity),
					object_id=activity.pk,
					rating=3,
				).exists())

	def test_generated_agent_activity_can_be_assigned_to_a_child_and_date(self):
		child = self.create_child('Scheduled Child', True)
		activity = SocialCurriculum.objects.create(
			title='Name That Feeling',
			activity_type='EMOTIONAL',
			description='Name a feeling together.',
			created_by=self.user,
		)
		scheduled_date = date.today() + timedelta(days=1)

		response = self.client.post(
			reverse('enroll:schedule_activity'),
			data=json.dumps({
				'child_id': child.child_id,
				'title': activity.title,
				'activity_type': activity.activity_type,
				'agent': 'grace',
				'scheduled_date': scheduled_date.isoformat(),
				'description': activity.description,
				'entry_id': activity.pk,
			}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		scheduled = ChildActivity.objects.get(pk=response.json()['activity_id'])
		self.assertEqual(scheduled.child, child)
		self.assertEqual(scheduled.scheduled_date, scheduled_date)
		self.assertEqual(scheduled.curriculum_entry, activity)


class AgentFallbackTests(SimpleTestCase):
	@patch('materalleapp.agent_base.get_anthropic_response', side_effect=TimeoutError)
	def test_timeout_returns_the_matching_canned_answer_for_each_agent(self, llm_call):
		cases = (
			('grace', 'Help with sharing and turns', 'Roll and Take Turns'),
			('patience', 'Suggest a gross motor movement', 'Animal Movement Path'),
			('sage', 'Can you suggest a healthy meal?', 'balanced meal'),
		)
		for agent_name, prompt, expected_answer in cases:
			with self.subTest(agent_name=agent_name):
				response, fallback_used = get_agent_response(
					agent_name,
					[{'role': 'user', 'content': prompt}],
					'agent system prompt',
				)
				self.assertTrue(fallback_used)
				self.assertIn('LLM is not responding', response)
				self.assertIn(expected_answer, response)

	@patch('materalleapp.agent_base.get_anthropic_response', return_value=' ')
	def test_empty_response_uses_the_canned_fallback(self, llm_call):
		response, fallback_used = get_agent_response(
			'sage',
			[{'role': 'user', 'content': 'Tell me about learning'}],
		)

		self.assertTrue(fallback_used)
		self.assertIn('LLM is not responding', response)
		self.assertIn('play-based activity', response)


class GroceryListUploadTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='grocery-test', password='test-password')
		self.client.force_login(self.user)

	@patch('sage.parser.parse_document', return_value={
		'VEGETABLE': ['Carrots'],
		'PROTEIN': ['Beans'],
		'DRINK': ['Water'],
		'OTHER': ['Salt'],
		'CONFLICTS': [],
	})
	def test_uploaded_items_populate_current_grocery_list(self, parse_document):
		response = self.client.post(
			reverse('sage:upload_grocery_list'),
			{'grocery_file': SimpleUploadedFile('list.txt', b'Salt\\nCarrots')},
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertEqual(response.json()['createdCount'], 2)
		self.assertEqual(GroceryItem.objects.filter(added_by=self.user).count(), 2)

		list_response = self.client.get(reverse('sage:grocery_list'))
		self.assertContains(list_response, 'Carrots')
		self.assertContains(list_response, 'Beans')
		self.assertNotContains(list_response, 'Water')
		self.assertNotContains(list_response, 'Salt')
		self.assertNotContains(list_response, 'other-item')
		self.assertEqual(set(GroceryItem.objects.values_list('category', flat=True)), {'VEGETABLE', 'PROTEIN'})


class GroceryParserTests(SimpleTestCase):
	@patch('sage.parser.get_anthropic_response', return_value=(
		'{"VEGETABLES":["carrots"],"FRUIT":["apples"],"PROTEIN":["beans"],'
		'"GRAIN":["rice"],"DRINK":["water"],"OTHER":["salt"]}'
	))
	def test_llm_output_is_limited_to_four_grocery_categories(self, llm_response):
		categorized = categorize_with_llm(['carrots', 'apples', 'beans', 'rice', 'water'])

		self.assertEqual(set(categorized), set(VALID_CATEGORIES))
		self.assertEqual(categorized['VEGETABLE'], ['carrots'])
		self.assertEqual(categorized['FRUIT'], ['apples'])
		self.assertEqual(categorized['PROTEIN'], ['beans'])
		self.assertEqual(categorized['GRAIN'], ['rice'])


class CurrentMenuTests(TestCase):
	def test_current_menu_renders_saved_menu_without_url_payload(self):
		user = User.objects.create_user(username='menu-test', password='test-password')
		self.client.force_login(user)
		Menu.objects.create(
			title='Menu Test',
			provider_name='Test Center',
			provider_address='1 Test Street',
			month_year='Sep-26',
			menu_data_json=json.dumps({'Week 1': {'LUNCH': {'titles': {'Monday': 'Beans and Rice'}}}}),
			created_by=user,
			is_current=True,
		)

		response = self.client.get(reverse('sage:current_menu'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Beans and Rice')


class SageDocumentContextTests(TestCase):
	def test_sage_chat_includes_uploaded_document_context(self):
		user = User.objects.create_user(username='sage-doc-test', password='test-password')
		self.client.force_login(user)
		Document.objects.create(
			title='classroom-guide.txt',
			file=SimpleUploadedFile('classroom-guide.txt', b'Uploaded classroom notes'),
			uploaded_by=user,
			analysis='Serve a vegetable, fruit, grain, and protein at lunch.',
		)

		async def return_prompt_context(agent, message, context):
			return agent.system_prompt

		with patch('sage.views.SageAgent.get_response', new=return_prompt_context):
			response = self.client.post(
				reverse('sage:sage_interaction'),
				data=json.dumps({'message': 'What should we serve at lunch?'}),
				content_type='application/json',
			)

		self.assertEqual(response.status_code, 200)
		self.assertIn('Serve a vegetable, fruit, grain, and protein at lunch.', response.json()['response'])


class MenuWeekWorkflowTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='weekly-menu-test', password='test-password')
		self.client.force_login(self.user)
		self.grocery_item_ids = [
			GroceryItem.objects.create(name=name, category=category, added_by=self.user).pk
			for category, name in (
				('VEGETABLE', 'Carrots'),
				('FRUIT', 'Apples'),
				('GRAIN', 'Rice'),
				('PROTEIN', 'Beans'),
				('DRINK', 'Milk'),
			)
		]

	def generate_week(self, action):
		return self.client.post(
			reverse('sage:generate_menu'),
			data=json.dumps({'action': action, 'grocery_item_ids': self.grocery_item_ids}),
			content_type='application/json',
		)

	def test_weeks_are_regenerable_then_accepted_into_monthly_report(self):
		first_draft = self.generate_week('generate')
		self.assertEqual(first_draft.status_code, 200)
		self.assertEqual(first_draft.json()['week_number'], 1)
		menu_record = Menu.objects.get(created_by=self.user, is_current=True)
		self.assertNotIn('Week 1', menu_record.menu_data)
		self.assertIn('_pending_week', menu_record.menu_data)
		self.assertEqual(Dish.objects.count(), 0)

		regenerated = self.generate_week('regenerate')
		self.assertEqual(regenerated.status_code, 200)
		self.assertEqual(regenerated.json()['week_number'], 1)
		self.assertEqual(Dish.objects.count(), 0)

		for expected_week in range(1, 5):
			if expected_week > 1:
				response = self.generate_week('generate')
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.json()['week_number'], expected_week)

			accepted = self.client.post(reverse('sage:accept_menu_week'))
			self.assertEqual(accepted.status_code, 200)
			self.assertEqual(accepted.json()['accepted_week'], expected_week)
			self.assertEqual(accepted.json()['complete'], expected_week == 4)

		menu_record.refresh_from_db()
		self.assertEqual(
			[key for key in menu_record.menu_data if key.startswith('Week ')],
			['Week 1', 'Week 2', 'Week 3', 'Week 4'],
		)
		self.assertNotIn('_pending_week', menu_record.menu_data)
		self.assertEqual(Dish.objects.count(), 100)
		self.assertEqual(self.generate_week('generate').status_code, 400)

		preview = self.client.get(reverse('sage:current_menu'))
		self.assertEqual(preview.status_code, 200)
		self.assertEqual(preview.context['accepted_week_count'], 4)
		self.assertTrue(preview.context['menu_complete'])


class ApplyMenuToScheduleTests(TestCase):
	def test_apply_menu_uses_the_week_matching_the_schedule_date(self):
		user = User.objects.create_user(username='menu-schedule-test', password='test-password')
		self.client.force_login(user)
		week_start = date.today() - timedelta(days=date.today().weekday())
		menu_start = week_start - timedelta(weeks=1)
		weekdays = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday')

		def week_meals(prefix):
			return {
				'LUNCH': {
					'components': [{
						'name': 'Protein',
						'items': {day: f'{prefix} {day}' for day in weekdays},
					}],
					'titles': {day: f'{prefix} {day}' for day in weekdays},
				}
			}

		Menu.objects.create(
			title='Weekly Menu',
			provider_name='Test Center',
			provider_address='1 Test Street',
			month_year=menu_start.strftime('%b-%y'),
			menu_data_json=json.dumps({
				'_workflow': {'start_date': menu_start.isoformat()},
				'Week 1': week_meals('First Week'),
				'Week 2': week_meals('Second Week'),
			}),
			created_by=user,
			is_current=True,
		)

		response = self.client.post(reverse('sage:apply_menu_to_schedule'))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		monday_meal = WeeklyPlanEntry.objects.get(
			week_start_date=week_start,
			scheduled_date=week_start,
			activity_type='MEAL',
		)
		self.assertEqual(monday_meal.description, 'Second Week Monday')


class AssignChatActivityToScheduleTests(TestCase):
	def test_chat_activity_uses_selected_default_time_slot_without_child(self):
		user = User.objects.create_user(username='schedule-slot-test', password='test-password')
		self.client.force_login(user)
		default_slot = Schedule.objects.create(
			start_time=time(10, 0),
			end_time=time(11, 0),
			activity='Movement activity',
		agent='patience',
			day_of_week=0,
			is_default=True,
		)
		activity = MotorCurriculum.objects.create(
			title='Texture Discovery',
			activity_type='SENSORY',
			description='Explore several textures.',
		)
		today = date.today()
		day_of_week = today.weekday() if today.weekday() < 5 else 0
		week_start = today - timedelta(days=today.weekday())
		if today.weekday() > 4:
			week_start += timedelta(days=7)

		response = self.client.post(
			reverse('sage:assign_chat_activity'),
			data=json.dumps({
				'agent': 'patience',
				'entry_id': activity.pk,
				'day_of_week': day_of_week,
				'schedule_slot_id': default_slot.pk,
			}),
			content_type='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		entry = WeeklyPlanEntry.objects.get(pk=response.json()['entry_id'])
		self.assertEqual(entry.week_start_date, week_start)
		self.assertEqual(entry.scheduled_date, week_start + timedelta(days=day_of_week))
		self.assertEqual(entry.start_time, time(10, 0))
		self.assertEqual(entry.title, activity.title)
		self.assertEqual(entry.agent, 'patience')
		self.assertFalse(entry.children.exists())
