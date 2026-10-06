from django.conf import settings
from django.db import models
from apps.common.models import TimeStampedModel


class OwnerContact(TimeStampedModel):
    listing = models.OneToOneField("listings.Listing", on_delete=models.PROTECT, related_name="owner_contact")
    name = models.CharField(max_length=255)
    whatsapp = models.CharField(max_length=30)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_owner_price = models.DecimalField(max_digits=18, decimal_places=0, null=True, blank=True)
    decision = models.CharField(max_length=16, blank=True)


class BankAccount(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="bank_account")
    owner_contact = models.OneToOneField(OwnerContact, on_delete=models.PROTECT, null=True, blank=True, related_name="bank_account")
    is_oweru = models.BooleanField(default=False)
    bank_name = models.CharField(max_length=255)
    account_name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=100)
    branch = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(user__isnull=False, owner_contact__isnull=True, is_oweru=False) | models.Q(user__isnull=True, owner_contact__isnull=False, is_oweru=False) | models.Q(user__isnull=True, owner_contact__isnull=True, is_oweru=True)), name="bank_holder_exclusive"),
            models.UniqueConstraint(fields=["is_oweru"], condition=models.Q(is_oweru=True), name="one_oweru_bank"),
        ]


class ConfirmationDelivery(TimeStampedModel):
    """Minimum staff outbox: never returned to the initiating Agent."""
    purpose = models.CharField(max_length=32)
    listing = models.ForeignKey("listings.Listing", null=True, blank=True, on_delete=models.PROTECT)
    deal = models.ForeignKey("deals.Deal", null=True, blank=True, on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    recipient = models.CharField(max_length=30)
    token_digest = models.CharField(max_length=64)
    delivery_token = models.CharField(max_length=100)
    context = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="financial_confirmations_sent")
    consumed_at = models.DateTimeField(null=True, blank=True)
    decision = models.CharField(max_length=16, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=2000, blank=True)


class PhoneConfirmation(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="marketplace_phone_confirmation")
    phone = models.CharField(max_length=30)
    confirmed_at = models.DateTimeField()


class PaymentProof(TimeStampedModel):
    deal = models.ForeignKey("deals.Deal", on_delete=models.PROTECT, related_name="payment_proofs")
    transfer = models.CharField(max_length=16, choices=[("OWNER", "Owner"), ("OWERU", "Oweru")])
    media = models.ForeignKey("media.Media", on_delete=models.PROTECT)
    digest = models.CharField(max_length=64)
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["deal", "transfer", "digest"], name="proof_content_unique"), models.CheckConstraint(condition=models.Q(transfer__in=["OWNER", "OWERU"]), name="proof_transfer_valid")]


class PaymentConfirmation(TimeStampedModel):
    deal = models.ForeignKey("deals.Deal", on_delete=models.PROTECT, related_name="payment_confirmations")
    transfer = models.CharField(max_length=16)
    amount = models.DecimalField(max_digits=18, decimal_places=0)
    bank_reference = models.CharField(max_length=255)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    delivery = models.OneToOneField(ConfirmationDelivery, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["deal", "transfer"], name="confirmation_transfer_unique"), models.CheckConstraint(condition=models.Q(transfer__in=["OWNER", "OWERU"], amount__gte=0), name="confirmation_context_valid")]


class OfficialTaxReceipt(TimeStampedModel):
    deal = models.OneToOneField("deals.Deal", on_delete=models.PROTECT, related_name="tax_receipt")
    number = models.CharField(max_length=255, unique=True)
    kind = models.CharField(max_length=8, choices=[("EFD", "EFD"), ("VFD", "VFD")])
    media = models.ForeignKey("media.Media", on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class IdempotencyRecord(TimeStampedModel):
    actor_scope = models.CharField(max_length=100)
    operation = models.CharField(max_length=64)
    resource = models.UUIDField()
    key = models.CharField(max_length=128)
    fingerprint = models.CharField(max_length=64)
    result = models.JSONField()
    status_code = models.PositiveSmallIntegerField(default=200)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["actor_scope", "operation", "resource", "key"], name="financial_idempotency_scope")]


class Payout(TimeStampedModel):
    deal = models.OneToOneField("deals.Deal", on_delete=models.PROTECT, related_name="payout")
    agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="agent_payouts")
    amount = models.DecimalField(max_digits=18, decimal_places=0)
    status = models.CharField(max_length=16, default="PENDING")
    due_at = models.DateTimeField(db_index=True)
    hold_reason = models.TextField(blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="recorded_payouts")
    bank_reference = models.CharField(max_length=255, blank=True)
    proof = models.ForeignKey("media.Media", null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(amount__gte=0), name="payout_amount_nonnegative"), models.CheckConstraint(condition=models.Q(status__in=["PENDING", "DUE", "PAID", "ON_HOLD"]), name="payout_status_valid")]


class PayoutBlock(TimeStampedModel):
    """M20 writes this policy boundary through set_complaint_block, not raw ORM."""
    deal = models.ForeignKey("deals.Deal", on_delete=models.PROTECT, related_name="payout_blocks")
    external_reference = models.CharField(max_length=255)
    is_open = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["deal", "external_reference"], name="complaint_block_unique")]


class FinancialNotice(TimeStampedModel):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=32)
    lead = models.ForeignKey("leads.Lead", on_delete=models.PROTECT, null=True, blank=True)
    deal = models.ForeignKey("deals.Deal", on_delete=models.PROTECT, null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="sent_financial_notices")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["recipient", "purpose", "lead"], condition=models.Q(lead__isnull=False), name="notice_lead_unique"),
            models.UniqueConstraint(fields=["recipient", "purpose", "deal"], condition=models.Q(deal__isnull=False), name="notice_deal_unique"),
        ]
