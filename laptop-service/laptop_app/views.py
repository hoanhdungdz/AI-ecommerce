from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Laptop
from .serializers import LaptopSerializer


class LaptopViewSet(viewsets.ModelViewSet):
    queryset = Laptop.objects.all()
    serializer_class = LaptopSerializer

    @action(detail=True, methods=['post'])
    def deduct_stock(self, request, pk=None):
        laptop = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        if laptop.quantity < quantity:
            return Response({'error': f'Không đủ hàng. Hiện còn {laptop.quantity}'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        laptop.quantity = F('quantity') - quantity
        laptop.save()
        laptop.refresh_from_db()
        
        return Response({
            'message': 'Trừ kho thành công',
            'new_quantity': laptop.quantity
        })

    @action(detail=True, methods=['post'])
    def return_stock(self, request, pk=None):
        laptop = self.get_object()
        quantity = int(request.data.get('quantity', 0))
        
        if quantity <= 0:
            return Response({'error': 'Số lượng phải lớn hơn 0'}, status=status.HTTP_400_BAD_REQUEST)
            
        from django.db.models import F
        laptop.quantity = F('quantity') + quantity
        laptop.save()
        laptop.refresh_from_db()
        
        return Response({
            'message': 'Hoàn kho thành công',
            'new_quantity': laptop.quantity
        })

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '')
        if query:
            laptops = Laptop.objects.filter(
                Q(name__icontains=query) | Q(brand__icontains=query)
            )
        else:
            laptops = Laptop.objects.all()
        serializer = self.get_serializer(laptops, many=True)
        return Response(serializer.data)
