-- Top two genres by 2021 revenue for each billing country (SQLite, read-only).
WITH period_lines AS (
    -- Filter invoices to the half-open period first; InvoiceDate is ISO text, so text comparison is ordered.
    SELECT
        inv.BillingCountry AS country,
        trk.GenreId AS genre_id,
        -- Round unit price to whole cents before multiplying by quantity.
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS quantity
    FROM Invoice AS inv
    INNER JOIN InvoiceLine AS il
        ON il.InvoiceId = inv.InvoiceId
    INNER JOIN Track AS trk
        ON trk.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
),
country_genre AS (
    SELECT
        pl.country,
        pl.genre_id,
        gen.Name AS genre,
        SUM(pl.line_cents) AS revenue_cents,
        SUM(pl.quantity) AS units
    FROM period_lines AS pl
    INNER JOIN Genre AS gen
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
        -- ROW_NUMBER gives distinct ranks; ties broken by smaller GenreId.
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
