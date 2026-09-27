#!/usr/bin/env python
import os
import django
from datetime import date, timedelta
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'materalleapp.settings')
django.setup()

from enroll.models import Child
from django.contrib.auth.models import User

# Get or create admin user
admin_user, _ = User.objects.get_or_create(
    username='admin',
    defaults={'email': 'admin@materalle.local', 'is_staff': True, 'is_superuser': True}
)

names_male = ['Liam', 'Noah', 'Oliver', 'Elijah', 'James', 'Benjamin', 'Lucas', 'Henry', 'Alexander', 'Mason']
names_female = ['Emma', 'Olivia', 'Ava', 'Isabella', 'Sophia', 'Charlotte', 'Amelia', 'Harper', 'Evelyn', 'Abigail']

today = date.today()
created = 0

for i in range(15):
    days_old = random.randint(365, 1095)
    dob = today - timedelta(days=days_old)
    gender = random.choice(['M', 'F'])
    name = random.choice(names_male if gender == 'M' else names_female)
    full_name = f"{name} Child {i+1}"

    if Child.objects.filter(child_name=full_name).exists():
        print(f"Skipping {full_name} (exists)")
        continue

    child = Child.objects.create(
        child_name=full_name,
        date_of_birth=dob,
        child_address=f"{random.randint(100, 9999)} Main St, Anytown",
        child_gender=gender,
        parent_name=f"Parent {i+1}",
        parent_address=f"{random.randint(100, 9999)} Oak St, Anytown",
        parent_phone=f"555-{random.randint(1000, 9999)}",
        parent_email=f"parent{i+1}@example.com",
        parent_name_1=f"Guardian {i+1}",
        parent_phone_1=f"555-{random.randint(1000, 9999)}",
        parent_email_1=f"guardian{i+1}@example.com",
        date_of_enrollment=today,
        date_of_withdrawal=today + timedelta(days=365),
        child_physician="Dr. Smith",
        child_physician_phone="555-1234",
        preferred_hospital="City Hospital",
        hospital_phone="555-5678",
        child_dentist="Dr. Johnson",
        dentist_phone="555-9012",
        signature="Test Sig",
        date_signed=today,
        enrolled_by=admin_user,
    )
    created += 1
    age_m = (today.year - dob.year) * 12 + (today.month - dob.month)
    print(f"✓ {full_name} (age: {age_m//12}y {age_m%12}m, DOB: {dob})")

print(f"\n✓ Created {created} test children")
