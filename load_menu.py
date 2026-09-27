#!/usr/bin/env python
"""Load the Happy Caterpillars weekly menu into Sage as the current menu.

The shape here is dictated by the client-side renderer in
sage/templates/sage/generate_menu.html: it reads the `menu` query param and
indexes menu["Week N"][mealType].components[].items[dayName].
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'materalleapp.settings')
django.setup()

from django.contrib.auth.models import User
from sage.models import Menu

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']


def row(name, *values):
    """One component row; values are Mon..Fri, '' for blanks."""
    return {"name": name, "items": {d: v for d, v in zip(DAYS, values) if v}}


MILK = ('1% MILK',) * 5

week1 = {
    "BREAKFAST": {"components": [
        row("Fluid Milk", *MILK),
        row("Fruit or Vegetable", 'Cucumber', 'Apple', 'Banana', 'Cucumber', 'Apple'),
        row("Bread or Alternate", 'Bagel', '', 'Waffle', 'Bagel', 'Oatmeal'),
        row("Other", 'Cheese', 'Cottage cheese', '', 'Cheese', ''),
    ]},
    "A.M. SNACK (Choose 2)": {"components": [
        row("Fluid Milk"), row("Fruit or Vegetable"), row("Bread or Alternate"),
        row("Meat or Alternate"), row("Water"),
    ]},
    "LUNCH": {"components": [
        row("Fluid Milk", *MILK),
        row("Meat or Alternate", 'Salmon', 'Chicken Brea', 'Meatballs', 'Chicken', 'Cheese'),
        row("Fruit or Vegetable", 'Green Beans', 'Broccoli', 'Avocado', 'Brussel Sprout', 'Banana'),
        row("Fruit or Vegetable", 'Orange', 'Apple', 'Banana', 'Orange', 'Tomato Sauce'),
        row("Bread or Alternate", 'White Rice', 'WW Pasta', 'White Rice', 'Pasta', 'Pizza Crust'),
        row("Other"),
    ]},
    "P.M. SNACK (Choose 2)": {"components": [
        row("Fluid Milk"),
        row("Fruit or Vegetable", '', '', '', 'Orange', 'Fruit Cup'),
        row("Bread or Alternate", 'Toast', 'Goldfish', 'Granola', '', ''),
        row("Meat or Alternate", 'Cheese stick', 'Yogurt', 'Beans', 'Falafel', 'Yogurt'),
        row("Water", *('Water',) * 5),
    ]},
    "SUPPER": {"components": [
        row("Fluid Milk"), row("Meat or Alternate"), row("Fruit or Vegetable"),
        row("Fruit or Vegetable"), row("Bread or Alternate"), row("Milk"),
    ]},
    "EVENING SNACK": {"components": [row("Fluid Milk"), row("Bread or Alternate")]},
}

menu_data = {"Week 1": week1}

admin = User.objects.get(username='admin')
menu, created = Menu.objects.get_or_create(
    provider_name='Happy Caterpillars',
    month_year='Jun-24',
    created_by=admin,
    defaults={'title': 'Happy Caterpillars Weekly Menu',
              'provider_address': '26 Glen Park Rd'},
)
menu.title = 'Happy Caterpillars Weekly Menu'
menu.provider_address = '26 Glen Park Rd'
menu.menu_data = menu_data
menu.is_current = True
menu.save()
Menu.objects.exclude(pk=menu.pk).update(is_current=False)

print(f"{'Created' if created else 'Updated'} menu: {menu}")
print(f"weeks: {list(menu.menu_data)}")
print(f"meals in Week 1: {list(menu.menu_data['Week 1'])}")
print(f"Mon lunch protein: {menu.menu_data['Week 1']['LUNCH']['components'][1]['items']['Monday']}")
