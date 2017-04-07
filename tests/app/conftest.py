import json
from uuid import uuid4

import pytest

from flask import request_started, request as flask_request
from werkzeug.routing import MapAdapter


@pytest.yield_fixture(autouse=True)
def trace_urls(request):
    app_requests = []

    @request_started.connect
    def _request_started_listener(*args, **kwargs):
        app_requests.append({
            "endpoint": flask_request.endpoint,
            "path": flask_request.path,
            "method": flask_request.method,
            "url_pattern": str(flask_request.url_rule),
            "view_args": flask_request.view_args,
            "url_fors": [],
        })

    original_build = MapAdapter.build
    def _dummy_build(*args, **kwargs):
        app_requests[-1]["url_fors"].append({
            "endpoint": args[1],
            "kwargs": args[2],
        })
        return original_build(*args, **kwargs)
    MapAdapter.build = _dummy_build

    yield

    MapAdapter.build = original_build

    if app_requests:
        with open("/home/bob/code/gds/dmp/scratch/view_graph/supplier_app_01/{}.json".format(uuid4()), "w") as outfile:
            json.dump(app_requests, outfile, default=lambda x: repr(x))
