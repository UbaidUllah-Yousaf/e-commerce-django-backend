from rest_framework.pagination import CursorPagination


class ApiCursorPagination(CursorPagination):
    """
    Cursor-based list pagination (Stable ordering: newest first, ``id`` tie-break).
    Use ``?cursor=…`` for next/previous and optional ``?page_size=…`` (max 100).
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    cursor_query_param = "cursor"
    ordering = ("-created_at", "-id")
