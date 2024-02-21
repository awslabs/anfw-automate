all: pre-synth build

help: 
	@cat Makefile

build: 
	bash -e scripts/build.sh
	
update: 
	bash -e scripts/update-packages.sh

pre-synth:
	bash -e scripts/pre-synth-script.sh

deploy: pre-synth	
	cdk deploy

clean:
	git clean -fdx