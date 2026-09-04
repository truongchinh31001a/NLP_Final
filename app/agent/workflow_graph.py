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
    """Static workflow graph for the bounded learning agent.

    The runtime agent still calls existing services directly. This graph makes
    the P2 orchestration contract explicit and can be compiled with LangGraph
    for inspection or future node-by-node execution.
    """

    def __init__(self) -> None:
        self.nodes = [
            WorkflowNode("parse", "Parse Intent", "Normalize learner text."),
            WorkflowNode("profile", "Load Profile", "Load long-term learner state."),
            WorkflowNode("plan", "Build Plan", "Choose target skill and difficulty."),
            WorkflowNode("retrieve", "Retrieve", "Fetch grounded knowledge chunks."),
            WorkflowNode("generate", "Generate", "Create candidate exercises."),
            WorkflowNode("validate", "Validate", "Check exercise schema and answers."),
            WorkflowNode("serve", "Serve", "Return the exercise set to the learner."),
            WorkflowNode("grade", "Grade", "Score submitted answers."),
            WorkflowNode("diagnose", "Diagnose", "Classify answer-level mistakes."),
            WorkflowNode("mastery", "Update Mastery", "Apply BKT skill updates."),
            WorkflowNode("recommend", "Recommend", "Rank next learning activity."),
            WorkflowNode("review", "Review", "Create feedback and next steps."),
        ]
        self.generation_edges = [
            WorkflowEdge("parse", "profile"),
            WorkflowEdge("profile", "plan"),
            WorkflowEdge("plan", "retrieve"),
            WorkflowEdge("retrieve", "generate"),
            WorkflowEdge("generate", "validate"),
            WorkflowEdge("validate", "serve"),
            WorkflowEdge("validate", "generate", "retry if invalid"),
        ]
        self.scoring_edges = [
            WorkflowEdge("grade", "diagnose"),
            WorkflowEdge("diagnose", "mastery"),
            WorkflowEdge("mastery", "recommend"),
            WorkflowEdge("recommend", "review"),
        ]

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine": "langgraph-compatible",
            "nodes": [asdict(node) for node in self.nodes],
            "generation_edges": [asdict(edge) for edge in self.generation_edges],
            "scoring_edges": [asdict(edge) for edge in self.scoring_edges],
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
        graph.add_edge(START, "parse")
        graph.add_edge("serve", END)
        return graph.compile()

    def _node_runner(self, node_id: str):
        def run(state: WorkflowState) -> WorkflowState:
            events = [*state.get("events", []), node_id]
            return {"events": events}

        return run
