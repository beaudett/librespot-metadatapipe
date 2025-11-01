# librespot-metadatapipe
Uses the onevent feature of librespot to create a minimal metadata pipe which can be used with the software masterpiece 
that is [owntone](https://owntone.github.io/owntone-server/)

Based on the discussion [here](https://github.com/librespot-org/librespot/issues/1431), this simple script 
is supposed to be executed through `librespot --onevent=/path/to/my/event/script/program` and writes a few metadata 
to the pipe. 

On `track_changed`, it writes
* Title
* Artist
* Album
* Cover

On `volume` it writes
* Volume


