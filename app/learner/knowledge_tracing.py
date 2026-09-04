from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BKTParameters:
    initial_mastery: float = 0.35
    learn_probability: float = 0.12
    guess_probability: float = 0.2
    slip_probability: float = 0.1
    min_mastery: float = 0.02
    max_mastery: float = 0.98


class BayesianKnowledgeTracer:
    """Small Bayesian Knowledge Tracing implementation for binary answers."""

    def __init__(self, parameters: BKTParameters | None = None) -> None:
        self.parameters = parameters or BKTParameters()

    def update(self, prior_mastery: float | None, is_correct: bool) -> float:
        params = self.parameters
        prior = self._clamp(
            params.initial_mastery if prior_mastery is None else prior_mastery,
            params.min_mastery,
            params.max_mastery,
        )

        if is_correct:
            likelihood_known = 1.0 - params.slip_probability
            likelihood_unknown = params.guess_probability
        else:
            likelihood_known = params.slip_probability
            likelihood_unknown = 1.0 - params.guess_probability

        numerator = prior * likelihood_known
        denominator = numerator + ((1.0 - prior) * likelihood_unknown)
        posterior = numerator / denominator if denominator else prior
        learned = posterior + ((1.0 - posterior) * params.learn_probability)
        return self._clamp(learned, params.min_mastery, params.max_mastery)

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(value, upper))

