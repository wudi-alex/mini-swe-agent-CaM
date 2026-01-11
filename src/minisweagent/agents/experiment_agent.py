"""Experiment agents with folder structure rendering."""

from minisweagent.agents.default import DefaultAgent
from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.agents.experiment_mixin import ExperimentMixin


class ExperimentAgent(ExperimentMixin, DefaultAgent):
    """DefaultAgent with folder structure rendering (for batch processing)."""
    pass


class InteractiveExperimentAgent(ExperimentMixin, InteractiveAgent):
    """InteractiveAgent with folder structure rendering (for single instance)."""
    pass