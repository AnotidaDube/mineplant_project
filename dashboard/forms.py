from django import forms
from django.core.exceptions import ValidationError
from .models import ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule, MinePhase, Plant

# ==========================================
# 1. PLANT DEMAND FORM
# ==========================================
class PlantDemandForm(forms.ModelForm):
    plant = forms.ModelChoiceField(
        queryset=Plant.objects.all(),
        empty_label="Select Plant",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = PlantDemand
        fields = ['plant', 'timestamp', 'required_tonnage']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
        }

# ==========================================
# 2. PRODUCTION RECORD FORM (Fixed Order)
# ==========================================
class ProductionRecordForm(forms.ModelForm):
    # 1. Custom Text Fields
    mine_phase_name = forms.CharField(
        label="Mine Phase",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Type phase name (e.g. mucs_luck_pit)'
        })
    )
    
    plant_name = forms.CharField(
        label="Plant",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Type plant name (e.g. Plant A)'
        })
    )

    # 2. FORCE THE ORDER HERE
    # This ensures Phase and Plant appear at the TOP, not the bottom
    field_order = [
        'mine_phase_name', 
        'plant_name', 
        'timestamp', 
        'expected_tonnage', 
        'tonnage', 
        'grade', 
        'recovery', 
        'gold_price', 
        'material_type', 
        'source', 
        'variance'
    ]

    class Meta:
        model = ProductionRecord
        # We exclude 'mine_phase' and 'plant' from here because we map them manually
        fields = ['timestamp', 'expected_tonnage', 'tonnage', 'grade', 'recovery', 'gold_price', 'material_type', 'source', 'variance']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'expected_tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Expected tons'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Actual tons'}),
            'material_type': forms.Select(attrs={'class': 'form-control'}),
            'source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Source pit or phase'}),
            'variance': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Variance', 'readonly': 'readonly'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # A. Resolve Mine Phase
        p_name = cleaned_data.get('mine_phase_name')
        if p_name:
            phase = MinePhase.objects.filter(name__iexact=p_name.strip()).first()
            if not phase:
                raise ValidationError(f"Mine Phase '{p_name}' not found. Please check spelling.")
            self.instance.mine_phase = phase

        # B. Resolve Plant
        pl_name = cleaned_data.get('plant_name')
        if pl_name:
            plant = Plant.objects.filter(name__iexact=pl_name.strip()).first()
            if not plant:
                raise ValidationError(f"Plant '{pl_name}' not found. Check spelling.")
            self.instance.plant = plant
        elif not pl_name and self.instance.plant:
            pass
        else:
            self.instance.plant = None

        # C. Calculate Variance
        tonnage = cleaned_data.get('tonnage')
        expected = cleaned_data.get('expected_tonnage')
        if tonnage is not None and expected is not None:
            cleaned_data['variance'] = tonnage - expected
            self.instance.variance = tonnage - expected

        return cleaned_data

# ==========================================
# 3. OTHER FORMS
# ==========================================
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

class StockpileForm(forms.ModelForm):
    class Meta:
        model = Stockpile
        fields = ['name', 'current_tonnage', 'projected_tonnage', 'grade']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Enter stockpile name'}),
            'current_tonnage': forms.NumberInput(attrs={'placeholder': 'Enter tonnage in tons'}),
        }

# ==========================================
# 4. PHASE SCHEDULE FORM
# ==========================================
class PhaseScheduleForm(forms.Form):
    # 1. Phase Name
    phase_name = forms.CharField(
        max_length=100, 
        label="Phase Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'e.g. mucs_luck_pit',
            'list': 'csv_phases' 
        })
    )
    
    pit_name = forms.CharField(
        max_length=100, 
        label="Pit Name",
        initial="Main Pit",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    # 2. Manual Tonnage Override
    expected_tonnage = forms.FloatField(
        required=False,
        label="Target Tonnage (Manual Override)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control', 
            'placeholder': 'e.g. 4500000 (Leave blank to auto-sync)'
        })
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
            'expected_grade': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'expected_tonnage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
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