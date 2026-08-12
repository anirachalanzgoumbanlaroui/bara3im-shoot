from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from apps.daily_sessions.models import WorkDay, DailyTeam, DailyEmployeePerformance, SellerDailyOperation
from apps.employees.models import Bonus, Deduction
from apps.attendance.models import AttendanceRecord
from .services import StatisticsService


@receiver([post_save, post_delete], sender=WorkDay)
@receiver([post_save, post_delete], sender=DailyTeam)
@receiver([post_save, post_delete], sender=DailyEmployeePerformance)
@receiver([post_save, post_delete], sender=SellerDailyOperation)
@receiver([post_save, post_delete], sender=Bonus)
@receiver([post_save, post_delete], sender=Deduction)
@receiver([post_save, post_delete], sender=AttendanceRecord)
def invalidate_statistics_cache(sender, **kwargs):
    """
    Automated signal listener to clear statistics cache on data mutations.
    """
    StatisticsService.clear_cache()
