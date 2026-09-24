# setsail — codemap

Ownership and placement only. Status is in `docs/project-state.md`.

## Dependency direction

```
setsail
  -> wiiuport      (Wii U runtime; frame record/replay with substituted state)
  -> shared/setup-ui  (first-run picker for the player's disc image)
  -> lucent           (logging, layered configuration, HTTP)
```

setsail never reimplements runtime, GPU, record/replay, or control-channel mechanics.
`wiiuport` never contains Wind Waker HD's identity, transform layout, or blend rules.

## Responsibility owners

| Responsibility | Owner | Notes |
|---|---|---|
| Title identity facts and their validation | `docs/title-identity.md` + `src/setsail/title/` | The document is the source of truth; code reads it, and does not scatter bare literals. |
| Which submitted render state is a camera transform | `src/setsail/renderstate/` | Recovered from the running game, with provenance recorded per slot. |
| Which submitted render state is an actor transform, and object identity across ticks | `src/setsail/renderstate/` | An object that cannot be matched across ticks is presented un-blended and counted; it is never blended against a different object. |
| Blend policy (what is interpolated, at what phase, what is excluded) | `src/setsail/interp/` | Supplied to `wiiuport`'s title-neutral substitution interface. |
| First-run setup wording and acceptance rules | `src/setsail/setup/` | Mechanics come from `shared/setup-ui`. |
| Save and settings location | `src/setsail/config/` | OS user-data location; never the checkout or an AppImage mount. Also the single owner of environment reads. |
| The player's package | `tools/setsail/appimage.py`, entry `tools/package_appimage.py` | Asset-free AppImage of the runtime: bundles what a desktop cannot be assumed to have, a launcher fixing the product's name and title, and a start-up check that the package refuses another title as the runtime does. Tested in `tests/test_appimage.py`. |
| Launcher | `run.sh` -> `bootstrap.py` | Zero-argument path launches the game. Diagnostics and verification are separate named Python tools and never route through it. |

## Where interpolation splits between the two projects

`wiiuport` answers *how* a frame is recorded, how recorded dwords are substituted, and
how the replayed frame is presented. setsail answers *which* dwords mean a camera or an
actor, *how* two ticks' values are blended, and *when* blending must be refused.
