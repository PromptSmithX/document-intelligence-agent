# Evaluation Results

- Generated at: `2026-06-15T10:45:06+00:00`
- Dataset: `synthetic_policy_v1`
- Document ID: `doc_3a6846d48f734b15a19c0ad177a24274`
- top_k: `5`
- LLM judge: `disabled`

## Aggregate Metrics

| Metric | Value |
|---|---:|
| Total cases | 5 |
| Error cases | 0 |
| Hit@5 | 100.0% |
| MRR@5 | 1.000 |
| Avg top score | 0.601 |
| Answer pass rate | 60.0% |
| Answer term pass rate | 50.0% |
| No-answer pass rate | 100.0% |
| Citation pass rate | 100.0% |
| Latency avg | 2.64s |
| Latency p50 | 2.60s |
| Latency p95 | 3.07s |

## Case Results

| Case | Answerable | Status | Hit | MRR | Answer pass | Citation pass | Latency | Error |
|---|---:|---|---:|---:|---:|---:|---:|---|
| payment_terms | true | ok | yes | 1.000 | yes | yes | 2.98s |  |
| termination_notice | true | ok | yes | 1.000 | no | yes | 2.30s |  |
| governing_law | true | ok | yes | 1.000 | no | yes | 2.60s |  |
| support_sla | true | ok | yes | 1.000 | yes | yes | 2.27s |  |
| renewal_discount_unanswerable | false | ok | no | 0.000 | yes | n/a | 3.07s |  |

## Answers

### payment_terms

- Question: When must approved invoices be paid and in what currency?
- Expected pages: `[1]`
- Citation pages: `[1, 4, 5, 3, 2]`

Approved invoices must be paid within 45 calendar days of the invoice date. All payments must be made in USD by electronic transfer unless both parties agree otherwise in writing.

### termination_notice

- Question: How much notice is required before either party may terminate for material breach?
- Expected pages: `[2]`
- Citation pages: `[2, 5, 1, 3, 4]`

Either party may terminate the agreement for material breach only after giving 30 days written notice to the breaching party.

### governing_law

- Question: Which law governs the agreement and where is venue?
- Expected pages: `[3]`
- Citation pages: `[3, 1, 2, 4, 5]`

The agreement is governed by the laws of the State of New York, without regard to conflict of law principles. Any lawsuit or proceeding must be brought exclusively in the state or federal courts located in New York County, New York.

### support_sla

- Question: What is the response time for critical support incidents?
- Expected pages: `[4]`
- Citation pages: `[4, 5, 1, 2, 3]`

Critical support incidents receive an initial response within 4 business hours after a complete ticket is submitted.

### renewal_discount_unanswerable

- Question: What renewal discount does the policy guarantee after the first year?
- Expected pages: `[]`
- Citation pages: `[5, 1, 4, 2, 3]`

I could not find this information in the document.
