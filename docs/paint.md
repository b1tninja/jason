# Paint schedules

Communities keep a palette that says which color goes on which surface (fascia, trim, field, doors) and, often, which scheme
a building takes. The palette is the association's record of what was approved. jason reads it, looks each color up with the
maker, and says when the maker's catalog has moved under it.

- **The schedule is data.** A `PaintSchedule` of `PaintRow`s (`jason.community.paint`), returned by
  `Community.paint_schedules()`. The default is none. A color from another maker (a roof tile) is `Maker.OTHER` and is not checked.
- **The catalog is a reader.** `jason.sources.sherwin_williams.SherwinWilliams` makes one open call,
  `GET api.sherwin-williams.com/prism/v1/colors/sherwin?lng=en-US`: every color with number, name, hex, RGB, LRV, Lab, families,
  and `archived` (discontinued). It needs no login or key (the site's `Origin` and `Referer` are sent). The answer is kept at
  `data/paint/sherwin-williams-colors.json` for a week. The same host gives one color's page data at
  `/shared-color-service/color/byColorNumber/SW7027` (description, coordinating and similar colors). Findings from
  `www.sherwin-williams.com.har`.
- **The check reports; it never edits.** `jason paint --check` marks each color ok, renamed (the printed name is not the
  catalog's; case, spacing, and "grey" for "gray" do not count), discontinued, or not found. The number governs; a renamed or
  discontinued color is for the board and the architectural record.

```bash
jason paint                  # each row with hex, LRV, family, exterior
jason paint --check          # exit 1 when a color differs from the catalog
jason paint --find "gray"    # search the catalog
jason paint --match "SW 7029" --exterior   # closest current colors (CIE76), for a discontinued color or a touch-up
jason paint --page           # data/paint/schedule.html swatches
```

Open: which building takes which scheme is not on the schedule; it is the architectural record's to say, and a scheme-by-building
row would be a new field on `PaintSchedule.buildings`. Prints and screens differ, so hex values are a guide, not a match.
