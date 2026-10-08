import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize, management
from apps.listings.models import Listing
from apps.payments.documents import save_document, validate_document
from apps.payments.idempotency import execute, Conflict, fingerprint
from apps.payments.models import BankAccount, ConfirmationDelivery, OwnerContact
from apps.payments.services import working_deadline
from apps.properties.models import PropertyRecord
from apps.properties.services import generate_property_id
from apps.lister_identity.services import add_calendar_months

from .configuration import setting
from .conflicts import has_property_conflict
from .models import (
    VerificationJob, VerificationTask, VerificationResult, VerificationNotice,
    FullCheckProof, FullCheckReceipt, OwnerConsent, JobHistory,
)
from .task_services import lock_job, require_responsible_verifier, transition, private_write_scope, require_work


def quote():
    fee = setting("full_check_fee")
    if fee is None:
        raise ValidationError("Management must configure the Director-approved Full Check fee before ordering.")
    payload = {"fee": str(Decimal(str(fee))), "scope": setting("full_check_scope")}
    return {**payload, "currency": "TZS", "quote": signing.dumps(payload, salt="oweru.full-check-quote")}


def check_quote(token):
    try:
        value = signing.loads(token, salt="oweru.full-check-quote", max_age=3600)
    except signing.BadSignature as exc:
        raise ValidationError("A valid current fee/scope quote is required before ordering.") from exc
    current = quote()
    if value != {"fee": current["fee"], "scope": current["scope"]}:
        raise Conflict("Full Check fee or scope changed; review the new quote.")
    return value


def subject_snapshot(property_record):
    return {
        "property_id": property_record.property_id, "category": property_record.category,
        "title_type": property_record.title_type, "stated_size": str(property_record.stated_size),
        "size_unit": property_record.size_unit, "locality_id": str(property_record.locality_id),
        "geometry_digest": fingerprint({"pin": property_record.pin.ewkt, "boundary": property_record.boundary.ewkt if property_record.boundary else None}),
    }


def require_buyer(actor, job=None, permission="verification.order"):
    actor = authorize(actor, permission)
    if not actor.has_role("buyer") or job is not None and job.buyer_id != actor.pk:
        raise PermissionDenied("Only the paying Buyer may perform this action.")
    return actor


def audit(actor, action, instance, after=None, request=None):
    create_audit_log(actor=actor, action=action, entity_type=type(instance).__name__, entity_id=instance.pk, before={}, after=after or {}, request=request)


def order_full_check(*, actor, quote_token, key, listing_id=None, outside=None, owner_user=None, owner_name="", owner_phone="", request=None):
    actor = require_buyer(actor)
    if bool(listing_id) == bool(outside):
        raise ValidationError("Choose exactly one listed or outside property.")
    try:
        offered = signing.loads(quote_token, salt="oweru.full-check-quote")
    except signing.BadSignature as exc:
        raise ValidationError("A signed fee/scope quote is required.") from exc
    payload = {"quote": offered, "listing_id": listing_id, "outside": outside, "owner_user": str(getattr(owner_user, "pk", owner_user) or ""), "owner_name": owner_name, "owner_phone": owner_phone}

    def mutate(buyer):
        check_quote(quote_token)
        listing = None
        if listing_id:
            listing = Listing.objects.select_for_update().select_related("property", "lister").filter(listing_id=listing_id, status__in=["ACTIVE", "UNDER_OFFER"]).first()
            if listing is None:
                raise NotFound("An available public listing is required.")
            property_record = PropertyRecord.objects.select_for_update().get(pk=listing.property_id)
            if listing.lister_kind == "OWNER":
                owner = listing.lister
                name, phone = owner.full_name, owner.phone
            else:
                owner = None
                contact = OwnerContact.objects.filter(listing=listing).first()
                name, phone = (contact.name, contact.whatsapp) if contact else ("", "")
        else:
            from apps.properties.serializers import PropertyRecordCreateSerializer
            serializer = PropertyRecordCreateSerializer(data=outside)
            serializer.is_valid(raise_exception=True)
            from apps.properties.services import resolve_property_locality, _audit_property_created, _run_duplicate_detection
            values = dict(serializer.validated_data)
            values["locality"] = resolve_property_locality(actor=buyer, region=values["region"], district=values["district"], ward=values["ward"], locality=values.pop("locality", None), locality_name=values.pop("locality_name", None), locality_kind=values.pop("locality_kind", None))
            property_record = PropertyRecord(property_id=generate_property_id(), created_by=buyer, **values)
            try:
                property_record.full_clean()
            except DjangoValidationError as exc:
                raise ValidationError(exc.message_dict) from exc
            if not 29 <= property_record.pin.x <= 41 or not -12 <= property_record.pin.y <= -0.9:
                raise ValidationError("Outside property must be located in Tanzania.")
            property_record.save()
            _audit_property_created(actor=buyer, property_record=property_record, request=request)
            _run_duplicate_detection(property_record, request=request)
            owner = User.objects.filter(pk=getattr(owner_user, "pk", owner_user), is_active=True, account_category="public").first() if owner_user else None
            if owner_user and (owner is None or not owner.has_role("owner")):
                raise ValidationError("Outside property consent account must be an active Owner.")
            name, phone = (owner.full_name, owner.phone) if owner else (owner_name.strip(), owner_phone.strip())
            if not name or not phone:
                raise ValidationError("Outside property owner contact is required.")
        if listing and listing.lister_kind == "AGENT" and phone and phone == listing.lister.phone:
            raise ValidationError("Owner and Agent WhatsApp numbers must differ.")
        if VerificationJob.objects.filter(buyer=buyer, property=property_record, status__in=["AWAITING_PAYMENT", "AWAITING_CONSENT", "IN_PROGRESS", "UNDER_REVIEW"]).exists():
            raise Conflict("This Buyer already has an unfinished Full Check for the property.")
        job = VerificationJob.objects.create(property=property_record, listing=listing, buyer=buyer, kind="FULL" if listing else "OUTSIDE_FULL", fee=Decimal(offered["fee"]), scope_snapshot={"scope": offered["scope"]}, subject_snapshot=subject_snapshot(property_record), owner_user=owner, owner_name=name, owner_phone=phone)
        JobHistory.objects.create(job=job, actor=buyer, status=job.status)
        VerificationNotice.objects.get_or_create(job=job, recipient=buyer, purpose="FULL_CHECK_ORDERED", defaults={"channels": ["screen", "email"]})
        audit(buyer, "full_check.ordered", job, {"property_id": property_record.property_id, "fee": str(job.fee)}, request)
        return {"job_id": str(job.pk), "status": job.status, "fee": str(job.fee), "payment_reference": str(job.payment_reference)}

    return execute(actor_scope=actor.pk, operation="full_check.order", resource=actor.pk, key=key, payload=payload, lock=lambda: User.objects.select_for_update().get(pk=actor.pk), authorize=lambda buyer: require_buyer(buyer), mutation=mutate)


@transaction.atomic
def payment_instructions(*, actor, job_id, request=None):
    job = lock_job(job_id)
    actor = require_buyer(actor, job, "payment.submit_proof")
    if job.status != "AWAITING_PAYMENT":
        raise ValidationError("This order is no longer awaiting payment.")
    bank = BankAccount.objects.filter(is_oweru=True).first()
    if bank is None:
        raise ValidationError("Oweru's receiving bank account must be configured.")
    audit(actor, "sensitive_data.accessed", job, {"purpose": "full_check_payment_instructions"}, request)
    return {"amount": str(job.fee), "currency": "TZS", "reference": str(job.payment_reference), "bank": {name: getattr(bank, name) for name in ["bank_name", "account_name", "account_number", "branch"]}}


def submit_payment_proof(*, actor, job_id, upload, key, request=None):
    _, mime, digest = validate_document(upload)
    def mutate(job):
        if job.status != "AWAITING_PAYMENT":
            raise ValidationError("Payment proof is accepted only before receipt confirmation.")
        proof = FullCheckProof.objects.filter(job=job, digest=digest).first()
        if proof is None:
            media = save_document(actor=actor, owner=job, upload=upload)
            proof = FullCheckProof.objects.create(job=job, media=media, buyer=actor, digest=digest)
            audit(actor, "full_check.payment_proof_submitted", proof, {"job_id": str(job.pk)}, request)
        return {"proof_id": str(proof.pk), "media_id": proof.media.media_id}
    return execute(actor_scope=actor.pk, operation="full_check.proof", resource=job_id, key=key, payload={"digest": digest, "mime": mime}, lock=lambda: lock_job(job_id), authorize=lambda job: require_buyer(actor, job, "payment.submit_proof"), mutation=mutate)


def _queue_owner_consent(job, actor, request=None):
    if not job.owner_phone:
        job.contact_due_at = working_deadline(timezone.now(), int(setting("owner_contact_working_days")))
        job.save()
        VerificationNotice.objects.get_or_create(job=job, recipient=job.listing.lister, purpose="OWNER_CONTACT_REQUIRED", defaults={"channels": ["screen", "email"]})
        return
    job.consent_due_at = timezone.now() + timedelta(days=float(setting("owner_consent_days")))
    job.save()
    if job.owner_user_id:
        VerificationNotice.objects.get_or_create(job=job, recipient=job.owner_user, purpose="FULL_CHECK_CONSENT", defaults={"channels": ["screen"]})
    else:
        raw = secrets.token_urlsafe(32)
        delivery = ConfirmationDelivery.objects.create(purpose="FULL_CHECK_CONSENT", listing=job.listing, recipient=job.owner_phone, token_digest=hashlib.sha256(raw.encode()).hexdigest(), delivery_token=raw, context={"job_id": str(job.pk), "property_id": job.property.property_id, "owner_name": job.owner_name, "scope": job.scope_snapshot}, expires_at=job.consent_due_at)
        audit(actor, "full_check.consent_queued", delivery, {"job_id": str(job.pk)}, request)


def confirm_full_check_payment(*, actor, job_id, amount, reference, bank_reference, tax_receipt_number, tax_receipt, key, request=None):
    _, _, digest = validate_document(tax_receipt)
    if not bank_reference.strip() or not tax_receipt_number.strip():
        raise ValidationError("Bank reference and official tax receipt number/copy are required.")
    def policy(job):
        authorized = authorize(actor, "payment.confirm")
        if not management(authorized):
            raise PermissionDenied("Management must confirm Oweru's bank receipt.")
    def mutate(job):
        if str(reference) != str(job.payment_reference):
            raise ValidationError("Payment reference must match the frozen order.")
        existing = FullCheckReceipt.objects.filter(job=job).first()
        if existing:
            if existing.amount != Decimal(str(amount)) or existing.bank_reference != bank_reference.strip() or existing.tax_receipt_number != tax_receipt_number.strip() or existing.tax_receipt.file_hash != digest:
                raise Conflict("Full Check already has a different receipt.")
            return {"receipt_id": str(existing.pk), "status": job.status}
        if job.status != "AWAITING_PAYMENT" or Decimal(str(amount)) != job.fee or str(reference) != str(job.payment_reference):
            raise ValidationError("Receipt amount and reference must match the unpaid order.")
        media = save_document(actor=actor, owner=job, upload=tax_receipt)
        receipt = FullCheckReceipt.objects.create(job=job, actor=actor, amount=job.fee, bank_reference=bank_reference.strip(), tax_receipt_number=tax_receipt_number.strip(), tax_receipt=media)
        transition(job, "AWAITING_CONSENT", actor, request=request)
        _queue_owner_consent(job, actor, request)
        audit(actor, "full_check.payment_confirmed", job, {"amount": str(job.fee), "receipt_id": str(receipt.pk)}, request)
        return {"receipt_id": str(receipt.pk), "status": job.status}
    return execute(actor_scope=actor.pk, operation="full_check.payment_confirm", resource=job_id, key=key, payload={"amount": str(amount), "reference": str(reference), "bank_reference": bank_reference.strip(), "tax_number": tax_receipt_number.strip(), "digest": digest}, lock=lambda: lock_job(job_id), authorize=policy, mutation=mutate)


@transaction.atomic
def supply_owner_contact(*, actor, job_id, owner_name, owner_phone, request=None):
    job = lock_job(job_id)
    actor = authorize(actor, "listing.update")
    if job.listing_id is None or job.listing.lister_kind != "AGENT" or job.listing.lister_id != actor.pk:
        raise PermissionDenied("Only this listing's Agent may supply the missing owner contact.")
    if job.status != "AWAITING_CONSENT" or job.owner_phone or not job.contact_due_at or job.contact_due_at <= timezone.now():
        raise ValidationError("Contact may only be supplied during the missing-contact deadline.")
    if not owner_name.strip() or not owner_phone.strip() or owner_phone.strip() == actor.phone:
        raise ValidationError("A named owner and a distinct owner WhatsApp number are required.")
    job.owner_name, job.owner_phone = owner_name.strip(), owner_phone.strip()
    job.save()
    _queue_owner_consent(job, actor, request)
    audit(actor, "full_check.owner_contact_supplied", job, request=request)
    return {"job_id": str(job.pk), "status": job.status}


def _record_consent(job, decision, actor=None, delivery=None, request=None):
    if job.status != "AWAITING_CONSENT" or not hasattr(job, "payment_receipt") or not job.consent_due_at or job.consent_due_at <= timezone.now():
        raise ValidationError("Valid paid owner consent must be received within the reply deadline.")
    if decision not in {"CONFIRM", "DECLINE"}:
        raise ValidationError("Confirm or Decline is required.")
    consent = OwnerConsent.objects.create(job=job, actor=actor, delivery=delivery, decision=decision, recipient_phone=job.owner_phone, context={"property_id": job.property.property_id, "owner_name": job.owner_name, "scope": job.scope_snapshot}, ip_address=request.META.get("REMOTE_ADDR") if request else None, device=request.META.get("HTTP_USER_AGENT", "")[:2000] if request else "")
    if decision == "DECLINE":
        transition(job, "NOT_COMPLETED", actor, "Owner declined consent", request)
        VerificationNotice.objects.get_or_create(job=job, recipient=job.buyer, purpose="FULL_CHECK_NOT_COMPLETED", defaults={"channels": ["screen", "email", "outbox"]})
    else:
        transition(job, "IN_PROGRESS", actor, request=request)
    audit(actor, "full_check.owner_consent", consent, {"decision": decision, "job_id": str(job.pk)}, request)
    return {"consent_id": str(consent.pk), "status": job.status}


@transaction.atomic
def owner_consent(*, actor, job_id, decision, request=None):
    job = lock_job(job_id)
    actor = User.objects.filter(pk=actor.pk, is_active=True).first()
    if actor is None or job.owner_user_id != actor.pk or actor.phone != job.owner_phone:
        raise PermissionDenied("Only the actual Owner account may consent; Agents cannot act for the Owner.")
    return _record_consent(job, decision, actor=actor, request=request)


def external_owner_consent(*, delivery_id, token, decision, key, request=None):
    from apps.payments.confirmations import check_token
    delivery = ConfirmationDelivery.objects.filter(pk=delivery_id, purpose="FULL_CHECK_CONSENT").first()
    if delivery is None:
        raise PermissionDenied("This is not a Full Check consent link.")
    job_id = delivery.context["job_id"]
    def lock():
        job = lock_job(job_id)
        row = ConfirmationDelivery.objects.select_for_update().get(pk=delivery_id)
        row.full_check_job = job
        return row
    def policy(row):
        check_token(row, token, allow_consumed=True)
        job = row.full_check_job
        if row.recipient != job.owner_phone or row.context.get("property_id") != job.property.property_id or row.context.get("scope") != job.scope_snapshot:
            raise PermissionDenied("Owner consent context changed.")
    def mutate(row):
        check_token(row, token)
        response = _record_consent(row.full_check_job, decision, delivery=row, request=request)
        row.consumed_at, row.decision, row.delivery_token = timezone.now(), decision, ""
        row.ip_address = request.META.get("REMOTE_ADDR") if request else None
        row.user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000] if request else ""
        row.save()
        return response
    return execute(actor_scope=f"delivery:{delivery_id}", operation="full_check.external_consent", resource=job_id, key=key, payload={"decision": decision}, lock=lock, authorize=policy, mutation=mutate)


@transaction.atomic
def assign_verifier(*, actor, job_id, verifier, request=None):
    job = lock_job(job_id)
    actor = authorize(actor, "verification.record_result")
    if not management(actor):
        raise PermissionDenied("Management assigns the responsible Verifier.")
    target = authorize(verifier, "verification.record_result")
    if not target.has_role("verifier") or has_property_conflict(target, job.property):
        raise PermissionDenied("An active nonconflicted Verifier is required.")
    if job.status in {"PASSED", "PROBLEM_FOUND", "NOT_COMPLETED"}:
        raise ValidationError("Completed verification history cannot be reassigned.")
    job.verifier = target
    job.save()
    audit(actor, "full_check.verifier_assigned", job, {"verifier_id": str(target.pk)}, request)
    return job


@transaction.atomic
def start_tasks(*, actor, job_id, professional_types=(), surveyor_capture=False, request=None):
    job = lock_job(job_id)
    actor = require_responsible_verifier(actor, job, "verification.assign_task")
    require_work(job)
    from apps.professionals.models import ProfessionalProfile
    if len(set(professional_types)) != len(professional_types) or set(professional_types) - set(ProfessionalProfile.Type.values):
        raise ValidationError("Professional tasks must use distinct SRD professional types.")
    if surveyor_capture and "SURVEYOR" not in professional_types:
        raise ValidationError("Surveyor capture requires a Surveyor task.")
    if job.tasks.exists():
        raise Conflict("Tasks already exist; use assignment or correction services.")
    assignee = job.listing.lister if job.listing_id else job.owner_user
    if not surveyor_capture and assignee is None:
        raise ValidationError("Outside properties need an Owner account or Surveyor for site capture.")
    if not surveyor_capture:
        from .task_services import require_task_actor
        require_task_actor(assignee, job, VerificationTask(job=job, kind="SITE_CAPTURE", status="ASSIGNED", assignee=assignee))
        VerificationTask.objects.create(job=job, kind="SITE_CAPTURE", status="ASSIGNED", assignee=assignee)
    # Local-office routing starts after valid site evidence is submitted.
    VerificationTask.objects.create(job=job, kind="LOCAL_OFFICE", status="UNASSIGNED")
    if job.property.title_type == "REGISTERED_TITLE":
        VerificationTask.objects.create(job=job, kind="REGISTRY", status="ASSIGNED", assignee=actor)
    for professional_type in professional_types:
        VerificationTask.objects.create(job=job, kind="PROFESSIONAL", professional_type=professional_type)
    audit(actor, "full_check.tasks_created", job, {"task_count": job.tasks.count()}, request)
    return list(job.tasks.order_by("kind", "professional_type"))


def finalize_full_check(*, actor, job_id, result, risk_assessment, not_checked=(), request=None):
    with private_write_scope(), transaction.atomic():
        job = lock_job(job_id)
        actor = require_responsible_verifier(actor, job)
        if job.status != "UNDER_REVIEW" or job.invalidated_at or result not in {"PASSED", "PROBLEM_FOUND"}:
            raise ValidationError("Only an uninvalidated job under final review may receive a result.")
        if not isinstance(risk_assessment, str) or not risk_assessment.strip() or len(risk_assessment) > 20000:
            raise ValidationError("Verifier risk assessment is required.")
        if not isinstance(not_checked, (list, tuple)) or any(not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in not_checked):
            raise ValidationError("Not-checked items must be bounded plain text.")
        if not hasattr(job, "payment_receipt") or not hasattr(job, "consent") or job.consent.decision != "CONFIRM":
            raise ValidationError("Payment and Owner consent are mandatory.")
        tasks = list(job.tasks.select_for_update().order_by("kind", "id"))
        if not tasks or any(task.required and task.status != "SUBMITTED" for task in tasks):
            raise ValidationError("Every required task must be submitted.")
        kinds = {task.kind for task in tasks}
        if "LOCAL_OFFICE" not in kinds or "SITE_CAPTURE" not in kinds and not any(task.kind == "PROFESSIONAL" and task.professional_type == "SURVEYOR" for task in tasks) or job.property.title_type == "REGISTERED_TITLE" and "REGISTRY" not in kinds:
            raise ValidationError("Mandatory site, local office and applicable Registry checks are missing.")
        basis = []
        adverse_answers = False
        from apps.site_capture.services import require_full_check_capture
        for task in tasks:
            submission = task.submissions.order_by("-version").first()
            if submission is None:
                raise ValidationError("A task status cannot substitute for submitted evidence.")
            if task.kind == "SITE_CAPTURE" or task.professional_type == "SURVEYOR":
                require_full_check_capture(submission.capture, job.property)
            if task.kind == "LOCAL_OFFICE":
                answers = submission.findings
                expected = {"1": "YES", "2": "YES", "3": "NO", "4": "NO", "5": "YES"}
                adverse_answers = any(answers.get(key, {}).get("answer") != answer for key, answer in expected.items())
            basis.append({"task_id": str(task.pk), "submission_id": str(submission.pk), "version": submission.version, "kind": task.kind, "professional_type": task.professional_type, "author_reference": str(submission.author_id), "author_name": submission.author_name, "author_role": submission.author_role, "registration_number": submission.registration_number, "submitted_at": submission.created_at.isoformat(), "findings": submission.findings})
        if result == "PASSED" and adverse_answers:
            raise ValidationError("Adverse local-office answers require Problem found or new corrected evidence; they cannot be silently passed.")
        if result == "PASSED" and VerificationJob.objects.filter(property=job.property, status="PROBLEM_FOUND", invalidated_at__isnull=True).exists():
            raise ValidationError("An unresolved adverse Full Check blocks Oweru Verified. It cannot be silently cleared by a later result.")
        decision = VerificationResult.objects.create(job=job, verifier=actor, result=result, risk_assessment=risk_assessment.strip(), not_checked=list(not_checked), evidence_basis=basis)
        now = timezone.now()
        job.completed_at = now
        job.refresh_limit_at = add_calendar_months(now, int(setting("full_check_refresh_months")))
        job.expires_at = min(now + timedelta(days=float(setting("full_check_reliance_days"))), job.refresh_limit_at) if result == "PASSED" else None
        from .reports import generate_report
        report = generate_report(job=job, result=decision, actor=actor, request=request)
        transition(job, result, actor, request=request)
        if result == "PROBLEM_FOUND":
            for prior in VerificationJob.objects.select_for_update().filter(property=job.property, status="PASSED", invalidated_at__isnull=True):
                prior.invalidated_at, prior.invalidation_reason = now, "Later adverse ownership check"
                prior.save()
                audit(actor, "full_check.invalidated", prior, {"reason": "later_adverse_result"}, request)
        VerificationNotice.objects.get_or_create(job=job, recipient=job.buyer, phone=job.buyer.phone, purpose="FULL_CHECK_REPORT_READY", defaults={"channels": ["screen", "email", "outbox"]})
        audit(actor, "full_check.final_result", decision, {"result": result, "job_id": str(job.pk)}, request)
        audit(actor, "verification.level_recalculated", job.property, {"full_check_result": result}, request)
        return {"job_id": str(job.pk), "status": job.status, "report_id": str(report.pk)}


def refresh_full_check(*, actor, job_id, risk_assessment, request=None):
    with private_write_scope(), transaction.atomic():
        job = lock_job(job_id)
        actor = require_responsible_verifier(actor, job)
        if job.status != "PASSED" or job.invalidated_at or not job.refresh_limit_at or job.refresh_limit_at <= timezone.now() or not isinstance(risk_assessment, str) or not risk_assessment.strip() or len(risk_assessment) > 20000:
            raise ValidationError("Only an unchanged passed check within its refresh ceiling may be refreshed with a new assessment.")
        job.expires_at = min(timezone.now() + timedelta(days=float(setting("full_check_reliance_days"))), job.refresh_limit_at)
        job.save()
        from .reports import generate_report
        report = generate_report(job=job, result=job.result, actor=actor, request=request, refresh_assessment=risk_assessment.strip())
        audit(actor, "full_check.refreshed", job, {"expires_at": job.expires_at.isoformat(), "report_id": str(report.pk)}, request)
        return job
