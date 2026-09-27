from rest_framework.response import Response
from rest_framework import status


def api_response(data=None, message="", status_code=status.HTTP_200_OK, errors=None, meta=None):
    """Standard response envelope per API_CONTRACT.md."""
    return Response(
        {
            "status": "success" if status_code < 400 else "error",
            "data": data or {},
            "message": message,
            "errors": errors,
            "meta": meta or {},
        },
        status=status_code,
    )