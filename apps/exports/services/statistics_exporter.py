"""
Executive Statistics Excel Exporter.
Exports raw underlying numerical series and analytical metrics into structured multi-sheet Excel files.
"""

from decimal import Decimal
from datetime import date
from apps.statistics.services import StatisticsService
from common.exports.excel.base_exporter import BaseExcelExporter
from common.exports.excel.utils import generate_export_filename


class StatisticsExporter(BaseExcelExporter):
    """
    Generates a multi-sheet Executive Statistics workbook.
    """

    def __init__(self, time_filter: str = 'this_month', location_id=None, start_date=None, end_date=None):
        filename = generate_export_filename("Bara3im_Shoot_Statistics", time_filter, start_date=start_date, end_date=end_date)
        super().__init__(filename=filename, theme="gold")
        self.time_filter = time_filter
        self.location_id = location_id
        self.start_date = start_date
        self.end_date = end_date

    def build_workbook(self):
        tf, loc_id, s_d, e_d = self.time_filter, self.location_id, self.start_date, self.end_date

        overview = StatisticsService.get_overview(tf, loc_id, s_d, e_d)
        photo_stats = StatisticsService.get_role_stats('photographer', tf, loc_id, s_d, e_d)
        clown_stats = StatisticsService.get_role_stats('clown', tf, loc_id, s_d, e_d)
        seller_stats = StatisticsService.get_seller_stats(tf, loc_id, s_d, e_d)
        couple_stats = StatisticsService.get_couple_stats(tf, loc_id, s_d, e_d)
        att_stats = StatisticsService.get_attendance_stats(tf, loc_id, s_d, e_d)

        # ── Sheet 1 — Executive Overview ──────────────────────────────────────
        ws_ov = self.create_sheet("Overview")
        r = self.add_header_block(ws_ov, "Executive Overview Analytics", f"Time Filter: {tf.replace('_', ' ').capitalize()}")

        ov_cols = [
            {'key': 'metric', 'label': 'Metric', 'align': 'left', 'format': 'text'},
            {'key': 'val', 'label': 'Value', 'align': 'right', 'format': 'text'},
        ]
        ov_rows = [
            {'metric': 'Total WorkDays', 'val': str(overview.get('total_work_days', 0))},
            {'metric': 'Total Active Employees', 'val': str(overview.get('total_employees', 0))},
            {'metric': 'Total Pictures Taken', 'val': f"{overview.get('total_pictures', 0):,}"},
            {'metric': 'Average Pictures / Day', 'val': str(overview.get('avg_pictures_per_day', 0.0))},
            {'metric': 'Average Revenue / Day', 'val': f"{overview.get('avg_revenue', 0.0):,.2f} DA"},
            {'metric': 'Attendance Rate', 'val': f"{overview.get('attendance_rate', 0.0)}%"},
            {'metric': 'Avg Team Performance', 'val': str(overview.get('avg_team_performance', 0.0))},
        ]
        self.write_table(ws_ov, r, ov_cols, ov_rows, theme="gold")

        # ── Sheet 2 — Photographers ───────────────────────────────────────────
        ws_p = self.create_sheet("Photographers")
        r = self.add_header_block(ws_p, "Photographers Rankings", "Leaderboard data")
        p_cols = [
            {'key': 'rank', 'label': 'Rank', 'align': 'center', 'format': 'integer'},
            {'key': 'name', 'label': 'Photographer', 'align': 'left', 'format': 'text'},
            {'key': 'code', 'label': 'Code', 'align': 'center', 'format': 'text'},
            {'key': 'score', 'label': 'Productivity Score', 'align': 'right', 'format': 'integer'},
            {'key': 'total_pics', 'label': 'Total Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'days', 'label': 'Worked Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'avg_pics', 'label': 'Avg Pictures', 'align': 'right', 'format': 'decimal'},
            {'key': 'best_day', 'label': 'Best Day', 'align': 'right', 'format': 'integer'},
            {'key': 'att_rate', 'label': 'Attendance Rate', 'align': 'right', 'format': 'percentage'},
        ]
        p_rows = []
        for item in photo_stats.get('all_employees_stats', []):
            p_rows.append({
                'rank': item.get('rank', 0),
                'name': item.get('name', ''),
                'code': item.get('employee_code', ''),
                'score': item.get('productivity_score', 0),
                'total_pics': item.get('total_pictures', 0),
                'days': item.get('work_days_count', 0),
                'avg_pics': item.get('avg_pictures', 0.0),
                'best_day': item.get('best_day', 0),
                'att_rate': item.get('attendance_rate', 0.0) / 100.0,
            })
        self.write_table(ws_p, r, p_cols, p_rows, theme="gold", include_totals=True, total_label_col='name')

        # ── Sheet 3 — Clowns ──────────────────────────────────────────────────
        ws_c = self.create_sheet("Clowns")
        r = self.add_header_block(ws_c, "Clowns Rankings", "Leaderboard data")
        c_rows = []
        for item in clown_stats.get('all_employees_stats', []):
            c_rows.append({
                'rank': item.get('rank', 0),
                'name': item.get('name', ''),
                'code': item.get('employee_code', ''),
                'score': item.get('productivity_score', 0),
                'total_pics': item.get('total_pictures', 0),
                'days': item.get('work_days_count', 0),
                'avg_pics': item.get('avg_pictures', 0.0),
                'best_day': item.get('best_day', 0),
                'att_rate': item.get('attendance_rate', 0.0) / 100.0,
            })
        self.write_table(ws_c, r, p_cols, c_rows, theme="gold", include_totals=True, total_label_col='name')

        # ── Sheet 4 — Couples ─────────────────────────────────────────────────
        ws_cp = self.create_sheet("Couples")
        r = self.add_header_block(ws_cp, "Couples / Teams Rankings", "Top performing pairs")
        cp_cols = [
            {'key': 'rank', 'label': 'Rank', 'align': 'center', 'format': 'integer'},
            {'key': 'team_name', 'label': 'Team / Pair', 'align': 'left', 'format': 'text'},
            {'key': 'photographer', 'label': 'Photographer', 'align': 'left', 'format': 'text'},
            {'key': 'clown', 'label': 'Clown', 'align': 'left', 'format': 'text'},
            {'key': 'total_pics', 'label': 'Total Pictures', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'sessions', 'label': 'Sessions', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'avg_pics', 'label': 'Avg Pictures', 'align': 'right', 'format': 'decimal'},
            {'key': 'highest_daily', 'label': 'Highest Single Day', 'align': 'right', 'format': 'integer'},
        ]
        cp_rows = []
        for item in couple_stats.get('all_couples', []):
            cp_rows.append({
                'rank': item.get('rank', 0),
                'team_name': item.get('team_name', ''),
                'photographer': item.get('photographer', {}).get('name', ''),
                'clown': item.get('clown', {}).get('name', ''),
                'total_pics': item.get('total_pictures', 0),
                'sessions': item.get('sessions_count', 0),
                'avg_pics': item.get('avg_pictures', 0.0),
                'highest_daily': item.get('highest_daily', 0),
            })
        self.write_table(ws_cp, r, cp_cols, cp_rows, theme="gold", include_totals=True, total_label_col='team_name')

        # ── Sheet 5 — Sellers ─────────────────────────────────────────────────
        ws_s = self.create_sheet("Sellers")
        r = self.add_header_block(ws_s, "Sellers Rankings", "Seller revenue leaderboard")
        s_cols = [
            {'key': 'rank', 'label': 'Rank', 'align': 'center', 'format': 'integer'},
            {'key': 'name', 'label': 'Seller Name', 'align': 'left', 'format': 'text'},
            {'key': 'tot_rev', 'label': 'Total Revenue', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
            {'key': 'days', 'label': 'Worked Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'avg_rev', 'label': 'Avg Revenue/Day', 'align': 'right', 'format': 'currency'},
            {'key': 'best_rating', 'label': 'Best Rating', 'align': 'center', 'format': 'status'},
            {'key': 'highest_daily', 'label': 'Highest Day Amount', 'align': 'right', 'format': 'currency'},
        ]
        s_rows = []
        for item in seller_stats.get('leaderboard', []):
            s_rows.append({
                'rank': item.get('rank', 0),
                'name': item.get('name', ''),
                'tot_rev': Decimal(str(item.get('total_revenue', 0.0))),
                'days': item.get('work_days_count', 0),
                'avg_rev': Decimal(str(item.get('avg_revenue', 0.0))),
                'best_rating': item.get('best_rating', 'N/A'),
                'highest_daily': Decimal(str(item.get('highest_daily', 0.0))),
            })
        self.write_table(ws_s, r, s_cols, s_rows, theme="gold", include_totals=True, total_label_col='name')

        # ── Sheet 6 — Attendance ──────────────────────────────────────────────
        ws_a = self.create_sheet("Attendance Analytics")
        r = self.add_header_block(ws_a, "Attendance Analytics", "Attendance records summary")
        a_cols = [
            {'key': 'name', 'label': 'Employee Name', 'align': 'left', 'format': 'text'},
            {'key': 'role', 'label': 'Role', 'align': 'center', 'format': 'text'},
            {'key': 'att_rate', 'label': 'Attendance Rate', 'align': 'right', 'format': 'percentage'},
            {'key': 'present', 'label': 'Present Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'late', 'label': 'Late Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'absent', 'label': 'Absent Days', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
        ]
        a_rows = []
        for item in att_stats.get('rankings', []):
            a_rows.append({
                'name': item.get('name', ''),
                'role': item.get('role', '').capitalize(),
                'att_rate': item.get('attendance_rate', 0.0) / 100.0,
                'present': item.get('present_days', 0),
                'late': item.get('late_days', 0),
                'absent': item.get('absent_days', 0),
            })
        self.write_table(ws_a, r, a_cols, a_rows, theme="gold", include_totals=True, total_label_col='name')

        # ── Sheet 7 — Daily Trend Graph Data ─────────────────────────────────
        ws_trend = self.create_sheet("Daily Trend Graph Data")
        r = self.add_header_block(ws_trend, "Daily Graph Data Series", "Underlying numerical data for charts")
        t_cols = [
            {'key': 'date', 'label': 'Date', 'align': 'center', 'format': 'date'},
            {'key': 'day_name', 'label': 'Day', 'align': 'center', 'format': 'text'},
            {'key': 'pictures', 'label': 'Pictures Count', 'align': 'right', 'format': 'integer', 'formula_total': 'SUM'},
            {'key': 'revenue', 'label': 'Seller Revenue', 'align': 'right', 'format': 'currency', 'formula_total': 'SUM'},
        ]
        t_rows = []
        for item in overview.get('daily_trends', []):
            t_rows.append({
                'date': item.get('date', ''),
                'day_name': item.get('day_name', ''),
                'pictures': item.get('pictures', 0),
                'revenue': Decimal(str(item.get('revenue', 0.0))),
            })
        self.write_table(ws_trend, r, t_cols, t_rows, theme="gold", include_totals=True, total_label_col='day_name')
