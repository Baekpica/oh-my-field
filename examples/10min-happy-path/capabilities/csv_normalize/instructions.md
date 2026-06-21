# csv_normalize

## Purpose
Normalize a messy orders CSV into strict, schema-checked JSON. These instructions
were distilled from a successful Opus run (see `source_evidence_id` in
`capability.yaml`) so a smaller model can reproduce the result.

## Goal
Read the messy orders CSV the user provides and write a single normalized JSON
document to `output/normalized.json`.

## Output format
- Write **only** JSON — no prose, no markdown, **no ```code fences```**.
- Shape: `{"records": [ ... ]}`.
- Sort `records` by `order_id` **ascending**, treating `order_id` as an integer.

## Each record — exactly these six keys, nothing else
| key          | type    | rule                                                                            |
|--------------|---------|---------------------------------------------------------------------------------|
| `order_id`   | integer | parse the `order_id` column as an int (strip surrounding whitespace)             |
| `customer`   | string  | the `customer` column, trimmed                                                   |
| `email`      | string  | the `email` column, trimmed **and lowercased**                                   |
| `amount_usd` | number  | the `amount` column with `$` and thousands `,` removed, numeric (2 decimals)     |
| `ordered_on` | string  | the `ordered_on` column normalized to **`YYYY-MM-DD`**                           |
| `fulfilled`  | boolean | JSON `true`/`false` per the mapping below                                        |

## Field rules
- **Dates** may be `M/D/YYYY`, `M-D-YYYY`, `Mon D, YYYY` (e.g. `Jan 5, 2026`), or
  already-ISO `YYYY-MM-DD`. Month-first (US) ordering. Always emit zero-padded
  `YYYY-MM-DD` (`12/31/2025` → `2025-12-31`).
- **Amounts**: drop `$` and `,`, parse as a number rounded to 2 decimals
  (`"$1,200.50"` → `1200.5`, `"2,000"` → `2000.0`, `1200` → `1200.0`).
- **Booleans**: `yes`, `y`, `true`, `1` (case-insensitive) → `true`; anything
  else, including blank → `false`.
- **Emails**: lowercase + trim.

## Row filtering (apply in this order — these are the easy ones to get wrong)
1. **Drop fully-blank rows** (every column empty).
2. **Drop any row whose `order_id` is empty or not an integer.**
   Example: `,Eve,eve@baz.com,...` → dropped (no order_id).
3. **Drop any row whose `email` is empty.** Check the email column itself, not
   whether the row looks complete otherwise.
   Example: `1005,Dan,,$10.00,03-15-2026,1` → dropped (empty email), even though
   it has an order_id and an amount.
4. **Deduplicate by `order_id`, keeping the first occurrence.** Later rows with an
   `order_id` already seen are dropped.
   Example: a second `1001,...` row after the first `1001,...` → dropped.

A correct result keeps **only** rows that survive all four filters. Do not include
a dropped row's data anywhere in the output.

## Completion gate
- Run the harness checks (`harness.yaml`) and the contract (`contracts/`) before
  declaring done. Do not emit mock/placeholder data — derive every record from the
  input CSV.
