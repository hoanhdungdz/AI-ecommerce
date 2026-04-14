from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Accessory
from .serializers import AccessorySerializer


class AccessoryViewSet(viewsets.ModelViewSet):
    queryset = Accessory.objects.all()
    serializer_class = AccessorySerializer

    @action(detail=True, methods=['post'])
    def deduct_stock(self, request, pk=None):
        accessory = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        if accessory.quantity < quantity:
            return Response({'error': f'Không đủ hàng. Hiện còn {accessory.quantity}'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        accessory.quantity = F('quantity') - quantity
        accessory.save()
        accessory.refresh_from_db()
        
        return Response({
            'message': 'Trừ kho thành công',
            'new_quantity': accessory.quantity
        })

    @action(detail=True, methods=['post'])
    def return_stock(self, request, pk=None):
        accessory = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        accessory.quantity = F('quantity') + quantity
        accessory.save()
        accessory.refresh_from_db()
        
        return Response({
            'message': 'Hoàn kho thành công',
            'new_quantity': accessory.quantity
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            accessories = Accessory.objects.filter(
                Q(name__icontains=query) | Q(brand__icontains=query)
            )
        else:
            accessories = Accessory.objects.all()
        serializer = self.get_serializer(accessories, many=True)
        return Response(serializer.data)
