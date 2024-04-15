all: build

help: 
	@cat Makefile

build: 
	bash -e ../scripts/build.sh
	
update: 
	bash -e ../scripts/update-packages.sh

deploy: build
	cdk deploy --all

clean:
	git clean -fdx