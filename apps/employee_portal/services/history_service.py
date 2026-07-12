from apps.attendance.models import AttendanceRecord
from apps.daily_sessions.models import DailyEmployeePerformance

class HistoryService:
    @staticmethod
    def get_attendance_history(employee):
        """Returns queryset of attendance records for the employee"""
        return AttendanceRecord.objects.filter(employee=employee).order_by('-date')

    @staticmethod
    def get_work_history(employee):
        """Returns queryset of performance records (Work Days) for the employee"""
        return DailyEmployeePerformance.objects.filter(
            employee=employee
        ).select_related('work_day', 'team', 'team__photographer', 'team__clown').order_by('-work_day__date')
