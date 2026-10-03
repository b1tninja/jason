<!--
key: owners-manual
title: Owner's Manual
kind: guide
version: 1
authority: CIV 4340, CIV 4350, CIV 4360, CIV 4765, CIV 5730, CIV 5850
renders: jason manual --render (jason.tasks.manual)

The base of an owner's manual, for any association. It names no association: the profile fills it
(Community.owners_manual(), docs/owners-manual.md). Its parts, in order:

  {PART:front}        the cover
  {PART:welcome}      what the association is, and answers to owners' common questions
  {PART:contacts}     who to contact, and for what
  {EXCERPTS}          the governing documents' own words, each a {QUOTE:key#n} filled from the document as amended
  {INCLUDE:rules}     the operating rules (the rules book and its parts), with the guide's notes beside them
  {INCLUDE:disc}      the discipline policy and schedule of monetary penalties (Civil Code 5850)
  {INCLUDE:coll}      the assessment collection policy and the notice Civil Code 5730 requires
  {INCLUDE:arch}      the architectural review procedure's application (Civil Code 4765)
  {PART:guidance}     anything else the guide says

The manual is a guide; the rules, the policies, and the governing documents it includes are read from
their own sources each time it is rendered, so the guide never keeps a stale copy of them.
-->
{PART:front}

{PART:welcome optional}

{PART:contacts optional}

{EXCERPTS}

{INCLUDE:rules}

{INCLUDE:disc optional}

{INCLUDE:coll optional}

{INCLUDE:arch optional}

{PART:guidance optional}
