-- Top two genres by revenue per billing country for calendar year 2021.
-- InvoiceDate is stored as ISO-8601 text, so a half-open string range is exact.
WITH period_lines AS (
    SELECT
        inv.BillingCountry                                          AS country,
        trk.GenreId                                                 AS genre_id,
        -- round the unit price to whole cents first, then multiply by quantity
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity    AS line_cents,
        il.Quantity                                                 AS quantity
    FROM Invoice AS inv
    JOIN InvoiceLine AS il
        ON il.InvoiceId = inv.InvoiceId
    JOIN Track AS trk
        ON trk.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate <  '2022-01-01'
      AND il.Quantity > 0              -- only lines that actually sold units
),
country_genre AS (
    SELECT
        pl.country,
        pl.genre_id,
        gen.Name                AS genre,
        SUM(pl.line_cents)      AS revenue_cents,
        SUM(pl.quantity)        AS units
    FROM period_lines AS pl
    JOIN Genre AS gen
        ON gen.GenreId = pl.genre_id
    GROUP BY pl.country, pl.genre_id, gen.Name
),
ranked AS (
    SELECT
        cg.country,
        cg.genre_id,
        cg.genre,
        cg.revenue_cents,
        cg.units,
        ROW_NUMBER() OVER (
            PARTITION BY cg.country
            ORDER BY cg.revenue_cents DESC, cg.genre_id ASC
        ) AS country_rank
    FROM country_genre AS cg
)
SELECT
    country,
    CAST(genre_id AS INTEGER)       AS genre_id,
    genre,
    CAST(revenue_cents AS INTEGER)  AS revenue_cents,
    CAST(units AS INTEGER)          AS units,
    CAST(country_rank AS INTEGER)   AS country_rank
FROM ranked
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
