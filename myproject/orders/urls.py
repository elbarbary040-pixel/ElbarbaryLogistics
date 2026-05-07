from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("", views.order_list, name="list"),
    path("add/", views.order_add, name="add"),
    path("api/merchants/", views.merchant_autocomplete, name="api_merchants"),
    path("api/delegates/", views.delegate_autocomplete, name="api_delegates"),
    path("<int:pk>/delete/", views.order_soft_delete, name="delete"),
    path("<int:pk>/edit/", views.order_edit, name="edit"),
    path("<int:pk>/qr.png", views.order_qr_png, name="qr_png"),
    path("import/", views.order_import, name="import"),
    path("bulk/", views.order_bulk, name="bulk"),
    path("export/", views.order_export_excel, name="export"),
    path("print/", views.order_print, name="print"),
    path("qr/", views.order_qr, name="qr"),
    path("scanner/", views.order_scanner, name="scanner"),
    path("lookup/", views.order_lookup_api, name="lookup"),
]
