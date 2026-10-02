"""The topics Mystique's owners, vendors, and agencies write about, and the words that name them in a subject line.

Words match at the start of a word, ignoring case ("bin" matches "Bins", not "cabinet"). Built from the subjects of
the association's email (read September 29, 2026): a new owner's questions ran to parking, bins, solar, the master
flood policy, the HOA invoice, and HVAC.
"""

from __future__ import annotations

from jason.community.topics import Intent, IntentRule, Topic, TopicRule, TopicSources

TOPIC_RULES: tuple[TopicRule, ...] = (
    TopicRule(Topic.PARKING, ("parking", "park ", "parked", "guest permit", "parking permit", "tow", "vehicle", "car ")),
    TopicRule(Topic.BINS, ("bin", "trash", "garbage", "recycl", "green waste", "bulky")),
    TopicRule(Topic.SOLAR, ("solar", "sunrun", "sunpower", "tesla energy", "panels")),
    TopicRule(Topic.INSURANCE, ("insurance", "flood", "policy", "certificate of insurance", "coi", "ho-6", "ho6", "claim", "adjuster",
                                "renewal", "premium")),
    TopicRule(Topic.ASSESSMENTS, ("hoa invoice", "invoice", "payment", "dues", "assessment", "autopay", "auto pay", "statement",
                                  "balance", "late fee", "receipt", "refund", "collections")),
    TopicRule(Topic.MAINTENANCE, ("repair", "leak", "roof", "gutter", "maintenance", "hvac", "garage door", "door", "window",
                                  "plumbing", "water intrusion", "stucco", "balcon", "light", "sprinkler head", "handyman")),
    TopicRule(Topic.LANDSCAPING, ("landscap", "grass", "lawn", "tree", "irrigation", "weeds", "patio", "shrub", "mulch")),
    TopicRule(Topic.PESTS, ("pest", "rodent", "rat", "rats", "mice", "ant", "ants", "termite", "bees", "wasp", "cockroach")),
    TopicRule(Topic.ARCHITECTURE, ("architectural", "alteration", "modification", "arc ", "remodel", "building permit", "plans approved",
                                   "installation", "ev charger")),
    TopicRule(Topic.NEIGHBORS, ("noise", "neighbor", "dog", "barking", "smoke", "smoking", "pet", "harass", "disciplinary")),
    TopicRule(Topic.ESCROW, ("escrow", "resale", "hoa demand", "demand and docs", "payoff", "estoppel", "sale", "title company",
                             "closing", "4528")),
    TopicRule(Topic.GOVERNANCE, ("meeting", "minutes", "agenda", "board", "election", "ballot", "vote", "cc&r", "ccr", "bylaws",
                                 "rules", "policy statement", "annual disclosure", "budget")),
    TopicRule(Topic.SECURITY, ("camera", "flock", "break-in", "theft", "stolen", "police", "broken window", "vandal", "incident",
                               "attack", "trespass")),
    TopicRule(Topic.UTILITIES, ("water", "smud", "electric", "sewer", "backflow", "utility", "utilities", "ebill")),
)


# What a subject asks, in order. Read from the association's email (September 29, 2026): complaints name the conduct
# ("Noise complaint", "Unauthorized parking", "Issues with tenant / Smoking in garage"); the association's own notices
# carry "Courtesy Notice", "Notice of Violation", "Disciplinary Hearing".
INTENT_RULES: tuple[IntentRule, ...] = (
    IntentRule(Intent.ENFORCEMENT, (r"courtesy notice", r"notice of violation", r"violation (?:notice|report)", r"disciplinary hearing",
                                    r"board hearing", r"notice of (?:board )?hearing", r"intent to levy", r"fine\b")),
    IntentRule(Intent.COMPLAINT, (r"complain", r"concern", r"nuisance", r"no[is]{2}e\b", r"unauthori[sz]ed", r"blocking", r"in front of (?:my|the|our) garage",
                                  r"parked (?:in|on|at)", r"harass", r"attack", r"smok", r"barking", r"left out", r"cans? (?:left|out)",
                                  r"issues? (?:with|in)", r"problem with", r"neighbor", r"theft", r"vandal", r"trespass", r"dog (?:waste|poop)",
                                  r"off[- ]leash", r"violat")),
    IntentRule(Intent.MAINTENANCE, (r"repair", r"leak", r"broken", r"not working", r"maintenance", r"\bfix", r"replace", r"clog",
                                    r"outage", r"damage", r"crack", r"mold", r"pest", r"wasps?", r"weeds", r"gutter", r"light(?:s|ing)? out")),
    IntentRule(Intent.INFORMATION, (r"copy of", r"request for (?:the |a |current )?(?:copy|records?|documents?|policy|certificate|minutes|budget|information)",
                                    r"records? request", r"documents? request", r"certificate of insurance", r"\bcoi\b", r"insurance documents",
                                    r"master (?:flood )?policy", r"resale", r"(?:ccr|cc&r|bylaws|rules)\b.*(?:copy|request)", r"repair records",
                                    r"hoa demand", r"demand (?:and|&) docs", r"estoppel", r"questionnaire")),
    IntentRule(Intent.BILLING, (r"invoice", r"payment", r"late (?:fee|charge)", r"double charge", r"refund", r"balance", r"autopay",
                                r"auto pay", r"receipt", r"statement", r"dues", r"assessment")),
    IntentRule(Intent.QUESTION, (r"\?", r"question", r"^how\b", r"\bhow (?:do|to|can)", r"\bcan (?:i|we)\b", r"\bmay i\b", r"\bis it\b",
                                 r"who handles", r"allowed", r"permitted", r"rules?\b", r"clarif", r"inquiry", r"follow ?up", r"responsib")),
)

# Where each topic's answer is likely written: the governing documents' passages, the library's kinds, and the PayHOA
# violations that are its precedents (CC&R 4.10(c) is cited on the January 2025 trash storage violation).
TOPIC_SOURCES: tuple[TopicSources, ...] = (
    TopicSources(Topic.PARKING, "parking garage vehicles guest parking tow driveway common area streets",
                 ("operating_rules", "policy", "declaration"), ("parking", "vehicle", "garage")),
    TopicSources(Topic.BINS, "trash disposal containers screened from view pickup collection refuse",
                 ("operating_rules", "declaration"), ("trash", "garbage", "cans")),
    TopicSources(Topic.NEIGHBORS, "nuisance noise animals pets dogs leash offensive conduct",
                 ("operating_rules", "declaration", "policy"), ("noise", "nuisance", "dog", "offensive", "smok")),
    TopicSources(Topic.SECURITY, "security cameras common area damage theft",
                 ("policy", "security_report"), ("damage", "sign")),
    TopicSources(Topic.SOLAR, "solar energy system roof installation architectural approval", ("policy", "declaration"), ()),
    TopicSources(Topic.INSURANCE, "insurance master policy association shall maintain owner coverage deductible",
                 ("evidence_of_insurance", "insurance_policy", "annual_disclosure", "declaration"), ()),
    TopicSources(Topic.ARCHITECTURE, "architectural approval improvements alterations application committee",
                 ("policy", "declaration", "operating_rules"), ("garage being used", "sign")),
    TopicSources(Topic.MAINTENANCE, "maintenance repair responsibility association owner exclusive use common area",
                 ("declaration", "policy"), ()),
    TopicSources(Topic.LANDSCAPING, "landscaping exclusive use common area patio maintenance plants",
                 ("declaration", "operating_rules"), ()),
    TopicSources(Topic.PESTS, "pest control termites association maintenance", ("declaration", "contract"), ()),
    TopicSources(Topic.ASSESSMENTS, "assessments due late charges collection payment delinquent",
                 ("policy", "annual_disclosure", "declaration"), ()),
    TopicSources(Topic.ESCROW, "transfer disclosure documents fees sale of unit", ("resale_disclosure", "policy"), ()),
    TopicSources(Topic.GOVERNANCE, "meetings of the board notice agenda members election",
                 ("bylaws", "election_rules", "minutes", "agenda"), ()),
    TopicSources(Topic.UTILITIES, "utilities water service association common meter", ("declaration",), ()),
)
