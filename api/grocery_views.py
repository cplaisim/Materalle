import json

from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status

from sage.parser import parse_document
from sage.models import GroceryItem, Document
from .response import api_response


class GroceryUploadView(APIView):
    """
    Upload a document (receipt image, PDF, CSV, or text file) and
    automatically extract and categorize grocery items.

    POST /api/v1/grocery/upload/
    Content-Type: multipart/form-data
    Body: file=<upload>
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return api_response(
                message="No file provided. Send a file in the 'file' field.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        # Save document record
        doc = Document.objects.create(
            title=uploaded.name,
            file=uploaded,
            uploaded_by=request.user,
            file_type=uploaded.name.rsplit(".", 1)[-1].lower(),
            file_size=uploaded.size,
        )

        # Parse and categorize (sync — works in both WSGI and ASGI)
        uploaded.seek(0)
        try:
            categorized = parse_document(uploaded, uploaded.name)
        except Exception as e:
            doc.analysis = json.dumps({"error": str(e), "processed": False})
            doc.save()
            return api_response(
                message=f"Failed to parse document: {e}",
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        # Deduplicate against existing items
        existing = set(
            GroceryItem.objects.filter(added_by=request.user)
            .values_list("name", flat=True)
        )
        existing_lower = {n.lower() for n in existing}

        conflicts = categorized.pop("CONFLICTS", [])

        created = []
        items_by_category = {}
        for raw_cat, items in categorized.items():
            cat = raw_cat.upper().rstrip("S")
            if cat not in dict(GroceryItem.CATEGORIES):
                cat = "OTHER"
            if cat not in items_by_category:
                items_by_category[cat] = []

            for item_name in items:
                name = item_name.strip().title()
                if not name or name.lower() in existing_lower:
                    continue
                existing_lower.add(name.lower())
                created.append(GroceryItem(name=name, category=cat, added_by=request.user))
                items_by_category[cat].append(name)

        if created:
            GroceryItem.objects.bulk_create(created)

        doc.analysis = json.dumps({
            "categories": items_by_category,
            "total_items": len(created),
            "processed": True,
        })
        doc.save()

        return api_response(
            data={
                "document_id": doc.id,
                "file_name": doc.title,
                "categories": items_by_category,
                "items_created": len(created),
                "conflicts": [c for c in conflicts if c["name"].lower() not in existing_lower],
            },
            message=f"Parsed {len(created)} grocery item(s) from {doc.title}.",
            status_code=status.HTTP_201_CREATED,
        )


class GroceryListView(APIView):
    """GET /api/v1/grocery/ — list all grocery items for the current user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = GroceryItem.objects.filter(added_by=request.user).order_by("category", "name")
        data = {}
        for item in items:
            if item.category not in data:
                data[item.category] = []
            data[item.category].append({"id": item.id, "name": item.name})
        return api_response(data=data)
