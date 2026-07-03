# Security Architecture

## Overview
OmniModal is built with enterprise-grade security from day one.

## Authentication
- API keys (JWT‑backed) with rotation
- OAuth2 / SSO integration (Google, Okta)

## Authorization (RBAC)
Roles: Admin, Developer, Viewer, Billing
Each role has granular permissions (see config/rbac_policies.json)

## Data Privacy
- PII redaction (customizable via regex + ML)
- Data residency: route to region‑specific providers
- Encryption at rest (AES‑256) for cached media
- Encrypted secrets via Vault / AWS Secrets Manager

## Auditing
- Immutable audit logs sent to AWS CloudTrail / Elasticsearch
- Every request logs: user, timestamp, modality, cost, provider, redaction applied

## Compliance
- GDPR, HIPAA (with BAA support)
- SOC2 Type II ready

## Security Headers
- HSTS, CSP, X‑Frame‑Options enforced by middleware
