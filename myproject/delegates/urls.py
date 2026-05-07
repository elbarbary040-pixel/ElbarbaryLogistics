from django.urls import path

from . import views

app_name = "delegates"

urlpatterns = [
    path("", views.delegate_list, name="list"),
    path("add/", views.delegate_add, name="add"),
    path("<int:delegate_id>/edit/", views.delegate_edit, name="edit"),
    path("<int:delegate_id>/delete/", views.delegate_soft_delete, name="delete"),
    path("<int:delegate_id>/", views.delegate_detail, name="detail"),
]

