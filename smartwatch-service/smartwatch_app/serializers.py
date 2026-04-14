from rest_framework import serializers
from .models import Smartwatch


class SmartwatchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Smartwatch
        fields = '__all__'
