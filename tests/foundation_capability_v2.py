"""Historical versioned compatibility check; never a frozen-evaluation replacement."""
from policy_experiments.archive import module
_historical = module('foundation_v2', 'foundation_capability_v2')
NEW, VERSION = _historical.NEW, _historical.VERSION
observe, capture = _historical.observe, _historical.capture
