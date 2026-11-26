WITH line_sales AS (
    SELECT
        i.BillingCountry AS country,
        t.GenreId AS genre_id,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS qty
    FROM Invoice AS i
    JOIN InvoiceLine AS il ON il.InvoiceId = i.InvoiceId
    JOIN Track AS t ON t.TrackId = il.TrackId
    WHERE i.InvoiceDate >= '2021-01-01'
      AND i.InvoiceDate < '2022-01-01'
      AND il.Quantity > 0
),
grouped AS (
    SELECT country, genre_id,
           SUM(line_cents) AS revenue_cents,
           SUM(qty) AS units
    FROM line_sales
    GROUP BY country, genre_id
),
ranked AS (
    SELECT g.country, g.genre_id, gn.Name AS genre,
           g.revenue_cents, g.units,
           ROW_NUMBER() OVER (
               PARTITION BY g.country
               ORDER BY g.revenue_cents DESC, g.genre_id ASC
           ) AS country_rank
    FROM grouped AS g
    LEFT JOIN Genre AS gn ON gn.GenreId = g.genre_id
)
SELECT
    CAST(country AS TEXT) AS country,
    CAST(genre_id AS INTEGER) AS genre_id,
    CAST(genre AS TEXT) AS genre,
    CAST(revenue_cents AS INTEGER) AS revenue_cents,
    CAST(units AS INTEGER) AS units,
    CAST(country_rank AS INTEGER) AS country_rank
FROM ranked
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
