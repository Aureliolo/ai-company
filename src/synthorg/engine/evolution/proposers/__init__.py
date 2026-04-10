"""Evolution proposer strategy implementations.

Three pluggable proposer implementations:
  - SeparateAnalyzerProposer: Dedicated LLM call analyzing evolution context
  - SelfReportProposer: Lightweight heuristic-based proposer
  - CompositeProposer: Routes between failure/success paths based on trajectory
"""
