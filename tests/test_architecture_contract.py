import unittest
from pathlib import Path


class ArchitectureContractTests(unittest.TestCase):
    def test_canonical_api_routes_are_split_from_main(self) -> None:
        route_modules = [
            Path("app/api/routes/conversations.py"),
            Path("app/api/routes/activities.py"),
            Path("app/api/routes/learners.py"),
            Path("app/api/routes/recommendations.py"),
        ]

        for route_module in route_modules:
            with self.subTest(route_module=str(route_module)):
                self.assertTrue(route_module.exists())

        main_lines = Path("app/api/main.py").read_text(encoding="utf-8").splitlines()
        self.assertLess(len(main_lines), 700)

    def test_new_activity_work_uses_plural_activities_package(self) -> None:
        self.assertTrue(Path("app/activities").is_dir())
        self.assertFalse(Path("app/activity").exists())

    def test_conversation_runtime_does_not_import_workflow_graph(self) -> None:
        for path in Path("app/conversation").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=str(path)):
                self.assertNotIn("workflow_graph", text)
                self.assertNotIn("LearningWorkflowGraph", text)

    def test_architecture_doc_names_current_ownership(self) -> None:
        doc = Path("docs/architecture.md").read_text(encoding="utf-8")
        required_terms = [
            "app/api/routes/conversations.py",
            "app/api/routes/activities.py",
            "app/api/routes/learners.py",
            "app/api/routes/recommendations.py",
            "app/activities/",
            "LearningWorkflowGraph",
            "conversation routing does not depend on LangGraph at runtime",
            "microservices",
        ]

        for term in required_terms:
            with self.subTest(term=term):
                self.assertIn(term, doc)


if __name__ == "__main__":
    unittest.main()
