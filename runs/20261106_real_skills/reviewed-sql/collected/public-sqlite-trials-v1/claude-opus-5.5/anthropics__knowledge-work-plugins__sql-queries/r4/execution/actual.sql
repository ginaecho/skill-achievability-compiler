WITH line_sales AS (
    SELECT
        i.BillingCountry AS country,
        t.GenreId AS genre_id,
        CAST(ROUND(ROUND(il.UnitPrice, 2) * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS qty
    FROM Invoice AS i
    JOIN InvoiceLine AS il ON il.InvoiceId = i.InvoiceId
    JOIN Track AS t ON t.TrackId = il.TrackId
    WHERE i.InvoiceDate >= '2021-01-01'
      AND i.InvoiceDate < '2022-01-01'
      AND il.Quantity > 0
),
grouped AS (
    SELECT
        ls.country,
        ls.genre_id,
        g.Name AS genre,
        CAST(SUM(ls.line_cents) AS INTEGER) AS revenue_cents,
        CAST(SUM(ls.qty) AS INTEGER) AS units
    FROM line_sales AS ls
    LEFT JOIN Genre AS g ON g.GenreId = ls.genre_id
    GROUP BY ls.country, ls.genre_id, g.Name
),
ranked AS (
    SELECT
        country, genre_id, genre, revenue_cents, units,
        ROW_NUMBER() OVER (
            PARTITION BY country
            ORDER BY revenue_cents DESC, genre_id IS NULL, genre_id ASC
        ) AS country_rank
    FROM grouped
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
