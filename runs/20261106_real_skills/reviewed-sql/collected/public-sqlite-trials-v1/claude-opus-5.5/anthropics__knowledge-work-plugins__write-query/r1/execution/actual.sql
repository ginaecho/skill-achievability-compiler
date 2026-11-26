-- Top-2 genres by 2021 revenue per billing country (SQLite, read-only)
WITH sold_lines AS (
    -- Lines on invoices dated in [2021-01-01, 2022-01-01); InvoiceDate is ISO text
    SELECT
        inv.BillingCountry AS country,
        trk.GenreId AS genre_id,
        -- unit price rounded to whole cents first, then multiplied by quantity
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS quantity
    FROM Invoice AS inv
    INNER JOIN InvoiceLine AS il
        ON il.InvoiceId = inv.InvoiceId
    INNER JOIN Track AS trk
        ON trk.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
      AND il.Quantity > 0  -- only lines that actually sold units
),
country_genre AS (
    SELECT
        sl.country,
        sl.genre_id,
        gen.Name AS genre,
        SUM(sl.line_cents) AS revenue_cents,
        SUM(sl.quantity) AS units
    FROM sold_lines AS sl
    INNER JOIN Genre AS gen
        ON gen.GenreId = sl.genre_id
    GROUP BY sl.country, sl.genre_id, gen.Name
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
    genre_id,
    genre,
    revenue_cents,
    units,
    country_rank
FROM ranked
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
