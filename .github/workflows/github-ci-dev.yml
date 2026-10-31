name: base-ci

on:
  pull_request:
    branches: ["develop"]

permissions:
  contents: read

concurrency:
  group: base-ci-${{ github.ref }}
  cancel-in-progress: true

env:
  DOCKER_BUILDKIT: "1"

jobs:
  ruff-sca:
    name: ruff
    runs-on: afaci-runner-01
    steps:
      - name: Checkout code
        uses: actions/checkout@v5

      - name: Set up Python
        uses: actions/setup-python@v6
        with:
          python-version: "3.11"
          cache: pip
          cache-dependency-path: requirements.txt

      - name: Install ruff
        run: pip install ruff

      - name: Run Ruff (Linting)
        run: ruff check .

      - name: Run Ruff (Format Check)
        run: ruff format --check .

  build-and-deploy:
    name: build & deploy
    runs-on: afaci-runner-01
    needs: ruff-sca
    env:
      DOCKER_HOST: ${{ secrets.DOCKER_HOST }}
      BACKEND_IMAGE: ${{ secrets.IMAGE_NAME }}:${{ github.sha }}
    steps:
      - name: Check out repository
        uses: actions/checkout@v5

      - name: Build image
        run: docker build -t "$BACKEND_IMAGE" .

      - name: Deploy to devops-server (external daemon)
        env:
          POSTGRES_USER: ${{ secrets.POSTGRES_USER }}
          POSTGRES_PASSWORD: ${{ secrets.POSTGRES_PASSWORD }}
          POSTGRES_DB: ${{ secrets.POSTGRES_DB }}
          JWT_SECRET: ${{ secrets.JWT_SECRET }}
          JWT_ALGORITHM: ${{ secrets.JWT_ALGORITHM || 'HS256' }}
          ACCESS_TOKEN_EXPIRE_MINUTES: ${{ secrets.ACCESS_TOKEN_EXPIRE_MINUTES || '10080' }}
          BACKEND_PORT: ${{ secrets.BACKEND_PORT || '8000' }}
        run: docker compose -f - up -d --pull missing < docker-compose.yml

      - name: Remove dangling images
        if: always()
        run: docker image prune -f
