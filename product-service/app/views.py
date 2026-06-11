from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status


class HealthView(APIView):
    """Health check endpoint"""
    
    def get(self, request):
        return Response(
            {
                'status': 'healthy',
                'service': 'product-service',
                'message': 'Product service is running',
            },
            status=status.HTTP_200_OK
        )
