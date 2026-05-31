from langchain_core.prompts import ChatPromptTemplate


def build_generation_prompt(format_instructions: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an English exercise generator for a personalized learning chatbot. "
                    "Generate exercises that follow the requested topic, difficulty, and exercise type. "
                    "Return JSON only.\n\n"
                    "{format_instructions}"
                ),
            ),
            (
                "human",
                (
                    "topic: {topic}\n"
                    "difficulty: {difficulty}\n"
                    "exercise_type: {exercise_type}\n"
                    "num_questions: {num_questions}\n"
                    "learner_level: {learner_level}\n"
                    "retrieved_context:\n{retrieved_context}"
                ),
            ),
        ]
    ).partial(format_instructions=format_instructions)
