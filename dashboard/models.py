from django.db import models
from django.conf import settings

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
    capacity_tph = models.FloatField(
        null=True, blank=True,
        help_text="Plant throughput capacity (tons per hour)"
    )

    # --- Default processing parameters (used if not set in ProductionRecord) ---
    default_grade = models.FloatField(
        null=True, blank=True, help_text="Default feed grade in g/t"
    )
    default_recovery = models.FloatField(
        null=True, blank=True, help_text="Default gold recovery fraction (e.g. 0.92 = 92%)"
    )
    default_gold_price = models.FloatField(
        null=True, blank=True, help_text="Default gold price per kg (USD)"
    )

    class Meta:
        verbose_name = "Processing Plant"
        verbose_name_plural = "Processing Plants"
        ordering = ['name']

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
    """Tracks production tonnage, grade, and economic impact for each phase and plant."""
    
    mine_phase = models.ForeignKey(
        'MinePhase', on_delete=models.CASCADE, related_name='production_records'
    )
    plant = models.ForeignKey(
        'Plant', on_delete=models.CASCADE, related_name='productions', null=True, blank=True
    )
    timestamp = models.DateTimeField()
    tonnage = models.FloatField()
    expected_tonnage = models.FloatField(
        null=True, blank=True, help_text="Planned tonnage for this batch"
    )
    material_type = models.CharField(
        max_length=20,
        choices=[('ore', 'Ore'), ('waste', 'Waste')],
        default='ore'
    )
    variance = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, blank=True)
    source = models.CharField(max_length=100, blank=True)

    # --- New adjustable fields for economic calculations ---
    grade = models.FloatField(null=True, blank=True, help_text="Grade in g/t")
    recovery = models.FloatField(null=True, blank=True, help_text="Recovery fraction (0.9 = 90%)")
    gold_price = models.FloatField(null=True, blank=True, help_text="Gold price per kg (USD)")

    class Meta:
        ordering = ['-timestamp']

    # --- Auto-calculated variance and status ---
    def save(self, *args, **kwargs):
        """Auto-calculate tonnage variance and status before saving."""
        if self.expected_tonnage is not None:
            self.variance = self.tonnage - self.expected_tonnage
            if self.variance > 0:
                self.status = "Overbreak"
            elif self.variance < 0:
                self.status = "Underbreak"
            else:
                self.status = "Balanced"
        else:
            self.variance = None
            self.status = "N/A"
        super().save(*args, **kwargs)

    # --- Processing loss calculations ---
    def is_underbreak(self):
        return self.status == "Underbreak" and self.variance is not None

    def _effective_grade(self):
        """Get effective grade (record > plant default > global default)."""
        if self.grade is not None:
            return self.grade
        if self.plant and getattr(self.plant, 'default_grade', None) is not None:
            return self.plant.default_grade
        return getattr(settings, 'DEFAULT_GRADE_GPT', None)

    def _effective_recovery(self):
        """Get effective recovery (record > plant default > global default)."""
        if self.recovery is not None:
            return self.recovery
        if self.plant and getattr(self.plant, 'default_recovery', None) is not None:
            return self.plant.default_recovery
        return getattr(settings, 'DEFAULT_RECOVERY', None)

    def _effective_gold_price(self):
        """Get effective gold price (record > plant default > global default)."""
        if self.gold_price is not None:
            return self.gold_price
        if self.plant and getattr(self.plant, 'default_gold_price', None) is not None:
            return self.plant.default_gold_price
        return getattr(settings, 'DEFAULT_GOLD_PRICE_PER_KG', None)

    def gold_lost_kg(self):
        """Calculate gold lost (in kg) when underbreak occurs."""
        if not self.is_underbreak():
            return 0.0

        grade = self._effective_grade()
        recovery = self._effective_recovery()
        if grade is None or recovery is None:
            return 0.0

        variance_t = abs(self.variance)
        gold_kg = variance_t * grade * recovery / 1000.0  # (tonnes * g/t = g, /1000 = kg)
        return round(gold_kg, 6)

    def revenue_lost_usd(self):
        """Calculate revenue lost (in USD) due to gold lost."""
        gold_kg = self.gold_lost_kg()
        if gold_kg <= 0:
            return 0.0
        price = self._effective_gold_price()
        if price is None:
            return 0.0
        return round(gold_kg * price, 2)

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