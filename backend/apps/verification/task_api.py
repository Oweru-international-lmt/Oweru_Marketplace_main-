from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .serializers import StrictInputSerializer
from .models import VerificationTask, TaskSubmission
from .pagination import VerificationReviewPagination
from .access import visible_tasks, require_task_read


class TaskSerializer(serializers.ModelSerializer):
    property_id = serializers.CharField(source="job.property.property_id", read_only=True)
    locality = serializers.CharField(source="job.property.locality.name", read_only=True)
    owner_name = serializers.CharField(source="job.owner_name", read_only=True)
    class Meta:
        model = VerificationTask
        fields = ["id", "kind", "status", "professional_type", "due_at", "property_id", "locality", "owner_name"]
        read_only_fields = fields


class AssignSerializer(StrictInputSerializer):
    profile_id = serializers.UUIDField()


class DecisionSerializer(StrictInputSerializer):
    decision = serializers.ChoiceField(choices=["ACCEPT", "DECLINE"])
    reason = serializers.CharField(max_length=1000, required=False, allow_blank=True)


class SubmissionSerializer(StrictInputSerializer):
    findings = serializers.JSONField()
    device = serializers.CharField(max_length=255)
    report = serializers.FileField(required=False)
    capture_id = serializers.CharField(max_length=20, required=False)
    signed_and_stamped = serializers.BooleanField(required=False)


class CorrectionSerializer(StrictInputSerializer):
    reason = serializers.CharField(max_length=1000)


class TaskCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSerializer
    pagination_class = VerificationReviewPagination
    def get(self, request):
        queryset = visible_tasks(request.user)
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class TaskDetailView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TaskSerializer
    def get(self, request, task_id):
        task = get_object_or_404(VerificationTask.objects.select_related("job__property__locality"), pk=task_id)
        require_task_read(request.user, task)
        from apps.audit.services import create_audit_log
        create_audit_log(actor=request.user, action="sensitive_data.accessed", entity_type="VerificationTask", entity_id=task.pk, before={}, after={"purpose": "verification_workspace"}, request=request)
        data = self.get_serializer(task).data
        if task.kind == "LOCAL_OFFICE":
            from apps.local_officials.full_check import QUESTIONS
            data["questions"] = [q.replace("[owner name]", task.job.owner_name) for q in QUESTIONS]
        data["submissions"] = [{"id": str(s.pk), "version": s.version, "findings": s.findings, "author_name": s.author_name, "registration_number": s.registration_number, "created_at": s.created_at} for s in task.submissions.order_by("version")]
        return Response(data)


class TaskAssignView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AssignSerializer
    def post(self, request, task_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.professionals.services import assign_professional
        task = assign_professional(actor=request.user, task_id=task_id, request=request, **serializer.validated_data)
        return Response(TaskSerializer(task).data)


class TaskDecisionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DecisionSerializer
    def post(self, request, task_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from apps.professionals.services import decide_task
        task = decide_task(actor=request.user, task_id=task_id, request=request, **serializer.validated_data)
        return Response(TaskSerializer(task).data)


class TaskSubmissionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SubmissionSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    def post(self, request, task_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        values = dict(serializer.validated_data)
        capture_id = values.pop("capture_id", None)
        if capture_id:
            from apps.site_capture.models import SiteCapture
            values["capture"] = get_object_or_404(SiteCapture, capture_id=capture_id)
        from .task_services import submit_task
        submission = submit_task(actor=request.user, task_id=task_id, request=request, **values)
        return Response({"submission_id": str(submission.pk), "version": submission.version}, status=201)


class TaskCorrectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CorrectionSerializer
    def post(self, request, task_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .task_services import reopen_task
        task = reopen_task(actor=request.user, task_id=task_id, request=request, **serializer.validated_data)
        return Response(TaskSerializer(task).data)


class TaskRelationshipView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CorrectionSerializer

    def post(self, request, task_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        from .relationships import declare_task_relationship
        row = declare_task_relationship(actor=request.user, task_id=task_id, request=request, **serializer.validated_data)
        return Response({"id": str(row.pk), "property_id": row.property.property_id}, status=201)


class TaskEvidenceView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, submission_id):
        submission = get_object_or_404(TaskSubmission.objects.select_related("task__job__property__locality", "report"), pk=submission_id)
        require_task_read(request.user, submission.task)
        if not submission.report_id:
            return Response({"detail": "This submission has no report."}, status=404)
        from apps.media.storage import get_private_media_storage
        from apps.audit.services import create_audit_log
        create_audit_log(actor=request.user, action="sensitive_data.accessed", entity_type="TaskSubmission", entity_id=submission.pk, before={}, after={"purpose": "task_report"}, request=request)
        return Response({"url": get_private_media_storage().generate_signed_read_url(key=submission.report.file_key)})
