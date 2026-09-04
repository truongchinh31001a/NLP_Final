from dataclasses import asdict, dataclass
from typing import Any, TypedDict


@dataclass(slots=True)
class WorkflowNode:
    id: str
    label: str
    description: str


@dataclass(slots=True)
class WorkflowEdge:
    source: str
    target: str
    label: str = ""


class WorkflowState(TypedDict, total=False):
    events: list[str]


class LearningWorkflowGraph:
    """Static workflow graph for the conversation-to-activity learning flow.

    The runtime still calls existing services directly. This graph makes the
    orchestration contract explicit and can be compiled with LangGraph for
    inspection or future node-by-node execution.
    """

    def __init__(self) -> None:
        self.nodes = [
            WorkflowNode(
                "conversation_api",
                "Conversation API",
                "Receive learner turns.",
            ),
            WorkflowNode(
                "route_intent",
                "Route Intent",
                "Classify practice, review, progress, explain, or profile turns.",
            ),
            WorkflowNode(
                "activity_created",
                "Create Activity",
                "Create a stable learning activity identity.",
            ),
            WorkflowNode(
                "activity_generating",
                "Activity Generating",
                "Mark practice generation in progress.",
            ),
            WorkflowNode("parse", "Parse Intent", "Normalize learner text."),
            WorkflowNode("profile", "Load Profile", "Load long-term learner state."),
            WorkflowNode("plan", "Build Plan", "Choose target skill and difficulty."),
            WorkflowNode("retrieve", "Retrieve", "Fetch grounded knowledge chunks."),
            WorkflowNode("generate", "Generate", "Create candidate exercises."),
            WorkflowNode("validate", "Validate", "Check exercise schema and answers."),
            WorkflowNode(
                "activity_ready",
                "Activity Ready",
                "Link generation run to the activity.",
            ),
            WorkflowNode("serve", "Serve", "Return the exercise set to the learner."),
            WorkflowNode(
                "activity_submitted",
                "Submit Activity",
                "Receive answers by activity id.",
            ),
            WorkflowNode("grade", "Grade", "Score submitted answers."),
            WorkflowNode("diagnose", "Diagnose", "Classify answer-level mistakes."),
            WorkflowNode("mastery", "Update Mastery", "Apply BKT skill updates."),
            WorkflowNode("recommend", "Recommend", "Rank next learning activity."),
            WorkflowNode("review", "Review", "Create feedback and next steps."),
            WorkflowNode(
                "activity_completed",
                "Activity Completed",
                "Persist the completed practice result.",
            ),
            WorkflowNode(
                "accept_recommendation",
                "Accept Recommendation",
                "Create the next activity from structured fields.",
            ),
        ]
        self.generation_edges = [
            WorkflowEdge("conversation_api", "route_intent"),
            WorkflowEdge("route_intent", "activity_created"),
            WorkflowEdge("activity_created", "activity_generating"),
            WorkflowEdge("activity_generating", "parse"),
            WorkflowEdge("parse", "profile"),
            WorkflowEdge("profile", "plan"),
            WorkflowEdge("plan", "retrieve"),
            WorkflowEdge("retrieve", "generate"),
            WorkflowEdge("generate", "validate"),
            WorkflowEdge("validate", "activity_ready"),
            WorkflowEdge("activity_ready", "serve"),
            WorkflowEdge("validate", "generate", "retry if invalid"),
        ]
        self.scoring_edges = [
            WorkflowEdge("activity_submitted", "grade"),
            WorkflowEdge("grade", "diagnose"),
            WorkflowEdge("diagnose", "mastery"),
            WorkflowEdge("mastery", "recommend"),
            WorkflowEdge("recommend", "review"),
            WorkflowEdge("review", "activity_completed"),
        ]
        self.recommendation_edges = [
            WorkflowEdge("recommend", "accept_recommendation"),
            WorkflowEdge("accept_recommendation", "activity_created"),
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": "langgraph-compatible",
            "nodes": [asdict(node) for node in self.nodes],
            "generation_edges": [asdict(edge) for edge in self.generation_edges],
            "scoring_edges": [asdict(edge) for edge in self.scoring_edges],
            "recommendation_edges": [
                asdict(edge) for edge in self.recommendation_edges
            ],
        }

    def compile_langgraph(self):
        from langgraph.graph import END, START, StateGraph

        graph = StateGraph(WorkflowState)
        for node in self.nodes:
            graph.add_node(node.id, self._node_runner(node.id))

        for edge in self.generation_edges:
            if edge.label:
                continue
            graph.add_edge(edge.source, edge.target)
        graph.add_edge(START, "conversation_api")
        graph.add_edge("serve", END)
        return graph.compile()

    def _node_runner(self, node_id: str):
        def run(state: WorkflowState) -> WorkflowState:
            events = [*state.get("events", []), node_id]
            return {"events": events}

        return run
