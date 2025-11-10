from django.contrib import admin

from .models import MinePhase, ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule, Plant

admin.site.register(MinePhase)
admin.site.register(ProductionRecord)
admin.site.register(OreSample)
admin.site.register(PlantDemand)
admin.site.register(Stockpile)
admin.site.register(PhaseSchedule)
admin.site.register(Plant)

# Register your models here.
