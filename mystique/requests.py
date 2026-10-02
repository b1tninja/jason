"""Mystique's PayHOA request forms, and which form an emailed request belongs on by its topic.

The three forms and their question ids are PayHOA's (read from the stored requests, September 29, 2026). Each asks
for a title and a message; the attachment is optional. A draft built from an email thread takes the first form whose
topics the thread carries, else the General Request.
"""

from __future__ import annotations

from jason.community.request_forms import RequestForm
from jason.community.topics import Topic

REQUEST_FORMS: tuple[RequestForm, ...] = (
    RequestForm("Architectural Request", 55147, 194103, 194104, 194105, (Topic.ARCHITECTURE,)),
    RequestForm("Maintenance Request", 55146, 194100, 194101, 194102,
                (Topic.MAINTENANCE, Topic.LANDSCAPING, Topic.PESTS, Topic.UTILITIES, Topic.BINS)),
    RequestForm("General Request", 55145, 194097, 194098, 194099),
)

# Topics that are a request of the association when an owner raises them (not a question answered by a document).
REQUEST_TOPICS: tuple[Topic, ...] = (Topic.MAINTENANCE, Topic.LANDSCAPING, Topic.PESTS, Topic.ARCHITECTURE, Topic.PARKING,
                                     Topic.BINS, Topic.NEIGHBORS, Topic.SECURITY, Topic.UTILITIES)
