from django.urls import path
from .api import ProfessionalCollectionView, ProfessionalDetailView, ProfessionalSelfView
from apps.verification.task_api import TaskCollectionView

urlpatterns = [path("me/", ProfessionalSelfView.as_view()), path("tasks/", TaskCollectionView.as_view())]
management_urlpatterns = [path("", ProfessionalCollectionView.as_view()), path("<uuid:profile_id>/", ProfessionalDetailView.as_view())]
