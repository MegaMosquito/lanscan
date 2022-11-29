#
# lanscan  -- implements an IP LAN host discovery REST API service
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#

NAME         := lanscan
DOCKERHUB_ID := ibmosquito
VERSION      := 1.0.0

# Useful bits from https://github.com/MegaMosquito/netstuff/blob/master/Makefile
LOCAL_DEFAULT_ROUTE     := $(shell sh -c "ip route | grep default | sed 's/dhcp src //'")
LOCAL_ROUTER_ADDRESS    := $(word 3, $(LOCAL_DEFAULT_ROUTE))
LOCAL_DEFAULT_INTERFACE := $(word 5, $(LOCAL_DEFAULT_ROUTE))
LOCAL_IP_ADDRESS        := $(word 7, $(LOCAL_DEFAULT_ROUTE))
LOCAL_MAC_ADDRESS       := $(shell sh -c "ip link show | sed 'N;s/\n/ /' | grep $(LOCAL_DEFAULT_INTERFACE) | head -1 | sed 's/.*ether //;s/ .*//;'")
LOCAL_SUBNET_CIDR       := $(shell sh -c "echo $(wordlist 1, 3, $(subst ., ,$(LOCAL_IP_ADDRESS))) | sed 's/ /./g;s|.*|&.0/24|'")

# You may optionally override these "MY_" variables in your shell environment
MY_SUBNET_CIDR        ?= $(LOCAL_SUBNET_CIDR)
MY_HOST_IPV4          ?= $(LOCAL_IP_ADDRESS)
MY_HOST_MAC           ?= $(LOCAL_MAC_ADDRESS)
MY_REST_API_BASE_URL  ?= /$(NAME)
MY_REST_API_PORT      ?= 8003# Note that --network=host so this is a host port!
MY_NUM_PROCESSES      ?= 40

# Running `make` with no target builds and runs this as a restarting daemon
default: build run

# Check the values of the "MY_" variables
chkvars:
	@echo "MY_SUBNET_CIDR:      = \"$(MY_SUBNET_CIDR)\""
	@echo "MY_HOST_IPV4:        = \"$(MY_HOST_IPV4)\""
	@echo "MY_HOST_MAC:         = \"$(MY_HOST_MAC)\""
	@echo "MY_REST_API_BASE_URL = \"$(MY_REST_API_BASE_URL)\""
	@echo "MY_REST_API_PORT     = \"$(MY_REST_API_PORT)\""
	@echo "MY_NUM_PROCESSES     = \"$(MY_NUM_PROCESSES)\""

# Build the container and tag it
build:
	docker build -t $(DOCKERHUB_ID)/$(NAME):$(VERSION) .

# Running `make dev` will setup a working environment, just the way I like it.
# On entry to the container's bash shell, run `cd /outside` to work here.
dev: stop build
	docker run -it --volume `pwd`:/outside \
	  --privileged --network=host \
	  --volume /proc/net/arp:/host_arp_table \
	  --name $(NAME) \
	  -e MY_SUBNET_CIDR=$(MY_SUBNET_CIDR) \
	  -e MY_HOST_IPV4=$(MY_HOST_IPV4) \
	  -e MY_HOST_MAC=$(MY_HOST_MAC) \
	  -e MY_REST_API_BASE_URL=$(MY_REST_API_BASE_URL) \
	  -e MY_REST_API_PORT=$(MY_REST_API_PORT) \
	  -e MY_NUM_PROCESSES=$(MY_NUM_PROCESSES) \
	  $(DOCKERHUB_ID)/$(NAME):$(VERSION) /bin/bash

# Run the container as a daemon (build not forecd here, so build it first)
run: stop
	docker run -d --restart unless-stopped \
	  --privileged --network=host \
	  --volume /proc/net/arp:/host_arp_table \
	  --name $(NAME) \
	  -e MY_SUBNET_CIDR=$(MY_SUBNET_CIDR) \
	  -e MY_HOST_IPV4=$(MY_HOST_IPV4) \
	  -e MY_HOST_MAC=$(MY_HOST_MAC) \
	  -e MY_REST_API_BASE_URL=$(MY_REST_API_BASE_URL) \
	  -e MY_REST_API_PORT=$(MY_REST_API_PORT) \
	  -e MY_NUM_PROCESSES=$(MY_NUM_PROCESSES) \
	  $(DOCKERHUB_ID)/$(NAME):$(VERSION)

# Test the service by retrieving a JSON snapshot
# You may wish to pipe this to `jq`, e.g., `make test | jq .`
test:
	@curl -s localhost:$(MY_REST_API_PORT)/$(MY_REST_API_BASE_URL)/json

# Enter the context of the daemon container
exec:
	@docker exec -it ${NAME} /bin/sh

# Push the conatiner to DockerHub (you need to `docker login` first of course)
push:
	docker push $(DOCKERHUB_ID)/$(NAME):$(VERSION) 

# Stop the daemon container
stop:
	@docker rm -f ${NAME} >/dev/null 2>&1 || :

# Stop the daemon container, and cleanup
clean: stop
	@docker rmi -f $(DOCKERHUB_ID)/$(NAME):$(VERSION) >/dev/null 2>&1 || :

# Declare all of these non-file-system targets as .PHONY
.PHONY: default build dev run test exec push stop clean

