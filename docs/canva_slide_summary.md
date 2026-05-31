# Tóm tắt đề tài cho Canva Slide

Tài liệu này tổng hợp các ý chính của đề tài theo dạng bảng, phù hợp để dán vào Canva hoặc dùng làm nguồn tạo slide tự động.

| Hạng mục | Nội dung |
|---|---|
| Tên đề tài | Xây dựng chatbot sinh bài tập tiếng Anh cá nhân hóa sử dụng truy xuất ngữ nghĩa và mô hình Transformer |
| Tên tiếng Anh | Personalized English Exercise Generation using Semantic Retrieval and Transformer-based Models |
| Bài toán | Nhiều người học tiếng Anh chưa biết mình yếu phần nào, bài tập chưa phù hợp trình độ, thiếu giải thích lỗi sai và chưa có lộ trình luyện tập tiếp theo |
| Mục tiêu tổng quát | Xây dựng hệ thống chatbot có khả năng sinh bài tập tiếng Anh cá nhân hóa dựa trên yêu cầu người học, trình độ, lịch sử làm bài và điểm yếu |
| Mục tiêu cụ thể | Phân tích yêu cầu tự nhiên, truy xuất kiến thức liên quan, sinh bài tập, tạo đáp án và giải thích, chấm bài, phân tích lỗi sai, cập nhật hồ sơ học tập, đề xuất bài luyện tiếp theo |
| Đối tượng sử dụng | Người mới học tiếng Anh, học sinh, sinh viên, người đi làm muốn ôn ngữ pháp, người học cần luyện theo điểm yếu cá nhân |
| Phạm vi MVP | Grammar MCQ, Vocabulary MCQ, Fill-in-the-blank, cá nhân hóa theo learner profile, error analysis mức topic/subtopic, recommendation cho lượt học tiếp theo |
| Ngoài phạm vi MVP | Speaking practice, pronunciation assessment, essay writing correction, voice chatbot, adaptive learning nâng cao, fine-tune nội bộ |
| Ý tưởng cốt lõi | Kết hợp RAG + prompt engineering + rule-based personalization để tạo bài tập phù hợp từng người học |
| Workflow hệ thống | User Input → Intent Extraction → User Profile Retrieval → Topic & Difficulty Selection → Knowledge Retrieval → Context Selection → Exercise Generation → Validation → User Answers → Answer Checking → Error Analysis → Update Topic Stats → Recommendation |
| Kiến trúc hệ thống | Interaction Layer, API & Orchestration Layer, Retrieval Layer, Generation Layer, Personalization Layer |
| Giao diện | Next.js App Router, giao diện chatbot/web dashboard cho nhập yêu cầu, làm bài, xem kết quả và gợi ý |
| Backend | FastAPI cung cấp API generate, score, healthcheck và điều phối pipeline xử lý |
| Orchestration | LangChain dùng cho prompt chain, retrieval flow, output parsing và khả năng thay backend model linh hoạt |
| Retrieval | Knowledge chunks được embedding và lưu trong Chroma để semantic search theo topic, level, skill |
| Generation | LLM backend linh hoạt, có thể dùng OpenAI hoặc Ollama/local model để sinh câu hỏi, đáp án, distractor và explanation |
| Validation | Kiểm tra đủ số câu hỏi, đúng topic, đúng format, MCQ có 4 lựa chọn, chỉ 1 đáp án đúng, explanation không rỗng |
| Cá nhân hóa | Dựa trên learner level, preferred difficulty, topic accuracy, weak topics, lịch sử luyện tập và recommendation rules |
| Knowledge Base | Nguồn đề xuất: British Council LearnEnglish, Perfect English Grammar, EF English Grammar Guide |
| Exercise Bank | Nguồn đề xuất: Perfect English Grammar, All Things Grammar, các bộ bài tập grammar public khác |
| Error Analysis Data | Có thể tham khảo Kaggle Grammar Error Correction Dataset và Hugging Face grammar-correction datasets, nhưng MVP ưu tiên rule-based tags từ câu sai, topic và subtopic |
| Data MVP | 6 topic chính: Tenses, Passive Voice, Relative Clauses, Conditionals, Reported Speech, Prepositions |
| Quy mô dữ liệu MVP | Mỗi topic 15-25 grammar chunks và 30-50 exercise samples, tổng khoảng 120 grammar chunks và 300 bài tập mẫu |
| Knowledge Chunk Format | chunk_id, topic_code, subtopic, level, skill, content, formula, examples, common_mistakes, source, language |
| Exercise Format | exercise_code, exercise_type, topic_code, subtopic, level, difficulty, question_text, options, correct_answer, explanation, source |
| Lưu trữ dữ liệu | SQLite lưu dữ liệu có cấu trúc như user profile, session, answers, generation runs; Chroma lưu embeddings và metadata retrieval |
| Bảng dữ liệu chính | topics, knowledge_chunks, seed_exercises, seed_exercise_options, users, user_profiles, generation_runs, practice_sessions, session_exercises, session_exercise_options, user_answers, user_topic_stats, evaluation_records |
| Evaluation | Question Quality, Retrieval Quality, Personalization Quality, User Performance |
| Chỉ số đánh giá | Fluency, Relevance, Answerability, Distractor Quality, Difficulty Appropriateness, Weakness Targeting, Recommendation Usefulness, Accuracy by Topic, Improvement Rate |
| Roadmap | Tuần 1 chuẩn bị dữ liệu; Tuần 2 xây knowledge base và retrieval; Tuần 3 xây generation pipeline; Tuần 4 xây personalization và database; Tuần 5 xây UI demo; Tuần 6 evaluation và hoàn thiện báo cáo |
| Future Work | Fine-tune mô hình sinh bài tập, speaking, pronunciation, essay correction, spaced repetition, adaptive learning, mở rộng CEFR và thêm chủ đề/kỹ năng |
| Điểm mạnh đề tài | Có ứng dụng thực tế, có đủ yếu tố NLP, có retrieval bằng vector DB, có generation bằng LLM, có chatbot UI, có personalization loop, có thể demo trực quan |
| Kết quả kỳ vọng | Hệ thống có thể sinh bài tập cá nhân hóa, chấm bài, giải thích, phân tích lỗi sai, cập nhật hồ sơ học tập và đề xuất lượt luyện tập tiếp theo |
| Stack triển khai hiện tại | Next.js + FastAPI + LangChain + SQLite + Chroma + OpenAI/Ollama + Docker |
| Thông điệp demo | Không phải ai cũng nên làm cùng một bài tập; hệ thống sẽ tạo bài luyện riêng cho từng người học dựa trên dữ liệu học tập của họ |
| Tính khả thi MVP | Phạm vi vừa đủ cho đồ án NLP, có thể triển khai end-to-end, demo rõ ràng và mở rộng về sau |

## Gợi ý dùng với Canva

- Nếu cần bảng đầy đủ: copy toàn bộ bảng trên.
- Nếu cần slide ngắn gọn hơn: chọn các dòng `Bài toán`, `Mục tiêu tổng quát`, `Phạm vi MVP`, `Kiến trúc hệ thống`, `Stack triển khai hiện tại`, `Quy mô dữ liệu MVP`, `Điểm mạnh đề tài`, `Kết quả kỳ vọng`.
- Nếu cần tạo slide tự động bằng prompt, có thể dùng file này làm nguồn nội dung đầu vào.
