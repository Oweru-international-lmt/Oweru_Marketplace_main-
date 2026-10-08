from django.urls import path
from .full_check_api import (
    QuoteView, FullCheckCollectionView, FullCheckDetailView, InstructionsView,
    ProofView, ReceiptView, OwnerConsentView, ExternalOwnerConsentView, OwnerContactView,
    VerifierView, StartView, ResultView, RefreshView, ReportView, EligibleProfessionalsView, PaymentDocumentView,
)

urlpatterns = [
    path("quote/", QuoteView.as_view()),
    path("", FullCheckCollectionView.as_view()),
    path("consent/<uuid:delivery_id>/", ExternalOwnerConsentView.as_view()),
    path("<uuid:job_id>/", FullCheckDetailView.as_view()),
    path("<uuid:job_id>/instructions/", InstructionsView.as_view()),
    path("<uuid:job_id>/proof/", ProofView.as_view()),
    path("<uuid:job_id>/payment-documents/<uuid:document_id>/", PaymentDocumentView.as_view()),
    path("<uuid:job_id>/payment-confirm/", ReceiptView.as_view()),
    path("<uuid:job_id>/owner-consent/", OwnerConsentView.as_view()),
    path("<uuid:job_id>/owner-contact/", OwnerContactView.as_view()),
    path("<uuid:job_id>/verifier/", VerifierView.as_view()),
    path("<uuid:job_id>/start/", StartView.as_view()),
    path("<uuid:job_id>/result/", ResultView.as_view()),
    path("<uuid:job_id>/refresh/", RefreshView.as_view()),
    path("<uuid:job_id>/professionals/", EligibleProfessionalsView.as_view()),
    path("<uuid:job_id>/reports/<uuid:report_id>/", ReportView.as_view()),
]
