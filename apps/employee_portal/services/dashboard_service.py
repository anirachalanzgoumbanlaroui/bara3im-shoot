from datetime import date, timedelta
from django.db.models import Sum, Count, Avg, Max, Q
from django.db.models.functions import ExtractMonth, ExtractYear
from django.utils import timezone
from apps.attendance.models import AttendanceRecord, AttendanceRule
from apps.daily_sessions.models import DailyEmployeePerformance, DailyTeam, WorkDay
from apps.notifications.models import Notification
from apps.employees.models import Bonus, Advance, Deduction
from .motivation_service import MotivationService


class EmployeeDashboardService:
    @staticmethod
    def get_dashboard_data(employee):
        today = date.today()
        role = employee.role

        if role == 'seller':
            return EmployeeDashboardService.get_seller_dashboard_data(employee)

        # 1. Today's Attendance
        attendance = AttendanceRecord.objects.filter(employee=employee, date=today).first()
        attendance_data = {
            'status': attendance.status if attendance else 'No Attendance Recorded',
            'check_in_time': attendance.check_in_time.isoformat() if attendance else None,
            'minutes_late': attendance.minutes_late if attendance else 0,
        }

        # 2. Today's Performance & Team
        performance = DailyEmployeePerformance.objects.filter(
            employee=employee, work_day__date=today
        ).select_related('work_day', 'work_day__location', 'team', 'team__photographer', 'team__clown').first()

        team_data = None
        performance_data = None
        today_location = None

        if performance:
            wd = performance.work_day
            today_location = {
                'id': str(wd.location.id),
                'name': wd.location.name,
                'icon': wd.location.icon,
                'color_hex': wd.location.color_hex,
            }
            team = performance.team
            team_data = {
                'team_name': team.team_name,
                'photographer': f"{team.photographer.first_name} {team.photographer.last_name}",
                'clown': f"{team.clown.first_name} {team.clown.last_name}",
            }

            unit_price = wd.photographer_unit_price if role == 'photographer' else wd.clown_unit_price
            earnings = float(performance.photo_count * unit_price)

            performance_data = {
                'photo_count': performance.photo_count,
                'earnings': earnings,
                'unit_price': float(unit_price)
            }

        # 3. Financial Summary
        all_performances = DailyEmployeePerformance.objects.filter(
            employee=employee
        ).select_related('work_day')
        gross_earnings = 0.0
        for p in all_performances:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            gross_earnings += float(p.photo_count * u_price)

        late_records_count = AttendanceRecord.objects.filter(employee=employee, status='late').count()
        active_rule = AttendanceRule.get_active_rule()
        late_deduction_amount = float(active_rule.late_deduction_amount) if active_rule else 0.0
        late_penalties = float(late_records_count * late_deduction_amount)

        bonuses = float(Bonus.objects.filter(employee=employee).aggregate(total=Sum('amount'))['total'] or 0.0)
        advances = float(Advance.objects.filter(employee=employee).aggregate(total=Sum('amount'))['total'] or 0.0)
        deductions = float(Deduction.objects.filter(employee=employee).aggregate(total=Sum('amount'))['total'] or 0.0)

        net_balance = gross_earnings + bonuses - late_penalties - advances - deductions

        financial_summary = {
            'gross_earnings': gross_earnings,
            'late_penalties': late_penalties,
            'bonuses': bonuses,
            'advances': advances,
            'deductions': deductions,
            'net_balance': net_balance,
        }

        # 4. Today's Progress
        goal = 50
        today_photos = performance.photo_count if performance else 0
        progress_percentage = float(today_photos) / goal if goal > 0 else 0.0

        unit_price_today = 0.0
        if performance:
            unit_price_today = float(
                performance.work_day.photographer_unit_price if role == 'photographer'
                else performance.work_day.clown_unit_price
            )
        else:
            latest_workday = WorkDay.objects.order_by('-date').first()
            if latest_workday:
                unit_price_today = float(
                    latest_workday.photographer_unit_price if role == 'photographer'
                    else latest_workday.clown_unit_price
                )

        estimated_earnings = float(today_photos * unit_price_today)
        remaining_photos = max(0, goal - today_photos)

        if today_photos == 0:
            progress_msg = "Let's start strong today!"
        elif today_photos < goal:
            progress_msg = f"Only {remaining_photos} photos remaining to hit today's goal!"
        else:
            progress_msg = "Excellent! You exceeded today's goal."

        today_progress = {
            'photos': today_photos,
            'goal': goal,
            'percentage': progress_percentage,
            'estimated_earnings': estimated_earnings,
            'remaining_photos': remaining_photos,
            'status_message': progress_msg,
        }

        # 5. Dynamic Motivation Messages
        motivation_payload = MotivationService.get_message(attendance, performance, goal)

        # 6. Streak Calculations
        all_att_asc = list(AttendanceRecord.objects.filter(employee=employee).order_by('date'))
        current_att_streak = 0
        longest_att_streak = 0
        temp_streak = 0
        prev_d = None
        for r in all_att_asc:
            if r.status in ['present', 'late']:
                if prev_d is None or (r.date - prev_d).days == 1:
                    temp_streak += 1
                elif (r.date - prev_d).days > 1:
                    temp_streak = 1
                prev_d = r.date
                longest_att_streak = max(longest_att_streak, temp_streak)
            else:
                temp_streak = 0
                prev_d = None
        if prev_d and (today - prev_d).days <= 1:
            current_att_streak = temp_streak
        else:
            current_att_streak = 0

        # On-time Streak
        current_on_time_streak = 0
        longest_on_time_streak = 0
        temp_ot_streak = 0
        prev_ot_d = None
        for r in all_att_asc:
            if r.status == 'present':
                if prev_ot_d is None or (r.date - prev_ot_d).days == 1:
                    temp_ot_streak += 1
                elif (r.date - prev_ot_d).days > 1:
                    temp_ot_streak = 1
                prev_ot_d = r.date
                longest_on_time_streak = max(longest_on_time_streak, temp_ot_streak)
            else:
                temp_ot_streak = 0
                prev_ot_d = None
        if prev_ot_d and (today - prev_ot_d).days <= 1:
            current_on_time_streak = temp_ot_streak
        else:
            current_on_time_streak = 0

        # Goal Streak
        all_perf_asc = list(
            DailyEmployeePerformance.objects.filter(employee=employee)
            .select_related('work_day').order_by('work_day__date')
        )
        current_goal_streak = 0
        longest_goal_streak = 0
        temp_g_streak = 0
        prev_g_d = None
        for p in all_perf_asc:
            if p.photo_count >= goal:
                if prev_g_d is None or (p.work_day.date - prev_g_d).days == 1:
                    temp_g_streak += 1
                elif (p.work_day.date - prev_g_d).days > 1:
                    temp_g_streak = 1
                prev_g_d = p.work_day.date
                longest_goal_streak = max(longest_goal_streak, temp_g_streak)
            else:
                temp_g_streak = 0
                prev_g_d = None
        if prev_g_d and (today - prev_g_d).days <= 1:
            current_goal_streak = temp_g_streak
        else:
            current_goal_streak = 0

        # 7. Goals & Challenges
        goals_challenges = [
            {
                'id': 'challenge_goal_50',
                'name': 'Reach 50 photos today',
                'description': 'Take 50 photos in your current shift.',
                'progress': min(1.0, float(today_photos) / 50.0),
                'reward_icon': 'star',
                'status': 'completed' if today_photos >= 50 else 'in_progress',
                'current_value': today_photos,
                'target_value': 50
            },
            {
                'id': 'challenge_goal_60',
                'name': 'Reach 60 photos today',
                'description': 'Push harder and hit 60 photos today!',
                'progress': min(1.0, float(today_photos) / 60.0),
                'reward_icon': 'fire_flower',
                'status': 'completed' if today_photos >= 60 else 'in_progress',
                'current_value': today_photos,
                'target_value': 60
            },
            {
                'id': 'challenge_on_time',
                'name': 'Arrive on time',
                'description': 'Avoid lateness today by checking in early.',
                'progress': 1.0 if (attendance and attendance.status == 'present') else 0.0,
                'reward_icon': 'super_mushroom',
                'status': 'completed' if (attendance and attendance.status == 'present') else 'in_progress',
                'current_value': 1 if (attendance and attendance.status == 'present') else 0,
                'target_value': 1
            },
            {
                'id': 'challenge_no_late_5',
                'name': 'Punctual Streak',
                'description': 'Arrive on time for 5 consecutive work days.',
                'progress': min(1.0, float(current_on_time_streak) / 5.0),
                'reward_icon': 'yoshi_egg',
                'status': 'completed' if current_on_time_streak >= 5 else 'in_progress',
                'current_value': current_on_time_streak,
                'target_value': 5
            },
            {
                'id': 'challenge_work_10',
                'name': 'Dedicated Worker',
                'description': 'Attend work for 10 consecutive scheduled days.',
                'progress': min(1.0, float(current_att_streak) / 10.0),
                'reward_icon': 'gold_crown',
                'status': 'completed' if current_att_streak >= 10 else 'in_progress',
                'current_value': current_att_streak,
                'target_value': 10
            }
        ]

        # 8. Achievement Badges
        worked_days = len(all_perf_asc)
        max_photos_single_day = max([p.photo_count for p in all_perf_asc]) if all_perf_asc else 0
        total_photos = sum([p.photo_count for p in all_perf_asc]) if all_perf_asc else 0
        days_exceeding_goal = len([p for p in all_perf_asc if p.photo_count >= 50])

        monthly_totals = DailyEmployeePerformance.objects.filter(employee=employee).annotate(
            month=ExtractMonth('work_day__date'),
            year=ExtractYear('work_day__date')
        ).values('year', 'month').annotate(
            total_photos=Sum('photo_count')
        )
        max_photos_single_month = max([m['total_photos'] for m in monthly_totals]) if monthly_totals else 0

        attendance_stats = AttendanceRecord.objects.filter(employee=employee).aggregate(
            total=Count('id'),
            absent=Count('id', filter=Q(status='absent'))
        )
        total_attendance_days = attendance_stats['total'] or 0
        absent_days_count = attendance_stats['absent'] or 0
        has_perfect_att = (total_attendance_days >= 10 and absent_days_count == 0)

        achievement_badges = [
            {
                'id': 'badge_first_day',
                'name': 'First Work Day',
                'description': 'Successfully completed your first day of work.',
                'icon': 'first_day',
                'is_unlocked': worked_days >= 1,
                'unlocked_date': all_perf_asc[0].work_day.date.isoformat() if worked_days >= 1 else None,
                'progress': 1.0 if worked_days >= 1 else 0.0,
            },
            {
                'id': 'badge_photos_100',
                'name': '100 Photos in a Day',
                'description': 'Took 100 or more photos in a single shift.',
                'icon': 'photos_100',
                'is_unlocked': max_photos_single_day >= 100,
                'unlocked_date': next(
                    (p.work_day.date.isoformat() for p in all_perf_asc if p.photo_count >= 100), None
                ) if max_photos_single_day >= 100 else None,
                'progress': min(1.0, float(max_photos_single_day) / 100.0),
            },
            {
                'id': 'badge_monthly_1000',
                'name': '1000 Monthly Photos',
                'description': 'Reached 1000 photos inside a single month.',
                'icon': 'monthly_1000',
                'is_unlocked': max_photos_single_month >= 1000,
                'unlocked_date': None,
                'progress': min(1.0, float(max_photos_single_month) / 1000.0),
            },
            {
                'id': 'badge_perfect_attendance',
                'name': 'Perfect Attendance',
                'description': 'Work at least 10 days with zero absences.',
                'icon': 'perfect_attendance',
                'is_unlocked': has_perfect_att,
                'unlocked_date': None,
                'progress': 1.0 if has_perfect_att else min(1.0, float(total_attendance_days) / 10.0),
            },
            {
                'id': 'badge_streak_5',
                'name': 'Attendance Streak',
                'description': 'Record attendance for 5 consecutive work days.',
                'icon': 'streak_5',
                'is_unlocked': longest_att_streak >= 5,
                'unlocked_date': None,
                'progress': min(1.0, float(longest_att_streak) / 5.0),
            },
            {
                'id': 'badge_photo_master',
                'name': 'Photo Master',
                'description': 'Take 500 photos overall during your career.',
                'icon': 'photo_master',
                'is_unlocked': total_photos >= 500,
                'unlocked_date': None,
                'progress': min(1.0, float(total_photos) / 500.0),
            },
            {
                'id': 'badge_top_performer',
                'name': 'Top Performer',
                'description': 'Exceeded the daily 50 photos goal on 5 separate days.',
                'icon': 'top_performer',
                'is_unlocked': days_exceeding_goal >= 5,
                'unlocked_date': None,
                'progress': min(1.0, float(days_exceeding_goal) / 5.0),
            }
        ]

        # 9. Personal Records
        best_day_perf = DailyEmployeePerformance.objects.filter(employee=employee).order_by('-photo_count').first()
        best_day_val = best_day_perf.photo_count if best_day_perf else 0
        best_day_date = best_day_perf.work_day.date.isoformat() if best_day_perf else None

        best_earnings_val = 0.0
        best_earnings_date = None
        for p in all_perf_asc:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            earns = float(p.photo_count * u_price)
            if earns > best_earnings_val:
                best_earnings_val = earns
                best_earnings_date = p.work_day.date.isoformat()

        best_month_rec = monthly_totals.order_by('-total_photos').first()
        best_month_val = ""
        best_month_photos = 0
        if best_month_rec:
            months_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]
            best_month_val = f"{months_names[best_month_rec['month'] - 1]} {best_month_rec['year']}"
            best_month_photos = best_month_rec['total_photos']

        near_record = None
        if today_photos < best_day_val and (best_day_val - today_photos) <= 5:
            near_record = {
                'beaten': False,
                'type': 'best_day',
                'remaining': best_day_val - today_photos,
                'message': f"Only {best_day_val - today_photos} more photos to beat your best day ({best_day_val} photos)!",
            }

        personal_records = {
            'best_day': {'value': float(best_day_val), 'date': best_day_date, 'label': 'Photos'},
            'highest_photos': {'value': float(best_day_val), 'date': best_day_date, 'label': 'Photos'},
            'highest_daily_earnings': {'value': best_earnings_val, 'date': best_earnings_date, 'label': 'DA'},
            'longest_attendance_streak': {'value': float(longest_att_streak), 'date': None, 'label': 'Days'},
            'longest_goal_streak': {'value': float(longest_goal_streak), 'date': None, 'label': 'Days'},
            'best_month': {'value_string': best_month_val, 'value': float(best_month_photos), 'label': 'Photos'},
            'near_record': near_record,
        }

        # 10. Smart Insights
        smart_insights = []
        yesterday = today - timedelta(days=1)
        yesterday_perf = DailyEmployeePerformance.objects.filter(
            employee=employee, work_day__date=yesterday
        ).first()
        if yesterday_perf:
            diff = today_photos - yesterday_perf.photo_count
            if diff > 0:
                smart_insights.append(f"You improved by {diff} photos compared to yesterday!")
            elif diff < 0:
                smart_insights.append(f"You are {abs(diff)} photos away from matching yesterday's performance.")

        start_of_week = today - timedelta(days=today.weekday())
        start_of_last_week = start_of_week - timedelta(days=7)
        end_of_last_week = start_of_week - timedelta(days=1)

        this_week_earnings = 0.0
        this_week_perfs = DailyEmployeePerformance.objects.filter(
            employee=employee, work_day__date__gte=start_of_week, work_day__date__lte=today
        )
        for p in this_week_perfs:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            this_week_earnings += float(p.photo_count * u_price)

        last_week_earnings = 0.0
        last_week_perfs = DailyEmployeePerformance.objects.filter(
            employee=employee, work_day__date__gte=start_of_last_week, work_day__date__lte=end_of_last_week
        )
        for p in last_week_perfs:
            u_price = p.work_day.photographer_unit_price if role == 'photographer' else p.work_day.clown_unit_price
            last_week_earnings += float(p.photo_count * u_price)

        if last_week_earnings > 0:
            increase = ((this_week_earnings - last_week_earnings) / last_week_earnings) * 100.0
            if increase > 0:
                smart_insights.append(f"You earned {increase:.1f}% more than last week.")

        if total_attendance_days > 0:
            att_rate = float(total_attendance_days - absent_days_count) / total_attendance_days * 100.0
            if att_rate >= 90.0:
                smart_insights.append("Your attendance is excellent! Keep up the good work.")

        if today_photos < goal:
            rem = goal - today_photos
            if rem <= 10:
                smart_insights.append(f"You're only {rem} photos away from today's goal!")
        else:
            smart_insights.append("Goal achieved today! Spectacular!")

        if not smart_insights:
            smart_insights.append("Start adding photos to see daily insights and track your growth.")
            smart_insights.append("Check in daily to build up your attendance streak and earn badges!")

        # 11. Notification Preview (Latest 5)
        notifications = Notification.objects.filter(user=employee.user).order_by('-timestamp')[:5]
        notification_preview = []
        for n in notifications:
            notification_preview.append({
                'id': str(n.id),
                'title': n.title,
                'description': n.description,
                'timestamp': n.timestamp.isoformat(),
                'is_read': n.is_read,
                'icon': n.icon or 'bell',
            })

        greeting = f"Welcome back, {employee.first_name}!"

        return {
            'greeting': greeting,
            'employee_name': f"{employee.first_name} {employee.last_name}",
            'role': role.title(),
            'current_date': today.isoformat(),
            'today_location': today_location,
            'attendance': attendance_data,
            'performance': performance_data,
            'team': team_data,
            'financial_summary': financial_summary,
            'today_progress': today_progress,
            'motivation_message': motivation_payload,
            'goals_challenges': goals_challenges,
            'achievement_badges': achievement_badges,
            'personal_records': personal_records,
            'smart_insights': smart_insights,
            'recent_notifications': notification_preview,
        }

    @staticmethod
    def get_seller_dashboard_data(employee):
        from apps.daily_sessions.models import SellerDailyOperation
        today = date.today()

        ops = list(
            SellerDailyOperation.objects.filter(seller=employee)
            .select_related('work_day', 'work_day__location')
            .order_by('work_day__date')
        )

        today_op = SellerDailyOperation.objects.filter(
            seller=employee, work_day__date=today
        ).select_related('work_day', 'work_day__location').first()
        today_earnings = float(today_op.amount) if today_op else None

        today_location = None
        if today_op and today_op.work_day:
            today_location = {
                'id': str(today_op.work_day.location.id),
                'name': today_op.work_day.location.name,
                'icon': today_op.work_day.location.icon,
                'color_hex': today_op.work_day.location.color_hex,
            }

        start_of_month = today.replace(day=1)
        monthly_earnings = float(SellerDailyOperation.objects.filter(
            seller=employee,
            work_day__date__gte=start_of_month,
            work_day__date__lte=today
        ).aggregate(total=Sum('amount'))['total'] or 0.0)

        lifetime_earnings = float(SellerDailyOperation.objects.filter(
            seller=employee
        ).aggregate(total=Sum('amount'))['total'] or 0.0)

        current_streak = 0
        longest_streak = 0
        temp_streak = 0
        prev_date = None
        for op in ops:
            d = op.work_day.date
            if prev_date is None:
                temp_streak = 1
            else:
                if (d - prev_date).days == 1:
                    temp_streak += 1
                elif (d - prev_date).days > 1:
                    temp_streak = 1
            prev_date = d
            longest_streak = max(longest_streak, temp_streak)

        if prev_date and (today - prev_date).days <= 1:
            current_streak = temp_streak
        else:
            current_streak = 0

        highest_day_val = float(SellerDailyOperation.objects.filter(
            seller=employee
        ).aggregate(max_val=Max('amount'))['max_val'] or 0.0)

        total_working_days = len(ops)

        history_list = []
        for op in reversed(ops[-10:]):
            history_list.append({
                'id': str(op.id),
                'date': op.work_day.date.isoformat(),
                'amount': float(op.amount),
                'notes': op.notes or ''
            })

        achievements = [
            {
                'id': 'first_sale',
                'name': 'First Sale',
                'description': 'Successfully completed your first sale operation.',
                'icon': '💰',
                'is_unlocked': lifetime_earnings > 0,
                'progress': 1.0 if lifetime_earnings > 0 else 0.0
            },
            {
                'id': 'streak_7',
                'name': '7 Day Streak',
                'description': 'Record earnings for 7 consecutive days.',
                'icon': '🏆',
                'is_unlocked': longest_streak >= 7,
                'progress': min(1.0, float(longest_streak) / 7.0)
            },
            {
                'id': 'earned_100k',
                'name': 'Earned 100K',
                'description': 'Reach 100,000 DA in lifetime earnings.',
                'icon': '💎',
                'is_unlocked': lifetime_earnings >= 100000,
                'progress': min(1.0, lifetime_earnings / 100000.0)
            },
            {
                'id': 'earned_500k',
                'name': 'Earned 500K',
                'description': 'Reach 500,000 DA in lifetime earnings.',
                'icon': '👑',
                'is_unlocked': lifetime_earnings >= 500000,
                'progress': min(1.0, lifetime_earnings / 500000.0)
            },
            {
                'id': 'working_30_days',
                'name': '30 Working Days',
                'description': 'Complete 30 working days as a seller.',
                'icon': '🔥',
                'is_unlocked': total_working_days >= 30,
                'progress': min(1.0, float(total_working_days) / 30.0)
            }
        ]

        hall_of_closers = {
            'highest_day': highest_day_val,
            'longest_streak': longest_streak,
            'total_working_days': total_working_days,
            'lifetime_earnings': lifetime_earnings,
            'favorite_quote': 'Consistency beats motivation.'
        }

        if today_earnings is None:
            motivational_message = "No operations today yet."
        elif today_earnings < 4000:
            motivational_message = "Every great closer started with zero sales."
        elif today_earnings < 6000:
            motivational_message = "Nice work. Keep pushing."
        elif today_earnings < 8000:
            motivational_message = "You're printing money today."
        else:
            motivational_message = "Leave some commissions for tomorrow 😂"

        notifications = Notification.objects.filter(user=employee.user).order_by('-timestamp')[:5]
        notification_preview = []
        for n in notifications:
            notification_preview.append({
                'id': str(n.id),
                'title': n.title,
                'description': n.description,
                'timestamp': n.timestamp.isoformat(),
                'is_read': n.is_read,
                'icon': n.icon or 'bell',
            })

        return {
            'greeting': f"Welcome back, {employee.first_name}!",
            'employee_name': f"{employee.first_name} {employee.last_name}",
            'role': 'seller',
            'current_date': today.isoformat(),
            'today_location': today_location,
            'today_earnings': today_earnings,
            'monthly_earnings': monthly_earnings,
            'lifetime_earnings': lifetime_earnings,
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'history': history_list,
            'achievements': achievements,
            'hall_of_closers': hall_of_closers,
            'motivational_message': motivational_message,
            'recent_notifications': notification_preview,
        }
