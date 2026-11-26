WITH sold AS (
    SELECT
        inv.BillingCountry AS country,
        t.GenreId AS genre_id,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_revenue_cents,
        il.Quantity AS qty
    FROM Invoice inv
    JOIN InvoiceLine il ON il.InvoiceId = inv.InvoiceId
    JOIN Track t ON t.TrackId = il.TrackId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
),
agg AS (
    SELECT
        country,
        genre_id,
        SUM(line_revenue_cents) AS revenue_cents,
        SUM(qty) AS units
    FROM sold
    GROUP BY country, genre_id
),
ranked AS (
    SELECT
        a.country,
        a.genre_id,
        g.Name AS genre,
        a.revenue_cents,
        a.units,
        ROW_NUMBER() OVER (
            PARTITION BY a.country
            ORDER BY a.revenue_cents DESC, a.genre_id ASC
        ) AS country_rank
    FROM agg a
    JOIN Genre g ON g.GenreId = a.genre_id
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
