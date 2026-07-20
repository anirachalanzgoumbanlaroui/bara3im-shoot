from datetime import date, timedelta
from django.db.models import Sum, Count, Q
from apps.attendance.models import AttendanceRecord
from apps.daily_sessions.models import DailyEmployeePerformance, WorkDay

class StatisticsService:
    @staticmethod
    def get_statistics(employee):
        today = date.today()
        role = employee.role
        
        if role == 'seller':
            from apps.daily_sessions.models import SellerDailyOperation
            ops = list(SellerDailyOperation.objects.filter(seller=employee).order_by('work_day__date'))
            
            # Monthly overview
            start_of_month = date(today.year, today.month, 1)
            month_ops = SellerDailyOperation.objects.filter(
                seller=employee,
                work_day__date__gte=start_of_month,
                work_day__date__lte=today
            )
            month_worked_days = month_ops.count()
            month_earnings = float(month_ops.aggregate(total=Sum('amount'))['total'] or 0.0)
            
            # Weekly stats
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            week_ops = SellerDailyOperation.objects.filter(
                seller=employee,
                work_day__date__gte=start_of_week,
                work_day__date__lte=end_of_week
            )
            week_worked_days = week_ops.count()
            week_earnings = float(week_ops.aggregate(total=Sum('amount'))['total'] or 0.0)
            
            # Bar chart data for earnings (repuposed fields to prevent crash)
            daily_photo_counts = []
            days_of_week_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            for i in range(7):
                d = start_of_week + timedelta(days=i)
                op_d = week_ops.filter(work_day__date=d).first()
                daily_photo_counts.append({
                    'day': days_of_week_names[i],
                    'photos': int(op_d.amount) if op_d else 0, # Map earnings to photos to utilize chart
                    'date': d.isoformat(),
                })
                
            all_time_earnings = float(SellerDailyOperation.objects.filter(seller=employee).aggregate(total=Sum('amount'))['total'] or 0.0)
            best_day = float(SellerDailyOperation.objects.filter(seller=employee).aggregate(max_val=Max('amount'))['max_val'] or 0.0)
            
            # Attendance stats
            all_att = AttendanceRecord.objects.filter(employee=employee)
            all_att_stats = all_att.aggregate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present')),
                late=Count('id', filter=Q(status='late')),
                absent=Count('id', filter=Q(status='absent'))
            )
            all_total = all_att_stats['total'] or 0
            all_pres_late = (all_att_stats['present'] or 0) + (all_att_stats['late'] or 0)
            all_att_rate = (all_pres_late / all_total * 100.0) if all_total > 0 else 0.0
            
            # Month attendance
            month_attendance = AttendanceRecord.objects.filter(
                employee=employee,
                date__gte=start_of_month,
                date__lte=today
            )
            month_att_stats = month_attendance.aggregate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present')),
                late=Count('id', filter=Q(status='late')),
                absent=Count('id', filter=Q(status='absent'))
            )
            month_total_days = month_att_stats['total'] or 0
            month_present_late_days = (month_att_stats['present'] or 0) + (month_att_stats['late'] or 0)
            month_att_rate = (month_present_late_days / month_total_days * 100.0) if month_total_days > 0 else 0.0
            
            # Attendance Streak
            current_streak = 0
            temp_streak = 0
            prev_d = None
            for r in list(all_att.order_by('date')):
                if r.status in ['present', 'late']:
                    if prev_d is None or (r.date - prev_d).days == 1:
                        temp_streak += 1
                    elif (r.date - prev_d).days > 1:
                        temp_streak = 1
                    prev_d = r.date
                else:
                    temp_streak = 0
                    prev_d = None
            if prev_d and (today - prev_d).days <= 1:
                current_streak = temp_streak
            else:
                current_streak = 0

            return {
                'worked_days': len(ops),
                'attendance_rate': round(all_att_rate, 2),
                'present_days': all_att_stats['present'] or 0,
                'late_days': all_att_stats['late'] or 0,
                'absent_days': all_att_stats['absent'] or 0,
                'total_photos': 0,
                'average_photos_per_day': 0.0,
                'estimated_monthly_earnings': month_earnings,
                'best_day_earnings': best_day,
                'worst_day_earnings': 0.0,
                'weekly_stats': {
                    'worked_days': week_worked_days,
                    'attendance_rate': round(month_att_rate, 2),
                    'average_photos': 0.0,
                    'weekly_photos': 0,
                    'weekly_earnings': week_earnings,
                    'weekly_goal_completion': 0.0,
                    'daily_photo_counts': daily_photo_counts,
                },
                'monthly_overview': {
                    'worked_days': month_worked_days,
                    'present_days': month_att_stats['present'] or 0,
                    'late_days': month_att_stats['late'] or 0,
                    'absent_days': month_att_stats['absent'] or 0,
                    'total_photos': 0,
                    'average_photos_per_day': 0.0,
                    'estimated_monthly_earnings': month_earnings,
                    'best_performance_day': None,
                    'current_attendance_streak': current_streak,
                    'goal_completion_rate': 0.0,
                },
            }
        
        # 1. Monthly Overview
        start_of_month = date(today.year, today.month, 1)
        if today.month == 12:
            end_of_month = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_of_month = date(today.year, today.month + 1, 1) - timedelta(days=1)
            
        month_perf = DailyEmployeePerformance.objects.filter(
            employee=employee,
            work_day__date__gte=start_of_month,
            work_day__date__lte=end_of_month
        ).select_related('work_day')
        
        month_worked_days = month_perf.count()
        month_total_photos = month_perf.aggregate(total=Sum('photo_count'))['total'] or 0
        month_avg_photos = (month_total_photos / month_worked_days) if month_worked_days > 0 else 0.0
        
        month_earnings = 0.0
        best_perf_day = None
        best_day_photos = 0
        best_day_earns = 0.0
        days_met_goal = 0
        
        for p in month_perf:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            earns = float(p.photo_count * u_price)
            month_earnings += earns
            
            if earns > best_day_earns:
                best_day_earns = earns
                best_day_photos = p.photo_count
                best_perf_day = p.work_day.date.isoformat()
                
            if p.photo_count >= 50:
                days_met_goal += 1
                
        month_goal_rate = (days_met_goal / month_worked_days * 100.0) if month_worked_days > 0 else 0.0
        
        # Month attendance
        month_attendance = AttendanceRecord.objects.filter(
            employee=employee,
            date__gte=start_of_month,
            date__lte=end_of_month
        )
        
        month_att_stats = month_attendance.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent'))
        )
        
        month_total_days = month_att_stats['total'] or 0
        month_present = month_att_stats['present'] or 0
        month_late = month_att_stats['late'] or 0
        month_absent = month_att_stats['absent'] or 0
        month_present_late_days = month_present + month_late
        month_att_rate = (month_present_late_days / month_total_days * 100.0) if month_total_days > 0 else 0.0
        
        # Attendance Streak
        all_att_asc = list(AttendanceRecord.objects.filter(employee=employee).order_by('date'))
        current_streak = 0
        temp_streak = 0
        prev_d = None
        for r in all_att_asc:
            if r.status in ['present', 'late']:
                if prev_d is None or (r.date - prev_d).days == 1:
                    temp_streak += 1
                elif (r.date - prev_d).days > 1:
                    temp_streak = 1
                prev_d = r.date
            else:
                temp_streak = 0
                prev_d = None
        if prev_d and (today - prev_d).days <= 1:
            current_streak = temp_streak
        else:
            current_streak = 0
            
        monthly_overview = {
            'worked_days': month_worked_days,
            'present_days': month_present,
            'late_days': month_late,
            'absent_days': month_absent,
            'total_photos': month_total_photos,
            'average_photos_per_day': round(month_avg_photos, 2),
            'estimated_monthly_earnings': month_earnings,
            'best_performance_day': best_perf_day,
            'current_attendance_streak': current_streak,
            'goal_completion_rate': round(month_goal_rate, 2),
        }
        
        # 2. Weekly Statistics
        # Start and end of the current week (Monday to Sunday)
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        week_perf = DailyEmployeePerformance.objects.filter(
            employee=employee,
            work_day__date__gte=start_of_week,
            work_day__date__lte=end_of_week
        ).select_related('work_day')
        
        week_worked_days = week_perf.count()
        week_total_photos = week_perf.aggregate(total=Sum('photo_count'))['total'] or 0
        week_avg_photos = (week_total_photos / week_worked_days) if week_worked_days > 0 else 0.0
        
        week_earnings = 0.0
        week_days_met_goal = 0
        for p in week_perf:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            week_earnings += float(p.photo_count * u_price)
            if p.photo_count >= 50:
                week_days_met_goal += 1
                
        week_goal_completion = (week_days_met_goal / week_worked_days * 100.0) if week_worked_days > 0 else 0.0
        
        week_attendance = AttendanceRecord.objects.filter(
            employee=employee,
            date__gte=start_of_week,
            date__lte=end_of_week
        )
        week_att_stats = week_attendance.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late'))
        )
        week_total_days = week_att_stats['total'] or 0
        week_present_late_days = (week_att_stats['present'] or 0) + (week_att_stats['late'] or 0)
        week_att_rate = (week_present_late_days / week_total_days * 100.0) if week_total_days > 0 else 0.0
        
        # Build bar chart data (Mon-Sun)
        daily_photo_counts = []
        days_of_week_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for i in range(7):
            d = start_of_week + timedelta(days=i)
            perf_d = week_perf.filter(work_day__date=d).first()
            daily_photo_counts.append({
                'day': days_of_week_names[i],
                'photos': perf_d.photo_count if perf_d else 0,
                'date': d.isoformat(),
            })
            
        weekly_stats = {
            'worked_days': week_worked_days,
            'attendance_rate': round(week_att_rate, 2),
            'average_photos': round(week_avg_photos, 2),
            'weekly_photos': week_total_photos,
            'weekly_earnings': week_earnings,
            'weekly_goal_completion': round(week_goal_completion, 2),
            'daily_photo_counts': daily_photo_counts,
        }
        
        # All time / fallback stats for backward compatibility
        all_perf = DailyEmployeePerformance.objects.filter(employee=employee).select_related('work_day')
        all_worked = all_perf.count()
        all_photos = all_perf.aggregate(total=Sum('photo_count'))['total'] or 0
        all_avg = (all_photos / all_worked) if all_worked > 0 else 0.0
        
        all_earnings = 0.0
        best_day_earns_all = 0.0
        worst_day_earns_all = None
        for p in all_perf:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            earns = float(p.photo_count * u_price)
            all_earnings += earns
            if earns > best_day_earns_all:
                best_day_earns_all = earns
            if worst_day_earns_all is None or earns < worst_day_earns_all:
                worst_day_earns_all = earns
                
        all_att = AttendanceRecord.objects.filter(employee=employee)
        all_att_stats = all_att.aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            late=Count('id', filter=Q(status='late')),
            absent=Count('id', filter=Q(status='absent'))
        )
        all_total = all_att_stats['total'] or 0
        all_pres_late = (all_att_stats['present'] or 0) + (all_att_stats['late'] or 0)
        all_att_rate = (all_pres_late / all_total * 100.0) if all_total > 0 else 0.0

        return {
            'worked_days': all_worked,
            'attendance_rate': round(all_att_rate, 2),
            'present_days': all_att_stats['present'] or 0,
            'late_days': all_att_stats['late'] or 0,
            'absent_days': all_att_stats['absent'] or 0,
            'total_photos': all_photos,
            'average_photos_per_day': round(all_avg, 2),
            'estimated_monthly_earnings': month_earnings,
            'best_day_earnings': best_day_earns_all,
            'worst_day_earnings': worst_day_earns_all or 0.0,
            'weekly_stats': weekly_stats,
            'monthly_overview': monthly_overview,
        }
