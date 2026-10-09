from django.urls import path
from .api import IntakeView, PublicStatusView, DeskView

urlpatterns = [path("", IntakeView.as_view()), path("<uuid:complaint_id>/status/", PublicStatusView.as_view()), path("<uuid:complaint_id>/final-review/", PublicStatusView.as_view(), {"action": "final-review"}), path("<uuid:complaint_id>/response/", PublicStatusView.as_view(), {"action": "response"})]
management_urlpatterns = [path("", DeskView.as_view()), path("<uuid:complaint_id>/", DeskView.as_view()), path("<uuid:complaint_id>/evidence/<uuid:evidence_id>/", DeskView.as_view()), path("<uuid:complaint_id>/<str:action>/", DeskView.as_view())]
