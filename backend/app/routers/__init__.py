from . import anchors, audio, button, camera, dashboard, devices, diagnostics, events, risk, system, uwb, zones

ALL_ROUTERS = [
    devices.router,
    camera.router,
    audio.router,
    button.router,
    uwb.router,
    anchors.router,
    zones.router,
    risk.router,
    events.router,
    diagnostics.router,
    system.router,
    dashboard.router,
]

