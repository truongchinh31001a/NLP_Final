# Knowledge Core V1 — Master Plan

## 1. Purpose

This document is the single source of truth for building **Knowledge Core V1** of the Adaptive AI English Learning Platform.

The goal is to avoid implementing the Knowledge Core source-by-source without a global plan. All V1 sources, schemas, ingestion pipelines, normalization logic, validation rules, review queues, and persistence layers should be tracked against this checklist.

Knowledge Core V1 focuses on **Grammar** only.

The intended architecture is:

```text
Knowledge Sources
        ↓
Source Acquisition
        ↓
Source Inspection / Profiling
        ↓
Source-specific Ingestion
        ↓
Common SourceRecord Layer
        ↓
Normalization / Alignment
        ↓
Canonical Knowledge Model
        ↓
Misconception / Error Modeling
        ↓
Assessment Enrichment
        ↓
Global Validation + Human Review
        ↓
Knowledge Storage
        ↓
KnowledgeRepository
        ↓
KnowledgeService
```

---

## 2. V1 Scope

### 2.1 Domain

```text
Domain: Grammar
```

Vocabulary and lexical-semantic modeling are explicitly deferred to a later version.

### 2.2 Canonical Taxonomy

Current canonical taxonomy:

```text
1 root
10 group nodes
43 atomic grammar skills
54 total taxonomy nodes
```

Status:

- [x] Canonical Grammar V1 taxonomy defined
- [x] Canonical IDs frozen
- [x] 43 atomic skills defined
- [x] Taxonomy hierarchy defined
- [x] External sources prevented from automatically creating new canonical skills
- [x] Taxonomy hash available
- [x] Taxonomy unchanged through completed pipelines

### Canonical rule

External data is treated as **evidence**, not as the canonical curriculum.

```text
External Source
     ↓
Source Evidence
     ↓
Canonical Mapping
     ↓
Existing Skill
```

External records MUST NOT silently mutate the canonical taxonomy.

---

## 3. Canonical Grammar V1

### 3.1 Taxonomy

```text
Grammar
├── Tenses
│   ├── Present Simple
│   │   ├── affirmative
│   │   ├── third-person -s
│   │   ├── negative
│   │   └── questions
│   ├── Present Continuous
│   │   ├── form
│   │   ├── current action
│   │   └── temporary situation
│   ├── Past Simple
│   │   ├── regular verbs
│   │   ├── irregular verbs
│   │   ├── negative
│   │   ├── questions
│   │   └── finished past
│   ├── Past Continuous
│   │   ├── form
│   │   ├── background action
│   │   └── interrupted action
│   └── Present Perfect
│       ├── form
│       ├── past participle
│       ├── experience
│       ├── unfinished time
│       ├── recent result
│       └── since / for
├── Future
│   └── Will
│       ├── prediction
│       ├── spontaneous decision
│       └── offer / promise
├── Modality
│   ├── can ability
│   ├── can permission
│   ├── could past ability
│   ├── must obligation
│   ├── should advice
│   └── must vs have to
├── Determiners
│   └── Articles
│       ├── a / an
│       ├── the
│       ├── zero article
│       ├── first/subsequent mention
│       └── generic reference
├── Clauses
│   └── Conditionals
│       ├── zero
│       ├── first
│       ├── second
│       └── first vs second
└── Passives
    ├── be + past participle
    ├── present simple passive
    ├── past simple passive
    └── agent with by
```

### 3.2 Canonical Atomic Skill IDs

```text
grammar.present_simple.affirmative
grammar.present_simple.third_person_s
grammar.present_simple.negative
grammar.present_simple.questions

grammar.present_continuous.form
grammar.present_continuous.current_action
grammar.present_continuous.temporary_situation

grammar.past_simple.regular_verbs
grammar.past_simple.irregular_verbs
grammar.past_simple.negative
grammar.past_simple.questions
grammar.past_simple.finished_past

grammar.past_continuous.form
grammar.past_continuous.background_action
grammar.past_continuous.interrupted_action

grammar.present_perfect.form
grammar.present_perfect.past_participle
grammar.present_perfect.experience
grammar.present_perfect.unfinished_time
grammar.present_perfect.recent_result
grammar.present_perfect.since_for

grammar.future.will_prediction
grammar.future.will_spontaneous_decision
grammar.future.will_offer_promise

grammar.modality.can_ability
grammar.modality.can_permission
grammar.modality.could_past_ability
grammar.modality.must_obligation
grammar.modality.should_advice
grammar.modality.must_vs_have_to

grammar.articles.a_an
grammar.articles.the_specific_reference
grammar.articles.zero_article
grammar.articles.first_vs_subsequent_mention
grammar.articles.generic_reference

grammar.conditionals.zero
grammar.conditionals.first
grammar.conditionals.second
grammar.conditionals.first_vs_second

grammar.passive.be_past_participle
grammar.passive.present_simple
grammar.passive.past_simple
grammar.passive.agent_by
```

---

## 4. Knowledge Sources V1

The V1 source scope MUST be frozen before further model enrichment.

### 4.1 Required Sources

| Source | Role | Required | Status |
|---|---|---:|---|
| English Grammar Profile (EGP) | Grammar feature evidence, CEFR progression evidence | Yes | Completed |
| CEFR Companion Volume 2020 | Proficiency descriptors, objectives, grammatical accuracy context | Yes | Completed |
| EFCAMDAT | Learner errors, progression, frequency, misconception evidence | Yes | Acquired + inventoried; ingestion completed |
| CLC FCE Dataset | Annotated learner errors, misconception evidence, validation source | Yes | Acquired + inventoried; ingestion completed |

### 4.2 Optional V1 Enrichment Sources

| Source | Role | Required | Status |
|---|---|---:|---|
| Universal Dependencies English EWT | Morphosyntactic / dependency structure evidence | No | Acquired + inventoried; optional structural ingestion completed |
| Write & Improve Corpus | Additional learner error / CEFR validation | No | Acquired + inventoried; optional ingestion not started |

### 4.3 Explicitly Deferred Sources

These sources are useful, but they open a different knowledge domain and MUST NOT be mixed into Grammar V1.

| Source | Future Role |
|---|---|
| English Vocabulary Profile (EVP) | Vocabulary skill taxonomy and lexical CEFR evidence |
| WordNet | Lexical semantic graph: synonymy, antonymy, hypernymy, etc. |

---

## 5. Source Acquisition Checklist

Recommended structure:

```text
data/
└── external/
    ├── english_profile/
    ├── cefr/
    ├── efcamdat/
    ├── clc_fce/
    ├── write_improve/
    └── universal_dependencies/
```

For every source:

- [x] Official source page recorded
- [ ] License / user agreement reviewed
- [ ] Source version recorded
- [ ] Publication year recorded
- [x] Raw files acquired
- [x] File names preserved
- [ ] File hashes calculated
- [x] Restricted raw data added to `.gitignore`
- [x] Raw files not redistributed if license forbids it
- [x] Source metadata registered
- [x] Acquisition notes documented

---

## 6. Source Inventory

Before source-specific extraction logic is finalized, every acquired source should have an inspection report.

Target output:

```text
data/reports/source_inventory/source_inventory.json
```

Current repo output:

```text
data/reports/source_inventory/source_inventory.json
data/reports/source_inventory/source_inventory.md
data/reports/source_inventory/efcamdat_inspection.json
data/reports/source_inventory/clc_fce_inspection.json
data/reports/source_inventory/write_improve_inspection.json
data/reports/source_inventory/ud_ewt_inspection.json
data/reports/source_inventory/error_annotation_comparison.json
data/reports/source_inventory/proficiency_comparison.json
data/reports/source_inventory/inspection_issues.json
data/reports/source_inventory/source_governance.json
data/reports/source_inventory/source_governance.md
```

Current validation:

```text
generated_at: 2026-09-16T10:51:53Z
sources accounted for: 6/6
inspection errors: 0
inspection warnings: 0
validation passed: true
raw data unchanged: true
canonical taxonomy unchanged: true
ingestion artifacts created by inventory: false
```

For each source capture:

```text
source_key
source_name
source_version
file_format
file_count
record_count
schema
important_columns
record_identifier
CEFR_representation
error_annotation_format
missing_value_behavior
duplicate_behavior
known_quirks
license_notes
```

Checklist:

### English Grammar Profile

- [x] File format inspected
- [x] Category structure inspected
- [x] CEFR fields inspected
- [x] 273 valid normalized records
- [x] Source validation clean

### CEFR

- [x] PDF structure inspected
- [x] Selected scales defined
- [x] Descriptor extraction implemented
- [x] 334 descriptor records
- [x] 292 learning objective candidates
- [x] Validation clean

### EFCAMDAT

- [x] Local raw corpus discovered
- [x] Original corpus acquired
- [x] Cleaned corpus acquired
- [x] Error-coded corpus acquired
- [x] Task metadata discovered
- [x] Format inspected
- [x] Schema documented
- [x] Learner / text identifiers documented
- [x] Error annotation representation documented
- [x] Course/proficiency representation documented; CEFR mapping not assumed
- [x] Corpus profiling report produced
- [x] License / user agreement manually reviewed for redistribution constraints
- [ ] File hashes / source manifest promoted from inventory into source metadata

### CLC FCE

- [x] Local source located
- [x] Dataset acquired
- [x] File format inspected
- [x] Annotation schema documented
- [x] Source-native error taxonomy documented
- [x] CEFR / proficiency metadata documented
- [x] Corpus profiling report produced
- [x] Official source URL recorded
- [ ] License checked manually
- [ ] File hashes / source manifest promoted from inventory into source metadata

### Optional Sources

- [x] UD EWT inspected
- [x] Write & Improve inspected
- [x] UD EWT inclusion decision recorded
- [x] Write & Improve inclusion decision recorded
- [ ] Optional-source license checks completed before ingestion

---

## 7. Unified Knowledge Model

All source-specific pipelines should eventually enrich the same canonical model.

### 7.1 Core Entities

```text
KnowledgeVersion
KnowledgeSource
SourceDocument
SourceRecord

Skill
SkillProfile
LearningObjective
SkillLearningObjectiveAlignment
SkillCEFRAlignment

SkillRelationship
RelationshipEvidence

AssessmentCriterion
AssessmentEvidence

ErrorInstance
ErrorPattern
Misconception
MisconceptionEvidence
```

### 7.2 High-level Relationships

```text
Skill
├── CEFR Alignment
├── Learning Objectives
├── Relationships
├── Assessment Criteria
├── Misconceptions
└── Source Evidence
```

### 7.3 Key Principle

A source record and a canonical entity are different concepts.

```text
SourceRecord
    ↓
Evidence / Alignment
    ↓
Canonical Entity
```

Never collapse the source layer into the canonical layer.

---

## 8. Provenance Model

Every derived fact must answer:

```text
Where did this come from?
```

Canonical skill evidence:

```text
Skill
  ↓
SkillSourceEvidence
  ↓
SourceRecord
  ↓
SourceDocument
  ↓
KnowledgeSource
```

Relationship evidence:

```text
SkillRelationship
  ↓
RelationshipEvidence
  ↓
SourceRecord / Curated Rule
```

Assessment evidence:

```text
AssessmentCriterion
  ↓
AssessmentEvidence
  ↓
EGP / CEFR / Curated Rule
```

Misconception evidence:

```text
Misconception
  ↓
MisconceptionEvidence
  ↓
ErrorInstance
  ↓
EFCAMDAT / CLC FCE
```

Checklist:

- [x] Knowledge source registry concept implemented
- [x] Source records persisted
- [x] Skill source evidence links implemented
- [x] Relationship evidence implemented
- [x] Assessment evidence implemented
- [ ] Error instance provenance implemented
- [ ] Misconception evidence implemented

---

## 9. Source-specific Ingestion Layer

Recommended adapter architecture:

```text
Source Ingestion Adapters
├── EGP XLSX Adapter
├── CEFR PDF Adapter
├── EFCAMDAT Corpus Adapter
├── CLC FCE Adapter
├── UD CoNLL-U Adapter
└── Write & Improve Adapter
```

Every adapter should produce a common intermediate source representation.

```text
Raw Source
    ↓
Source Adapter
    ↓
SourceRecord
```

Source adapters MUST NOT directly modify canonical skills.

---

## 10. EGP Pipeline

Status: **DONE**

Pipeline:

```text
EGP XLSX
   ↓
inspection
   ↓
normalization
   ↓
validation
   ↓
canonical skill mapping
   ↓
review queue
   ↓
evidence profile
```

Current metrics:

```text
raw_total: 330
excluded: 57
valid normalized: 273

exact: 76
candidate: 46
ambiguous: 4
unmapped: 147

canonical taxonomy unchanged: true
validation errors: 0
validation warnings: 0
```

Outputs:

```text
data/reports/egp/source_inspection_report.json
data/interim/english_profile/grammar/egp_records.jsonl
data/interim/english_profile/grammar/egp_records.parquet
data/interim/english_profile/grammar/egp_mappings.jsonl
data/interim/english_profile/grammar/egp_mappings.parquet
data/curated/review/egp_mapping_review.csv
data/reports/egp/mapping_report.json
```

Checklist:

- [x] Source inspected
- [x] Normalization implemented
- [x] Validation implemented
- [x] Canonical mapping implemented
- [x] Review queue generated
- [x] Provenance preserved
- [x] Canonical taxonomy unchanged

---

## 11. CEFR Pipeline

Status: **DONE**

Current V1 extraction scope:

### Reception

- Overall oral comprehension
- Overall reading comprehension
- Reading for information and argument
- Reading instructions

### Production

- Overall oral production
- Sustained monologue: describing experience
- Sustained monologue: giving information
- Overall written production
- Creative writing
- Reports and essays

### Interaction

- Overall oral interaction
- Conversation
- Information exchange
- Overall written interaction

### Linguistic Competence

- General linguistic range
- Vocabulary range
- Grammatical accuracy
- Vocabulary control
- Orthographic control

Current metrics:

```text
descriptor records: 334
descriptor-available records: 322
no-descriptor rows: 12
learning objective candidates: 292

validation errors: 0
validation warnings: 0
malformed records: 0
duplicate candidates: 0
```

Important conceptual rule:

```text
EGP  → What grammar feature?
CEFR → How well should language be controlled/performed?
```

CEFR grammatical accuracy descriptors MUST NOT be interpreted as direct atomic grammar skill definitions.

Checklist:

- [x] Selected V1 scales extracted
- [x] Descriptor records preserved
- [x] Learning objective candidates created
- [x] Grammatical accuracy context extracted
- [x] Validation clean
- [x] Provenance preserved
- [x] No false atomic-skill claims derived from CEFR

---

## 12. CEFR ↔ EGP Alignment

Status: **IMPLEMENTED — REVIEW ARTIFACTS SHOULD REMAIN PART OF V1 FINAL VALIDATION**

Purpose:

```text
Canonical Grammar Skill
       +
EGP evidence
       +
CEFR proficiency context
       ↓
Skill Evidence Profile
```

Rules:

- EGP provides grammar feature evidence.
- CEFR provides proficiency context.
- Ambiguous mappings do not establish level automatically.
- CEFR grammatical accuracy is contextual, not skill-specific proof.
- Curated skills with no source evidence remain explicit.
- No LLM inference in V1 alignment.

Checklist:

- [x] Alignment pipeline implemented
- [x] All canonical skills retained
- [x] Provenance preserved
- [x] Conservative CEFR inference
- [ ] Alignment artifacts included in final global validation pass
- [ ] Human review status consolidated in final V1 report

---

## 13. Relationship / Prerequisite Modeling

Status: **DONE**

Supported relation types:

```text
parent_of
prerequisite_of
recommended_before
related_to
contrast_with
commonly_confused_with
supports
```

Dependency strength:

```text
hard
soft
none
```

Current metrics:

```text
total relationships: 93
prerequisite relationships: 15
canonical skills covered: 43/43
non-structural skill coverage: 43/43

prerequisite DAG valid: true
cycles: 0
invalid references: 0
duplicate edges: 0
taxonomy unchanged: true
```

Core rules:

- CEFR progression != prerequisite
- recommended_before != prerequisite_of
- hard prerequisite graph MUST remain acyclic
- semantic relations may be bidirectional
- external evidence supports but does not blindly generate topology

Checklist:

- [x] Structural relations
- [x] Hard prerequisites
- [x] Soft pedagogical ordering
- [x] Semantic relations
- [x] Reason / provenance
- [x] Cycle validation
- [x] Reference validation
- [x] Taxonomy unchanged

---

## 14. EFCAMDAT Pipeline

Status: **ACQUIRED + INVENTORIED — INGESTION COMPLETED**

Goal:

Use empirical learner data to model:

```text
learner error
    ↓
normalized error
    ↓
canonical skill
    ↓
error pattern
    ↓
misconception candidate
```

Planned stages:

```text
EFCAMDAT Raw Data
        ↓
Corpus Inspection
        ↓
Corpus Parsing
        ↓
Error Instance Extraction
        ↓
Error Normalization
        ↓
Canonical Skill Alignment
        ↓
Frequency / CEFR Analysis
        ↓
Misconception Candidate Evidence
```

Checklist:

### Acquisition

- [x] Local corpus discovered at `data/raw/EFCAMDAT`
- [x] Original corpus present: `EFCAMDAT_Database.xml`
- [x] Cleaned subcorpus present
- [x] Error-coded subcorpus present
- [x] Task prompt metadata discovered
- [x] User agreement file present locally
- [x] License conditions manually reviewed and summarized

### Inspection

- [x] XML / source format profiled
- [x] Learner IDs understood: `learner.id`, `learnerID`
- [x] Text IDs understood: `writing.id`, `writingID`
- [x] Task/topic IDs understood: `topic.id`, `topicID`
- [x] Course / proficiency fields documented
- [x] CEFR mapping rule documented: do not force course levels into CEFR
- [x] Error annotation format understood
- [x] XML `change` markup identified as annotation source of truth
- [x] Cleaned CSV identified as derived support, not standalone label source
- [x] Error tags profiled
- [x] Known quirks and parser requirements documented

### Ingestion

- [x] EFCAMDAT adapter implemented
- [x] Streaming writing-block XML parser implemented; no full DOM load
- [x] Chunked CSV support parser implemented
- [x] Deterministic record IDs
- [x] SourceRecord representation
- [x] ErrorInstance representation
- [x] Pseudonymous learner/text identifiers
- [x] No learner free text emitted in logs
- [x] Provenance preserved
- [x] Validation report
- [x] Review queue for ambiguous labels/spans
- [x] Test suite

---

## 15. CLC FCE Pipeline

Status: **ACQUIRED + INVENTORIED — INGESTION COMPLETED**

Role:

CLC FCE should act as an additional annotated learner-error source.

Primary uses:

```text
error taxonomy evidence
misconception evidence
cross-source validation
benchmarking
```

Pipeline:

```text
CLC FCE
   ↓
Corpus Inspection
   ↓
Annotation Parsing
   ↓
Error Instance Extraction
   ↓
Error Taxonomy Normalization
   ↓
Canonical Skill Mapping
   ↓
Misconception Evidence
```

Checklist:

- [x] Local access/source identified
- [x] Dataset acquired
- [x] Format inspected
- [x] JSON and XML representations documented
- [x] Error annotation schema documented
- [x] Source-native error taxonomy documented
- [x] FCE / B2 proficiency context documented
- [x] Task prompt metadata documented
- [x] Official source URL recorded
- [ ] License checked manually
- [x] Parser implemented
- [x] XML parser implemented for nested structure preservation
- [x] JSONL parser implemented for answer-level parsing
- [ ] Error instances normalized
- [ ] Canonical grammar mapping implemented
- [x] Validation report
- [x] Review queue
- [x] Provenance preserved
- [x] Tests

---

## 16. Error Normalization Layer

This layer should be source-independent.

Target flow:

```text
EFCAMDAT Error
       \
        → Normalized Error Instance
       /
CLC FCE Error
```

### 16.1 ErrorInstance

Suggested structure:

```text
error_instance_id
source_key
source_record_id
learner_id_hash / pseudonymous identifier
text_id
cefr_level
task_id

text_fingerprint
text_length

span_kind
span_offsets_or_selection_fingerprint
correction_fingerprint
correction_length

source_error_label
normalized_error_category
normalized_error_subtype

candidate_skill_ids

confidence
status
review_status

provenance
```

### 16.2 Controlled Error Categories

Initial controlled vocabulary:

```text
article
determiner
noun_number
subject_verb_agreement
verb_tense
verb_form
auxiliary
modal
preposition
word_order
pronoun
adjective_adverb
conjunction_clause
negation
passive_voice
spelling
punctuation
lexical_choice
word_form
sentence_structure
other
unmapped
```

This vocabulary may be extended only through explicit review.

Checklist:

- [x] Unified error schema finalized
- [x] Source-specific labels mapped
- [x] Error categories normalized
- [x] Error subtype strategy defined
- [x] Candidate skill mapping implemented
- [x] Ambiguous mappings preserved
- [x] Review queue generated

---

## 17. Misconception Modeling

Status: **CANDIDATE MINING DONE — HUMAN REVIEW PENDING**

Critical distinction:

```text
Error Instance != Misconception
```

Example:

```text
He go to school.
She work every day.
My father drive to work.
```

These may represent multiple error instances but one normalized misconception:

```text
missing_third_person_s
```

### 17.1 Misconception Entity

Suggested fields:

```text
misconception_id
canonical_skill_id

name
description

error_category
error_subtype

expected_pattern
observed_pattern
diagnostic_rule

example_correct
example_incorrect

source_evidence_count
frequency
frequency_scope
cefr_distribution

severity
confidence

status
review_status

provenance
version
```

### 17.2 Misconception Mining Pipeline

```text
Normalized Error Instances
        ↓
Skill Alignment
        ↓
Pattern Grouping / Clustering
        ↓
Candidate Misconceptions
        ↓
Cross-source Evidence Aggregation
        ↓
Frequency / CEFR Distribution
        ↓
Human Review
        ↓
Canonical Misconception Model
```

V1 should prefer deterministic / interpretable grouping.

LLM-based misconception discovery is optional and NOT required.

Checklist:

- [x] Misconception schema frozen
- [x] Error instances mapped to skills
- [x] Pattern grouping implemented
- [x] Cross-source evidence aggregation
- [x] Frequency statistics
- [x] CEFR distribution
- [x] Confidence rules
- [x] Review queue
- [x] Accepted misconception set
- [x] Misconception provenance
- [x] Tests

---

## 18. Assessment Criteria Modeling

Status: **CURATED V1 DONE — EMPIRICAL ENRICHMENT PENDING**

Current metrics:

```text
total skills: 43
skills covered: 43/43
total criteria: 79
average criteria per skill: 1.84

CEFR-context coverage:
34/43 skills
61/79 criteria

validation:
0 errors
0 warnings

taxonomy unchanged: true
```

Criteria by type:

```text
form_accuracy: 15
meaning_use: 28
production: 29
contrast_discrimination: 3
error_correction: 4
```

Current state:

```text
Assessment Criterion
├── observable behavior
├── evidence requirements
├── task types
├── failure signals
├── CEFR context
└── curated scoring recommendation
```

Important limitation:

Current `failure_signals` are curated diagnostic hints.

They MUST NOT be described as corpus-validated misconception evidence until EFCAMDAT / CLC FCE enrichment is complete.

### 18.1 Empirical Enrichment

After misconception modeling:

```text
Assessment Criterion
       +
Accepted Misconceptions
       +
Empirical Error Frequency
       ↓
Enriched Assessment Criterion
```

Checklist:

- [x] 43/43 skills have criteria
- [x] Observable behavior structured
- [x] Evidence requirements structured
- [x] Task types structured
- [x] CEFR context attached where available
- [x] Curated failure signals
- [ ] Corpus-supported failure signals
- [ ] Misconception links
- [ ] Empirical error evidence
- [ ] Final human review consolidation

---

## 19. Optional Universal Dependencies Enrichment

Structural ingestion status: **COMPLETE**

Status: **OPTIONAL — ACQUIRED + INVENTORIED + STRUCTURALLY INGESTED**

Potential role:

```text
tokens
POS
morphological features
dependency relations
```

Possible uses:

- deterministic syntax rules
- error detection support
- exercise generation constraints
- structural linguistic evidence

UD EWT MUST NOT define curriculum or CEFR ordering.

Checklist if included:

- [x] Dataset acquired
- [x] Source inventory report generated
- [x] Released train/dev/test CoNLL-U files identified
- [x] License file located
- [x] CoNLL-U adapter
- [x] Morphological feature normalization
- [x] Dependency feature normalization
- [x] Relevant grammar evidence mappings
- [x] Validation
- [x] Provenance

---

## 20. Optional Write & Improve Enrichment

Status: **OPTIONAL — ACQUIRED + INVENTORIED**

Potential role:

- additional learner writing evidence
- error validation
- CEFR-linked error analysis
- external validation

Checklist if included:

- [x] Dataset acquired
- [x] Dataset inspected
- [x] Whole-corpus TSV metadata identified
- [x] M2 / CoNLL derived annotation views identified
- [x] CEFR-like automarker and human annotation fields documented
- [ ] Access/license confirmed by manual review
- [ ] Optional inclusion decision recorded
- [ ] Adapter implemented
- [ ] Error schema normalized
- [ ] Cross-source validation
- [ ] Provenance retained

---

## 21. Global Knowledge Build

Once required V1 sources are normalized, build a complete per-skill profile.

Target:

```text
Canonical Skill
├── identity
├── taxonomy position
├── EGP evidence
├── CEFR profile
├── learning objectives
├── prerequisites
├── pedagogical relationships
├── assessment criteria
├── misconceptions
├── empirical error statistics
└── provenance
```

Example target profile:

```text
grammar.present_simple.third_person_s
├── CEFR context
├── EGP evidence
├── learning objectives
├── prerequisite context
├── related skills
├── assessment criteria
└── misconceptions
    ├── missing third-person -s
    ├── overgeneralized -s
    └── subject-verb agreement confusion
```

Checklist:

- [ ] All required source records ingested
- [ ] All source mappings normalized
- [ ] All accepted relationships included
- [ ] Misconceptions included
- [ ] Assessment criteria enriched
- [ ] Per-skill knowledge profiles generated
- [ ] Profiles versioned

---

## 22. Global Validation

A final Knowledge Core V1 validation must run after all required sources are integrated.

Target report:

```text
data/reports/knowledge_core_v1_report.json
```

### 22.1 Taxonomy

- [ ] total taxonomy nodes = 54
- [ ] atomic skills = 43
- [ ] canonical IDs unchanged
- [ ] taxonomy hash unchanged
- [ ] no orphan nodes

### 22.2 Source Integrity

- [ ] all registered sources valid
- [ ] no duplicate source records
- [ ] all source references resolvable
- [ ] file/source provenance complete
- [ ] licenses recorded

### 22.3 Skill Coverage

- [ ] 43/43 canonical skills represented
- [ ] evidence coverage reported
- [ ] CEFR coverage reported
- [ ] objective coverage reported
- [ ] relationship coverage reported
- [ ] misconception coverage reported
- [ ] assessment coverage reported

### 22.4 Graph

- [ ] prerequisite DAG valid
- [ ] cycles = 0
- [ ] invalid references = 0
- [ ] duplicate logical edges = 0

### 22.5 Misconceptions

- [ ] no misconception without canonical skill
- [ ] no accepted misconception without evidence
- [ ] empirical frequency scope explicit
- [ ] corpus source provenance preserved
- [ ] ambiguous mappings retained for review

### 22.6 Assessment

- [ ] 43/43 skills have criteria
- [ ] no unsupported empirical claims
- [ ] corpus-linked failure signals clearly tagged
- [ ] curated thresholds remain non-psychometric recommendations

### 22.7 Persistence

- [ ] FK violations = 0
- [ ] duplicate logical rows = 0
- [ ] idempotent loader
- [ ] knowledge version valid
- [ ] DB counts match artifact counts within documented normalization differences

---

## 23. Human Review

Review must remain a first-class part of V1.

Recommended review files:

```text
data/curated/review/
├── egp_mapping_review.csv
├── cefr_egp_alignment_review.csv
├── grammar_relationship_review.csv
├── grammar_assessment_criteria_review.csv
├── error_skill_mapping_review.csv
├── misconception_review.csv
└── knowledge_core_v1_review_summary.csv
```

Checklist:

- [ ] EGP mapping review consolidated
- [ ] CEFR alignment review consolidated
- [ ] Relationship review consolidated
- [ ] Assessment review consolidated
- [ ] Error mapping review completed
- [ ] Misconception review completed
- [ ] Final unresolved candidates explicitly reported
- [ ] No automatic mass-approval of ambiguous records

---

## 24. Knowledge Storage

Status: **INFRASTRUCTURE DONE**

Current verified state:

```text
storage backend tested: SQLite
Knowledge Core tables: 17
views: 3
knowledge version: knowledge_core_v1
validation: PASS
taxonomy hash: matched
```

Persisted counts:

```text
taxonomy nodes: 54
atomic skills: 43

source records: 607
├── EGP: 273
└── CEFR: 334

skill source evidence: 205

learning objectives: 292
skill-objective links: 31

CEFR alignments: 43

relationships: 93
prerequisite relationships: 15

assessment criteria: 79
assessment requirements: 309
assessment failure signals: 306
assessment task-type links: 343

relationship evidence: 382
assessment evidence: 418
```

Integrity:

```text
duplicates: 0
FK violations: 0
orphan nodes: 0
idempotent load: PASS
```

Tests:

```text
storage tests: 9 passed
full suite at storage milestone: 243 passed
```

Known limitation:

```text
SQLite execution verified
PostgreSQL-compatible DDL exists
Live PostgreSQL execution not yet verified
```

### 24.1 Storage Follow-up After Final Knowledge Build

When EFCAMDAT / CLC / misconceptions are integrated:

- [ ] Add ErrorInstance storage
- [ ] Add Misconception storage
- [ ] Add MisconceptionEvidence storage
- [ ] Add corpus source records
- [ ] Extend loader
- [ ] Reload final Knowledge Core V1
- [ ] Re-run idempotency
- [ ] Re-run FK validation
- [ ] Re-run DB count reconciliation
- [ ] Validate against live PostgreSQL before production claim

---

## 25. KnowledgeRepository

Status: **INFRASTRUCTURE DONE**

Implemented:

```text
knowledge_core/repository/
```

Repository coverage:

- [x] Knowledge version repository
- [x] Knowledge node repository
- [x] Source evidence repository
- [x] Learning objective repository
- [x] Relationship repository
- [x] Prerequisite / unlock queries
- [x] Assessment repository
- [x] Composite snapshot query
- [x] Version isolation
- [x] Bidirectional relation handling
- [x] Transitive prerequisite query

Read models:

```text
11 immutable read models
```

Tests:

```text
repository tests: 19 passed
full suite at repository milestone: 262 passed
```

Known limitation:

```text
Concrete repository implementation tested on SQLite.
Live PostgreSQL repository execution not yet tested.
```

### 25.1 Repository Follow-up

After corpus/misconception integration:

- [ ] ErrorInstanceRepository
- [x] MisconceptionRepository
- [x] Misconception evidence queries
- [x] Corpus statistics queries
- [x] Misconception-by-skill query
- [ ] Error-pattern-by-CEFR query
- [ ] PostgreSQL integration tests

---

## 26. KnowledgeService

Status: **V1 DONE (SQLITE VERIFIED)**

KnowledgeService should be implemented only after the required V1 knowledge model is stable.

Target architecture:

```text
Assessment Engine
Learner Modeling Engine
Adaptive Decision Engine
AI Content & Feedback Engine
        ↓
KnowledgeService
        ↓
KnowledgeRepository
        ↓
Knowledge Storage
```

Candidate future APIs:

```text
get_skill(skill_id)

get_skill_context(skill_id)

get_prerequisites(skill_id)

get_learning_path(skill_id)

is_unlocked(skill_id, mastered_skill_ids)

get_unlocked_skills(mastered_skill_ids)

get_learning_objectives(skill_id)

get_cefr_profile(skill_id)

get_assessment_profile(skill_id)

get_misconceptions(skill_id)

get_diagnostic_signals(skill_id)

get_related_learning_targets(skill_id)
```

Implemented in:

```text
knowledge_core/service/
```

The V1 service is a read-only composition layer. Learning paths and unlocks use
only persisted `prerequisite_of` edges. Adaptive policy, mastery estimation,
learner state, content generation, and LLM calls remain outside the service.

Do NOT implement learner-specific adaptive policy inside KnowledgeRepository.

---

## 27. Folder Structure Target

```text
knowledge_core/
├── taxonomy/
│   └── grammar/
│
├── ingestion/
│   ├── egp/
│   ├── cefr/
│   ├── efcamdat/
│   ├── clc_fce/
│   ├── universal_dependencies/
│   └── write_improve/
│
├── normalization/
│   ├── source_records/
│   ├── error_taxonomy/
│   └── skill_mapping/
│
├── alignment/
│   ├── egp/
│   ├── cefr/
│   └── corpus_errors/
│
├── relationships/
│
├── misconceptions/
│
├── assessment/
│
├── validation/
│
├── storage/
│
├── repository/
│
└── service/
```

Data:

```text
data/
├── external/
│   ├── english_profile/
│   ├── cefr/
│   ├── efcamdat/
│   ├── clc_fce/
│   ├── universal_dependencies/
│   └── write_improve/
│
├── interim/
│
├── curated/
│   ├── relationships/
│   ├── assessment/
│   ├── misconceptions/
│   └── review/
│
└── reports/
    ├── source_inventory.json
    ├── egp/
    ├── cefr/
    ├── knowledge_alignment/
    ├── relationships/
    ├── assessment/
    ├── misconceptions/
    └── knowledge_core_v1_report.json
```

---

## 28. Execution Order From This Point

Do not continue directly to KnowledgeService yet.

### Phase A — Freeze Scope

- [x] Grammar V1 scope
- [x] Canonical taxonomy
- [x] Required source list

### Phase B — Finish Source Acquisition / Inventory

- [x] EGP
- [x] CEFR
- [x] EFCAMDAT local corpus acquired
- [x] CLC FCE local dataset acquired
- [x] Optional UD EWT local dataset acquired
- [x] Optional Write & Improve local dataset acquired
- [ ] Manual license review for EFCAMDAT, CLC FCE, EGP, CEFR, Write & Improve
- [x] Restricted/raw corpus paths added to `.gitignore` or moved outside tracked workspace
- [x] Optional UD EWT inclusion decision
- [x] Optional Write & Improve inclusion decision

### Phase C — Complete Source Inventory

- [x] EGP
- [x] CEFR
- [x] EFCAMDAT
- [x] CLC FCE
- [x] UD EWT
- [x] Write & Improve
- [x] Generate consolidated `data/reports/source_inventory/source_inventory.json`
- [x] Generate source-specific inspection reports
- [x] Generate error/proficiency comparison reports
- [x] Preserve raw data unchanged during inspection

### Phase D — Complete Required Ingestion

- [x] EGP ingestion
- [x] CEFR ingestion
- [x] EFCAMDAT ingestion
- [x] CLC FCE ingestion
- [x] Required corpus ingestion reports
- [x] Required corpus review queues
- [x] Required corpus ingestion tests

### Phase E — Error Knowledge

- [x] Unified ErrorInstance schema
- [x] Error taxonomy normalization
- [x] EFCAMDAT error normalization
- [x] CLC FCE error normalization
- [x] Error → canonical skill alignment
- [x] Review ambiguous mappings

### Phase F — Misconceptions

- [x] Misconception schema
- [x] Pattern aggregation
- [x] Frequency statistics
- [x] CEFR distributions
- [x] Cross-source validation
- [ ] Human review
- [x] Accepted misconception set

### Phase G — Enrich Existing Knowledge

- [ ] Link misconceptions to skills
- [ ] Enrich assessment failure signals
- [ ] Attach empirical error evidence
- [ ] Recompute complete per-skill profiles

### Phase H — Global Validation

- [ ] Run system-wide validation
- [ ] Generate `knowledge_core_v1_report.json`
- [ ] Consolidate all review queues
- [ ] Verify taxonomy hash
- [ ] Verify provenance completeness

### Phase I — Reload Persistence

- [ ] Extend DB schema for misconceptions/errors
- [ ] Load final Knowledge Core V1
- [ ] Verify idempotency
- [ ] Verify FK integrity
- [ ] Verify artifact/DB count consistency

### Phase J — Repository Extension

- [ ] Misconception repository
- [ ] Error statistics repository
- [ ] PostgreSQL integration tests

### Phase K — KnowledgeService

- [x] Service API design
- [x] Skill context
- [x] Learning path
- [x] Unlock logic
- [x] Assessment profile
- [x] Misconception profile
- [x] Diagnostic context
- [x] Tests

---

## 29. V1 Definition of Done

Knowledge Core V1 is complete only when all required conditions below are satisfied.

### 29.1 Canonical Model

- [x] Grammar V1 taxonomy frozen
- [x] 43 atomic skills
- [x] Stable canonical IDs
- [x] Taxonomy hash

### 29.2 Required Sources

- [x] EGP acquired and ingested
- [x] CEFR acquired and ingested
- [x] EFCAMDAT acquired and inventoried
- [x] EFCAMDAT ingested
- [x] CLC FCE acquired and inventoried
- [x] CLC FCE ingested

### 29.3 Normalization

- [x] EGP normalized
- [x] CEFR normalized
- [x] Corpus error normalization
- [x] Unified error taxonomy
- [x] Error → skill mapping

### 29.4 Knowledge Relations

- [x] Structural taxonomy
- [x] Prerequisite graph
- [x] Soft ordering
- [x] Semantic relations
- [x] DAG validation

### 29.5 Learning Objectives / CEFR

- [x] CEFR descriptors
- [x] Learning objective candidates
- [x] CEFR skill alignment
- [ ] Final review consolidation

### 29.6 Misconceptions

- [x] Misconception schema
- [x] Empirical misconception candidates
- [x] Cross-source evidence
- [x] Frequency
- [x] CEFR distribution
- [ ] Human-reviewed accepted misconceptions

### 29.7 Assessment

- [x] 43/43 skills assessed
- [x] 79 structured criteria
- [x] CEFR context
- [x] Curated failure signals
- [ ] Corpus-backed diagnostic evidence
- [ ] Misconception links
- [ ] Final review consolidation

### 29.8 Provenance

- [x] Source registry
- [x] Source records
- [x] Skill evidence
- [x] Relationship evidence
- [x] Assessment evidence
- [ ] Error instance provenance
- [ ] Misconception provenance

### 29.9 Validation

- [ ] Final global validation
- [ ] All canonical skill references valid
- [ ] No orphan evidence
- [ ] No duplicate logical entities
- [ ] DAG valid
- [ ] Taxonomy unchanged
- [ ] Provenance complete
- [ ] Review summary generated

### 29.10 Storage / API

- [x] Knowledge Storage infrastructure
- [x] Idempotent loader
- [x] KnowledgeRepository infrastructure
- [x] Misconception/error persistence extension
- [x] Misconception repository extension
- [ ] Live PostgreSQL integration verification
- [x] KnowledgeService V1

---

## 30. Current Project Status

```text
Canonical Grammar V1              ✅ DONE
EGP                                ✅ DONE
CEFR                               ✅ DONE
CEFR ↔ EGP alignment              ✅ IMPLEMENTED
Relationships / prerequisites      ✅ DONE
Source Inventory V1                ✅ DONE

EFCAMDAT                           ✅ ACQUIRED + INVENTORIED; INGESTION COMPLETE
CLC FCE                            ✅ ACQUIRED + INVENTORIED; INGESTION COMPLETE
UD EWT                             ✅ INVENTORIED; OPTIONAL STRUCTURAL INGESTION COMPLETE
Write & Improve                    ✅ INVENTORIED; OPTIONAL INGESTION NOT STARTED

Error normalization                ✅ DONE
Misconception modeling             ✅ CANDIDATE MINING DONE; HUMAN REVIEW PENDING

Assessment Criteria V1             ✅ CURATED VERSION DONE
Assessment empirical enrichment    ⬜ NOT STARTED

Global Knowledge Validation        ✅ DONE LOCALLY; POSTGRES GATE OPEN

Knowledge Storage infrastructure   ✅ DONE
KnowledgeRepository                ✅ DONE
KnowledgeService                   ✅ V1 DONE (SQLITE VERIFIED)
```

---

## 31. Repo-derived Build Checklist

This checklist reflects the project state observed on 2026-09-16.

### 31.1 Immediate Safety / Governance Gate

- [x] Add `.gitignore` coverage or move restricted raw corpora out of the tracked workspace:
  `data/raw/EFCAMDAT/`, `data/raw/_fce-released-dataset-1.1/`, `data/raw/write-and-improve-corpus-2024-v2/`, `data/raw/UD_English-EWT-master/`.
- [x] Record official source URLs for EFCAMDAT, CLC FCE, EGP, CEFR, UD EWT, and Write & Improve.
- [x] Summarize license / user-agreement constraints in source metadata before any ingestion artifact is redistributed.
- [x] Decide whether UD EWT and Write & Improve remain inventory-only for V1 or enter optional enrichment.
- [x] Keep `data/raw/Dataset` excluded from Knowledge Core V1; it is unrelated exam data.

### 31.2 Freeze Error Schema

- [x] Create source-independent `ErrorInstance` model.
- [x] Freeze normalized error category vocabulary.
- [x] Define deterministic IDs for source records, error instances, normalized errors, and review rows.
- [x] Define span policy for XML inline spans, JSON offsets, M2 token offsets, and EFCAMDAT selection text.
- [x] Define PII/free-text policy: no learner free text in logs, reports, exceptions, or test snapshots.
- [x] Add schema validation tests.

Target outputs:

```text
knowledge_core/normalization/error_taxonomy/
tests/knowledge_core/normalization/
```

### 31.3 Implement CLC FCE Ingestion First

CLC FCE is smaller and should harden the common error pipeline before EFCAMDAT.

- [x] Create `knowledge_core/sources/clc_fce/`.
- [x] Parse XML for nested structure preservation.
- [x] Parse JSONL for answer-level records and offsets.
- [x] Preserve train/dev/test/outlier split metadata.
- [x] Emit common `SourceRecord` artifacts.
- [x] Emit source-native `ErrorInstance` artifacts.
- [x] Generate validation report.
- [x] Generate review queue for ambiguous labels/spans.
- [x] Add parser, normalizer, validator, and CLI tests.

Target outputs:

```text
data/interim/clc_fce/source_records.jsonl
data/interim/clc_fce/error_instances.jsonl
data/reports/clc_fce/ingestion_report.json
data/curated/review/clc_fce_error_review.csv
```

### 31.4 Implement EFCAMDAT Ingestion

- [x] Create `knowledge_core/sources/efcamdat/`.
- [x] Stream `EFCAMDAT_Database.xml` by writing block; do not DOM-load large XML.
- [x] Parse XML `change` markup as annotation source of truth.
- [x] Use cleaned/error-coded CSV only as derived support.
- [x] Process large CSV in chunks.
- [x] Preserve learner, writing, topic, level, and unit identifiers pseudonymously.
- [x] Emit common `SourceRecord` artifacts.
- [x] Emit source-native `ErrorInstance` artifacts.
- [x] Generate validation report.
- [x] Generate review queue for ambiguous labels/spans.
- [x] Add parser, normalizer, validator, and CLI tests.

Target outputs:

```text
data/interim/efcamdat/source_records.jsonl
data/interim/efcamdat/error_instances.jsonl
data/reports/efcamdat/ingestion_report.json
data/curated/review/efcamdat_error_review.csv
```

### 31.5 Normalize Errors And Map To Skills

- [x] Map CLC FCE source-native labels to normalized error categories.
- [x] Map EFCAMDAT source-native labels to normalized error categories.
- [x] Preserve unmapped/ambiguous labels for review.
- [x] Implement deterministic error → canonical grammar skill mapping rules.
- [x] Reject implicit creation of new canonical skills.
- [x] Generate `error_skill_mapping_review.csv`.
- [x] Validate taxonomy hash unchanged.
- [x] Implement explicit APPROVE / REJECT / NEEDS_REVIEW closure with audit history.
- [x] Isolate accepted, rejected, and unresolved mappings into separate artifacts.
- [x] Restrict storage and misconception evidence to human-approved mappings.
- [ ] Complete human adjudication of the 822 mappings currently marked `NEEDS_REVIEW`.

Target outputs:

```text
data/interim/corpus_errors/normalized_error_instances.jsonl
data/interim/corpus_errors/error_skill_mappings.jsonl
data/curated/review/error_skill_mapping_review.csv
data/reports/corpus_errors/error_normalization_report.json
```

### 31.6 Mine Misconception Candidates

- [x] Freeze misconception schema.
- [x] Group normalized errors into deterministic pattern candidates.
- [x] Aggregate evidence across CLC FCE and EFCAMDAT.
- [x] Compute frequency and proficiency distributions with explicit scope.
- [x] Keep source-specific evidence links for every candidate.
- [x] Generate misconception review queue.
- [x] Accept only human-reviewed misconceptions into canonical output.
- [x] Implement explicit APPROVE / REJECT / NEEDS_REVIEW misconception closure.
- [x] Generate accepted, rejected, and unresolved misconception artifacts.
- [x] Restrict accepted misconception evidence to approved error-skill mappings.
- [x] Generate proposed assessment links without mutating assessment criteria.
- [ ] Complete human adjudication of the candidate currently marked `NEEDS_REVIEW`.

Target outputs:

```text
knowledge_core/misconceptions/
data/interim/misconceptions/candidate_misconceptions.jsonl
data/curated/review/misconception_review.csv
data/curated/misconceptions/accepted_misconceptions.jsonl
data/reports/misconceptions/misconception_report.json
```

### 31.7 Enrich Existing Knowledge

- [x] Link accepted misconceptions to canonical skills.
- [x] Enrich assessment criteria with corpus-backed failure signals.
- [x] Clearly tag curated vs empirical diagnostic evidence.
- [x] Recompute per-skill profiles.
- [x] Consolidate EGP, CEFR, relationship, assessment, error, and misconception review status.

Target outputs:

```text
knowledge_core/enrichment/
data/curated/knowledge_enrichment/grammar_assessment_criteria_enriched.jsonl
data/curated/knowledge_enrichment/grammar_skill_profiles_enriched.jsonl
data/curated/knowledge_enrichment/skill_misconception_links.jsonl
data/curated/review/knowledge_enrichment_review.csv
data/reports/knowledge_enrichment/knowledge_enrichment_report.json
```

### 31.8 Global Validation And Persistence

- [x] Generate `data/reports/knowledge_core_v1_report.json`.
- [x] Validate taxonomy nodes = 54 and atomic skills = 43.
- [x] Validate source references, provenance links, FK consistency, duplicate logical rows, and prerequisite DAG.
- [x] Extend storage schema for errors, misconceptions, and misconception evidence.
- [x] Reload final Knowledge Core V1 idempotently.
- [x] Reconcile artifact counts with DB counts.
- [x] Add repository support for misconceptions and corpus error statistics.
- [x] Gate live PostgreSQL validation before any production claim.

Target outputs:

```text
knowledge_core/global_validation/
data/reports/knowledge_core_v1_report.json
```

Note:

```text
Local SQLite validation passed. Live PostgreSQL validation is recorded as
not_executed in the report, so production_claim_allowed=false until a reachable
PostgreSQL instance is validated.
```

### 31.9 KnowledgeService Gate

- [x] Implement KnowledgeService only after required corpus ingestion, misconception review artifacts, global validation, and persistence reload are complete.
- [x] Keep adaptive policy, learner modeling, generation, and LLM calls outside KnowledgeRepository and KnowledgeService.
- [x] Expose skill context, prerequisites, learning paths, deterministic unlock checks, learning objectives, CEFR profiles, assessment profiles, misconceptions, related targets, and diagnostic signals.
- [x] Preserve active/explicit knowledge-version resolution through every service API.
- [x] Add focused KnowledgeService tests.

Implemented:

```text
knowledge_core/service/
tests/knowledge_core/service/
```

Note:

```text
Unlock checks consume caller-provided mastered skill IDs but do not estimate
mastery or choose an adaptive action. Live PostgreSQL execution remains gated;
the V1 service is verified against SQLite persistence.
```

---

## 32. Project Rule Going Forward

Before implementing a new Knowledge Core feature:

```text
1. Check this plan.
2. Confirm the source belongs to V1.
3. Confirm which canonical entity it enriches.
4. Confirm the intermediate representation.
5. Preserve provenance.
6. Validate before persistence.
7. Do not create new canonical taxonomy implicitly.
8. Do not claim empirical support for curated rules.
9. Do not proceed to service/business logic before required knowledge is complete.
```

This document should be updated whenever:

- a source is added or removed from V1,
- a source is acquired,
- a schema is frozen,
- a milestone reaches Definition of Done,
- a validation result changes,
- the canonical taxonomy changes intentionally,
- a new known limitation is discovered.
