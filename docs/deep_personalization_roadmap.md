# Deep Personalization Roadmap

Muc tieu: nang cap he thong tu rule-based personalization MVP len learner model sau hon, co tri nho theo topic, subtopic, error pattern va adaptive difficulty.

## Trang thai hien tai

- Da co SQLite persistence cho user profile, generation runs, practice sessions, user answers va topic stats.
- Da co seed exercises co `subtopic` va `error_tag`.
- Da co generation bang Ollama/fallback, validation va seed-bank fallback.
- Da co bilingual request normalization Viet/Anh.
- Personalization hien tai moi o muc topic-level: chon topic yeu, difficulty tu level/preference, update accuracy theo topic.

## Phase 1 - Data Foundation

Trang thai: Done.

Can lam:

- Them `skill`, `subtopic`, `error_tag` vao generated/session exercises.
- Them bang `user_subtopic_stats` de luu mastery/weakness theo subtopic.
- Them bang `user_error_stats` de luu ti le sai theo error pattern.
- Migrate SQLite hien co bang `_ensure_column`.
- Load cac stats moi vao `LearnerProfile`.

Ket qua mong doi:

- Moi cau hoi biet no dang target subtopic nao va loi sai nao.
- Sau moi bai lam, he thong co du lieu chi tiet hon score tong.

## Phase 2 - Metadata-Aware Generation

Trang thai: Done.

Can lam:

- Mo rong `ExerciseItem` va output parser de nhan `skill`, `subtopic`, `error_tag`.
- Prompt LLM yeu cau sinh metadata cho moi cau.
- Seed fallback copy metadata tu seed bank.
- Neu LLM thieu metadata, service infer tu plan/chunks/seed examples.

Ket qua mong doi:

- Bai sinh moi co the cham va cap nhat loi chi tiet.

## Phase 3 - Deep Scoring

Trang thai: Done.

Can lam:

- Khi user tra loi, update topic stats, subtopic stats va error stats.
- Dung cumulative accuracy + mastery score, khong chi ghi de bang session gan nhat.
- Luu `error_tag` that cua cau sai vao `user_answers`.

Ket qua mong doi:

- He thong biet nguoi hoc yeu `passive_voice:present_simple_passive` hay hay sai `missing_be`.

## Phase 4 - Adaptive Planner

Trang thai: First version done.

Can lam:

- `PracticePlan` co `target_subtopic`, `target_error_tag`, `learner_summary`.
- Neu user noi chung chung, planner chon weak subtopic/error tag uu tien.
- Difficulty tu dong tang/giam theo mastery va accuracy.
- Focus reason giai thich vi sao chon bai nay.

Ket qua mong doi:

- Yeu cau kieu "cho minh luyen tiep" co the tao bai dung diem yeu that.

## Phase 5 - Personalized Prompting

Trang thai: First version done.

Can lam:

- Dua learner summary vao prompt LLM.
- Neu co `target_error_tag`, sinh distractors gan loi sai cua nguoi hoc.
- Recommendation noi ro loi sai va buoc tiep theo.

Ket qua mong doi:

- Bai tap va giai thich co cam giac "viet rieng cho nguoi hoc nay".

## Phase 6 - UI And Evaluation

Trang thai: UI first version done, evaluation pending.

Can lam:

- Frontend hien weak topics, weak subtopics va frequent errors.
- Cho phep user khac nhau thay vi hardcode `demo-user`.
- Them tests cho parser, personalization, repository, agent scoring.
- Them evaluation metric: weakness targeting, level appropriateness, recommendation usefulness.

Ket qua mong doi:

- Demo co bang chung ro rang cho personalization quality.

Da lam:

- Them trang `/personalization` dung Ant Design de hien topic stats, subtopic mastery, frequent errors va next personalized plan.
- Them API `/api/users/{user_id}/personalization` de frontend doc du lieu ca nhan hoa that tu backend.
- Them onboarding modal truoc chatbot va API `PATCH /api/users/{user_id}/profile` de luu level, goals, preferred difficulty, preferred question count va weak topics tu khai bao.

Con lai:

- Them user selector/login de khong con hardcode `demo-user`.
- Them test suite va evaluation metrics.

## Thu tu thuc hien de an toan

1. Phase 1 + 2 + 3: tao nen data va metadata.
2. Phase 4: dung data do de lap ke hoach adaptive.
3. Phase 5: dua learner model vao prompt/recommendation.
4. Phase 6: hien thi va do luong.
