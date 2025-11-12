import base64
from io import BytesIO
import os
import json
from django.views.decorators.csrf import csrf_exempt
from reportlab.pdfgen import canvas
from django.http import JsonResponse
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.db.models import Sum
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from dashboard.utils.str_parser import parse_str_file
from django.conf import settings
from PIL import Image, ImageDraw
from django.shortcuts import render, redirect
from .forms import ProductionRecordForm, OreSampleForm, PlantDemandForm, StockpileForm, PhaseScheduleForm, ExpectedValuesForm
from rest_framework import generics
from .models import MinePhase, ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule, Plant
from .serializers import (
    MinePhaseSerializer,
    ProductionRecordSerializer,
    OreSampleSerializer,
    PlantDemandSerializer,
    StockpileSerializer,
    PhaseScheduleSerializer
)
from matplotlib import pyplot as plt
from django.utils.timezone import make_aware
from datetime import date



# List of APIs
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


def production_vs_demand_view(request):
    """ If it's a data fetch request, return API response (charts use this soon) """
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        data = {
            "production": list(ProductionRecord.objects.values()),
            "demand": list(PlantDemand.objects.values())
        }
        return JsonResponse(data, safe=False)

    """ Dashboard context (optional initial stats)"""
    context = {
        "page_title": "Production vs Demand Dashboard",
        "total_production": ProductionRecord.objects.aggregate(Sum('tonnage'))['tonnage__sum'] or 0,
        "total_demand": PlantDemand.objects.aggregate(Sum('required_tonnage'))['required_tonnage__sum'] or 0,
    }

    return render(request, "dashboard/production_vs_demand.html", context)


def ore_grade_tonnage_view(request):
    phases = MinePhase.objects.all()

    phase_data = []
    for phase in phases:
        phase_data.append({
            'id': phase.id,  # ✅ Include ID here
            'name': phase.name,
            'pit': phase.pit,
            'expected_grade': phase.expected_grade or 0,
            'actual_grade': phase.actual_grade(),
            'variance_grade': phase.variance_grade(),
            'expected_tonnage': phase.expected_tonnage or 0,
            'actual_tonnage': phase.actual_tonnage(),
            'variance_tonnage': phase.variance_tonnage(),
        })

    # Provide JSON-stringified data for Chart.js & JS consumption
    context = {
        'phase_data': phase_data,
        'phase_data_json': json.dumps(phase_data),
    }
    return render(request, 'dashboard/ore_grade_tonnage.html', context)



def stockpile_forecast_view(request):
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


def phase_progress_view(request):
    phases = PhaseSchedule.objects.select_related('mine_phase').all().order_by('mine_phase__sequence_order')

    """ Auto-refresh tonnage values """
    for p in phases:
        p.update_removed_tonnage()

    """ Filter by status """
    active_phases = phases.filter(status='active')
    completed_phases = phases.filter(status='completed')

    # Chart data
    phase_names = [p.mine_phase.name for p in phases]
    planned_tonnage = [p.planned_tonnage for p in phases]
    removed_tonnage = [p.removed_tonnage for p in phases]
    progress_percentages = [p.current_progress for p in phases]

    # Variance calculations
    variance = [(removed - planned) for removed, planned in zip(removed_tonnage, planned_tonnage)]
    variance_percent = [
        ((removed - planned) / planned) * 100 if planned else None
        for removed, planned in zip(removed_tonnage, planned_tonnage)
    ]

    # Combine variance data for table rendering
    variance_data = []
    for p in phases:
        planned = p.planned_tonnage
        removed = p.removed_tonnage
        var = removed - planned
        var_pct = ((removed - planned) / planned) * 100 if planned else None

        variance_data.append({
            'phase': p.mine_phase.name,
            'planned': planned,
            'removed': removed,
            'variance': round(var, 2),
            'variance_percent': round(var_pct, 2) if var_pct is not None else None,
        })

    # Ore and waste movement per phase
    ore_movement = []
    waste_movement = []
    for p in phases:
        records = p.mine_phase.production_records
        ore = records.filter(material_type='ore').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
        waste = records.filter(material_type='waste').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
        ore_movement.append(round(ore, 2))
        waste_movement.append(round(waste, 2))

    context = {
        "phases": phases,
        "active_phases_count": active_phases.count(),
        "completed_phases_count": completed_phases.count(),
        "phase_names": phase_names,
        "planned_tonnage": planned_tonnage,
        "removed_tonnage": removed_tonnage,
        "progress_percentages": progress_percentages,
        "ore_movement": ore_movement,
        "waste_movement": waste_movement,
        "variance": variance,
        "variance_percent": variance_percent,
        "variance_data": variance_data,
    }

    return render(request, 'dashboard/phase_progress.html', context)


def mine_plant_dashboard(request):
    """
    Renders the main dashboard home page linking all sections.
    """
    return render(request, 'dashboard/home.html')



def add_stockpile(request):
    """ -In this view we Add Stockpile"""
    if request.method == 'POST':
        form = StockpileForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('stockpile-forecast')  # goes to stockpile dashboard
    else:
        form = StockpileForm()
    return render(request, 'dashboard/add_stockpile.html', {'form': form})


def add_production(request):
    """--- Add Production ---"""
    if request.method == 'POST':
        form = ProductionRecordForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('production-vs-demand')  # goes to production vs demand dashboard
    else:
        form = ProductionRecordForm()
    return render(request, 'dashboard/add_production.html', {
        'form': form,
        'plants': Plant.objects.all()
    })

def add_oresample(request):
    """ --- Add Ore Sample ---"""
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


def add_plantdemand(request):
    """ --- Add Plant Demand ---"""
    if request.method == 'POST':
        form = PlantDemandForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('production-vs-demand')  # goes to production vs demand dashboard
    else:
        form = PlantDemandForm()
    return render(request, 'dashboard/add_plantdemand.html', {'form': form})

# --- Add Phase Schedule ---
def add_phaseschedule(request):
    if request.method == 'POST':
        form = PhaseScheduleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('pit_phase_dashboard')  # goes to phase progress dashboard
    else:
        form = PhaseScheduleForm()
    return render(request, 'dashboard/add_phaseschedule.html', {'form': form})


def welcome_dashboard(request):
    return render(request, 'dashboard/home_dashboard.html')

def pit_map_view(request):
    """ Path to STR file (adjust if yours has a different name) """
    str_file = os.path.join(
        os.path.dirname(__file__),
        'static', 'data', 'pit_design.str'
    )

    if not os.path.exists(str_file):
        return render(request, 'dashboard/pit_preview.html', {
            'error': f'STR file not found at {str_file}'
        })

    # Parse the STR file
    phases = parse_str_file(str_file)
    if not phases:
        return render(request, 'dashboard/pit_preview.html', {
            'error': 'Failed to read coordinates from STR file.'
        })

    # Plot pit map
    plt.figure(figsize=(10, 8))
    for name, coords in phases.items():
        xs, ys, zs = zip(*coords)
        plt.scatter(xs, ys, s=6, label=name)
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title('Pit STR Progress Map')
    plt.legend(fontsize=8)
    plt.axis('equal')

    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    pit_map_img = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    plt.close()

    # Example data for the charts
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




def pit_phase_dashboard(request):
    # Get all phases ordered by sequence
    phases = PhaseSchedule.objects.select_related('mine_phase').all().order_by('mine_phase__sequence_order')

    phase_names = [p.mine_phase.name for p in phases]
    progress_percentages = [round(p.current_progress, 2) for p in phases]

    # Prepare Planned vs Actual data
    planned_tonnage = []
    actual_ore = []
    actual_waste = []
    variance_total = []

    for p in phases:
        planned = p.planned_tonnage
        planned_tonnage.append(round(planned, 2))

        records = p.mine_phase.production_records
        ore = records.filter(material_type='ore').aggregate(Sum('tonnage'))['tonnage__sum'] or 0
        waste = records.filter(material_type='waste').aggregate(Sum('tonnage'))['tonnage__sum'] or 0

        actual_ore.append(round(ore, 2))
        actual_waste.append(round(waste, 2))
        variance_total.append(round((ore + waste) - planned, 2))  # Overbreak / Underbreak

    # KPI Totals
    total_planned = sum(planned_tonnage)
    total_actual = sum(actual_ore) + sum(actual_waste)
    total_variance = total_actual - total_planned

    context = {
        "phases": phases,
        "phase_names": phase_names,
        "progress_percentages": progress_percentages,
        "planned_tonnage": planned_tonnage,
        "actual_ore": actual_ore,
        "actual_waste": actual_waste,
        "variance_total": variance_total,
        "total_planned": total_planned,
        "total_actual": total_actual,
        "total_variance": total_variance,
    }
    return render(request, "dashboard/pit_phase_dashboard.html", context)

@csrf_exempt
def update_expected_values(request, phase_id):
    """AJAX endpoint for inline editing of expected grade/tonnage."""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            field = data.get("field")
            value = data.get("value")

            phase = MinePhase.objects.get(id=phase_id)

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

        except MinePhase.DoesNotExist:
            return JsonResponse({"success": False, "error": "Phase not found"}, status=404)
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)

    return JsonResponse({"success": False, "error": "Invalid request method"}, status=405)


def export_pdf(request):
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


def production_summary(request):
    records = ProductionRecord.objects.order_by('-timestamp')[:20]  # last 20 records
    return render(request, 'dashboard/production_summary.html', {'records': records})


#adding these views for experimental puropses and later integration
def processing_loss_dashboard(request):
    # Main page; charts fetch data via AJAX from `processing_loss_data`
    return render(request, 'dashboard/processing_loss_analysis.html')

def processing_loss_data(request):
    period = request.GET.get('period', 'daily')
    start = request.GET.get('start')
    end = request.GET.get('end')

    qs = ProductionRecord.objects.all()

    # ✅ Match date-only input from frontend
    if start:
        start_date = date.fromisoformat(start)
        qs = qs.filter(timestamp__date__gte=start_date)
    if end:
        end_date = date.fromisoformat(end)
        qs = qs.filter(timestamp__date__lte=end_date)

    qs = [r for r in qs if r.is_underbreak()]

    # ✅ Aggregate into buckets
    buckets = {}

    def bucket_key(rec):
        if period == 'weekly':
            return rec.timestamp.date().isocalendar()[0:2]  # (year, week)
        if period == 'monthly':
            return (rec.timestamp.year, rec.timestamp.month)
        return rec.timestamp.date()  # Default daily

    for r in qs:
        key = bucket_key(r)
        if key not in buckets:
            buckets[key] = {'gold_lost_kg': 0.0, 'revenue_lost_usd': 0.0}

        buckets[key]['gold_lost_kg'] += r.gold_lost_kg()
        buckets[key]['revenue_lost_usd'] += r.revenue_lost_usd()

    # ✅ Prepare chart data
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