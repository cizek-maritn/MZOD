# cython: boundscheck=False
# cython: wraparound=False
# cython: nonecheck=False

def c_pixel_sum(unsigned char[:, :]img):
    cdef int height = img.shape[0]
    cdef int width = img.shape[1]
    cdef int i, j
    cdef unsigned long long total_sum = 0

    for i in range(height):
        for j in range(width):
            total_sum += img[i, j]
    return total_sum
