from apps.attendance.models import AttendanceRecord
from apps.daily_sessions.models import DailyEmployeePerformance
from apps.notifications.models import Notification
from django.db.models import F

class TimelineService:
    @staticmethod
    def get_timeline(employee):
        """
        Aggregates events from Attendance, Performance (WorkDays), and Notifications.
        Returns a chronologically sorted list of dictionaries.
        """
        events = []
        
        # Attendance events
        attendances = AttendanceRecord.objects.filter(employee=employee).order_by('-check_in_time')[:20]
        for att in attendances:
            events.append({
                'type': 'attendance',
                'title': 'Attendance Recorded',
                'description': f"Checked in as {att.status} at {att.check_in_time.strftime('%H:%M')}",
                'timestamp': att.check_in_time,
                'icon': 'fingerprint'
            })
            
        # Work Result events
        performances = DailyEmployeePerformance.objects.filter(
            employee=employee
        ).select_related('work_day').order_by('-updated_at')[:20]
        
        for perf in performances:
            unit_price = perf.work_day.photographer_unit_price if employee.role == 'photographer' else perf.work_day.clown_unit_price
            earnings = perf.photo_count * unit_price
            events.append({
                'type': 'work_results',
                'title': 'Results Published',
                'description': f"{perf.photo_count} photos - Earnings: {earnings} DA",
                'timestamp': perf.updated_at,
                'icon': 'camera'
            })
                
        # Notifications
        notifications = Notification.objects.filter(user=employee.user).order_by('-timestamp')[:20]
        for notif in notifications:
            events.append({
                'type': 'notification',
                'title': notif.title,
                'description': notif.description,
                'timestamp': notif.timestamp,
                'icon': notif.icon or 'bell'
            })
            
        # Sort combined events by timestamp descending
        events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Serialize timestamps
        for e in events:
            e['timestamp'] = e['timestamp'].isoformat()
            
        return events
