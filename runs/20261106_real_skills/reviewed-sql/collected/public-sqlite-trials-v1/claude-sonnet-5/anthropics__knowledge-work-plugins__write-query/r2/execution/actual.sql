
WITH sold AS (
    SELECT
        inv.BillingCountry AS country,
        t.GenreId AS genre_id,
        g.Name AS genre,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_revenue_cents,
        il.Quantity AS qty
    FROM Invoice AS inv
    JOIN InvoiceLine AS il
        ON il.InvoiceId = inv.InvoiceId
    JOIN Track AS t
        ON t.TrackId = il.TrackId
    JOIN Genre AS g
        ON g.GenreId = t.GenreId
    WHERE inv.InvoiceDate >= '2021-01-01'
      AND inv.InvoiceDate < '2022-01-01'
),
genre_totals AS (
    SELECT
        country,
        genre_id,
        genre,
        SUM(line_revenue_cents) AS revenue_cents,
        SUM(qty) AS units
    FROM sold
    GROUP BY country, genre_id, genre
),
ranked AS (
    SELECT
        country,
        genre_id,
        genre,
        revenue_cents,
        units,
        ROW_NUMBER() OVER (
            PARTITION BY country
            ORDER BY revenue_cents DESC, genre_id ASC
        ) AS country_rank
    FROM genre_totals
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
