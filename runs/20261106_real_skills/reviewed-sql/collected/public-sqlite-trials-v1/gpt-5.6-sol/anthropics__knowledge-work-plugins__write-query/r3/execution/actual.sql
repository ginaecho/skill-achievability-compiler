WITH genre_sales AS (
    SELECT
        invoice.BillingCountry AS country,
        track.GenreId AS genre_id,
        genre.Name AS genre,
        CAST(SUM(
            CAST(ROUND(invoice_line.UnitPrice * 100, 0) AS INTEGER)
            * invoice_line.Quantity
        ) AS INTEGER) AS revenue_cents,
        CAST(SUM(invoice_line.Quantity) AS INTEGER) AS units
    FROM Invoice AS invoice
    INNER JOIN InvoiceLine AS invoice_line
        ON invoice_line.InvoiceId = invoice.InvoiceId
    INNER JOIN Track AS track
        ON track.TrackId = invoice_line.TrackId
    INNER JOIN Genre AS genre
        ON genre.GenreId = track.GenreId
    WHERE invoice.InvoiceDate >= '2021-01-01'
      AND invoice.InvoiceDate < '2022-01-01'
    GROUP BY
        invoice.BillingCountry,
        track.GenreId,
        genre.Name
),
ranked_genres AS (
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
    FROM genre_sales
)
SELECT
    country,
    genre_id,
    genre,
    revenue_cents,
    units,
    country_rank
FROM ranked_genres
WHERE country_rank <= 2
ORDER BY country ASC, country_rank ASC;
