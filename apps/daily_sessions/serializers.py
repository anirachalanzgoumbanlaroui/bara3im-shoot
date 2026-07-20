from rest_framework import serializers
from .models import WorkDay, DailyTeam, DailyEmployeePerformance, DailyOperationLog, SellerDailyOperation
from .services import DailyOperationsService


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

        if photographer and photographer.role != 'photographer':
            raise serializers.ValidationError({"photographer": "Must have role 'photographer'."})
        if clown and clown.role != 'clown':
            raise serializers.ValidationError({"clown": "Must have role 'clown'."})
            
        return attrs


class WorkDaySerializer(serializers.ModelSerializer):
    teams = DailyTeamSerializer(many=True, read_only=True)
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkDay
        fields = [
            'id', 'date', 'photographer_unit_price', 'clown_unit_price',
            'notes', 'created_by', 'created_by_name',
            'teams', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']

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

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        work_day = super().create(validated_data)
        DailyOperationsService.log_action(work_day, "Work Day Created", self.context['request'].user)
        return work_day


class WorkDayListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for listing work days.
    """
    class Meta:
        model = WorkDay
        fields = [
            'id', 'date', 'photographer_unit_price', 'clown_unit_price',
            'notes', 'created_at', 'updated_at'
        ]


class DailyOperationLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = DailyOperationLog
        fields = ['id', 'work_day', 'action', 'user', 'user_name', 'details', 'created_at']

    def get_user_name(self, obj):
        return obj.user.username if obj.user else "System"


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
