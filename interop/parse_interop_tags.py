import re
import os
import sys
import json

def is_valid_option(option):
    return ("req" in option and "req-id" in option and "req-type" in option)

def create_test_from_option(option):
    assert(is_valid_option(option))
    return {
        "name": option["req"],
        "id": option["req-id"],
        "kind": option["req-type"],
    }

def create_test_summary_from_options(fname, options):
    valid_options = filter(lambda option : is_valid_option(option), options)
    tests = [create_test_from_option(option) for option in valid_options]
    data = {
        "name": draft_title(fname),
        "id": draft_to_test_name(fname),
        "description": "Interoperability test results for " + draft_title(fname),
        "tests": tests,
    }
    return data

def draft_to_test_name(fname):
    return os.path.basename(fname).split(".")[0] + ".mjs"

def draft_title(fname):
    with open(fname, "r") as fh:
        return re.search(r'title: (.*?)\n', fh.read()).group(1).strip()

def parse_options_from_draft(draft_name):
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
        return options

def parse_options(draft_name, output_path):
    options = parse_options_from_draft(draft_name)
    test_summary = create_test_summary_from_options(draft_name, options)
    with open(os.path.join(output_path, draft_to_test_name(draft_name)), "w") as fh:
        fh.write("export default\n")
        fh.write(json.dumps(test_summary, indent=4))

if __name__ == '__main__':
    draft_name = sys.argv[1]
    output_path = sys.argv[2]
    parse_options(draft_name, output_path)