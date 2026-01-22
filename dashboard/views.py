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
from django.db.models import Sum, Count
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
    PlantForm
)
from .models import (
    MinePhase, 
    ProductionRecord, 
    OreSample, 
    PlantDemand, 
    Stockpile, 
    PhaseSchedule, 
    Plant
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
    View for the Production vs Demand dashboard.
    FIXED: Uses DjangoJSONEncoder to prevent AJAX errors with Decimal numbers.
    """
    # 1. AJAX Data Fetch for Charts (The Graph & Log Table)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        
        # Get raw data values
        prod_data = list(ProductionRecord.objects.values('timestamp', 'tonnage', 'material_type', 'plant__name'))
        demand_data = list(PlantDemand.objects.values('timestamp', 'required_tonnage', 'plant__name'))
        
        data = {
            "production": prod_data,
            "demand": demand_data
        }
        
        # CRITICAL FIX: encoder=DjangoJSONEncoder handles Decimal fields correctly
        return JsonResponse(data, safe=False, encoder=DjangoJSONEncoder)

    # 2. Standard Page Load (The Top Cards & Recent Tables)
    recent_production = ProductionRecord.objects.select_related('plant').order_by('-timestamp')[:20]
    recent_demand = PlantDemand.objects.select_related('plant').order_by('-timestamp')[:20]

    context = {
        "page_title": "Production vs Demand Dashboard",
        "total_production": ProductionRecord.objects.aggregate(Sum('tonnage'))['tonnage__sum'] or 0,
        "total_demand": PlantDemand.objects.aggregate(Sum('required_tonnage'))['required_tonnage__sum'] or 0,
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


def stockpile_forecast_view(request):
    """
    View for Stockpile levels and variance.
    """
    stockpiles = Stockpile.objects.all().order_by('name')

    stockpile_data = []
    for s in stockpiles:
        variance = s.variance()
        variance_pct = s.variance_percent()
        stockpile_data.append({
            'name': s.name,
            'current_tonnage': s.current_tonnage,
            'projected_tonnage': s.projected_tonnage,
            'grade': s.grade,
            'variance': round(variance, 1),
            'variance_percent': round(variance_pct, 1),
        })

    context = {
        "stockpile_data": stockpile_data,
        "stockpile_names_json": json.dumps([s['name'] for s in stockpile_data]),
        "actual_tonnage_json": json.dumps([s['current_tonnage'] for s in stockpile_data]),
        "projected_tonnage_json": json.dumps([s['projected_tonnage'] for s in stockpile_data]),
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
    API endpoint that aggregates production loss data by daily/weekly/monthly buckets.
    Used by Chart.js in the frontend.
    """
    period = request.GET.get('period', 'daily')
    start = request.GET.get('start')
    end = request.GET.get('end')

    qs = ProductionRecord.objects.all()

    # Date Filtering
    if start:
        try:
            start_date = date.fromisoformat(start)
            qs = qs.filter(timestamp__date__gte=start_date)
        except ValueError:
            pass # Ignore invalid dates
            
    if end:
        try:
            end_date = date.fromisoformat(end)
            qs = qs.filter(timestamp__date__lte=end_date)
        except ValueError:  # <--- FIXED: Added missing except block here
            pass

    # Filter for underbreak records only
    relevant_records = [r for r in qs if r.is_underbreak()]

    buckets = {}

    def bucket_key(rec):
        if period == 'weekly':
            # returns (iso_year, iso_week)
            return rec.timestamp.date().isocalendar()[0:2]
        if period == 'monthly':
            return (rec.timestamp.year, rec.timestamp.month)
        return rec.timestamp.date()

    for r in relevant_records:
        key = bucket_key(r)
        if key not in buckets:
            buckets[key] = {'gold_lost_kg': 0.0, 'revenue_lost_usd': 0.0}

        # The model handles the logic: if material_type == 'waste', returns 0
        buckets[key]['gold_lost_kg'] += r.gold_lost_kg()
        buckets[key]['revenue_lost_usd'] += r.revenue_lost_usd()

    # Sort and Format for Chart.js
    sorted_items = sorted(buckets.items())
    labels = []
    gold = []
    revenue = []

    for key, vals in sorted_items:
        if period == 'weekly':
            year, week = key
            labels.append(f'{year}-W{week}')
        elif period == 'monthly':
            year, month = key
            labels.append(f'{year}-{month:02d}')
        else:
            labels.append(key.isoformat())
            
        gold.append(round(vals['gold_lost_kg'], 6))
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

def add_plantdemand(request):
    if request.method == 'POST':
        form = PlantDemandForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('production-vs-demand')
    else:
        form = PlantDemandForm()
    return render(request, 'dashboard/add_plantdemand.html', {'form': form})

def add_production(request):
    if request.method == 'POST':
        form = ProductionRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            # Link is handled in form.clean() or form.save() logic
            record.save()
            return redirect('production-vs-demand')
    else:
        form = ProductionRecordForm()
    return render(request, 'dashboard/add_production.html', {'form': form})

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

# dashboard/views.py

def upload_schedule_view(request):
    """
    Robust Importer that handles 'MineSched' style CSVs with metadata headers.
    It automatically finds the header row and maps 'Mining Location' to 'Phase'.
    INCLUDES: 'Ghost Scenario' cleanup (deletes scenario if upload fails).
    """
    if request.method == "POST":
        form = ScheduleUploadForm(request.POST, request.FILES)
        if form.is_valid():
            scenario_name = form.cleaned_data['scenario_name']
            csv_file = request.FILES['csv_file']

            # 1. Safety Check
            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Error: Please upload a CSV file.")
                return render(request, 'dashboard/upload_schedule.html', {'form': form})

            # Create Scenario (We save it now, but delete it later if parsing fails)
            scenario = ScheduleScenario.objects.create(name=scenario_name)

            try:
                # 2. Decode and Read Line-by-Line
                decoded_file = csv_file.read().decode('utf-8').splitlines()
                
                # 3. Find the Header Row dynamically
                # We look for the row that starts with 'Period Number'
                header_row_index = -1
                for i, line in enumerate(decoded_file):
                    if 'Period Number' in line:
                        header_row_index = i
                        break
                
                if header_row_index == -1:
                    raise Exception("Could not find the 'Period Number' header row.")

                # 4. Parse Data starting from the header row
                # We join the rest of the lines back into a string for DictReader
                data_content = "\n".join(decoded_file[header_row_index:])
                io_string = io.StringIO(data_content)
                reader = csv.DictReader(io_string)

                count = 0
                for row in reader:
                    # Skip empty rows (sometimes exist at bottom of Excel exports)
                    if not row.get('Period Number'):
                        continue

                    try:
                        # CLEANING FUNCTIONS
                        def clean_num(value):
                            if not value: return 0.0
                            return float(str(value).replace(',', '').strip())

                        def clean_date(value):
                            # Handle dd/mm/yyyy
                            return datetime.strptime(value.strip(), '%d/%m/%Y').date()

                        # MAPPING
                        # We map 'Mining Location' -> 'phase_name'
                        # We map 'avarge' -> 'grade'
                        MaterialSchedule.objects.create(
                            scenario=scenario,
                            period=int(row['Period Number']),
                            phase_name=row.get('Mining Location', 'Unknown'), # Uses CSV Location as Phase
                            
                            start_date=clean_date(row['Start Date']),
                            end_date=clean_date(row['End Date']),
                            
                            source=row.get('Mining Location', ''),
                            destination=row.get('Mining Location', ''), # Or map to a destination if exists
                            
                            material_type=row.get('Material', 'waste').lower(),
                            
                            volume=clean_num(row.get('Volume', 0)),
                            mass=clean_num(row.get('Mass', 0)),
                            haul_distance=clean_num(row.get('Length', 0)),
                            
                            # Handle the typo 'avarge' from your specific CSV
                            grade=clean_num(row.get('avarge', 0)) 
                        )
                        count += 1
                    except Exception as e:
                        print(f"Skipping row {count}: {e}")
                        continue

                messages.success(request, f"Success! Uploaded {count} schedule records from '{csv_file.name}'.")
                return redirect('schedule_dashboard')

            except Exception as e:
                # --- GHOST SCENARIO CLEANUP ---
                # If anything went wrong above, delete the empty/broken scenario
                scenario.delete()
                # ------------------------------
                messages.error(request, f"Upload Failed: {str(e)}")
                return render(request, 'dashboard/upload_schedule.html', {'form': form})
            
    else:
        form = ScheduleUploadForm()

    return render(request, 'dashboard/upload_schedule.html', {'form': form})

# dashboard/views.py

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