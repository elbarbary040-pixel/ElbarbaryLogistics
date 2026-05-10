from django.urls import path

from . import views

app_name = "merchants"

urlpatterns = [
    path("", views.merchant_list, name="list"),
    path("add/", views.merchant_add, name="add"),
    path("external/", views.external_merchant_list, name="external_list"),
    path("external/add/", views.external_merchant_add, name="external_add"),
    path("external/<int:merchant_id>/", views.external_merchant_detail, name="external_detail"),
    path("<int:merchant_id>/edit/", views.merchant_edit, name="edit"),
    path("<int:merchant_id>/delete/", views.merchant_soft_delete, name="delete"),
    path("<int:merchant_id>/", views.merchant_detail, name="detail"),
]

