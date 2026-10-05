"""Mystique's PayHOA request forms, and which form an emailed request belongs on by its topic.

The three forms and their question ids are PayHOA's (read from the stored requests, September 29, 2026). Each asks
for a title and a message; the attachment is optional. A draft built from an email thread takes the first form whose
topics the thread carries, else the General Request.
"""

from __future__ import annotations

from jason.community.request_forms import RequestForm, RequestGroup, RequestKind
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

# The open requests as a person sorted them for the request sheet (``jason request-sheet``): whose repair each is, the
# vendor or trade it goes to, and the issue in a line. A request with no row is listed as unclear.
A, H, U, N = RequestKind.ASSOCIATION, RequestKind.HOMEOWNER, RequestKind.UNCLEAR, RequestKind.NOT_MAINTENANCE
REQUEST_GROUPS: tuple[RequestGroup, ...] = (
    RequestGroup(260564, A, "City Gutters", "Exterior gutter pulled off the fascia at Building 4."),
    RequestGroup(256609, A, "Certified Handyman Service", "Caulk above the door frame is cracked."),
    RequestGroup(247055, A, "Landscaping", "A sprinkler sprays the house at 4 a.m."),
    RequestGroup(241161, A, "Landscaping", "Asks for a fruit tree where one was removed."),
    RequestGroup(227754, A, "Good Life Construction", "Vehicle collision damaged the garage wall and door."),
    RequestGroup(223260, A, "More than one trade", "Inspection photos: flashing at the front, drain grate at the back."),
    RequestGroup(220090, A, "HighClass Window and Gutter", "Second-floor gutter is clogged and the seam is leaking."),
    RequestGroup(189766, A, "Mirowski Electric", "Street light at Whimsical Lane and Picasso flickers."),
    RequestGroup(187182, A, "Landscaping", "Asks for a lime tree where a tree was removed."),
    RequestGroup(134617, A, "Drainage", "Rainwater collects around the building."),
    RequestGroup(129543, A, "Drainage", "Three drains on Whimsical Lane hold water."),
    RequestGroup(244572, H, "Homeowner", "Bedroom door will not latch. Garage entry door is hard to lock."),
    RequestGroup(234633, H, "Homeowner", "HVAC serving the unit has needed repeated service."),
    RequestGroup(176699, H, "Homeowner", "Front door must be lifted before the lock will turn."),
    RequestGroup(166767, H, "Homeowner", "Asks about cleaning a second-floor window."),
    RequestGroup(257206, U, "No listed garage-door vendor", "Garage door grinds on one side."),
    RequestGroup(172697, U, "Unclear", "Unit address light is out."),
    RequestGroup(172696, U, "Unclear", "Unit address light is out."),
    RequestGroup(160082, U, "Painter", "Paint is peeling on front doorframes in Building 4."),
    RequestGroup(259084, N, "No vendor", "Asks how many parking permits one residence may have."),
    RequestGroup(203251, N, "No vendor", "Asks where a second household car may park."),
    RequestGroup(201850, N, "No vendor", "Complaint about parking and the common area."),
    RequestGroup(163887, N, "No vendor", "Asks for two parking passes."),
)
