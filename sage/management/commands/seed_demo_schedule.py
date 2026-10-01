"""Seed a full demo week: guideline slots, Grace/Patience activities, and menu meals.

Offline stand-in for the LLM-backed `generate_weekly_schedule` view, so
/sage/weekly-schedule/ renders a complete week without an API key.
"""

import json
from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from enroll.models import Child
from sage.models import Menu, Schedule, WeeklyPlanEntry
from sage.views import (
    SAGE_MEAL_MAP,
    SAGE_STATIC_ACTIVITIES,
    _menu_week_for_date,
    _normalize_activity,
)

WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

# (hour, activity label, agent) — one slot per hour, since the weekly grid
# renders a single entry per day/hour cell.
GUIDELINE_SLOTS = [
    (7, 'Drop Off', 'sage'),
    (8, 'Breakfast', 'sage'),
    (9, 'Morning Circle', 'grace'),
    (10, 'A.M. Snack', 'sage'),
    (11, 'Outdoor Gross Motor', 'patience'),
    (12, 'Lunch', 'sage'),
    (13, 'Quiet Time & Self-Regulation', 'grace'),
    (14, 'Fine Motor Workshop', 'patience'),
    (15, 'P.M. Snack', 'sage'),
    (16, 'Afternoon Social Play', 'grace'),
    (17, 'Pick Up', 'sage'),
]

# Consumed slot-major (each slot takes the next five, one per weekday), so the
# ordering here lines up with the Grace slots in GUIDELINE_SLOTS.
GRACE_ACTIVITIES = [
    ('Hello Song & Feelings Check-In', 'EMOTIONAL',
     'Children greet each person by name, then point to a feelings face showing how they arrived today. '
     'The teacher names each emotion out loud.'),
    ('Our Classroom Promises', 'COMMUNICATION',
     'Review the three classroom promises with hand motions, then invite each child to say one way they '
     'will keep a promise today.'),
    ('Story Circle: Helping Hands', 'EMPATHY',
     'Read a short picture book about a character who helps a friend, pausing to ask how the friend might feel.'),
    ('Pass the Talking Stone', 'SHARING',
     'Children pass a smooth stone around the circle; only the holder speaks while everyone else practises listening.'),
    ('Kindness Wall', 'EMPATHY',
     'Each child names one kind thing a classmate did this week, and the teacher writes it on a paper heart '
     'for the kindness wall.'),

    ('Balloon Belly Breathing', 'SELF_REG',
     'Children lie down with a small beanbag on the belly and watch it rise and fall through five slow breaths.'),
    ('Calm Down Corner Tour', 'SELF_REG',
     'Walk through the calm-down corner tools one at a time and let each child practise choosing the one that helps them.'),
    ('Body Scan Rest', 'SELF_REG',
     'A guided head-to-toe relax with soft music playing, squeezing and releasing each body part in turn.'),
    ('Glitter Jar Settling', 'SELF_REG',
     'Shake a glitter jar and watch it settle, connecting the swirl to big feelings and the stillness to a calm body.'),
    ('Quiet Choice Time', 'SELF_REG',
     'Children independently choose a book, puzzle, or drawing and work quietly for the full rest period.'),

    ('Two-Friend Block Build', 'SOCIAL_PLAY',
     'Pairs build a single tower from one shared bin of blocks, negotiating who places each piece.'),
    ('Turn-Taking Train', 'SHARING',
     'Children take turns adding a car to a shared train track, using a sand timer to mark the end of each turn.'),
    ('Dramatic Play: Family Kitchen', 'SOCIAL_PLAY',
     'Open the kitchen centre and support children in assigning roles and playing out a shared mealtime story.'),
    ('Problem-Solving Puppets', 'CONFLICT',
     'Puppets act out a disagreement over a toy and children suggest fair ways to solve it.'),
    ('Parachute Together', 'SOCIAL_PLAY',
     'The whole group lifts and lowers a parachute on a shared count, practising moving as one team.'),
]

PATIENCE_ACTIVITIES = [
    ('Animal Walk Relay', 'GROSS',
     'Children bear-crawl, bunny-hop, and crab-walk between two cones, changing animal at each turn.'),
    ('Bean Bag Toss Targets', 'HAND_EYE',
     'Underhand toss bean bags into hoops set at increasing distances.'),
    ('Balance Beam Line Walk', 'BALANCE',
     'Heel-to-toe walk along a low beam or chalk line with arms out for balance.'),
    ('Ball Roll & Catch Partners', 'HAND_EYE',
     'Seated partners roll a large ball back and forth, then progress to a gentle bounce pass.'),
    ('Obstacle Course Challenge', 'GROSS',
     'Crawl through the tunnel, step over cones, jump into two hoops, and run back to the start.'),

    ('Play Dough Squeeze & Roll', 'FINE',
     'Squeeze, pinch, and roll dough into snakes and balls to build hand strength.'),
    ('Threading Big Beads', 'FINE',
     'String large wooden beads onto a stiff lace to make a pattern necklace.'),
    ('Tongs & Pom-Poms Sort', 'HAND_EYE',
     'Use child-sized tongs to move pom-poms into matching colour cups.'),
    ('Scissor Snip Strips', 'FINE',
     'Single-snip narrow paper strips with child-safe scissors, collecting the confetti in a bowl.'),
    ('Water Pouring Station', 'SENSORY',
     'Pour tinted water between small pitchers and cups, wiping spills with a sponge.'),

    ('Freeze Dance', 'GROSS',
     'Children dance freely while the music plays and hold completely still each time it stops.'),
    ('Ribbon Twirl Patterns', 'GROSS',
     'Trace big circles, zigzags, and figure eights in the air with a ribbon streamer on each arm.'),
    ('Stop & Go Marching', 'BALANCE',
     'March in place to a drumbeat, balancing on one foot each time the drum pauses.'),
    ('Mirror Movement Partners', 'GROSS',
     'Facing a partner, one child leads a slow movement and the other mirrors it, then they swap.'),
    ('Bubble Wrap Stomp', 'SENSORY',
     'Stomp, tiptoe, and jump along a taped strip of bubble wrap, listening to the pops change with each step.'),
]

AGENT_ACTIVITIES = {
    'grace': GRACE_ACTIVITIES,
    'patience': PATIENCE_ACTIVITIES,
}

# {meal: {component: {day: item}}} — expanded into the Menu JSON shape below.
DEMO_MENU = {
    'BREAKFAST': {
        'Fruit': ['Banana', 'Applesauce', 'Diced Peaches', 'Blueberries', 'Orange Slices'],
        'Grain': ['Oatmeal', 'Whole Wheat Toast', 'Whole Grain Cereal', 'Pancakes', 'Whole Wheat Bagel'],
        'Drink': ['1% Milk'] * 5,
    },
    'A.M. SNACK': {
        'Vegetable': ['', 'Cucumber Rounds', '', 'Carrot Sticks', ''],
        'Fruit': ['Apple Slices', '', 'Halved Grapes', '', 'Pear Slices'],
        'Grain': ['', 'Whole Grain Crackers', '', '', 'Graham Crackers'],
        'Protein': ['Cheese Cubes', '', 'Yogurt', 'Hummus', ''],
    },
    'LUNCH': {
        'Vegetable': ['Green Beans', 'Broccoli', 'Roasted Sweet Potato', 'Corn', 'Mixed Vegetables'],
        'Fruit': ['Pineapple', 'Mandarin Oranges', 'Apple Slices', 'Strawberries', 'Watermelon'],
        'Grain': ['Brown Rice', 'Whole Wheat Pasta', 'Dinner Roll', 'Soft Tortilla', 'Whole Wheat Bun'],
        'Protein': ['Baked Chicken', 'Turkey Meatballs', 'Black Beans', 'Seasoned Ground Beef', 'Baked Fish'],
        'Drink': ['1% Milk'] * 5,
    },
    'P.M. SNACK': {
        'Vegetable': ['Celery Sticks', '', 'Bell Pepper Strips', '', ''],
        'Fruit': ['', 'Banana', '', 'Melon Cubes', 'Mixed Berries'],
        'Grain': ['', 'Rice Cakes', '', 'Pretzels', ''],
        'Protein': ['Sunflower Seed Butter', '', 'Cheese Stick', '', 'Yogurt'],
    },
}

COMPONENT_ORDER = ['Vegetable', 'Fruit', 'Grain', 'Protein', 'Drink']


def build_menu_week():
    """Expand DEMO_MENU into the {meal: {components, titles}} shape the menu tools read."""
    week = {}
    for meal, by_component in DEMO_MENU.items():
        components = [
            {'name': name, 'items': {
                day: by_component.get(name, [''] * 5)[i] for i, day in enumerate(WEEKDAYS)
            }}
            for name in COMPONENT_ORDER
        ]
        titles = {}
        for i, day in enumerate(WEEKDAYS):
            protein = by_component.get('Protein', [''] * 5)[i]
            grain = by_component.get('Grain', [''] * 5)[i]
            parts = [p for p in (protein, grain) if p]
            titles[day] = ' and '.join(parts) if parts else meal.title()
        week[meal] = {'components': components, 'titles': titles}
    return week


class Command(BaseCommand):
    help = 'Seed a demo week of Grace/Patience activities and menu meals onto the guideline schedule.'

    def add_arguments(self, parser):
        parser.add_argument('--user', help='Username to own the seeded week (default: first superuser).')
        parser.add_argument('--week', help='Monday of the target week as YYYY-MM-DD (default: this week).')
        parser.add_argument('--reset-guideline', action='store_true',
                            help='Replace an existing guideline schedule with the demo slots.')
        parser.add_argument('--reset-menu', action='store_true',
                            help='Replace the current menu with the demo menu.')

    def handle(self, *args, **options):
        user = self._resolve_user(options.get('user'))
        week_start = self._resolve_week(options.get('week'))

        with transaction.atomic():
            slots = self._ensure_guideline(options['reset_guideline'])
            menu_week = self._ensure_menu(user, week_start, options['reset_menu'])
            created = self._seed_week(user, week_start, slots, menu_week)

        self.stdout.write(self.style.SUCCESS(
            f'\nSeeded {created} entries for the week of {week_start:%B %d, %Y} as "{user.get_username()}".'
        ))
        self.stdout.write('View at: http://localhost:8000/sage/weekly-schedule/')

    def _resolve_user(self, username):
        User = get_user_model()
        if username:
            try:
                return User.objects.get(**{User.USERNAME_FIELD: username})
            except User.DoesNotExist:
                raise CommandError(f'No user named "{username}".')
        user = User.objects.filter(is_superuser=True).order_by('pk').first() or User.objects.order_by('pk').first()
        if not user:
            raise CommandError('No users exist. Create one with `python manage.py createsuperuser` first.')
        return user

    def _resolve_week(self, week):
        if week:
            try:
                parsed = date.fromisoformat(week)
            except ValueError:
                raise CommandError(f'--week must be YYYY-MM-DD, got "{week}".')
            return parsed - timedelta(days=parsed.weekday())
        today = date.today()
        return today - timedelta(days=today.weekday())

    def _ensure_guideline(self, reset):
        existing = Schedule.objects.filter(is_default=False, day_of_week=0)
        if existing.exists() and not reset:
            self.stdout.write(f'Using existing guideline schedule ({existing.count()} slots).')
            return list(existing.order_by('start_time'))

        existing.delete()
        Schedule.objects.filter(is_default=True, day_of_week=0).delete()
        for hour, activity, agent in GUIDELINE_SLOTS:
            for is_default in (False, True):
                Schedule.objects.create(
                    start_time=time(hour, 0),
                    end_time=time(hour + 1, 0) if hour < 23 else time(23, 59),
                    activity=activity,
                    agent=agent,
                    day_of_week=0,
                    is_default=is_default,
                )
        self.stdout.write(self.style.SUCCESS(f'Created guideline schedule ({len(GUIDELINE_SLOTS)} slots).'))
        return list(Schedule.objects.filter(is_default=False, day_of_week=0).order_by('start_time'))

    def _ensure_menu(self, user, week_start, reset):
        current = Menu.objects.filter(created_by=user, is_current=True).first()
        if not current:
            current = Menu.objects.filter(created_by=user).order_by('-created_at').first()

        if current and not reset:
            menu_week = _menu_week_for_date(current.menu_data, week_start)
            if menu_week:
                self.stdout.write(f'Using existing menu "{current.title}".')
                return menu_week
            self.stdout.write(self.style.WARNING(
                f'Menu "{current.title}" does not cover this week — seeding the demo menu instead.'
            ))

        Menu.objects.filter(created_by=user, is_current=True).update(is_current=False)
        menu_week = build_menu_week()
        menu = Menu.objects.create(
            title=f'Demo Menu {week_start:%b-%y}',
            provider_name='Materalle Demo Center',
            provider_address='123 Learning Lane',
            month_year=week_start.strftime('%b-%y'),
            menu_data_json=json.dumps({
                '_workflow': {'start_date': week_start.isoformat()},
                'Week 1': menu_week,
            }),
            created_by=user,
            is_current=True,
        )
        self.stdout.write(self.style.SUCCESS(f'Created menu "{menu.title}".'))
        return menu_week

    def _seed_week(self, user, week_start, slots, menu_week):
        WeeklyPlanEntry.objects.filter(week_start_date=week_start).delete()
        weekday_dates = [week_start + timedelta(days=i) for i in range(5)]
        checked_in = list(Child.objects.filter(is_checked_in=True))
        cursors = {agent: 0 for agent in AGENT_ACTIVITIES}
        created = 0

        for slot in slots:
            agent = slot.agent or 'sage'
            label = _normalize_activity(slot.activity)
            static = next((s for key, s in SAGE_STATIC_ACTIVITIES.items() if key in label), None)
            meal_key = next((m for key, m in SAGE_MEAL_MAP.items() if key in label), None)

            for index, day in enumerate(WEEKDAYS):
                if agent in AGENT_ACTIVITIES:
                    pool = AGENT_ACTIVITIES[agent]
                    title, activity_type, description = pool[cursors[agent] % len(pool)]
                    cursors[agent] += 1
                    is_static = False
                elif static:
                    title = static['title']
                    activity_type = static['activity_type']
                    description = static['description']
                    is_static = True
                elif meal_key:
                    title = f'{slot.activity} — {day}'
                    activity_type = 'MEAL'
                    description = self._meal_description(menu_week, meal_key, day)
                    is_static = True
                else:
                    title = slot.activity
                    activity_type = 'ADMIN'
                    description = slot.activity
                    is_static = True

                entry = WeeklyPlanEntry.objects.create(
                    week_start_date=week_start,
                    scheduled_date=weekday_dates[index],
                    start_time=slot.start_time,
                    agent=agent,
                    title=title[:200],
                    activity_type=activity_type[:50],
                    description=description,
                    is_static=is_static,
                    guideline_activity=slot.activity,
                    created_by=user,
                )
                entry.children.set(checked_in)
                created += 1

            self.stdout.write(
                f'  {slot.start_time:%I:%M %p} {slot.activity} ({agent}) — 5 days'
            )

        return created

    def _meal_description(self, menu_week, menu_key, day):
        meal = (menu_week or {}).get(menu_key, {})
        items = [
            component.get('items', {}).get(day, '')
            for component in meal.get('components', [])
        ]
        return ', '.join(item for item in items if item) or menu_key
