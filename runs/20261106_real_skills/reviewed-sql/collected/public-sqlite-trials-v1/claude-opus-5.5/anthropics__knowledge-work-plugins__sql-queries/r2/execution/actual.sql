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
),
country_genre AS (
    SELECT
        country,
        genre_id,
        CAST(SUM(line_cents) AS INTEGER) AS revenue_cents,
        CAST(SUM(qty) AS INTEGER) AS units
    FROM line_sales
    GROUP BY country, genre_id
),
ranked AS (
    SELECT
        cg.country,
        cg.genre_id,
        g.Name AS genre,
        cg.revenue_cents,
        cg.units,
        ROW_NUMBER() OVER (
            PARTITION BY cg.country
            ORDER BY cg.revenue_cents DESC, cg.genre_id ASC
        ) AS country_rank
    FROM country_genre AS cg
    LEFT JOIN Genre AS g ON g.GenreId = cg.genre_id
)
SELECT
    country,
    CAST(genre_id AS INTEGER) AS genre_id,
    genre,
    revenue_cents,
    units,
    CAST(country_rank AS INTEGER) AS country_rank
FROM ranked
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
