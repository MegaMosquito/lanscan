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

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'

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
last_scan_total_sec = "0.0"
last_scan_host_count = 0
last_scan_html = '<p>(just starting up)</p>'

# Return status info
def get_status ():
  return '{"status":{"last_utc":"' + last_scan_UTC + '","last_time_sec":' + last_scan_total_sec + ',"last_count":' + str(last_scan_host_count) + '}}\n'

# GET: (base URL)/json
@restapi.route(REST_API_BASE_URL + '/json', methods=['GET'])
def base_api ():
  return get_cache()

# GET: (base URL)/status
@restapi.route(REST_API_BASE_URL + '/status', methods=['GET'])
def status_api ():
  return get_status()

# GET: /
@restapi.route('/', methods=['GET'])
def web_page ():
  page = \
    '<html>\n' + \
    '  <head>\n' + \
    '    <title>DarlingEvil LAN Scanner</title>\n' + \
    '  </head>\n' + \
    '  <body>\n' + \
    '    <h2>DarlingEvil LAN Scanner</h2>\n' + \
    last_scan_html + \
    '  </body>\n' + \
    '</html>\n'
  return page

# Prevent caching on all requests
@webapp.after_request
def add_header(r):
  r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
  r.headers["Pragma"] = "no-cache"
  r.headers["Expires"] = "0"
  r.headers['Cache-Control'] = 'public, max-age=0'
  return r

def numeric_ip(k):
  b = k.split('.')
  return int(b[0]) << 24 + \
         int(b[1]) << 16 + \
         int(b[2]) << 8 + \
         int(b[3])

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
    for i in range(1, 255):
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

    # Get the current UTC time too
    utc_now = datetime.now(timezone.utc).strftime(TIME_FORMAT)

    # Compute the phase timing
    times = (
      _wait - _start,
      _end - _wait,
      _end - _start)
    debug('This pass took took {0} seconds.'.format(times[2]))

    # Collect, count and sort the results from the output queue
    results = {}
    while not output.empty():
      try:
        out = output.get_nowait().strip()
        #debug(out)
        j = json.loads(out)
        results[j['ipv4']] = out
      except queue.Empty:
        pass
    # Add this host
    results[MY_HOST_IPV4] = \
      '{"ipv4":"' + MY_HOST_IPV4 + '","mac":"' + MY_HOST_MAC + '"}'
    sorted_ips = sorted(results.keys(), key=lambda k: numeric_ip(k))
    count = len(sorted_ips)

    # Construct HTML and JSON results with IPv4 and MAC info
    temp_h = \
      '    <table>\n' + \
      '      <tr>\n' + \
      '        <th>IPv4</th>\n' + \
      '        <th>MAC</th>\n' + \
      '      </tr>\n'

    # The timing info
    temp_j = '{"time":{'
    temp_j += '"utc":"' + utc_now + '",'
    temp_j += ('"prep_sec":%0.4f' % times[0]) + ','
    temp_j += ('"scan_sec":%0.4f' % times[1]) + ','
    temp_j += ('"total_sec":%0.4f' % times[2])
    temp_j += '},'

    # The scan array
    temp_j += '"scan":['
    for ip_key in sorted_ips:
      out = results[ip_key]
      #debug(out)
      temp_j += out + ','
      j = json.loads(out)
      temp_h += '      <tr><td>' + j['ipv4'] + '</td><td>' + j['mac'] + '</td></tr>\n'
    # Strip trailing comma
    temp_j = temp_j[:-1]
    temp_j += '],'
    temp_h += '    </table>\n'

    # The count of hosts
    temp_j += '"count":' + str(count)

    # All done!
    temp_j += '}'

    # Update globals for the status API
    last_scan_UTC = utc_now
    last_scan_total_sec = ('%0.4f' % times[2])
    last_scan_host_count = count

    # Refrash the JSON cache with this JSON, and HTML cache with this HTML
    cache = temp_j
    last_scan_html = temp_h

    # Highlight the end of this pass in the debug output
    debug('----------------------------------------------------')


