from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import ProductionRecord, PhaseSchedule

# WebSocket broadcasting
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

@receiver(post_save, sender=ProductionRecord)
def update_phase_schedule_on_production(sender, instance, created, **kwargs):
    phase = instance.mine_phase

    # Update schedule if the related PhaseSchedule exists
    try:
        schedule = PhaseSchedule.objects.get(mine_phase=phase)
        schedule.update_removed_tonnage()  #existing method
    except PhaseSchedule.DoesNotExist:
        print(f"No schedule found for phase: {phase}")
    
    # Broadcast real-time update ONLY if it's a new record
    if created:
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "production_updates",  # Group name (WebSocket subscribers)
                {
                    "type": "production_update",
                    "data": {
                        "id": instance.id,
                        "phase": str(phase),
                        "timestamp": instance.timestamp.isoformat(),
                        "tonnage": instance.tonnage,
                    }
                }
            )
            print("Production update broadcasted 🚀")
        except Exception as e:
            print(f"WebSocket broadcast failed: {e}")
