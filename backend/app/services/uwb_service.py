def measurements_to_dict(measurements) -> list[dict]:
    return [
        {"anchor_id": item.anchor_id, "distance_m": item.distance_m, "quality": item.quality}
        for item in measurements
    ]

