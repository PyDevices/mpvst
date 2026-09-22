# The engine build symlinks this directory into cmods; the workspace manifest
# includes it, and this line is what compiles the C (MicroPython 1.29 c_module()).
c_module(".")  # this directory holds the micropython.cmake / micropython.mk for the C half
