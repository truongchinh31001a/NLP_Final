import json
import os
import re
from typing import Any

from langchain_core.runnables import Runnable, RunnableLambda
from langchain_openai import ChatOpenAI

from app.config import AppConfig


class LangChainModelFactory:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def build_generation_runnable(self) -> Runnable[Any, Any]:
        backend = self._resolve_backend()

        if backend == "ollama":
            return self._build_ollama_runnable()

        if backend == "openai":
            return ChatOpenAI(
                model=self.config.openai_model,
                temperature=self.config.openai_temperature,
            )

        return RunnableLambda(self._fallback_json_response)

    def get_backend_name(self) -> str:
        backend = self._resolve_backend()
        if backend == "ollama":
            return f"langchain-ollama:{self.config.ollama_model}"
        if backend == "openai":
            return f"langchain-openai:{self.config.openai_model}"
        return "langchain-fallback:runnable-lambda"

    def _resolve_backend(self) -> str:
        requested = self.config.llm_backend.strip().lower()
        if requested in {"fallback", "local", "seed"}:
            return "fallback"
        if requested in {"ollama", "openai"}:
            return requested
        if requested != "auto":
            raise ValueError(
                "Unsupported LLM_BACKEND. Use auto, openai, ollama, or fallback."
            )
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        return "fallback"

    def _build_ollama_runnable(self) -> Runnable[Any, Any]:
        try:
            from langchain_ollama import ChatOllama
        except ImportError as exc:
            raise RuntimeError(
                "LLM_BACKEND=ollama requires the `langchain-ollama` package. "
                "Install dependencies with `pip install -r requirements.txt`."
            ) from exc

        return ChatOllama(
            model=self.config.ollama_model,
            base_url=self.config.ollama_base_url,
            temperature=self.config.ollama_temperature,
            format="json",
        )

    def _fallback_json_response(self, prompt_value: Any) -> str:
        prompt_text = (
            prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)
        )

        topic = self._extract_field(prompt_text, "topic", "grammar")
        difficulty = self._extract_field(prompt_text, "difficulty", "easy")
        exercise_type = self._extract_field(prompt_text, "exercise_type", "grammar_mcq")
        num_questions = int(self._extract_field(prompt_text, "num_questions", "5"))

        payload = {
            "exercises": [
                self._build_fallback_item(topic, difficulty, exercise_type, index)
                for index in range(1, num_questions + 1)
            ]
        }
        return json.dumps(payload, ensure_ascii=True)

    def _extract_field(self, text: str, field_name: str, default: str) -> str:
        pattern = rf"(?im)^(?:human:\s*)?{field_name}\s*:\s*(.+)$"
        matches = re.findall(pattern, text)
        if matches:
            return matches[-1].strip()
        return default

    def _build_fallback_item(
        self,
        topic: str,
        difficulty: str,
        exercise_type: str,
        index: int,
    ) -> dict[str, Any]:
        topic_text = topic.replace("_", " ")

        if exercise_type == "fill_blank":
            return {
                "exercise_id": f"{topic}-{index}",
                "question_text": f"Fill in the blank: This practice focuses on {topic_text} at {difficulty} level number {index}. ____",
                "options": [],
                "correct_answer": "today",
                "explanation": f"Baseline fallback item for {topic_text}. Replace with a real chat model when API access is ready.",
            }

        return {
            "exercise_id": f"{topic}-{index}",
            "question_text": f"Question {index}: Which option best matches a {difficulty} lesson about {topic_text}?",
            "options": [
                {
                    "label": "A",
                    "text": f"A correct placeholder answer for {topic_text}",
                    "is_correct": True,
                },
                {
                    "label": "B",
                    "text": f"A distractor related to {topic_text}",
                    "is_correct": False,
                },
                {
                    "label": "C",
                    "text": "A distractor with wrong grammar or meaning",
                    "is_correct": False,
                },
                {
                    "label": "D",
                    "text": "A distractor with incorrect structure",
                    "is_correct": False,
                },
            ],
            "correct_answer": "A",
            "explanation": f"Baseline fallback item for {topic_text}. Replace with a real chat model when API access is ready.",
        }
