# Next.js Frontend

This folder contains the Next.js UI for the personalized English exercise chatbot.

## Stack

- Next.js App Router
- React
- TypeScript
- ESLint

## Intent

The frontend calls the Python backend for:

- parsing learner requests
- generating personalized exercises
- scoring answers
- returning recommendations and profile updates

## Expected integration

Current API endpoints used or planned:

- `POST /api/practice/generate`
- `POST /api/practice/score`
- `GET /api/health`

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
