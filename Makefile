help: 
	@cat Makefile

build: 
	cd app && make all
	cd firewall && make all
	cd vpc && make all
	
update: 
	cd app && make update
	cd firewall && make update
	cd vpc && make update

deploy: build	
	cdk deploy --all

clean:
	git clean -fdx