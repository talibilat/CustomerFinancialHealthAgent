# Preserve immutable versioned financial snapshots

Each confirmation stores the reported inputs, confirmed classifications, calculated outputs, warnings, and calculation-policy version as an immutable snapshot.
A correction creates a new snapshot that supersedes the earlier record instead of updating it, which keeps historical explanations reproducible and makes failed or concurrent saves safe to reason about.
