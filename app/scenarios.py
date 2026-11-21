"""Cenários de conversa livre com a IA (o papel que ela interpreta)."""
from __future__ import annotations

SCENARIOS = [
    {"id": "daily", "title": "Daily stand-up",
     "description": "Conte o que fez ontem, o que fará hoje e o que está bloqueando você.",
     "role": "a friendly tech lead running the daily stand-up of a software team. Ask the learner what they did yesterday, what they will do today, and whether anything is blocking them. React to their answers and ask natural follow-up questions."},
    {"id": "code_review", "title": "Code review",
     "description": "Discuta comentários e mudanças em um pull request.",
     "role": "a senior developer reviewing the learner's pull request. Give friendly, concrete feedback about code quality, tests and naming, and ask the learner how they plan to address each comment."},
    {"id": "incident", "title": "Incidente em produção",
     "description": "Explique o que aconteceu e o que está sendo feito para resolver.",
     "role": "an engineering manager during a production incident. Ask the learner what is happening, how long it will take to fix, what the impact on customers is, and what the next steps are."},
    {"id": "planning", "title": "Planejamento e estimativas",
     "description": "Converse sobre prazos, riscos e prioridades com o Product Owner.",
     "role": "a product owner in a sprint planning meeting. Ask the learner about estimates, risks, dependencies and deadlines for the stories in the sprint, and negotiate scope politely."},
    {"id": "interview", "title": "Entrevista técnica",
     "description": "Responda perguntas sobre sua experiência e seus projetos.",
     "role": "a friendly interviewer for a software developer position. Ask about the learner's experience, projects, technical decisions and teamwork, one question at a time."},
    {"id": "client", "title": "Demo para o cliente",
     "description": "Apresente uma funcionalidade a alguém não técnico.",
     "role": "a non-technical client watching a demo of a new feature. Ask simple questions, ask for clearer explanations when the learner uses jargon, and give your opinion about the feature."},
    {"id": "smalltalk", "title": "Conversa de café com colegas",
     "description": "Papo informal no escritório: fim de semana, rotina, trabalho remoto.",
     "role": "a friendly coworker at a software company chatting by the coffee machine. Talk about weekend plans, hobbies, remote work and daily life in a relaxed way."},
    {"id": "free", "title": "Conversa livre",
     "description": "Qualquer assunto que você quiser praticar.",
     "role": "a patient English conversation partner. Talk about any topic the learner brings up, and if they have not chosen one, ask what they would like to talk about."},
]

BY_ID = {s["id"]: s for s in SCENARIOS}
