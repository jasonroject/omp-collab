# OMP compatibility boundary

The CLI flags were exercised on OMP 18.8.4 on Windows. The runner uses an argument-array launch with `shell=False` (Python's default). Windows shell wrappers are rejected; POSIX executable scripts are permitted because the OS can invoke their interpreter without interpolating the task into shell source.

`--no-tools` is documented as disabling built-in tools. It is not a complete configuration-discovery switch. OMP may discover MCP, custom tools, user context and ancestor configuration even when the working directory is new. `--no-extensions` also does not mean all discovery is disabled. A trusted OMP installation and configuration are prerequisites; a task instruction saying “do not call tools” is not a sandbox.

The upstream source inspected for this distinction is commit `3a2758b68f7c8e6bdf22c3a76b86c8675e5e0c9e`:

- [CLI options mapping](https://github.com/can1357/oh-my-pi/blob/3a2758b68f7c8e6bdf22c3a76b86c8675e5e0c9e/packages/coding-agent/src/main.ts): `noTools` maps to an empty `toolNames` array.
- [Session construction](https://github.com/can1357/oh-my-pi/blob/3a2758b68f7c8e6bdf22c3a76b86c8675e5e0c9e/packages/coding-agent/src/sdk.ts): strict `restrictToolNames` and MCP discovery are separate; some custom tools may be included independently of the requested built-in tools.
- [Configuration discovery](https://github.com/can1357/oh-my-pi/blob/3a2758b68f7c8e6bdf22c3a76b86c8675e5e0c9e/docs/config-usage.md): user and ancestor sources can be inherited.

This source inspection is distinct from the local CLI test; releases may differ. The metadata records the requested model and disabled-built-in-tools flag, not a provider-attested model identity or verified runtime capability inventory. If strict tool isolation is necessary, use a separately validated restricted OMP host/profile or SDK integration; that setup is outside this first version.
