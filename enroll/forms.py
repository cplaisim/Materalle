# enroll/forms.py
from django import forms
from .models import Student, Child, StudentRating, AttendanceLog
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class StudentEnrollmentForm(forms.ModelForm):
    class Meta:
        model = Student
        exclude = ['enrolled_by', 'enrollment_date']
        fields = [
            'date_of_enrollment',
            'date_of_withdrawal',  
            'profile_picture',
            'child_name',
            'date_of_birth',
            'child_address',
            'child_gender',
            # Primary Contact
            'parent_name',
            'parent_address',
            'parent_phone',
            'parent_email',
            'ok_to_text',
            # Relationship Type
            'parent',
            'caretaker',
            'relative',
            'guardian',
            'other',
            # Additional Contacts
            'parent_name_1',
            'parent_phone_1',
            'parent_email_1',
            'ok_to_text_1',
            'authorized_pickup_1',
            'parent_name_2',
            'parent_phone_2',
            'parent_email_2',
            'ok_to_text_2',
            'authorized_pickup_2',
            'parent_name_3',
            'parent_phone_3',
            'parent_email_3',
            'ok_to_text_3',
            'authorized_pickup_3',
            # Medical Information
            'child_physician',
            'child_physician_phone',
            'preferred_hospital',
            'hospital_phone',
            'child_dentist',
            'dentist_phone',
            'child_allergies',
            # Therapy Information
            'speech_therapy',
            'physical_therapy',
            'early_intervention',
            'other_therapy',
            'none_therapy',
            # Consents and Agreements
            'info_to_share',
            'consent_to_treat',
            'consent_to_transport',
            'consent_to_trip',
            'understand_permissions',
            'agree_to_update',
            'agree_policies',
            'photo_release',
            'signature',
            'date_signed'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'date_of_enrollment': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'date_of_withdrawal': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'date_signed': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'info_to_share': forms.Textarea(attrs={
                'rows': 4,
                'class': 'form-control'
            }),
            'profile_picture': forms.ClearableFileInput(attrs={
                'class': 'form-control'
            }),
            'child_gender': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If editing and user is not admin/caregiver, make certain fields readonly
        if self.instance.pk and self.user and self.user.role == 'PARENT':
            if self.instance.enrolled_by != self.user:
                for field in self.fields:
                    self.fields[field].widget.attrs['readonly'] = True

    def clean(self):
        cleaned_data = super().clean()
        if self.user and self.user.role == 'PARENT':
            if self.instance.pk and self.instance.enrolled_by != self.user:
                raise ValidationError(_('Parents can only edit their own enrolled students'))
        # Ensure at least one emergency contact is provided
        if not any([
            cleaned_data.get('parent_name_1'),
            cleaned_data.get('parent_name_2'),
            cleaned_data.get('parent_name_3')
        ]):
            raise ValidationError(_('At least one emergency contact must be provided'))
        
        # Ensure date of withdrawal is after date of enrollment if provided
        date_enrollment = cleaned_data.get('date_of_enrollment')
        date_withdrawal = cleaned_data.get('date_of_withdrawal')
        if date_enrollment and date_withdrawal and date_withdrawal < date_enrollment:
            raise ValidationError(_('Date of withdrawal must be after date of enrollment'))
        
        return cleaned_data

class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = ['child_id', 'child_name', 'date_of_birth', 'parent_name']
        widgets = {
            'child_id': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Child ID'
            }),
            'child_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Child Name'
            }),
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'parent_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter Parent Name'
            })
        }

class StudentRatingForm(forms.ModelForm):
    class Meta:
        model = StudentRating
        fields = ['rating']
        widgets = {
            'rating': forms.NumberInput(attrs={'class': 'form-control'})
        }

class AttendanceLogForm(forms.ModelForm):
    class Meta:
        model = AttendanceLog
        fields = ['child', 'check_in', 'check_out', 'recorded_by']
        widgets = {
            'child': forms.Select(attrs={'class': 'form-select'}),
            'check_in': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'check_out': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'recorded_by': forms.Select(attrs={'class': 'form-select'}),
        }