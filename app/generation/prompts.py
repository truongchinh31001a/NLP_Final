from langchain_core.prompts import ChatPromptTemplate


def build_generation_prompt(format_instructions: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            (
                "system",
                (
                    "You are an English exercise generator for a personalized learning chatbot. "
                    "Generate exercises that follow the requested topic, difficulty, and exercise type. "
                    "Use the seed examples only as style and distractor-quality references; "
                    "do not copy any seed question exactly. "
                    "Hard output rules: create exactly the requested number of exercises; "
                    "for MCQ-like exercise types, every exercise must contain exactly 4 options "
                    "labeled A, B, C, and D; exactly one option must have is_correct=true; "
                    "correct_answer must be the label of that correct option; "
                    "every exercise should include skill, subtopic, and error_tag metadata; "
                    "question_text and explanation must be non-empty. "
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
                    "target_subtopic: {target_subtopic}\n"
                    "target_error_tag: {target_error_tag}\n"
                    "content_theme: {content_theme}\n"
                    "learner_summary:\n{learner_summary}\n"
                    "retrieved_context:\n{retrieved_context}"
                    "\n\nseed_exercise_examples:\n{seed_exercise_examples}"
                    "\n\nBefore returning the final JSON, silently verify that every MCQ has "
                    "exactly the labels A, B, C, D and one correct option."
                ),
            ),
        ]
    ).partial(format_instructions=format_instructions)
