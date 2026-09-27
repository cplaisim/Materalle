from django.core.management.base import BaseCommand
from django.utils import timezone
from enroll.models import Child
from django.contrib.auth.models import User
from datetime import date, timedelta
import random

class Command(BaseCommand):
    help = 'Create 15 test child profiles with ages 1-3 years'

    def handle(self, *args, **options):
        # Get or create a default admin user for enrolled_by
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@materalle.local',
                'is_staff': True,
                'is_superuser': True,
            }
        )

        names_male = ['Liam', 'Noah', 'Oliver', 'Elijah', 'James', 'Benjamin', 'Lucas', 'Henry', 'Alexander', 'Mason']
        names_female = ['Emma', 'Olivia', 'Ava', 'Isabella', 'Sophia', 'Charlotte', 'Amelia', 'Harper', 'Evelyn', 'Abigail']
        genders = ['M', 'F']

        today = date.today()
        created_count = 0

        for i in range(15):
            # Random age between 1-3 years (365-1095 days ago)
            days_old = random.randint(365, 1095)
            dob = today - timedelta(days=days_old)

            gender = random.choice(genders)
            name = random.choice(names_male if gender == 'M' else names_female)
            full_name = f"{name} Child {i+1}"

            # Check if already exists
            if Child.objects.filter(child_name=full_name).exists():
                self.stdout.write(f"Skipping {full_name} (already exists)")
                continue

            child = Child.objects.create(
                child_name=full_name,
                date_of_birth=dob,
                child_address=f"{random.randint(100, 9999)} Main St, Anytown, USA",
                child_gender=gender,
                parent_name=f"Parent of {full_name}",
                parent_address=f"{random.randint(100, 9999)} Oak St, Anytown, USA",
                parent_phone=f"555-{random.randint(1000, 9999)}",
                parent_email=f"parent{i+1}@example.com",
                ok_to_text=random.choice([True, False]),
                parent_name_1=f"Guardian 1 for {full_name}",
                parent_phone_1=f"555-{random.randint(1000, 9999)}",
                parent_email_1=f"guardian1_{i+1}@example.com",
                date_of_enrollment=today,
                date_of_withdrawal=today + timedelta(days=365),
                child_physician="Dr. Smith",
                child_physician_phone="555-1234",
                preferred_hospital="City Hospital",
                hospital_phone="555-5678",
                child_dentist="Dr. Johnson",
                dentist_phone="555-9012",
                child_allergies="None reported" if random.random() > 0.3 else "Peanuts, Dairy",
                consent_to_treat=True,
                consent_to_transport=True,
                consent_to_trip=True,
                understand_permissions=True,
                agree_to_update=True,
                agree_policies=True,
                photo_release=random.choice([True, False]),
                signature="Test Signature",
                date_signed=today,
                enrolled_by=admin_user,
            )
            created_count += 1
            age_months = (today.year - dob.year) * 12 + (today.month - dob.month)
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Created: {full_name} (age: {age_months // 12}y {age_months % 12}m, DOB: {dob})'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully created {created_count} test children (ages 1-3 years)')
        )
