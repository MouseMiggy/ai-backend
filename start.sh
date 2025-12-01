# Production startup script for AgriLink AI Backend
gunicorn app:app --bind 0.0.0.0:$PORT