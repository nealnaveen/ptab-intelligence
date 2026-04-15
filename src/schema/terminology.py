"""
PTAB Intelligence — Canonical Terminology Schema
================================================
Single source of truth for all synonym clusters in the USPTO/PTAB domain.

Usage:
    from src.schema.terminology import normalize, normalize_field_name, SYNONYMS

Every Lambda, script, and Claude prompt that deals with patent terminology
should import from here so normalization never diverges.
"""

# ---------------------------------------------------------------------------
# SYNONYM CLUSTERS
# Each key is the canonical term. Values are known variants (case-insensitive).
# ---------------------------------------------------------------------------
SYNONYMS: dict[str, list[str]] = {

    # ── Identifiers ──────────────────────────────────────────────────────────
    "proceeding_number": [
        "proceeding number", "proceeding no", "proceeding no.",
        "case number", "case #", "case no", "case no.", "case num",
        "trial number", "trial no", "trial no.",
        "ipr number", "ipr no", "ipr no.", "ipr #",
        "pgr number", "pgr no", "pgr no.", "pgr #",
        "cbm number", "cbm no",
        "ptab case", "ptab number",
    ],
    "application_number": [
        "application number", "application no", "application no.",
        "app number", "app no", "app no.", "app #",
        "serial number", "serial no", "serial no.",
        "appl no", "appl. no", "appl. no.",
        "patent application",
    ],
    "patent_number": [
        "patent number", "patent no", "patent no.", "patent #",
        "us patent", "u.s. patent", "issued patent",
    ],

    # ── Rejection / Objection grounds ────────────────────────────────────────
    "section_101": [
        "101", "§101", "§ 101", "sec 101", "sec. 101", "section 101",
        "35 usc 101", "35 u.s.c. 101", "35 usc § 101",
        "subject matter eligibility", "subject matter ineligibility",
        "sme", "sme rejection",
        "alice", "alice rejection", "alice/mayo", "mayo",
        "abstract idea", "law of nature", "natural phenomenon",
        "patent eligible", "patent ineligible",
    ],
    "section_102": [
        "102", "§102", "§ 102", "sec 102", "sec. 102", "section 102",
        "35 usc 102", "35 u.s.c. 102", "35 usc § 102",
        "anticipation", "anticipated", "prior art anticipation",
        "novelty", "lack of novelty", "not novel",
    ],
    "section_103": [
        "103", "§103", "§ 103", "sec 103", "sec. 103", "section 103",
        "35 usc 103", "35 u.s.c. 103", "35 usc § 103",
        "obviousness", "obvious", "obv", "obv rejection",
        "non-statutory obviousness", "103 rejection",
        "obviousness-type double patenting", "otdp",
        "would have been obvious", "prima facie obvious",
    ],
    "section_112": [
        "112", "§112", "§ 112", "sec 112", "sec. 112", "section 112",
        "35 usc 112", "35 u.s.c. 112", "35 usc § 112",
        "written description", "written description requirement",
        "enablement", "enablement requirement",
        "indefiniteness", "indefinite", "indefinite claim",
        "best mode",
    ],

    # ── Proceeding types ─────────────────────────────────────────────────────
    "ipr": [
        "ipr", "inter partes review", "inter-partes review",
        "inter partes", "ip review",
    ],
    "pgr": [
        "pgr", "post grant review", "post-grant review",
        "post grant", "post-grant",
    ],
    "cbm": [
        "cbm", "covered business method", "covered business method review",
        "business method patent",
    ],
    "ex_parte_reexamination": [
        "ex parte reexamination", "ex parte reexam", "reexamination",
        "reexam", "reexamination proceeding",
    ],

    # ── Decisions & Outcomes ──────────────────────────────────────────────────
    "institution_decision": [
        "institution decision", "institution", "instituted",
        "decision to institute", "dti", "granted institution",
        "institution granted", "instituted trial",
        "decision on institution", "doi",
    ],
    "final_written_decision": [
        "final written decision", "fwd", "final decision",
        "final written", "final determination",
        "final judgment", "final ruling",
    ],
    "claims_unpatentable": [
        "claims unpatentable", "all claims unpatentable",
        "claims cancelled", "claims invalidated",
        "found unpatentable", "held unpatentable",
        "claims invalid",
    ],
    "claims_patentable": [
        "claims patentable", "claims upheld", "claims confirmed",
        "found patentable", "held patentable", "survived",
    ],
    "petition_denied": [
        "petition denied", "denied", "institution denied",
        "not instituted", "no institution",
    ],
    "settlement": [
        "settlement", "settled", "joint motion to terminate",
        "termination", "terminated", "dismissed",
    ],

    # ── Prosecution status ───────────────────────────────────────────────────
    "pending": [
        "pending", "pend", "application pending",
        "prosecution pending", "active",
    ],
    "allowed": [
        "allowed", "allowance", "notice of allowance",
        "noa", "approved",
    ],
    "abandoned": [
        "abandoned", "abandon", "applicant abandoned",
        "failure to respond", "express abandonment",
    ],
    "patented": [
        "patented", "issued", "patent issued", "granted",
        "patent granted",
    ],

    # ── Parties ──────────────────────────────────────────────────────────────
    "petitioner": [
        "petitioner", "challenger", "requester",
        "ipr petitioner", "pgr petitioner",
        "real party in interest", "rpi",
    ],
    "patent_owner": [
        "patent owner", "patent holder", "patentee",
        "respondent", "po", "patent proprietor",
    ],
    "examiner": [
        "examiner", "patent examiner", "primary examiner",
        "uspto examiner",
    ],

    # ── Document types ───────────────────────────────────────────────────────
    "office_action": [
        "office action", "oa", "non-final office action", "nfoa",
        "final office action", "foa", "final rejection",
        "non-final rejection", "office communication",
    ],
    "petition": [
        "petition", "ipr petition", "pgr petition",
        "petition for inter partes review",
        "petition for post grant review",
    ],
    "response": [
        "response", "reply", "applicant response",
        "patent owner response", "por",
        "patent owner preliminary response", "popr",
        "response to office action",
    ],
    "declaration": [
        "declaration", "expert declaration", "expert testimony",
        "affidavit", "exhibit",
    ],
    "claim_amendment": [
        "claim amendment", "amended claims", "amendment",
        "motion to amend", "mta", "substitute claims",
    ],

    # ── Patent structure ─────────────────────────────────────────────────────
    "independent_claim": [
        "independent claim", "independent claims",
        "base claim", "main claim",
    ],
    "dependent_claim": [
        "dependent claim", "dependent claims",
    ],
    "prior_art": [
        "prior art", "prior art reference", "reference",
        "cited reference", "prior publication",
        "anticipatory reference",
    ],
    "art_unit": [
        "art unit", "art unit number", "au",
        "examination group", "technology center",
    ],
    "continuation": [
        "continuation", "continuation application",
        "con", "continuing application",
    ],
    "continuation_in_part": [
        "continuation-in-part", "continuation in part", "cip",
    ],
    "divisional": [
        "divisional", "divisional application", "div",
    ],
    "appeal": [
        "appeal", "appeal brief", "ex parte appeal",
        "notice of appeal", "noa", "board of appeals",
        "ptab appeal",
    ],
}

# ---------------------------------------------------------------------------
# FIELD NAME ALIASES
# Maps variant column/field names to the canonical S3 field name.
# ---------------------------------------------------------------------------
FIELD_ALIASES: dict[str, str] = {
    # Proceeding identifiers
    "case #":              "proceeding_number",
    "case no":             "proceeding_number",
    "case no.":            "proceeding_number",
    "case number":         "proceeding_number",
    "trial number":        "proceeding_number",
    "ipr no":              "proceeding_number",
    "pgr no":              "proceeding_number",

    # Application identifiers
    "app no":              "application_number",
    "appl no":             "application_number",
    "serial number":       "application_number",
    "serial no":           "application_number",

    # Dates
    "accordedfilingdate":  "filing_date",
    "applicationfilingdate": "filing_date",
    "filingdate":          "filing_date",
    "terminationdate":     "decision_date",
    "finalwrittendecisiondate": "decision_date",

    # Status
    "applicationstatuscodedescriptiontext": "status",
    "applicationstatuscategorytext":        "status",
    "applicationstatuscode":                "status",
    "trialstatuscode":                      "status",
    "proceedingstatus":                     "status",

    # Type
    "trialtypecode":       "proceeding_type",
    "proceedingtype":      "proceeding_type",

    # Parties
    "assigneename":        "applicant",
    "assigneeentityname":  "applicant",
    "patentownername":     "patent_owner",
    "petitionername":      "petitioner",
    "realpartyininterestname": "petitioner",

    # Classification
    "groupartunitnumber":  "art_unit",
    "technologycenternumber": "technology_center",
    "inventiontitle":      "invention_title",
    "inventiontitletext":  "invention_title",
}

# ---------------------------------------------------------------------------
# STATUS DISPLAY NORMALIZATION
# Maps raw ODP status codes/values → clean display strings.
# ---------------------------------------------------------------------------
STATUS_MAP: dict[str, str] = {
    # Application statuses
    "pend":                "Pending",
    "pending":             "Pending",
    "patented case":       "Patented",
    "issued":              "Patented",
    "patent issued":       "Patented",
    "allowed":             "Allowed",
    "allowance":           "Allowed",
    "abandoned":           "Abandoned",
    "abandon":             "Abandoned",
    "applicant abandoned": "Abandoned",
    "expired":             "Expired",
    "withdrawn":           "Withdrawn",

    # Proceeding statuses
    "fwd":                 "Final Written Decision",
    "final written decision issued": "Final Written Decision",
    "terminated-settlement": "Settled",
    "settled":             "Settled",
    "terminated":          "Terminated",
    "instituted":          "Instituted",
    "institution granted": "Instituted",
    "denied":              "Petition Denied",
    "not instituted":      "Petition Denied",
    "pending":             "Pending",
    "joinder":             "Joinder",
}

# ---------------------------------------------------------------------------
# PROCEEDING TYPE NORMALIZATION
# ---------------------------------------------------------------------------
PROCEEDING_TYPE_MAP: dict[str, str] = {
    "ipr":                        "IPR",
    "inter partes review":        "IPR",
    "inter-partes review":        "IPR",
    "pgr":                        "PGR",
    "post grant review":          "PGR",
    "post-grant review":          "PGR",
    "cbm":                        "CBM",
    "covered business method":    "CBM",
    "derivation":                 "Derivation",
    "der":                        "Derivation",
}

# ---------------------------------------------------------------------------
# HELPER FUNCTIONS
# ---------------------------------------------------------------------------

# Build a reverse lookup: variant (lower) → canonical key
_REVERSE: dict[str, str] = {}
for _canonical, _variants in SYNONYMS.items():
    for _v in _variants:
        _REVERSE[_v.lower().strip()] = _canonical
    # The canonical itself maps to itself
    _REVERSE[_canonical.lower().strip()] = _canonical


def normalize(term: str) -> str:
    """
    Return the canonical term for a given variant, or the original
    (lowercased, stripped) if no mapping exists.

    Example:
        normalize("case #")        → "proceeding_number"
        normalize("FWD")           → "final_written_decision"
        normalize("§103")          → "section_103"
        normalize("unknown term")  → "unknown term"
    """
    if not term:
        return term
    return _REVERSE.get(term.lower().strip(), term.lower().strip())


def normalize_field_name(raw_field: str) -> str:
    """
    Map a raw/variant field name to the canonical S3 field name.

    Example:
        normalize_field_name("case no.")  → "proceeding_number"
        normalize_field_name("appl no")   → "application_number"
    """
    return FIELD_ALIASES.get(raw_field.lower().strip(), raw_field)


def normalize_status(raw: str) -> str:
    """Return a clean display status string."""
    if not raw:
        return raw
    return STATUS_MAP.get(str(raw).lower().strip(), str(raw))


def normalize_proceeding_type(raw: str) -> str:
    """Return the canonical proceeding type label (IPR, PGR, CBM, etc.)."""
    if not raw:
        return raw
    return PROCEEDING_TYPE_MAP.get(str(raw).lower().strip(), str(raw).upper())


def build_prompt_context() -> str:
    """
    Return a compact string listing canonical terms for inclusion in
    Claude prompts so the model uses consistent vocabulary.
    """
    lines = [
        "Use only these canonical terms in your output:",
        f"  Identifiers:  proceeding_number, application_number, patent_number",
        f"  Rejections:   section_101, section_102, section_103, section_112",
        f"  Proceedings:  IPR, PGR, CBM",
        f"  Decisions:    institution_decision, final_written_decision,",
        f"                claims_unpatentable, claims_patentable, petition_denied, settlement",
        f"  Status:       Pending, Allowed, Abandoned, Patented, Expired",
        f"  Parties:      petitioner, patent_owner, examiner",
        f"  Documents:    office_action, petition, response, declaration, claim_amendment",
    ]
    return "\n".join(lines)
