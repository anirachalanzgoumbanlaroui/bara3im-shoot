from decimal import Decimal
from django.utils import timezone
from .models import WorkDay, DailyLocation, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation
from apps.employees.models import Employee
from apps.attendance.models import AttendanceRecord

class DailyOperationsService:
    @staticmethod
    def calculate_employee_earnings(performance: DailyEmployeePerformance) -> Decimal:
        """
        Dynamically calculate earnings based on the unit price for the employee's role.
        """
        if performance.employee.role == 'photographer':
            unit_price = performance.work_day.photographer_unit_price
        elif performance.employee.role == 'clown':
            unit_price = performance.work_day.clown_unit_price
        else:
            unit_price = Decimal('0.00')
            
        return Decimal(performance.photo_count) * unit_price

    @staticmethod
    def log_action(work_day, action, user, details=None):
        """
        Log an audit action.
        """
        DailyOperationLog.objects.create(
            work_day=work_day,
            action=action,
            user=user,
            details=details or {}
        )

    @staticmethod
    def generate_teams(daily_location: DailyLocation, user):
        """
        Auto-generate teams for a daily location based on today's attendance.
        Only photographer/clown who are present and NOT already assigned to any location are paired.
        """
        work_day = daily_location.work_day
        
        # Already assigned today in ANY location
        assigned_photographers = DailyTeam.objects.filter(
            daily_location__work_day=work_day
        ).values_list('photographer_id', flat=True)
        
        assigned_clowns = DailyTeam.objects.filter(
            daily_location__work_day=work_day
        ).values_list('clown_id', flat=True)
        
        attendances = AttendanceRecord.objects.filter(date=work_day.date, status='present')
        present_employees = [a.employee for a in attendances]
        
        photographers = [e for e in present_employees if e.role == 'photographer' and e.id not in assigned_photographers]
        clowns = [e for e in present_employees if e.role == 'clown' and e.id not in assigned_clowns]
        
        # Pair them up
        teams_created = 0
        for i in range(min(len(photographers), len(clowns))):
            team, created = DailyTeam.objects.get_or_create(
                daily_location=daily_location,
                photographer=photographers[i],
                clown=clowns[i]
            )
            if created:
                teams_created += 1
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=photographers[i],
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                        'daily_location': daily_location
                    }
                )
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=clowns[i],
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                        'daily_location': daily_location
                    }
                )
                
        DailyOperationsService.log_action(
            work_day=work_day,
            action=f"Generated Teams automatically for {daily_location.location.name}",
            user=user,
            details={"teams_created": teams_created, "location": daily_location.location.name}
        )
        return teams_created

    @staticmethod
    def copy_yesterday_teams(daily_location: DailyLocation, user):
        """
        Copy teams from the previous WorkDay's corresponding location.
        """
        work_day = daily_location.work_day
        previous_day = WorkDay.objects.filter(date__lt=work_day.date).order_by('-date').first()
        if not previous_day:
            return 0
            
        prev_daily_loc = DailyLocation.objects.filter(
            work_day=previous_day,
            location=daily_location.location
        ).first()
        if not prev_daily_loc:
            return 0
            
        # Filter out already assigned today in ANY location
        assigned_photographers = DailyTeam.objects.filter(
            daily_location__work_day=work_day
        ).values_list('photographer_id', flat=True)
        
        assigned_clowns = DailyTeam.objects.filter(
            daily_location__work_day=work_day
        ).values_list('clown_id', flat=True)
            
        teams_created = 0
        for old_team in prev_daily_loc.teams.all():
            if old_team.photographer.id in assigned_photographers or old_team.clown.id in assigned_clowns:
                continue
                
            team, created = DailyTeam.objects.get_or_create(
                daily_location=daily_location,
                photographer=old_team.photographer,
                clown=old_team.clown,
                defaults={'team_name': old_team.team_name}
            )
            if created:
                teams_created += 1
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=old_team.photographer,
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                        'daily_location': daily_location
                    }
                )
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=old_team.clown,
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                        'daily_location': daily_location
                    }
                )
                
        DailyOperationsService.log_action(
            work_day=work_day,
            action=f"Copied Yesterday's Teams for {daily_location.location.name}",
            user=user,
            details={"teams_copied": teams_created, "from_date": str(previous_day.date), "location": daily_location.location.name}
        )
        return teams_created

    @staticmethod
    def quick_entry_update_team(team: DailyTeam, new_photo_count: int, user):
        """
        Update a team's photo count and cascade to its members.
        """
        team.team_photo_count = new_photo_count
        team.save(update_fields=['team_photo_count', 'updated_at'])
        
        # Update members if they don't have a manual adjustment
        for perf in team.performances.all():
            if perf.adjustment_type == DailyEmployeePerformance.AdjustmentType.AUTOMATIC:
                perf.photo_count = new_photo_count
                perf.save(update_fields=['photo_count', 'updated_at'])
                
        DailyOperationsService.log_action(
            work_day=team.daily_location.work_day,
            action="Quick Entry Update",
            user=user,
            details={"team_id": str(team.id), "new_photo_count": new_photo_count, "location": team.daily_location.location.name}
        )

    @staticmethod
    def generate_daily_summary(work_day: WorkDay) -> dict:
        """
        Generate summary dynamically across all locations for a workday.
        """
        location_summaries = []
        
        overall_teams = 0
        overall_sellers = 0
        overall_photos = 0
        overall_photographer_earnings = Decimal('0.00')
        overall_clown_earnings = Decimal('0.00')
        overall_seller_earnings = Decimal('0.00')
        
        for dl in work_day.daily_locations.all():
            teams = dl.teams.all()
            sellers_ops = dl.seller_operations.all()
            performances = dl.performances.all()
            
            loc_photos = sum(t.team_photo_count for t in teams)
            loc_photographer_earnings = Decimal('0.00')
            loc_clown_earnings = Decimal('0.00')
            
            for perf in performances:
                earnings = DailyOperationsService.calculate_employee_earnings(perf)
                if perf.employee.role == 'photographer':
                    loc_photographer_earnings += earnings
                elif perf.employee.role == 'clown':
                    loc_clown_earnings += earnings
                    
            loc_seller_earnings = sum(op.amount for op in sellers_ops)
            
            location_summaries.append({
                "location_id": str(dl.location.id),
                "location_name": dl.location.name,
                "location_icon": dl.location.icon,
                "color_hex": dl.location.color_hex,
                "teams_count": teams.count(),
                "sellers_count": sellers_ops.count(),
                "total_photos": loc_photos,
                "photographer_earnings": float(loc_photographer_earnings),
                "clown_earnings": float(loc_clown_earnings),
                "seller_earnings": float(loc_seller_earnings),
            })
            
            overall_teams += teams.count()
            overall_sellers += sellers_ops.count()
            overall_photos += loc_photos
            overall_photographer_earnings += loc_photographer_earnings
            overall_clown_earnings += loc_clown_earnings
            overall_seller_earnings += loc_seller_earnings
            
        return {
            "date": str(work_day.date),
            "photographer_unit_price": float(work_day.photographer_unit_price),
            "clown_unit_price": float(work_day.clown_unit_price),
            "locations": location_summaries,
            "totals": {
                "teams": overall_teams,
                "sellers": overall_sellers,
                "total_photos": overall_photos,
                "photographer_earnings": float(overall_photographer_earnings),
                "clown_earnings": float(overall_clown_earnings),
                "seller_earnings": float(overall_seller_earnings),
            }
        }

    @staticmethod
    def recalculate_work_day(work_day: WorkDay, user):
        """
        Recalculates all derived values after a unit price change or other modifications.
        It enforces synchronization of team photos to members that are set to AUTOMATIC.
        """
        for dl in work_day.daily_locations.all():
            for team in dl.teams.all():
                for perf in team.performances.all():
                    if perf.adjustment_type == DailyEmployeePerformance.AdjustmentType.AUTOMATIC:
                        perf.photo_count = team.team_photo_count
                        perf.save(update_fields=['photo_count', 'updated_at'])
                     
        DailyOperationsService.log_action(
            work_day=work_day,
            action="Work Day Recalculated",
            user=user,
            details={"reason": "Manual trigger or unit price change"}
        )
