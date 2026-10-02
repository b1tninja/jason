# Property histories, title, and county records

Each unit's chain of title runs from the developer's first conveyance to the current owner. Each deed carries its price, computed from the transfer tax, and the base the assessor enrolled after it. The instruments recorded beside each deed are listed, and the chain is audited against the tax bills. The method, its bounds, and the strategies for an open parcel are in the private notes; the skill is in [SKILLS.md](../SKILLS.md#write-the-property-histories). Unit numbers do not identify a parcel here: the community has two numberings, and twelve numbers exist twice.

## The reports

```bash
jason property-history                       # one Markdown page per parcel under data/reports/property-history/
jason property-history --sheet --no-browser  # and one spreadsheet
jason unit-charts --no-browser               # the two unit numberings, their overlap, every sale by building
jason sales-charts --no-browser              # conveyances by year and process, prices, tenure, deed price against the base
jason equity-charts --no-browser             # values and appreciation, a Unit lookup tab, the trend by building
jason sync-characteristics                   # the assessor's living area, bedrooms, baths, year built (run before equity-charts)
```

The parcel pages carry the chain as a flowchart, a tenure gantt, and the unit's value. `market.md` has Mermaid charts of the market by year and a quadrant of every unit. With the `charts` extra (`pip install -e ".[charts]"`), SVG scatter charts with moving averages go under `charts/`; `--no-charts` skips them. Only the spreadsheet steps need Google. The pages are under `data/`, which git ignores.

## The county index

```bash
jason sync-liens            # mechanic's liens naming the developers, the association, and every owner on a chain
jason sync-liens --all      # also association, utility, judgment, tax, default liens, and reconveyances
jason sync-solar            # the solar lease funds' UCC filings, for each unit's solar standing
jason recent-filings --since 2026-09-01
jason title-watch --attention
```

A lien indexes a person, not a parcel. A lien row whose filing dropped the deed's middle name carries `namesakeRisk`: say so. An expired mechanic's lien is unenforceable but still of record. No solar filing is not proof of purchase. Run `sync-solar` again before an escrow question; new filings record with each transfer.

## One unit on a page

```bash
jason brief 201-1170-022-0013 --escrow
```

`jason brief` prints one unit from the stores: the owner, the chain, liens, solar, taxes, members, value, and the audit. `--escrow` adds the lines the association can tell escrow. It reads disk only, so run the syncs first for the newest filings. The same briefs are MCP tools ([mcp.md](mcp.md)).

## Records the association lacks

```bash
jason records-request --pages
```

`jason records-request` lists the recorded instruments the association's record names that no copy on disk carries. For each it gives the county order form's fields, why it matters, its page count, and the copy cost at the county's fees, as Markdown and CSV under `data/reports/`. Reading the instruments themselves, and where OCR defeats it, is in [document-readings.md](document-readings.md).
