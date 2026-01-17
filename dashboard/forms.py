from django import forms
from .models import ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule, MinePhase, Plant


class PlantDemandForm(forms.ModelForm):
    """Form to handle demand for multiple plants."""
    plant = forms.ModelChoiceField(
        queryset=Plant.objects.all(),
        empty_label="Select Plant",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = PlantDemand
        fields = ['plant', 'timestamp', 'required_tonnage']


class ProductionRecordForm(forms.ModelForm):
    """Form for entering production and comparing expected vs actual tonnage."""
    class Meta:
        model = ProductionRecord
        fields = ['mine_phase', 'plant', 'timestamp', 'expected_tonnage', 'tonnage', 'grade', 'recovery', 'gold_price', 'material_type', 'source', 'variance']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'mine_phase': forms.Select(attrs={'class': 'form-control'}),
            'plant': forms.Select(attrs={'class': 'form-control'}),
            'expected_tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Expected tons'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Actual tons'}),
            'material_type': forms.Select(attrs={'class': 'form-control'}),
            'source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Source pit or phase'}),
            'variance': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Variance'}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['variance'].widget.attrs['readonly'] = True

        # ✅ Show variance if editing an existing record
        if self.instance and self.instance.variance is not None:
            self.fields['variance'].initial = self.instance.variance

    def clean(self):
        cleaned_data = super().clean()
        tonnage = cleaned_data.get('tonnage')
        expected = cleaned_data.get('expected_tonnage')
        if tonnage is not None and expected is not None:
            cleaned_data['variance'] = tonnage - expected
        return cleaned_data   
    
                                  
class OreSampleForm(forms.ModelForm):
    class Meta:
        model = OreSample
        fields = [
            'mine_phase', 'sample_id',
            'actual_grade_g_t', 'actual_tonnage',
            'expected_grade', 'expected_tonnage'
        ]
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

        

# dashboard/forms.py

class PhaseScheduleForm(forms.Form):
    # 1. We ask for the Name instead of a Dropdown
    phase_name = forms.CharField(
        max_length=100, 
        label="Phase Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'e.g. Phase 1',
            'list': 'csv_phases' # Connects to the datalist for auto-complete
        })
    )
    
    pit_name = forms.CharField(
        max_length=100, 
        label="Pit Name",
        initial="Open Pit A",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    planned_start = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    planned_end = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

class ExpectedValuesForm(forms.ModelForm):
    class Meta:
        model = MinePhase
        fields = ['expected_grade', 'expected_tonnage']
        widgets = {
            'expected_grade': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter expected grade (g/t)',
                'step': '0.01'
            }),
            'expected_tonnage': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter expected tonnage (tons)',
                'step': '0.01'
            }),
        }

class ScheduleUploadForm(forms.Form):
    scenario_name = forms.CharField(
        max_length=100, 
        label="Scenario Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Budget_2026'})
    )
    csv_file = forms.FileField(
        label="Upload MineSched CSV",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )