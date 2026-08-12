from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializes user data for the /me/ endpoint and login response."""

    class Meta:
        model = User
        fields = (
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'role',
            'date_joined',
        )
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    """Validates login credentials."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            username=attrs['username'],
            password=attrs['password'],
        )
        if not user:
            raise serializers.ValidationError('Invalid credentials.')
        if not user.is_active:
            raise serializers.ValidationError('User account is disabled.')
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """Validates employee password changes."""

    current_password = serializers.CharField(write_only=True, required=False)
    old_password = serializers.CharField(write_only=True, required=False)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True, required=False)

    def validate(self, attrs):
        user = self.context['request'].user
        curr_pwd = attrs.get('current_password') or attrs.get('old_password')
        
        if not curr_pwd:
            raise serializers.ValidationError({'detail': 'Current password is required.'})

        if not user.check_password(curr_pwd):
            raise serializers.ValidationError({'detail': 'Current password is incorrect.'})

        new_pwd = attrs.get('new_password')
        confirm_pwd = attrs.get('confirm_password')

        if confirm_pwd is not None and new_pwd != confirm_pwd:
            raise serializers.ValidationError({'detail': 'Passwords do not match.'})

        if curr_pwd == new_pwd:
            raise serializers.ValidationError({'detail': 'The new password must be different from the current password.'})

        from django.contrib.auth.password_validation import validate_password, ValidationError as DjangoValidationError
        try:
            validate_password(new_pwd, user)
        except DjangoValidationError as e:
            raise serializers.ValidationError({'detail': ' '.join(e.messages)})

        return attrs
