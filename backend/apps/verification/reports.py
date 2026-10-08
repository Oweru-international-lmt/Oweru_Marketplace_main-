from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from apps.payments.documents import save_document
from apps.audit.services import create_audit_log
from .models import VerificationReport


def build_pdf(*, job, result, language, refresh_assessment=""):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    stream = BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=45, leftMargin=45, topMargin=45, bottomMargin=45)
    sw = language == "sw"
    story = []
    def paragraph(text, style="BodyText"):
        story.append(Paragraph(escape(str(text)), styles[style]))
        story.append(Spacer(1, 5))
    paragraph("Ripoti ya ukaguzi kamili wa Oweru" if sw else "Oweru Full Check Report", "Title")
    paragraph(f"{'Kumbukumbu' if sw else 'Reference'}: {job.pk}")
    paragraph(f"{'Tarehe' if sw else 'Date'}: {timezone.localtime(job.completed_at or timezone.now()).date()}")
    paragraph(f"{'Mali' if sw else 'Property'}: {job.property.property_id} | {job.property.locality.name}")
    paragraph(f"{'Matokeo' if sw else 'Result'}: { {'PASSED': 'Imepita', 'PROBLEM_FOUND': 'Tatizo limepatikana', 'NOT_COMPLETED': 'Haijakamilika'}.get(result.result, result.result) if sw else result.get_result_display() }")
    paragraph(f"{'Wigo' if sw else 'Scope'}: {job.scope_snapshot['scope']}")
    paragraph(f"{'Tathmini ya hatari' if sw else 'Risk assessment'}: {refresh_assessment or result.risk_assessment}")
    paragraph(f"{'Uhalali hadi' if sw else 'Valid until'}: {timezone.localtime(job.expires_at).date() if job.expires_at else ('Haitumiki' if sw else 'Not applicable')}")
    paragraph(f"{'Mhakiki' if sw else 'Verifier reference'}: {result.verifier_id}")
    if job.property.title_type != "REGISTERED_TITLE":
        paragraph("Hakuna hati iliyosajiliwa. Kumbukumbu za ofisi ya eneo zinatoa ulinzi mdogo kuliko hati." if sw else "No registered title. Local office records give less protection than a title.")
    paragraph("Ramani na picha za satelaiti hazithibitishi umiliki." if sw else "Maps and imagery do not prove ownership.")
    paragraph("Mambo ambayo hayakukaguliwa" if sw else "What was not checked", "Heading2")
    for item in result.not_checked:
        paragraph(item)
    paragraph("Msingi wa ushahidi" if sw else "Evidence basis", "Heading2")
    for item in result.evidence_basis:
        from apps.professionals.models import ProfessionalProfile
        names = {"LOCAL_OFFICE": "Ofisi ya eneo" if sw else "Local office", "REGISTRY": "Utafutaji wa Land Registry" if sw else "Land Registry search", "SITE_CAPTURE": "Upimaji wa eneo" if sw else "Site capture", "PROFESSIONAL": "Mtaalamu" if sw else "Professional"}
        title = names[item["kind"]]
        if item.get("professional_type"):
            title += f" - {ProfessionalProfile.Type(item['professional_type']).label}"
        paragraph(title, "Heading3")
        author = f"{'Kumbukumbu ya mhakiki' if sw else 'Verifier reference'}: {item.get('author_reference', result.verifier_id)}" if item["author_role"] == "verifier" else item["author_name"]
        timestamp = timezone.localtime(datetime.fromisoformat(item["submitted_at"])).strftime("%Y-%m-%d %H:%M")
        attribution = f"{author} | {timestamp} | {'Toleo' if sw else 'Version'} {item['version']}"
        if item["registration_number"]:
            attribution += f" | {'Usajili' if sw else 'Registration'}: {item['registration_number']}"
        paragraph(attribution)
        labels = {"layout": "Mpangilio" if sw else "Layout", "development_restrictions": "Masharti ya uendelezaji" if sw else "Development restrictions", "planning_context": "Mazingira ya mipango" if sw else "Planning context", "permitted_use": "Matumizi yanayoruhusiwa" if sw else "Permitted use", "planned_roads_or_reserves": "Barabara au maeneo yaliyotengwa" if sw else "Planned roads or reserves", "supporting_extracts": "Nyaraka zinazounga mkono" if sw else "Supporting extracts", "beacon_photos": "Picha za alama za mipaka" if sw else "Beacon photographs", "overlap_notes": "Maelezo ya mwingiliano" if sw else "Overlap notes", "search_result": "Matokeo ya utafutaji" if sw else "Search result", "reference": "Kumbukumbu" if sw else "Reference", "measured_area_sqm": "Eneo lililopimwa (m²)" if sw else "Measured area (m²)", "review_flags": "Mambo ya kuzingatia" if sw else "Review observations"}
        observations = {"SATELLITE_CHECK_UNAVAILABLE": "Ukaguzi wa satelaiti haupatikani" if sw else "Satellite check unavailable", "AREA_DIFFERENCE": "Tofauti ya eneo inahitaji mapitio" if sw else "Area difference requires review", "AREA_COMPARISON_UNAVAILABLE": "Ulinganisho wa eneo haupatikani" if sw else "Area comparison unavailable", "BOUNDARY_INTERSECTION_REVIEW": "Mwingiliano wa mipaka unahitaji mapitio" if sw else "Boundary overlap requires review", "MEDIA_LOCATION_MISSING": "Mahali pa picha/video hapajulikani" if sw else "Media location missing", "MEDIA_LOCATION_DISTANT": "Picha/video iko mbali na eneo" if sw else "Media location distant from plot", "MEDIA_DATE_OLD": "Picha/video ni ya zamani" if sw else "Media date is older than the configured limit"}
        for key, value in item["findings"].items():
            if isinstance(value, dict):
                paragraph(f"{value.get('question', key).replace('[owner name]', job.owner_name)}: {value.get('answer', '')}. {value.get('comment', '')}")
            else:
                if isinstance(value, list):
                    value = "; ".join(observations.get(flag, flag) for flag in value) or ("Hakuna" if sw else "None")
                paragraph(f"{labels.get(key, key)}: {value}")
    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawString(45, 24, "Oweru Marketplace | " + ("Ripoti ya mnunuzi" if sw else "Private buyer report"))
        canvas.drawRightString(A4[0] - 45, 24, f"{'Ukurasa' if sw else 'Page'} {document.page}")
        canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def generate_report(*, job, result, actor, request=None, refresh_assessment=""):
    version = job.reports.count() + 1
    language = job.buyer.preferred_language
    content = build_pdf(job=job, result=result, language=language, refresh_assessment=refresh_assessment)
    upload = SimpleUploadedFile("full-check-report.pdf", content, content_type="application/pdf")
    media = save_document(actor=actor, owner=job, upload=upload)
    report = VerificationReport.objects.create(job=job, result=result, media=media, language=language, version=version, assessment_snapshot=refresh_assessment or result.risk_assessment)
    create_audit_log(actor=actor, action="full_check.report_generated", entity_type="VerificationReport", entity_id=report.pk, before={}, after={"job_id": str(job.pk), "version": version}, request=request)
    return report
