from . import anchors, audio, auth, button, camera, dashboard, devices, diagnostics, evacuation, events, layout, risk, system, uwb, workers, zones

ALL_ROUTERS = [
    auth.router,
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



