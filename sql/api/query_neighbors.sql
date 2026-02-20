SELECT
    neighbor_pitcher, neighbor_season, similarity_score, rank
FROM gold_repertoire_shape_neighbors
WHERE source_pitcher = {pitcher}
  AND source_season = {season}
ORDER BY rank
