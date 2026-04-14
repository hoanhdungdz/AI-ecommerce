from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import monitor
from .serializers import monitorSerializer


class monitorViewSet(viewsets.ModelViewSet):
    queryset = monitor.objects.all()
    serializer_class = monitorSerializer

    @action(detail=True, methods=['post'])
    def deduct_stock(self, request, pk=None):
        monitor = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        if monitor.quantity < quantity:
            return Response({'error': f'Không đủ hàng. Hiện còn {monitor.quantity}'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        monitor.quantity = F('quantity') - quantity
        monitor.save()
        monitor.refresh_from_db()
        
        return Response({
            'message': 'Trừ kho thành công',
            'new_quantity': monitor.quantity
        })

    @action(detail=True, methods=['post'])
    def return_stock(self, request, pk=None):
        monitor = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        monitor.quantity = F('quantity') + quantity
        monitor.save()
        monitor.refresh_from_db()
        
        return Response({
            'message': 'Hoàn kho thành công',
            'new_quantity': monitor.quantity
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            monitors = monitor.objects.filter(
                Q(name__icontains=query) | Q(brand__icontains=query)
            )
        else:
            monitors = monitor.objects.all()
        serializer = self.get_serializer(monitors, many=True)
        return Response(serializer.data)

