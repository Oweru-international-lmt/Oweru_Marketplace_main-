from django.urls import path
from .api import SubmitView, ReportView

urlpatterns = [path("", SubmitView.as_view()), path("<uuid:check_id>/", ReportView.as_view()), path("<uuid:check_id>/pdf/", ReportView.as_view(), {"pdf": True})]
