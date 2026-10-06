from .models import FinancialNotice


def queue_notice(*, recipient, purpose, lead=None, deal=None):
    """Transactional manual-delivery intent, not automatic WhatsApp dispatch."""
    return FinancialNotice.objects.get_or_create(recipient=recipient, purpose=purpose, lead=lead, deal=deal)[0]
