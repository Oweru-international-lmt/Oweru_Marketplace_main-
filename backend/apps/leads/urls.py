from django.urls import path
from . import views

urlpatterns = [
    path("", views.LeadCollectionView.as_view()),
    path("customers/", views.CustomersView.as_view()),
    path("metrics/", views.MetricsView.as_view()),
    path("<uuid:pk>/", views.LeadDetailView.as_view()),
    path("<uuid:pk>/transition/", views.LeadTransitionView.as_view()),
    path("<uuid:pk>/notes/", views.LeadNoteView.as_view()),
    path("<uuid:pk>/follow-up/", views.LeadFollowUpView.as_view()),
]
