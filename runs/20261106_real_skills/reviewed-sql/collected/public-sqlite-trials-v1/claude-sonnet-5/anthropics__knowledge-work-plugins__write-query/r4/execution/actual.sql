WITH sold_lines AS (
    SELECT
        inv.BillingCountry AS country,
        t.GenreId AS genre_id,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_revenue_cents,
        il.Quantity AS quantity
    FROM InvoiceLine AS il
    INNER JOIN Invoice AS inv
        ON inv.InvoiceId = il.InvoiceId
    INNER JOIN Track AS t
        ON t.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
),
genre_revenue AS (
    SELECT
        sl.country AS country,
        sl.genre_id AS genre_id,
        SUM(sl.line_revenue_cents) AS revenue_cents,
        SUM(sl.quantity) AS units
    FROM sold_lines AS sl
    GROUP BY sl.country, sl.genre_id
),
ranked AS (
    SELECT
        gr.country AS country,
        gr.genre_id AS genre_id,
        gr.revenue_cents AS revenue_cents,
        gr.units AS units,
        ROW_NUMBER() OVER (
            PARTITION BY gr.country
            ORDER BY gr.revenue_cents DESC, gr.genre_id ASC
        ) AS country_rank
    FROM genre_revenue AS gr
)
SELECT
    r.country AS country,
    r.genre_id AS genre_id,
    g.Name AS genre,
    r.revenue_cents AS revenue_cents,
    r.units AS units,
    r.country_rank AS country_rank
FROM ranked AS r
INNER JOIN Genre AS g
    ON g.GenreId = r.genre_id
WHERE r.country_rank <= 2
ORDER BY r.country ASC, r.country_rank ASC;
