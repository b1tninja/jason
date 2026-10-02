"""PayHOA's own help articles that letters and emails point owners to, by what the owner wants to do.

Read from PayHOA's public help center (intercom.help/payhoa, the "Homeowner How-To Articles" collection) on October 1,
2026. An owner keeps their own name, email, phone, and mailing address in PayHOA (``update-contact``). PayHOA has no owner
setting for how notices are delivered, and owners cannot add contacts or tenants, so everything else (delivery, a second
address, a legal representative, occupancy) comes in through the owner-information form or a request (``request``). A
template names an article as ``{HELP:key}``; ``links.fill_help_tokens`` makes it a link with the article's title.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HelpArticle:
    key: str
    title: str
    url: str
    steps: str = ""          # the steps in a line, for a printed letter where the link cannot be clicked


HELP_CENTER = "https://intercom.help/payhoa/en/collections/1767520-homeowner-how-to-articles"

# The association's own PayHOA sign-up page, checked October 1, 2026: "Welcome to Mystique Community Association", a
# sign-in (email, password, "Forgot your password?") and "Need to create your account?" (an email address, then
# Continue; "Once approved by your community, you'll receive an email registration link"). An owner whose email PayHOA
# has is sent an activation email instead. The help center has no owner article on signing up, so a letter gives
# these steps itself. Approving a registration (People, New Registrations) is a person's.
PORTAL_SIGN_UP = "https://app.payhoa.com/sign-up/27889-mystique-community-association"

HELP_ARTICLES: tuple[HelpArticle, ...] = (
    HelpArticle("update-contact", "How To Update Contact Information",
                "https://intercom.help/payhoa/en/articles/3443969-how-to-update-contact-information",
                steps="in PayHOA, click the person icon at the top right, then Account Settings, then User Settings"),
    HelpArticle("request", "How to Submit a Request",
                "https://intercom.help/payhoa/en/articles/3443109-how-to-submit-a-request",
                steps="in PayHOA, click Requests on the left, choose the request type, then + New Request"),
    HelpArticle("portal", "How to Navigate Your Homeowner Portal",
                "https://intercom.help/payhoa/en/articles/11879789-how-to-navigate-your-homeowner-portal"),
    HelpArticle("documents", "How to View Shared Documents",
                "https://intercom.help/payhoa/en/articles/3443071-how-to-view-shared-documents"),
    HelpArticle("help-center", "PayHOA's homeowner help articles", HELP_CENTER),
)
