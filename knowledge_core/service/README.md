# KnowledgeService V1

`KnowledgeService` is the read-only application boundary over
`KnowledgeRepository`. It resolves versioned Knowledge Core data and composes
skill context, prerequisite paths, unlock checks, objectives, CEFR profiles,
assessment profiles, misconceptions, and diagnostic evidence.

```python
from knowledge_core.service import open_knowledge_service

with open_knowledge_service() as knowledge:
    context = knowledge.get_skill_context("grammar.present_simple.affirmative")
    path = knowledge.get_learning_path("grammar.passive.agent_by")
```

Unlock checks are deterministic graph checks only: a skill is unlocked when all
of its direct `prerequisite_of` source skills appear in the caller-provided set.
The service does not estimate mastery or decide what a learner should study.

Adaptive policy, learner state, activity selection, content generation,
feedback generation, and LLM calls remain outside both KnowledgeService and
KnowledgeRepository.
