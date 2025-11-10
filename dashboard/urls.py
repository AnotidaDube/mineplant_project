from django.urls import path
from . import views
from .views import pit_map_view

urlpatterns = [
    path('dashboard/production_vs_demand/', views.production_vs_demand_view, name='production-vs-demand'),
    path('dashboard/ore_grade_tonnage/', views.ore_grade_tonnage_view, name='ore-grade-tonnage'),
    path('dashboard/stockpile_forecast/', views.stockpile_forecast_view, name='stockpile-forecast'),
    path('dashboard/phase_progress/', views.phase_progress_view, name='pit_phase_dashboard'),
    path('dashboard/', views.mine_plant_dashboard, name='mine_plant_dashboard'),
    path('', views.welcome_dashboard, name='home_dashboard'),
    
    # Add data input pages
    path('dashboard/add_stockpile/', views.add_stockpile, name='add-stockpile'),
    path('dashboard/add_production/', views.add_production, name='add-production'),
    path('dashboard/add_oresample/', views.add_oresample, name='add-oresample'),
    path('dashboard/add_plantdemand/', views.add_plantdemand, name='add-plantdemand'),
    path('dashboard/add_phaseschedule/', views.add_phaseschedule, name='add-phaseschedule'),
    path('update-expected/<int:phase_id>/', views.update_expected_values, name='update-expected'),
    path('export-pdf/', views.export_pdf, name='export-pdf'),
    


    #pitmap
    path('pit-map/', views.pit_map_view, name='pit_map'),
   
    path('dashboard/pit_phase_dashboard/', views.pit_phase_dashboard, name='pit-phase-dashboard'),
    

]
