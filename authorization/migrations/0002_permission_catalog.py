# Frozen SRD v1.3 policy snapshot. Do not import the runtime catalog here.
"""SRD v1.3 action permissions. A grant NEVER establishes object access.

Historical data migrations carry their own frozen snapshot of this policy.
"""

PUBLIC_ROLES = frozenset({"buyer", "owner", "agent"})
PARTNER_ROLES = frozenset({"local_official", "professional"})
STAFF_ROLES = frozenset({"verifier", "marketer", "management"})
OPERATIONAL_ROLES = PARTNER_ROLES | STAFF_ROLES
ASSIGNABLE_STAFF_ROLES = frozenset({"verifier", "marketer"})

# code: (meaning, source, roles). Object qualifications are retained in meaning.
CATALOG = {
    "account.view": ("View own profile", "ACC-08", "buyer owner agent local_official professional verifier marketer management"),
    "account.update": ("Edit own profile", "ACC-08", "buyer owner agent local_official professional verifier marketer management"),
    "account.request_deletion": ("Request own account deletion", "ACC-08", "buyer owner agent local_official professional verifier marketer management"),
    "account.manage": ("Manage staff and partner accounts", "ACC-06; section 4", "management"),
    "account.suspend": ("Suspend or restore accounts with a reason", "ADM-02", "management"),
    "authorization.view": ("Inspect roles and grants for account administration", "ACC-06; section 4", "management"),
    "authorization.assign_role": ("Assign permitted staff roles", "ACC-06; section 2.2", "management"),
    "authorization.revoke_role": ("Revoke operational roles", "ACC-06", "management"),
    "authorization.manage_outbox": ("Configure optional staff outbox-send grants", "section 4; NTF-02; section 26", "management"),
    "identity.submit": ("Submit own lister identity", "IDV-01", "owner agent"),
    "identity.review": ("Approve or reject lister identities", "IDV-03", "management"),
    "property.search": ("Search public properties; anonymous policy is separate", "SRC-01; section 4", "buyer owner agent management"),
    "listing.view": ("View public listings; anonymous policy is separate", "SRC-03; section 4", "buyer owner agent management"),
    "listing.create": ("Create listings within permitted scope", "LST-02; section 4", "owner agent management"),
    "listing.update": ("Edit own listings; management scope requires domain policy", "section 4; LST-10", "owner agent management"),
    "listing.import": ("Import own listings or on a lister's behalf", "LST-11", "owner agent management"),
    "listing.view_owner_price": ("View owner price within own listing or management scope", "section 4", "owner agent management"),
    "listing.suspend": ("Suspend or restore listing with reason", "ADM-02", "management"),
    "lead.create": ("Enquire about a listing", "section 4; LEAD-01", "buyer owner agent management"),
    "lead.view": ("View own leads; management may view all", "section 4; LEAD-06", "owner agent management"),
    "lead.update": ("Manage own lead stages and notes", "section 4; LEAD-02", "owner agent"),
    "deal.view": ("View own deals; management may view all", "section 4", "owner agent management"),
    "deal.update": ("Manage own deal closing", "section 4; LEAD-03", "owner agent"),
    "verification.order": ("Order a full check", "FUL-01; section 4", "buyer"),
    "verification.complete_task": ("Complete tasks subject to assignment/locality/conflict checks", "section 4; VER-06; LOC-02; PRO-02", "local_official professional verifier"),
    "verification.record_result": ("Record verification results", "section 4; FUL-07", "verifier management"),
    "verification.assign_task": ("Assign professional verification tasks", "FUL-05; PRO-02", "verifier"),
    "partner.manage": ("Register and approve partners through onboarding", "section 4; LOC-01; PRO-01", "management"),
    "commission.view": ("View current commission table", "PAY-02; PAY-01", "owner agent management"),
    "commission.manage": ("Publish commission rate table versions", "PAY-01", "management"),
    "payment.submit_proof": ("Submit own deal/full-check payment proof", "PAY-07; PAY-13", "buyer"),
    "payment.confirm": ("Confirm Oweru receipt", "PAY-09; PAY-13", "management"),
    "payout.record": ("Record agent payout", "PAY-10", "management"),
    "payout.hold": ("Hold payout with a reason", "PAY-12", "management"),
    "complaint.handle": ("Handle verification complaints or management scope; object policy deferred", "section 4; CMP-04", "verifier management"),
    "outbox.send": ("Manually send and mark outbox messages sent", "section 4; NTF-02", "management"),
    "marketing.manage": ("Manage featured listings, banners and bilingual content", "MAR-01; MAR-02; section 4", "marketer management"),
    "marketing.send_campaign": ("Send campaigns only to consenting recipients", "MAR-03; section 4", "marketer management"),
    "analytics.view": ("View non-personal market monitoring data", "MON-01; MON-03; section 4", "marketer management"),
    "analytics.export": ("Export market monitoring views", "MON-02", "marketer management"),
    "settings.manage": ("Edit database settings with change log", "ADM-04", "management"),
    "audit.view": ("View immutable management audit log", "ADM-05; section 24", "management"),
}

DEFAULT_ROLE_PERMISSIONS = {
    role: frozenset(code for code, (_, _, roles) in CATALOG.items() if role in roles.split())
    for role in sorted(PUBLIC_ROLES | OPERATIONAL_ROLES)
}
OPTIONAL_GRANTS = frozenset({("verifier", "outbox.send"), ("marketer", "outbox.send")})

from django.db import migrations


def seed_catalog(apps, schema_editor):
    alias = schema_editor.connection.alias
    Permission = apps.get_model("authorization", "Permission")
    Role = apps.get_model("authorization", "Role")
    Grant = apps.get_model("authorization", "RolePermission")
    Audit = apps.get_model("audit", "AuditEvent")
    allowed = {(role, code) for role, codes in DEFAULT_ROLE_PERMISSIONS.items() for code in codes} | set(OPTIONAL_GRANTS)
    existing = set(Grant.objects.using(alias).values_list("role__code", "permission__code"))
    if existing - allowed:
        raise RuntimeError("Existing noncanonical grants require operator review before seeding.")
    for code, (name, source, roles) in sorted(CATALOG.items()):
        permission, _ = Permission.objects.using(alias).get_or_create(code=code, defaults={"name": name, "description": source})
        for role_code in roles.split():
            role = Role.objects.using(alias).get(code=role_code)
            grant, created = Grant.objects.using(alias).get_or_create(role=role, permission=permission)
            if created:
                state = {"role": role_code, "permission": code, "source": "authorization.0002_permission_catalog"}
                Audit.objects.using(alias).create(action="permission.granted", entity_type="RolePermission", entity_id=str(grant.pk), before_state={**state, "granted": False}, after_state={**state, "granted": True})


class Migration(migrations.Migration):
    dependencies = [("authorization", "0001_initial"), ("accounts", "0003_account_category"), ("audit", "0001_initial")]
    operations = [migrations.RunPython(seed_catalog)]