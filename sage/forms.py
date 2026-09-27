from django import forms
from .models import Dish, GroceryItem

class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = [ 
                  'vegetable','fruit','grain','protein','drink'
        ]

class GroceryItemForm(forms.ModelForm):
    is_default = forms.BooleanField(
        required=False,
        label='Set as default item',
        help_text='This item will be automatically selected in future menu generations'
    )
    
    class Meta:
        model = GroceryItem
        fields = ['name', 'category', 'is_default']
        
    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get('name')
        category = cleaned_data.get('category')
        is_default = cleaned_data.get('is_default')
        
        # Check for duplicate items
        if name and category:
            if GroceryItem.objects.filter(name__iexact=name, category=category).exists():
                raise forms.ValidationError('This item already exists in this category.')
        
        # Check default items limit
        if is_default:
            default_count = GroceryItem.objects.filter(
                category=category,
                is_default=True
            ).count()
            
            if default_count >= 4:
                raise forms.ValidationError(
                    f'Maximum of 4 default items allowed for {dict(GroceryItem.CATEGORIES)[category]}'
                )
        
        return cleaned_data
        
