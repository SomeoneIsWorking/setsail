# setsail

The Legend of Zelda: The Wind Waker HD on Linux, presenting at 60 Hz.

The game simulates at 30 Hz and there is no working community 60 fps pack for it,
because raising the tick rate breaks the simulation. setsail instead renders real
in-between frames: it replays the frame's own draw stream with the camera and actor
transforms blended between the previous and current simulation tick. The simulation is
untouched; only presentation rate changes.

- Epic intent: [`docs/project-goals.md`](docs/project-goals.md)
- What actually works today: [`docs/project-state.md`](docs/project-state.md)
- Who owns what: [`docs/codemap.md`](docs/codemap.md)
- The conformance target: [`docs/title-identity.md`](docs/title-identity.md)

The runtime comes from [`wiiuport`](../wiiuport), a fork of
[Cemu](https://github.com/cemu-project/Cemu) (MPL-2.0).

**You supply the game.** setsail ships no game files, keys, or anything derived from
them. It asks for your own Wind Waker HD disc image on first run.
