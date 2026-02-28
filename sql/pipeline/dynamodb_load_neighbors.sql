SELECT
    source_pitcher, source_season,
    neighbor_pitcher, neighbor_season,
    similarity_score, rank
FROM gold_repertoire_shape_neighbors
WHERE source_season = {season}
ORDER BY source_pitcher, rank
