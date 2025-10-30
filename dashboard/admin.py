from django.contrib import admin

from django.contrib import admin
from .models import MinePhase, ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule

admin.site.register(MinePhase)
admin.site.register(ProductionRecord)
admin.site.register(OreSample)
admin.site.register(PlantDemand)
admin.site.register(Stockpile)
admin.site.register(PhaseSchedule)

# Register your models here.
