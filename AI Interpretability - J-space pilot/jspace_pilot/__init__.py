"""J-space pilot: does J-lens-indexed ablation selectively impair tool-information
integration at an LLM agent's decision step?

Modules that need only numpy/pandas (``config``, ``scenarios``, ``agent``,
``validation``, ``metrics``) import without torch, so the benchmark and the
statistics can be tested on any machine. ``model_io``, ``interventions``,
``lens_setup``, ``experiment`` and ``reporting.environment_info`` need torch.
"""

__version__ = "2.0.0"
