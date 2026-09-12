"""
Unit and integration tests for the Advanced Excel Export Center in Bara3im Shoot.
Verifies workbook generation, openpyxl sheets, dynamic pricing calculation, location filters,
data privacy, and permission security.
"""

from decimal import Decimal
from datetime import date, timedelta
import openpyxl
from io import BytesIO

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.employees.models import Employee, Bonus, Deduction, Advance
from apps.daily_sessions.models import Location, WorkDay, DailyTeam, DailyEmployeePerformance, SellerDailyOperation
from apps.attendance.models import AttendanceRecord
from apps.exports.services import (
    EmployeeExporter,
    AllEmployeesExporter,
    DailyExporter,
    DateRangeExporter,
    StatisticsExporter,
    DatabaseExporter,
)

User = get_user_model()


class ExcelExportTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Users
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Password123!',
            role='admin',
            is_staff=True
        )
        self.employee_user = User.objects.create_user(
            username='emp_test',
            email='emp@test.com',
            password='Password123!',
            role='photographer'
        )

        # Locations
        self.loc_ardis = Location.objects.create(name='ARDIS', icon='📍', color_hex='#1565C0')
        self.loc_sabllet = Location.objects.create(name='SABLLET', icon='🎡', color_hex='#D81B60')

        # Employees
        self.photographer = Employee.objects.create(
            user=self.employee_user,
            employee_code='EMP-0001',
            first_name='Ahmed',
            last_name='Benali',
            phone_number='0555123456',
            hiring_date=date(2026, 1, 1),
            role='photographer',
            status='active'
        )
        self.clown_user = User.objects.create_user(username='clown_test', email='clown@test.com', password='Password123!', role='clown')
        self.clown = Employee.objects.create(
            user=self.clown_user,
            employee_code='EMP-0002',
            first_name='Yacine',
            last_name='Brahimi',
            phone_number='0555987654',
            hiring_date=date(2026, 1, 1),
            role='clown',
            status='active'
        )

        # WorkDay at ARDIS with high tier photo count (85 photos -> >= 80 tier)
        self.workday_ardis = WorkDay.objects.create(
            location=self.loc_ardis,
            date=date(2026, 9, 12),
            status='completed',
            dynamic_pricing_enabled=True,
            photographer_unit_price=45,
            clown_unit_price=50,
            high_photo_threshold=80,
            high_photographer_price=50,
            high_clown_price=55
        )
        self.team = DailyTeam.objects.create(
            work_day=self.workday_ardis,
            photographer=self.photographer,
            clown=self.clown,
            team_name='Team Alpha',
            team_photo_count=85
        )

        # Attendance Record
        AttendanceRecord.objects.create(
            employee=self.photographer,
            date=date(2026, 9, 12),
            check_in_time=date(2026, 9, 12),
            minutes_late=0,
            status='present'
        )

    def test_employee_exporter_sheets_and_content(self):
        """Test individual employee Excel workbook generation."""
        exporter = EmployeeExporter(self.photographer)
        exporter.build_workbook()
        raw_bytes = exporter.generate_workbook_bytes()
        
        wb = openpyxl.load_workbook(filename=BytesIO(raw_bytes))
        sheet_names = wb.sheetnames
        
        self.assertIn("Employee Summary", sheet_names)
        self.assertIn("Daily History", sheet_names)
        self.assertIn("Attendance", sheet_names)
        self.assertIn("Earnings", sheet_names)
        self.assertIn("Teams", sheet_names)
        self.assertIn("Locations", sheet_names)
        self.assertIn("Statistics", sheet_names)
        self.assertIn("Picture Performance", sheet_names)

    def test_daily_exporter_dynamic_pricing_tier(self):
        """Test single workday export applies dynamic pricing rules correctly."""
        exporter = DailyExporter(self.workday_ardis)
        exporter.build_workbook()
        raw_bytes = exporter.generate_workbook_bytes()
        
        wb = openpyxl.load_workbook(filename=BytesIO(raw_bytes))
        ws_teams = wb["Teams"]
        
        # Check photographer unit price cell for high tier (50 DA)
        cell_val = ws_teams.cell(row=6, column=5).value
        self.assertEqual(float(cell_val), 50.0)

    def test_database_exporter_excludes_sensitive_auth(self):
        """Test complete database archive NEVER exposes passwords or secret tokens."""
        exporter = DatabaseExporter()
        exporter.build_workbook()
        raw_bytes = exporter.generate_workbook_bytes()

        wb = openpyxl.load_workbook(filename=BytesIO(raw_bytes))
        content_str = str(raw_bytes)

        self.assertNotIn("password", content_str.lower())
        self.assertNotIn("pbkdf2", content_str.lower())

    def test_api_permission_security(self):
        """Test permission checks on API export endpoints."""
        # Unauthenticated request fails
        url = reverse('export_database_excel')
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Employee user request to admin database export fails with 403 Forbidden
        self.client.force_authenticate(user=self.employee_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        # Admin user request succeeds with 200 OK and Excel content header
        self.client.force_authenticate(user=self.admin_user)
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", res['Content-Type'])
