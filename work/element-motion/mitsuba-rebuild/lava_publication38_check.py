"""Unapproved diagnostics must not replace the user's current media."""
from lava_mpm import ROOT
from lava_acceptance38 import publish,hot_origin
import json
folder=ROOT/'rebuild-38/hot-nozzle'
target=ROOT/'rebuild-38/publication-guard.fixture';target.write_bytes(b'previous accepted media')
try:publish(folder,ROOT/'rebuild-38/hot-nozzle-30.png',target)
except RuntimeError:pass
else:raise AssertionError('Unreviewed lava replaced public media')
assert target.read_bytes()==b'previous accepted media'
assert hot_origin(folder)
report=dict(status='pass',unapprovedPublicationBlocked=True,previousMediaUnchanged=True,initialHotStateVerified=True)
(ROOT/'rebuild-38/publication-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
