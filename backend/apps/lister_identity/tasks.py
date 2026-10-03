from celery import shared_task

from .services import expire_lister_identities


@shared_task
def process_lister_identity_expiry():
    return expire_lister_identities()
