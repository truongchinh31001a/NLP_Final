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

    def update(
        self,
        prior_mastery: float | None,
        is_correct: bool,
        *,
        attempts_count: int = 0,
        repeated_error_count: int = 0,
    ) -> float:
        params = self.parameters_for_history(
            attempts_count=attempts_count,
            repeated_error_count=repeated_error_count,
        )
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

    def parameters_for_history(
        self,
        *,
        attempts_count: int = 0,
        repeated_error_count: int = 0,
    ) -> BKTParameters:
        base = self.parameters
        confidence = self._clamp(attempts_count / 12, 0.0, 1.0)
        recurrence = self._clamp(repeated_error_count / 5, 0.0, 1.0)
        return BKTParameters(
            initial_mastery=base.initial_mastery,
            learn_probability=self._clamp(
                base.learn_probability + (0.03 * confidence) - (0.05 * recurrence),
                0.05,
                0.18,
            ),
            guess_probability=self._clamp(
                base.guess_probability - (0.04 * confidence),
                0.12,
                0.25,
            ),
            slip_probability=self._clamp(
                base.slip_probability - (0.05 * recurrence) + (0.02 * confidence),
                0.04,
                0.14,
            ),
            min_mastery=base.min_mastery,
            max_mastery=base.max_mastery,
        )

    def _clamp(self, value: float, lower: float, upper: float) -> float:
        return max(lower, min(value, upper))
