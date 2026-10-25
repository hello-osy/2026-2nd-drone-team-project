"""Image-only horizontal control. Camera +X points down, image top is body +X."""
import math

def velocity(center, width, height, altitude, max_speed=.7):
    if center is None:
        return 0., 0.
    focal = width / (2 * math.tan(1.2 / 2))
    right_error = (center[0] - width/2) * altitude / focal
    forward_error = -(center[1] - height/2) * altitude / focal
    forward, right = .65 * forward_error, .65 * right_error
    speed = math.hypot(forward, right)
    if speed > max_speed:
        forward, right = forward*max_speed/speed, right*max_speed/speed
    return forward, right

def fresh(observation_time, now, limit=.8):
    return observation_time > 0 and 0 <= now - observation_time < limit
