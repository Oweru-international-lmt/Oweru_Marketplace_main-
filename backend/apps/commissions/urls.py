from django.urls import path
from .views import RateTableView, RateTableDetailView, PublishView, RateTableVersionsView
urlpatterns = [path("rate-tables/", RateTableView.as_view()), path("rate-tables/versions/", RateTableVersionsView.as_view()), path("rate-tables/<uuid:pk>/", RateTableDetailView.as_view()), path("rate-tables/<uuid:pk>/publish/", PublishView.as_view())]
