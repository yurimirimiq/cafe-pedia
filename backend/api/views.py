from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(['GET'])
def hello(request):
    """프론트엔드와 백엔드 연결 확인용 API"""
    return Response({'message': '안녕하세요, 카페피디아 API예요'})
