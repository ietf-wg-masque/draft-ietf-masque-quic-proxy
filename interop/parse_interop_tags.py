import re
import os
import sys
import json

'''
export default
{
  name: 'Connect-UDP',
  id: 'connect-udp',
  description: 'Specification support for draft-ietf-masque-connect-udp-00',
  tests: [
    {
      name: 'The client supports CONNECT-UDP over HTTP/3',
      id: 'connect-udp-h3-client',
      kind: 'supported',
    },
    ... 
  ]

  [{'req-id': 'connect-udp-quic-client-cid', 'req': 'Client sends `Client-Connection-Id` in first `CONNECT-UDP` request', 'req-type': 'must'}]
}
'''
def options_to_tests(fname, output_path, options):
    tests = []
    for option in options:
        tests.append({
            "name": option["req"],
            "id": option["req-id"],
            "kind": option["req-type"],
        })
    data = {
        "name": draft_title(fname),
        "id": draft_to_test_name(fname),
        "description": "TBD",
        "tests": tests
    }

    with open(os.path.join(output_path, draft_to_test_name(fname)), "w") as fh:
        fh.write("export default\n")
        fh.write(json.dumps(data, indent=4))

def draft_to_test_name(fname):
    return os.path.basename(fname).split(".")[0] + ".mjs"

def draft_title(fname):
    with open(fname, "r") as fh:
        return re.search(r'title: (.*?)\n', fh.read()).group(1).strip()

draft_name = sys.argv[1]
output_path = sys.argv[2]
with open(draft_name, "r") as fh:
    filedata = fh.read()
    option_pattern = re.compile(r'\{::options(.*?)/\}')
    options = []
    for option in re.findall(option_pattern, filedata):
        data = option.split(" ")
        entry = {}
        pattern = re.compile(r' (.*?)=\"(.*?)\"')
        for k, v in re.findall(pattern, option):
            entry[k] = v
        options.append(entry)
    
    options_to_tests(draft_name, output_path, options)

