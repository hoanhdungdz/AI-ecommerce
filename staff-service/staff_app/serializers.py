from rest_framework import serializers
from .models import Staff


class StaffSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ['id', 'username', 'email', 'full_name', 'role', 'created_at']


class StaffRegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Staff
        fields = ['username', 'password', 'email', 'full_name', 'role']
