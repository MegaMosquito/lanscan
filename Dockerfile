#
# A network monitor daemon container that scans a "/24" LAN to discover hosts
# and makes this data available through a REST API..
#
# This code is intended to replace previous work I have done using `nmap`
# and direct ARP pings, each of which had problems. This is simpler, faster,
# and should more reliably collect *all* hosts on the IP LAN than the others.
#
# My methodology here relies on the underlying IP stack performing an ARP
# probe before the ICMP echo request is sent for the `ping` command. My
# code uses `ping` but ignores its result then directly looks into the
# host's `/proc/net/arp` (the standard GNU/Linux ARP table pseudo-file)
# to get the MAC address of the target host from the ARP table. If the
# target host responded to the ARP probe then it will be found there,
# and this code will capture it. I believe that any host that does *not*
# respond to ARP requests simply cannot receive IP traffic at all. So I
# believe all hosts on the LAN will be discovered with this approach.
#
# Written by Glen Darling (mosquito@darlingevil.com), December 2022.
#
FROM ubuntu:latest

# Install required stuff
RUN apt update && apt install -y python3 python3-pip iputils-ping
RUN pip3 install flask waitress

# Setup a workspace directory
RUN mkdir /lanscan
WORKDIR /lanscan

# Install convenience tools (may omit these in production)
# RUN apt install -y curl jq

# Copy over the netmon files
COPY ./lanscan.py /lanscan

# Start up the daemon process
CMD python3 lanscan.py >/dev/null 2>&1

