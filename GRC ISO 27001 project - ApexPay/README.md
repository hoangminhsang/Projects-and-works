# ISO 27001 GRC case study: ApexPay

I built this portfolio project to practise taking a company from "no ISMS" to "ready for a certification audit" under ISO/IEC 27001:2022. The company is ApexPay Solutions Ltd, a fictional UK fintech with 120 staff. It runs on AWS, Microsoft 365 and GitHub, and it processes payments and customer personal data.

The repo has about 80 documents across the eight phases of the job: context and scope, governance, risk, policies, implementation, incident and business cases, internal audit, and corrective action.

> **This is a simulation.** ApexPay, its staff, suppliers, incidents, costs and progress figures are all made up. The internal audit is a mock audit that I wrote myself. Nothing here certifies anything or shows that a real organisation complies with anything.

## What I did

- Scoped the ISMS (the platform, AWS production, corporate IT, all staff, the London office and remote working) and ran a gap assessment against all clauses and Annex A. Average maturity came out at 0.8 out of 5.
- Wrote a 5×5 risk method, built an asset register of 32 assets, drew a data flow diagram and ran STRIDE on it (19 threats). Fed it all into a risk register of 28 risks and a Statement of Applicability for all 93 controls.
- Wrote 12 topic policies and 7 procedures, plus a training plan, a document register and a communication plan.
- Planned a £98k security budget. When the budget was cut to £70k in Case 7, I rebuilt the plan and formally accepted the risk that was left over.
- Worked through 8 cases: account compromise, a personal data breach with a mock ICO notification, ransomware and business continuity, an at-risk supplier, a rushed release that needed a risk exception, a new AI feature that needed a DPIA, the budget cut, and a UK GDPR and regulatory review.
- Ran a mock internal audit (1 major and 6 minor nonconformities), wrote management review minutes, then did root cause analysis and corrective actions and a readiness report.

## Results (simulated)

| Measure | Baseline (Nov 2026) | Jun 2027 |
|---|---|---|
| Critical risks | 7 | 1 (R-08, monitoring) |
| MFA / EDR / training coverage | 80% / 70.8% / 60% | 95% / 85% / 90% |
| Internal audit | n/a | 1 major, 6 minor |
| UK GDPR assessment score | n/a | 48% |
| Certification readiness | n/a | Stage 1 Sep 2027, Stage 2 Nov 2027 |

The single Critical risk left is security monitoring. That is where the budget cut hurt most, and I left it visible on purpose. I did not want to hide it in the numbers.

## Repository layout

| Folder | What's in it |
|---|---|
| `01_Context_and_Scope/` | Organisational context, interested parties, ISMS scope, gap assessment and report |
| `02_Leadership_and_Governance/` | Information security policy, RACI, governance framework, objectives |
| `03_Risk_Management/` | Risk method, asset register, data flow diagram (`.drawio`), STRIDE model, risk register, treatment plan, Statement of Applicability |
| `04_Support/` | `Policies/` (12), `Procedures/` (7), awareness plan, training register, document register, communication plan |
| `05_Implementation_and_Labs/` | Budget, remediation roadmap, control testing register, `Lab_Writeups/`, `Technical_Evidence/` |
| `06_Case_Scenarios/` | One subfolder per case, Case01 to Case08 |
| `07_Performance_and_Audit/` | KPI dashboard, audit programme, checklist, evidence register, audit report, management review minutes |
| `08_Improvement_and_Readiness/` | Root cause analysis, corrective action register, readiness report, risk to control to evidence traceability matrix |

If you only have ten minutes, start with `08_Improvement_and_Readiness/ISO27001_Certification_Readiness_Report.pdf`, then the risk register and the Statement of Applicability in `03_Risk_Management/`.

## Method

- **Standards:** ISO/IEC 27001:2022 including Amendment 1:2024 (climate change), Annex A, a risk approach in the style of ISO/IEC 27005, UK GDPR and the Data Protection Act 2018.
- **Risk scoring:** likelihood × impact on a 5×5 grid. Low is 1 to 4, Medium 5 to 9, High 10 to 16 and Critical 17 to 25. Who can accept a risk depends on its level.
- **IDs:** each document has an ID, a version, an owner and an approval status, so the registers can point at each other (risks R-01 to R-28, threats T-01 to T-19, corrective actions CAR-01 to CAR-09).

## Labs

The write-ups in `05_Implementation_and_Labs/Lab_Writeups/` are step-by-step guides for hands-on labs: MFA on an identity platform, locking down an S3 bucket, Wazuh logging, authorised vulnerability scanning, backup and restore, secret scanning with fake secrets, and offboarding a leaver. The real screenshots and logs from my own runs go in `Technical_Evidence/`, one folder per lab. I keep them apart from the simulated ApexPay records on purpose.

## Limitations

- All organisational data is simulated. Where the brief gave no figure, I marked the value as an assumption.
- I did not invent certificates for real providers like AWS, Microsoft or GitHub. The vendor register only says where to get their reports.
- FCA authorisation status and PCI DSS scope were never given in the brief, so they are marked "to confirm".
- I wrote both the ISMS and the audit, so the audit is not independent. A real one would need a separate auditor.
- I paraphrased requirements and did not copy text from the ISO standards.
