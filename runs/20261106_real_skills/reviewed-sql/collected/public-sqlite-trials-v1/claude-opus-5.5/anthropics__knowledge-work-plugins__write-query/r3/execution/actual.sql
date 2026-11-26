-- Top two genres by revenue per billing country, invoices dated in calendar 2021.
WITH line_sales AS (
    -- Filter early to the requested half-open date range (ISO text dates).
    SELECT
        inv.BillingCountry AS country,
        trk.GenreId AS genre_id,
        -- Round each unit price to whole cents before multiplying by quantity.
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS quantity
    FROM Invoice AS inv
    JOIN InvoiceLine AS il
        ON il.InvoiceId = inv.InvoiceId
    JOIN Track AS trk
        ON trk.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
),
country_genre AS (
    SELECT
        ls.country,
        ls.genre_id,
        gen.Name AS genre,
        SUM(ls.line_cents) AS revenue_cents,
        SUM(ls.quantity) AS units
    FROM line_sales AS ls
    JOIN Genre AS gen
        ON gen.GenreId = ls.genre_id
    GROUP BY ls.country, ls.genre_id, gen.Name
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
    CAST(rk.country AS TEXT) AS country,
    CAST(rk.genre_id AS INTEGER) AS genre_id,
    CAST(rk.genre AS TEXT) AS genre,
    CAST(rk.revenue_cents AS INTEGER) AS revenue_cents,
    CAST(rk.units AS INTEGER) AS units,
    CAST(rk.country_rank AS INTEGER) AS country_rank
FROM ranked AS rk
WHERE rk.country_rank <= 2
ORDER BY rk.country ASC, rk.country_rank ASC;
