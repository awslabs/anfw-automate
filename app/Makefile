all: pre-synth build

help: 
	@cat Makefile

build: 
	bash -e ../scripts/build.sh
	
update: 
	bash -e ../scripts/update-packages.sh

pre-synth:
	bash -e scripts/package.sh

deploy: all
	cdk deploy --all

clean:
	git clean -fdx