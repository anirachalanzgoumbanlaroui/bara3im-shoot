from rest_framework import serializers
from django.utils import timezone
from .models import Location, WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation
from .services import DailyOperationsService


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ['id', 'name', 'icon', 'color_hex', 'created_at']


class DailyEmployeePerformanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_role = serializers.SerializerMethodField()
    daily_earnings = serializers.SerializerMethodField()

    class Meta:
        model = DailyEmployeePerformance
        fields = [
            'id', 'employee', 'employee_name', 'employee_role', 'work_day', 'team',
            'photo_count', 'adjustment_type', 'adjustment_reason', 'daily_earnings',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'daily_earnings', 'created_at', 'updated_at']

    def get_employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"

    def get_employee_role(self, obj):
        return obj.employee.role

    def get_daily_earnings(self, obj):
        return str(DailyOperationsService.calculate_employee_earnings(obj))

    def validate_photo_count(self, value):
        if value < 0:
            raise serializers.ValidationError("Photos count cannot be negative.")
        return value


class DailyTeamSerializer(serializers.ModelSerializer):
    photographer_name = serializers.SerializerMethodField()
    clown_name = serializers.SerializerMethodField()
    performances = DailyEmployeePerformanceSerializer(many=True, read_only=True)

    class Meta:
        model = DailyTeam
        fields = [
            'id', 'work_day', 'photographer', 'photographer_name',
            'clown', 'clown_name', 'team_name', 'team_photo_count',
            'performances', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'performances']

    def get_photographer_name(self, obj):
        return f"{obj.photographer.first_name} {obj.photographer.last_name}"

    def get_clown_name(self, obj):
        return f"{obj.clown.first_name} {obj.clown.last_name}"

    def validate(self, attrs):
        photographer = attrs.get('photographer')
        clown = attrs.get('clown')
        work_day = attrs.get('work_day')

        if photographer and photographer.role != 'photographer':
            raise serializers.ValidationError({"photographer": "Must have role 'photographer'."})
        if clown and clown.role != 'clown':
            raise serializers.ValidationError({"clown": "Must have role 'clown'."})

        if work_day:
            if photographer:
                conflict_photo = DailyTeam.objects.filter(
                    work_day=work_day, photographer=photographer
                )
                if self.instance:
                    conflict_photo = conflict_photo.exclude(pk=self.instance.pk)
                if conflict_photo.exists():
                    raise serializers.ValidationError(
                        {"photographer": f"{photographer.first_name} is already in a team today."}
                    )

            if clown:
                conflict_clown = DailyTeam.objects.filter(
                    work_day=work_day, clown=clown
                )
                if self.instance:
                    conflict_clown = conflict_clown.exclude(pk=self.instance.pk)
                if conflict_clown.exists():
                    raise serializers.ValidationError(
                        {"clown": f"{clown.first_name} is already in a team today."}
                    )

        return attrs


class SellerDailyOperationSerializer(serializers.ModelSerializer):
    seller_name = serializers.SerializerMethodField()

    class Meta:
        model = SellerDailyOperation
        fields = [
            'id', 'seller', 'seller_name', 'work_day',
            'amount', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_seller_name(self, obj):
        return f"{obj.seller.first_name} {obj.seller.last_name}"

    def validate_amount(self, value):
        if value < 0:
            raise serializers.ValidationError("Amount cannot be negative.")
        return value

    def validate(self, attrs):
        seller = attrs.get('seller')
        work_day = attrs.get('work_day')

        if seller and seller.role != 'seller':
            raise serializers.ValidationError({"seller": "Must have role 'seller'."})

        if seller and work_day:
            conflict = SellerDailyOperation.objects.filter(
                work_day=work_day, seller=seller
            )
            if self.instance:
                conflict = conflict.exclude(pk=self.instance.pk)
            if conflict.exists():
                raise serializers.ValidationError(
                    {"seller": f"{seller.first_name} already has an operation today."}
                )

        return attrs


class WorkDaySerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_id = serializers.PrimaryKeyRelatedField(
        queryset=Location.objects.all(), source='location', write_only=True
    )
    teams = DailyTeamSerializer(many=True, read_only=True)
    seller_operations = SellerDailyOperationSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkDay
        fields = [
            'id', 'location', 'location_id', 'date', 'status',
            'photographer_unit_price', 'clown_unit_price',
            'notes', 'created_by', 'created_by_name',
            'teams', 'seller_operations',
            'created_at', 'updated_at', 'closed_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at', 'closed_at']

    def get_created_by_name(self, obj):
        return obj.created_by.username if obj.created_by else None

    def validate_photographer_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def validate_clown_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def to_representation(self, instance):
        if hasattr(instance, '_prefetched_objects_cache'):
            instance._prefetched_objects_cache = {}
        return super().to_representation(instance)

    def create(self, validated_data):
        location = validated_data['location']
        date = validated_data['date']

        existing = WorkDay.objects.filter(location=location, date=date).first()
        if existing:
            return existing

        validated_data['created_by'] = self.context['request'].user
        work_day = super().create(validated_data)

        DailyOperationsService.log_action(
            work_day, "Work Day Created", self.context['request'].user,
            {"location": location.name, "date": str(date)}
        )
        return work_day


class WorkDayListSerializer(serializers.ModelSerializer):
    location_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkDay
        fields = [
            'id', 'location', 'location_name', 'date', 'status',
            'photographer_unit_price', 'clown_unit_price',
            'notes', 'created_at', 'updated_at'
        ]

    def get_location_name(self, obj):
        return obj.location.name if obj.location else None


class DailyOperationLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = DailyOperationLog
        fields = ['id', 'work_day', 'action', 'user', 'user_name', 'details', 'created_at']

    def get_user_name(self, obj):
        return obj.user.username if obj.user else "System"
