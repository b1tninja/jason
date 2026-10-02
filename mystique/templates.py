"""Mystique's letter templates in Drive, and where the letters made from them are filed.

The templates live in "My Drive/Templates" and were built from "My Drive/Letterhead" (the logo header), with the
Letterhead's footer, which read "LETTERHEAD", replaced by the mailing address (mail.py). A filled hearing or decision
notice goes in "My Drive/Disciplinary", in a folder for the matter, "<address> - <matter> <M-D-YY>", as the board has
filed them since 2026.

The units' city line is the one the association's own April 14, 2026 decision letter printed for a unit on
Mesmerizing Walk.
"""

from __future__ import annotations

from jason.community.templates import DocumentTemplate, TemplateKind

LETTERHEAD_DOC = "1PBWiv7bjmwfZeX_snM3reiabiR9A8GELhrTstoIqnwo"
MY_DRIVE = "0ACGfgho-G00gUk9PVA"
DISCIPLINARY_FOLDER = "17mDrjjJyPqjaiIKtf6LV6ixODCW2nqPu"
TEMPLATES_FOLDER = "13ZFNKBRMsJywFVZ0XnWA_3jp0ntXaJnu"   # My Drive/Templates, built October 1, 2026
# My Drive/Meetings: one folder a year ("2026") holds the agendas ("Agenda for 10/20/26") and minutes. It and the Templates
# folder are private to the association's account (checked 2026-09-30); a board packet Doc goes in the year's folder.
MEETINGS_FOLDER = "1N2zznlTagwS5wUeZrcBa4V3KuSZVxcbo"
# My Drive/Templates/PayHOA Broadcasts: one Doc per PayHOA broadcast template (jason broadcast --sync-docs);
# the first sync created it October 1, 2026.
BROADCASTS_FOLDER = "1wnFv8QewIEYNm6uSp7xSpCS6fK83Vti3"
BROADCASTS_FOLDER_NAME = "PayHOA Broadcasts"

# The letterhead as an email frame (jason broadcast --letterhead): the Letterhead Doc's first-page header is the logo
# (49 x 72 pt) centered over the name in Century Gothic 24 pt bold; its footer is the mailing address. PayHOA's own
# email layout already puts the association's logo (PayHOA's organization logo, public at core.payhoa.com/org-logo/27889
# with a signed link) centered above the message card, so for PayHOA the frame is the name banner at the top of the card
# and the address footer, and EMAIL_LOGO_URL stays empty: a logo in the body would show twice. Seen in the Sep 15, 2026
# meeting notice (October 1, 2026); its layout is kept as data/brand/payhoa-wrapper.html for previews.
EMAIL_LOGO_URL = ""
EMAIL_LETTERHEAD_NAME = "MYSTIQUE COMMUNITY ASSOCIATION"
EMAIL_LETTERHEAD_FONT = "'Century Gothic', Futura, 'Trebuchet MS', Arial, sans-serif"
FOOTER = "901 H St Ste 120, PMB 188, Sacramento, CA 95814"
# Where an owner mails a form back (the board, October 1, 2026): the Association by name, no officer's title, which
# readers took for a person to address. The designated recipient for official notices (Civil Code 4035) stays in the
# annual budget report and policy statement, where the law names it.
MAILING_ADDRESS_LINES = ("Mystique Community Association", "901 H ST STE 120 PMB 188", "Sacramento, CA 95814")
UNIT_CITY_STATE_ZIP = "Sacramento, CA 95835"

TEMPLATES: tuple[DocumentTemplate, ...] = (
    DocumentTemplate(TemplateKind.LETTERHEAD, "Template - Letter on Letterhead", "1Ka_KDdXlOhO6HfW5dTktc-3njSEwkgoAMN2AdsiRpuE"),
    DocumentTemplate(TemplateKind.HEARING_NOTICE, "Template - Notice of Hearing", "143y0KQTVuXQ3rePizCYvCvIsQ55fz43llnnm2fScdlg", folder_id=DISCIPLINARY_FOLDER,
                     optional=("CURE",), link_tokens=("ZOOM_LINK",), authority="CIV 5855(a)-(c), 4935(b)"),
    DocumentTemplate(TemplateKind.DECISION_NOTICE, "Template - Notice of Decision", "1lkDz4lWAJXPQP03ix15uAvd6neIKofLk9wWMGUXbrS0", folder_id=DISCIPLINARY_FOLDER,
                     authority="CIV 5855(f), 5910"),
    DocumentTemplate(TemplateKind.AGENDA, "Template - Board Meeting Agenda", "118KnW6AQ0K4xIXzmXvs4pn_sy_y-VNjKzLKcr-YLhgM", link_tokens=("ZOOM_LINK",),
                     authority="CIV 4920, 4926(a), 4930, 4935(a)"),
)
