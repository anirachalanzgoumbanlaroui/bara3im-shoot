"""
Employee Excel Exporters (Individual Employee Workbook & All Employees Workbook).
Generates detailed operational data into formatted multi-sheet Excel files.
"""

from decimal import Decimal
from datetime import date
from django.db.models import Sum, Count, Max, Min, Q
from apps.employees.models import Employee, Bonus, Deduction, Advance
from apps.daily_sessions.models import WorkDay, DailyTeam, DailyEmployeePerformance, SellerDailyOperation, Location
from apps.attendance.models import AttendanceRecord, AttendanceRule
from common.exports.excel.base_exporter import BaseExcelExporter
from common.exports.excel.utils import generate_export_filename


class EmployeeExporter(BaseExcelExporter):
    """
    Generates a multi-sheet Excel workbook for an individual employee containing EVERYTHING relevant to that employee.
    Exports ALL historical worked days in the database without arbitrary limits.
    """

    def __init__(self, employee: Employee):
        filename = generate_export_filename("Bara3im_Shoot_Employee", f"{employee.first_name}_{employee.last_name}")
        super().__init__(filename=filename, theme="gold")
        self.employee = employee

    def build_workbook(self):
        emp = self.employee

        # Query all relevant data models for this employee
        perfs_qs = DailyEmployeePerformance.objects.filter(
            employee=emp,
            work_day__status__in=['draft', 'in_progress', 'completed', 'locked']
        ).select_related('work_day', 'work_day__location', 'team', 'team__photographer', 'team__clown').order_by('work_day__date')

        seller_ops_qs = SellerDailyOperation.objects.filter(
            seller=emp,
            work_day__status__in=['draft', 'in_progress', 'completed', 'locked']
        ).select_related('work_day', 'work_day__location').order_by('work_day__date')

        attendance_qs = AttendanceRecord.objects.filter(employee=emp).select_related('recorded_by').order_by('date')
        bonuses_qs = Bonus.objects.filter(employee=emp).order_by('date')
        deductions_qs = Deduction.objects.filter(employee=emp).order_by('date')
        advances_qs = Advance.objects.filter(employee=emp).order_by('date')

        # Gather worked days
        worked_days_set = set()
        for p in perfs_qs:
            worked_days_set.add(p.work_day)
        for s in seller_ops_qs:
            worked_days_set.add(s.work_day)

        sorted_workdays = sorted(list(worked_days_set), key=lambda x: x.date)
        total_worked_days = len(sorted_workdays)

        # Photo & Seller Earnings calculations
        total_pictures = 0
        ardis_pictures = 0
        sabllet_pictures = 0
        ardis_days = 0
        sabllet_days = 0
        photo_gross_earnings = Decimal('0.00')

        daily_perf_rows = []
        best_day_date = None
        best_day_pics = 0

        for perf in perfs_qs:
            wd = perf.work_day
            loc_name = wd.location.name if wd.location else 'Unknown'
            pics = perf.photo_count
            total_pictures += pics

            if 'ardis' in loc_name.lower():
                ardis_pictures += pics
                ardis_days += 1
            else:
                sabllet_pictures += pics
                sabllet_days += 1

            u_price = wd.calculate_employee_unit_price(emp.role, pics)
            gross = Decimal(str(pics)) * Decimal(str(u_price))
            photo_gross_earnings += gross

            if pics > best_day_pics:
                best_day_pics = pics
                best_day_date = wd.date

            partner_name = "N/A"
            if perf.team:
                if perf.team.photographer_id == emp.id and perf.team.clown:
                    partner_name = f"{perf.team.clown.first_name} {perf.team.clown.last_name}"
                elif perf.team.clown_id == emp.id and perf.team.photographer:
                    partner_name = f"{perf.team.photographer.first_name} {perf.team.photographer.last_name}"

            daily_perf_rows.append({
                'date': wd.date,
                'location': loc_name,
                'role': emp.role.capitalize(),
                'photographer': f"{perf.team.photographer.first_name} {perf.team.photographer.last_name}" if perf.team and perf.team.photographer else "N/A",
                'clown': f"{perf.team.clown.first_name} {perf.team.clown.last_name}" if perf.team and perf.team.clown else "N/A",
                'team': perf.team.team_name or partner_name if perf.team else "N/A",
                'pictures': pics,
                'unit_price': u_price,
                'gross_amount': gross,
                'bonus': Decimal('0.00'),
                'deduction': Decimal('0.00'),
                'advance': Decimal('0.00'),
                'net_amount': gross,
            })

        seller_gross_earnings = Decimal('0.00')
        for op in seller_ops_qs:
            amt = Decimal(str(op.amount))
            seller_gross_earnings += amt
            loc_name = op.work_day.location.name if op.work_day.location else 'Unknown'
            if 'ardis' in loc_name.lower():
                ardis_days += 1
            else:
                sabllet_days += 1

            daily_perf_rows.append({
                'date': op.work_day.date,
                'location': loc_name,
                'role': 'Seller',
                'photographer': 'N/A',
                'clown': 'N/A',
                'team': 'N/A',
                'pictures': 0,
                'unit_price': Decimal('0.00'),
                'gross_amount': amt,
                'bonus': Decimal('0.00'),
                'deduction': Decimal('0.00'),
                'advance': Decimal('0.00'),
                'net_amount': amt,
            })

        # Sort combined daily history rows by date
        daily_perf_rows.sort(key=lambda x: x['date'])

        # Totals
        total_earnings = photo_gross_earnings + seller_gross_earnings
        total_bonuses = bonuses_qs.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
        total_deductions = deductions_qs.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
        total_advances = advances_qs.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')

        # Attendance late deductions
        rule = AttendanceRule.get_active_rule()
        late_ded_rate = Decimal(str(rule.late_deduction_amount)) if rule else Decimal('0.00')
        late_records_cnt = attendance_qs.filter(status='late').count()
        attendance_deductions = Decimal(str(late_records_cnt)) * late_ded_rate

        current_balance = total_earnings + total_bonuses - total_deductions - total_advances - attendance_deductions
        avg_pictures_day = round(total_pictures / max(1, total_worked_days), 1)
        avg_earnings_day = round(float(total_earnings) / max(1, total_worked_days), 2)

        # ── Sheet 1 — Employee Summary ────────────────────────────────────────
        ws_sum = self.create_sheet("Employee Summary")
        r = self.add_header_block(
            ws_sum,
            f"Employee Summary — {emp.first_name} {emp.last_name}",
            f"Employee Code: {emp.employee_code} | Role: {emp.role.capitalize()} | Status: {emp.status.capitalize()}"
        )

        sum_cols = [
            {'key': 'metric', 'label': 'Metric / Attribute', 'align': 'left', 'format': 'text'},
            {'key': 'val', 'label': 'Value', 'align': 'right', 'format': 'text'},
        ]
        sum_data = [
            {'metric': 'Employee Name', 'val': f"{emp.first_name} {emp.last_name}"},
            {'metric': 'Employee ID / Code', 'val': emp.employee_code or str(emp.id)[:8]},
            {'metric': 'Role', 'val': emp.role.capitalize()},
            {'metric': 'Phone Number', 'val': emp.phone_number or 'N/A'},
            {'metric': 'Status', 'val': emp.status.capitalize()},
            {'metric': 'Hiring Date', 'val': str(emp.hiring_date)},
            {'metric': 'Total Worked Days', 'val': str(total_worked_days)},
            {'metric': 'Total Pictures Count', 'val': f"{total_pictures:,}"},
            {'metric': 'Total Gross Earnings', 'val': f"{total_earnings:,.2f} DA"},
            {'metric': 'Total Bonuses', 'val': f"{total_bonuses:,.2f} DA"},
            {'metric': 'Total Deductions', 'val': f"{total_deductions:,.2f} DA"},
            {'metric': 'Total Advances', 'val': f"{total_advances:,.2f} DA"},
            {'metric': 'Attendance Late Deductions', 'val': f"{attendance_deductions:,.2f} DA"},
            {'metric': 'Current Net Balance', 'val': f"{current_balance:,.2f} DA"},
            {'metric': 'Average Pictures / Day', 'val': f"{avg_pictures_day}"},
            {'metric': 'Average Earnings / Day', 'val': f"{avg_earnings_day:,.2f} DA"},
            {'metric': 'Best Day Date', 'val': str(best_day_date) if best_day_date else 'N/A'},
            {'metric': 'Best Day Picture Count', 'val': f"{best_day_pics}"},
            {'metric': 'ARDIS Pictures', 'val': f"{ardis_pictures:,}"},
            {'metric': 'SABLLET Pictures', 'val': f"{sabllet_pictures:,}"},
        ]
        self.write_table(ws_sum, r, sum_cols, sum_data, theme="gold")

        # ── Sheet 2 — Daily History ───────────────────────────────────────────
        ws_daily = self.create_sheet("Daily History")
        r = self.add_header_block(ws_daily, "Daily History", f"Complete historical worked days ({len(daily_perf_rows)} days)")
        daily_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'photographer', 'label': 'Photographer', 'align': 'left', 'format': 'text'},
            {'key': 'clown', 'label': 'Clown', 'align': 'left', 'format': 'text'},
            {'key': 'team', 'label': 'Team', 'align': 'left', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'gross_amount', 'label': 'Gross Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'bonus', 'label': 'Bonus', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'deduction', 'label': 'Deduction', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'advance', 'label': 'Advance', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'net_amount', 'label': 'Net Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        self.write_table(ws_daily, r, daily_cols, daily_perf_rows, theme="gold", include_totals=True, total_label_col='location')

        # ── Sheet 3 — Attendance ──────────────────────────────────────────────
        ws_att = self.create_sheet("Attendance")
        r = self.add_header_block(ws_att, "Attendance Records", f"Historical check-ins for {emp.first_name}")
        att_rows = []
        for att in attendance_qs:
            att_rows.append({
                'date': att.date,
                'location': 'Recorded',
                'check_in_time': att.check_in_time.strftime('%H:%M:%S') if att.check_in_time else 'N/A',
                'status': att.status,
                'late': 'Yes' if att.status == 'late' else 'No',
                'late_duration': att.minutes_late,
                'deduction': late_ded_rate if att.status == 'late' else Decimal('0.00'),
                'notes': att.notes or '',
            })
        att_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'check_in_time', 'label': 'Check-In Time', 'align': 'center', 'format': 'time'},
            {'key': 'status', 'label': 'Status', 'align': 'center', 'format': 'status'},
            {'key': 'late', 'label': 'Late?', 'align': 'center', 'format': 'text'},
            {'key': 'late_duration', 'label': 'Minutes Late', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'deduction', 'label': 'Late Deduction', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'notes', 'label': 'Notes', 'align': 'left', 'format': 'text'},
        ]
        self.write_table(ws_att, r, att_cols, att_rows, theme="gold", include_totals=True, total_label_col='status')

        # ── Sheet 4 — Earnings ────────────────────────────────────────────────
        ws_earn = self.create_sheet("Earnings")
        r = self.add_header_block(ws_earn, "Earnings & Financial Transactions", f"Earnings log for {emp.first_name}")
        earn_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'base_amount', 'label': 'Base Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'bonus', 'label': 'Bonus', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'deduction', 'label': 'Deduction', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'advance', 'label': 'Advance', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'net_amount', 'label': 'Net Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        earn_rows = []
        for row in daily_perf_rows:
            earn_rows.append({
                'date': row['date'],
                'location': row['location'],
                'pictures': row['pictures'],
                'unit_price': row['unit_price'],
                'base_amount': row['gross_amount'],
                'bonus': row['bonus'],
                'deduction': row['deduction'],
                'advance': row['advance'],
                'net_amount': row['net_amount'],
            })
        self.write_table(ws_earn, r, earn_cols, earn_rows, theme="gold", include_totals=True, total_label_col='location')

        # ── Sheet 5 — Teams ───────────────────────────────────────────────────
        ws_teams = self.create_sheet("Teams")
        r = self.add_header_block(ws_teams, "Team Partner History", f"Teams worked with by {emp.first_name}")
        team_rows = []
        for perf in perfs_qs:
            if perf.team:
                t = perf.team
                loc_name = perf.work_day.location.name if perf.work_day.location else 'Unknown'
                u_price = perf.work_day.calculate_employee_unit_price(emp.role, perf.photo_count)
                team_rows.append({
                    'date': perf.work_day.date,
                    'location': loc_name,
                    'photographer': f"{t.photographer.first_name} {t.photographer.last_name}" if t.photographer else "N/A",
                    'clown': f"{t.clown.first_name} {t.clown.last_name}" if t.clown else "N/A",
                    'employee_role': emp.role.capitalize(),
                    'team_pictures': perf.photo_count,
                    'unit_price': u_price,
                    'employee_amount': Decimal(str(perf.photo_count)) * Decimal(str(u_price)),
                })
        team_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'photographer', 'label': 'Photographer', 'align': 'left', 'format': 'text'},
            {'key': 'clown', 'label': 'Clown', 'align': 'left', 'format': 'text'},
            {'key': 'employee_role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'team_pictures', 'label': 'Team Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'employee_amount', 'label': 'Employee Earnings', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        self.write_table(ws_teams, r, team_cols, team_rows, theme="gold", include_totals=True, total_label_col='location')

        # ── Sheet 6 — Locations ───────────────────────────────────────────────
        ws_loc = self.create_sheet("Locations")
        r = self.add_header_block(ws_loc, "Location Breakdown", f"Performance across ARDIS & SABLLET")
        loc_rows = [
            {'location': 'ARDIS', 'days': ardis_days, 'pictures': ardis_pictures, 'avg_pics': round(ardis_pictures / max(1, ardis_days), 1)},
            {'location': 'SABLLET', 'days': sabllet_days, 'pictures': sabllet_pictures, 'avg_pics': round(sabllet_pictures / max(1, sabllet_days), 1)},
        ]
        loc_cols = [
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'days', 'label': 'Worked Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'pictures', 'label': 'Total Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'avg_pics', 'label': 'Avg Pictures / Day', 'align': 'right', 'format': 'decimal'},
        ]
        self.write_table(ws_loc, r, loc_cols, loc_rows, theme="gold", include_totals=True, total_label_col='location')

        # ── Sheet 7 — Statistics ──────────────────────────────────────────────
        ws_stat = self.create_sheet("Statistics")
        r = self.add_header_block(ws_stat, "Aggregated Statistics", f"Executive metrics for {emp.first_name}")
        max_pics = max([p.photo_count for p in perfs_qs], default=0)
        min_pics = min([p.photo_count for p in perfs_qs], default=0) if perfs_qs else 0
        partners_set = set()
        for p in perfs_qs:
            if p.team:
                if p.team.photographer_id == emp.id and p.team.clown:
                    partners_set.add(p.team.clown.first_name)
                elif p.team.clown_id == emp.id and p.team.photographer:
                    partners_set.add(p.team.photographer.first_name)

        stat_cols = [
            {'key': 'metric', 'label': 'Statistic Name', 'align': 'left', 'format': 'text'},
            {'key': 'value', 'label': 'Metric Value', 'align': 'right', 'format': 'text'},
        ]
        stat_rows = [
            {'metric': 'Total Pictures Count', 'value': f"{total_pictures:,}"},
            {'metric': 'Average Pictures / Day', 'value': f"{avg_pictures_day}"},
            {'metric': 'Maximum Pictures Single Day', 'value': f"{max_pics}"},
            {'metric': 'Minimum Pictures Single Day', 'value': f"{min_pics}"},
            {'metric': 'Total Worked Days', 'value': f"{total_worked_days}"},
            {'metric': 'Average Earnings / Day', 'value': f"{avg_earnings_day:,.2f} DA"},
            {'metric': 'Best Day', 'value': f"{best_day_date} ({best_day_pics} pics)" if best_day_date else "N/A"},
            {'metric': 'Number of Different Partners', 'value': f"{len(partners_set)}"},
            {'metric': 'ARDIS Worked Days', 'value': f"{ardis_days}"},
            {'metric': 'SABLLET Worked Days', 'value': f"{sabllet_days}"},
        ]
        self.write_table(ws_stat, r, stat_cols, stat_rows, theme="gold")

        # ── Sheet 8 — Picture Performance ────────────────────────────────────
        ws_perf = self.create_sheet("Picture Performance")
        r = self.add_header_block(ws_perf, "Picture Performance Analysis", "Day-over-day photo trend analysis")
        perf_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer'},
            {'key': 'prev_pictures', 'label': 'Previous Worked Day', 'align': 'right', 'format': 'integer'},
            {'key': 'diff', 'label': 'Difference', 'align': 'right', 'format': 'integer'},
            {'key': 'pct_change', 'label': '% Change', 'align': 'right', 'format': 'percentage'},
            {'key': 'team', 'label': 'Team', 'align': 'left', 'format': 'text'},
        ]
        perf_rows = []
        prev_p = None
        for p in perfs_qs:
            curr_p = p.photo_count
            diff = curr_p - prev_p if prev_p is not None else 0
            pct = ((curr_p - prev_p) / max(1, prev_p)) * 100.0 if prev_p is not None and prev_p > 0 else 0.0
            loc_name = p.work_day.location.name if p.work_day.location else 'Unknown'

            perf_rows.append({
                'date': p.work_day.date,
                'location': loc_name,
                'pictures': curr_p,
                'prev_pictures': prev_p if prev_p is not None else 0,
                'diff': diff,
                'pct_change': pct / 100.0,
                'team': p.team.team_name if p.team else 'N/A',
            })
            prev_p = curr_p

        self.write_table(ws_perf, r, perf_cols, perf_rows, theme="gold")


class AllEmployeesExporter(BaseExcelExporter):
    """
    Generates an Excel workbook containing information for EVERY employee.
    """

    def __init__(self):
        filename = generate_export_filename("Bara3im_Shoot", "All_Employees")
        super().__init__(filename=filename, theme="gold")

    def build_workbook(self):
        employees = Employee.objects.all().order_by('role', 'first_name')

        # ── Sheet 1 — Employee Summary ────────────────────────────────────────
        ws_sum = self.create_sheet("Employee Summary")
        r = self.add_header_block(ws_sum, "All Employees Summary", f"Master summary for all {employees.count()} employees")

        sum_cols = [
            {'key': 'employee_code', 'label': 'Code', 'align': 'center', 'format': 'text'},
            {'key': 'name', 'label': 'Employee Name', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'status', 'label': 'Status', 'align': 'center', 'format': 'status'},
            {'key': 'phone', 'label': 'Phone', 'align': 'left', 'format': 'text'},
            {'key': 'hiring_date', 'label': 'Hire Date', 'align': 'center', 'format': 'date'},
            {'key': 'worked_days', 'label': 'Worked Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'avg_pictures', 'label': 'Avg Pics/Day', 'align': 'right', 'format': 'decimal'},
            {'key': 'gross_earnings', 'label': 'Gross Earnings', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'bonuses', 'label': 'Bonuses', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'deductions', 'label': 'Deductions', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'advances', 'label': 'Advances', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'net_balance', 'label': 'Net Balance', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]

        sum_rows = []
        for emp in employees:
            perfs = DailyEmployeePerformance.objects.filter(employee=emp, work_day__status__in=['draft', 'in_progress', 'completed', 'locked'])
            seller_ops = SellerDailyOperation.objects.filter(seller=emp, work_day__status__in=['draft', 'in_progress', 'completed', 'locked'])

            worked_cnt = perfs.values('work_day').distinct().count() + seller_ops.values('work_day').distinct().count()
            tot_pics = perfs.aggregate(tot=Sum('photo_count'))['tot'] or 0

            photo_earnings = Decimal('0.00')
            for p in perfs.select_related('work_day'):
                u_p = p.work_day.calculate_employee_unit_price(emp.role, p.photo_count)
                photo_earnings += Decimal(str(p.photo_count)) * Decimal(str(u_p))

            seller_earnings = Decimal(str(seller_ops.aggregate(tot=Sum('amount'))['tot'] or 0))
            tot_gross = photo_earnings + seller_earnings

            bonuses = emp.bonuses.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
            deductions = emp.deductions.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')
            advances = emp.advances.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')

            net = tot_gross + bonuses - deductions - advances

            sum_rows.append({
                'employee_code': emp.employee_code or str(emp.id)[:8],
                'name': f"{emp.first_name} {emp.last_name}",
                'role': emp.role.capitalize(),
                'status': emp.status.capitalize(),
                'phone': emp.phone_number or 'N/A',
                'hiring_date': str(emp.hiring_date),
                'worked_days': worked_cnt,
                'pictures': tot_pics,
                'avg_pictures': round(tot_pics / max(1, worked_cnt), 1),
                'gross_earnings': tot_gross,
                'bonuses': bonuses,
                'deductions': deductions,
                'advances': advances,
                'net_balance': net,
            })

        self.write_table(ws_sum, r, sum_cols, sum_rows, theme="gold", include_totals=True, total_label_col='name')

        # ── Sheet 2 — Daily Performance ───────────────────────────────────────
        ws_perf = self.create_sheet("Daily Performance")
        r = self.add_header_block(ws_perf, "All Employees Daily Performance", "Every employee/day combination in database")

        all_perfs = DailyEmployeePerformance.objects.filter(
            work_day__status__in=['draft', 'in_progress', 'completed', 'locked']
        ).select_related('employee', 'work_day', 'work_day__location', 'team', 'team__photographer', 'team__clown').order_by('-work_day__date')

        perf_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'employee', 'label': 'Employee', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'gross_amount', 'label': 'Gross Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'team', 'label': 'Team', 'align': 'left', 'format': 'text'},
        ]
        perf_rows = []
        for p in all_perfs:
            u_p = p.work_day.calculate_employee_unit_price(p.employee.role, p.photo_count)
            loc_name = p.work_day.location.name if p.work_day.location else 'Unknown'
            perf_rows.append({
                'date': p.work_day.date,
                'location': loc_name,
                'employee': f"{p.employee.first_name} {p.employee.last_name}",
                'role': p.employee.role.capitalize(),
                'pictures': p.photo_count,
                'unit_price': u_p,
                'gross_amount': Decimal(str(p.photo_count)) * Decimal(str(u_p)),
                'team': p.team.team_name if p.team else 'N/A',
            })
        self.write_table(ws_perf, r, perf_cols, perf_rows, theme="gold", include_totals=True, total_label_col='location')
