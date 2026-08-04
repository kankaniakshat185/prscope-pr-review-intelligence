"""
A small, real, sourced set of well-documented public software incidents,
used to seed incident-similarity matching (see incident_similarity.py) and
to evaluate its retrieval quality (see retrieval_eval.py).

Each entry is a factual, independently-written summary of a publicly
reported incident - not a verbatim quote from any single source - with a
`source` field naming where it was documented, so provenance is checkable.
These replace the earlier 3 hand-written placeholder examples that had no
real-world grounding at all.

This is still a small, manually-curated set (15 incidents), not a real
production incident database - see retrieval_eval.py for how its retrieval
quality is actually measured rather than just assumed.
"""

REAL_INCIDENTS = [
    {
        "incident_id": "REAL-001",
        "date": "2012-08-01",
        "severity": "Critical",
        "category": "deployment",
        "description": (
            "A trading firm deployed new order-routing code to only 7 of 8 production servers; the 8th "
            "still ran old code that reused a flag repurposed by the new deployment, causing it to send a "
            "flood of unintended live orders into the market. The runaway trading ran for 45 minutes before "
            "being stopped, causing a loss of roughly $440 million and the firm's near-collapse."
        ),
        "source": "Knight Capital Group, August 1 2012 (widely documented in SEC filings and press coverage)",
    },
    {
        "incident_id": "REAL-002",
        "date": "2017-01-31",
        "severity": "Critical",
        "category": "operations",
        "description": (
            "During an incident response, an engineer ran a directory-removal command against what they "
            "believed was a secondary database replica, but was actually connected to the primary, deleting "
            "several hundred gigabytes of production data. Investigation afterward found that all of the "
            "team's automated backup mechanisms had been silently failing for weeks beforehand."
        ),
        "source": "GitLab.com database incident, January 31 2017 (GitLab's own published postmortem)",
    },
    {
        "incident_id": "REAL-003",
        "date": "2019-07-02",
        "severity": "Critical",
        "category": "performance",
        "description": (
            "A single regular expression deployed to a web application firewall rule contained a pattern "
            "vulnerable to catastrophic backtracking. Certain incoming request bodies caused CPU usage on "
            "that expression to spike toward 100% across the fleet simultaneously, degrading service "
            "worldwide until the offending rule was identified and rolled back."
        ),
        "source": "Cloudflare WAF outage, July 2 2019 (Cloudflare's own published postmortem)",
    },
    {
        "incident_id": "REAL-004",
        "date": "2017-02-28",
        "severity": "Critical",
        "category": "operations",
        "description": (
            "An engineer running an established debugging playbook to take a small number of servers "
            "offline for a subsystem mistakenly entered a command that removed a much larger set of "
            "servers than intended, including ones supporting core index and placement services. The "
            "resulting cascading restart took hours and degraded many dependent cloud services in the region."
        ),
        "source": "AWS S3 us-east-1 outage, February 28 2017 (AWS's own published post-event summary)",
    },
    {
        "incident_id": "REAL-005",
        "date": "2014-04-01",
        "severity": "Critical",
        "category": "security",
        "description": (
            "A widely used TLS library's implementation of a heartbeat extension failed to validate that a "
            "client-supplied length field matched the actual payload size, allowing a remote attacker to "
            "read up to 64KB of adjacent server memory per request - including private keys, session "
            "tokens, and credentials - without leaving any trace in normal logs."
        ),
        "source": "Heartbleed, CVE-2014-0160, OpenSSL (public CVE record and coordinated disclosure writeups)",
    },
    {
        "incident_id": "REAL-006",
        "date": "2021-12-09",
        "severity": "Critical",
        "category": "security",
        "description": (
            "A popular Java logging library evaluated special lookup syntax embedded in log messages by "
            "default, including JNDI lookups. An attacker who could get a single crafted string logged - "
            "for example via a request header - could cause the server to fetch and execute arbitrary "
            "remote code, with no further interaction required."
        ),
        "source": "Log4Shell, CVE-2021-44228, Apache Log4j (public CVE record and Apache Foundation advisory)",
    },
    {
        "incident_id": "REAL-007",
        "date": "2024-07-19",
        "severity": "Critical",
        "category": "deployment",
        "description": (
            "An endpoint security vendor pushed a content configuration update to its kernel-level sensor "
            "that contained malformed data its validation logic failed to catch. The sensor crashed on "
            "load, taking down the operating system on every machine that received the update, grounding "
            "flights and disrupting hospitals and other critical services worldwide."
        ),
        "source": "CrowdStrike Falcon sensor outage, July 19 2024 (CrowdStrike's own published root-cause analysis)",
    },
    {
        "incident_id": "REAL-008",
        "date": "2021-10-04",
        "severity": "Critical",
        "category": "networking",
        "description": (
            "A routine maintenance change intended to assess backbone capacity contained a command that "
            "accidentally withdrew the network routes advertising the company's own DNS servers. With those "
            "routes gone, the company's services became globally unreachable, and the same networking "
            "failure also disabled the badge and access systems staff needed to physically reach the "
            "affected hardware."
        ),
        "source": "Meta/Facebook BGP outage, October 4 2021 (Meta's own published engineering postmortem)",
    },
    {
        "incident_id": "REAL-009",
        "date": "2021-06-08",
        "severity": "High",
        "category": "deployment",
        "description": (
            "A customer made a valid, permitted configuration change that happened to trigger a latent bug "
            "introduced by a software deployment made months earlier. The bug caused the majority of the "
            "CDN provider's network to begin returning errors within about a minute of the triggering change."
        ),
        "source": "Fastly CDN outage, June 8 2021 (Fastly's own published postmortem)",
    },
    {
        "incident_id": "REAL-010",
        "date": "2021-01-04",
        "severity": "High",
        "category": "scalability",
        "description": (
            "A surge in traffic following a holiday combined with a misconfigured database transitioning "
            "state caused a spike in connection errors, which triggered aggressive client-side retries that "
            "further overloaded the already-struggling database tier, producing a multi-hour cascading outage."
        ),
        "source": "Slack outage, January 4 2021 (Slack's own published engineering postmortem)",
    },
    {
        "incident_id": "REAL-011",
        "date": "2020-03-02",
        "severity": "High",
        "category": "scalability",
        "description": (
            "Record trading volume and market volatility exceeded the capacity the trading platform's "
            "infrastructure had been provisioned and tested for, causing full-platform outages that "
            "prevented customers from trading during some of the most volatile sessions of the year."
        ),
        "source": "Robinhood trading outages, March 2020 (widely reported and later covered in regulatory filings)",
    },
    {
        "incident_id": "REAL-012",
        "date": "2017-09-07",
        "severity": "Critical",
        "category": "security",
        "description": (
            "A known remote-code-execution vulnerability in a popular web application framework, for which "
            "a patch had already been publicly available for months, was exploited to gain access to "
            "internal systems, ultimately exposing sensitive personal records for a large portion of a "
            "country's population."
        ),
        "source": "Equifax data breach via CVE-2017-5638 (Apache Struts), disclosed September 2017",
    },
    {
        "incident_id": "REAL-013",
        "date": "2017-05-27",
        "severity": "High",
        "category": "operations",
        "description": (
            "During planned electrical maintenance at a data center, a power supply was disconnected "
            "incorrectly and then reconnected in an uncontrolled way, causing a physical power surge that "
            "damaged equipment and took core systems offline, cancelling hundreds of flights over several days."
        ),
        "source": "British Airways IT outage, May 27 2017 (widely reported, including UK parliamentary inquiry testimony)",
    },
    {
        "incident_id": "REAL-014",
        "date": "2016-03-22",
        "severity": "Medium",
        "category": "dependency",
        "description": (
            "The author of a very small, widely-depended-upon open-source package unpublished it from the "
            "public registry in a dispute over naming. Because a huge number of other packages depended on "
            "it transitively, builds across a large portion of the ecosystem started failing simultaneously "
            "until the registry intervened."
        ),
        "source": "The npm \"left-pad\" incident, March 22 2016 (widely documented in developer community writeups)",
    },
    {
        "incident_id": "REAL-015",
        "date": "2019-06-02",
        "severity": "High",
        "category": "networking",
        "description": (
            "A network configuration change intended to apply to a small number of servers in one location "
            "was, due to a software bug, applied much more broadly than intended, removing capacity across "
            "multiple regions simultaneously and causing several hours of major service disruption across "
            "many products hosted on the same cloud network."
        ),
        "source": "Google Cloud network congestion incident, June 2 2019 (Google's own published incident report)",
    },
]
