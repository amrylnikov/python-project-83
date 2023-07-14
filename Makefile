install:
	poetry install

run:
	poetry run app

dev:
	poetry run flask --app page_analyzer:app run

now:
	flask --app page_analyzer/app --debug run --port 8000

PORT ?= 8000
start:
	poetry run gunicorn -w 5 -b 0.0.0.0:$(PORT) page_analyzer:app
