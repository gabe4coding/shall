---
id: SCALE-0063
title: Runbooks for alerts
status: approved
domain: documentation
artifacts: [doc, diff]
languages: [any]
owner: sre
review_by: 2027-06-30
supersedes: []
summary: >
  Every paging alert links to a runbook that lets an on-call engineer who does not know
  the service diagnose and mitigate the problem.
applies_when: >
  The content adds or changes a runbook, an alert or monitor definition, or an on-call
  guide.
not_applies_when: >
  No runbook, alert, monitor or on-call guide is added, changed or described.
---

# SCALE-0063: Runbooks for alerts

## Context

At night the engineer who is paged is often not the one who wrote the service. An alert
without a runbook turns a ten-minute mitigation into an hour of reading code. Runbooks
are only useful when they contain the exact steps and are kept current with the alert.

## Requirements

### SCALE-0063.1 Every paging alert has a runbook
Every alert that pages on-call MUST link to a runbook in its notification message.

- Applies when: the content adds or changes a Datadog monitor, Prometheus alert rule or PagerDuty-routed alert with a paging priority.
- Enforcement: linter

### SCALE-0063.2 What the alert means
A runbook MUST state what the alert measures, the threshold that triggers it, and the
user impact when it fires.

- Applies when: the content adds or changes a runbook for an alert or monitor.
- Enforcement: agent

### SCALE-0063.3 Diagnosis steps
A runbook MUST give ordered diagnosis steps with the exact dashboards, log queries and
commands to run, not general advice such as "check the logs".

- Applies when: the content adds or changes the diagnosis or investigation section of a runbook.
- Enforcement: agent

### SCALE-0063.4 Mitigation steps
A runbook MUST list the mitigations for each known cause (rollback, scale up, disable a
feature flag, fail over) with the command or console action for each.

- Applies when: the content adds or changes the mitigation, remediation or resolution section of a runbook.
- Enforcement: agent

### SCALE-0063.5 Escalation path
A runbook MUST name who to escalate to, and after how many minutes, when the listed
mitigations do not work.

- Applies when: the content adds or changes a runbook or on-call guide.
- Enforcement: agent

### SCALE-0063.6 Commands safe to copy
Commands in a runbook SHOULD be copy-paste ready with placeholders marked in angle
brackets, and SHOULD state which ones change production state.

- Applies when: a runbook contains shell, kubectl, SQL or CLI commands.
- Enforcement: agent

### SCALE-0063.7 Last verified date
A runbook SHOULD show the date it was last tested in a drill or real incident, and SHOULD
be reviewed when that date is older than six months.

- Applies when: the content adds or changes a runbook.
- Enforcement: agent

### SCALE-0063.8 Runbook updated with the alert
A change to an alert's query, threshold or scope MUST update the linked runbook in the
same pull request when the meaning or diagnosis of the alert changes.

- Applies when: the diff changes the query, threshold, evaluation window or tags of an alert or monitor definition.
- Enforcement: agent

### SCALE-0063.9 Non-paging alerts
Alerts that only notify a Slack channel and never page MAY link to a shared runbook for
the alert type instead of a runbook of their own.

- Applies when: the content adds or changes an alert or monitor that notifies only a chat channel or ticket queue.
- Enforcement: agent
