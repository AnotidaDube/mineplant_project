from rest_framework import serializers
from .models import MinePhase, ProductionRecord, OreSample, PlantDemand, Stockpile, PhaseSchedule

class MinePhaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MinePhase
        fields = '__all__'

class ProductionRecordSerializer(serializers.ModelSerializer):
    mine_phase = MinePhaseSerializer()  # nested
    class Meta:
        model = ProductionRecord
        fields = '__all__'

class OreSampleSerializer(serializers.ModelSerializer):
    mine_phase = MinePhaseSerializer()  # nested serializer
    class Meta:
        model = OreSample
        fields = '__all__'


class PlantDemandSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlantDemand
        fields = '__all__'

class StockpileSerializer(serializers.ModelSerializer):
    timestamp = serializers.DateTimeField(source='last_updated')

    class Meta:
        model = Stockpile
        fields = ['name', 'current_tonnage', 'timestamp']

class PhaseScheduleSerializer(serializers.ModelSerializer):
    mine_phase = MinePhaseSerializer()  # nested
    class Meta:
        model = PhaseSchedule
        fields = '__all__'

