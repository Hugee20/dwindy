from reach_history_support import bind_foundation
bind_foundation()
"""Historical assertions bound to a hash-checked candidate, not production."""
from policy_experiments.archive import module
FoundationRunnerTests = module('foundation_v1', 'test_policy_foundation_runner').FoundationRunnerTests
