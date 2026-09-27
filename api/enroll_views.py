from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from enroll.models import Child
from django.utils import timezone

from .response import api_response


class EnrollChildView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        required = ['child_name', 'date_of_birth', 'child_address', 'parent_name',
                     'parent_address', 'parent_phone', 'parent_email',
                     'date_of_enrollment', 'child_physician', 'child_physician_phone',
                     'preferred_hospital', 'hospital_phone', 'child_dentist',
                     'dentist_phone', 'child_allergies', 'signature', 'date_signed']

        missing = [f for f in required if not data.get(f)]
        if missing:
            return api_response(
                message=f"Missing required fields: {', '.join(missing)}",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            child = Child.objects.create(
                # Child info
                child_name=data['child_name'],
                date_of_birth=data['date_of_birth'],
                child_address=data['child_address'],
                child_gender=data.get('child_gender', 'M'),
                # Primary contact
                parent_name=data['parent_name'],
                parent_address=data['parent_address'],
                parent_phone=data['parent_phone'],
                parent_email=data['parent_email'],
                ok_to_text=data.get('ok_to_text', True),
                # Relationship
                parent=data.get('parent', True),
                caretaker=data.get('caretaker', False),
                relative=data.get('relative', False),
                guardian=data.get('guardian', False),
                other=data.get('other', False),
                # Additional contacts
                parent_name_1=data.get('parent_name_1', ''),
                parent_phone_1=data.get('parent_phone_1', ''),
                parent_email_1=data.get('parent_email_1', ''),
                ok_to_text_1=data.get('ok_to_text_1', False),
                authorized_pickup_1=data.get('authorized_pickup_1', False),
                parent_name_2=data.get('parent_name_2', ''),
                parent_phone_2=data.get('parent_phone_2', ''),
                parent_email_2=data.get('parent_email_2', ''),
                ok_to_text_2=data.get('ok_to_text_2', False),
                authorized_pickup_2=data.get('authorized_pickup_2', False),
                parent_name_3=data.get('parent_name_3', ''),
                parent_phone_3=data.get('parent_phone_3', ''),
                parent_email_3=data.get('parent_email_3', ''),
                ok_to_text_3=data.get('ok_to_text_3', False),
                authorized_pickup_3=data.get('authorized_pickup_3', False),
                # Dates
                date_of_enrollment=data['date_of_enrollment'],
                date_of_withdrawal=data.get('date_of_withdrawal', data['date_of_enrollment']),
                # Medical
                child_physician=data['child_physician'],
                child_physician_phone=data['child_physician_phone'],
                preferred_hospital=data['preferred_hospital'],
                hospital_phone=data['hospital_phone'],
                child_dentist=data['child_dentist'],
                dentist_phone=data['dentist_phone'],
                child_allergies=data['child_allergies'],
                # Therapy
                speech_therapy=data.get('speech_therapy', False),
                physical_therapy=data.get('physical_therapy', False),
                early_intervention=data.get('early_intervention', False),
                other_therapy=data.get('other_therapy', False),
                none_therapy=data.get('none_therapy', True),
                # Info
                info_to_share=data.get('info_to_share', ''),
                # Consents
                consent_to_treat=data.get('consent_to_treat', True),
                consent_to_transport=data.get('consent_to_transport', True),
                consent_to_trip=data.get('consent_to_trip', True),
                understand_permissions=data.get('understand_permissions', True),
                agree_to_update=data.get('agree_to_update', True),
                agree_policies=data.get('agree_policies', True),
                photo_release=data.get('photo_release', True),
                # Signature
                signature=data['signature'],
                date_signed=data['date_signed'],
                # Tracking
                enrolled_by=request.user,
            )

            return api_response(
                data={'child_id': child.child_id, 'child_name': child.child_name},
                message="Child enrolled successfully.",
                status_code=status.HTTP_201_CREATED,
            )
        except Exception as e:
            return api_response(
                message=str(e),
                status_code=status.HTTP_400_BAD_REQUEST,
            )
