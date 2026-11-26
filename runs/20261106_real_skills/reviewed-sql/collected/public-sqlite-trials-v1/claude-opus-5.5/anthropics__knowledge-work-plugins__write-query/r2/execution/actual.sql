-- Top two genres by 2021 revenue per billing country (read-only SQLite).
WITH period_lines AS (
    -- Filter invoices early; InvoiceDate is stored as 'YYYY-MM-DD HH:MM:SS' text.
    SELECT
        inv.BillingCountry AS country,
        trk.GenreId AS genre_id,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS quantity
    FROM Invoice AS inv
    JOIN InvoiceLine AS il
        ON il.InvoiceId = inv.InvoiceId
    JOIN Track AS trk
        ON trk.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
      AND inv.BillingCountry IS NOT NULL
),
country_genre AS (
    SELECT
        pl.country,
        pl.genre_id,
        gen.Name AS genre,
        SUM(pl.line_cents) AS revenue_cents,
        SUM(pl.quantity) AS units
    FROM period_lines AS pl
    JOIN Genre AS gen
        ON gen.GenreId = pl.genre_id
    GROUP BY pl.country, pl.genre_id, gen.Name
),
ranked AS (
    SELECT
        cg.*,
        ROW_NUMBER() OVER (
            PARTITION BY cg.country
            ORDER BY cg.revenue_cents DESC, cg.genre_id ASC
        ) AS country_rank
    FROM country_genre AS cg
)
SELECT
    country,
    genre_id,
    genre,
    revenue_cents,
    units,
    country_rank
FROM ranked
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
