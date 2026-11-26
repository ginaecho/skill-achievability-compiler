WITH sold_lines AS (
    SELECT
        inv.BillingCountry AS country,
        trk.GenreId AS genre_id,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_revenue_cents,
        il.Quantity AS line_units
    FROM InvoiceLine AS il
    JOIN Invoice AS inv
        ON inv.InvoiceId = il.InvoiceId
    JOIN Track AS trk
        ON trk.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
),
country_genre_totals AS (
    SELECT
        sl.country AS country,
        sl.genre_id AS genre_id,
        SUM(sl.line_revenue_cents) AS revenue_cents,
        SUM(sl.line_units) AS units
    FROM sold_lines AS sl
    GROUP BY sl.country, sl.genre_id
),
ranked AS (
    SELECT
        cgt.country AS country,
        cgt.genre_id AS genre_id,
        cgt.revenue_cents AS revenue_cents,
        cgt.units AS units,
        ROW_NUMBER() OVER (
            PARTITION BY cgt.country
            ORDER BY cgt.revenue_cents DESC, cgt.genre_id ASC
        ) AS country_rank
    FROM country_genre_totals AS cgt
)
SELECT
    r.country AS country,
    r.genre_id AS genre_id,
    g.Name AS genre,
    r.revenue_cents AS revenue_cents,
    r.units AS units,
    r.country_rank AS country_rank
FROM ranked AS r
JOIN Genre AS g
    ON g.GenreId = r.genre_id
WHERE r.country_rank <= 2
ORDER BY country ASC, country_rank ASC;
