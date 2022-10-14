import makehuman

# Makehuman loads most modules by manipulating the system path, so we have to
# run this before we can run the rest of our makehuman imports
makehuman.set_sys_path()
# skeleton (imported from MakeHuman via path) provides Bone and Skeleton classes
import skeleton