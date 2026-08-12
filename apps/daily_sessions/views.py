from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from .models import Location, WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation
from .serializers import (
    LocationSerializer,
    WorkDaySerializer, WorkDayListSerializer,
    DailyTeamSerializer, DailyEmployeePerformanceSerializer,
    DailyOperationLogSerializer, SellerDailyOperationSerializer
)
from .services import DailyOperationsService
from apps.employees.models import Employee
from apps.statistics.services import StatisticsService


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

    @action(detail=False, methods=['get'], url_path='resolve')
    def resolve(self, request):
        location_id = request.query_params.get('location')
        date = request.query_params.get('date')
        if not location_id or not date:
            raise ValidationError("Both 'location' and 'date' parameters are required.")

        try:
            work_day = WorkDay.objects.prefetch_related(
                'teams', 'seller_operations', 'teams__performances',
                'teams__photographer', 'teams__clown', 'seller_operations__seller'
            ).get(location_id=location_id, date=date)
            serializer = WorkDaySerializer(work_day, context={'request': request})
            data = serializer.data
            data['is_virtual'] = False
            return Response(data)
        except WorkDay.DoesNotExist:
            location = get_object_or_404(Location, id=location_id)
            virtual = {
                'id': None,
                'location': LocationSerializer(location).data,
                'date': date,
                'status': 'empty',
                'photographer_unit_price': '45.00',
                'clown_unit_price': '50.00',
                'dynamic_pricing_enabled': False,
                'low_photo_threshold': 40,
                'high_photo_threshold': 80,
                'low_photographer_price': '40.00',
                'low_clown_price': '45.00',
                'high_photographer_price': '50.00',
                'high_clown_price': '55.00',
                'low_tier_active': True,
                'normal_tier_active': True,
                'high_tier_active': True,
                'is_manually_overridden': False,
                'override_photographer_price': None,
                'override_clown_price': None,
                'pricing': {
                    'dynamic_enabled': False,
                    'is_manually_overridden': False,
                    'tier': 'normal',
                    'total_photos': 0,
                    'low_tier_active': True,
                    'normal_tier_active': True,
                    'high_tier_active': True,
                    'photographer': {
                        'normal': 45.0, 'low': 40.0, 'high': 50.0, 'override': None, 'current': 45.0
                    },
                    'clown': {
                        'normal': 50.0, 'low': 45.0, 'high': 55.0, 'override': None, 'current': 50.0
                    },
                    'thresholds': {'low': 40, 'high': 80}
                },
                'notes': None,
                'teams': [],
                'seller_operations': [],
                'is_virtual': True,
                'created_by': None,
                'created_by_name': None,
                'created_at': None,
                'updated_at': None,
                'closed_at': None,
            }
            return Response(virtual)

    @action(detail=False, methods=['get'], url_path='calendar')
    def calendar(self, request):
        location_id = request.query_params.get('location')
        year = request.query_params.get('year')
        month = request.query_params.get('month')
        if not location_id or not year or not month:
            raise ValidationError("'location', 'year', and 'month' parameters are required.")

        work_days = WorkDay.objects.filter(
            location_id=location_id,
            date__year=int(year),
            date__month=int(month)
        ).values('date', 'status')

        days_map = {str(wd['date']): wd['status'] for wd in work_days}
        return Response({'days': days_map})

    @action(detail=False, methods=['post'], url_path='bulk-save')
    @transaction.atomic
    def bulk_save(self, request):
        data = request.data
        location_id = data.get('location_id')
        date = data.get('date')
        if not location_id or not date:
            raise ValidationError({"detail": "location_id and date are required."})

        location = get_object_or_404(Location, id=location_id)

        defaults = {
            'photographer_unit_price': data.get('photographer_unit_price', 45),
            'clown_unit_price': data.get('clown_unit_price', 50),
            'dynamic_pricing_enabled': data.get('dynamic_pricing_enabled', False),
            'low_photo_threshold': data.get('low_photo_threshold', 40),
            'high_photo_threshold': data.get('high_photo_threshold', 80),
            'low_photographer_price': data.get('low_photographer_price', 40),
            'low_clown_price': data.get('low_clown_price', 45),
            'high_photographer_price': data.get('high_photographer_price', 50),
            'high_clown_price': data.get('high_clown_price', 55),
            'low_tier_active': data.get('low_tier_active', True),
            'normal_tier_active': data.get('normal_tier_active', True),
            'high_tier_active': data.get('high_tier_active', True),
            'is_manually_overridden': data.get('is_manually_overridden', False),
            'override_photographer_price': data.get('override_photographer_price'),
            'override_clown_price': data.get('override_clown_price'),
            'notes': data.get('notes', ''),
            'status': data.get('status', WorkDay.Status.DRAFT),
            'created_by': request.user,
        }

        work_day, created = WorkDay.objects.get_or_create(
            location=location,
            date=date,
            defaults=defaults
        )
        if not created:
            for field in [
                'photographer_unit_price', 'clown_unit_price',
                'dynamic_pricing_enabled', 'low_photo_threshold', 'high_photo_threshold',
                'low_photographer_price', 'low_clown_price',
                'high_photographer_price', 'high_clown_price',
                'low_tier_active', 'normal_tier_active', 'high_tier_active',
                'is_manually_overridden', 'override_photographer_price', 'override_clown_price',
                'notes', 'status'
            ]:
                if field in data:
                    setattr(work_day, field, data[field])
            work_day.save()

        # Update existing teams photo count
        teams_data = data.get('teams', [])
        for t_data in teams_data:
            team_id = t_data.get('id')
            photo_count = int(t_data.get('team_photo_count', 0))
            if team_id:
                team = DailyTeam.objects.filter(id=team_id, work_day=work_day).first()
                if team:
                    team.team_photo_count = photo_count
                    if 'team_name' in t_data:
                        team.team_name = t_data['team_name']
                    team.save(update_fields=['team_photo_count', 'updated_at'] + (['team_name'] if 'team_name' in t_data else []))
                    # Update auto performances
                    for perf in team.performances.all():
                        if perf.adjustment_type == DailyEmployeePerformance.AdjustmentType.AUTOMATIC:
                            perf.photo_count = photo_count
                            perf.save(update_fields=['photo_count', 'updated_at'])

        # Update seller operations
        sellers_data = data.get('seller_operations', [])
        saved_seller_ids = []
        for s_data in sellers_data:
            seller_id = s_data.get('seller')
            amount = s_data.get('amount', 0)
            notes = s_data.get('notes', '')
            if seller_id and amount is not None:
                seller = get_object_or_404(Employee, id=seller_id, role='seller')
                op, _ = SellerDailyOperation.objects.update_or_create(
                    work_day=work_day,
                    seller=seller,
                    defaults={'amount': amount, 'notes': notes}
                )
                saved_seller_ids.append(str(seller.id))

        if 'seller_operations' in data:
            SellerDailyOperation.objects.filter(
                work_day=work_day
            ).exclude(seller_id__in=saved_seller_ids).delete()

        DailyOperationsService.log_action(
            work_day,
            "Work Day Bulk Saved",
            request.user,
            {"created": created, "location": location.name, "date": str(date)}
        )
        StatisticsService.clear_cache()

        work_day = WorkDay.objects.prefetch_related(
            'teams', 'teams__performances', 'teams__photographer', 'teams__clown',
            'seller_operations', 'seller_operations__seller', 'performances',
            'performances__employee',
        ).get(pk=work_day.pk)

        serializer = WorkDaySerializer(work_day, context={'request': request})
        res = dict(serializer.data)
        res['is_virtual'] = False
        summary = DailyOperationsService.generate_daily_summary(work_day)
        return Response({'work_day': res, 'summary': summary})

    @action(detail=True, methods=['get'])
    def summary(self, request, pk=None):
        work_day = self.get_object()
        summary_data = DailyOperationsService.generate_daily_summary(work_day)
        return Response(summary_data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        return self.summary(request, pk)

    @action(detail=True, methods=['get'])
    def teams(self, request, pk=None):
        work_day = self.get_object()
        serializer = DailyTeamSerializer(work_day.teams.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def sellers(self, request, pk=None):
        work_day = self.get_object()
        serializer = SellerDailyOperationSerializer(work_day.seller_operations.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def logs(self, request, pk=None):
        work_day = self.get_object()
        serializer = DailyOperationLogSerializer(work_day.audit_logs.all(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def performances(self, request, pk=None):
        work_day = self.get_object()
        serializer = DailyEmployeePerformanceSerializer(work_day.performances.all(), many=True)
        return Response(serializer.data)


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
    queryset = DailyTeam.objects.select_related('photographer', 'clown', 'work_day', 'work_day__location').all()
    serializer_class = DailyTeamSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            qs = qs.filter(work_day__location_id=location_id)
        work_day_id = self.request.query_params.get('work_day')
        if work_day_id and location_id:
            work_day = get_object_or_404(WorkDay, id=work_day_id)
            if str(work_day.location_id) != str(location_id):
                raise ValidationError("work_day does not belong to the specified location.")
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        team = DailyTeam.objects.select_related(
            'photographer', 'clown', 'work_day', 'work_day__location'
        ).prefetch_related('performances').get(pk=serializer.instance.pk)
        headers = self.get_success_headers(serializer.data)
        return Response(self.get_serializer(team).data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_create(self, serializer):
        team = serializer.save()
        work_day = team.work_day

        DailyEmployeePerformance.objects.update_or_create(
            work_day=work_day,
            employee=team.photographer,
            defaults={
                'team': team,
                'photo_count': team.team_photo_count,
                'adjustment_type': DailyEmployeePerformance.AdjustmentType.AUTOMATIC,
            }
        )
        DailyEmployeePerformance.objects.update_or_create(
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
        # Sync automatic performances when team_photo_count is updated
        if 'team_photo_count' in serializer.validated_data:
            new_count = team.team_photo_count
            for perf in team.performances.all():
                if perf.adjustment_type == DailyEmployeePerformance.AdjustmentType.AUTOMATIC:
                    perf.photo_count = new_count
                    perf.save(update_fields=['photo_count', 'updated_at'])
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
        'employee', 'work_day', 'work_day__location', 'team'
    ).all()
    serializer_class = DailyEmployeePerformanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day', 'team', 'employee']

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            qs = qs.filter(work_day__location_id=location_id)
        work_day_id = self.request.query_params.get('work_day')
        if work_day_id and location_id:
            work_day = get_object_or_404(WorkDay, id=work_day_id)
            if str(work_day.location_id) != str(location_id):
                raise ValidationError("work_day does not belong to the specified location.")
        return qs

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
    queryset = DailyOperationLog.objects.select_related('work_day', 'work_day__location', 'user').all()
    serializer_class = DailyOperationLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day']

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            qs = qs.filter(work_day__location_id=location_id)
        return qs


class SellerDailyOperationViewSet(viewsets.ModelViewSet):
    queryset = SellerDailyOperation.objects.select_related(
        'seller', 'work_day', 'work_day__location'
    ).all()
    serializer_class = SellerDailyOperationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['work_day', 'seller']

    def get_queryset(self):
        qs = super().get_queryset()
        location_id = self.request.query_params.get('location')
        if location_id:
            qs = qs.filter(work_day__location_id=location_id)
        work_day_id = self.request.query_params.get('work_day')
        if work_day_id and location_id:
            work_day = get_object_or_404(WorkDay, id=work_day_id)
            if str(work_day.location_id) != str(location_id):
                raise ValidationError("work_day does not belong to the specified location.")
        return qs

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
