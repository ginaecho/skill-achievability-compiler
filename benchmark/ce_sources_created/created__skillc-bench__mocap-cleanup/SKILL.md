---
name: mocap-cleanup
description: Clean and gap-fill motion-capture trials recorded in Vicon Nexus before biomechanical analysis.
---
# Mocap trial cleanup

1. Open each trial in Vicon Nexus 2 and run the "Reconstruct and Label" pipeline.
2. Fill marker gaps shorter than 10 frames with the Woltring spline fill; flag longer gaps.
3. Export the cleaned trials to C3D in `cleaned/`.
4. Write `cleanup_log.md` listing, per trial, the gaps filled and the gaps flagged.
