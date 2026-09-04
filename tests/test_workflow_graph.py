import unittest

from app.agent.workflow_graph import LearningWorkflowGraph


class LearningWorkflowGraphTests(unittest.TestCase):
    def test_graph_exposes_p2_learning_loop_nodes(self) -> None:
        graph = LearningWorkflowGraph().as_dict()
        node_ids = {node["id"] for node in graph["nodes"]}
        scoring_edges = {
            (edge["source"], edge["target"])
            for edge in graph["scoring_edges"]
        }
        recommendation_edges = {
            (edge["source"], edge["target"])
            for edge in graph["recommendation_edges"]
        }

        self.assertIn("conversation_api", node_ids)
        self.assertIn("route_intent", node_ids)
        self.assertIn("activity_created", node_ids)
        self.assertIn("activity_ready", node_ids)
        self.assertIn("activity_completed", node_ids)
        self.assertIn("accept_recommendation", node_ids)
        self.assertIn("retrieve", node_ids)
        self.assertIn("diagnose", node_ids)
        self.assertIn("mastery", node_ids)
        self.assertIn(("activity_submitted", "grade"), scoring_edges)
        self.assertIn(("diagnose", "mastery"), scoring_edges)
        self.assertIn(("mastery", "recommend"), scoring_edges)
        self.assertIn(("recommend", "accept_recommendation"), recommendation_edges)
        self.assertIn(
            ("accept_recommendation", "activity_created"),
            recommendation_edges,
        )

    def test_generation_path_can_compile_with_langgraph(self) -> None:
        graph = LearningWorkflowGraph().compile_langgraph()

        result = graph.invoke({"events": []})

        self.assertEqual(
            result["events"],
            [
                "conversation_api",
                "route_intent",
                "activity_created",
                "activity_generating",
                "parse",
                "profile",
                "plan",
                "retrieve",
                "generate",
                "validate",
                "activity_ready",
                "serve",
            ],
        )


if __name__ == "__main__":
    unittest.main()
