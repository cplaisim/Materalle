from django.contrib.auth.forms import UserCreationForm  
from django.contrib.auth.models import User
from django import forms
from enroll.models import Student
from .models import UserProfile
import re

class CustomUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(
        required=True,
        choices=[
            ('PARENT', 'Parent'),
            ('CAREGIVER', 'Caregiver'),
            ('ADMINISTRATOR', 'Administrator'),
        ],
        initial='PARENT',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    username = forms.CharField(required=True)
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    phone_number = forms.CharField(required=False, help_text='Required for Parents and Caregivers.')
    address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    
    # Administrator-specific fields
    admin_title = forms.CharField(required=False, help_text='Optional: Your position or title')
    admin_department = forms.CharField(required=False, help_text='Optional: Your department')
    is_staff = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())

    class Meta:
        model = User
        fields = ('role', 'username', 'email', 'first_name', 'last_name', 'phone_number', 
                 'address', 'password1', 'password2', 'admin_title', 'admin_department', 'is_staff')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].widget.attrs.update({'class': 'form-control'})
        
        # Add help text for password requirements
        self.fields['password1'].help_text = """
        Your password must contain at least 8 characters and can't be entirely numeric.
        """
        
        # Configure role field
        self.fields['role'].widget.attrs.update({
            'class': 'form-select',
            'id': 'id_role'
        })

        # Configure admin fields
        for field in ['admin_title', 'admin_department']:
            self.fields[field].widget.attrs.update({
                'class': 'form-control admin-field',
                'style': 'display: none;'
            })

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        phone_number = cleaned_data.get('phone_number')
        address = cleaned_data.get('address')

        if role in ['PARENT', 'CAREGIVER']:
            if not phone_number:
                self.add_error('phone_number', 'Phone number is required for Parents and Caregivers')
            if not address:
                self.add_error('address', 'Address is required for Parents and Caregivers')
        
        if role == 'ADMINISTRATOR':
            cleaned_data['is_staff'] = True

        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if not phone_number:
            return phone_number
            
        # Remove any non-digit characters
        phone_number = re.sub(r'\D', '', phone_number)
        
        # Check if the phone number has a valid length
        if len(phone_number) < 10 or len(phone_number) > 15:
            raise forms.ValidationError('Please enter a valid phone number (10-15 digits).')
        
        # Format the phone number
        if len(phone_number) == 10:
            phone_number = f"({phone_number[:3]}) {phone_number[3:6]}-{phone_number[6:]}"
        
        return phone_number

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.is_staff = self.cleaned_data.get('is_staff', False)
        
        if commit:
            user.save()
            # Create the associated UserProfile
            profile = UserProfile.objects.create(
                user=user,
                role=self.cleaned_data['role'],
                email=self.cleaned_data['email'],
                phone_number=self.cleaned_data.get('phone_number', ''),
                address=self.cleaned_data.get('address', '')
            )
            
            # Save administrator-specific information if applicable
            if self.cleaned_data['role'] == 'ADMINISTRATOR':
                profile.admin_title = self.cleaned_data.get('admin_title', '')
                profile.admin_department = self.cleaned_data.get('admin_department', '')
                profile.save()
        
        return user

#class StudentForm(forms.ModelForm):
 #   class Meta:
  #      model = Student
   #     fields = ['childname', 'dateofbirth',]