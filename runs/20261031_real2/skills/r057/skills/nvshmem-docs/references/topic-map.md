# NVSHMEM Topic Map

Use this map for every NVSHMEM documentation request to route release, installation, application-use, best-practice, and API questions. Fetch selected pages before making technical claims.

- `introduced_in` and `removed_in` are optional feature-family gates
- Gates describe changes within the supported documentation range, currently NVSHMEM 3.0 and newer. Do not encode gates below that range.
- Unprefixed `MAJOR.MINOR` values apply to NVSHMEM; prefix Python-only full-version gates with `nvshmem4py:`.
- A dash means that no boundary is asserted. Every populated gate must cite direct official release-note evidence.
- For an NVSHMEM gate, a patch release is evidence for the feature family and is not part of the gate; preserve the full version for an NVSHMEM4Py gate.
- Gates apply to the named feature family, not automatically to every identifying symbol; verify an exact symbol in the requested edition.

| Topic and identifying terms | Primary current page | Stable fallback | Inspect for | `introduced_in` | `removed_in` | Gate evidence |
| --- | --- | --- | --- | --- | --- | --- |
| Documentation home, top-level navigation | [NVSHMEM documentation]([url-1]) | Same page | Installation, release-note, and best-practice entry points | — | — | — |
| Current release, features, compatibility, limitations, known issues | [Release Notes]([url-2]) | [Documentation home]([url-1]) | Current version-specific release note | — | — | — |
| Older release, introduction, deprecation, breaking change, fixed issue | [Prior Releases]([url-3]) | [Older Prior Releases]([url-4]) | Matching version notes and feature boundaries | — | — | — |
| Hardware, software, system, CUDA, compiler, network, launcher requirements | [Installation Guide]([url-5]) | [Documentation home]([url-1]) | Requirements and compatibility prerequisites | — | — | — |
| Download, package installation, archive, Ubuntu, APT, DEB, RHEL, RPM, YUM, DNF, tarball | [Installation]([url-6]) | [Installation Guide]([url-5]) | Package selection and installation procedures | — | — | — |
| NVIDIA HPC SDK or NGC container, `[host-1]`, Docker, Apptainer, Singularity, development image, runtime image | [NVIDIA HPC SDK NGC container]([url-7]) | [NVIDIA HPC SDK documentation]([url-8]) | Current image tags, devel/runtime choice, container requirements, and links to the current container guide; do not infer the bundled NVSHMEM version from the tag | — | — | — |
| Build NVSHMEM itself, source build, CMake build variables, packages, dependency support | [Installation]([url-6]) | [Installation Guide]([url-5]) | Library build system and optional dependencies | — | — | — |
| GDAKI, IBGDA, GPUNetIO requirements, Mellanox, DMA-BUF, peer-memory, DOCA SDK | [Installation Guide]([url-5]) | [Installation]([url-6]) | Transport prerequisites and optional dependencies; apply the feature gates below before using current requirements for older releases | — | — | — |
| Build with IBGDA or GPUNetIO, `NVSHMEM_IBGDA_SUPPORT`, `NVSHMEM_GPUNETIO_SUPPORT` | [Installation]([url-6]) | [Installation Guide]([url-5]) | Transport build options; apply the feature gates below before using current options for older releases | — | — | — |
| Compile or link an NVSHMEM program, `nvcc`, `-rdc`, headers, host/device libraries | [Compiling NVSHMEM Programs]([url-9]) | [Using NVSHMEM]([url-10]) | Application compiler and linker commands, required libraries, and transport-specific link flags | — | — | — |
| Build an application or library that uses NVSHMEM, CMake, `find_package`, shared library, symbol visibility | [Building NVSHMEM Applications/Libraries]([url-11]) | [Using NVSHMEM]([url-10]) | CMake integration, host/device library linkage, and library-composition constraints | — | — | — |
| Run or launch an NVSHMEM program, `mpirun`, `srun`, `nvshmrun`, Hydra, PMI, PMIx | [Running NVSHMEM Programs]([url-12]) | [Using NVSHMEM]([url-10]) | Application launch procedures and process-manager selection | — | — | — |
| NVSHMEM4Py installation, Python, pip, wheel, conda | [Installing NVSHMEM Language Bindings for Python]([url-13]) | [Installation Guide]([url-5]) | Python requirements and installation methods; inspect compatibility only for a versioned request | — | — | — |
| Support, report a problem, security issue | [Support]([url-14]) | [Documentation home]([url-1]) | Official support and reporting paths | — | — | — |
| Introduction, features, transports, PGAS | [Introduction]([url-15]) | [API guide]([url-16]) | Conceptual overview | — | — | — |
| Examples of use, MPI/OpenSHMEM interoperability, communication model | [Using NVSHMEM]([url-10]) | [API guide]([url-16]) | General application usage | — | — | — |
| GPU-initiated NIC transport capability, current GDAKI terminology, historical GIC, CPU-proxy bypass | [Using GPUDirect Async Kernel-Initiated Communication]([url-17]) | [Using NVSHMEM]([url-10]) | GDAKI concepts and prerequisites | — | — | — |
| IBRC remote transport, `NVSHMEM_REMOTE_TRANSPORT=ibrc`, InfiniBand or RoCE, native atomics, GDRCopy, `NVSHMEM_DISABLE_IB_NATIVE_ATOMICS`, `NVSHMEM_DISABLE_GDRCOPY`, `NVSHMEM_IB_*` | [Environment Variables]([url-18]) | [Installation Guide]([url-5]) | IBRC selection and IB/ROCE runtime settings | — | — | — |
| IBDEVX remote transport, `NVSHMEM_REMOTE_TRANSPORT=ibdevx`, `libmlx5` | [Environment Variables]([url-18]) | [Compiling NVSHMEM Programs]([url-9]) | IBDEVX selection and application link requirements | — | — | — |
| IBGDA name and configuration, InfiniBand GPUDirect Async, `NVSHMEM_IB_ENABLE_IBGDA`, `NVSHMEM_IBGDA_*` | [Environment Variables]([url-18]) | [Using GPUDirect Async Kernel-Initiated Communication]([url-17]) | IBGDA runtime settings | — | — | — |
| GPUNetIO remote transport and GDAKI mode, `NVSHMEM_REMOTE_TRANSPORT=gpunetio`, `NVSHMEM_GPUNETIO_ENABLE_GDAKI`, `NVSHMEM_GPUNETIO_*` | [Environment Variables]([url-18]) | [Using GPUDirect Async Kernel-Initiated Communication]([url-17]) | GPUNetIO transport selection and runtime settings | `3.7` | — | [NVSHMEM 3.7.0 release notes]([url-19]) |
| Libfabric remote transport, `NVSHMEM_REMOTE_TRANSPORT=libfabric`, `NVSHMEM_LIBFABRIC_PROVIDER`, `NVSHMEM_LIBFABRIC_*`, EFA, CXI, verbs | [Environment Variables]([url-18]) | [Installation Guide]([url-5]) | Libfabric selection, provider, and runtime settings | — | — | — |
| UCX remote transport, `NVSHMEM_REMOTE_TRANSPORT=ucx`, `UCX_HOME`, `libucs`, `libucp` | [Environment Variables]([url-18]) | [Compiling NVSHMEM Programs]([url-9]) | UCX selection and application link requirements | — | — | — |
| Best-practice overview | [NVSHMEM Best Practices Guide]([url-20]) | [Documentation home]([url-1]) | Best-practice topic selection | — | — | — |
| Initialization, bootstrap, MPI, OpenSHMEM, UID | [NVSHMEM Initialization]([url-21]) | [Best Practices Guide]([url-20]) | Initialization choices and guidance | — | — | — |
| Device, host, on-stream, thread, warp, block APIs | [Device APIs]([url-22]) | [Best Practices Guide]([url-20]) | API execution scopes and usage guidance | — | — | — |
| GDAKI device API behavior, IBGDA and GPUNetIO GDAKI, transport-aware RMA | [Device APIs]([url-22]) | [Using NVSHMEM]([url-10]) | GDAKI-specific device API guidance; apply transport gates before using it for older releases | — | — | — |
| CUDA stream, CUDA interoperability, circular dependency, ordering | [CUDA NVSHMEM Interoperability]([url-23]) | [NVSHMEM and the CUDA Model]([url-24]) | CUDA and NVSHMEM interaction guidance | — | — | — |
| Runtime configuration, symmetric heap, transport selection | [NVSHMEM Runtime Configuration]([url-25]) | [Environment Variables]([url-18]) | High-level runtime configuration guidance | — | — | — |
| Unsupported API, operation, transport restriction | [NVSHMEM Unsupported Operations]([url-26]) | [Overview of the APIs]([url-27]) | Unsupported and restricted behavior | — | — | — |
| Performance, coalescing, message size, quiet, synchronization cost | [NVSHMEM Performance]([url-28]) | [Best Practices Guide]([url-20]) | Performance practices and tradeoffs | — | — | — |
| IBGDA performance, QP type, DCI, RC, queue-pair tuning | [NVSHMEM Performance]([url-28]) | [Environment Variables]([url-18]) | IBGDA queue-pair tuning; apply the IBGDA gate before using current settings for older releases | — | — | — |
| CUDA execution, streams, circular dependencies, cooperative launch | [NVSHMEM and the CUDA Model]([url-24]) | [API guide]([url-16]) | CUDA execution semantics | — | — | — |
| TMA, `NVSHMEM_TMA_POLICY`, `nvshmemx_ask_smem`, `nvshmemx_give_smem`, `nvshmemx_release_smem` | [Using TMA with NVSHMEM]([url-29]) | [API guide]([url-16]) | TMA use and constraints | `3.7` | — | [NVSHMEM 3.7.0 release notes]([url-19]) |
| Symmetric objects, operation ordering, atomicity, OpenSHMEM differences | [Memory Model]([url-30]) | [API guide]([url-16]) | Memory-model semantics | — | — | — |
| Progress, invocation, host/on-stream/device execution | [Execution Model]([url-31]) | [API guide]([url-16]) | Execution-model semantics | — | — | — |
| Constants, comparison operators, thread levels, team constants | [Library Constants]([url-32]) | [API guide]([url-16]) | Constant definitions | — | — | — |
| Handles, teams, initialization attributes, QP handles | [Library Handles]([url-33]) | [API guide]([url-16]) | Handle definitions | — | — | — |
| Environment variables, bootstrap, collectives, transport, NVTX, `NVSHMEM_*` setting | [Environment Variables]([url-18]) | [API guide]([url-16]) | Runtime option names, types, and defaults | — | — | — |
| Supported APIs, unsupported OpenSHMEM APIs, CPU/GPU extensions, tile APIs | [Overview of the APIs]([url-27]) | [API guide]([url-16]) | API-family overview | — | — | — |
| Initialize, finalize, query, UID, MPI communicator, `nvshmem_init`, `nvshmemx_init_attr`, thread support | [Library Setup, Exit, and Query]([url-34]) | [API overview]([url-27]) | Setup and teardown APIs | — | — | — |
| Cooperative kernel launch, grid size, `nvshmemx_collective_launch` | [Kernel Launch Routines]([url-35]) | [API overview]([url-27]) | Kernel launch APIs | — | — | — |
| Symmetric allocation, malloc, calloc, free, align, buffer registration | [Memory Management]([url-36]) | [API overview]([url-27]) | Allocation and registration APIs | — | — | — |
| QP-specific APIs, qpair, queue pair handle, `nvshmemx_qp_*`, `nvshmemx_qp_handle_t`, `NVSHMEMX_QP_*` | [Queue Pair Specific APIs]([url-37]) | [API overview]([url-27]) | QP creation, RMA, signaling, and ordering APIs | `3.5` | — | [NVSHMEM 3.5.19 release notes]([url-38]) |
| Teams, split, translate PE, team creation/destruction, `nvshmem_team_*` | [Team Management]([url-39]) | [API overview]([url-27]) | Team APIs | — | — | — |
| Put, get, p, g, iput, iget, NBI, tile RMA | [Remote Memory Access]([url-40]) | [API overview]([url-27]) | RMA APIs | — | — | — |
| Atomic, fetch, set, compare-swap, swap, inc, add, and/or/xor | [Atomic Memory Operations]([url-41]) | [API overview]([url-27]) | Atomic APIs | — | — | — |
| Signal, put-with-signal, signal fetch, signal operator | [Signaling Operations]([url-42]) | [API overview]([url-27]) | Signaling APIs | — | — | — |
| Barrier, sync, all-to-all, broadcast, fcollect, reduction, tile collective | [Collective Communication]([url-43]) | [API overview]([url-27]) | Collective APIs | — | — | — |
| Wait, test, wait-until, signal-wait-until, point-to-point synchronization | [Point-To-Point Synchronization]([url-44]) | [API overview]([url-27]) | Synchronization APIs | — | — | — |
| Fence, quiet, flush, completion, visibility, source-buffer reuse | [Memory Ordering]([url-45]) | [Memory Model]([url-30]) | Ordering and completion APIs | — | — | — |
| NVSHMEM4Py, Python bindings, Python device API, Python interoperability | [Language Bindings]([url-46]) | [API guide]([url-16]) | Latest Python API documentation | — | — | — |
| NVSHMEM4Py package version, compatible NVSHMEM version, version pair, compatibility | [NVSHMEM4Py Overview and Compatibility Guide]([url-47]) | [Language Bindings]([url-46]) | Live NVSHMEM-to-NVSHMEM4Py compatibility table | — | — | — |
| Sample code, initialization, on-stream, threadgroup, ring, registration, Python examples | [Examples]([url-48]) | [API guide]([url-16]) | Example selection | — | — | — |
| FAQ, prerequisites, running, MPI/OpenSHMEM interoperability, GPU interconnect, debugging | [Troubleshooting and FAQs]([url-49]) | [API guide]([url-16]) | Troubleshooting guidance | — | — | — |

## Exact-Symbol and Tool Routing

| Symbol or term pattern | Route to |
| --- | --- |
| `nvcc`, `-rdc`, or `libnvshmem_*` in program compilation context | Compile or link an NVSHMEM program |
| `find_package`, CMake application/library integration, or shared-library symbol visibility | Build an application or library that uses NVSHMEM |
| `mpirun`, `srun`, `nvshmrun`, Hydra, PMI, or PMIx in application launch context | Run or launch an NVSHMEM program |
| `[host-1]`, HPC SDK container, NGC container, Docker, Apptainer, or Singularity in installation context | NVIDIA HPC SDK or NGC container |
| `nvshmem_init*`, `nvshmem_finalize`, `nvshmem_global_exit`, `nvshmem*_info*`, `nvshmemx_*uniqueid*` | Library Setup, Exit, and Query |
| `nvshmem_malloc`, `nvshmem_calloc`, `nvshmem_align`, `nvshmem_free`, `nvshmemx_buffer_*` | Memory Management |
| `nvshmemx_qp_*`, `nvshmemx_qp_handle_t`, or `NVSHMEMX_QP_*` | Queue Pair Specific APIs |
| `GDAKI`, `GPUDirect Async Kernel-Initiated`, historical `GIC`, or GPU-initiated NIC communication | GDAKI overview; also inspect Device APIs and NVSHMEM Performance topics in this map |
| `IBRC`, `NVSHMEM_REMOTE_TRANSPORT=ibrc`, `NVSHMEM_DISABLE_IB_NATIVE_ATOMICS`, `NVSHMEM_DISABLE_GDRCOPY`, or `NVSHMEM_IB_*` | IBRC remote transport; also inspect its installation requirements |
| `IBDEVX` or `NVSHMEM_REMOTE_TRANSPORT=ibdevx` | IBDEVX remote transport; also inspect application link requirements |
| `IBGDA`, `NVSHMEM_IB_ENABLE_IBGDA`, or `NVSHMEM_IBGDA_*` | IBGDA name and configuration; also inspect its requirements, build, and performance topics |
| `GPUNetIO`, `NVSHMEM_REMOTE_TRANSPORT=gpunetio`, or `NVSHMEM_GPUNETIO_*` | GPUNetIO remote transport and GDAKI mode; also inspect its requirements and build topics |
| `libfabric`, `NVSHMEM_REMOTE_TRANSPORT=libfabric`, or `NVSHMEM_LIBFABRIC_*` | Libfabric remote transport; also inspect its installation requirements |
| `UCX`, `NVSHMEM_REMOTE_TRANSPORT=ucx`, `UCX_HOME`, `libucs`, or `libucp` | UCX remote transport; also inspect application link requirements |
| `nvshmem_team_*`, `nvshmemx_team_*` | Team Management |
| Put/get families, including `p`, `g`, strided, nonblocking, and tile variants | Remote Memory Access |
| Names containing `atomic` | Atomic Memory Operations |
| Put-with-signal and signal update/fetch operations | Signaling Operations |
| Barrier, sync, all-to-all, broadcast, collect, and reduction operations | Collective Communication |
| Wait and test operations | Point-To-Point Synchronization |
| Fence, quiet, and flush operations | Memory Ordering |
| `NVSHMEM_*` runtime setting | Environment Variables |
| NVSHMEM4Py or Python API without a version | Language Bindings; also inspect NVSHMEM4Py installation for package questions |
| NVSHMEM4Py package version, `nvshmem4py_version`, or NVSHMEM/NVSHMEM4Py compatibility | NVSHMEM4Py Overview and Compatibility Guide |
