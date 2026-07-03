"""
Used only if no GPS file is provided. Real visual localization (matching
drone footage against satellite imagery) is a substantial AI project on
its own — this is left as a placeholder so the rest of the app works
end-to-end without it.
"""

def estimate_location(frame, candidate_region=None) -> tuple | None:
    return None