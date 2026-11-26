WITH sales_by_country_genre AS (
    SELECT
        i.BillingCountry AS country,
        t.GenreId AS genre_id,
        g.Name AS genre,
        SUM(CAST(ROUND(il.UnitPrice * 100.0, 0) AS INTEGER) * il.Quantity) AS revenue_cents,
        SUM(il.Quantity) AS units
    FROM Invoice AS i
    JOIN InvoiceLine AS il
      ON il.InvoiceId = i.InvoiceId
    JOIN Track AS t
      ON t.TrackId = il.TrackId
    JOIN Genre AS g
      ON g.GenreId = t.GenreId
    WHERE i.InvoiceDate >= '2021-01-01'
      AND i.InvoiceDate < '2022-01-01'
    GROUP BY
        i.BillingCountry,
        t.GenreId,
        g.Name
), ranked AS (
    SELECT
        country,
        genre_id,
        genre,
        CAST(revenue_cents AS INTEGER) AS revenue_cents,
        CAST(units AS INTEGER) AS units,
        ROW_NUMBER() OVER (
            PARTITION BY country
            ORDER BY revenue_cents DESC, genre_id ASC
        ) AS country_rank
    FROM sales_by_country_genre
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
