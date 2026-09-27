from django import forms
from .models import SocialCurriculum

class graceForm(forms.ModelForm):
    class Meta:
        model = SocialCurriculum
        fields = [
            'title', 'activity_type', 'age_range', 'description',
            'developmental_goal', 'materials', 'duration_minutes',
            'group_size', 'author'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'developmental_goal': forms.Textarea(attrs={'rows': 3}),
            'materials': forms.Textarea(attrs={'rows': 3}),
        }