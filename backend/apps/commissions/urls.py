from django.urls import path
from .views import RateTableView, RateTableDetailView, PublishView
urlpatterns = [path("rate-tables/", RateTableView.as_view()), path("rate-tables/<uuid:pk>/", RateTableDetailView.as_view()), path("rate-tables/<uuid:pk>/publish/", PublishView.as_view())]
