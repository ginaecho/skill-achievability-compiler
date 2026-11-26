WITH sales AS (
  SELECT
    i.BillingCountry AS country,
    t.GenreId AS genre_id,
    CAST(ROUND(il.UnitPrice * 100) AS INTEGER) * il.Quantity AS line_revenue_cents,
    il.Quantity AS qty
  FROM Invoice AS i
  JOIN InvoiceLine AS il
    ON il.InvoiceId = i.InvoiceId
  JOIN Track AS t
    ON t.TrackId = il.TrackId
  WHERE i.InvoiceDate >= '2021-01-01'
    AND i.InvoiceDate < '2022-01-01'
),
agg AS (
  SELECT
    country,
    genre_id,
    SUM(line_revenue_cents) AS revenue_cents,
    SUM(qty) AS units
  FROM sales
  GROUP BY country, genre_id
),
ranked AS (
  SELECT
    agg.country AS country,
    agg.genre_id AS genre_id,
    g.Name AS genre,
    agg.revenue_cents AS revenue_cents,
    agg.units AS units,
    ROW_NUMBER() OVER (
      PARTITION BY agg.country
      ORDER BY agg.revenue_cents DESC, agg.genre_id ASC
    ) AS country_rank
  FROM agg
  JOIN Genre AS g
    ON g.GenreId = agg.genre_id
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
