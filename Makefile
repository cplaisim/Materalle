.PHONY: up down build logs migrate shell test createsuperuser restart clean

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --parallel && docker compose up -d

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

logs-mobile:
	docker compose logs -f mobile

migrate:
	docker compose exec backend python manage.py migrate

makemigrations:
	docker compose exec backend python manage.py makemigrations

shell:
	docker compose exec backend python manage.py shell

test:
	docker compose exec backend python manage.py test

createsuperuser:
	docker compose exec backend python manage.py createsuperuser

restart:
	docker compose restart backend frontend mobile

clean:
	docker compose down -v --rmi local
