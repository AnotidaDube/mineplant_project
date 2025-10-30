from django import forms
from .models import ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule

class ProductionRecordForm(forms.ModelForm):
    class Meta:
        model = ProductionRecord
        fields = ['mine_phase', 'timestamp', 'tonnage', 'material_type', 'source']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }

class OreSampleForm(forms.ModelForm):
    class Meta:
        model = OreSample
        fields = ['mine_phase', 'timestamp', 'sample_id', 'grade_g_t', 'tonnage']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }

class PlantDemandForm(forms.ModelForm):
    class Meta:
        model = PlantDemand
        fields = ['timestamp', 'required_tonnage']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local'})
        }

class StockpileForm(forms.ModelForm):
    """
    Form for recording and updating ore stockpile information.
    This matches your Stockpile model exactly.
    """

    class Meta:
        model = Stockpile
        fields = ['name', 'current_tonnage', 'projected_tonnage', 'grade']  # ✅ only real fields in models.py
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter stockpile name'}),
            'current_tonnage': forms.NumberInput(attrs={'placeholder': 'Enter tonnage in tons'}),
        }

        

class PhaseScheduleForm(forms.ModelForm):
    class Meta:
        model = PhaseSchedule
        fields = [
            'mine_phase',
            'planned_start',
            'planned_end',
            'planned_tonnage',
            'removed_tonnage',
            'status'
        ]
        widgets = {
            'planned_start': forms.DateInput(attrs={'type': 'date'}),
            'planned_end': forms.DateInput(attrs={'type': 'date'}),
        }