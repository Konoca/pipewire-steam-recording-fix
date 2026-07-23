# Steam Background Recording fix (PipeWire)

If you are using PipeWire, you can fix Steam background recording to record only the game audio instead of system audio.
This can manually be done using something like qpwgraph.

This script will do it automatically, just duplicate `config.json.example` as `config.json`. You shouldn't need to edit anything except adding additional games under "sources".

Written using python3.11
