from django import forms
from django.core.exceptions import ValidationError
from .models import ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule, MinePhase, Plant

class PlantForm(forms.ModelForm):
    class Meta:
        model = Plant
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter new plant name'})
        }

# 3. Updated Production Form (Reads from the Plant List)
class ProductionRecordForm(forms.ModelForm):
    # --- Custom Text Fields ---
    mine_phase_name = forms.CharField(
        label="Mine Phase / Pit",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Type phase name (e.g. Phase 1)',
            'list': 'phase_list' # Enables auto-complete if we add a datalist
        })
    )
    
    plant_name = forms.CharField(
        label="Destination Plant",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Type plant name (e.g. Plant A)'
        })
    )

    class Meta:
        model = ProductionRecord
        fields = ['timestamp', 'material_type', 'tonnage', 'grade', 'recovery']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'material_type': forms.Select(attrs={'class': 'form-select'}),
            'tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Actual Tonnes'}),
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Grade (g/t)'}),
            'recovery': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.1', 'placeholder': 'Recovery %'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # A. Resolve Mine Phase (Text -> ID)
        p_name = cleaned_data.get('mine_phase_name')
        if p_name:
            # Look for the phase in the database
            phase = MinePhase.objects.filter(name__iexact=p_name.strip()).first()
            if not phase:
                # Optional: Auto-create if it doesn't exist? 
                # For now, let's raise an error to prevent typos.
                raise ValidationError(f"Mine Phase '{p_name}' not found. Please check spelling.")
            self.instance.mine_phase = phase

        # B. Resolve Plant (Text -> ID)
        pl_name = cleaned_data.get('plant_name')
        if pl_name:
            plant = Plant.objects.filter(name__iexact=pl_name.strip()).first()
            if not plant:
                 raise ValidationError(f"Plant '{pl_name}' not found.")
            self.instance.plant = plant
        
        return cleaned_data

# ==========================================
# 2. PLANT DEMAND FORM
# ==========================================
class PlantDemandForm(forms.ModelForm):
    # 1. Text Box for Plant Name (Matches Production Form style)
    plant_name = forms.CharField(
        label="Destination Plant",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Type plant name (e.g. Plant A)',
            'list': 'plant_list' # Connects to the HTML auto-complete list
        })
    )
    
    # 2. Dropdown for Source Stockpile
    source_stockpile = forms.ModelChoiceField(
        queryset=Stockpile.objects.all(),
        required=False,
        label="Feed Source (Stockpile)",
        help_text="Leave blank to auto-deduct from ROM",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = PlantDemand
        fields = ['timestamp', 'required_tonnage']
        widgets = {
            'timestamp': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'required_tonnage': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Target Tonnes'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        
        # Resolve Plant Name (Text) -> Plant Object (ID)
        pl_name = cleaned_data.get('plant_name')
        if pl_name:
            plant = Plant.objects.filter(name__iexact=pl_name.strip()).first()
            if not plant:
                raise ValidationError(f"Plant '{pl_name}' not found. Please check spelling.")
            self.instance.plant = plant
            
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

from django import forms

class BlockModelUploadForm(forms.Form):
    # 1. The Pit Design (Strings)
    pit_design_file = forms.FileField(
        label="Pit Design File (.str)",
        help_text="Upload your latest Surpac string file (e.g., pit_design.str)",
        required=False
    )
    
    # 2. The High Grade Ore (Gold)
    ore_file = forms.FileField(
        label="High Grade Ore CSV",
        help_text="Export from Surpac using 'ore cutt of grade.con'. Columns: Y, X, Z",
        required=False
    )
    
    # 3. The Waste Rock (Grey)
    waste_file = forms.FileField(
        label="Waste/Rock CSV",
        help_text="Export from Surpac using 'coooon.con'. Columns: Y, X, Z",
        required=False
    )