from celery import shared_task

from .services import expire_property_verifications


@shared_task
def process_document_verification_expiry():
    return expire_property_verifications()


@shared_task
def process_full_check_deadlines():
    from .deadlines import process_deadlines
    return process_deadlines()


@shared_task
def recalculate_verification_levels():
    from .levels import recalculate_levels
    return recalculate_levels()
