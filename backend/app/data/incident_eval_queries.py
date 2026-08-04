"""
Hand-labeled evaluation set for incident-retrieval quality: one realistic
PR-style query per incident in real_incidents.py, deliberately phrased very
differently from that incident's own description (as a genuine PR title/
description would read, not a paraphrase of the incident text) so retrieval
is actually being tested on semantic similarity, not keyword overlap.

Used by retrieval_eval.py to compute precision@k.
"""

EVAL_QUERIES = [
    {
        "expected_incident_id": "REAL-001",
        "title": "Remove legacy feature flag from order routing",
        "description": "This flag was left over from an old rollout. If even one server in the fleet is still running the previous build while the rest are upgraded, it could reinterpret the flag differently and send unexpected live orders.",
    },
    {
        "expected_incident_id": "REAL-002",
        "title": "Add pre-flight safety check before destructive DB commands during incident response",
        "description": "We want to stop an on-call engineer from accidentally running a deletion command against the wrong database host while responding to an outage, and add alerting so a backup job can't silently fail for weeks without anyone noticing.",
    },
    {
        "expected_incident_id": "REAL-003",
        "title": "Add timeout to regex matching in request filtering",
        "description": "Our request-filtering rules can spike CPU to 100% on certain crafted inputs because of catastrophic backtracking in one pattern. We need to bound how long a single match is allowed to run.",
    },
    {
        "expected_incident_id": "REAL-004",
        "title": "Add confirmation step and dry-run mode to the fleet decommissioning script",
        "description": "If an operator mistypes the count parameter in our internal tooling, it could remove far more server capacity than intended in one shot.",
    },
    {
        "expected_incident_id": "REAL-005",
        "title": "Validate declared length field against actual payload size",
        "description": "Found a spot in our keepalive protocol handler where the client-supplied length isn't checked against the real buffer size before reading, which could leak adjacent memory contents back to the client.",
    },
    {
        "expected_incident_id": "REAL-006",
        "title": "Disable remote lookup syntax in logging library by default",
        "description": "Our logging framework evaluates special substitution syntax inside log messages, including remote directory lookups. Untrusted input that ends up logged could trigger code execution on the server.",
    },
    {
        "expected_incident_id": "REAL-007",
        "title": "Add stricter validation for content update files before the driver loads them",
        "description": "A malformed configuration pushed to our kernel-level agent could crash the driver on load and take down the whole machine. We need real validation before an update is applied, not just a version check.",
    },
    {
        "expected_incident_id": "REAL-008",
        "title": "Add a safety check before withdrawing BGP routes during maintenance",
        "description": "A bad route withdrawal during routine network maintenance could make our own DNS servers unreachable. We should also make sure emergency physical access systems don't depend on that same network path.",
    },
    {
        "expected_incident_id": "REAL-009",
        "title": "Add regression coverage for rare customer configuration combinations",
        "description": "A customer-supplied config value almost nobody uses tripped a bug that had been sitting dormant in the code for months. We want broader test coverage for uncommon config combinations, not just the common paths.",
    },
    {
        "expected_incident_id": "REAL-010",
        "title": "Add exponential backoff and jitter to client retry logic",
        "description": "During a traffic spike, clients started aggressively retrying failed requests, which made the already-struggling database tier even worse. We need real backoff instead of immediate retries.",
    },
    {
        "expected_incident_id": "REAL-011",
        "title": "Load test the platform for peak trading volume scenarios",
        "description": "We've never verified our infrastructure can handle a full day of record-high trading volume and volatility. Want capacity testing before the next major earnings season.",
    },
    {
        "expected_incident_id": "REAL-012",
        "title": "Automate dependency vulnerability scanning with enforced patch SLAs",
        "description": "We found a web framework dependency with a publicly disclosed critical CVE that had gone unpatched for months. Need an automated process to catch this instead of relying on someone noticing.",
    },
    {
        "expected_incident_id": "REAL-013",
        "title": "Document the correct procedure for reconnecting power during data center maintenance",
        "description": "An improperly sequenced power reconnection during planned electrical maintenance could cause a surge that damages equipment and takes core systems offline.",
    },
    {
        "expected_incident_id": "REAL-014",
        "title": "Vendor critical small dependencies instead of pulling them from the public registry at build time",
        "description": "One of our builds transitively depends on a tiny package that its maintainer could unpublish at any time, breaking every downstream build with no warning.",
    },
    {
        "expected_incident_id": "REAL-015",
        "title": "Add scope validation to the network config rollout tool",
        "description": "A configuration change meant for a handful of servers in one region got applied far more broadly than intended because of a bug in the rollout tool. We need to validate the blast radius before applying changes network-wide.",
    },
]
