# First resource your shell with $ source venv/bin/activate

freeze:
	pip3 freeze > requirements.txt

build:
	docker build -t powerchainger:hwe-skt-proxy-latest .

run:
	docker run --name HWE-SKT-Proxy powerchainger:hwe-skt-proxy-latest

stop:
	docker stop HWE-SKT-Proxy

clear:
	docker image prune
	docker rm HWE-SKT-Proxy

lint: 
	autopep8 src --in-place --recursive
	pylint src