import base64
import json
import os
import io
from io import BytesIO
from datetime import date, timedelta, datetime
import plotly.graph_objects as go
from plotly.offline import plot
import matplotlib
# Set backend to 'Agg' before importing pyplot to avoid GUI errors on server
matplotlib.use('Agg')
from matplotlib import pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from PIL import Image, ImageDraw
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseNotAllowed
from django.db.models import Sum, Count, Avg, F, FloatField, ExpressionWrapper, Case, When, FloatField

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
    PitAliasForm,
    DailyFeedForm,
    IRRCalculationForm
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
    FinancialSettings,
    PitBlock, 
    DailyProductionLog,
    PeriodStockpileActual,
    DailyPlantFeed

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

def stockpile_forecast(request, pk=None):
    """
    Fixed Stockpile Forecast.
    FIX: Now safely handles empty inputs from the 'Add Actuals' form.
    """
    if pk:
        scenario = get_object_or_404(ScheduleScenario, pk=pk)
    else:
        scenario = ScheduleScenario.objects.filter(is_active=True).first()
        if not scenario:
            scenario = ScheduleScenario.objects.last()

    if not scenario:
        messages.error(request, "No schedule found.")
        return redirect('upload_schedule')

    settings, _ = FinancialSettings.objects.get_or_create(scenario=scenario)
    PLANT_CAP = settings.plant_capacity

    # --- POST: Save Manual Actuals ---
    if request.method == "POST":
        try:
            # 1. HELPER: Converts empty strings "" to 0.0
            def clean_float(val):
                if not val or val == '': 
                    return 0.0
                return float(val)

            period = int(request.POST.get('period'))
            actual, _ = PeriodStockpileActual.objects.get_or_create(scenario=scenario, period=period)
            
            # 2. Use helper to safely get numbers
            actual.hg_tonnage = clean_float(request.POST.get('hg_tonnage'))
            actual.hg_grade = clean_float(request.POST.get('hg_grade'))
            
            actual.mg_tonnage = clean_float(request.POST.get('mg_tonnage'))
            actual.mg_grade = clean_float(request.POST.get('mg_grade'))
            
            actual.lg_tonnage = clean_float(request.POST.get('lg_tonnage'))
            actual.lg_grade = clean_float(request.POST.get('lg_grade'))
            
            actual.save()
            messages.success(request, f"Saved Actuals for Period {period}")
            return redirect('stockpile-forecast')
            
        except Exception as e:
            messages.error(request, f"Error: {e}")

    # --- ALGORITHM (Standard Logic) ---
    periods = MaterialSchedule.objects.filter(scenario=scenario).values_list('period', flat=True).distinct().order_by('period')
    
    detailed_data = [] 
    
    bal_hg = 0
    bal_mg = 0
    bal_lg = 0

    latest_actual_hg = 0
    latest_actual_mg = 0
    latest_actual_lg = 0

    for p in periods:
        ore_rows = MaterialSchedule.objects.filter(scenario=scenario, period=p).exclude(material_type__icontains='waste')
        sorted_ore = sorted(ore_rows, key=lambda x: x.grade, reverse=True)
        
        plant_rem = PLANT_CAP
        add_hg, add_mg, add_lg = 0, 0, 0

        for row in sorted_ore:
            mass = row.mass
            grade = row.grade
            if plant_rem > 0:
                if mass <= plant_rem:
                    plant_rem -= mass
                    mass = 0
                else:
                    mass -= plant_rem
                    plant_rem = 0
            
            if mass > 0:
                if grade >= 3.5: add_hg += mass
                elif grade >= 1.5: add_mg += mass
                else: add_lg += mass
        
        bal_hg += add_hg
        bal_mg += add_mg
        bal_lg += add_lg
        
        actual = PeriodStockpileActual.objects.filter(scenario=scenario, period=p).first()
        
        if actual:
            if actual.hg_tonnage > 0: latest_actual_hg = actual.hg_tonnage
            if actual.mg_tonnage > 0: latest_actual_mg = actual.mg_tonnage
            if actual.lg_tonnage > 0: latest_actual_lg = actual.lg_tonnage

        detailed_data.append({'name': f"Period {p} - High Grade", 'projected': bal_hg, 'actual': actual.hg_tonnage if actual else 0, 'grade': actual.hg_grade if actual else 0, 'variance': (actual.hg_tonnage - bal_hg) if actual else 0, 'color': '#198754'})
        detailed_data.append({'name': f"Period {p} - Med Grade", 'projected': bal_mg, 'actual': actual.mg_tonnage if actual else 0, 'grade': actual.mg_grade if actual else 0, 'variance': (actual.mg_tonnage - bal_mg) if actual else 0, 'color': '#ffc107'})
        detailed_data.append({'name': f"Period {p} - Low Grade", 'projected': bal_lg, 'actual': actual.lg_tonnage if actual else 0, 'grade': actual.lg_grade if actual else 0, 'variance': (actual.lg_tonnage - bal_lg) if actual else 0, 'color': '#dc3545'})

    chart_data = [
        {
            'name': 'High Grade Stockpile',
            'projected': bal_hg,
            'actual': latest_actual_hg, 
            'color': 'rgba(25, 135, 84, 0.7)',
            'border': '#198754'
        },
        {
            'name': 'Medium Grade Stockpile',
            'projected': bal_mg,
            'actual': latest_actual_mg,
            'color': 'rgba(255, 193, 7, 0.7)',
            'border': '#ffc107'
        },
        {
            'name': 'Low Grade Stockpile',
            'projected': bal_lg,
            'actual': latest_actual_lg,
            'color': 'rgba(220, 53, 69, 0.7)',
            'border': '#dc3545'
        }
    ]

    return render(request, 'dashboard/stockpile_forecast.html', {
        'chart_data': chart_data,       
        'detailed_data': detailed_data, 
        'periods': periods,
        'scenario': scenario
    })

# Pit & Phase Visualization Views
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
    API for Processing Loss (Dilution Analysis).
    - Compares Actual Grade vs. Expected Phase Grade.
    - USES SETTINGS for Gold Price (No more hardcoded $65).
    - HANDLES NONE values safely to prevent crashes.
    """
    try:
        period = request.GET.get('period', 'daily')
        start = request.GET.get('start')
        end = request.GET.get('end')

        # 1. Get Settings (For Gold Price)
        scenario = ScheduleScenario.objects.filter(is_active=True).first() or ScheduleScenario.objects.last()
        price_per_gram = 65.0 # Default fallback
        if scenario:
            settings, _ = FinancialSettings.objects.get_or_create(scenario=scenario)
            price_per_gram = settings.gold_price

        # 2. Get Ore Records
        qs = ProductionRecord.objects.filter(material_type='ore').select_related('mine_phase')

        # 3. Date Filtering
        if start:
            qs = qs.filter(timestamp__date__gte=date.fromisoformat(start))
        if end:
            qs = qs.filter(timestamp__date__lte=date.fromisoformat(end))

        buckets = {}

        for r in qs:
            # --- SAFETY CHECK (The Fix) ---
            # Treat None (Blank) as 0.0 to prevent crashes
            target = r.mine_phase.expected_grade if (r.mine_phase and r.mine_phase.expected_grade) else 0.0
            actual = r.grade if r.grade is not None else 0.0
            tonnage = r.tonnage if r.tonnage is not None else 0.0
            
            # Calculate Difference
            grade_diff = target - actual
            
            # Only count it as a LOSS if Actual < Target (Underbreak/Dilution)
            if grade_diff > 0 and tonnage > 0:
                loss_grams = grade_diff * tonnage 
                loss_kg = loss_grams / 1000.0
                
                # Revenue Loss = Grams Lost * Current Gold Price
                loss_usd = loss_grams * price_per_gram
            else:
                loss_kg = 0
                loss_usd = 0

            # --- Aggregation Logic ---
            if period == 'weekly':
                # Returns (Year, WeekNum, Day) -> slice to (Year, Week)
                iso = r.timestamp.date().isocalendar()
                key = (iso[0], iso[1]) 
            elif period == 'monthly':
                key = (r.timestamp.year, r.timestamp.month)
            else:
                key = r.timestamp.date()

            if key not in buckets:
                buckets[key] = {'gold_lost_kg': 0.0, 'revenue_lost_usd': 0.0}

            buckets[key]['gold_lost_kg'] += loss_kg
            buckets[key]['revenue_lost_usd'] += loss_usd

        # 4. Sort and Format for Chart
        sorted_items = sorted(buckets.items())
        labels = []
        gold = []
        revenue = []

        for key, vals in sorted_items:
            # Format Labels
            if period == 'weekly':
                labels.append(f'{key[0]}-W{key[1]}')
            elif period == 'monthly':
                import calendar
                month_name = calendar.month_abbr[key[1]]
                labels.append(f'{month_name}-{key[0]}')
            else:
                labels.append(key.isoformat())
                
            gold.append(round(vals['gold_lost_kg'], 4))
            revenue.append(round(vals['revenue_lost_usd'], 2))

        return JsonResponse({
            'labels': labels,
            'gold': gold,
            'revenue': revenue
        })

    except Exception as e:
        print(f"Error in Processing Loss API: {e}")
        # Return empty structure so frontend doesn't show "Failed to load" alert
        return JsonResponse({'labels': [], 'gold': [], 'revenue': []})
    
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
    Handles Manual Production Entry.
    FIX: Now correctly Renders the form on GET requests instead of redirecting.
    """
    # 1. HANDLE FORM SUBMISSION (POST)
    if request.method == "POST":
        try:
            # Check if this is a Block Update (from the Map)
            block_id = request.POST.get('block_id')
            
            if block_id:
                # Logic for Visual Map Blocks
                tonnage = float(request.POST.get('tonnage', 0))
                block = get_object_or_404(PitBlock, id=block_id)
                
                # Safety Fix: Handle None values
                current_removed = block.removed_tonnage or 0.0
                target = block.target_tonnage or 0.0 
                
                block.removed_tonnage = current_removed + tonnage
                
                if target > 0 and block.removed_tonnage >= target:
                    block.status = 'mined'
                else:
                    block.status = 'in_progress'
                block.save()
                
                # Save History
                DailyProductionLog.objects.create(
                    block=block,
                    tonnage_removed=tonnage,
                    date=datetime.now().date()
                )
                messages.success(request, f"Updated Block {block.block_id}: +{tonnage}t")
                return redirect('pit_phase_dashboard')

            else:
                # Logic for Standard Production Form
                form = ProductionRecordForm(request.POST)
                if form.is_valid():
                    form.save()
                    messages.success(request, "Production record saved.")
                    return redirect('pit_phase_dashboard')

        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            return redirect('pit_phase_dashboard')

    # 2. HANDLE PAGE LOAD (GET) - THIS WAS MISSING!
    else:
        form = ProductionRecordForm()
        
    # We pass the form and lists for dropdowns
    context = {
        'form': form,
        'phases': MinePhase.objects.all(),
        'plants': Plant.objects.all()
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

def mass_analysis_view(request):
    """
    Mass Analysis of the ACTIVE SCHEDULE.
    FIX: Dynamically categorizes 'Ore' into Low/Med/High based on grade
    so it doesn't show 0 if the CSV just says "ore".
    """
    # 1. Get the Active Scenario
    scenario = ScheduleScenario.objects.filter(is_active=True).first()
    if not scenario:
        scenario = ScheduleScenario.objects.last()

    if not scenario:
        messages.warning(request, "No schedule found.")
        return redirect('upload_schedule')

    # 2. Aggregate from the SCHEDULE
    # We look for "waste" explicitly.
    # For ore, we look at the GRADE value to decide the bucket.
    analysis = MaterialSchedule.objects.filter(scenario=scenario).aggregate(
        # Waste: explicit label
        waste=Sum(
            Case(When(material_type__iexact='waste', then='mass'), default=0, output_field=FloatField())
        ),
        # Low Grade: Type is Ore AND Grade < 1.5
        low_grade=Sum(
            Case(When(material_type__iexact='ore', grade__lt=1.5, then='mass'), default=0, output_field=FloatField())
        ),
        # Medium Grade: Type is Ore AND 1.5 <= Grade < 3.5
        medium_grade=Sum(
            Case(When(material_type__iexact='ore', grade__gte=1.5, grade__lt=3.5, then='mass'), default=0, output_field=FloatField())
        ),
        # High Grade: Type is Ore AND Grade >= 3.5
        high_grade=Sum(
            Case(When(material_type__iexact='ore', grade__gte=3.5, then='mass'), default=0, output_field=FloatField())
        )
    )

    # 3. Calculate Totals
    waste_t = analysis['waste'] or 0
    lg_t = analysis['low_grade'] or 0
    mg_t = analysis['medium_grade'] or 0
    hg_t = analysis['high_grade'] or 0
    
    total_ore = lg_t + mg_t + hg_t
    total_moved = waste_t + total_ore

    # Avoid division by zero
    strip_ratio = round(waste_t / total_ore, 2) if total_ore > 0 else 0

    context = {
        'scenario': scenario,
        'waste': waste_t,
        'low_grade': lg_t,
        'medium_grade': mg_t,
        'high_grade': hg_t,
        'total_ore': total_ore,
        'total_moved': total_moved,
        'strip_ratio': strip_ratio
    }

    return render(request, 'dashboard/mass_analysis.html', context)

def upload_schedule_view(request):
    """
    Robust Importer V9 - The "End Date" Fix
    1. Skips text rows in CSV.
    2. Maps Dates (1-Jan-26) to Period Numbers.
    3. Calculates End Date automatically (Start + 1 Month) to satisfy database constraints.
    """
    if request.method == "POST":
        form = ScheduleUploadForm(request.POST, request.FILES)
        if form.is_valid():
            scenario_name = form.cleaned_data['scenario_name']
            csv_file = request.FILES['csv_file']

            if not csv_file.name.lower().endswith('.csv'):
                messages.error(request, "Error: Please upload a CSV file.")
                return redirect('upload_schedule')

            # Create Scenario
            scenario = ScheduleScenario.objects.create(name=scenario_name)

            try:
                # 1. READ FILE & FIND HEADER
                decoded_file = csv_file.read().decode('utf-8-sig').splitlines()
                
                header_row_index = -1
                for i, line in enumerate(decoded_file[:20]):
                    # Look for the main header row (flexible match)
                    if 'period' in line.lower() and 'tonnes' in line.lower():
                        header_row_index = i
                        break
                
                if header_row_index == -1:
                    raise Exception("Could not find header row with 'Period' and 'tonnes'.")

                # 2. PARSE DATA
                # Skip the header row itself for DictReader to consume
                data_content = "\n".join(decoded_file[header_row_index:])
                reader = csv.DictReader(io.StringIO(data_content))
                
                # Clean Headers (strip whitespace)
                if reader.fieldnames:
                    reader.fieldnames = [name.strip() for name in reader.fieldnames]

                # 3. HELPER: Get Value Flexibly
                def get_val(row, *aliases):
                    for alias in aliases:
                        for key in row.keys():
                            if key and alias.lower() in key.lower():
                                val = row[key]
                                if val and val.strip():
                                    return val.replace(',', '').replace('"', '').strip()
                    return 0.0

                # 4. PRE-PROCESS DATES TO PERIOD NUMBERS
                rows = list(reader)
                unique_dates = set()
                
                for row in rows:
                    raw_period = row.get('Period') or row.get('Period Number')
                    if not raw_period: continue
                    
                    # SAFETY CHECK: Skip text rows
                    if any(x in raw_period.lower() for x in ['start', 'tonnes', 'ore', 'g/t']):
                        continue
                        
                    try:
                        # Try to parse date
                        for fmt in ('%d-%b-%y', '%d-%m-%y', '%Y-%m-%d', '%d/%m/%Y'):
                            try:
                                dt = datetime.strptime(raw_period.strip(), fmt).date()
                                unique_dates.add(dt)
                                break
                            except ValueError:
                                continue
                    except:
                        continue

                # Create Map: Date -> Period Number (1, 2, 3...)
                sorted_dates = sorted(list(unique_dates))
                date_to_period_map = {d: i+1 for i, d in enumerate(sorted_dates)}

                # 5. IMPORT LOOP
                count = 0
                for row in rows:
                    raw_period = row.get('Period')
                    if not raw_period: continue
                    
                    # SAFETY CHECK: Skip junk rows
                    if any(x in raw_period.lower() for x in ['start', 'tonnes', 'ore', 'g/t']):
                        continue

                    # Determine Period Number & Date
                    period_num = None
                    row_date = None
                    
                    # Try to parse as Date first
                    for fmt in ('%d-%b-%y', '%d-%m-%y', '%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            row_date = datetime.strptime(raw_period.strip(), fmt).date()
                            period_num = date_to_period_map.get(row_date)
                            break
                        except ValueError:
                            pass
                    
                    # If not a date, assume it's an integer
                    if period_num is None:
                        try:
                            period_num = int(float(raw_period))
                            # Default date if missing (e.g., today + period months)
                            row_date = date.today().replace(day=1) 
                        except:
                            continue 

                    # --- CRITICAL FIX: CALCULATE END DATE ---
                    # If we have a start date, End Date = Start Date + ~30 days
                    if row_date:
                        # Logic: Add 32 days, then snap to the 1st of that month, then subtract 1 day
                        # This handles Feb (28 days) vs March (31 days) correctly
                        next_month = (row_date.replace(day=1) + timedelta(days=32)).replace(day=1)
                        calc_end_date = next_month - timedelta(days=1)
                    else:
                        # Fallback if no date found at all
                        calc_end_date = date.today()
                        row_date = date.today()

                    # --- EXTRACT MATERIALS (Split by Column) ---
                    
                    # A. WASTE
                    waste_mass = float(get_val(row, 'waste', 'pit waste'))
                    if waste_mass > 0:
                        MaterialSchedule.objects.create(
                            scenario=scenario, period=period_num,
                            material_type='waste', mass=waste_mass, grade=0.0,
                            start_date=row_date, end_date=calc_end_date
                        )

                    # B. LOW GRADE
                    lg_mass = float(get_val(row, 'low grade', 'low_grade'))
                    lg_grade = float(get_val(row, 'avarage low', 'average low', 'low grade grade'))
                    if lg_mass > 0:
                        MaterialSchedule.objects.create(
                            scenario=scenario, period=period_num,
                            material_type='low_grade', mass=lg_mass, grade=lg_grade,
                            start_date=row_date, end_date=calc_end_date
                        )

                    # C. MEDIUM GRADE
                    mg_mass = float(get_val(row, 'medium grade', 'med grade'))
                    mg_grade = float(get_val(row, 'avarage medium', 'average medium', 'med grade grade'))
                    if mg_mass > 0:
                        MaterialSchedule.objects.create(
                            scenario=scenario, period=period_num,
                            material_type='medium_grade', mass=mg_mass, grade=mg_grade,
                            start_date=row_date, end_date=calc_end_date
                        )

                    # D. HIGH GRADE
                    hg_mass = float(get_val(row, 'high grade'))
                    hg_grade = float(get_val(row, 'avarage high', 'average high', 'high grade grade'))
                    if hg_mass > 0:
                        MaterialSchedule.objects.create(
                            scenario=scenario, period=period_num,
                            material_type='high_grade', mass=hg_mass, grade=hg_grade,
                            start_date=row_date, end_date=calc_end_date
                        )

                    count += 1

                if count > 0:
                    messages.success(request, f"Successfully processed {count} rows for '{scenario.name}'.")
                    return redirect('upload_schedule')
                else:
                    scenario.delete()
                    messages.error(request, "Found headers but could not extract valid data rows.")

            except Exception as e:
                scenario.delete()
                messages.error(request, f"Upload Failed: {str(e)}")
                return redirect('upload_schedule')
    
    else:
        form = ScheduleUploadForm()

    scenarios = ScheduleScenario.objects.all().order_by('-created_at')
    return render(request, 'dashboard/upload_schedule.html', {'form': form, 'scenarios': scenarios})

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
    Reconciliation: Plan vs Actual.
    FINAL VERSION: 
    1. Dynamically loads the NEWEST Active Scenario (matching Production Schedule).
    2. Manually loops data to GUARANTEE rows appear (no empty tables).
    """
    # 1. GET ACTIVE SCENARIO (Prioritize the most recently activated one)
    # This logic matches your Production Schedule view exactly.
    scenario = ScheduleScenario.objects.filter(is_active=True).order_by('-id').first()
    
    # Fallback: If no active flag, get the most recently uploaded one
    if not scenario:
        scenario = ScheduleScenario.objects.order_by('-id').first()

    if not scenario:
        messages.warning(request, "No schedule found.")
        return redirect('upload_schedule')

    # 2. LOAD PLAN (Manual Loop to guarantee data visibility)
    report = {}
    plan_rows = MaterialSchedule.objects.filter(scenario=scenario)
    
    for row in plan_rows:
        p = row.period
        if p not in report: 
            report[p] = {'plan_ore': 0, 'plan_waste': 0, 'act_ore': 0, 'act_waste': 0}

        name = row.material_type.lower()
        mass = row.mass if row.mass else 0.0

        if 'waste' in name:
            report[p]['plan_waste'] += mass
        else:
            report[p]['plan_ore'] += mass

    # 3. LOAD ACTUALS
    act_rows = ProductionRecord.objects.all()
    
    for row in act_rows:
        p = row.timestamp.month
        if p not in report: 
            report[p] = {'plan_ore': 0, 'plan_waste': 0, 'act_ore': 0, 'act_waste': 0}

        name = row.material_type.lower()
        tonnage = row.tonnage if row.tonnage else 0.0

        if 'waste' in name:
            report[p]['act_waste'] += tonnage
        else:
            report[p]['act_ore'] += tonnage

    # 4. BUILD TABLE (Variable names match your Template)
    reconciliation_table = []
    
    for p in sorted(report.keys()):
        data = report[p]
        
        # ORE ROW (Show if ANY data exists)
        if data['plan_ore'] > 0 or data['act_ore'] > 0:
            var = data['act_ore'] - data['plan_ore']
            reconciliation_table.append({
                'period': p,
                'type': 'Total Ore',
                'plan_mass': data['plan_ore'],
                'act_mass': data['act_ore'],
                'var_mass': var,
                'perf_percent': round((data['act_ore'] / data['plan_ore'] * 100), 1) if data['plan_ore'] > 0 else 0,
                'status': 'Underperforming' if var < 0 else 'On Track'
            })
            
        # WASTE ROW
        if data['plan_waste'] > 0 or data['act_waste'] > 0:
            var = data['act_waste'] - data['plan_waste']
            reconciliation_table.append({
                'period': p,
                'type': 'Waste',
                'plan_mass': data['plan_waste'],
                'act_mass': data['act_waste'],
                'var_mass': var,
                'perf_percent': round((data['act_waste'] / data['plan_waste'] * 100), 1) if data['plan_waste'] > 0 else 0,
                'status': 'Behind Schedule' if var < 0 else 'On Track'
            })

    # 5. SEND CONTEXT (Keys match the template logic)
    return render(request, 'dashboard/reconciliation.html', {
        'table': reconciliation_table,   # Matches {% for row in table %}
        'scenario': scenario
    })
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

# dashboard/views.py

def cash_flow_view(request, pk):
    """
    PROJECT LM FINANCIAL ENGINE
    
    Rules Implemented:
    1. INPUTS: Ore Tonnages, Grades, Recovery, Gold Price, Variable Mining Cost.
    2. LOGIC: 
       - Plant Demand = 23,400t / period.
       - Priority: High Grade -> Medium -> Low -> Stockpile.
       - Revenue = Tonnage * Grade * Recovery * Price.
       - Mining Cost = (Ore + Waste) * MiningCost (Sunk Cost Rule).
       - Processing Cost = Processed * $36/t (Fixed).
    3. FLEXIBILITY:
       - Uses the uploaded Schedule (MaterialSchedule) as the input source.
       - Calculates Stockpile balances dynamically per period.
    """
    scenario = get_object_or_404(ScheduleScenario, pk=pk)
    settings, _ = FinancialSettings.objects.get_or_create(scenario=scenario)
    
    # Initialize IRR Form
    irr_form = IRRCalculationForm(request.POST if request.method == "POST" and request.POST.get('action') == 'calculate_irr' else None)
    irr_result = None

    # --- 1. HANDLE SETTINGS UPDATES ---
    if request.method == "POST" and request.POST.get('action') == 'update_settings':
        try:
            settings.gold_price = float(request.POST.get('gold_price', 0))
            # Plant Capacity is fixed at 23,400 per Project LM rules, but we allow override if needed
            input_cap = float(request.POST.get('plant_capacity', 0))
            settings.plant_capacity = input_cap if input_cap > 0 else 23400.0
            
            settings.base_mining_cost = float(request.POST.get('mining_cost', 0))
            # Processing cost fixed at 36, but adjustable via settings if rules change
            settings.processing_cost = float(request.POST.get('processing_cost', 36.0))
            
            settings.save()
            messages.success(request, "Financial parameters updated.")
        except ValueError:
            messages.error(request, "Invalid input.")
        return redirect('cash_flow', pk=pk)

    # --- 2. DEFINE CONSTANTS (PROJECT LM RULES) ---
    PLANT_CAPACITY = settings.plant_capacity if settings.plant_capacity > 0 else 23400.0
    PROC_COST_PER_T = settings.processing_cost # Default 36.0
    RECOVERY = settings.recovery_rate # Default 0.90
    PRICE = settings.gold_price # Default 80.0
    MINING_COST_BASE = settings.base_mining_cost # Variable per period if in CSV, else uses this base

    # --- 3. RUN SIMULATION LOOP ---
    periods = MaterialSchedule.objects.filter(scenario=scenario).values_list('period', flat=True).distinct().order_by('period')
    
    table_data = []
    cumulative_cashflow = 0
    
    # Stockpile State (Carried over between periods)
    stockpile_state = {'mass': 0.0, 'metal': 0.0}
    
    for p in periods:
        rows = MaterialSchedule.objects.filter(scenario=scenario, period=p)
        
        # A. Aggregate Input Data for this Period
        period_inputs = {
            'waste_t': 0.0,
            'high_t': 0.0, 'high_g': 0.0, 'high_metal': 0.0,
            'med_t': 0.0, 'med_g': 0.0, 'med_metal': 0.0,
            'low_t': 0.0, 'low_g': 0.0, 'low_metal': 0.0,
            # If CSV has 'Mining Cost' column, we could fetch it here. For now, use Settings base.
            'mining_cost': MINING_COST_BASE 
        }
        
        # Helper to categorize ore based on grade (Project LM Logic)
        # High > 3.5, Med 1.5-3.5, Low < 1.5 (Adjust thresholds as needed)
        for row in rows:
            mass = row.mass or 0.0
            grade = row.grade or 0.0
            name = row.material_type.lower()
            
            if 'waste' in name:
                period_inputs['waste_t'] += mass
            else:
                # It's Ore - Categorize by Grade
                metal = mass * grade
                if grade >= 3.5:
                    period_inputs['high_t'] += mass
                    period_inputs['high_metal'] += metal
                elif grade >= 1.5:
                    period_inputs['med_t'] += mass
                    period_inputs['med_metal'] += metal
                else:
                    period_inputs['low_t'] += mass
                    period_inputs['low_metal'] += metal

        # Calculate Average Grades for the batches
        period_inputs['high_g'] = (period_inputs['high_metal'] / period_inputs['high_t']) if period_inputs['high_t'] > 0 else 0
        period_inputs['med_g'] = (period_inputs['med_metal'] / period_inputs['med_t']) if period_inputs['med_t'] > 0 else 0
        period_inputs['low_g'] = (period_inputs['low_metal'] / period_inputs['low_t']) if period_inputs['low_t'] > 0 else 0

        # B. Priority Sorting Logic (High -> Med -> Low -> Stockpile)
        batches = [
            {'type': 'High', 'mass': period_inputs['high_t'], 'grade': period_inputs['high_g']},
            {'type': 'Medium', 'mass': period_inputs['med_t'], 'grade': period_inputs['med_g']},
            {'type': 'Low', 'mass': period_inputs['low_t'], 'grade': period_inputs['low_g']},
        ]
        
        # Add existing stockpile as a candidate batch
        if stockpile_state['mass'] > 0:
            stock_grade = stockpile_state['metal'] / stockpile_state['mass']
            batches.append({'type': 'Stockpile', 'mass': stockpile_state['mass'], 'grade': stock_grade})
            
        # SORT: Highest Grade First
        batches.sort(key=lambda x: x['grade'], reverse=True)
        
        # C. Fill the Plant
        remaining_cap = PLANT_CAPACITY
        processed_mass = 0.0
        processed_metal = 0.0
        
        # Reset Stockpile for next state (we rebuild it with leftovers)
        new_stock_mass = 0.0
        new_stock_metal = 0.0
        
        for batch in batches:
            b_mass = batch['mass']
            b_grade = batch['grade']
            
            if b_mass <= 0: continue
            
            if remaining_cap > 0:
                to_process = min(b_mass, remaining_cap)
                
                processed_mass += to_process
                processed_metal += (to_process * b_grade)
                remaining_cap -= to_process
                
                # Remainder goes to NEW stockpile
                remainder = b_mass - to_process
                if remainder > 0:
                    new_stock_mass += remainder
                    new_stock_metal += (remainder * b_grade)
            else:
                # Plant full, batch goes to stockpile
                new_stock_mass += b_mass
                new_stock_metal += (b_mass * b_grade)

        # Update Stockpile State for next loop
        stockpile_state = {'mass': new_stock_mass, 'metal': new_stock_metal}
        
        # D. Financial Calculations
        
        # 1. Revenue
        gold_produced_g = processed_metal * RECOVERY
        revenue = gold_produced_g * PRICE
        
        # 2. Mining Cost (Sunk Cost on ALL mined material + Waste)
        # Note: We do NOT charge mining cost on the "Old Stockpile" portion, only Fresh Mined.
        fresh_ore_mined = period_inputs['high_t'] + period_inputs['med_t'] + period_inputs['low_t']
        total_moved = fresh_ore_mined + period_inputs['waste_t']
        mining_cost = total_moved * period_inputs['mining_cost']
        
        # 3. Processing Cost (On Processed only)
        processing_cost = processed_mass * PROC_COST_PER_T
        
        total_cost = mining_cost + processing_cost
        net_cash_flow = revenue - total_cost
        cumulative_cashflow += net_cash_flow
        
        # 4. Stockpile Valuation
        stock_grade_final = (new_stock_metal / new_stock_mass) if new_stock_mass > 0 else 0
        stockpile_value = (new_stock_metal * RECOVERY) * PRICE

        # E. Pack Data for Template
        table_data.append({
            'period': p,
            'ore_mined': fresh_ore_mined,
            'waste': period_inputs['waste_t'],
            'processed': processed_mass,
            'stockpiled': new_stock_mass,
            'grade': (processed_metal / processed_mass) if processed_mass > 0 else 0,
            'revenue': revenue,
            'mining_cost': mining_cost,
            'processing_cost': processing_cost,
            'total_cost': total_cost,
            'net_cash_flow': net_cash_flow,
            'stockpile_value': stockpile_value,
            'stockpile_grade': stock_grade_final # Added for visibility
        })

    # --- 4. IRR CALCULATION (Keep existing logic) ---
    total_processed_cf = sum(item['net_cash_flow'] for item in table_data)
    total_stockpile_val = sum(item['stockpile_value'] for item in table_data)

    if request.method == "POST" and request.POST.get('action') == 'calculate_irr':
        if irr_form.is_valid():
            initial_inv = irr_form.cleaned_data['initial_investment']
            user_n = irr_form.cleaned_data['periods']
            include_stock = irr_form.cleaned_data['include_stockpile']

            final_cash_flow = total_processed_cf
            if include_stock:
                final_cash_flow += total_stockpile_val

            n = user_n if user_n else len(periods)

            try:
                if final_cash_flow > 0:
                    irr_decimal = (final_cash_flow / initial_inv) ** (1/n) - 1
                else:
                    irr_decimal = -1.0 

                irr_result = {
                    'irr': round(irr_decimal * 100, 2),
                    'total_return': final_cash_flow,
                    'initial': initial_inv,
                    'n': n,
                    'is_stockpile_included': include_stock
                }
            except ZeroDivisionError:
                irr_result = {'error': "Periods cannot be zero."}

    return render(request, 'dashboard/cash_flow.html', {
        'scenario': scenario,
        'settings': settings,
        'table_data': table_data,
        'cumulative_cashflow': cumulative_cashflow,
        'irr_form': irr_form,
        'irr_result': irr_result
    })

def settings_view(request):
    """
    Central Control Room.
    1. Update Financial Parameters (Capacity, Gold Price, Costs).
    2. Switch Active Schedule Scenarios.
    """
    # 1. Identify the Active Scenario
    active_scenario = ScheduleScenario.objects.filter(is_active=True).first()
    
    # Fallback: If none is active, grab the most recent one
    if not active_scenario:
        active_scenario = ScheduleScenario.objects.last()
        if active_scenario:
            active_scenario.is_active = True
            active_scenario.save()

    # 2. Get (or Create) the Settings for this Scenario
    settings_obj = None
    if active_scenario:
        settings_obj, _ = FinancialSettings.objects.get_or_create(scenario=active_scenario)

    # 3. Handle Updates (POST)
    if request.method == "POST":
        action = request.POST.get('action')

        # A. Update Financial Numbers
        if action == "update_settings" and settings_obj:
            try:
                settings_obj.plant_capacity = float(request.POST.get('plant_capacity'))
                settings_obj.gold_price = float(request.POST.get('gold_price'))
                settings_obj.recovery_rate = float(request.POST.get('recovery_rate'))
                settings_obj.base_mining_cost = float(request.POST.get('mining_cost'))
                settings_obj.processing_cost = float(request.POST.get('processing_cost'))
                settings_obj.save()
                messages.success(request, "Parameters Updated Successfully!")
            except ValueError:
                messages.error(request, "Invalid input. Please ensure all fields are numbers.")

        # B. Switch Active Scenario
        elif action == "activate_scenario":
            new_id = request.POST.get('scenario_id')
            if new_id:
                # Deactivate all others
                ScheduleScenario.objects.update(is_active=False)
                # Activate the chosen one
                new_active = ScheduleScenario.objects.get(id=new_id)
                new_active.is_active = True
                new_active.save()
                messages.success(request, f"Switched to Scenario: {new_active.name}")
                return redirect('settings') 

        return redirect('settings')

    # 4. Render Page
    all_scenarios = ScheduleScenario.objects.all().order_by('-created_at')
    
    return render(request, 'dashboard/settings.html', {
        'settings': settings_obj,
        'active_scenario': active_scenario,
        'scenarios': all_scenarios
    })

def daily_financials_view(request):
    """
    Manual Daily Plant Feed & Cash Flow Visualization.
    INTEGRATED: Fetches Gold Price, Costs, and Recovery from 'Settings'.
    """
    # 1. Handle Form Submission
    if request.method == 'POST':
        form = DailyFeedForm(request.POST)
        if form.is_valid():
            # Save or Update existing date
            obj, created = DailyPlantFeed.objects.update_or_create(
                date=form.cleaned_data['date'],
                defaults={'tonnes_fed': form.cleaned_data['tonnes_fed'], 'comments': form.cleaned_data['comments']}
            )
            messages.success(request, f"Updated Plant Feed for {obj.date}")
            return redirect('daily_financials')
    else:
        form = DailyFeedForm()

    # 2. Get Dynamic Financial Settings (CONNECT TO SETTINGS)
    # Find the active scenario first
    active_scenario = ScheduleScenario.objects.filter(is_active=True).first()
    if not active_scenario:
        active_scenario = ScheduleScenario.objects.last()

    # Get the settings object linked to this scenario
    settings_obj = None
    if active_scenario:
        settings_obj = FinancialSettings.objects.filter(scenario=active_scenario).first()

    # Define variables (Use Database values, fallback to defaults if missing)
    if settings_obj:
        PRICE = settings_obj.gold_price
        RECOVERY = settings_obj.recovery_rate
        # For daily cost, we sum Mining + Processing as a rough per-tonne estimate
        COST_PER_TONNE = settings_obj.base_mining_cost + settings_obj.processing_cost
    else:
        # Emergency Fallback if no settings exist
        PRICE = 55.0
        RECOVERY = 0.90
        COST_PER_TONNE = 25.0 

    # 3. Calculate Daily Financials
    daily_data = []
    feeds = DailyPlantFeed.objects.all().order_by('-date')
    
    for feed in feeds:
        # Find mining data for this specific date
        mining_rec = ProductionRecord.objects.filter(timestamp__date=feed.date).first()
        
        # If we mined that day, use the mined grade. If not, assume average 1.5g/t
        grade = mining_rec.grade if (mining_rec and mining_rec.grade) else 1.5
        
        # Calculations using DYNAMIC settings
        gold_produced = feed.tonnes_fed * grade * RECOVERY
        revenue = gold_produced * PRICE
        cost = feed.tonnes_fed * COST_PER_TONNE
        profit = revenue - cost
        
        daily_data.append({
            'date': feed.date,
            'feed_t': feed.tonnes_fed,
            'grade': grade,
            'revenue': revenue,
            'profit': profit,
            'source': mining_rec.source if mining_rec else "Stockpile/Unknown"
        })

    context = {
        'form': form,
        'daily_data': daily_data,
        'settings': settings_obj  # Pass settings to template if you want to display current assumptions
    }
    return render(request, 'dashboard/daily_financials.html', context)