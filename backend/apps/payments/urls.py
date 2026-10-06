from django.urls import path
from . import views

urlpatterns = [
    path("bank-account/", views.BankView.as_view()),
    path("confirmation-requests/", views.ConfirmationRequestView.as_view()),
    path("confirmations/<uuid:pk>/", views.DecisionView.as_view()),
    path("deals/<uuid:pk>/instructions/", views.InstructionsView.as_view()),
    path("deals/<uuid:pk>/proofs/", views.ProofView.as_view()),
    path("deals/<uuid:pk>/confirm/<str:transfer>/", views.ReceiptView.as_view()),
    path("deals/<uuid:pk>/tax-receipt/", views.TaxReceiptView.as_view()),
]
deal_urlpatterns = [
    path("", views.DealListView.as_view()),
    path("<uuid:pk>/", views.DealDetailView.as_view()),
    path("<uuid:pk>/agreement/<str:action>/", views.AgreementView.as_view()),
    path("<uuid:pk>/complete/", views.CompleteView.as_view()),
    path("<uuid:pk>/final-price/", views.RepriceView.as_view()),
    path("<uuid:pk>/documents/<str:media_id>/", views.DocumentAccessView.as_view()),
]
payout_urlpatterns = [path("", views.PayoutListView.as_view()), path("deals/<uuid:pk>/history/", views.PayoutHistoryView.as_view()), path("deals/<uuid:pk>/<str:action>/", views.PayoutActionView.as_view())]
management_urlpatterns = [path("outbox/", views.OutboxView.as_view()), path("outbox/<uuid:pk>/sent/", views.SentView.as_view()), path("notices/", views.NoticesView.as_view()), path("notices/<uuid:pk>/sent/", views.NoticeSentView.as_view()), path("banks/<uuid:pk>/", views.ManagementBankView.as_view()), path("oweru-bank/", views.OweruBankView.as_view())]
