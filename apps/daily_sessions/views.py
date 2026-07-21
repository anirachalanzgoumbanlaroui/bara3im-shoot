import os
import subprocess
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Location, DailyLocation, WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation
from .serializers import (
    LocationSerializer, DailyLocationSerializer,
    WorkDaySerializer, WorkDayListSerializer,
    DailyTeamSerializer, DailyEmployeePerformanceSerializer,
    DailyOperationLogSerializer, SellerDailyOperationSerializer
)
from .services import DailyOperationsService
from apps.employees.models import Employee


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticated]


class DailyLocationViewSet(viewsets.ModelViewSet):
    queryset = DailyLocation.objects.all()
    serializer_class = DailyLocationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day', 'location']

    @action(detail=True, methods=['post'])
    def generate_teams(self, request, pk=None):
        daily_location = self.get_object()
        teams_created = DailyOperationsService.generate_teams(daily_location, request.user)
        return Response({"detail": f"Generated {teams_created} teams.", "teams_created": teams_created})

    @action(detail=True, methods=['post'])
    def copy_yesterday(self, request, pk=None):
        daily_location = self.get_object()
        teams_copied = DailyOperationsService.copy_yesterday_teams(daily_location, request.user)
        return Response({"detail": f"Copied {teams_copied} teams.", "teams_copied": teams_copied})


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


class DailyTeamViewSet(viewsets.ModelViewSet):
    queryset = DailyTeam.objects.all()
    serializer_class = DailyTeamSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['daily_location', 'daily_location__work_day']

    def perform_create(self, serializer):
        team = serializer.save()
        work_day = team.daily_location.work_day
        
        # Create performance records so earnings are tracked and cascade correctly
        DailyEmployeePerformance.objects.get_or_create(
            work_day=work_day,
            employee=team.photographer,
            defaults={
                'team': team,
                'photo_count': team.team_photo_count,
                'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                'daily_location': team.daily_location
            }
        )
        DailyEmployeePerformance.objects.get_or_create(
            work_day=work_day,
            employee=team.clown,
            defaults={
                'team': team,
                'photo_count': team.team_photo_count,
                'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
                'daily_location': team.daily_location
            }
        )
        
        DailyOperationsService.log_action(
            work_day, "Team Created", self.request.user, 
            {"team_id": str(team.id), "team_name": team.team_name, "location": team.daily_location.location.name}
        )

    def perform_update(self, serializer):
        team = serializer.save()
        DailyOperationsService.log_action(
            team.daily_location.work_day, "Team Edited", self.request.user, 
            {"team_id": str(team.id), "location": team.daily_location.location.name}
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
    filterset_fields = ['work_day', 'daily_location', 'team', 'employee']

    def perform_update(self, serializer):
        perf = serializer.save()
        DailyOperationsService.log_action(
            perf.work_day, "Employee Performance Updated", self.request.user,
            {"performance_id": str(perf.id), "employee": perf.employee.first_name, "type": perf.adjustment_type, "location": perf.daily_location.location.name if perf.daily_location else None}
        )


class DailyOperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyOperationLog.objects.all()
    serializer_class = DailyOperationLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']


class SellerDailyOperationViewSet(viewsets.ModelViewSet):
    queryset = SellerDailyOperation.objects.all()
    serializer_class = SellerDailyOperationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['daily_location', 'daily_location__work_day', 'seller']

    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        daily_location_id = request.data.get('daily_location')
        operations_data = request.data.get('operations', [])

        if not daily_location_id:
            return Response({"detail": "daily_location is required."}, status=status.HTTP_400_BAD_REQUEST)

        daily_location = get_object_or_404(DailyLocation, id=daily_location_id)
        saved_seller_ids = []

        for op in operations_data:
            seller_id = op.get('seller')
            amount = op.get('amount')
            notes = op.get('notes', '')

            if not seller_id or amount is None:
                continue

            seller = get_object_or_404(Employee, id=seller_id, role='seller')

            # Update or create
            operation, created = SellerDailyOperation.objects.update_or_create(
                daily_location=daily_location,
                seller=seller,
                defaults={
                    'amount': amount,
                    'notes': notes
                }
            )
            saved_seller_ids.append(seller.id)

        # Delete operations that are not in the list anymore for this specific location
        SellerDailyOperation.objects.filter(daily_location=daily_location).exclude(seller_id__in=saved_seller_ids).delete()

        DailyOperationsService.log_action(
            daily_location.work_day, "Seller Earnings Bulk Saved", request.user,
            {"count": len(saved_seller_ids), "location": daily_location.location.name}
        )

        updated_ops = SellerDailyOperation.objects.filter(daily_location=daily_location)
        serializer = self.get_serializer(updated_ops, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
