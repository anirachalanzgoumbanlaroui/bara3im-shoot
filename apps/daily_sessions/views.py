from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog
from .serializers import (
    WorkDaySerializer, WorkDayListSerializer,
    DailyTeamSerializer, DailyEmployeePerformanceSerializer,
    DailyOperationLogSerializer
)
from .services import DailyOperationsService


class WorkDayViewSet(viewsets.ModelViewSet):
    queryset = WorkDay.objects.all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkDayListSerializer
        return WorkDaySerializer

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        work_day = self.get_object()
        summary_data = DailyOperationsService.generate_daily_summary(work_day)
        return Response(summary_data)

    @action(detail=True, methods=['post'])
    def recalculate(self, request, pk=None):
        work_day = self.get_object()
        DailyOperationsService.recalculate_work_day(work_day, request.user)
        return Response(self.get_serializer(work_day).data)

    @action(detail=True, methods=['post'])
    def generate_teams(self, request, pk=None):
        work_day = self.get_object()
        teams_created = DailyOperationsService.generate_teams(work_day, request.user)
        return Response({"detail": f"Generated {teams_created} teams.", "teams_created": teams_created})

    @action(detail=True, methods=['post'])
    def copy_yesterday(self, request, pk=None):
        work_day = self.get_object()
        teams_copied = DailyOperationsService.copy_yesterday_teams(work_day, request.user)
        return Response({"detail": f"Copied {teams_copied} teams.", "teams_copied": teams_copied})


class DailyTeamViewSet(viewsets.ModelViewSet):
    queryset = DailyTeam.objects.all()
    serializer_class = DailyTeamSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']

    def perform_create(self, serializer):
        team = serializer.save()
        
        # Create performance records so earnings are tracked and cascade correctly
        DailyEmployeePerformance.objects.get_or_create(
            work_day=team.work_day,
            employee=team.photographer,
            team=team,
            defaults={'photo_count': team.team_photo_count, 'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC}
        )
        DailyEmployeePerformance.objects.get_or_create(
            work_day=team.work_day,
            employee=team.clown,
            team=team,
            defaults={'photo_count': team.team_photo_count, 'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC}
        )
        
        DailyOperationsService.log_action(
            team.work_day, "Team Created", self.request.user, 
            {"team_id": str(team.id), "team_name": team.team_name}
        )

    def perform_update(self, serializer):
        team = serializer.save()
        DailyOperationsService.log_action(
            team.work_day, "Team Edited", self.request.user, 
            {"team_id": str(team.id)}
        )

    @action(detail=False, methods=['post'], url_path='quick-entry')
    def quick_entry(self, request):
        """
        Accepts a list of dictionaries: [{"id": "uuid", "team_photo_count": 100}, ...]
        """
        data = request.data
        if not isinstance(data, list):
            return Response({"detail": "Expected a list of updates."}, status=status.HTTP_400_BAD_REQUEST)
            
        updated_teams = []
        for item in data:
            team_id = item.get('id')
            new_count = item.get('team_photo_count')
            if team_id and new_count is not None:
                team = get_object_or_404(DailyTeam, id=team_id)
                DailyOperationsService.quick_entry_update_team(team, int(new_count), request.user)
                updated_teams.append(team.id)
                
        return Response({"detail": f"Updated {len(updated_teams)} teams."})


class DailyEmployeePerformanceViewSet(viewsets.ModelViewSet):
    queryset = DailyEmployeePerformance.objects.all()
    serializer_class = DailyEmployeePerformanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day', 'team', 'employee']

    def perform_update(self, serializer):
        perf = serializer.save()
        DailyOperationsService.log_action(
            perf.work_day, "Employee Performance Updated", self.request.user,
            {"performance_id": str(perf.id), "employee": perf.employee.first_name, "type": perf.adjustment_type}
        )

class DailyOperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyOperationLog.objects.all()
    serializer_class = DailyOperationLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']
