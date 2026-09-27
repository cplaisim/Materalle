from django import forms
from .models import MotorCurriculum, PhysicalActivity

class patienceForm(forms.ModelForm):
    class Meta:
        model = MotorCurriculum
        fields = [
            'title', 'activity_type', 'age_range', 'description',
            'developmental_goal', 'materials', 'safety_notes',
            'duration_minutes', 'activity_picture'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'developmental_goal': forms.Textarea(attrs={'rows': 3}),
            'materials': forms.Textarea(attrs={'rows': 3}),
            'safety_notes': forms.Textarea(attrs={'rows': 3}),
        }


class ActivityForm(forms.ModelForm):
    class Meta:
        model = PhysicalActivity
        fields = [
            'title', 'activity_type', 'age_range', 'description',
            'materials', 'safety_notes', 'benefits', 'modifications'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'materials': forms.Textarea(attrs={'rows': 3}),
            'safety_notes': forms.Textarea(attrs={'rows': 3}),
            'benefits': forms.Textarea(attrs={'rows': 3}),
            'modifications': forms.Textarea(attrs={'rows': 3}),
        }