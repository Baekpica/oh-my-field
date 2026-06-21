# CSV Normalization Spec (distilled from the Opus run)

Convert a messy orders CSV into one strict JSON document. This is the know-how an
Opus run worked out once; the rules below are what make a cheaper model succeed.

## Output

- Write **only** a JSON object — no prose, no markdown, **no ```code fences```**.
- Shape: `{"records": [ ... ]}`.
- Sort `records` by `order_id` **ascending**, treating `order_id` as an integer.

## Each record (exactly these six keys, no others)

| key          | type    | how to derive it                                                                 |
|--------------|---------|----------------------------------------------------------------------------------|
| `order_id`   | integer | parse the `order_id` column as an int (strip surrounding whitespace)              |
| `customer`   | string  | the `customer` column, trimmed of leading/trailing whitespace                    |
| `email`      | string  | the `email` column, trimmed **and lowercased**                                    |
| `amount_usd` | number  | the `amount` column with `$` and thousands `,` removed, as a number (2 decimals)  |
| `ordered_on` | string  | the `ordered_on` column normalized to **`YYYY-MM-DD`**                            |
| `fulfilled`  | boolean | JSON `true`/`false` (see mapping)                                                 |

## Field rules

- **Dates** (`ordered_on`) may arrive as `M/D/YYYY`, `M-D-YYYY`, `Mon D, YYYY`
  (e.g. `Jan 5, 2026`), or already-ISO `YYYY-MM-DD`. US month-first ordering.
  Always emit zero-padded `YYYY-MM-DD` (e.g. `12/31/2025` → `2025-12-31`).
- **Amounts** (`amount_usd`): drop `$` and any `,`, then parse as a number rounded
  to 2 decimals. `"$1,200.50"` → `1200.5`, `"2,000"` → `2000.0`, `1200` → `1200.0`.
- **Booleans** (`fulfilled`): `yes`, `y`, `true`, `1` (case-insensitive) → `true`;
  everything else, including blank, → `false`.
- **Emails**: lowercase and trim. `"Alice.Park@Example.COM "` → `"alice.park@example.com"`.

## Row filtering (apply in this order)

1. **Drop fully-blank rows** (every column empty).
2. **Drop rows with no usable `order_id`** (empty or non-integer).
3. **Drop rows with an empty `email`**.
4. **Deduplicate by `order_id`, keeping the first occurrence** (later duplicates dropped).

## Worked example (subset)

Input row `1001,Bob Lee,bob@foo.io ,$99.9,2025-01-05,no` →
`{"order_id": 1001, "customer": "Bob Lee", "email": "bob@foo.io", "amount_usd": 99.9, "ordered_on": "2025-01-05", "fulfilled": false}`
