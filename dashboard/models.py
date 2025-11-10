from django.db import models

class MinePhase(models.Model):
    """Represents a mining phase or pushback within a pit."""
    name = models.CharField(max_length=100)
    pit = models.CharField(max_length=100)
    phase_number = models.PositiveIntegerField()
    sequence_order = models.PositiveIntegerField()
    planned_start = models.DateField(null=True, blank=True)
    planned_end = models.DateField(null=True, blank=True)

    # Expected targets
    expected_grade = models.FloatField(null=True, blank=True, help_text="Expected average grade (g/t)")
    expected_tonnage = models.FloatField(null=True, blank=True, help_text="Expected total tonnage (t)")

    class Meta:
        ordering = ['sequence_order']

    def __str__(self):
        return f"{self.pit} - Phase {self.phase_number}"

    # --- Derived values ---
    def actual_grade(self):
        samples = self.ore_samples.all()
        if not samples.exists():
            return 0
        total_grade = sum(s.actual_grade_g_t * s.actual_tonnage for s in samples)
        total_tonnage = sum(s.actual_tonnage for s in samples)
        return round(total_grade / total_tonnage, 2) if total_tonnage > 0 else 0

    def actual_tonnage(self):
        return round(sum(s.actual_tonnage for s in self.ore_samples.all()), 2)

    def variance_grade(self):
        if self.expected_grade is None:
            return 0
        return round(self.actual_grade() - self.expected_grade, 2)

    def variance_tonnage(self):
        if self.expected_tonnage is None:
            return 0
        return round(self.actual_tonnage() - self.expected_tonnage, 2)


class OreSample(models.Model):
    """Ore grade samples taken from each phase."""
    mine_phase = models.ForeignKey(MinePhase, on_delete=models.CASCADE, related_name='ore_samples')
    timestamp = models.DateTimeField(auto_now_add=True)
    sample_id = models.CharField(max_length=100, blank=True)
    actual_grade_g_t = models.FloatField()
    actual_tonnage = models.FloatField(default=0.0, help_text="Tonnage in tons")
    expected_grade = models.FloatField()
    expected_tonnage = models.FloatField()

    @property
    def variance_grade(self):
        return self.actual_grade_g_t - self.expected_grade

    @property
    def variance_tonnage(self):
        return self.actual_tonnage - self.expected_tonnage

    def __str__(self):
        return f"{self.sample_id or 'Sample'} ({self.actual_grade_g_t} g/t)"


class Plant(models.Model):
    """Represents a processing plant (Plant A, Plant B, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=200, blank=True)
    capacity_tph = models.FloatField(null=True, blank=True, help_text="Capacity in tons per hour")

    def __str__(self):
        return self.name


class PlantDemand(models.Model):
    """Records plant ore demand over time for multiple plants."""
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="demands", null=True, blank=True)

    timestamp = models.DateTimeField()
    required_tonnage = models.FloatField()

    def __str__(self):
        plant_name = self.plant.name if self.plant else "Unknown Plant"
        timestamp = self.timestamp.date() if self.timestamp else "No Date"
        return f"{plant_name} - {timestamp}: {self.required_tonnage}t"


class ProductionRecord(models.Model):
    """Tracks production tonnage for each phase and plant."""
    mine_phase = models.ForeignKey(
        MinePhase, on_delete=models.CASCADE, related_name='production_records'
    )
    plant = models.ForeignKey(Plant, on_delete=models.CASCADE, related_name="productions", null=True, blank=True)
    timestamp = models.DateTimeField()
    tonnage = models.FloatField()
    expected_tonnage = models.FloatField(null=True, blank=True, help_text="Planned tonnage for this batch")
    material_type = models.CharField(
        max_length=20,
        choices=[('ore', 'Ore'), ('waste', 'Waste')],
        default='ore'
    )
    source = models.CharField(max_length=100, blank=True)

    def overbreak_or_underbreak(self):
        """Determine if actual production exceeded or fell below expected tonnage."""
        if not self.expected_tonnage:
            return "N/A"
        diff = self.tonnage - self.expected_tonnage
        if diff > 0:
            return f"Overbreak (+{diff:.2f}t)"
        elif diff < 0:
            return f"Underbreak ({diff:.2f}t)"
        return "On target"

    def __str__(self):
        return f"{self.mine_phase} → {self.plant or 'No Plant'} ({self.tonnage}t)"


class Stockpile(models.Model):
    """Tracks ore stockpiles ready for plant feed."""
    name = models.CharField(max_length=100)
    current_tonnage = models.FloatField(default=0)
    projected_tonnage = models.FloatField(default=0)
    grade = models.FloatField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.current_tonnage}t)"

    def variance(self):
        return self.current_tonnage - self.projected_tonnage

    def variance_percent(self):
        if self.projected_tonnage:
            return ((self.current_tonnage - self.projected_tonnage) / self.projected_tonnage) * 100
        return 0


class PhaseSchedule(models.Model):
    """Monitors progress of a mining phase."""
    mine_phase = models.OneToOneField('MinePhase', on_delete=models.CASCADE, related_name='schedule')
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
        total_removed = (
            self.mine_phase.production_records.aggregate(models.Sum('tonnage'))['tonnage__sum'] or 0
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