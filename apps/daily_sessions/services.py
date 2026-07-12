from decimal import Decimal
from django.utils import timezone
from .models import WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog
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
    def generate_teams(work_day: WorkDay, user):
        """
        Auto-generate teams for a workday based on today's attendance.
        """
        attendances = AttendanceRecord.objects.filter(date=work_day.date, status='present')
        present_employees = [a.employee for a in attendances]
        
        photographers = [e for e in present_employees if e.role == 'photographer']
        clowns = [e for e in present_employees if e.role == 'clown']
        
        # Pair them up
        teams_created = 0
        for i in range(min(len(photographers), len(clowns))):
            team, created = DailyTeam.objects.get_or_create(
                work_day=work_day,
                photographer=photographers[i],
                clown=clowns[i]
            )
            if created:
                teams_created += 1
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=photographers[i],
                    team=team,
                    defaults={'photo_count': 0, 'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC}
                )
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=clowns[i],
                    team=team,
                    defaults={'photo_count': 0, 'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC}
                )
                
        DailyOperationsService.log_action(
            work_day=work_day,
            action="Generated Teams Automatically",
            user=user,
            details={"teams_created": teams_created}
        )
        return teams_created

    @staticmethod
    def copy_yesterday_teams(work_day: WorkDay, user):
        """
        Copy teams from the previous WorkDay.
        """
        previous_day = WorkDay.objects.filter(date__lt=work_day.date).order_by('-date').first()
        if not previous_day:
            return 0
            
        teams_created = 0
        for old_team in previous_day.teams.all():
            team, created = DailyTeam.objects.get_or_create(
                work_day=work_day,
                photographer=old_team.photographer,
                clown=old_team.clown,
                defaults={'team_name': old_team.team_name}
            )
            if created:
                teams_created += 1
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=old_team.photographer,
                    team=team,
                    defaults={'photo_count': 0, 'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC}
                )
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=old_team.clown,
                    team=team,
                    defaults={'photo_count': 0, 'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC}
                )
                
        DailyOperationsService.log_action(
            work_day=work_day,
            action="Copied Yesterday's Teams",
            user=user,
            details={"teams_copied": teams_created, "from_date": str(previous_day.date)}
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
            work_day=team.work_day,
            action="Quick Entry Update",
            user=user,
            details={"team_id": str(team.id), "new_photo_count": new_photo_count}
        )

    @staticmethod
    def generate_daily_summary(work_day: WorkDay) -> dict:
        """
        Generate summary dynamically without saving to DB.
        """
        performances = work_day.performances.all()
        teams = work_day.teams.all()
        
        total_team_photos = sum(team.team_photo_count for team in teams)
        total_individual_photos = sum(perf.photo_count for perf in performances)
        
        total_photographer_earnings = Decimal('0.00')
        total_clown_earnings = Decimal('0.00')
        employees_working = set()
        
        for perf in performances:
            earnings = DailyOperationsService.calculate_employee_earnings(perf)
            if perf.employee.role == 'photographer':
                total_photographer_earnings += earnings
            elif perf.employee.role == 'clown':
                total_clown_earnings += earnings
            employees_working.add(perf.employee.id)
            
        return {
            "date": str(work_day.date),
            "employees_working": len(employees_working),
            "teams": teams.count(),
            "total_team_photos": total_team_photos,
            "total_individual_photos": total_individual_photos,
            "photographer_unit_price": work_day.photographer_unit_price,
            "clown_unit_price": work_day.clown_unit_price,
            "total_photographer_earnings": total_photographer_earnings,
            "total_clown_earnings": total_clown_earnings
        }

    @staticmethod
    def recalculate_work_day(work_day: WorkDay, user):
        """
        Recalculates all derived values after a unit price change or other modifications.
        It enforces synchronization of team photos to members that are set to AUTOMATIC.
        """
        for team in work_day.teams.all():
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
