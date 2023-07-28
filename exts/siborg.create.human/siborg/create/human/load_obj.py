import os
import numpy as np

# Do what you need for file data
filename = 'base.obj'
script_directory = os.path.dirname(os.path.realpath(__file__))
filename = os.path.join(script_directory, filename)

# Read the file
with open(filename, 'r') as f: data = f.readlines()

# Remove comments
newdata = [x.rstrip('\n').split() for x in data if '#' not in x]
verts = np.asarray([x[1:] for x in newdata if x[0]=='v'], float)
idx = np.arange(len(verts))
uv = np.asarray([x[1:] for x in newdata if x[0]=='vt'], float)
face = np.asarray([x[1:] for x in newdata if x[0]=='f']) # This should fail if it creates a ragged array
face = np.apply_along_axis(lambda x: [y.split('/') for y in x], 0, face)
# Get the face number without vertex coordinate
face = np.asarray(face[:,0,:], int)

print(face)

# print(verts)
# print(idx)


with open(filename, 'r') as infile:
    lines = infile.readlines()

vertices = []
uvs = []
normals = []
faces = []
nface_verts = []

for line in lines:
    parts = line.strip().split()
    if parts[0] == 'v':
        vertices.append(tuple(parts[1:]))
    elif parts[0] == 'vt':
        uvs.append(parts[1:])
    elif parts[0] == 'vn':
        normals.append(parts[1:])
    elif parts[0] == 'f':
        if nPerFace:
            if nPerFace > len(parts[1:]):
                raise ValueError(f'Face has less than {nPerFace} vertices')
            faces.append(parts[1:nPerFace+1])  # Only consider the first nPerFace vertices
            nface_verts.append(nPerFace)
        else:
            faces.append(parts[1:]) # Consider all vertices
            nface_verts.append(len(parts[1:]))

# Flat lists of face vertex indices
vert_indices = []
uv_indices = []
normal_indices = []

for face in faces:
    for i in range(len(face)):
        vert_indices.append(int(face[i].split('/')[0]) - 1)
        if uvs:
            uv_indices.append(int(face[i].split('/')[1]) - 1)
        if normals:
            normal_indices.append(int(face[i].split('/')[2]) - 1)

# # convert to Gf.Vec3f
# vertices = [Gf.Vec3f(*map(float, v)) for v in vertices]
# uvs = [Gf.Vec2f(*map(float, uv)) for uv in uvs]

# return MeshData(vertices, uvs, normals, faces, vert_indices, uv_indices, normal_indices, nface_verts)
