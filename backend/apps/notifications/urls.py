from django.urls import path
from .api import InboxView, OutboxView, TemplateView, PaymentSelfServiceView, ContactSelfServiceView

urlpatterns = [path("", InboxView.as_view()), path("<uuid:notification_id>/read/", InboxView.as_view()), path("self-service/deals/<uuid:deal_id>/", PaymentSelfServiceView.as_view())]
urlpatterns += [path("self-service/listings/<str:listing_id>/", ContactSelfServiceView.as_view())]
management_urlpatterns = [path("outbox/", OutboxView.as_view()), path("outbox/<uuid:notification_id>/sent/", OutboxView.as_view()), path("message-templates/", TemplateView.as_view()), path("message-templates/<str:template_key>/", TemplateView.as_view())]
