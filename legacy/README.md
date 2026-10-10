# Legacy analyses

The study was originally developed across several Jupyter notebooks. Those notebooks are not committed here because they contain duplicated analysis logic, hard-coded local paths, and site-specific implementation details.

The canonical package in `src/stroke_phenotype/` replaces repeated phenotype mask construction, first-event selection, FIN/encounter-based linked validation, monthly count aggregation, MAE/normalized MAE/Pearson correlation calculations, and manuscript table generation.

Legacy notebooks should be retained only in the protected project workspace for provenance. New analysis changes should be made in the package and covered by tests rather than added to another notebook copy.
