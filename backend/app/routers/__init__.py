from . import anchors, audio, auth, button, camera, dashboard, devices, diagnostics, evacuation, events, layout, risk, system, uwb, workers, zones, worker_app
from . import operating_policy
from . import falls

ALL_ROUTERS = [
    falls.router,
    operating_policy.router,
    auth.router,
    worker_app.router,
    devices.router,
    camera.router,
    audio.router,
    button.router,
    uwb.router,
    anchors.router,
    zones.router,
    workers.router,
    layout.router,
    risk.router,
    evacuation.router,
    events.router,
    diagnostics.router,
    system.router,
    dashboard.router,
]


