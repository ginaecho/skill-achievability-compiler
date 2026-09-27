---
name: unit-aware-recipes
description: Scale a recipe to a new number of servings and convert every quantity to metric, using the pint units library.
---
# Recipe scaler

1. Parse `recipe.md` (ingredient lines like `2 cups flour`, `8 oz butter`).
2. Use the Python `pint` library to parse quantities and convert volumes to millilitres and weights to grams.
3. Multiply every quantity by `target_servings / servings`.
4. Write `recipe_scaled.md` with the converted, rounded quantities.
