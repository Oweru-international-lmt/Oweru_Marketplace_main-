from django.urls import path
from .task_api import TaskCollectionView, TaskDetailView, TaskAssignView, TaskDecisionView, TaskSubmissionView, TaskCorrectionView, TaskEvidenceView, TaskRelationshipView

urlpatterns = [
    path("<uuid:task_id>/declare-relationship/", TaskRelationshipView.as_view()),
    path("", TaskCollectionView.as_view()),
    path("<uuid:task_id>/", TaskDetailView.as_view()),
    path("<uuid:task_id>/assign/", TaskAssignView.as_view()),
    path("<uuid:task_id>/decision/", TaskDecisionView.as_view()),
    path("<uuid:task_id>/submit/", TaskSubmissionView.as_view()),
    path("<uuid:task_id>/correction/", TaskCorrectionView.as_view()),
    path("submissions/<uuid:submission_id>/report/", TaskEvidenceView.as_view()),
]
