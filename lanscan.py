#
# lanscan  -- implements an IP LAN host discovery REST API service
#
# Written by Glen Darling (mosquito@darlingevil.com), November 2022.
#

import multiprocessing
import queue
import time
import os
import subprocess
import threading
import logging
import json
from datetime import datetime, timezone
from flask import Flask
from flask import send_file
from waitress import serve

# Basic debug printing
DEBUG = False
def debug (s):
  if DEBUG:
    print(s)

# Get values from the environment or use defaults
def get_from_env(v, d):
  if v in os.environ and '' != os.environ[v]:
    return os.environ[v]
  else:
    return d
MY_SUBNET_CIDR       = get_from_env('MY_SUBNET_CIDR', '')
MY_HOST_IPV4         = get_from_env('MY_HOST_IPV4', '')
MY_HOST_MAC          = get_from_env('MY_HOST_MAC', '')
MY_REST_API_BASE_URL = get_from_env('MY_REST_API_BASE_URL', '/lanscan')
MY_REST_API_PORT     = int(get_from_env('MY_REST_API_PORT', '8003'))
MY_NUM_PROCESSES     = int(get_from_env('MY_NUM_PROCESSES', '40'))

# Validate input
if '' == MY_SUBNET_CIDR or not '.0/' in MY_SUBNET_CIDR:
  raise Exception('Bad value \"{0}\" for MY_SUBNET_CIDR.'.format(MY_SUBNET_CIDR))
if '' == MY_HOST_IPV4 or '' == MY_HOST_MAC:
  raise Exception('Either MY_HOST_IPV4 or MY_HOST_MAC not provided.')

# Setup network prefix string
PREFIX = MY_SUBNET_CIDR[0:MY_SUBNET_CIDR.find('0/')]
debug('PREFIX=' + PREFIX)

# REST API details
REST_API_BIND_ADDRESS = '0.0.0.0'
REST_API_PORT = MY_REST_API_PORT
REST_API_BASE_URL = MY_REST_API_BASE_URL
restapi = Flask('lanscan')

def proc (id, input, output):
  debug('Process id ' + str(id) + ' has started.')
  while True:
    try:
      msg = input.get_nowait()
      addr = PREFIX + str(msg)
      debug('Process id ' + str(id) + ' is acting on "' + addr + '".')
      r = os.system('ping -c 1 ' + addr + ' >/dev/null 2>&1')
      try:
        out = str(subprocess.check_output('grep "^' + addr + ' " /host_arp_table |grep -v "00:00:00:00:00:00" | head -1 | awk \'{print $1 " " $4;}\'', shell=True).decode("utf-8").strip())
        if '' != out:
          tokens = out.split(' ')
          out = '{"ipv4":"' + tokens[0] + '","mac":"' + tokens[1] + '"}'
          output.put(out)
          debug('INFO: adding: "' + out + '"')
      except subprocess.CalledProcessError as e:
        if e.returncode > 1:
          logging.exception('grep command returned: ' + str(e.returncode))
          raise
      except:
        logging.exception('grep command failed.')
        raise
    except queue.Empty:
      # This exception occurs when an item cannot immediately be removed from
      # the queue. This may be because it is empty, BUT it may also be because
      # the queue is busy. So a second check to verify the queue is actually
      # empty is needed here! What a goofy API.
      if input.empty():
        debug('INFO: Process id ' + str(id) + ' has ended.')
        return
      else:
        debug('INFO: queue.Empty exception but queue was not actually empty')
    except:
      logging.exception('process failed.')
      raise

# Global JSON cache
cache = '{}'

# Return the JSON cache
def get_cache ():
  return cache + '\n'

# Global status
last_scan_UTC = '(just starting up)'
last_scan_time_sec = "0.0"
last_scan_host_count = 0

# Return status info
def get_status ():
  return '{"status":{"last_utc":"' + last_scan_UTC + '","last_time_sec":' + last_scan_time_sec + ',"last_count":' + str(last_scan_host_count) + '}}\n'

# GET: (base URL)/json
@restapi.route(REST_API_BASE_URL + '/json', methods=['GET'])
def base_api ():
  return get_cache()

# GET: (base URL)/status
@restapi.route(REST_API_BASE_URL + '/status', methods=['GET'])
def status_api ():
  return get_status()

# Main program (to start the web server thread)
if __name__ == '__main__':

  debug('Creating the input and output queues...')
  input = multiprocessing.Queue()
  output = multiprocessing.Queue()

  debug('Starting the REST API server thread...')
  threading.Thread(target=lambda: serve(
    restapi,
    host=REST_API_BIND_ADDRESS,
    port=REST_API_PORT)).start(),

  # Run the daemon forever
  while True:

    debug('Fill (or refill) the input queue with the target octets (1..254)...')
    for i in range(1, 254):
      input.put(i)

    # Note the time before process creation begins
    _start = time.time()

    debug('Create {0} new processes...'.format(MY_NUM_PROCESSES))
    procs = list()
    for i in range(MY_NUM_PROCESSES):
      p = multiprocessing.Process(target=proc, args=((i),(input),(output),))
      p.daemon = True
      p.start()
      procs.append(p)

    # Note the scan start time once all procs are up and running
    _wait = time.time()

    debug('Wait for all procs to finish...')
    for i, p in enumerate(procs):
      p.join()

    # Note the final end time
    _end = time.time()

    # Compute the process phase timing
    times = (
      _wait - _start,
      _end - _wait,
      _end - _start)

    # Construct the JSON results (adding in the host IPv4 and MAC info)
    utc_now = datetime.now(timezone.utc).isoformat()
    debug('This pass took took {0} seconds.'.format(times[2]))
    temp = '{"time":{'
    temp += '"utc":"' + utc_now + '",'
    temp += ('"prep_sec":%0.4f' % times[0]) + ','
    temp += ('"scan_sec":%0.4f' % times[1]) + ','
    temp += ('"total_sec":%0.4f' % times[2]) + '},'
    temp += '"scan":['
    temp += '{"ipv4":"' + MY_HOST_IPV4 + '","mac":"' + MY_HOST_MAC + '"}'
    c = 1
    while not output.empty():
      try:
        out = output.get_nowait()
        debug(out)
        temp += ',' + out.strip()
        c += 1
      except queue.Empty:
        pass
    temp += ']}'

    # Update globals for the status API
    last_scan_UTC = utc_now
    last_scan_time_sec = ('%0.4f' % times[2])
    last_scan_host_count = c

    # Refrash the cache with this JSON
    cache = temp

    # Highlight the end of this pass in the debug output
    debug('----------------------------------------------------')


