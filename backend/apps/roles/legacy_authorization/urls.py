from django.urls import path
from . import views

urlpatterns = [
    path("roles/", views.RoleListView.as_view(), name="authorization-roles"),
    path("permissions/", views.PermissionListView.as_view(), name="authorization-permissions"),
    path("roles/<str:role_code>/permissions/", views.RolePermissionListView.as_view(), name="authorization-role-permissions"),
    path("roles/<str:role_code>/outbox-send/", views.OutboxGrantView.as_view(), name="authorization-outbox-grant"),
    path("users/", views.AccountLookupView.as_view(), name="authorization-account-lookup"),
    path("users/<uuid:user_id>/roles/", views.UserRoleListView.as_view(), name="authorization-user-roles"),
    path("users/<uuid:user_id>/roles/assign/", views.AssignRoleView.as_view(), name="authorization-assign"),
    path("users/<uuid:user_id>/roles/revoke/", views.RevokeRoleView.as_view(), name="authorization-revoke"),
]
