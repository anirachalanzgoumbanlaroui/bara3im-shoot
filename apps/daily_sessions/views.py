from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Location, WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation
from .serializers import (
    LocationSerializer,
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


class WorkDayViewSet(viewsets.ModelViewSet):
    queryset = WorkDay.objects.select_related('location', 'created_by').all()
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action == 'list':
            return WorkDayListSerializer
        return WorkDaySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            qs = qs.filter(location_id=location_id)
        date_from = self.request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(date__gte=date_from)
        date_to = self.request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(date__lte=date_to)
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

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

    @action(detail=True, methods=['post'])
    def close(self, request, pk=None):
        work_day = self.get_object()
        if work_day.status == WorkDay.Status.CLOSED:
            return Response({"detail": "Work day is already closed."}, status=status.HTTP_400_BAD_REQUEST)
        work_day.status = WorkDay.Status.CLOSED
        work_day.closed_at = timezone.now()
        work_day.save(update_fields=['status', 'closed_at', 'updated_at'])
        DailyOperationsService.log_action(
            work_day, "Work Day Closed", request.user,
            {"location": work_day.location.name}
        )
        return Response(self.get_serializer(work_day).data)


class DailyTeamViewSet(viewsets.ModelViewSet):
    queryset = DailyTeam.objects.select_related('photographer', 'clown', 'work_day').all()
    serializer_class = DailyTeamSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']

    def perform_create(self, serializer):
        team = serializer.save()
        work_day = team.work_day

        DailyEmployeePerformance.objects.get_or_create(
            work_day=work_day,
            employee=team.photographer,
            defaults={
                'team': team,
                'photo_count': team.team_photo_count,
                'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
            }
        )
        DailyEmployeePerformance.objects.get_or_create(
            work_day=work_day,
            employee=team.clown,
            defaults={
                'team': team,
                'photo_count': team.team_photo_count,
                'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
            }
        )

        DailyOperationsService.log_action(
            work_day, "Team Created", self.request.user,
            {
                "team_id": str(team.id),
                "team_name": team.team_name,
                "location": work_day.location.name,
            }
        )

    def perform_update(self, serializer):
        team = serializer.save()
        DailyOperationsService.log_action(
            team.work_day, "Team Edited", self.request.user,
            {"team_id": str(team.id), "location": team.work_day.location.name}
        )

    @action(detail=False, methods=['post'], url_path='quick-entry')
    def quick_entry(self, request):
        data = request.data
        if not isinstance(data, list):
            return Response(
                {"detail": "Expected a list of updates."},
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_teams = []
        for item in data:
            team_id = item.get('id')
            new_count = item.get('team_photo_count')
            if team_id and new_count is not None:
                team = get_object_or_404(DailyTeam, id=team_id)
                DailyOperationsService.quick_entry_update_team(team, int(new_count), request.user)
                updated_teams.append(str(team.id))

        return Response({"detail": f"Updated {len(updated_teams)} teams."})


class DailyEmployeePerformanceViewSet(viewsets.ModelViewSet):
    queryset = DailyEmployeePerformance.objects.select_related(
        'employee', 'work_day', 'team'
    ).all()
    serializer_class = DailyEmployeePerformanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day', 'team', 'employee']

    def perform_update(self, serializer):
        perf = serializer.save()
        DailyOperationsService.log_action(
            perf.work_day, "Employee Performance Updated", self.request.user,
            {
                "performance_id": str(perf.id),
                "employee": perf.employee.first_name,
                "type": perf.adjustment_type,
                "location": perf.work_day.location.name,
            }
        )


class DailyOperationLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyOperationLog.objects.select_related('work_day', 'user').all()
    serializer_class = DailyOperationLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']


class SellerDailyOperationViewSet(viewsets.ModelViewSet):
    queryset = SellerDailyOperation.objects.select_related(
        'seller', 'work_day', 'work_day__location'
    ).all()
    serializer_class = SellerDailyOperationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day', 'seller']

    @action(detail=False, methods=['post'], url_path='bulk-save')
    def bulk_save(self, request):
        work_day_id = request.data.get('work_day')
        operations_data = request.data.get('operations', [])

        if not work_day_id:
            return Response(
                {"detail": "work_day is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        work_day = get_object_or_404(WorkDay, id=work_day_id)
        saved_seller_ids = []

        for op in operations_data:
            seller_id = op.get('seller')
            amount = op.get('amount')
            notes = op.get('notes', '')

            if not seller_id or amount is None:
                continue

            seller = get_object_or_404(Employee, id=seller_id, role='seller')

            operation, created = SellerDailyOperation.objects.update_or_create(
                work_day=work_day,
                seller=seller,
                defaults={'amount': amount, 'notes': notes}
            )
            saved_seller_ids.append(str(seller.id))

        SellerDailyOperation.objects.filter(
            work_day=work_day
        ).exclude(seller_id__in=saved_seller_ids).delete()

        DailyOperationsService.log_action(
            work_day, "Seller Earnings Bulk Saved", request.user,
            {"count": len(saved_seller_ids), "location": work_day.location.name}
        )

        updated_ops = SellerDailyOperation.objects.filter(work_day=work_day)
        serializer = self.get_serializer(updated_ops, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
