WITH line_sales AS (
    SELECT
        i.BillingCountry AS country,
        t.GenreId AS genre_id,
        g.Name AS genre,
        CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_cents,
        il.Quantity AS qty
    FROM InvoiceLine AS il
    JOIN Invoice AS i ON i.InvoiceId = il.InvoiceId
    JOIN Track AS t ON t.TrackId = il.TrackId
    JOIN Genre AS g ON g.GenreId = t.GenreId
    WHERE i.InvoiceDate >= '2021-01-01'
      AND i.InvoiceDate < '2022-01-01'
),
country_genre AS (
    SELECT
        country,
        genre_id,
        genre,
        SUM(line_cents) AS revenue_cents,
        SUM(qty) AS units
    FROM line_sales
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
    FROM country_genre
)
SELECT
    country,
    CAST(genre_id AS INTEGER) AS genre_id,
    genre,
    CAST(revenue_cents AS INTEGER) AS revenue_cents,
    CAST(units AS INTEGER) AS units,
    CAST(country_rank AS INTEGER) AS country_rank
FROM ranked
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
