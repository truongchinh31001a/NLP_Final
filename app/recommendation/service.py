from app.schemas import SessionResult


class RecommendationService:
    def recommend(self, result: SessionResult) -> str:
        if result.score < 0.6:
            return (
                f"Keep practicing {result.topic} at an easier or equal difficulty before changing topic."
            )
        if result.score < 0.8:
            return f"Practice {result.topic} again with similar difficulty to stabilize accuracy."
        return f"Increase difficulty or move to a related subtopic after {result.topic}."
