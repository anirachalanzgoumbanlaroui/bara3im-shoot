from rest_framework import serializers
from .models import Employee
from apps.users.models import User
import re

class EmployeeSerializer(serializers.ModelSerializer):
    """
    Serializer for the Employee model.
    Handles data validation and transformation for the API.
    """
    username = serializers.CharField(write_only=True, required=False)
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Employee
        fields = [
            'id', 'user', 'employee_code', 'first_name', 'last_name',
            'phone_number', 'address', 'date_of_birth', 'hiring_date',
            'role', 'status', 'avatar', 'notes',
            'fingerprint_registered', 'fingerprint_template_id', 'fingerprint_registered_at',
            'face_registered', 'face_registered_at', 'face_last_updated',
            'created_at', 'updated_at',
            'username', 'password'
        ]
        read_only_fields = [
            'id', 'user', 'employee_code', 'fingerprint_registered',
            'fingerprint_template_id', 'fingerprint_registered_at',
            'face_registered', 'face_registered_at', 'face_last_updated',
            'created_at', 'updated_at'
        ]

    def validate_phone_number(self, value):
        """
        Validate phone number format.
        Assuming Algerian phone numbers for this project or general international format.
        """
        if not re.match(r'^\+?1?\d{8,15}$', value):
            raise serializers.ValidationError("Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.")
        return value

    def validate_user(self, value):
        """
        Ensure user isn't already linked to another employee (handled by OneToOne naturally,
        but good for explicit error message).
        """
        if self.instance is None and Employee.objects.filter(user=value).exists():
            raise serializers.ValidationError("This user is already linked to an employee profile.")
        return value

    def create(self, validated_data):
        username = validated_data.pop('username', None)
        password = validated_data.pop('password', None)
        
        if not username or not password:
            raise serializers.ValidationError({"detail": "Username and password are required to create an employee."})
            
        if User.objects.filter(username=username).exists():
            raise serializers.ValidationError({"username": "A user with this username already exists."})
            
        role = validated_data.get('role', User.Role.PHOTOGRAPHER)
        
        # Create user
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', ''),
            phone_number=validated_data.get('phone_number', ''),
            role=role
        )
        
        employee = Employee.objects.create(user=user, **validated_data)
        return employee

    def update(self, instance, validated_data):
        # Remove username/password if passed
        validated_data.pop('username', None)
        validated_data.pop('password', None)
        
        # Update linked User fields if they are changed
        user = instance.user
        
        if 'first_name' in validated_data:
            user.first_name = validated_data['first_name']
        if 'last_name' in validated_data:
            user.last_name = validated_data['last_name']
        if 'phone_number' in validated_data:
            user.phone_number = validated_data['phone_number']
        if 'role' in validated_data:
            user.role = validated_data['role']
            
        user.save()
        
        # Update Employee fields
        employee = super().update(instance, validated_data)
        return employee

class EmployeeListSerializer(serializers.ModelSerializer):
    """
    Simplified serializer for listing employees to optimize performance.
    """
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_code', 'first_name', 'last_name',
            'role', 'status', 'avatar', 'phone_number', 'hiring_date', 'fingerprint_registered', 'face_registered'
        ]
