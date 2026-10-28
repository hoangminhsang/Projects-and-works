# SOC Writeups

## About this collection

This folder is my growing collection of Security Operations Centre (SOC) investigation writeups and analysis reports. I will add new reports over time as I work through practical labs, training exercises, and security investigations.

My aim is to document how I approach an investigation: understand the initial alert, examine the evidence, connect relevant events, assess the findings, and explain an appropriate response. Each writeup is also a record of what I learn and how my analytical and reporting skills develop.

The collection is organised into three categories: **Malware analysis**, **Phishing analysis**, and **Web attack**. The topics below describe what reports may cover as the collection grows; they are not a list of completed investigations.

## Categories

### Malware analysis

Reports in this category examine suspicious files, scripts, and endpoint activity to understand their behaviour and identify useful detection and response opportunities.

Writeups may include:

- Initial file triage, including file type, hashes, metadata, and suspicious strings.
- Static analysis of executables, documents, or scripts.
- Behavioural analysis in an isolated lab, including process activity, file changes, persistence mechanisms, and network connections.
- Examination of endpoint alerts, process trees, event logs, and other supporting evidence.
- Indicators of compromise (IOCs), such as file hashes, domains, IP addresses, and file paths.
- Relevant MITRE ATT&CK techniques where supported by the evidence.
- Detection ideas, containment recommendations, remediation steps, and lessons learned.

### Phishing analysis

Reports in this category investigate suspicious emails and related content to assess their legitimacy, understand the attacker's objective, and explain the evidence behind the verdict.

Writeups may include:

- Email context, sender impersonation, and social engineering techniques.
- Header analysis, including routing information, sender and reply-to differences, and SPF, DKIM, and DMARC results.
- Examination of URLs, domains, redirects, attachments, and landing pages.
- Identification of credential harvesting, malicious attachments, or other suspicious behaviour.
- Correlation with available email, endpoint, or network logs.
- Extracted IOCs, evidence screenshots, and an explanation of the final classification.
- Recommended actions, such as blocking indicators, removing related messages, or investigating affected accounts.

### Web attack

Reports in this category investigate suspicious activity targeting websites, web applications, and web servers, with an emphasis on recognising attack patterns and assessing their impact.

Writeups may include:

- Analysis of web access logs, application logs, WAF alerts, and network traffic.
- Investigation of SQL injection, cross-site scripting (XSS), directory traversal, command injection, and malicious file upload attempts.
- Identification of scanning, enumeration, brute-force attempts, and suspicious authentication activity.
- Examination of request methods, URLs, parameters, response codes, user agents, and source IP addresses.
- Reconstruction of an attack timeline and correlation across relevant log sources.
- Assessment of whether the evidence shows an attempted attack or a successful compromise.
- Detection queries, monitoring improvements, response recommendations, and lessons learned.

## Folder organisation

As reports are added, the collection will follow this structure:

```text
SOC writeups/
|-- README.md
|-- Malware analysis/
|-- Phishing analysis/
`-- Web attack/
```

Each investigation can have its own clearly named subfolder containing the report and supporting material, such as sanitised screenshots, log excerpts, IOC tables, and detection queries. Reports may be published in Markdown or PDF format.

A suggested naming convention is `YYYY-MM-DD-short-case-title` to keep a growing collection easy to browse.

## What a writeup can contain

The depth of each report will depend on the case and the evidence available. A typical writeup can include:

1. **Overview** — the scenario, investigation objective, and a short summary of the findings.
2. **Scope and environment** — the lab or data source, relevant systems, tools used, and limitations.
3. **Initial alert or evidence** — what triggered the investigation and the information available at the start.
4. **Investigation process** — the analysis steps, queries, observations, and reasoning behind key decisions.
5. **Timeline and findings** — important events, supporting evidence, IOCs, and relevant ATT&CK mappings.
6. **Assessment and response** — the verdict, potential impact, recommended actions, and any actions actually performed.
7. **Lessons learned** — investigation challenges, detection improvements, and areas for further study.
8. **References** — the original lab or challenge, datasets, and supporting resources where applicable.

Reports will distinguish observed facts from assumptions and recommendations. Where the available evidence cannot confirm an outcome, the writeup will state that limitation.

## Ongoing development

I will update this collection periodically as I complete new investigations. Over time, it will serve as both a personal knowledge base and a portfolio of my approach to alert triage, evidence analysis, incident investigation, and clear technical reporting.

Any tools, techniques, and outcomes described in an individual report will reflect that specific investigation.

## Publication notes

These writeups are intended for learning and defensive security practice. Each report should identify whether it comes from a lab, training challenge, or another authorised investigation. Sensitive information will be removed or anonymised before publication, and suspicious URLs will be defanged where appropriate.
