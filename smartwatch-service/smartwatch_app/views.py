from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Smartwatch
from .serializers import SmartwatchSerializer


class SmartwatchViewSet(viewsets.ModelViewSet):
    queryset = Smartwatch.objects.all()
    serializer_class = SmartwatchSerializer

    @action(detail=True, methods=['post'])
    def deduct_stock(self, request, pk=None):
        smartwatch = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        if smartwatch.quantity < quantity:
            return Response({'error': f'Không đủ hàng. Hiện còn {smartwatch.quantity}'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        smartwatch.quantity = F('quantity') - quantity
        smartwatch.save()
        smartwatch.refresh_from_db()
        
        return Response({
            'message': 'Trừ kho thành công',
            'new_quantity': smartwatch.quantity
        })

    @action(detail=True, methods=['post'])
    def return_stock(self, request, pk=None):
        smartwatch = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        smartwatch.quantity = F('quantity') + quantity
        smartwatch.save()
        smartwatch.refresh_from_db()
        
        return Response({
            'message': 'Hoàn kho thành công',
            'new_quantity': smartwatch.quantity
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            smartwatches = Smartwatch.objects.filter(
                Q(name__icontains=query) | Q(brand__icontains=query)
            )
        else:
            smartwatches = Smartwatch.objects.all()
        serializer = self.get_serializer(smartwatches, many=True)
        return Response(serializer.data)
