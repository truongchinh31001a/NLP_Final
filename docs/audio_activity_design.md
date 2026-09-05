# Audio Activity Design

Phase 21 turns the planned listening and speaking work into a concrete contract.
It does not enable runtime audio yet. The next implementation phase can add the
activity types and UI against this design.

## Decisions

- STT for speaking feedback starts with browser Web Speech API transcript
  capture. It keeps the MVP low-friction, avoids backend audio handling by
  default, and works well enough for short practice prompts.
- Manual transcript entry is always available when browser Web Speech is not
  supported, permission is denied, or recognition quality is poor.
- Server-side STT remains a provider adapter behind the backend for later:
  OpenAI-compatible Whisper for quality/cloud deployments, or local Whisper /
  faster-whisper for private/offline deployments.
- TTS for listening starts with browser SpeechSynthesis. The backend provides
  the transcript and metadata; the browser renders audio and hides the transcript
  until the activity policy allows reveal.
- Generated audio files or external TTS can be added later only when voice
  consistency, phoneme marks, or shareable audio artifacts become product
  requirements.
- No raw audio is stored by default. The canonical submitted artifact is text
  transcript plus safe attempt metadata.

## ListeningActivity Metadata

Listening activities should be stored as `LearningActivity` records with
`type=LISTENING` once the enum is enabled. Until then, the router can keep
listening requests as planned `GENERAL` turns.

Example `LearningActivity.metadata`:

```json
{
  "mode": "listening",
  "audio_source": {
    "kind": "browser_tts",
    "voice_hint": "en-US",
    "rate": 0.95,
    "transcript_ref": "metadata.transcript"
  },
  "transcript": "The museum opens at nine and closes at five.",
  "target_skills": ["listening.main_idea", "listening.detail"],
  "target_vocabulary": ["museum", "opens", "closes"],
  "comprehension_prompts": [
    {
      "exercise_id": "listen_001_q1",
      "question_text": "What time does the museum open?",
      "options": [
        {"label": "A", "text": "At nine"},
        {"label": "B", "text": "At five"}
      ],
      "correct_answer": "A"
    }
  ],
  "replay_policy": {
    "max_replays": 3,
    "allow_speed_control": true
  },
  "reveal_policy": {
    "show_transcript_after_submit": true
  }
}
```

## SpeakingActivity Metadata

Speaking activities should also be stored as `LearningActivity` records with
`type=SPEAKING` once the enum is enabled. The backend scores submitted
transcripts first; audio-quality scoring can be added when a server STT provider
is selected.

Example `LearningActivity.metadata`:

```json
{
  "mode": "speaking",
  "prompt": "Order a small coffee politely.",
  "expected_patterns": ["could i have", "small coffee", "please"],
  "target_skills": ["speaking.polite_requests", "speaking.fluency_short_turn"],
  "rubric": {
    "pronunciation": 0.3,
    "fluency": 0.25,
    "grammar": 0.25,
    "task_completion": 0.2
  },
  "retry_policy": {
    "max_attempts": 3,
    "keep_best_score": true
  },
  "stt": {
    "preferred": "browser_web_speech",
    "allow_manual_transcript": true
  }
}
```

## Persistence

- `LearningActivity.metadata` stores the prompt, transcript source,
  comprehension prompts, rubric, replay policy, retry policy, and target skills.
- `LearningActivity.result` stores submitted answers, final transcript,
  score/rubric feedback, and attempt summaries after submission.
- Raw microphone audio is not persisted by default.
- Interim transcript text stays client-side until the learner submits it.
- Optional future audio persistence must use explicit consent, artifact ids or
  signed URLs instead of inline blobs, short TTL by default, size limits,
  content-type allowlists, and a deletion path.
- Generated listening audio artifacts, if added later, should store a stable
  `audio_artifact_id`, provider, voice, duration, checksum, and transcript ref.

## API Contract

Creation remains conversation-first:

```text
POST /api/conversations/{conversation_id}/messages
```

The future route response should return `intent=LISTENING` or
`intent=SPEAKING`, `ui_action=listening.start` or `ui_action=speaking.start`,
and a normal activity envelope. Until the enum and services exist, listening and
speaking requests stay as `GENERAL` with a planned-activity assistant reply.

Fetching remains canonical:

```text
GET /api/activities/{activity_id}?user_id={user_id}
```

Submission remains canonical:

```text
POST /api/activities/{activity_id}/submit
```

Listening submissions send selected answers:

```json
{
  "answers": {
    "listen_001_q1": "A"
  }
}
```

Speaking submissions send transcript-first attempt data:

```json
{
  "transcript": "Could I have a small coffee, please?",
  "stt_confidence": 0.88,
  "duration_ms": 4200,
  "attempt_number": 1
}
```

Raw audio blobs are intentionally absent from the default submit payload.

## Frontend Controls

Listening UI:

- Play, pause, stop, and replay controls.
- Replay counter and disabled state after `replay_policy.max_replays`.
- Speech rate control when `allow_speed_control` is true.
- Transcript hidden before submit unless the reveal policy says otherwise.
- Standard answer selection, submit, result, and review states.

Speaking UI:

- Microphone permission state shown before recording.
- Record, stop, playback-preview when available, transcript preview/edit, submit,
  retry, and result controls.
- Manual transcript input remains visible or one click away.
- Rubric result shows pronunciation, fluency, grammar, task completion, and
  short next-step feedback.
- The browser asks for microphone permission only after the learner clicks
  record.

## Eval Dataset

`evals/datasets/audio_activity_cases.json` is the Phase 21 seed dataset. It
checks:

- listening metadata has an audio source, transcript, comprehension prompts,
  and replay policy;
- listening submissions use answers, not raw audio;
- speaking metadata has prompt, expected patterns, rubric, retry policy, and
  manual transcript fallback;
- speaking submissions use transcript-first scoring data;
- privacy guardrails reject default raw audio persistence.
