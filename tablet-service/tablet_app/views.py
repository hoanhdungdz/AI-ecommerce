from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Tablet
from .serializers import TabletSerializer


class TabletViewSet(viewsets.ModelViewSet):
    queryset = Tablet.objects.all()
    serializer_class = TabletSerializer

    @action(detail=True, methods=['post'])
    def deduct_stock(self, request, pk=None):
        tablet = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        if tablet.quantity < quantity:
            return Response({'error': f'Không đủ hàng. Hiện còn {tablet.quantity}'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        tablet.quantity = F('quantity') - quantity
        tablet.save()
        tablet.refresh_from_db()
        
        return Response({
            'message': 'Trừ kho thành công',
            'new_quantity': tablet.quantity
        })

    @action(detail=True, methods=['post'])
    def return_stock(self, request, pk=None):
        tablet = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        tablet.quantity = F('quantity') + quantity
        tablet.save()
        tablet.refresh_from_db()
        
        return Response({
            'message': 'Hoàn kho thành công',
            'new_quantity': tablet.quantity
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            tablets = Tablet.objects.filter(
                Q(name__icontains=query) | Q(brand__icontains=query)
            )
        else:
            tablets = Tablet.objects.all()
        serializer = self.get_serializer(tablets, many=True)
        return Response(serializer.data)
