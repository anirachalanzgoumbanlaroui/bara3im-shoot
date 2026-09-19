from common.exports.excel.base_exporter import BaseExcelExporter
from common.exports.excel.utils import generate_export_filename
from apps.statistics.services import StatisticsService
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

class LocationDailyComparisonExporter(BaseExcelExporter):
    def __init__(self, time_filter='this_month', start_date=None, end_date=None):
        filename = generate_export_filename("Location_Comparison", time_filter, start_date=start_date, end_date=end_date)
        super().__init__(filename=filename, theme="blue")
        self.time_filter = time_filter
        self.start_date = start_date
        self.end_date = end_date

    def build_workbook(self):
        data = StatisticsService.get_location_daily_comparison(
            self.time_filter, None, self.start_date, self.end_date
        )
        
        ws = self.create_sheet("Location Daily Comparison")
        # Add basic header block (returns next row)
        r = self.add_header_block(ws, "Location Daily Comparison", f"Time Filter: {self.time_filter.replace('_', ' ').capitalize()}")
        
        series = data.get('series', [])
        
        # We need to make sure we get the correct location names to match ARDIS and SABLLET
        ardis_data = next((s for s in series if 'ARDIS' in s['location_name'].upper()), None)
        sabllet_data = next((s for s in series if 'SABLLET' in s['location_name'].upper()), None)
        
        dates = []
        if ardis_data and ardis_data.get('data'):
            dates = [d['date'] for d in ardis_data['data']]
        elif sabllet_data and sabllet_data.get('data'):
            dates = [d['date'] for d in sabllet_data['data']]
        
        # Write custom table header
        headers = ["Date", "ARDIS", "SABLLET", "Daily Total"]
        for col_idx, header_text in enumerate(headers, 1):
            cell = ws.cell(row=r, column=col_idx, value=header_text)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.alignment = Alignment(horizontal="center", vertical="center")
            if header_text == "ARDIS":
                cell.fill = PatternFill(start_color="1565C0", end_color="1565C0", fill_type="solid")
            elif header_text == "SABLLET":
                cell.fill = PatternFill(start_color="D81B60", end_color="D81B60", fill_type="solid")
            else:
                cell.fill = PatternFill(start_color="333333", end_color="333333", fill_type="solid")
        
        # Enable auto filter
        ws.auto_filter.ref = f"A{r}:D{r}"
        
        r += 1
        start_data_row = r
        
        ardis_map = {d['date']: d['pictures'] for d in ardis_data['data']} if ardis_data else {}
        sabllet_map = {d['date']: d['pictures'] for d in sabllet_data['data']} if sabllet_data else {}
        
        zebra_fill_1 = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
        zebra_fill_2 = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
        
        for idx, d in enumerate(dates):
            a_val = ardis_map.get(d, 0)
            s_val = sabllet_map.get(d, 0)
            total_val = a_val + s_val
            
            fill = zebra_fill_1 if idx % 2 == 0 else zebra_fill_2
            
            # Date
            c1 = ws.cell(row=r, column=1, value=d)
            c1.fill = fill
            
            # ARDIS
            c2 = ws.cell(row=r, column=2, value=a_val)
            c2.fill = fill
            c2.number_format = '#,##0'
            
            # SABLLET
            c3 = ws.cell(row=r, column=3, value=s_val)
            c3.fill = fill
            c3.number_format = '#,##0'
            
            # Total
            c4 = ws.cell(row=r, column=4, value=total_val)
            c4.fill = fill
            c4.number_format = '#,##0'
            
            r += 1
            
        end_data_row = r - 1
        
        # Summary Row (SUM)
        for col_idx, label in enumerate(["SUM", "AVERAGE"]):
            ws.cell(row=r, column=1, value=label).font = Font(bold=True)
            for c_idx in range(2, 5):
                col_letter = get_column_letter(c_idx)
                formula = f"={label}({col_letter}{start_data_row}:{col_letter}{end_data_row})"
                cell = ws.cell(row=r, column=c_idx, value=formula)
                cell.font = Font(bold=True)
                cell.number_format = '#,##0.00' if label == "AVERAGE" else '#,##0'
            r += 1
            
        # Auto-size columns
        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = adjusted_width
