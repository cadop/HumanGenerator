import os
import numpy as np

# Do what you need for file data
filename = 'l-foot-scale-decr.target'
script_directory = os.path.dirname(os.path.realpath(__file__))
filename = os.path.join(script_directory, filename)

# Read the file
with open(filename, 'r') as f: data = f.readlines()

# Remove comments
newdata = [x.rstrip('\n').split() for x in data if '#' not in x]
# Get it as a numpy array
newdata = np.asarray(newdata, dtype=float)
# Take out the indices
indices = np.asarray(newdata[:,0], int)  # -1 if index at 1 in obj
# Get only the vert modifications
verts = newdata[:,1:]

blendshape = np.zeros((19158,3), dtype=float)
# Assign the indices to the verts
blendshape[indices] = verts


print(blendshape[11438])

np.savetxt('test.csv', blendshape, delimiter=',')
np.save(os.path.join(script_directory, 'text.npy'), blendshape)

ls = np.load(os.path.join(script_directory, 'text.npy'))
# print(ls)