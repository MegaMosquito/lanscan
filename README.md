# lanscan -- an IP LAN host discovery tool

This code creates a Docker container that provides basic HTTP and JSON REST API services that return snapshots of all hosts currently found on an IP LAN. The results are
JSON-encoded and provide the UTC timestamp of the snapshot and a list of all
hosts on the IP LAN (providing the LAN IP address and MAC address for each).

## Configuring the REST Service:

Before starting this REST service you may **optionally** configure your shell environment with hard-coded values for the configuration variables described in this section. If you do so, the container will use the values you set in your environment. Otherwise the `Makefile` will use its default values for these variables, some of which are computed using standard Linux tools. This calculation should work for Linux hosts, but will fail on MacOS or Windos hosts.

To check what values will be actually used by `make`, run `make chkvars` (this will show either the values you have manually set if they exist, or the values that the Makefile discovers by examining your **default route** using standard Linux tools).

The `Makefie`-computed values include:

- **MY_SUBNET_CIDR** (network `CIDR` to scan, e.g., "192.168.1.0/24"), and/or
- **MY_HOST_IPV4** this scanning host's IPV4 address (in dotted decimal), and/or
- **MY_HOST_MAC** this scanning host's MAC address (in colon-separated hex)

Why are the host IPv4 address and MAC address being specified here (computed or manually specified by you)? Well, that's simple. This technique does not discover the host sending these probes, and since the code runs inside a docker container, it's tricky to get this information from the host. So I require it to be passed in (and I provide code in the Makefile to get the info for you, assuming you are running on a Linux host).

Other values you may choose to override include the base URL for the REST service (**MY_REST_API_BASE_URL**), and/or the host port that the REST servcie binds to (**MY_REST_API_PORT**).

For performance tuning, you may want to override the number of Python `multiprocessing`-module processes the code will spawn (**MY_NUM_PROCESSES**). Otherwise my default values will be used. In general more processes is better for faster convergence to discovery of the full set of MACs on your LAN, but there are tradeoffs. Processes take longer than threads to spawn at the start of the program and each process uses memory and creates CPU load on the host. In my home I run this on a Raspberry Pi 3B+, running the 64-bit Raspberry Pi OS "lite" release 11 (based on debian bullseye). I use the default of **40 processes** and the code takes about 19 seconds to complete a snapshot scanning all 253 IP addresses in my "/24" LAN which typically has about 100 hosts online. With 20 processes, scans take about 36 seconds. With 51 processes, scans take about 16 seconds. You may wish to experiment with different numbers of processes to tune things for your environment.

## Starting the service:

To start up the service, cd into this directory and execute this command:

```
make
```

Or you can manually do the 2 steps that command does, to first build the container then run it, by using the two steps below:

```
make build
make run
```

## Using the HTML Service:

Once the container is running, you can point your browser at this host to receiv basic HTML output, listing the IP addresses and MAC addresses of all hosts found on the LAN. It will look something like this:

```
DarlingEvil LAN Scanner
IPv4	MAC
192.168.123.1	3c:37:86:5e:ec:37
192.168.123.2	14:59:c0:93:19:f1
192.168.123.3	00:50:b6:13:d4:18
192.168.123.4	c4:04:15:19:f6:15
...
```

That is, just very basic/rudamentary unformatted HTML text output. You may wish to use my companion [https://github.com/MegaMosquito/monitor](https://github.com/MegaMosquito/monitor) service that continuously calls the JSON REST API provided by this service and formats its results more nicely. You can edit the CSS of that service to customize its appearance.

## Using the JSON REST API Service:

Once the container is running, you may use this command to test it and get a list of all of the hosts (IP and MAC addresses) discovered on the LAN, encoded in JSON:

```
make test
```

If you have a JSON parsing tool like `jq` installed, you may wish to pipe the output through that:

```
make test | jq .
```

You should see something like this as a result (after waiting a few seconds, long enough for at least one scan to have completed in the daemon):

```
pi@netmon:~/git/scanner $ make test | jq .
{
  "time": {
    "utc": "2022-11-29 06:15:40",
    "prep_sec": 0.5914,
    "scan_sec": 18.293,
    "total_sec": 18.8844
  },
  "scan": [
    {
      "ipv4": "192.168.123.1",
      "mac": "3c:37:86:5e:ec:37"
    },
    ... more of your hosts listed here ...
  ],
  "count": 93
}
```

These `make` targets just use `curl` to connect to the REST API provided by this service. Look at the Makefile to see how the `test` target implements this (just a single `curl` command). Essentially just append "json" to the BASE_URL when you connect to the REST API port.

A basic `/status` API is also provided and returns JSON. Just append `/status` to the base URL as above to get output similar to this:

```
{
  "status": {
    "last_utc": "2022-11-29 09:10:22",
    "last_time_sec": 19.3626,
    "last_count": 94
  }
}
```

## Some notes on my methodology

This code is intended to replace previous work I have done using `nmap`
([https://github.com/MegaMosquito/LAN2json](https://github.com/MegaMosquito/LAN2json)) and using direct ARP pings ([https://github.com/MegaMosquito/ARPmon](https://github.com/MegaMosquito/ARPmon)), each of which I found had significant problems in production. I also tried using the Linux `arping` tool with poor results. The new approch used here is simpler, faster, and should more reliably collect *all* hosts on the IP LAN than those other approaches.

My methodology here relies on the host's underlying IP stack performing an ARP probe before the ICMP echo request is sent for the `ping` command. My code uses just simple `ping` commands but then it ignores the direct results and instead directly looks into the host's `/proc/net/arp` (the standard GNU/Linux ARP table pseudo-file) to get the MAC address of the target host from the ARP table. If the target host responded to the ARP probe then it will be found there, and this code will capture it. I believe that any host that does *not* respond to ARP requests simply cannot receive IP traffic at all. So I believe all hosts on the LAN will be discovered with this approach.

If you have feedback, or wish to report issues or contribute fixes or improvements, **Issues** and **PRs** are most welcome!

Written by Glen Darling (mosquito@darlingevil.com), November 2022.

