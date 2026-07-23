# ADR 0010: Workload edges declare epistemic status

Every graph edge is classified as observed, derived, or inferred. Inferred edges require a confidence
score, an inference method, and supporting references. The UI renders inferred edges differently and
allows users to hide or threshold them. Causal hypotheses are never serialized as unqualified facts.
