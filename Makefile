.PHONY: install run test infra benchmark sample-report

install:
	python -m pip install -r requirements.txt

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -q

infra:
	docker compose up -d postgres redis

benchmark:
	locust -f benchmarks/locustfile.py --host http://localhost:8000

sample-report:
	python benchmarks/generate_sample_results.py
	python benchmarks/analyze_results.py --input benchmarks/results/sample_results.csv --prefix sample
