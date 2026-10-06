from celery import shared_task

from .services import expire_property_verifications


@shared_task
def process_document_verification_expiry():
    return expire_property_verifications()
