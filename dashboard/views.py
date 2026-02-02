import base64
import json
import os
import io
from io import BytesIO
from datetime import date
import plotly.graph_objects as go
from plotly.offline import plot
import matplotlib
# Set backend to 'Agg' before importing pyplot to avoid GUI errors on server
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from PIL import Image, ImageDraw
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.db.models import Sum, Count, Avg, F, FloatField, ExpressionWrapper
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import make_aware
from django.db import models
# ReportLab imports for Server-Side PDF generation
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from django.utils import timezone
# DRF Imports
from rest_framework import generics

# Local Imports
from dashboard.utils.str_parser import parse_str_file
from .forms import (
    ProductionRecordForm, 
    OreSampleForm, 
    PlantDemandForm, 
    StockpileForm, 
    PhaseScheduleForm, 
    ExpectedValuesForm,
    BlockModelUploadForm,
    PlantForm,
    PitAliasForm
)
from .models import (
    MinePhase, 
    ProductionRecord, 
    OreSample, 
    PlantDemand, 
    Stockpile, 
    PhaseSchedule, 
    Plant,
    MonthlyProductionPlan,
    FinancialSettings
)
from .serializers import (
    MinePhaseSerializer,
    ProductionRecordSerializer,
    OreSampleSerializer,
    PlantDemandSerializer,
    StockpileSerializer,
    PhaseScheduleSerializer
)
#imports for csv handling
import csv
import io
from collections import defaultdict
from django.contrib import messages
from .models import ScheduleScenario, MaterialSchedule
from .forms import ScheduleUploadForm


# ==========================================
# API Views (Django Rest Framework)
# ==========================================

class MinePhaseList(generics.ListAPIView):
    queryset = MinePhase.objects.all()
    serializer_class = MinePhaseSerializer

class ProductionRecordList(generics.ListAPIView):
    queryset = ProductionRecord.objects.all()
    serializer_class = ProductionRecordSerializer

class OreSampleList(generics.ListAPIView):
    queryset = OreSample.objects.all()
    serializer_class = OreSampleSerializer

class PlantDemandList(generics.ListAPIView):
    queryset = PlantDemand.objects.all()
    serializer_class = PlantDemandSerializer

class StockpileList(generics.ListAPIView):
    queryset = Stockpile.objects.all()
    serializer_class = StockpileSerializer

class PhaseScheduleList(generics.ListAPIView):
    queryset = PhaseSchedule.objects.all()
    serializer_class = PhaseScheduleSerializer


# ==========================================
# Dashboard Views
# ==========================================
""""
def pit_progress_view(request):
    # 1. Point to the file in your 'data' folder
    file_path = os.path.join(settings.BASE_DIR, 'data', 'pit_design.str')
    
    # 2. Parse the data
    pit_data = parse_str_file(file_path)

    # 3. Create the Plot
    plt.figure(figsize=(12, 10)) # Set a nice large size
    
    if pit_data:
        for str_id, coords in pit_data.items():
            # Extract X and Y for this specific string ID
            xs = [point[0] for point in coords]
            ys = [point[1] for point in coords]
            
            # Plot the line (linewidth=1 makes it look like a wireframe)
            plt.plot(xs, ys, linewidth=1, label=f"String {str_id}")
            
    else:
        plt.text(0.5, 0.5, "No Data Found. Check file path.", ha='center')

    # 4. Styling
    plt.title("Pit Phase Design")
    plt.xlabel("Easting (X)")
    plt.ylabel("Northing (Y)")
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.axis('equal') # Crucial: ensures the pit doesn't look stretched
    
    # 5. Convert plot to image string
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', bbox_inches='tight')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    plt.close() # Close memory

    graphic = base64.b64encode(image_png).decode('utf-8')

    return render(request, 'dashboard/pit_progress.html', {'graphic': graphic})
"""
def mine_plant_dashboard(request):
    """
    Renders the main dashboard home page linking all sections.
    """
    return render(request, 'dashboard/home.html')


# Add this import at the top of views.py if not present
from django.core.serializers.json import DjangoJSONEncoder 

def production_vs_demand_view(request):
    """
    Dashboard showing Production vs Demand with Stripping Ratio Analysis.
    """
    # 1. AJAX Handler for Chart & Table (Data Fetch)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        
        # Fetch detailed data for JS processing
        prod_data = list(ProductionRecord.objects.values(
            'timestamp', 'tonnage', 'material_type', 'grade', 
            'mine_phase__expected_grade'
        ))
        demand_data = list(PlantDemand.objects.values('timestamp', 'required_tonnage'))
        
        data = {
            "production": prod_data,
            "demand": demand_data
        }
        return JsonResponse(data, safe=False, encoder=DjangoJSONEncoder)

    # 2. Standard Page Load (Server-Side Calculations for Summary Cards)
    recent_production = ProductionRecord.objects.select_related('plant', 'mine_phase').order_by('-timestamp')[:20]
    recent_demand = PlantDemand.objects.select_related('plant').order_by('-timestamp')[:20]

    # --- STRIPPING RATIO ANALYSIS ---
    # Calculate Total Ore vs Total Waste
    total_ore = ProductionRecord.objects.filter(material_type='ore').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
    total_waste = ProductionRecord.objects.filter(material_type='waste').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
    total_demand = PlantDemand.objects.aggregate(Sum('required_tonnage'))['required_tonnage__sum'] or 0

    # Calculate Ratio (Waste / Ore)
    if total_ore > 0:
        stripping_ratio = total_waste / total_ore
    else:
        stripping_ratio = 0.0

    # Determine Traffic Light Status
    if stripping_ratio > 10:
        sr_color = "danger"   # Red (Critical)
        sr_msg = "CRITICAL: Optimization Required"
    elif stripping_ratio > 5:
        sr_color = "warning"  # Yellow (Warning)
        sr_msg = "WARNING: Moderate Dilution Risk"
    else:
        sr_color = "success"  # Green (Optimal)
        sr_msg = "OPTIMAL: Viable Operation"

    context = {
        "page_title": "Production vs Demand",
        "total_production": total_ore, # We treat 'Total Production' as Ore for the main card
        "total_waste": total_waste,    # Added for context if needed
        "total_demand": total_demand,
        
        # New Analysis Context
        "stripping_ratio": round(stripping_ratio, 2),
        "sr_color": sr_color,
        "sr_msg": sr_msg,
        
        "recent_production": recent_production,
        "recent_demand": recent_demand,
    }

    return render(request, "dashboard/production_vs_demand.html", context)


def ore_grade_tonnage_view(request):
    """
    View for Ore Grade & Tonnage analysis.
    Prepares data for Chart.js and tabular display.
    """
    phases = MinePhase.objects.all()

    phase_data = []
    for phase in phases:
        phase_data.append({
            'id': phase.id,
            'name': phase.name,
            'pit': phase.pit,
            'expected_grade': phase.expected_grade or 0,
            'actual_grade': phase.actual_grade(),
            'variance_grade': phase.variance_grade(),
            'expected_tonnage': phase.expected_tonnage or 0,
            'actual_tonnage': phase.actual_tonnage(),
            'variance_tonnage': phase.variance_tonnage(),
        })

    context = {
        'phase_data': phase_data,
        'phase_data_json': json.dumps(phase_data),
    }
    return render(request, 'dashboard/ore_grade_tonnage.html', context)


import json
from django.shortcuts import render, redirect
from .models import Stockpile
from .forms import StockpileForm

def stockpile_forecast(request):
    """
    View for Stockpile levels with Method A (Safety Stock) enforcement.
    Sends ALL data to the template, allowing the user to filter via JavaScript.
    """
    # 1. Fetch ALL Stockpiles (We do not filter here anymore)
    stockpiles = Stockpile.objects.all().order_by('name')
    
    # METHOD A CONFIGURATION:
    # 5 Days x 780t/day = 3,900t
    SAFETY_STOCK_TARGET = 3900 

    stockpile_data = []

    for s in stockpiles:
        # 1. Enforce Method A Logic
        # If the DB has 0 as the target, use the calculated Safety Stock
        target = s.projected_tonnage if s.projected_tonnage > 0 else SAFETY_STOCK_TARGET
        
        # Calculate Variance against this Target
        variance = s.current_tonnage - target
        variance_pct = (variance / target * 100) if target > 0 else 0

        # 2. Professional Color Coding (Passed to JS)
        # We assign colors here so they stay consistent regardless of sorting
        if 'High' in s.name:
            color = 'rgba(25, 135, 84, 0.7)'     # Green
            border = 'rgba(25, 135, 84, 1)'
        elif 'Medium' in s.name:
            color = 'rgba(255, 193, 7, 0.7)'     # Yellow/Orange
            border = 'rgba(255, 193, 7, 1)'
        elif 'Low' in s.name:
            color = 'rgba(220, 53, 69, 0.7)'     # Red
            border = 'rgba(220, 53, 69, 1)'
        elif 'Waste' in s.name:
            color = 'rgba(108, 117, 125, 0.7)'   # Grey
            border = 'rgba(108, 117, 125, 1)'
        else:
            color = 'rgba(13, 110, 253, 0.7)'    # Blue (ROM/Mixed)
            border = 'rgba(13, 110, 253, 1)'

        stockpile_data.append({
            'name': s.name,
            'current_tonnage': s.current_tonnage,
            'projected_tonnage': target,
            'grade': s.grade,
            'variance': round(variance, 0),
            'variance_percent': round(variance_pct, 1),
            'color': color,
            'border': border
        })

    # We pass the raw list of dicts to the template
    # The template will convert this to a JS Object for filtering
    context = {
        "stockpile_data": stockpile_data,
    }
    return render(request, 'dashboard/stockpile_forecast.html', context)


# ==========================================
# Pit & Phase Visualization Views
# ==========================================
def upload_block_model(request):
    """
    NEW VIEW: Handles uploading of Surpac Pit Design (.str) and Block Models (.csv).
    """
    if request.method == 'POST':
        form = BlockModelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            # Directory to save files (inside static so they persist)
            save_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'data')
            os.makedirs(save_path, exist_ok=True)

            # 1. Save Pit Design (.str)
            if 'pit_design_file' in request.FILES:
                with open(os.path.join(save_path, 'pit_design.str'), 'wb+') as dest:
                    for chunk in request.FILES['pit_design_file'].chunks():
                        dest.write(chunk)

            # 2. Save Ore CSV
            if 'ore_file' in request.FILES:
                with open(os.path.join(save_path, 'ore_blocks.csv'), 'wb+') as dest:
                    for chunk in request.FILES['ore_file'].chunks():
                        dest.write(chunk)
            
            # 3. Save Waste CSV
            if 'waste_file' in request.FILES:
                with open(os.path.join(save_path, 'waste_blocks.csv'), 'wb+') as dest:
                    for chunk in request.FILES['waste_file'].chunks():
                        dest.write(chunk)

            messages.success(request, "Files uploaded successfully! Map updated.")
            return redirect('pit_phase_dashboard')
    else:
        form = BlockModelUploadForm()

    return render(request, 'dashboard/upload_block_model.html', {'form': form})

def generate_pit_map_base64(parsed_phases, ore_data=None, waste_data=None):
    """
    Generates 3D Map with Pit Shell (Lines) + Block Model (Points).
    FIXED: Corrected 'titlefont' error by using title=dict(font=...).
    """
    if not parsed_phases and not ore_data and not waste_data:
        return None

    fig = go.Figure()

    # 1. Plot Pit Strings (White Lines)
    if parsed_phases:
        for name, coords in parsed_phases.items():
            if coords:
                # Unpack coordinates, keeping None values for line breaks
                xs = [c[0] if c[0] is not None else None for c in coords]
                ys = [c[1] if c[1] is not None else None for c in coords]
                zs = [c[2] if c[2] is not None else None for c in coords]

                fig.add_trace(go.Scatter3d(
                    x=xs, y=ys, z=zs,
                    mode='lines',
                    name=f'String {name}',
                    line=dict(width=2, color='white'), 
                    connectgaps=False 
                ))

    # 2. Plot WASTE Blocks (Grey Dots)
    if waste_data and len(waste_data[0]) > 0:
        fig.add_trace(go.Scatter3d(
            x=waste_data[0], y=waste_data[1], z=waste_data[2],
            mode='markers',
            name='Waste Rock',
            marker=dict(size=2, color='grey', opacity=0.3)
        ))

    # 3. Plot ORE Blocks (Gold Diamonds)
    if ore_data and len(ore_data[0]) > 0:
        fig.add_trace(go.Scatter3d(
            x=ore_data[0], y=ore_data[1], z=ore_data[2],
            mode='markers',
            name='High Grade Ore',
            marker=dict(size=3, color='#FFD700', opacity=0.8, symbol='diamond')
        ))

    # 4. Styling (Black Background + Visible White Axes)
    fig.update_layout(
        template='plotly_dark',
        margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            aspectmode='data', # Keeps real-world proportions
            
            # X-AXIS
            xaxis=dict(
                title=dict(text='Easting (X)', font=dict(color='white')), # <--- FIXED HERE
                backgroundcolor="black", 
                gridcolor="#444", 
                showbackground=True, 
                visible=True,
                tickfont=dict(color='white')
            ),
            
            # Y-AXIS
            yaxis=dict(
                title=dict(text='Northing (Y)', font=dict(color='white')), # <--- FIXED HERE
                backgroundcolor="black", 
                gridcolor="#444", 
                showbackground=True, 
                visible=True,
                tickfont=dict(color='white')
            ),
            
            # Z-AXIS (Elevation)
            zaxis=dict(
                title=dict(text='Elevation (Z)', font=dict(color='white')), # <--- FIXED HERE
                backgroundcolor="black", 
                gridcolor="#444", 
                showbackground=True, 
                visible=True,
                tickfont=dict(color='white')
            ),
        ),
        paper_bgcolor="black",
        plot_bgcolor="black",
    )

    return plot(fig, output_type='div', include_plotlyjs=True)

def phase_progress_view(request):
    """
    FINAL VERSION: Fixed 'NameError' by restoring total_variance calculation.
    """
    # 1. Standard Production Stats
    phases = PhaseSchedule.objects.select_related('mine_phase').all().order_by('mine_phase__sequence_order')
    for p in phases: p.update_removed_tonnage()

    total_planned = sum(p.planned_tonnage for p in phases)
    total_actual = sum(p.removed_tonnage for p in phases)
    
    # --- FIX: Restored this line ---
    total_variance = total_actual - total_planned 
    
    # Avoid Division by Zero
    progress_ratio = 0
    if total_planned > 0:
        progress_ratio = total_actual / total_planned
        progress_ratio = min(progress_ratio, 1.0) # Cap at 100%

    # Chart Data Arrays
    phase_names = [p.mine_phase.name for p in phases]
    planned_tonnage = [p.planned_tonnage for p in phases]
    removed_tonnage = [p.removed_tonnage for p in phases]
    progress_percentages = [p.current_progress for p in phases]
    variance_list = [p.removed_tonnage - p.planned_tonnage for p in phases]
    
    ore_movement = []
    waste_movement = []
    for p in phases:
        records = p.mine_phase.production_records.all()
        ore = records.filter(material_type='ore').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
        waste = records.filter(material_type='waste').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
        ore_movement.append(round(ore, 2))
        waste_movement.append(round(waste, 2))

    # =========================================================
    # LOAD DATA
    # =========================================================
    data_path = os.path.join(settings.BASE_DIR, 'dashboard', 'static', 'data')

    def load_csv_with_grade(filename, step=50):
        xs, ys, zs, grades = [], [], [], []
        fpath = os.path.join(data_path, filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r') as f:
                    reader = csv.DictReader(f)
                    count = 0
                    for row in reader:
                        if count % step != 0:
                            count += 1
                            continue
                        try:
                            # Auto-detect column names (case-insensitive)
                            row_lower = {k.lower().strip(): v for k, v in row.items()}
                            
                            x = float(row_lower.get('x', 0))
                            y = float(row_lower.get('y', 0))
                            z = float(row_lower.get('z', 0))
                            
                            # Try finding grade in various common column names
                            g_val = row_lower.get('au_ok', row_lower.get('au', row_lower.get('grade', 0)))
                            g = float(g_val)

                            xs.append(x); ys.append(y); zs.append(z); grades.append(g)
                        except ValueError:
                            continue
                        count += 1
            except Exception: pass
        return xs, ys, zs, grades

    # Load Data
    ore_x, ore_y, ore_z, ore_grade = load_csv_with_grade('ore_blocks.csv', step=50)
    waste_x, waste_y, waste_z, _ = load_csv_with_grade('waste_blocks.csv', step=100) 

    # =========================================================
    # MINING CUT LOGIC
    # =========================================================
    all_z = ore_z + waste_z
    cut_level = 9999 # Default high
    
    final_ore_x, final_ore_y, final_ore_z, final_ore_c = [], [], [], []
    final_waste_x, final_waste_y, final_waste_z = [], [], []

    if all_z:
        max_z = max(all_z)
        min_z = min(all_z)
        # Calculate level: Mine from Top (Max) down to Bottom (Min)
        cut_level = max_z - ((max_z - min_z) * progress_ratio)

        # Filter Ore
        for x, y, z, g in zip(ore_x, ore_y, ore_z, ore_grade):
            if z < cut_level:
                final_ore_x.append(x); final_ore_y.append(y); final_ore_z.append(z); final_ore_c.append(g)

        # Filter Waste
        for x, y, z in zip(waste_x, waste_y, waste_z):
            if z < cut_level:
                final_waste_x.append(x); final_waste_y.append(y); final_waste_z.append(z)

    # -------------------------------------------------------
    # GENERATE MAP
    # -------------------------------------------------------
    fig = go.Figure()

    # 1. Pit Shell
    parsed_phases = parse_str_file(os.path.join(data_path, 'pit_design.str'))
    
    # Calculate Pit Bounds for the Mining Plane
    pit_xs, pit_ys = [], []
    
    if parsed_phases:
        for name, coords in parsed_phases.items():
            if coords:
                px = [c[0] if c[0] is not None else None for c in coords]
                py = [c[1] if c[1] is not None else None for c in coords]
                pz = [c[2] if c[2] is not None else None for c in coords]
                
                # Collect coords for bounds calculation
                for p in coords:
                    if p[0] is not None: 
                        pit_xs.append(p[0])
                        pit_ys.append(p[1])

                fig.add_trace(go.Scatter3d(
                    x=px, y=py, z=pz, mode='lines', 
                    line=dict(color='white', width=2), connectgaps=False, showlegend=False
                ))

    # 2. Add "Mining Plane" (The Visual Update Indicator)
    if pit_xs and pit_ys:
        min_x, max_x = min(pit_xs), max(pit_xs)
        min_y, max_y = min(pit_ys), max(pit_ys)
        
        fig.add_trace(go.Mesh3d(
            x=[min_x, max_x, max_x, min_x],
            y=[min_y, min_y, max_y, max_y],
            z=[cut_level, cut_level, cut_level, cut_level],
            color='cyan', opacity=0.3, 
            name=f'Current Level: {cut_level:.1f}m',
            hoverinfo='name'
        ))

    # 3. Waste Blocks
    if final_waste_x:
        fig.add_trace(go.Scatter3d(
            x=final_waste_x, y=final_waste_y, z=final_waste_z,
            mode='markers', name='Waste',
            marker=dict(size=2, color='grey', opacity=0.3)
        ))

    # 4. Ore Blocks (Heatmap)
    if final_ore_x:
        fig.add_trace(go.Scatter3d(
            x=final_ore_x, y=final_ore_y, z=final_ore_z,
            mode='markers', name='Ore Block',
            marker=dict(
                size=4,
                color=final_ore_c,
                colorscale='Jet',
                cmin=0.0, cmax=3.0,
                showscale=True,
                colorbar=dict(
                    title=dict(text="Au (g/t)", font=dict(color='white')), 
                    tickfont=dict(color='white')
                )
            ),
            text=[f"Grade: {g:.2f} g/t" for g in final_ore_c],
            hoverinfo='text'
        ))

    # Styling
    fig.update_layout(
        title=dict(
            text=f"Mining Progress: {progress_ratio*100:.1f}% (Level {cut_level:.0f}m)",
            font=dict(color='white', size=14),
            x=0.05, y=0.95
        ),
        template='plotly_dark', margin=dict(l=0, r=0, b=0, t=0),
        scene=dict(
            aspectmode='data',
            xaxis=dict(title=dict(text='Easting', font=dict(color='white')), backgroundcolor="black", gridcolor="#444", showbackground=True, visible=True, tickfont=dict(color='white')),
            yaxis=dict(title=dict(text='Northing', font=dict(color='white')), backgroundcolor="black", gridcolor="#444", showbackground=True, visible=True, tickfont=dict(color='white')),
            zaxis=dict(title=dict(text='Elevation', font=dict(color='white')), backgroundcolor="black", gridcolor="#444", showbackground=True, visible=True, tickfont=dict(color='white'))
        ),
        paper_bgcolor="black", plot_bgcolor="black"
    )
    
    pit_map_img = plot(fig, output_type='div', include_plotlyjs=True)

    context = {
        "phases": phases,
        "active_phases_count": phases.filter(status='active').count(),
        "completed_phases_count": phases.filter(status='completed').count(),
        "total_planned": total_planned,
        "total_actual": total_actual,
        "total_variance": total_variance,
        "phase_names": phase_names,
        "planned_tonnage": planned_tonnage,
        "removed_tonnage": removed_tonnage,
        "progress_percentages": progress_percentages,
        "ore_movement": ore_movement,
        "waste_movement": waste_movement,
        "variance": variance_list,
        "pit_map_img": pit_map_img,
    }

    return render(request, 'dashboard/phase_progress.html', context)

def pit_map_view(request):
    """
    Standalone view to preview the Pit STR file.
    """
    str_file = os.path.join(os.path.dirname(__file__), 'static', 'data', 'pit_design.str')

    if not os.path.exists(str_file):
        return render(request, 'dashboard/pit_preview.html', {
            'error': f'STR file not found at {str_file}'
        })

    phases = parse_str_file(str_file)
    if not phases:
        return render(request, 'dashboard/pit_preview.html', {
            'error': 'Failed to read coordinates from STR file.'
        })

    pit_map_img = generate_pit_map_base64(phases)

    # Mock Data for preview visualization
    phase_names = list(phases.keys())
    progress_percent = [50] * len(phase_names)
    planned_tonnage = [1000] * len(phase_names)
    removed_tonnage = [800] * len(phase_names)

    context = {
        'pit_map_img': pit_map_img,
        'phase_names': phase_names,
        'progress_percent': progress_percent,
        'planned_tonnage': planned_tonnage,
        'removed_tonnage': removed_tonnage
    }

    return render(request, 'dashboard/pit_preview.html', context)

def pit_data(request):
    """API endpoint to return raw Pit Data JSON."""
    file_path = os.path.join(os.path.dirname(__file__), "static", "data", "pit.str")
    if os.path.exists(file_path):
        phases = parse_str_file(file_path)
        return JsonResponse(phases)
    return JsonResponse({"error": "File not found"}, status=404)


# ==========================================
# Processing & Loss Views
# ==========================================

def processing_loss_dashboard(request):
    """Renders the Processing Loss Analysis page."""
    return render(request, 'dashboard/processing_loss_analysis.html')


def processing_loss_data(request):
    """
    API that forces manual calculation to match the Shell Script logic.
    """
    period = request.GET.get('period', 'daily')
    start = request.GET.get('start')
    end = request.GET.get('end')

    # 1. Get Ore Records
    qs = ProductionRecord.objects.filter(material_type='ore')

    # 2. Date Filtering
    if start:
        qs = qs.filter(timestamp__date__gte=date.fromisoformat(start))
    if end:
        qs = qs.filter(timestamp__date__lte=date.fromisoformat(end))

    buckets = {}

    for r in qs:
        # --- THE MANUAL MATH (Exactly like your Shell) ---
        target = r.mine_phase.expected_grade
        actual = r.grade
        tonnage = r.tonnage
        
        # Calculate Difference
        grade_diff = target - actual
        
        # Only count it as a LOSS if Actual < Target
        if grade_diff > 0:
            loss_kg = (grade_diff * tonnage) / 1000  # Convert grams to kg
            # Estimate Revenue: (Loss kg * 1000g) * $65/g (approx gold price)
            loss_usd = (loss_kg * 1000) * 65 
        else:
            loss_kg = 0
            loss_usd = 0

        # --- Aggregation Logic ---
        # Group by Period (Daily/Weekly/Monthly)
        if period == 'weekly':
            key = r.timestamp.date().isocalendar()[0:2] # (Year, Week)
        elif period == 'monthly':
            key = (r.timestamp.year, r.timestamp.month)
        else:
            key = r.timestamp.date()

        if key not in buckets:
            buckets[key] = {'gold_lost_kg': 0.0, 'revenue_lost_usd': 0.0}

        buckets[key]['gold_lost_kg'] += loss_kg
        buckets[key]['revenue_lost_usd'] += loss_usd

    # 3. Sort and Format for Chart
    sorted_items = sorted(buckets.items())
    labels = []
    gold = []
    revenue = []

    for key, vals in sorted_items:
        # Format Labels
        if period == 'weekly':
            labels.append(f'{key[0]}-W{key[1]}')
        elif period == 'monthly':
            labels.append(f'{key[0]}-{key[1]:02d}')
        else:
            labels.append(key.isoformat())
            
        gold.append(round(vals['gold_lost_kg'], 4))
        revenue.append(round(vals['revenue_lost_usd'], 2))

    return JsonResponse({
        'labels': labels,
        'gold': gold,
        'revenue': revenue
    })

def production_summary(request):
    records = ProductionRecord.objects.order_by('-timestamp')[:20]
    return render(request, 'dashboard/production_summary.html', {'records': records})


# ==========================================
# Forms / Data Entry Views
# ==========================================

def add_stockpile(request):
    if request.method == 'POST':
        form = StockpileForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('stockpile-forecast')
    else:
        form = StockpileForm()
    return render(request, 'dashboard/add_stockpile.html', {'form': form})

def add_production(request):
    """
    Handles adding production records via Text Box inputs.
    Triggers:
    1. Pit Progress Update (PhaseSchedule)
    2. Stockpile Update (Mass Balance + Weighted Grade)
    """
    if request.method == 'POST':
        form = ProductionRecordForm(request.POST)
        if form.is_valid():
            production = form.save(commit=False)
            
            # --- SMART LOGIC 1: Auto-fill Expected Grade ---
            # If the user didn't type a grade, try to fetch it from the Pit Plan
            if production.mine_phase and production.mine_phase.expected_grade and not production.grade:
                production.grade = production.mine_phase.expected_grade
            
            production.save()
            
            # --- SMART LOGIC 2: Update Pit Progress ---
            # Find the schedule for this phase and add the tonnage so the Map updates
            schedule = PhaseSchedule.objects.filter(mine_phase=production.mine_phase).first()
            if schedule:
                schedule.removed_tonnage += production.tonnage
                schedule.update_status() # Auto-switch to 'Active'
                schedule.save()

            # --- SMART LOGIC 3: Update Stockpile ---
            if production.material_type == 'ore':
                # A. Determine Stockpile Name based on Grade
                # You can adjust these grade cut-offs as needed
                if production.grade >= 3.5:
                    sp_name = "High Grade Stockpile"
                elif production.grade >= 1.5:
                    sp_name = "Medium Grade Stockpile"
                else:
                    sp_name = "Low Grade Stockpile"
                
                sp, created = Stockpile.objects.get_or_create(name=sp_name)
                
                # B. Calculate New Weighted Average Grade
                # Formula: ((Old_Tons * Old_Grade) + (New_Tons * New_Grade)) / Total_Tons
                current_mass = sp.current_tonnage
                current_grade = sp.grade if sp.grade else 0.0
                new_mass = production.tonnage
                new_grade = production.grade if production.grade else 0.0
                
                total_mass = current_mass + new_mass
                
                if total_mass > 0:
                    weighted_grade = ((current_mass * current_grade) + (new_mass * new_grade)) / total_mass
                    sp.grade = round(weighted_grade, 2)
                
                # C. Update Tonnage
                sp.current_tonnage = total_mass
                sp.save()
                
                msg_location = sp_name
            else:
                msg_location = "Waste Dump"

            messages.success(request, f"Production Saved! {production.tonnage}t moved to {msg_location}. Pit '{production.mine_phase}' updated.")
            return redirect('production-vs-demand')
    else:
        form = ProductionRecordForm(initial={'timestamp': timezone.now()})
    
    # --- CONTEXT FOR AUTO-COMPLETE ---
    # We pass all phases and plants so the text box can suggest them
    context = {
        'form': form,
        'phases': MinePhase.objects.all().order_by('name'),
        'plants': Plant.objects.all().order_by('name')
    }
    
    return render(request, 'dashboard/add_production.html', context)

# --- 2. ADD DEMAND (STOCKPILE DEPLETION) ---
def add_plantdemand(request):
    if request.method == 'POST':
        form = PlantDemandForm(request.POST)
        if form.is_valid():
            demand = form.save()
            
            # --- CHAIN REACTION: DEPLETE STOCKPILE ---
            source = form.cleaned_data.get('source_stockpile')
            if source:
                source.current_tonnage -= demand.required_tonnage
                source.save()
                messages.success(request, f"Demand Saved! Removed {demand.required_tonnage}t from {source.name}.")
            else:
                # Default Logic: Try to take from 'ROM Stockpile' if no source selected
                rom, _ = Stockpile.objects.get_or_create(name="ROM Stockpile (Mixed)")
                rom.current_tonnage -= demand.required_tonnage
                rom.save()
                messages.warning(request, f"Demand Saved! Deducted from ROM Stockpile (Default).")

            return redirect('production-vs-demand')
    else:
        form = PlantDemandForm()
    
    return render(request, 'dashboard/add_plantdemand.html', {'form': form})

def add_oresample(request):
    if request.method == 'POST':
        form = OreSampleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('ore-grade-tonnage')
    else:
        form = OreSampleForm()

    samples = OreSample.objects.order_by('timestamp')
    return render(request, 'dashboard/add_oresample.html', {
        'form': form,
        'samples': samples
    })

def add_phaseschedule(request):
    # Smart Scenario Look-up for autocomplete
    scenario = ScheduleScenario.objects.annotate(c=Count('schedules')).filter(c__gt=0).last()
    suggested_names = []
    if scenario:
        suggested_names = MaterialSchedule.objects.filter(scenario=scenario)\
                          .values_list('phase_name', flat=True).distinct()

    if request.method == 'POST':
        form = PhaseScheduleForm(request.POST)
        if form.is_valid():
            p_name = form.cleaned_data['phase_name']
            pit_name = form.cleaned_data['pit_name']
            manual_tonnage = form.cleaned_data['expected_tonnage'] # <--- NEW
            start = form.cleaned_data['planned_start']
            end = form.cleaned_data['planned_end']

            # 1. Create the Phase
            phase, created = MinePhase.objects.get_or_create(
                name=p_name,
                defaults={'pit': pit_name, 'phase_number': 1, 'sequence_order': 1}
            )

            # 2. Handle Tonnage (Manual vs Auto)
            if manual_tonnage and manual_tonnage > 0:
                # OPTION A: User typed a number manually
                phase.expected_tonnage = manual_tonnage
                phase.save()
                final_tonnage = manual_tonnage
            else:
                # OPTION B: Auto-sync from CSV
                auto_update_phase_targets() # Run the sync
                phase.refresh_from_db()     # Reload to get the synced number
                final_tonnage = phase.expected_tonnage or 0

            # 3. Create the Schedule
            PhaseSchedule.objects.update_or_create(
                mine_phase=phase,
                defaults={
                    'planned_start': start,
                    'planned_end': end,
                    'planned_tonnage': final_tonnage, # Use the final determined number
                    'status': 'active'
                }
            )

            messages.success(request, f"Phase '{p_name}' created. Target: {final_tonnage:,.0f} tonnes.")
            return redirect('pit_phase_dashboard')
    else:
        form = PhaseScheduleForm()

    return render(request, 'dashboard/add_phaseschedule.html', {
        'form': form,
        'suggested_names': suggested_names
    })

@csrf_exempt
def update_expected_values(request, phase_id):
    """
    AJAX endpoint for inline editing of expected grade/tonnage on dashboards.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            field = data.get("field")
            value = data.get("value")

            phase = get_object_or_404(MinePhase, id=phase_id)

            if field not in ["expected_grade", "expected_tonnage"]:
                return JsonResponse({"success": False, "error": "Invalid field"}, status=400)

            # Convert numeric values safely
            try:
                value = float(value)
            except ValueError:
                return JsonResponse({"success": False, "error": "Invalid number"}, status=400)

            setattr(phase, field, value)
            phase.save()

            return JsonResponse({"success": True, "message": f"{field.replace('_',' ').title()} updated successfully."})

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


# ==========================================
# Export Views (Server Side)
# ==========================================

def export_pdf(request):
    """
    Generates a PDF report for Ore Grade using ReportLab (Server-Side).
    This serves as a backup to the JS Client-Side generation.
    """
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="ore_grade_tonnage.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    data = [['Mine Phase', 'Expected Grade', 'Actual Grade', 'Variance Grade',
             'Expected Tonnage', 'Actual Tonnage', 'Variance Tonnage']]

    for phase in MinePhase.objects.all():
        data.append([
            phase.name,
            phase.expected_grade,
            phase.actual_grade(),
            phase.variance_grade(),
            phase.expected_tonnage,
            phase.actual_tonnage(),
            phase.variance_tonnage()
        ])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgrey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))

    doc.build([table])
    return response


def welcome_dashboard(request):
    return render(request, 'dashboard/home_dashboard.html')


# dashboard/views.py
from django.db.models import Sum, Case, When, FloatField

def mass_analysis_view(request):
    """
    Dedicated view to analyze total mass columns:
    Waste, Low Grade, Medium Grade, and High Grade.
    """
    # We use Django's 'aggregate' to sum specific conditions efficiently
    analysis = ProductionRecord.objects.aggregate(
        waste=Sum(
            Case(When(material_type='waste', then='tonnage'), default=0, output_field=FloatField())
        ),
        low_grade=Sum(
            Case(When(material_type='ore', grade__lt=1.5, then='tonnage'), default=0, output_field=FloatField())
        ),
        medium_grade=Sum(
            Case(When(material_type='ore', grade__gte=1.5, grade__lt=2.5, then='tonnage'), default=0, output_field=FloatField())
        ),
        high_grade=Sum(
            Case(When(material_type='ore', grade__gte=2.5, then='tonnage'), default=0, output_field=FloatField())
        )
    )

    # Clean up None values (in case database is empty)
    context = {
        'waste': analysis['waste'] or 0,
        'low_grade': analysis['low_grade'] or 0,
        'medium_grade': analysis['medium_grade'] or 0,
        'high_grade': analysis['high_grade'] or 0,
        'total_moved': (analysis['waste'] or 0) + (analysis['low_grade'] or 0) + (analysis['medium_grade'] or 0) + (analysis['high_grade'] or 0)
    }

    return render(request, 'dashboard/mass_analysis.html', context)

def upload_schedule_view(request):
    """
    Robust Importer V7 - The "Smart Material" Fix
    1. Finds 'Material' column even if named differently.
    2. Forces 'low_grad' to be treated as ORE (Fixes the $0 Revenue).
    """
    if request.method == "POST":
        form = ScheduleUploadForm(request.POST, request.FILES)
        if form.is_valid():
            scenario_name = form.cleaned_data['scenario_name']
            csv_file = request.FILES['csv_file']

            if not csv_file.name.lower().endswith('.csv'):
                messages.error(request, "Error: Please upload a CSV file.")
                return redirect('upload_schedule')

            scenario = ScheduleScenario.objects.create(name=scenario_name)

            try:
                # 1. READ FILE
                decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
                
                # 2. FIND HEADER ROW
                header_row_index = -1
                for i, line in enumerate(decoded_file[:20]):
                    if 'period' in line.lower():
                        header_row_index = i
                        break
                
                if header_row_index == -1:
                    raise Exception("Could not find a row with 'Period' in the first 20 lines.")

                # 3. PARSE DATA
                data_content = "\n".join(decoded_file[header_row_index:])
                io_string = io.StringIO(data_content)
                reader = csv.DictReader(io_string)

                # CLEAN HEADERS
                if reader.fieldnames:
                    reader.fieldnames = [name.replace('\n', ' ').strip() for name in reader.fieldnames]

                print(f"DEBUG: Cleaned Headers: {reader.fieldnames}")

                # --- SMART COLUMN MAPPING (The Fix) ---
                def find_col(options):
                    for field in reader.fieldnames:
                        if field.lower() in options:
                            return field
                    return None

                # Find the critical columns, whatever they are named
                mat_col = find_col(['material', 'material type', 'dest material', 'rock type', 'mat'])
                vol_col = find_col(['volume', 'vol', 'bank volume'])
                mass_col = find_col(['mass', 'tonnes', 'tons', 't'])

                count = 0
                errors = []
                
                for row_idx, row in enumerate(reader):
                    p_num = row.get('Period') or row.get('Period Number')
                    if not p_num: continue

                    try:
                        def clean_num(val):
                            if not val: return 0.0
                            return float(str(val).replace(',', '').strip())

                        def clean_date(val):
                            if not val: return None
                            val = val.strip()
                            for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y'):
                                try:
                                    return datetime.strptime(val, fmt).date()
                                except ValueError:
                                    continue
                            return None

                        # --- SMART MATERIAL LOGIC ---
                        if mat_col and row.get(mat_col):
                            raw_mat = row.get(mat_col).lower()
                        else:
                            raw_mat = 'waste' # Default only if column missing

                        # CRITICAL FIX: Catch your CSV typo 'low_grad'
                        # This ensures it is NOT treated as waste in the cash flow
                        if 'low_grad' in raw_mat or 'medium_' in raw_mat:
                            raw_mat = 'ore' 
                        elif 'waste' in raw_mat:
                            raw_mat = 'waste'

                        # Map other columns
                        phase = row.get('Source') or row.get('Mining Location', 'Unknown')
                        grade_val = row.get('avarage') or row.get('Grade') or row.get('average')
                        
                        MaterialSchedule.objects.create(
                            scenario=scenario,
                            period=int(p_num),
                            phase_name=phase,
                            start_date=clean_date(row.get('Start') or row.get('Start Date')),
                            end_date=clean_date(row.get('End') or row.get('End Date')),
                            source=phase,
                            destination=row.get('Destination') or row.get('Dest', ''),
                            
                            material_type=raw_mat, # Using our fixed material type
                            
                            volume=clean_num(row.get(vol_col)) if vol_col else clean_num(row.get('Volume')),
                            mass=clean_num(row.get(mass_col)) if mass_col else clean_num(row.get('Mass')),
                            haul_distance=clean_num(row.get('Length') or row.get('Haul') or row.get('Haul Route')),
                            grade=clean_num(grade_val) 
                        )
                        count += 1
                    except Exception as e:
                        if len(errors) < 3:
                            errors.append(f"Row {row_idx + 1}: {str(e)}")
                        continue

                # Report Results
                if count > 0:
                    messages.success(request, f"Success! Uploaded {count} rows to '{scenario.name}'.")
                else:
                    scenario.delete()
                    if errors:
                        messages.error(request, f"Failed. First error: {errors[0]}")
                    else:
                        messages.warning(request, "Found correct headers, but no rows had a Period Number.")
                
                return redirect('upload_schedule')

            except Exception as e:
                scenario.delete()
                messages.error(request, f"Critical Upload Failed: {str(e)}")
                return redirect('upload_schedule')
            
    else:
        form = ScheduleUploadForm()

    # Get Scenarios for the History Table
    scenarios = ScheduleScenario.objects.all().order_by('-created_at')

    return render(request, 'dashboard/upload_schedule.html', {
        'form': form, 
        'scenarios': scenarios 
    })

def auto_update_phase_targets():
    """
    Scans the uploaded Schedule CSV and updates the 'Expected' values
    for every active MinePhase automatically.
    """
    # 1. Get the latest schedule scenario
    scenario = ScheduleScenario.objects.last()
    if not scenario:
        return

    # 2. Loop through all your defined Phases
    phases = MinePhase.objects.all()
    
    for phase in phases:
        # 3. Find matching rows in the CSV Schedule
        # We match strictly by name (e.g., CSV 'Phase 1' == Model 'Phase 1')
        schedule_rows = MaterialSchedule.objects.filter(
            scenario=scenario, 
            phase_name__iexact=phase.name  # Case-insensitive match
        )
        
        if schedule_rows.exists():
            # 4. Calculate Targets automatically
            total_waste = schedule_rows.filter(material_type='waste').aggregate(Sum('mass'))['mass__sum'] or 0
            
            # For Ore, we might sum Low, Medium, and High grades
            total_ore = schedule_rows.exclude(material_type='waste').aggregate(Sum('mass'))['mass__sum'] or 0
            
            # Calculate Average Planned Grade (Weighted Average)
            # (Mass * Grade) / Total Mass
            weighted_grade_sum = 0
            total_mass_for_grade = 0
            
            for row in schedule_rows.exclude(material_type='waste'):
                weighted_grade_sum += (row.mass * row.grade)
                total_mass_for_grade += row.mass
                
            avg_grade = (weighted_grade_sum / total_mass_for_grade) if total_mass_for_grade > 0 else 0

            # 5. SAVE to the Phase Model (Overwriting manual entry)
            phase.expected_tonnage = total_ore + total_waste # Total movement target
            phase.expected_grade = avg_grade
            phase.save()
            
            # Optional: You could save split targets (Ore vs Waste) if you added those fields to MinePhase

def schedule_dashboard_view(request):
    """
    Visualizes the Planning Data (The Targets).
    """
    scenario = ScheduleScenario.objects.last()
    if not scenario:
        return redirect('upload_schedule')

    schedules = MaterialSchedule.objects.filter(scenario=scenario).order_by('period')
    periods = list(schedules.values_list('period', flat=True).distinct().order_by('period'))

    # Prepare Chart Data
    waste_data = []
    low_data = []
    med_data = []
    high_data = []

    for p in periods:
        period_recs = schedules.filter(period=p)
        waste_data.append(period_recs.filter(material_type='waste').aggregate(Sum('mass'))['mass__sum'] or 0)
        low_data.append(period_recs.filter(material_type='low_grade').aggregate(Sum('mass'))['mass__sum'] or 0)
        med_data.append(period_recs.filter(material_type='medium_grade').aggregate(Sum('mass'))['mass__sum'] or 0)
        high_data.append(period_recs.filter(material_type='high_grade').aggregate(Sum('mass'))['mass__sum'] or 0)

    context = {
        'scenario': scenario,
        'schedules': schedules,
        'periods': periods,
        'waste_data': waste_data,
        'low_data': low_data,
        'med_data': med_data,
        'high_data': high_data,
    }
    return render(request, 'dashboard/schedule_view.html', context)

def reconciliation_view(request):
    """
    Professional Reconciliation: Compares Planned (CSV) vs Actual (ProductionRecords).
    """
    scenario = ScheduleScenario.objects.last()
    if not scenario:
        return render(request, 'dashboard/reconciliation.html', {'error': 'No Schedule Found'})

    # 1. Get the Plan
    planned_items = MaterialSchedule.objects.filter(scenario=scenario).order_by('period')
    periods = planned_items.values_list('period', flat=True).distinct().order_by('period')

    reconciliation_data = []

    for period in periods:
        # Get date range for this period from the plan
        p_items = planned_items.filter(period=period)
        start_date = p_items.first().start_date
        end_date = p_items.first().end_date

        # 2. Get the Actuals (ProductionRecords) for this specific timeframe
        actuals_qs = ProductionRecord.objects.filter(
            timestamp__date__gte=start_date, 
            timestamp__date__lte=end_date
        )

        # 3. Sum Actuals by Category
        actual_sums = defaultdict(float)
        for record in actuals_qs:
            # Re-use the logic from your Mass Analysis to categorize
            cat = 'waste'
            if record.material_type == 'ore':
                if record.grade < 1.5: cat = 'low_grade'
                elif record.grade < 2.5: cat = 'medium_grade' # Matches your mass analysis logic
                else: cat = 'high_grade'
            
            actual_sums[cat] += record.tonnage

        # 4. Compare Plan vs Actual
        for item in p_items:
            planned_mass = item.mass
            actual_mass = actual_sums.get(item.material_type, 0)
            variance = actual_mass - planned_mass
            
            pct = (variance / planned_mass * 100) if planned_mass > 0 else 0

            reconciliation_data.append({
                'period': item.period,
                'dates': f"{start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}",
                'material': item.get_material_type_display(),
                'planned': planned_mass,
                'actual': actual_mass,
                'variance': variance,
                'var_pct': pct,
            })

    context = {
        'scenario': scenario,
        'reconciliation_data': reconciliation_data
    }
    return render(request, 'dashboard/reconciliation.html', context)



    """
from django.http import HttpResponse

def debug_connection(request):
    scenario = ScheduleScenario.objects.last()
    if not scenario:
        return HttpResponse("No Schedule Scenario found!")

    # 1. Get unique names from the CSV Data
    csv_names = list(MaterialSchedule.objects.filter(scenario=scenario)
                     .values_list('phase_name', flat=True).distinct())
    
    # 2. Get names you created
    my_phases = list(MinePhase.objects.values_list('name', flat=True))

    # 3. Check for matches
    report = [f"<h1>DEBUG REPORT (Scenario: {scenario.name})</h1>"]
    report.append(f"<h3>1. Found these names in your CSV:</h3><ul>")
    for name in csv_names:
        report.append(f"<li>'{name}' (Length: {len(str(name))})</li>")
    report.append("</ul>")

    report.append(f"<h3>2. Found these Phases you created:</h3><ul>")
    for name in my_phases:
        report.append(f"<li>'{name}' (Length: {len(str(name))})</li>")
    report.append("</ul>")

    report.append("<h3>3. Connection Test:</h3>")
    for phase in MinePhase.objects.all():
        count = MaterialSchedule.objects.filter(scenario=scenario, phase_name__iexact=phase.name).count()
        total = MaterialSchedule.objects.filter(scenario=scenario, phase_name__iexact=phase.name).aggregate(models.Sum('mass'))['mass__sum']
        
        status = "✅ CONNECTED" if count > 0 else "❌ DISCONNECTED"
        report.append(f"<p><strong>{phase.name}</strong>: Found {count} rows. Total Mass: {total}. [{status}]</p>")

    return HttpResponse("".join(report))
    """

# dashboard/views.py

def auto_generate_phases(request):
    # 1. SMART SELECTION: Find the last scenario that actually has rows
    scenario = ScheduleScenario.objects.annotate(
        row_count=Count('schedules')
    ).filter(row_count__gt=0).last()
    
    if not scenario:
        messages.error(request, "No valid schedule data found! Please upload a CSV first.")
        return redirect('upload_schedule')

    unique_locations = MaterialSchedule.objects.filter(scenario=scenario)\
        .values_list('phase_name', flat=True).distinct()

    created_count = 0
    
    for loc_name in unique_locations:
        if not loc_name or loc_name == 'Unknown': continue

        # 2. Create Phase
        phase, created = MinePhase.objects.get_or_create(
            name=loc_name,
            defaults={
                'pit': 'Main Pit',
                'phase_number': 1,
                'sequence_order': 1
            }
        )

        # 3. Force Sync Tonnage from CSV
        match_rows = MaterialSchedule.objects.filter(scenario=scenario, phase_name=loc_name)
        total_planned = match_rows.aggregate(models.Sum('mass'))['mass__sum'] or 0
        
        # 4. Sync Dates
        first = match_rows.order_by('start_date').first()
        last = match_rows.order_by('-end_date').first()

        phase.expected_tonnage = total_planned
        if first and last:
            phase.planned_start = first.start_date
            phase.planned_end = last.end_date
        phase.save()

        # 5. Create Visual Tracker
        PhaseSchedule.objects.update_or_create(
            mine_phase=phase,
            defaults={
                'planned_tonnage': total_planned,
                'planned_start': phase.planned_start,
                'planned_end': phase.planned_end,
                'status': 'active'
            }
        )

        if created:
            created_count += 1

    messages.success(request, f"Success! Connected to '{scenario.name}' and synced {created_count} phases.")
    return redirect('pit_phase_dashboard')

def manage_plants(request):
    """
    Page to View and Add Plants (Master Data).
    """
    if request.method == 'POST':
        form = PlantForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('manage_plants') # Reload page to show new plant
    else:
        form = PlantForm()

    plants = Plant.objects.all().order_by('name')
    return render(request, 'dashboard/manage_plants.html', {'form': form, 'plants': plants})

def planning_dashboard(request):
    """
    Strategic Tool: Matches Schedule Availability vs. Plant Demand.
    Now supports 'all' (Wildcard) to aggregate Total Run of Mine (ROM).
    """
    context = {}
    
    # --- STEP 1: SEARCH AVAILABILITY ---
    if request.method == "POST" and 'search_availability' in request.POST:
        selected_month = request.POST.get('month')
        material = request.POST.get('material')
        
        # 1. Base Query: Always filter by Month first
        schedules = MaterialSchedule.objects.filter(start_date__startswith=selected_month)
        
        # 2. Wildcard Logic: Only filter by material if it is NOT 'all'
        if material != 'all':
            schedules = schedules.filter(material_type=material)
        
        # 3. Aggregate
        total_mass = schedules.aggregate(Sum('mass'))['mass__sum'] or 0
        avg_grade = schedules.aggregate(Avg('grade'))['grade__avg'] or 0

        # Format for display
        formatted_mass = f"{total_mass:,.0f}"
        
        context.update({
            'search_active': True,
            'selected_month': selected_month,
            'selected_material': material,
            'available_display': formatted_mass,
            'available_raw': total_mass,
            'available_grade': round(avg_grade, 2),
        })
        
        return render(request, 'dashboard/planning_tool.html', context)

    # --- STEP 2: SAVE THE PLAN ---
    elif request.method == "POST" and 'save_plan' in request.POST:
        month = request.POST.get('month')
        material = request.POST.get('material')
        
        try:
            available = float(request.POST.get('available_hidden'))
            grade = float(request.POST.get('grade_hidden'))
            target = float(request.POST.get('plant_target'))
        except (ValueError, TypeError):
            messages.error(request, "Invalid number format.")
            return redirect('planning_dashboard')
        
        # Calculate Excess
        to_stockpile = max(0, available - target)
        
        # 1. Naming the Stockpile
        if material == 'all':
            # If selecting ALL, excess goes to "ROM Stockpile" (Run of Mine)
            sp_name = "ROM Stockpile (Mixed)"
        else:
            # Specific Grade Stockpile
            sp_name = f"{material.replace('_', ' ').title()} Stockpile"
            
        stockpile, created = Stockpile.objects.get_or_create(name=sp_name)
        stockpile.current_tonnage += to_stockpile
        stockpile.save()
        
        # 2. Save Plan
        MonthlyProductionPlan.objects.create(
            month_period=month,
            material_type=material,
            available_tonnage=available,
            avg_grade=grade,
            plant_target=target,
            sent_to_stockpile=to_stockpile
        )
        
        messages.success(request, f"Plan Saved! {to_stockpile:,.0f}t moved to {sp_name}.")
        return redirect('planning_dashboard')

    return render(request, 'dashboard/planning_tool.html', context)

def sync_targets_view(request, pk):
    """
    Syncs targets AND updates the 'Active' status flag.
    """
    # 1. Get the scenario the user clicked
    scenario = get_object_or_404(ScheduleScenario, pk=pk)
    
    # 2. MARK ALL OTHERS AS INACTIVE (The Traffic Light Logic)
    # This turns off the green light for everyone else
    ScheduleScenario.objects.update(is_active=False)
    
    # 3. MARK THIS ONE AS ACTIVE
    scenario.is_active = True
    scenario.save()
    
    # 4. Perform the actual syncing of numbers (Your existing logic)
    updated_count = 0
    active_pits = MinePhase.objects.all()
    
    print(f"--- SYNCING FROM: {scenario.name} ---")

    for pit in active_pits:
        match = MaterialSchedule.objects.filter(
            scenario=scenario, 
            phase_name__icontains=pit.name
        ).first()
        
        if match:
            pit.expected_grade = match.grade
            pit.save()
            updated_count += 1
            
    messages.success(request, f"✅ Activated '{scenario.name}' and updated {updated_count} pits.")
    return redirect('upload_schedule')

def pit_config_view(request):
    """
    Allows users to map Pits to CSV Names without using the Admin Panel.
    """
    pits = MinePhase.objects.all().order_by('name')

    if request.method == 'POST':
        # We find which pit is being updated based on the hidden input 'pit_id'
        pit_id = request.POST.get('pit_id')
        pit = get_object_or_404(MinePhase, pk=pit_id)
        
        form = PitAliasForm(request.POST, instance=pit)
        if form.is_valid():
            form.save()
            messages.success(request, f"Updated alias for '{pit.name}'")
            return redirect('pit_config')
        else:
            messages.error(request, "Error updating alias.")
    
    return render(request, 'dashboard/pit_config.html', {'pits': pits})

def cash_flow_view(request, pk):
    scenario = get_object_or_404(ScheduleScenario, pk=pk)
    
    # 1. Settings
    settings, created = FinancialSettings.objects.get_or_create(scenario=scenario)
    
    if request.method == "POST":
        settings.gold_price = float(request.POST.get('gold_price', 1800))
        settings.plant_capacity = float(request.POST.get('plant_capacity', 23400))
        settings.base_mining_cost = float(request.POST.get('base_mining_cost', 4.5))
        settings.save()
        messages.success(request, "Financial parameters updated!")
        return redirect('cash_flow', pk=pk)

    # 2. Data Processing
    periods = MaterialSchedule.objects.filter(scenario=scenario).values('period').distinct().order_by('period')
    
    report_data = []
    cumulative_cash = 0
    
    for p in periods:
        pid = p['period']
        period_rows = MaterialSchedule.objects.filter(scenario=scenario, period=pid)
        
        total_mass = period_rows.aggregate(s=Sum('mass'))['s'] or 0
        
        # --- THE FIX IS HERE ---
        # Instead of looking for "ore", we EXCLUDE "waste".
        # This captures 'low_grade', 'medium_grade', 'high_grade' automatically.
        ore_rows = period_rows.exclude(material_type__icontains='waste')
        
        ore_mass = ore_rows.aggregate(s=Sum('mass'))['s'] or 0
        waste_mass = total_mass - ore_mass
        
        # Calculate Grade (Weighted Average)
        grade_product = 0
        for row in ore_rows:
            grade_product += (row.mass * row.grade)
        avg_grade = (grade_product / ore_mass) if ore_mass > 0 else 0
        
        # --- SPLIT LOGIC ---
        plant_cap = settings.plant_capacity
        if ore_mass > plant_cap:
            processed_tonnes = plant_cap
            stockpiled_tonnes = ore_mass - plant_cap
        else:
            processed_tonnes = ore_mass
            stockpiled_tonnes = 0
            
        # --- FINANCIALS ---
        recovered_grade = avg_grade * settings.recovery_rate
        value_per_tonne = recovered_grade * (settings.gold_price / 31.1)
        
        revenue = processed_tonnes * value_per_tonne
        stockpile_value = stockpiled_tonnes * value_per_tonne
        
        mining_cost = total_mass * settings.base_mining_cost 
        processing_cost = processed_tonnes * settings.processing_cost
        
        total_cost = mining_cost + processing_cost
        net_cash = revenue - total_cost
        cumulative_cash += net_cash
        
        # --- REPORT DATA ---
        report_data.append({
            'period': pid,
            'ore_mined': int(ore_mass),
            'waste_mined': int(waste_mass),
            'processed': int(processed_tonnes),
            'stockpiled': int(stockpiled_tonnes),
            'grade': round(avg_grade, 2),
            'revenue': int(revenue),
            'stockpile_val': int(stockpile_value),
            'mining_cost': int(mining_cost),
            'processing_cost': int(processing_cost),
            'total_cost': int(total_cost),
            'net_cash': int(net_cash),
            'cumulative': int(cumulative_cash)
        })

    return render(request, 'dashboard/cash_flow.html', {
        'scenario': scenario,
        'settings': settings,
        'report_data': report_data
    })