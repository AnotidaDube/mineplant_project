from django.urls import path
from . import views

urlpatterns = [
    path('minephases/', views.MinePhaseList.as_view(), name='minephase-list'),
    path('production/', views.ProductionRecordList.as_view(), name='production-list'),
    path('oresamples/', views.OreSampleList.as_view(), name='oresample-list'),
    path('plantdemand/', views.PlantDemandList.as_view(), name='plantdemand-list'),
    path('stockpiles/', views.StockpileList.as_view(), name='stockpile-list'),
    path('phaseschedule/', views.PhaseScheduleList.as_view(), name='phaseschedule-list'),
]
