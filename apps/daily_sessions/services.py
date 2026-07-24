from decimal import Decimal
from django.utils import timezone
from .models import WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog
from apps.employees.models import Employee
from apps.attendance.models import AttendanceRecord


class DailyOperationsService:

    @staticmethod
    def calculate_employee_earnings(performance: DailyEmployeePerformance) -> Decimal:
        if performance.employee.role == 'photographer':
            unit_price = performance.work_day.photographer_unit_price
        elif performance.employee.role == 'clown':
            unit_price = performance.work_day.clown_unit_price
        else:
            unit_price = Decimal('0.00')
        return Decimal(performance.photo_count) * unit_price

    @staticmethod
    def log_action(work_day, action, user, details=None):
        DailyOperationLog.objects.create(
            work_day=work_day,
            action=action,
            user=user,
            details=details or {}
        )

    @staticmethod
    def generate_teams(work_day: WorkDay, user):
        """
        Auto-generate teams for a work day based on attendance.
        Only photographers/clowns who are present and NOT already assigned
        to this work day are paired.
        """
        attendances = AttendanceRecord.objects.filter(
            date=work_day.date, status='present'
        )
        present_employees = [a.employee for a in attendances]

        assigned_photographers = set(
            DailyTeam.objects.filter(work_day=work_day)
            .values_list('photographer_id', flat=True)
        )
        assigned_clowns = set(
            DailyTeam.objects.filter(work_day=work_day)
            .values_list('clown_id', flat=True)
        )

        photographers = [
            e for e in present_employees
            if e.role == 'photographer' and e.id not in assigned_photographers
        ]
        clowns = [
            e for e in present_employees
            if e.role == 'clown' and e.id not in assigned_clowns
        ]

        teams_created = 0
        for i in range(min(len(photographers), len(clowns))):
            team, created = DailyTeam.objects.get_or_create(
                work_day=work_day,
                photographer=photographers[i],
                clown=clowns[i],
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
                    }
                )
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=clowns[i],
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                    }
                )

        DailyOperationsService.log_action(
            work_day=work_day,
            action=f"Generated Teams for {work_day.location.name}",
            user=user,
            details={"teams_created": teams_created, "location": work_day.location.name}
        )
        return teams_created

    @staticmethod
    def copy_yesterday_teams(work_day: WorkDay, user):
        """
        Copy teams from the previous WorkDay at the SAME location.
        """
        previous_day = WorkDay.objects.filter(
            location=work_day.location,
            date__lt=work_day.date,
        ).order_by('-date').first()
        if not previous_day:
            return 0

        assigned_photographers = set(
            DailyTeam.objects.filter(work_day=work_day)
            .values_list('photographer_id', flat=True)
        )
        assigned_clowns = set(
            DailyTeam.objects.filter(work_day=work_day)
            .values_list('clown_id', flat=True)
        )

        teams_created = 0
        for old_team in previous_day.teams.all():
            if old_team.photographer_id in assigned_photographers:
                continue
            if old_team.clown_id in assigned_clowns:
                continue

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
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                    }
                )
                DailyEmployeePerformance.objects.get_or_create(
                    work_day=work_day,
                    employee=old_team.clown,
                    defaults={
                        'team': team,
                        'photo_count': 0,
                        'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                    }
                )

        DailyOperationsService.log_action(
            work_day=work_day,
            action=f"Copied Yesterday's Teams for {work_day.location.name}",
            user=user,
            details={
                "teams_copied": teams_created,
                "from_date": str(previous_day.date),
                "location": work_day.location.name,
            }
        )
        return teams_created

    @staticmethod
    def quick_entry_update_team(team: DailyTeam, new_photo_count: int, user):
        team.team_photo_count = new_photo_count
        team.save(update_fields=['team_photo_count', 'updated_at'])

        for perf in team.performances.all():
            if perf.adjustment_type == DailyEmployeePerformance.AdjustmentType.AUTOMATIC:
                perf.photo_count = new_photo_count
                perf.save(update_fields=['photo_count', 'updated_at'])

        DailyOperationsService.log_action(
            work_day=team.work_day,
            action="Quick Entry Update",
            user=user,
            details={
                "team_id": str(team.id),
                "new_photo_count": new_photo_count,
                "location": team.work_day.location.name,
            }
        )

    @staticmethod
    def generate_daily_summary(work_day: WorkDay) -> dict:
        teams = work_day.teams.all()
        seller_ops = work_day.seller_operations.all()
        performances = work_day.performances.all()

        total_photos = sum(t.team_photo_count for t in teams)

        photographer_earnings = Decimal('0.00')
        clown_earnings = Decimal('0.00')
        for perf in performances:
            earnings = DailyOperationsService.calculate_employee_earnings(perf)
            if perf.employee.role == 'photographer':
                photographer_earnings += earnings
            elif perf.employee.role == 'clown':
                clown_earnings += earnings

        seller_earnings = sum(op.amount for op in seller_ops)

        return {
            "location": work_day.location.name,
            "location_id": str(work_day.location.id),
            "location_icon": work_day.location.icon,
            "color_hex": work_day.location.color_hex,
            "date": str(work_day.date),
            "status": work_day.status,
            "photographer_unit_price": float(work_day.photographer_unit_price),
            "clown_unit_price": float(work_day.clown_unit_price),
            "teams_count": teams.count(),
            "sellers_count": seller_ops.count(),
            "total_photos": total_photos,
            "photographer_earnings": float(photographer_earnings),
            "clown_earnings": float(clown_earnings),
            "seller_earnings": float(seller_earnings),
        }

    @staticmethod
    def recalculate_work_day(work_day: WorkDay, user):
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
