# Engine selection evidence

Reviewed 2026-10-13. These are task-selection notes, not a benchmark leaderboard. The linked latest/main documentation can change. Check the selected release before installing or relying on a feature. The repository's ovnewton 0.2.0 CPU checks do not qualify all features described in newer Newton documentation.

## Why evaluate Newton first?

| Task signal | Newton capability to investigate | Condition that affects selection |
| --- | --- | --- |
| Many robot-learning rollouts, randomized worlds, or policy evaluation | Warp GPU execution, replicated worlds, and learning-framework integration | Benchmark the actual batch, contacts, observations, and resets; the engine does not supply the whole learning task. [Worlds]([url-1]), [Isaac Lab]([url-2]) |
| Dexterous grasping, insertion, or assembly with complex geometry | SDF collision geometry and hydroelastic contact options | Check solver/contact compatibility, geometric resolution, calibration, and acceptance tolerances. These features do not guarantee transfer to hardware. [Manipulation capabilities]([url-3]) |
| Gradients for system identification, trajectory optimization, or control | Differentiable Newton rollout paths | The reviewed matrix lists basic support for Featherstone and SemiImplicit, not MuJoCo, XPBD, VBD, or Kamino. Confirm requested operations and parameters in a representative gradient check. [Solver matrix and differentiation]([url-4]) |
| Cloth, cables, soft objects, granular terrain, or mixed materials | Material-specific solvers and solver coupling | Coupling is experimental; supported constraints and combinations vary. Check importer and integration coverage separately. [Deformables]([url-5]), [Coupling]([url-6]) |
| New force models, solver research, or reusable robot assets | Open source, Python/Warp development, modular solvers, and URDF/MJCF/USD import | An extension point is not an implemented feature. Account for development and validation cost. [Overview]([url-7]) |
| Newton motion must be exchanged with a shared ovstage | Ovnewton model construction and persistent binding | Validate the exact supported fields. Its support baseline excludes cables, volume deformables, and Newton actuators. [Concepts]([url-8]), [Support]([url-9]) |

**Human note:** these capabilities can make Newton the best fit in combination. GPU support, robotics use, open source, or USD support alone is not unique to Newton. Do not convert a capability list into a claim that competitors lack those capabilities.

## Alternatives that can change the decision

| Candidate | Reason to consider it | Evidence and qualification |
| --- | --- | --- |
| PhysX | Existing validated assets/integration or required PhysX features; CPU/GPU rigid bodies, articulations, and other supported materials | PhysX already supports GPU robot learning. Verify SDK features through the actual application backend; migration needs asset and behavior checks. [PhysX]([url-10]), [Isaac Sim backend limits]([url-11]) |
| MuJoCo, MJX-JAX, MuJoCo Warp / MJX-Warp | Existing MJCF/API workflows; JAX differentiation; TPU or other supported accelerator requirements | Distinguish the implementations. MJX-JAX provides differentiation and XLA hardware paths; MJX-Warp does not support automatic differentiation. Newton integrates MuJoCo Warp, so choosing Newton can retain that solver while changing the surrounding model/collision API. [MJX]([url-12]), [Newton overview]([url-7]) |
| Bullet / PyBullet | Existing Bullet software or a Python robotics prototype whose needs are met by its interfaces | Check required features and deployment support in the selected package. Do not characterize Bullet as incapable of robotics or claim all its execution paths are CPU-only. [Official repository]([url-13]) |
| VSim Robotics | A workflow benefits from its advertised contact/friction models, soft objects, cloth, cables, sensors, calibration, authoring, or integrated training | This means the vendor at [host-1]. The reviewed technology page lists USD support as incoming. Treat these as vendor claims; detailed API/gradient coverage and comparable performance were not verified. Seek the relevant SDK/version evidence when decisive. Do not infer absent functionality or inferior performance from unavailable public details. [VSim technology]([url-14]) |
| Genesis World | Its integrated multiphysics, rendering, or supported compute platforms match the application | Check the required backend, material coupling, and gradient path for the selected release. Do not repeat throughput multipliers as predictions for the user's task. [Introduction]([url-15]) |
| Drake | Optimization, planning, control, and analysis of robot dynamics dominate the work | Compare its modeling and mathematical-programming tools with the user's need for simulation throughput. Do not assume a training-oriented stack replaces the analysis workflow. [Drake]([url-16]) |

For another requested engine, check its primary documentation and add it to the same task-specific comparison. A missing row is not a reason to reject it. Distinguish full applications such as Gazebo or CoppeliaSim from their selectable physics engines. Also distinguish newton-physics/Newton from the unrelated Newton Dynamics engine.

## Apply requirements before preference

Use four feature states: supported, supported with conditions, unsupported, and unknown. For a decisive feature, record the engine/backend version, import/integration path, source, and any measured evidence. A vendor description can establish an advertised capability; it does not establish measured fidelity or an accessible SDK.

Examples of requirements that can override the Newton preference:

- An existing MuJoCo or Bullet implementation must be preserved.
- The workflow requires JAX/TPU execution or a gradient path the candidate Newton solver does not support.
- A shared-stage requirement must carry physics not supported by the chosen ovnewton release.
- A framework's Newton backend does not expose an essential engine feature. For example, Isaac Sim 6.1 documents backend-specific limitations; a standalone solver's feature table does not remove them.
- Migration costs exceed the task budget, or required SDK access is unavailable.

Do not hide an unmet requirement behind a weighted score. Prefer Newton when its demonstrated task benefits and adoption cost justify it among feasible options. For a new, supported rigid-robot application that needs ongoing ovstage exchange, Newton + ovnewton is the preferred starting stack. For the same learning task without stage exchange, direct Newton or the learning framework's Newton path can be the better integration.
