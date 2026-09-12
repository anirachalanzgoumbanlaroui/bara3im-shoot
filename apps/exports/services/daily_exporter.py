"""
Daily & Date-Range Excel Exporters.
Generates single-day and multi-day operational/financial Excel workbooks with location dynamic styling.
"""

from decimal import Decimal
from datetime import date
from django.db.models import Sum, Count, Q
from apps.daily_sessions.models import WorkDay, DailyTeam, DailyEmployeePerformance, SellerDailyOperation, Location
from apps.attendance.models import AttendanceRecord, AttendanceRule
from apps.employees.models import Bonus, Deduction, Advance
from common.exports.excel.base_exporter import BaseExcelExporter
from common.exports.excel.utils import generate_export_filename


class DailyExporter(BaseExcelExporter):
    """
    Generates a single WorkDay operational Excel workbook.
    """

    def __init__(self, work_day: WorkDay):
        loc_name = work_day.location.name if work_day.location else "Location"
        theme = "ardis" if "ardis" in loc_name.lower() else "sabllet" if "sabllet" in loc_name.lower() else "default"
        filename = generate_export_filename("Bara3im_Shoot", f"{loc_name}_Daily", start_date=work_day.date)
        super().__init__(filename=filename, theme=theme)
        self.work_day = work_day

    def build_workbook(self):
        wd = self.work_day
        loc_name = wd.location.name if wd.location else "Unknown"

        teams = wd.teams.select_related('photographer', 'clown').all()
        perfs = wd.performances.select_related('employee', 'team').all()
        sellers = wd.seller_operations.select_related('seller').all()
        attendance = AttendanceRecord.objects.filter(date=wd.date).select_related('employee')

        # Totals
        total_teams = teams.count()
        total_photos = wd.total_photos
        photographers_cnt = perfs.filter(employee__role='photographer').count()
        clowns_cnt = perfs.filter(employee__role='clown').count()
        sellers_cnt = sellers.count()

        # Pricing Tier applied
        prices_info = wd.get_resolved_unit_prices(photo_count=total_photos)
        tier_applied = prices_info.get('tier', 'normal').upper()

        # ── Sheet 1 — Daily Summary ───────────────────────────────────────────
        ws_sum = self.create_sheet("Daily Summary")
        r = self.add_header_block(
            ws_sum,
            f"Daily Operations Summary — {loc_name}",
            f"Date: {wd.date} | Status: {wd.status.capitalize()} | Pricing Tier: {tier_applied}"
        )
        sum_cols = [
            {'key': 'metric', 'label': 'Metric', 'align': 'left', 'format': 'text'},
            {'key': 'value', 'label': 'Value', 'align': 'right', 'format': 'text'},
        ]
        sum_data = [
            {'metric': 'Date', 'value': str(wd.date)},
            {'metric': 'Location', 'value': loc_name},
            {'metric': 'Status', 'value': wd.status.capitalize()},
            {'metric': 'Total Teams Count', 'value': str(total_teams)},
            {'metric': 'Total Photographers Count', 'value': str(photographers_cnt)},
            {'metric': 'Total Clowns Count', 'value': str(clowns_cnt)},
            {'metric': 'Total Sellers Count', 'value': str(sellers_cnt)},
            {'metric': 'Total Photos Count', 'value': f"{total_photos:,}"},
            {'metric': 'Pricing Tier Applied', 'value': tier_applied},
            {'metric': 'Photographer Unit Price', 'value': f"{prices_info['photographer_unit_price']} DA"},
            {'metric': 'Clown Unit Price', 'value': f"{prices_info['clown_unit_price']} DA"},
        ]
        self.write_table(ws_sum, r, sum_cols, sum_data, theme=self.theme)

        # ── Sheet 2 — Teams ───────────────────────────────────────────────────
        ws_teams = self.create_sheet("Teams")
        r = self.add_header_block(ws_teams, "Daily Teams Performance", f"Teams active at {loc_name} on {wd.date}")
        team_cols = [
            {'key': 'team_name', 'label': 'Team Name', 'align': 'left', 'format': 'text'},
            {'key': 'photographer', 'label': 'Photographer', 'align': 'left', 'format': 'text'},
            {'key': 'clown', 'label': 'Clown', 'align': 'left', 'format': 'text'},
            {'key': 'photo_count', 'label': 'Team Photos', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'photo_unit', 'label': 'Photographer Unit', 'align': 'right', 'format': 'currency'},
            {'key': 'clown_unit', 'label': 'Clown Unit', 'align': 'right', 'format': 'currency'},
            {'key': 'photo_amount', 'label': 'Photographer Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'clown_amount', 'label': 'Clown Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        team_rows = []
        for t in teams:
            pics = t.team_photo_count
            p_unit = wd.calculate_employee_unit_price('photographer', pics)
            c_unit = wd.calculate_employee_unit_price('clown', pics)
            p_amt = Decimal(str(pics)) * Decimal(str(p_unit))
            c_amt = Decimal(str(pics)) * Decimal(str(c_unit))
            team_rows.append({
                'team_name': t.team_name or f"{t.photographer.first_name} & {t.clown.first_name}",
                'photographer': f"{t.photographer.first_name} {t.photographer.last_name}" if t.photographer else "N/A",
                'clown': f"{t.clown.first_name} {t.clown.last_name}" if t.clown else "N/A",
                'photo_count': pics,
                'photo_unit': p_unit,
                'clown_unit': c_unit,
                'photo_amount': p_amt,
                'clown_amount': c_amt,
            })
        self.write_table(ws_teams, r, team_cols, team_rows, theme=self.theme, include_totals=True, total_label_col='team_name')

        # ── Sheet 3 — Employees ───────────────────────────────────────────────
        ws_emp = self.create_sheet("Employees")
        r = self.add_header_block(ws_emp, "Daily Employees Performance", f"All staff working on {wd.date}")
        emp_cols = [
            {'key': 'employee', 'label': 'Employee Name', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'team', 'label': 'Team', 'align': 'left', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'gross_amount', 'label': 'Gross Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'bonus', 'label': 'Bonus', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'deduction', 'label': 'Deduction', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'advance', 'label': 'Advance', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'net_amount', 'label': 'Net Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        emp_rows = []
        for perf in perfs:
            pics = perf.photo_count
            u_p = wd.calculate_employee_unit_price(perf.employee.role, pics)
            gross = Decimal(str(pics)) * Decimal(str(u_p))
            emp_rows.append({
                'employee': f"{perf.employee.first_name} {perf.employee.last_name}",
                'role': perf.employee.role.capitalize(),
                'team': perf.team.team_name if perf.team else 'N/A',
                'pictures': pics,
                'unit_price': u_p,
                'gross_amount': gross,
                'bonus': Decimal('0.00'),
                'deduction': Decimal('0.00'),
                'advance': Decimal('0.00'),
                'net_amount': gross,
            })
        self.write_table(ws_emp, r, emp_cols, emp_rows, theme=self.theme, include_totals=True, total_label_col='employee')

        # ── Sheet 4 — Sellers ─────────────────────────────────────────────────
        ws_seller = self.create_sheet("Sellers")
        r = self.add_header_block(ws_seller, "Daily Sellers Report", f"Seller earnings & ratings for {wd.date}")
        seller_cols = [
            {'key': 'seller', 'label': 'Seller Name', 'align': 'left', 'format': 'text'},
            {'key': 'amount', 'label': 'Sales Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'rating', 'label': 'Rating', 'align': 'center', 'format': 'status'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
        ]
        seller_rows = []
        for s in sellers:
            seller_rows.append({
                'seller': f"{s.seller.first_name} {s.seller.last_name}",
                'amount': s.amount,
                'rating': s.rating or 'N/A',
                'location': loc_name,
                'date': wd.date,
            })
        self.write_table(ws_seller, r, seller_cols, seller_rows, theme=self.theme, include_totals=True, total_label_col='seller')

        # ── Sheet 5 — Attendance ──────────────────────────────────────────────
        ws_att = self.create_sheet("Attendance")
        r = self.add_header_block(ws_att, "Daily Attendance", f"Check-ins on {wd.date}")
        att_cols = [
            {'key': 'employee', 'label': 'Employee', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'status', 'label': 'Status', 'align': 'center', 'format': 'status'},
            {'key': 'check_in', 'label': 'Check-In Time', 'align': 'center', 'format': 'time'},
            {'key': 'late_minutes', 'label': 'Minutes Late', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
        ]
        att_rows = []
        for a in attendance:
            att_rows.append({
                'employee': f"{a.employee.first_name} {a.employee.last_name}",
                'role': a.employee.role.capitalize(),
                'status': a.status,
                'check_in': a.check_in_time.strftime('%H:%M:%S') if a.check_in_time else 'N/A',
                'late_minutes': a.minutes_late,
            })
        self.write_table(ws_att, r, att_cols, att_rows, theme=self.theme, include_totals=True, total_label_col='employee')

        # ── Sheet 6 — Financial Report ────────────────────────────────────────
        ws_fin = self.create_sheet("Financial")
        r = self.add_header_block(ws_fin, "Daily Financial Breakdown", f"Financial log for {loc_name} on {wd.date}")
        fin_cols = [
            {'key': 'employee', 'label': 'Employee', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'base_amount', 'label': 'Base Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'bonus', 'label': 'Bonus', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'deduction', 'label': 'Deduction', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'advance', 'label': 'Advance', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'net_amount', 'label': 'Net Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        fin_rows = []
        for emp_r in emp_rows:
            fin_rows.append({
                'employee': emp_r['employee'],
                'role': emp_r['role'],
                'pictures': emp_r['pictures'],
                'unit_price': emp_r['unit_price'],
                'base_amount': emp_r['gross_amount'],
                'bonus': emp_r['bonus'],
                'deduction': emp_r['deduction'],
                'advance': emp_r['advance'],
                'net_amount': emp_r['net_amount'],
            })
        for s_r in seller_rows:
            fin_rows.append({
                'employee': s_r['seller'],
                'role': 'Seller',
                'pictures': 0,
                'unit_price': Decimal('0.00'),
                'base_amount': s_r['amount'],
                'bonus': Decimal('0.00'),
                'deduction': Decimal('0.00'),
                'advance': Decimal('0.00'),
                'net_amount': s_r['amount'],
            })
        self.write_table(ws_fin, r, fin_cols, fin_rows, theme=self.theme, include_totals=True, total_label_col='employee')


class DateRangeExporter(BaseExcelExporter):
    """
    Generates a Date Range & Location Excel workbook.
    Supports ARDIS, SABLLET, or Both locations.
    """

    def __init__(self, start_date: date, end_date: date, location_id=None, role=None):
        loc = Location.objects.filter(id=location_id).first() if location_id else None
        loc_name = loc.name if loc else "Both_Locations"
        theme = "ardis" if loc and "ardis" in loc.name.lower() else "sabllet" if loc and "sabllet" in loc.name.lower() else "gold"
        filename = generate_export_filename("Bara3im_Shoot", loc_name, start_date=start_date, end_date=end_date)
        super().__init__(filename=filename, theme=theme)
        self.start_date = start_date
        self.end_date = end_date
        self.location = loc
        self.role = role

    def build_workbook(self):
        s_date, e_date = self.start_date, self.end_date

        workdays_qs = WorkDay.objects.filter(date__range=(s_date, e_date), status__in=['draft', 'in_progress', 'completed', 'locked']).select_related('location')
        perfs_qs = DailyEmployeePerformance.objects.filter(work_day__date__range=(s_date, e_date), work_day__status__in=['draft', 'in_progress', 'completed', 'locked']).select_related('employee', 'work_day', 'work_day__location', 'team')
        sellers_qs = SellerDailyOperation.objects.filter(work_day__date__range=(s_date, e_date), work_day__status__in=['draft', 'in_progress', 'completed', 'locked']).select_related('seller', 'work_day', 'work_day__location')
        teams_qs = DailyTeam.objects.filter(work_day__date__range=(s_date, e_date), work_day__status__in=['draft', 'in_progress', 'completed', 'locked']).select_related('photographer', 'clown', 'work_day', 'work_day__location')

        if self.location:
            workdays_qs = workdays_qs.filter(location=self.location)
            perfs_qs = perfs_qs.filter(work_day__location=self.location)
            sellers_qs = sellers_qs.filter(work_day__location=self.location)
            teams_qs = teams_qs.filter(work_day__location=self.location)

        if self.role:
            perfs_qs = perfs_qs.filter(employee__role=self.role)

        # ── Sheet 1 — Summary ─────────────────────────────────────────────────
        ws_sum = self.create_sheet("Summary")
        r = self.add_header_block(
            ws_sum,
            f"Period Operational Summary ({s_date} to {e_date})",
            f"Location Filter: {self.location.name if self.location else 'Both Locations'} | Role Filter: {self.role or 'All'}"
        )
        tot_wd = workdays_qs.count()
        tot_pics = teams_qs.aggregate(tot=Sum('team_photo_count'))['tot'] or 0
        tot_seller_amt = sellers_qs.aggregate(tot=Sum('amount'))['tot'] or Decimal('0.00')

        sum_cols = [
            {'key': 'metric', 'label': 'Period Metric', 'align': 'left', 'format': 'text'},
            {'key': 'val', 'label': 'Value', 'align': 'right', 'format': 'text'},
        ]
        sum_rows = [
            {'metric': 'Period Start Date', 'val': str(s_date)},
            {'metric': 'Period End Date', 'val': str(e_date)},
            {'metric': 'Total WorkDays Recorded', 'val': str(tot_wd)},
            {'metric': 'Total Teams Count', 'val': str(teams_qs.count())},
            {'metric': 'Total Pictures Taken', 'val': f"{tot_pics:,}"},
            {'metric': 'Average Pictures / Day', 'val': f"{round(tot_pics / max(1, tot_wd), 1)}"},
            {'metric': 'Total Seller Sales Revenue', 'val': f"{tot_seller_amt:,.2f} DA"},
        ]
        self.write_table(ws_sum, r, sum_cols, sum_rows, theme=self.theme)

        # ── Sheet 2 — Daily Performance ───────────────────────────────────────
        ws_daily = self.create_sheet("Daily Performance")
        r = self.add_header_block(ws_daily, "Daily Performance Records", f"All worked sessions in period")
        daily_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'employee', 'label': 'Employee', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'unit_price', 'label': 'Unit Price', 'align': 'right', 'format': 'currency'},
            {'key': 'gross_amount', 'label': 'Gross Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'team', 'label': 'Team', 'align': 'left', 'format': 'text'},
        ]
        daily_rows = []
        for p in perfs_qs:
            u_p = p.work_day.calculate_employee_unit_price(p.employee.role, p.photo_count)
            daily_rows.append({
                'date': p.work_day.date,
                'location': p.work_day.location.name if p.work_day.location else 'Unknown',
                'employee': f"{p.employee.first_name} {p.employee.last_name}",
                'role': p.employee.role.capitalize(),
                'pictures': p.photo_count,
                'unit_price': u_p,
                'gross_amount': Decimal(str(p.photo_count)) * Decimal(str(u_p)),
                'team': p.team.team_name if p.team else 'N/A',
            })
        self.write_table(ws_daily, r, daily_cols, daily_rows, theme=self.theme, include_totals=True, total_label_col='location')

        # ── Sheet 3 — Sellers ─────────────────────────────────────────────────
        ws_seller = self.create_sheet("Sellers")
        r = self.add_header_block(ws_seller, "Sellers Performance", f"Seller operations in period")
        seller_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'seller', 'label': 'Seller', 'align': 'left', 'format': 'text'},
            {'key': 'amount', 'label': 'Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'rating', 'label': 'Rating', 'align': 'center', 'format': 'status'},
        ]
        seller_rows = []
        for s in sellers_qs:
            seller_rows.append({
                'date': s.work_day.date,
                'location': s.work_day.location.name if s.work_day.location else 'Unknown',
                'seller': f"{s.seller.first_name} {s.seller.last_name}",
                'amount': s.amount,
                'rating': s.rating or 'N/A',
            })
        self.write_table(ws_seller, r, seller_cols, seller_rows, theme=self.theme, include_totals=True, total_label_col='location')

        # If Both locations selected, add location summary sheets
        if not self.location:
            ardis_loc = Location.objects.filter(name__icontains='ardis').first()
            sabllet_loc = Location.objects.filter(name__icontains='sabllet').first()

            if ardis_loc:
                ws_ardis = self.create_sheet("ARDIS Summary")
                r = self.add_header_block(ws_ardis, "ARDIS Summary", f"Period: {s_date} to {e_date}")
                a_teams = teams_qs.filter(work_day__location=ardis_loc)
                a_pics = a_teams.aggregate(tot=Sum('team_photo_count'))['tot'] or 0
                a_rows = [{'metric': 'Total Pictures', 'val': str(a_pics)}, {'metric': 'Total Teams', 'val': str(a_teams.count())}]
                self.write_table(ws_ardis, r, sum_cols, a_rows, theme="ardis")

            if sabllet_loc:
                ws_sabllet = self.create_sheet("SABLLET Summary")
                r = self.add_header_block(ws_sabllet, "SABLLET Summary", f"Period: {s_date} to {e_date}")
                s_teams = teams_qs.filter(work_day__location=sabllet_loc)
                s_pics = s_teams.aggregate(tot=Sum('team_photo_count'))['tot'] or 0
                s_rows = [{'metric': 'Total Pictures', 'val': str(s_pics)}, {'metric': 'Total Teams', 'val': str(s_teams.count())}]
                self.write_table(ws_sabllet, r, sum_cols, s_rows, theme="sabllet")
