# Next.js Frontend

This folder contains the Next.js UI for the personalized English exercise chatbot.

## Stack

- Next.js App Router
- React
- TypeScript
- ESLint

## Intent

The frontend calls the Python backend for:

- conversation turns and intent routing
- creating learning activities for practice
- submitting answers by `activity_id`
- returning structured recommendations and profile updates

## Expected integration

Current API endpoints used or planned:

- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/{conversation_id}`
- `POST /api/conversations/{conversation_id}/messages`
- `GET /api/activities/{activity_id}`
- `GET /api/activities/{activity_id}/review`
- `POST /api/activities/{activity_id}/submit`
- `GET /api/learners/{learner_id}/profile`
- `PATCH /api/learners/{learner_id}/profile`
- `GET /api/learners/{learner_id}/mastery`
- `GET /api/learners/{learner_id}/progress`
- `GET /api/learners/{learner_id}/recommendations`
- `POST /api/recommendations/{recommendation_id}/accept`
- `GET /api/users/{user_id}/personalization`
- `GET /api/health`

Compatibility endpoints kept for older clients:

- `POST /api/practice/generate`
- `POST /api/practice/score`
- `PATCH /api/users/{user_id}/profile`
- `GET /api/recommendations?user_id={user_id}`

## Run locally

```bash
npm install
npm run dev
```

## Run with Docker

From the project root:

```bash
docker compose up --build
```
