#!/usr/bin/env python3

from skimage.measure import find_contours
import matplotlib.pyplot as plt

import numpy as np

nda = np.array([
    [0.5, 1,   2,   1],
    [0.5, 0.5, 0.5, 1],
    [0.5, 1,   2,   1]
])

#nda = nda - 0.05

contours = find_contours(nda, 0.5)

fig, ax = plt.subplots()
ax.imshow(nda, interpolation='nearest', cmap=plt.cm.gray)
for a in contours:
    ax.plot(a[:, 1], a[:, 0], linewidth=2)

ax.axis('image')
ax.set_xticks([])
ax.set_yticks([])
plt.show()
