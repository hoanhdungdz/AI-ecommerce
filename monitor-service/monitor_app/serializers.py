from rest_framework import serializers
from .models import monitor


class monitorSerializer(serializers.ModelSerializer):
    class Meta:
        model = monitor
        fields = '__all__'

