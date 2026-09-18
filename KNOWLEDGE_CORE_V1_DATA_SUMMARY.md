# Tong hop du lieu Knowledge Core V1

> Tai lieu tong hop hien trang Knowledge Core trong repository. So lieu duoc doi chieu tu `KNOWLEDGE_CORE_V1_PLAN.md`, source inventory, cac bao cao pipeline va bao cao validation tong the.

## 1. Tong quan

Knowledge Core V1 hien tap trung vao mien **English Grammar**. He thong da xay dung duoc taxonomy chuan, tich hop du lieu EGP va CEFR, quan he tien quyet, tieu chi danh gia, du lieu loi nguoi hoc, mo hinh misconception, lop luu tru va API dich vu chi doc.

Trang thai validation tong the: **PASS**.

| Hang muc | Gia tri |
|---|---:|
| Tong node taxonomy | 54 |
| Atomic grammar skills | 43 |
| Group nodes | 10 |
| Quan he giua cac skill/node | 93 |
| Assessment criteria | 79 |
| Assessment profiles | 43 |
| Learning objectives | 292 |
| CEFR descriptors | 334 |
| EGP records | 273 |
| Skill-source evidence | 205 |
| Corpus error statistics | 737 |
| Normalized error instances | 6,222,430 |
| Candidate misconceptions | 1 |
| Accepted misconceptions | 0 |

Taxonomy hash:

```text
b5f455b12a706d862d9b578affd803036e8d77ca0c9085f8434aeb2d27115ab0
```

Taxonomy khong bi thay doi trong cac buoc mapping, alignment, enrichment va validation.

## 2. Nguon du lieu

### 2.1. Nguon bat buoc

| Nguon | Vai tro | Vi tri | Quy mo | Trang thai |
|---|---|---|---:|---|
| English Grammar Profile (EGP) | Bang chung grammar theo CEFR | `data/external/english_profile` | 273 records | Ready |
| CEFR Companion Volume 2020 | Descriptor va learning objective | `data/external/cefr` | 334 records | Ready |
| EFCAMDAT | Learner corpus va error corpus | `data/raw/EFCAMDAT` | 1,425,956 records uoc tinh trong inventory | Ready with known quirks |
| Cambridge Learner Corpus FCE | Annotated learner error corpus | `data/raw/_fce-released-dataset-1.1` | 2,543 source records | Ready with known quirks |

### 2.2. Nguon bo sung tuy chon

| Nguon | Vai tro | Vi tri | Quy mo | Trang thai |
|---|---|---|---:|---|
| Universal Dependencies English EWT | Bang chung cau truc va dependency | `data/raw/UD_English-EWT-master` | 16,622 sentences | Da ingest |
| Write & Improve Corpus 2024 | Learner writing corpus | `data/raw/write-and-improve-corpus-2024-v2` | 23,216 records | Da inventory, chua ingest |

Thu muc `data/raw/Dataset` da duoc xac dinh la du lieu VNHSGE/MET khong thuoc Knowledge Core V1 va khong duoc dua vao pipeline.

## 3. Luong xu ly du lieu

```text
Raw/External Sources
        |
        v
Source Inventory
        |
        +-------------------+
        |                   |
        v                   v
 EGP + CEFR           Learner Corpora
        |              EFCAMDAT + FCE
        v                   |
Skill Alignment             v
        |            Error Normalization
        v                   |
Relationships               v
        |              Skill Mapping
        v                   |
Assessment Criteria         v
        |            Misconception Mining
        +---------+---------+
                  |
                  v
       Global Validation + Storage
                  |
                  v
       Repository + Knowledge Service
```

## 4. Taxonomy Grammar V1

Taxonomy co 43 atomic skills, phan bo vao cac nhom chinh:

- Present Simple
- Present Continuous
- Past Simple
- Past Continuous
- Present Perfect
- Future with `will`
- Modality
- Articles
- Conditionals
- Passive Voice

Danh sach day du:

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

## 5. EGP

Pipeline EGP da trich xuat va validate thanh cong 273 records, khong co validation error hoac warning.

| CEFR level | So records |
|---|---:|
| A1 | 23 |
| A2 | 65 |
| B1 | 82 |
| B2 | 53 |
| C1 | 25 |
| C2 | 25 |

Ket qua mapping:

| Chi so | Gia tri |
|---|---:|
| Skills co EGP coverage | 37/43 |
| Skills co mapped evidence | 36/43 |
| Skills khong co EGP evidence | 6 |
| Exact mappings | 76 |
| Candidate mappings | 46 |
| Ambiguous mappings | 4 |
| Unmapped records | 147 |
| Approved reviews | 76 |
| Needs review | 151 |

## 6. CEFR va alignment CEFR-EGP

CEFR pipeline da doc 278 trang PDF, xem 53 bang va chon 24 bang phu hop. Ket qua gom 334 descriptors va 292 learning-objective candidates.

### Descriptor theo CEFR level

| Level | So records |
|---|---:|
| Pre-A1 | 30 |
| A1 | 38 |
| A2 | 81 |
| B1 | 69 |
| B2 | 54 |
| C1 | 36 |
| C2 | 26 |

### Learning objectives theo domain

| Domain | So objectives |
|---|---:|
| Interaction | 82 |
| Linguistic competence | 56 |
| Production | 93 |
| Reception | 61 |

### Ket qua alignment

| Chi so | Gia tri |
|---|---:|
| Tong canonical skills | 43 |
| Skills co CEFR alignment | 34 |
| Skills chua co CEFR alignment | 9 |
| Skills co EGP evidence trong alignment | 34 |
| Aligned | 18 |
| Partial | 17 |
| Curated only | 6 |
| Ambiguous | 2 |

Primary CEFR level cua cac skill: A1 co 6, A2 co 14, B1 co 12, B2 co 2 va 9 skill chua co primary level.

## 7. Quan he va prerequisite graph

He thong co 93 relationships va bao phu toan bo 43 atomic skills.

| Loai quan he | So luong |
|---|---:|
| `parent_of` | 53 |
| `prerequisite_of` | 15 |
| `recommended_before` | 10 |
| `supports` | 6 |
| `related_to` | 6 |
| `contrast_with` | 3 |

Ket qua validation graph:

- Prerequisite graph la DAG hop le.
- Khong co cycle, duplicate edge hoac invalid reference.
- Do sau prerequisite lon nhat la 2.
- Co 7 connected components.
- Khong co isolated skill.
- Co 15 hard prerequisites va 10 soft prerequisites.

## 8. Assessment Criteria V1

Toan bo 43 atomic skills deu co assessment profile va assessment criteria.

| Chi so | Gia tri |
|---|---:|
| Assessment criteria | 79 |
| Assessment profiles | 43 |
| Trung binh criteria/skill | 1.84 |
| Criteria co CEFR context | 61 |
| Criteria chua co CEFR context | 18 |
| Skills co CEFR context | 34 |

### Criteria theo loai

| Loai | So luong |
|---|---:|
| Production | 29 |
| Meaning/use | 28 |
| Form accuracy | 15 |
| Error correction | 4 |
| Contrast discrimination | 3 |

Assessment criteria la dinh nghia va huong dan curated. Cac threshold chua duoc xem la quy tac mastery da duoc thuc nghiem xac nhan.

## 9. Du lieu corpus va loi nguoi hoc

### 9.1. Cambridge Learner Corpus FCE

| Chi so | Gia tri |
|---|---:|
| Source records | 2,543 |
| Error instances | 53,417 |
| XML error nodes | 55,895 |
| Unique error labels | 681 |
| Review queue | 2,193 |

Phan bo source record: train 2,118; test 194; dev 159; outliers 72.

### 9.2. EFCAMDAT

| Chi so | Gia tri |
|---|---:|
| Ingested source records | 1,180,309 |
| Error instances | 6,169,013 |
| Changed writings | 782,648 |
| Unique error labels | 31 |
| Parser fallback/malformed writings | 39 |
| Review queue | 344 |

Pipeline khong phat tan raw learner text. Noi dung va correction chi duoc luu duoi dang fingerprint va do dai de bao ve du lieu nguoi hoc.

## 10. Error normalization va skill mapping

Tong cong 6,222,430 error instances da duoc normalization:

| Nguon | So loi |
|---|---:|
| EFCAMDAT | 6,169,013 |
| CLC FCE | 53,417 |

### Trang thai normalization

| Trang thai | So luong |
|---|---:|
| Exact | 3,123,899 |
| Candidate | 2,148,731 |
| Ambiguous | 949,730 |
| Unmapped | 70 |

### Cac nhom loi lon

| Category | So luong |
|---|---:|
| Spelling | 1,574,823 |
| Sentence structure | 1,413,177 |
| Other | 948,679 |
| Lexical choice | 678,500 |
| Punctuation | 635,548 |
| Article | 290,136 |
| Preposition | 272,106 |
| Verb tense | 169,815 |
| Noun number | 155,215 |
| Word order | 69,250 |

Pipeline sinh 822 candidate error-skill mappings, hien deu lien quan den `grammar.present_simple.third_person_s`. Tat ca 822 mapping van o trang thai `needs_review`; chua co mapping nao duoc approved hoac rejected.

## 11. Misconception modeling

Pipeline da sinh mot candidate misconception cho skill `grammar.present_simple.third_person_s`.

| Chi so | Gia tri |
|---|---:|
| Candidate misconceptions | 1 |
| Needs review | 1 |
| Accepted | 0 |
| Rejected | 0 |
| Skill-misconception links | 0 |
| Empirical failure signals | 0 |

Candidate chua duoc dung lam diagnostic evidence vi chinh sach enrichment chi chap nhan misconception da qua human review.

## 12. Universal Dependencies EWT

Nguon tuy chon UD English EWT da duoc ingest de bo sung bang chung cau truc.

| Chi so | Gia tri |
|---|---:|
| Sentences | 16,622 |
| Syntactic tokens | 254,820 |
| Total token rows | 258,190 |
| Dependency edges | 523,380 |
| Enhanced dependency edges | 268,560 |
| Morphology rows | 353,587 |
| Structural evidence records | 18 |

Du lieu UD khong tao skill moi va khong suy dien CEFR level moi. Trong 18 structural evidence records co 13 candidate va 5 ambiguous.

## 13. Luu tru

Knowledge Core duoc nap vao `data/sqlite/app.db` va da vuot qua kiem tra idempotency, reconciliation, foreign key, duplicate va orphan.

| Hang muc | So luong |
|---|---:|
| Knowledge Core tables | 22 |
| Knowledge Core views | 5 |
| Knowledge sources | 6 |
| Source documents | 15 |
| Loaded source records | 607 |
| Knowledge versions | 1 |
| Knowledge nodes | 54 |
| Atomic skills | 43 |
| Assessment evidence | 418 |
| Assessment requirements | 309 |
| Assessment task-type links | 343 |
| Relationship evidence | 382 |
| Prerequisite relationships | 15 |

Nam view chinh:

- `v_atomic_skills`
- `v_corpus_error_statistics`
- `v_skill_assessment_summary`
- `v_skill_misconceptions`
- `v_skill_prerequisites`

Luu y: mot so README cu trong module storage van ghi 17 tables va 3 views. Bao cao validation moi nhat xac nhan schema hien tai co 22 tables va 5 views.

## 14. Repository va service layer

`KnowledgeRepository` cung cap lop truy cap du lieu chi doc, co ho tro knowledge version va da duoc kiem tra voi SQLite.

`KnowledgeService` cung cap cac context phuc vu ung dung:

- Skill context va source evidence.
- Prerequisite paths va deterministic unlock checks.
- Learning objectives va CEFR profiles.
- Assessment profiles.
- Misconceptions va diagnostic evidence da duoc chap nhan.

Service khong tu thuc hien adaptive sequencing, mastery estimation, activity selection, exercise generation, feedback generation hoac LLM calls.

## 15. Quy mo thu muc du lieu

| Thu muc | So file | Kich thuoc xap xi |
|---|---:|---:|
| `data/raw` | 2,005 | 3,669.09 MB |
| `data/external` | 28 | 2.18 MB |
| `data/interim` | 29 | 13,295.65 MB |
| `data/curated` | 31 | 3.94 MB |
| `data/reports` | 41 | 2.38 MB |
| `data/sqlite` | 1 | 4.12 MB |
| `data/vector_store` | 5 | 0.99 MB |
| `data/processed` | 3 | 0.40 MB |
| `data/evaluation` | 1 | 0.01 MB |

`data/interim` co kich thuoc lon nhat do chua hon 6.2 trieu error instances va hon 1.18 trieu source records cua EFCAMDAT.

## 16. Artifact chinh

| Artifact | So records |
|---|---:|
| `data/interim/english_profile/grammar/egp_records.jsonl` | 273 |
| `data/interim/cefr/cefr_descriptors.jsonl` | 334 |
| `data/interim/cefr/cefr_learning_objective_candidates.jsonl` | 292 |
| `data/interim/knowledge_alignment/cefr_egp_alignment.jsonl` | 43 |
| `data/interim/knowledge_alignment/skill_source_evidence.jsonl` | 205 |
| `data/curated/relationships/grammar_relationships.jsonl` | 93 |
| `data/curated/assessment/grammar_assessment_criteria.jsonl` | 79 |
| `data/curated/assessment/grammar_assessment_profiles.jsonl` | 43 |
| `data/interim/clc_fce/source_records.jsonl` | 2,543 |
| `data/interim/clc_fce/error_instances.jsonl` | 53,417 |
| `data/interim/efcamdat/source_records.jsonl` | 1,180,309 |
| `data/interim/efcamdat/error_instances.jsonl` | 6,169,013 |
| `data/interim/corpus_errors/error_skill_mappings.jsonl` | 822 |
| `data/curated/error_mapping/unresolved_error_skill_mappings.jsonl` | 822 |
| `data/curated/error_mapping/accepted_error_skill_mappings.jsonl` | 0 |
| `data/interim/misconceptions/candidate_misconceptions.jsonl` | 1 |
| `data/curated/misconceptions/accepted_misconceptions.jsonl` | 0 |

## 17. Trang thai hoan thanh

| Hang muc | Trang thai |
|---|---|
| Canonical Grammar V1 | Hoan thanh |
| EGP ingestion va mapping | Hoan thanh; con mapping can review |
| CEFR extraction | Hoan thanh |
| CEFR-EGP alignment | Hoan thanh |
| Relationships/prerequisites | Hoan thanh |
| Source Inventory V1 | Hoan thanh |
| EFCAMDAT ingestion | Hoan thanh |
| CLC FCE ingestion | Hoan thanh |
| UD EWT structural ingestion | Hoan thanh |
| Write & Improve ingestion | Chua bat dau |
| Error normalization | Hoan thanh |
| Error-skill human review | Chua hoan thanh |
| Misconception candidate mining | Hoan thanh |
| Misconception human review | Chua hoan thanh |
| Assessment Criteria V1 | Hoan thanh |
| Global validation | PASS tren local/SQLite |
| Knowledge storage | Hoan thanh tren SQLite |
| KnowledgeRepository | Hoan thanh |
| KnowledgeService V1 | Hoan thanh va da verify tren SQLite |

## 18. Ton dong va gioi han

1. Ca 822 error-skill mappings dang cho human review, nen chua co accepted mapping trong storage.
2. Mot misconception candidate dang cho review; chua co accepted misconception de lam diagnostic evidence.
3. Write & Improve da duoc inventory nhung chua duoc ingest.
4. SQLite chi luu aggregate corpus-error statistics, mappings va evidence links; khong nap toan bo 6.2 trieu normalized error instances vao database.
5. Live PostgreSQL validation chua duoc chay. Vi vay chua the dua ra production persistence claim cho PostgreSQL.
6. Mot so license metadata cua EGP, CEFR va Write & Improve van can manual review; FCE co README cuc bo nhung thieu license file cu the.

De chay PostgreSQL validation can:

```text
KNOWLEDGE_CORE_RUN_POSTGRES_VALIDATION=1
POSTGRES_DATABASE_URL=<reachable PostgreSQL URL>
```

## 19. Tai lieu va bao cao tham chieu

- Ke hoach chinh: `KNOWLEDGE_CORE_V1_PLAN.md`
- Bao cao validation tong the: `data/reports/knowledge_core_v1_report.json`
- Source inventory: `data/reports/source_inventory/source_inventory.md`
- Database SQLite: `data/sqlite/app.db`
- Ma nguon Knowledge Core: `knowledge_core/`

## 20. Ket luan

Knowledge Core V1 da co mot nen tang Grammar kha day du: 43 atomic skills, mapping EGP/CEFR, graph quan he hop le, assessment criteria cho toan bo skill, hon 6.2 trieu loi nguoi hoc da chuan hoa, storage SQLite va service layer chi doc. Phan cot loi da vuot global validation; khoang trong chinh hien nay la human review cho error-skill mappings va misconception, ingestion Write & Improve, va validation thuc te tren PostgreSQL.
