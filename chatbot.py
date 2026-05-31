from app.bootstrap import build_baseline_pipeline


def main() -> None:
    pipeline = build_baseline_pipeline()
    exercise_set = pipeline.create_exercise_set(
        user_id="demo-user",
        raw_text="Toi muon luyen passive voice 5 cau muc de",
    )

    print("=== Parsed Request ===")
    print(exercise_set.request)
    print()
    print("=== Practice Plan ===")
    print(exercise_set.plan)
    print()
    print("=== Retrieved Chunks ===")
    print(exercise_set.retrieved_chunks)
    print()
    print("=== Generated Exercises ===")
    print(exercise_set.exercises)
    print()
    print("=== Runtime Stack ===")
    print(f"Generator backend: {pipeline.generator.backend_name}")
    print("Retriever backend: LangChain vector store")
    print()
    print("Next implementation target: replace fallback generation with a real chat model if needed.")


if __name__ == "__main__":
    main()
