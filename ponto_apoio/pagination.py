"""Paginação das listas exibidas na interface."""


def paginate(items, requested_page, per_page=20):
    total = len(items)
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(requested_page or 1, pages))
    return items[(page - 1) * per_page:page * per_page], total, page, pages
