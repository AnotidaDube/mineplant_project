from django.urls import path
from . import views

urlpatterns = [
    # ==========================
    # 1. Main Dashboards
    # ==========================
    path('', views.welcome_dashboard, name='home_dashboard'),
    path('dashboard/', views.mine_plant_dashboard, name='mine_plant_dashboard'),
    
    # This is your MAIN Pit Dashboard (The one we fixed)
    path('dashboard/phase_progress/', views.phase_progress_view, name='pit_phase_dashboard'),

    # ==========================
    # 2. Strategic Planning & Schedule
    # ==========================
    path('upload-schedule/', views.upload_schedule_view, name='upload_schedule'),
    path('schedule-dashboard/', views.schedule_dashboard_view, name='schedule_dashboard'),
    path('reconciliation/', views.reconciliation_view, name='reconciliation'),
    path('auto-generate/', views.auto_generate_phases, name='auto_generate_phases'),

    # ==========================
    # 3. Operational Analysis
    # ==========================
    path('dashboard/production_vs_demand/', views.production_vs_demand_view, name='production-vs-demand'),
    path('dashboard/ore_grade_tonnage/', views.ore_grade_tonnage_view, name='ore-grade-tonnage'),
    path('dashboard/stockpile_forecast/', views.stockpile_forecast, name='stockpile-forecast'),
    path('production_summary/', views.production_summary, name='production_summary'),
    path('mass-analysis/', views.mass_analysis_view, name='mass_analysis'),
    
    # ==========================
    # 4. Processing Plant
    # ==========================
    path('processing/loss/', views.processing_loss_dashboard, name='processing-loss-dashboard'),
    path('processing/loss/data/', views.processing_loss_data, name='processing-loss-data'),

    # ==========================
    # 5. Data Entry Forms
    # ==========================
    path('dashboard/add_stockpile/', views.add_stockpile, name='add-stockpile'),
    path('dashboard/add_production/', views.add_production, name='add-production'),
    path('dashboard/add_oresample/', views.add_oresample, name='add-oresample'),
    path('dashboard/add_plantdemand/', views.add_plantdemand, name='add-plantdemand'),
    path('dashboard/add_phaseschedule/', views.add_phaseschedule, name='add-phaseschedule'),
    path('dashboard/upload-blocks/', views.upload_block_model, name='upload_block_model'),
    
    # ==========================
    # 6. API & Utilities
    # ==========================
    path('update-expected/<int:phase_id>/', views.update_expected_values, name='update-expected'),
    path('export-pdf/', views.export_pdf, name='export-pdf'),
    path("pit-data/", views.pit_data, name="pit-data"),
    path('pit-map/', views.pit_map_view, name='pit_map'),
    path('manage_plants/', views.manage_plants, name='manage-plants'),

    #planning tool
    path('planning/', views.planning_dashboard, name='planning_dashboard'),
]