"""
API views for the Advanced Excel Export Center in Bara3im Shoot.
Handles authentication, permission checks, query parameter parsing, and streams openpyxl Excel workbooks.
"""

import uuid
from datetime import datetime, date
from django.shortcuts import get_object_or_404
from django.db import models
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.employees.models import Employee
from apps.daily_sessions.models import WorkDay, Location
from apps.exports.services import (
    EmployeeExporter,
    AllEmployeesExporter,
    DailyExporter,
    DateRangeExporter,
    StatisticsExporter,
    DatabaseExporter,
)


class IsAdminUserPermission(permissions.BasePermission):
    """Permission allowing only users with role='admin' or is_staff/is_superuser."""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return (
            getattr(request.user, 'role', '') == 'admin' or
            request.user.is_staff or
            request.user.is_superuser
        )


class ExportCenterOverviewView(APIView):
    """
    GET /api/exports/center/
    Returns configuration & options for the Export Center dashboard.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        is_admin = getattr(user, 'role', '') == 'admin' or user.is_staff or user.is_superuser

        categories = [
            {'id': 'employee', 'name': 'Employee Export', 'description': 'Export individual employee complete history', 'admin_only': False},
            {'id': 'all_employees', 'name': 'All Employees Report', 'description': 'Export master report for all employees', 'admin_only': True},
            {'id': 'daily', 'name': 'Daily Operations Report', 'description': 'Export single workday operational data', 'admin_only': False},
            {'id': 'date_range', 'name': 'Date Range & Location Report', 'description': 'Export custom period across ARDIS & SABLLET', 'admin_only': True},
            {'id': 'statistics', 'name': 'Executive Statistics', 'description': 'Export underlying data for executive analytics', 'admin_only': True},
            {'id': 'database', 'name': 'Complete Database Backup', 'description': 'Export full operational database archive', 'admin_only': True},
        ]

        presets = [
            {'id': 'today_ardis', 'label': "Today's ARDIS Report", 'type': 'daily', 'location': 'ARDIS', 'preset_date': 'today'},
            {'id': 'today_sabllet', 'label': "Today's SABLLET Report", 'type': 'daily', 'location': 'SABLLET', 'preset_date': 'today'},
            {'id': 'this_week_all', 'label': 'This Week — All Employees', 'type': 'date_range', 'time_filter': 'this_week'},
            {'id': 'this_month_financial', 'label': 'This Month — Financials', 'type': 'statistics', 'time_filter': 'this_month'},
            {'id': 'complete_database', 'label': 'Complete Database Backup', 'type': 'database'},
        ]

        locations = list(Location.objects.all().values('id', 'name', 'icon', 'color_hex'))

        return Response({
            'is_admin': is_admin,
            'categories': [c for c in categories if is_admin or not c['admin_only']],
            'presets': presets if is_admin else [p for p in presets if p['type'] in ['daily', 'employee']],
            'locations': locations,
        })


class EmployeeExcelExportView(APIView):
    """
    GET /api/exports/employee/<id>/excel/
    Generates and streams an individual employee's complete Excel workbook.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, employee_id):
        # Flexible lookup: UUID, user__id, or employee_code
        employee = None
        try:
            val = uuid.UUID(str(employee_id))
            employee = Employee.objects.filter(
                models.Q(id=val) | models.Q(user__id=val) | models.Q(employee_code=str(employee_id))
            ).first()
        except ValueError:
            employee = Employee.objects.filter(employee_code=str(employee_id)).first()

        if not employee:
            return Response({'detail': f'Employee with ID or code "{employee_id}" not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Permission check: Admin can export anyone. Employee can export only self if linked.
        user = request.user
        is_admin = getattr(user, 'role', '') == 'admin' or user.is_staff or user.is_superuser
        if not is_admin:
            if not hasattr(user, 'employee_profile') or user.employee_profile.id != employee.id:
                return Response({'detail': 'Permission denied. You can only export your own profile.'}, status=status.HTTP_403_FORBIDDEN)

        exporter = EmployeeExporter(employee)
        exporter.build_workbook()
        return exporter.export_to_response()


class AllEmployeesExcelExportView(APIView):
    """
    GET /api/exports/employees/excel/
    Generates and streams master workbook for all employees. Admin only.
    """
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        exporter = AllEmployeesExporter()
        exporter.build_workbook()
        return exporter.export_to_response()


class DailyWorkDayExcelExportView(APIView):
    """
    GET /api/exports/daily/<id>/excel/
    GET /api/exports/daily/excel/?date=YYYY-MM-DD&location_id=...
    Generates single day Excel report.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, workday_id=None):
        if workday_id:
            try:
                val = uuid.UUID(str(workday_id))
                work_day = get_object_or_404(WorkDay, pk=val)
            except ValueError:
                work_day = get_object_or_404(WorkDay, pk=workday_id)
        else:
            date_str = request.query_params.get('date')
            location_id = request.query_params.get('location_id') or request.query_params.get('location')

            if not date_str or not location_id:
                return Response({'detail': 'Both date and location are required.'}, status=status.HTTP_400_BAD_REQUEST)

            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'detail': 'Invalid date format. Use YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

            work_day = get_object_or_404(WorkDay, date=target_date, location_id=location_id)

        exporter = DailyExporter(work_day)
        exporter.build_workbook()
        return exporter.export_to_response()


class DateRangeExcelExportView(APIView):
    """
    GET /api/exports/date-range/excel/?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&location_id=...&role=...
    Generates range & location Excel report. Admin only.
    """
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        s_str = request.query_params.get('start_date')
        e_str = request.query_params.get('end_date')
        location_id = request.query_params.get('location_id') or request.query_params.get('location')
        role = request.query_params.get('role')

        today = date.today()
        start_date = today.replace(day=1)
        end_date = today

        if s_str:
            try:
                start_date = datetime.strptime(s_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        if e_str:
            try:
                end_date = datetime.strptime(e_str, '%Y-%m-%d').date()
            except ValueError:
                pass

        exporter = DateRangeExporter(start_date, end_date, location_id=location_id, role=role)
        exporter.build_workbook()
        return exporter.export_to_response()


class StatisticsExcelExportView(APIView):
    """
    GET /api/exports/statistics/excel/?time_filter=...&location_id=...&start_date=...&end_date=...
    Generates executive statistics analytics Excel workbook. Admin only.
    """
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        time_filter = request.query_params.get('time_filter', 'this_month')
        location_id = request.query_params.get('location_id') or request.query_params.get('location')
        s_str = request.query_params.get('start_date')
        e_str = request.query_params.get('end_date')

        s_d = datetime.strptime(s_str, '%Y-%m-%d').date() if s_str else None
        e_d = datetime.strptime(e_str, '%Y-%m-%d').date() if e_str else None

        exporter = StatisticsExporter(time_filter=time_filter, location_id=location_id, start_date=s_d, end_date=e_d)
        exporter.build_workbook()
        return exporter.export_to_response()


class DatabaseExcelExportView(APIView):
    """
    GET /api/exports/database/excel/
    Generates complete operational database backup workbook. Admin only.
    """
    permission_classes = [IsAdminUserPermission]

    def get(self, request):
        exporter = DatabaseExporter()
        exporter.build_workbook()
        return exporter.export_to_response()
