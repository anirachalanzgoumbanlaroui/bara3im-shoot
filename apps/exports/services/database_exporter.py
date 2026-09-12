"""
Complete Operational Database Backup Excel Exporter.
Exports all operational database models into a structured Excel workbook.
STRICT PRIVACY GUARANTEE: Excludes passwords, hashes, tokens, API keys, and sensitive auth data.
"""

from decimal import Decimal
from apps.employees.models import Employee, Bonus, Deduction, Advance
from apps.daily_sessions.models import Location, WorkDay, DailyTeam, DailyEmployeePerformance, SellerDailyOperation
from apps.attendance.models import AttendanceRecord, AttendanceRule
from common.exports.excel.base_exporter import BaseExcelExporter
from common.exports.excel.utils import generate_export_filename


class DatabaseExporter(BaseExcelExporter):
    """
    Generates a complete operational database backup Excel file.
    Admin-only access required.
    """

    def __init__(self):
        filename = generate_export_filename("Bara3im_Shoot_Complete_Database_Backup", "Archive")
        super().__init__(filename=filename, theme="gold")

    def build_workbook(self):
        # ── Sheet 1 — Employees ───────────────────────────────────────────────
        ws_emp = self.create_sheet("Employees")
        r = self.add_header_block(ws_emp, "Database Table — Employees", "Operational staff records")
        emp_cols = [
            {'key': 'id', 'label': 'UUID', 'align': 'center', 'format': 'text'},
            {'key': 'code', 'label': 'Employee Code', 'align': 'center', 'format': 'text'},
            {'key': 'first_name', 'label': 'First Name', 'align': 'left', 'format': 'text'},
            {'key': 'last_name', 'label': 'Last Name', 'align': 'left', 'format': 'text'},
            {'key': 'phone', 'label': 'Phone', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'status', 'label': 'Status', 'align': 'center', 'format': 'status'},
            {'key': 'hiring_date', 'label': 'Hiring Date', 'align': 'center', 'format': 'date'},
        ]
        emp_rows = []
        for emp in Employee.objects.all().order_by('hiring_date'):
            emp_rows.append({
                'id': str(emp.id),
                'code': emp.employee_code or '',
                'first_name': emp.first_name,
                'last_name': emp.last_name,
                'phone': emp.phone_number or '',
                'role': emp.role,
                'status': emp.status,
                'hiring_date': emp.hiring_date,
            })
        self.write_table(ws_emp, r, emp_cols, emp_rows, theme="gold")

        # ── Sheet 2 — Locations ───────────────────────────────────────────────
        ws_loc = self.create_sheet("Locations")
        r = self.add_header_block(ws_loc, "Database Table — Locations", "Work locations")
        loc_cols = [
            {'key': 'id', 'label': 'UUID', 'align': 'center', 'format': 'text'},
            {'key': 'name', 'label': 'Location Name', 'align': 'left', 'format': 'text'},
            {'key': 'icon', 'label': 'Icon', 'align': 'center', 'format': 'text'},
            {'key': 'color', 'label': 'Color Hex', 'align': 'center', 'format': 'text'},
        ]
        loc_rows = []
        for loc in Location.objects.all():
            loc_rows.append({
                'id': str(loc.id),
                'name': loc.name,
                'icon': loc.icon,
                'color': loc.color_hex,
            })
        self.write_table(ws_loc, r, loc_cols, loc_rows, theme="gold")

        # ── Sheet 3 — WorkDays ────────────────────────────────────────────────
        ws_wd = self.create_sheet("WorkDays")
        r = self.add_header_block(ws_wd, "Database Table — WorkDays", "Daily work sessions")
        wd_cols = [
            {'key': 'id', 'label': 'UUID', 'align': 'center', 'format': 'text'},
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'status', 'label': 'Status', 'align': 'center', 'format': 'status'},
            {'key': 'photo_unit', 'label': 'Photographer Unit', 'align': 'right', 'format': 'currency'},
            {'key': 'clown_unit', 'label': 'Clown Unit', 'align': 'right', 'format': 'currency'},
            {'key': 'total_photos', 'label': 'Total Photos', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
        ]
        wd_rows = []
        for wd in WorkDay.objects.select_related('location').all().order_by('-date'):
            wd_rows.append({
                'id': str(wd.id),
                'date': wd.date,
                'location': wd.location.name if wd.location else '',
                'status': wd.status,
                'photo_unit': wd.photographer_unit_price,
                'clown_unit': wd.clown_unit_price,
                'total_photos': wd.total_photos,
            })
        self.write_table(ws_wd, r, wd_cols, wd_rows, theme="gold", include_totals=True, total_label_col='location')

        # ── Sheet 4 — DailyTeams ──────────────────────────────────────────────
        ws_dt = self.create_sheet("DailyTeams")
        r = self.add_header_block(ws_dt, "Database Table — DailyTeams", "Team compositions")
        dt_cols = [
            {'key': 'id', 'label': 'UUID', 'align': 'center', 'format': 'text'},
            {'key': 'date', 'label': 'WorkDay Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'team_name', 'label': 'Team Name', 'align': 'left', 'format': 'text'},
            {'key': 'photographer', 'label': 'Photographer', 'align': 'left', 'format': 'text'},
            {'key': 'clown', 'label': 'Clown', 'align': 'left', 'format': 'text'},
            {'key': 'team_photos', 'label': 'Team Photos', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
        ]
        dt_rows = []
        for dt in DailyTeam.objects.select_related('work_day', 'work_day__location', 'photographer', 'clown').all().order_by('-work_day__date'):
            dt_rows.append({
                'id': str(dt.id),
                'date': dt.work_day.date,
                'location': dt.work_day.location.name if dt.work_day.location else '',
                'team_name': dt.team_name or '',
                'photographer': f"{dt.photographer.first_name} {dt.photographer.last_name}" if dt.photographer else '',
                'clown': f"{dt.clown.first_name} {dt.clown.last_name}" if dt.clown else '',
                'team_photos': dt.team_photo_count,
            })
        self.write_table(ws_dt, r, dt_cols, dt_rows, theme="gold", include_totals=True, total_label_col='team_name')

        # ── Sheet 5 — SellerDailyOperations ──────────────────────────────────
        ws_sdo = self.create_sheet("SellerDailyOperations")
        r = self.add_header_block(ws_sdo, "Database Table — SellerDailyOperations", "Seller performance")
        sdo_cols = [
            {'key': 'id', 'label': 'UUID', 'align': 'center', 'format': 'text'},
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'location', 'label': 'Location', 'align': 'left', 'format': 'text'},
            {'key': 'seller', 'label': 'Seller Name', 'align': 'left', 'format': 'text'},
            {'key': 'amount', 'label': 'Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'rating', 'label': 'Rating', 'align': 'center', 'format': 'status'},
        ]
        sdo_rows = []
        for op in SellerDailyOperation.objects.select_related('work_day', 'work_day__location', 'seller').all().order_by('-work_day__date'):
            sdo_rows.append({
                'id': str(op.id),
                'date': op.work_day.date,
                'location': op.work_day.location.name if op.work_day.location else '',
                'seller': f"{op.seller.first_name} {op.seller.last_name}",
                'amount': op.amount,
                'rating': op.rating or '',
            })
        self.write_table(ws_sdo, r, sdo_cols, sdo_rows, theme="gold", include_totals=True, total_label_col='seller')

        # ── Sheet 6 — AttendanceRecords ───────────────────────────────────────
        ws_att = self.create_sheet("AttendanceRecords")
        r = self.add_header_block(ws_att, "Database Table — AttendanceRecords", "Check-in logs")
        att_cols = [
            {'key': 'id', 'label': 'UUID', 'align': 'center', 'format': 'text'},
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'employee', 'label': 'Employee', 'align': 'left', 'format': 'text'},
            {'key': 'status', 'label': 'Status', 'align': 'center', 'format': 'status'},
            {'key': 'check_in', 'label': 'Check-In', 'align': 'center', 'format': 'time'},
            {'key': 'minutes_late', 'label': 'Minutes Late', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
        ]
        att_rows = []
        for att in AttendanceRecord.objects.select_related('employee').all().order_by('-date'):
            att_rows.append({
                'id': str(att.id),
                'date': att.date,
                'employee': f"{att.employee.first_name} {att.employee.last_name}",
                'status': att.status,
                'check_in': att.check_in_time.strftime('%H:%M:%S') if att.check_in_time else '',
                'late_minutes': att.minutes_late,
            })
        self.write_table(ws_att, r, att_cols, att_rows, theme="gold", include_totals=True, total_label_col='employee')

        # ── Sheet 7 — Financial Transactions (Bonuses, Deductions, Advances) ─
        ws_fin = self.create_sheet("Financial Transactions")
        r = self.add_header_block(ws_fin, "Database Table — Financial Transactions", "Bonuses, Deductions, Advances")
        fin_cols = [
            {'key': 'type', 'label': 'Type', 'align': 'center', 'format': 'text'},
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'employee', 'label': 'Employee', 'align': 'left', 'format': 'text'},
            {'key': 'amount', 'label': 'Amount', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'reason', 'label': 'Reason', 'align': 'left', 'format': 'text'},
        ]
        fin_rows = []
        for b in Bonus.objects.select_related('employee').all():
            fin_rows.append({
                'type': 'Bonus', 'date': b.date, 'employee': f"{b.employee.first_name} {b.employee.last_name}",
                'amount': b.amount, 'reason': b.reason or '',
            })
        for d in Deduction.objects.select_related('employee').all():
            fin_rows.append({
                'type': 'Deduction', 'date': d.date, 'employee': f"{d.employee.first_name} {d.employee.last_name}",
                'amount': d.amount, 'reason': d.reason or '',
            })
        for a in Advance.objects.select_related('employee').all():
            fin_rows.append({
                'type': 'Advance', 'date': a.date, 'employee': f"{a.employee.first_name} {a.employee.last_name}",
                'amount': a.amount, 'reason': a.reason or '',
            })
        fin_rows.sort(key=lambda x: str(x['date']), reverse=True)
        self.write_table(ws_fin, r, fin_cols, fin_rows, theme="gold", include_totals=True, total_label_col='employee')
