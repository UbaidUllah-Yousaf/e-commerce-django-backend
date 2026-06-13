---
name: django-migrations-pr
description: Blocks automatic database migrations, runs makemigrations when model changes exist before a PR from development, and keeps migration files reviewable. Use when the user opens or prepares a pull request from development, mentions migrate or makemigrations, changes Django models, or asks to sync the database after schema edits.
---

# Django migrations and PRs from development

## Non-negotiable: never auto-apply migrations

- **Do not** run `python manage.py migrate` unless the user **explicitly** asks to apply migrations to their database.
- It is fine to run **`makemigrations`** (generates files only) when detecting model changes before a PR, as below.

## When the user is creating a PR from `development` (or merging into it)

1. If the branch touched **Django models** or related schema (constraints, indexes, swappable deps), run **`makemigrations`** from the app directory that contains `manage.py` (this repo: `ecommerce/`).
   - Example: `venv/bin/python manage.py makemigrations`
2. If the command reports **no changes**, stop; do not invent migrations.
3. If it creates or updates migration files, **include them in the PR** and mention them in the PR summary.
4. **Do not** run `migrate` as part of PR prep unless the user clearly requests it.

## Commands (this repository)

- Working directory: `ecommerce/` (where `manage.py` lives).
- Prefer the project venv interpreter: `venv/bin/python manage.py makemigrations` [optional app label].

## Edge cases

- **Multiple apps:** run `makemigrations` without a label first so Django picks up all apps; use a label only when scoping intentionally.
- **Merge migrations:** if Django prompts for merge migrations, create them and commit like any other migration—still no `migrate` unless asked.
