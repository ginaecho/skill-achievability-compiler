WITH lines AS (
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
agg AS (
    SELECT country, genre_id,
           SUM(line_cents) AS revenue_cents,
           SUM(qty) AS units
    FROM lines
    GROUP BY country, genre_id
),
ranked AS (
    SELECT a.country, a.genre_id, g.Name AS genre,
           a.revenue_cents, a.units,
           ROW_NUMBER() OVER (PARTITION BY a.country
                              ORDER BY a.revenue_cents DESC, a.genre_id ASC) AS country_rank
    FROM agg AS a
    LEFT JOIN Genre AS g ON g.GenreId = a.genre_id
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
