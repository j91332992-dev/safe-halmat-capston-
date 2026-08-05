from . import anchors, audio, button, camera, dashboard, devices, diagnostics, events, layout, risk, system, uwb, workers, zones

ALL_ROUTERS = [
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
    events.router,
    diagnostics.router,
    system.router,
    dashboard.router,
]

