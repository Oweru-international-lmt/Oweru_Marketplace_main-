# Oweru Marketplace documents

Requirement documents for this repository. Read these before changing behaviour.

| File | What it is |
|---|---|
| `Oweru-Marketplace-SRD-v1.3.docx` | Software Requirements Document. The source of truth for business rules, requirement IDs (ACC-01, LST-04, ...) and acceptance tests. |
| `Oweru_Marketplace_Backend_Development_Guide-v1.1.docx` | How the SRD maps onto the Django backend: phases, models, endpoints, milestones M01 to M17. |

When the SRD and the guide disagree, the SRD wins.

## Version history

- **SRD 1.3 / Guide 1.1 (2 October 2026):** sign-in and password reset use email address instead of phone number. Every account must have an email; email and phone number are each unique. Changed: SRD 2.2, ACC-01, ACC-02, ACC-03, ACC-05, new ACC-T2, 14.1, 15, 25, 26. Implemented in `backend/accounts` (migration `0002_email_sign_in`) and the `frontend/` auth pages.
- **SRD 1.2 (29 September 2026):** previous version, phone number sign-in.

## Reading the .docx files as text

```bash
pandoc backend/doc/Oweru-Marketplace-SRD-v1.3.docx -t markdown
```
