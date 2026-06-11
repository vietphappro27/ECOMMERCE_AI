from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'id'

    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        category = self.get_object()
        products = category.products.all()
        serializer = ProductSerializer(products, many=True)
        return Response({'count': products.count(), 'data': serializer.data})


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'

    def get_queryset(self):
        queryset = Product.objects.select_related('category').all()

        category_filter = self.request.query_params.get('category')
        if category_filter:
            by_name = Q(category__name__iexact=category_filter)
            if str(category_filter).isdigit():
                queryset = queryset.filter(by_name | Q(category_id=int(category_filter)))
            else:
                queryset = queryset.filter(by_name)

        search_query = self.request.query_params.get('search') or self.request.query_params.get('q')
        if search_query:
            queryset = queryset.filter(name__icontains=search_query)

        return queryset.order_by('-id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        limit = int(request.query_params.get('limit', 100))
        offset = int(request.query_params.get('offset', 0))

        total_count = queryset.count()
        paginated = queryset[offset : offset + limit]

        serializer = self.get_serializer(paginated, many=True)
        return Response({
            'count': total_count,
            'limit': limit,
            'offset': offset,
            'data': serializer.data,
        })

    @action(detail=False, methods=['get'])
    def by_category(self, request):
        categories = Category.objects.prefetch_related('products')
        result = []
        for cat in categories:
            products = cat.products.all()
            serializer = ProductSerializer(products, many=True)
            result.append({
                'category': CategorySerializer(cat).data,
                'products': serializer.data,
            })
        return Response(result)

    @action(detail=False, methods=['get'])
    def search(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'error': 'q parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        products = self.get_queryset().filter(name__icontains=query)[:20]

        serializer = self.get_serializer(products, many=True)
        return Response({'count': products.count(), 'data': serializer.data})
