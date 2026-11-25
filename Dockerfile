FROM python:3.11-slim

WORKDIR /app

# Copy all application files
COPY . /app

# Hugging Face Spaces listens on port 7860 by default
ENV PORT=7860
EXPOSE 7860

CMD ["python3", "server.py"]
