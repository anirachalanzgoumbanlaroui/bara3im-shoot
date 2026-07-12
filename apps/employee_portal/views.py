from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.employees.models import Employee
from .services.dashboard_service import EmployeeDashboardService
from .services.statistics_service import StatisticsService
from .services.timeline_service import TimelineService
from .services.history_service import HistoryService

class EmployeePortalPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

class IsEmployee(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and hasattr(request.user, 'employee_profile')

class EmployeeDashboardViewSet(viewsets.ViewSet):
    """
    Backend-For-Frontend (BFF) endpoints for the Employee Portal.
    Strictly restricted to the currently authenticated employee.
    """
    permission_classes = [IsEmployee]

    def get_employee(self):
        return self.request.user.employee_profile

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        data = EmployeeDashboardService.get_dashboard_data(self.get_employee())
        return Response(data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        data = StatisticsService.get_statistics(self.get_employee())
        return Response(data)

    @action(detail=False, methods=['get'])
    def timeline(self, request):
        # We can paginate the timeline if needed, but for now we return top 20 of each combined
        data = TimelineService.get_timeline(self.get_employee())
        
        paginator = EmployeePortalPagination()
        paginated_data = paginator.paginate_queryset(data, request)
        return paginator.get_paginated_response(paginated_data)

    @action(detail=False, methods=['get'], url_path='history/attendance')
    def attendance_history(self, request):
        queryset = HistoryService.get_attendance_history(self.get_employee())
        
        # Filtering
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        paginator = EmployeePortalPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        data = []
        for att in page:
            data.append({
                'id': str(att.id),
                'date': att.date.isoformat(),
                'check_in_time': att.check_in_time.isoformat(),
                'status': att.status,
                'minutes_late': att.minutes_late,
                'method': getattr(att, 'method', 'unknown'), # Note: method is on rule, but we can just say attendance recorded
                'notes': att.notes
            })
            
        return paginator.get_paginated_response(data)

    @action(detail=False, methods=['get'], url_path='history/daily')
    def work_history(self, request):
        queryset = HistoryService.get_work_history(self.get_employee())
        
        paginator = EmployeePortalPagination()
        page = paginator.paginate_queryset(queryset, request)
        
        data = []
        for perf in page:
            work_day = perf.work_day
            team = perf.team
            unit_price = work_day.photographer_unit_price if self.get_employee().role == 'photographer' else work_day.clown_unit_price
            
            earnings = float(perf.photo_count * unit_price)
            
            data.append({
                'id': str(perf.id),
                'date': work_day.date.isoformat(),
                'photo_count': perf.photo_count,
                'earnings': earnings,
                'unit_price': float(unit_price),
                'adjustment_type': perf.adjustment_type,
                'adjustment_reason': perf.adjustment_reason,
                'team': {
                    'team_name': team.team_name,
                    'photographer': f"{team.photographer.first_name} {team.photographer.last_name}",
                    'clown': f"{team.clown.first_name} {team.clown.last_name}"
                }
            })
            
        return paginator.get_paginated_response(data)

    @action(detail=False, methods=['get'])
    def profile(self, request):
        employee = self.get_employee()
        
        return Response({
            'id': str(employee.id),
            'employee_code': employee.employee_code,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'role': employee.role,
            'hiring_date': employee.hiring_date.isoformat(),
            'status': employee.status,
            'phone_number': employee.phone_number,
            'avatar': employee.avatar.url if employee.avatar else None,
        })
