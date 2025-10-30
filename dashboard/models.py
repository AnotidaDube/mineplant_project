from django.db import models



class MinePhase(models.Model):
    """Represents a mining phase or pushback within a pit."""
    name = models.CharField(max_length=100)
    pit = models.CharField(max_length=100)
    phase_number = models.PositiveIntegerField()
    sequence_order = models.PositiveIntegerField()
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f"{self.pit} - Phase {self.phase_number}"


class ProductionRecord(models.Model):
    """Tracks production tonnage for each phase over time."""
    mine_phase = models.ForeignKey(
        MinePhase, on_delete=models.CASCADE, related_name='production_records'
    )
    timestamp = models.DateTimeField()
    tonnage = models.FloatField()
    material_type = models.CharField(
        max_length=20,
        choices=[('ore', 'Ore'), ('waste', 'Waste')],
        default='ore'
    )
    source = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.timestamp} - {self.tonnage} tonns"


class OreSample(models.Model):
    """Ore grade samples taken from each phase."""
    mine_phase = models.ForeignKey(
        MinePhase, on_delete=models.CASCADE, related_name='ore_samples'
    )
    timestamp = models.DateTimeField()
    sample_id = models.CharField(max_length=100, blank=True)
    grade_g_t = models.FloatField()
    tonnage = models.FloatField(default=0.0, help_text="Tonnage in tons")

    def __str__(self):
        return f"{self.sample_id} ({self.grade_g_t} g/tonne)"


class PlantDemand(models.Model):
    """Records daily or hourly plant demand for ore tonnage."""
    timestamp = models.DateTimeField()
    required_tonnage = models.FloatField()

    def __str__(self):
        return f"{self.timestamp}: {self.required_tonnage} t"


class Stockpile(models.Model):
    """Tracks ore stockpiles ready for plant feed."""
    name = models.CharField(max_length=100)
    current_tonnage = models.FloatField(default=0)
    projected_tonnage = models.FloatField(default=0)  
    grade = models.FloatField(null=True, blank=True)  #ore grade %
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.current_tonnage} tonns)"

   
    def variance(self):
        return self.current_tonnage - self.projected_tonnage

    def variance_percent(self):
        if self.projected_tonnage:
            return ((self.current_tonnage - self.projected_tonnage) / self.projected_tonnage) * 100
        return 0

    


class PhaseSchedule(models.Model):
    """Monitors progress of a mining phase."""
    mine_phase = models.OneToOneField(
        'MinePhase', on_delete=models.CASCADE, related_name='schedule'
    )
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)
    planned_tonnage = models.FloatField(default=0)
    removed_tonnage = models.FloatField(default=0)
    current_progress = models.FloatField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('planned', 'Planned'),
            ('active', 'Active'),
            ('completed', 'Completed'),
        ],
        default='planned'
    )

    def update_removed_tonnage(self):
        """Auto-calculate total removed tonnage from ProductionRecords."""
        total_removed = (
            self.mine_phase.production_records.aggregate(models.Sum('tonnage'))['tonnage__sum']
            or 0
        )
        self.removed_tonnage = total_removed
        self.current_progress = self.progress_percent()
        self.update_status()
        self.save()

    def progress_percent(self):
        if self.planned_tonnage <= 0:
            return 0
        return round(min(100, (self.removed_tonnage / self.planned_tonnage) * 100), 1)

    def update_status(self):
        if self.current_progress == 0:
            self.status = 'planned'
        elif self.current_progress < 100:
            self.status = 'active'
        else:
            self.status = 'completed'

    def __str__(self):
        return f"{self.mine_phase} - {self.status}"
    

   